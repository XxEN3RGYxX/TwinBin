import customtkinter as ctk
import tkinter.filedialog as fd
import tkinter.messagebox as mb
import os
import hashlib
import shutil
import threading
import concurrent.futures
from datetime import datetime
import csv
from fpdf import FPDF
from PIL import Image, ImageTk
import sys

# -----------------------------
# Function to handle resource paths when using PyInstaller executable
def resource_path(relative_path):
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.abspath("."), relative_path)
# -----------------------------

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("dark-blue")

class DuplicateManagerApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.iconbitmap(resource_path("trasferimento.ico"))
        self.title("Duplicate File Manager")
        self.geometry("1000x750")
        self.resizable(False, False)

        self.folder_var = ctk.StringVar()
        self.status_var = ctk.StringVar(value="Ready")
        self.sort_criteria = ctk.StringVar(value="Date: Newest first")
        self.duplicates = {}
        self.backup_folder = os.path.join(os.path.expanduser("~"), "duplicate_manager_backup")
        os.makedirs(self.backup_folder, exist_ok=True)

        self.setup_ui()

        self.scan_thread = None
        self.stop_scan = threading.Event()
        self.last_backup = []

    def setup_ui(self):
        frame_top = ctk.CTkFrame(self, corner_radius=12)
        frame_top.pack(fill="x", padx=15, pady=10)

        self.entry_path = ctk.CTkEntry(frame_top, textvariable=self.folder_var, width=550)
        self.entry_path.pack(side="left", padx=10, pady=10, ipady=6)

        btn_browse = ctk.CTkButton(frame_top, text="Browse", width=100, command=self.browse_folder)
        btn_browse.pack(side="left", padx=10, pady=10)

        frame_sort = ctk.CTkFrame(frame_top, corner_radius=12)
        frame_sort.pack(side="left", padx=10)
        ctk.CTkLabel(frame_sort, text="Sort by:").pack(anchor="w")
        sort_dropdown = ctk.CTkOptionMenu(
            frame_sort,
            variable=self.sort_criteria,
            values=[
                "Size: Largest first",
                "Size: Smallest first",
                "Name: A → Z",
                "Name: Z → A",
                "Physically sort by date",
                "Physically sort by type",
                "Physically sort by name"
            ],
            command=lambda _: self.populate_listbox()
        )
        sort_dropdown.pack(anchor="w")

        self.btn_scan = ctk.CTkButton(
            self,
            text="🔍 Scan Duplicates",
            font=ctk.CTkFont(size=16, weight="bold"),
            fg_color="#1E90FF",
            hover_color="#3AA0FF",
            command=self.start_scan_thread
        )
        self.btn_scan.pack(pady=10)
        self.btn_sort_physical = ctk.CTkButton(
            self,
            text="📂 Physically Organize Files",
            font=ctk.CTkFont(size=16, weight="bold"),
            fg_color="#6B8E23",
            hover_color="#7DAE30",
            command=self.organize_files_physically
        )
        self.btn_sort_physical.pack(pady=5)


        self.listbox = ctk.CTkScrollableFrame(self, width=950, height=350, corner_radius=12)
        self.listbox.pack(padx=20, pady=10, fill="both")
        self.file_vars = {}

        frame_buttons = ctk.CTkFrame(self, corner_radius=12)
        frame_buttons.pack(fill="x", padx=20, pady=10)

        ctk.CTkButton(frame_buttons, text="🗑️ Delete Selected", fg_color="#FF6347", hover_color="#FF7F50", command=self.delete_selected).pack(side="left", padx=10, pady=5)
        ctk.CTkButton(frame_buttons, text="📂 Move Selected", fg_color="#4682B4", hover_color="#5A9BD4", command=self.move_selected).pack(side="left", padx=10, pady=5)
        ctk.CTkButton(frame_buttons, text="🛡️ Backup Selected", fg_color="#6A5ACD", hover_color="#836FFF", command=self.backup_selected).pack(side="left", padx=10, pady=5)
        ctk.CTkButton(frame_buttons, text="↩️ Undo Last", fg_color="#DAA520", hover_color="#E0B52E", command=self.undo_last).pack(side="left", padx=10, pady=5)
        ctk.CTkButton(frame_buttons, text="📊 Export CSV", fg_color="#20B2AA", hover_color="#38C7BB", command=self.export_csv).pack(side="left", padx=10, pady=5)
        ctk.CTkButton(frame_buttons, text="📄 Export PDF", fg_color="#32CD32", hover_color="#4CE54C", command=self.export_pdf).pack(side="left", padx=10, pady=5)

        self.preview_frame = ctk.CTkFrame(self, corner_radius=12, width=950, height=200)
        self.preview_frame.pack(padx=20, pady=10, fill="both")

        self.preview_label = ctk.CTkLabel(self.preview_frame, text="File preview will appear here.", anchor="center")
        self.preview_label.pack(expand=True, fill="both")

        self.status_label = ctk.CTkLabel(self, textvariable=self.status_var, anchor="w", font=ctk.CTkFont(size=12))
        self.status_label.pack(fill="x", padx=15, pady=(0,10))

    def browse_folder(self):
        folder = fd.askdirectory()
        if folder:
            self.folder_var.set(folder)

    def update_status(self, text):
        self.status_var.set(text)

    def start_scan_thread(self):
        if self.scan_thread and self.scan_thread.is_alive():
            self.update_status("Scan already in progress...")
            return
        folder = self.folder_var.get()
        if not folder or not os.path.isdir(folder):
            mb.showerror("Error", "Please select a valid folder.")
            return
        self.stop_scan.clear()
        self.duplicates = {}
        self.file_vars.clear()
        self.clear_listbox()
        self.update_status("Starting scan...")
        self.scan_thread = threading.Thread(target=self.scan_folder, args=(folder,))
        self.scan_thread.daemon = True
        self.scan_thread.start()

    def scan_folder(self, folder):
        hash_dict = {}

        def file_hash(filepath):
            try:
                hasher = hashlib.md5()
                with open(filepath, "rb") as f:
                    while True:
                        chunk = f.read(8192)
                        if not chunk or self.stop_scan.is_set():
                            break
                        hasher.update(chunk)
                return filepath, hasher.hexdigest()
            except Exception:
                return filepath, None

        file_list = [os.path.join(root, f) for root, _, files in os.walk(folder) for f in files]
        self.update_status(f"Scanning {len(file_list)} files...")

        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            futures = {executor.submit(file_hash, fp): fp for fp in file_list}
            for future in concurrent.futures.as_completed(futures):
                if self.stop_scan.is_set():
                    self.update_status("Scan cancelled.")
                    return
                filepath, h = future.result()
                if h:
                    hash_dict.setdefault(h, []).append(filepath)

        self.duplicates = {h: files for h, files in hash_dict.items() if len(files) > 1}
        self.update_status(f"Scan complete. Found {len(self.duplicates)} sets of duplicates.")
        self.populate_listbox()

    def clear_listbox(self):
        for widget in self.listbox.winfo_children():
            widget.destroy()

    def populate_listbox(self):
        self.clear_listbox()
        self.file_vars.clear()
        criteria = self.sort_criteria.get()

        for h, files in self.duplicates.items():
            ctk.CTkLabel(self.listbox, text=f"Hash: {h}", font=ctk.CTkFont(weight="bold")).pack(anchor="w", pady=(10,2))

            if "Date" in criteria:
                sorted_files = sorted(files, key=lambda fp: os.path.getmtime(fp), reverse="Newest" in criteria)
            elif "Size" in criteria:
                sorted_files = sorted(files, key=lambda fp: os.path.getsize(fp), reverse="Largest" in criteria)
            elif "Name" in criteria:
                sorted_files = sorted(files, key=lambda fp: os.path.basename(fp).lower(), reverse="Z → A" in criteria)
            else:
                sorted_files = files

            for fpath in sorted_files:
                var = ctk.BooleanVar()
                self.file_vars[fpath] = var
                cb = ctk.CTkCheckBox(self.listbox, text=self.file_display_text(fpath), variable=var, command=lambda fp=fpath: self.show_preview(fp))
                cb.pack(anchor="w", padx=20)

    def file_display_text(self, filepath):
        try:
            size = os.path.getsize(filepath)
            mtime = datetime.fromtimestamp(os.path.getmtime(filepath)).strftime("%Y-%m-%d %H:%M:%S")
            return f"{os.path.basename(filepath)}  |  {size//1024} KB  |  Modified: {mtime}"
        except Exception:
            return os.path.basename(filepath)

    def get_selected_files(self):
        return [fp for fp, var in self.file_vars.items() if var.get()]

    def show_preview(self, filepath):
        ext = os.path.splitext(filepath)[1].lower()
        try:
            if ext in [".png", ".jpg", ".jpeg", ".bmp", ".gif"]:
                img = Image.open(filepath)
                img.thumbnail((400, 180))
                self.img_tk = ImageTk.PhotoImage(img)
                self.preview_label.configure(image=self.img_tk, text="")
            elif ext in [".txt", ".py", ".log", ".csv", ".md"]:
                with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
                    text = f.read(10240)
                self.preview_label.configure(image="", text=text)
            else:
                self.preview_label.configure(image="", text="No preview available.")
        except Exception as e:
            self.preview_label.configure(image="", text=f"Error previewing file:\n{e}")

    # Other methods like delete_selected, move_selected, etc... (already present in your code)


    def delete_selected(self):
        selected_files = self.get_selected_files()
        if not selected_files:
            mb.showinfo("Info", "No files selected.")
            return

        confirm = mb.askyesno("Confirm Deletion", f"Are you sure you want to delete {len(selected_files)} file(s)?")
        if not confirm:
            return

        deleted = []
        for filepath in selected_files:
            try:
                os.remove(filepath)
                deleted.append(filepath)
            except Exception as e:
                print(f"Error deleting {filepath}: {e}")

        self.last_backup = deleted.copy()
        self.update_status(f"Deleted {len(deleted)} files.")
        self.start_scan_thread()

    def move_selected(self):
        selected_files = self.get_selected_files()
        if not selected_files:
            mb.showinfo("Info", "No files selected.")
            return

        target_folder = fd.askdirectory(title="Select Destination Folder")
        if not target_folder:
            return

        moved = []
        for filepath in selected_files:
            try:
                dest = os.path.join(target_folder, os.path.basename(filepath))
                shutil.move(filepath, dest)
                moved.append(filepath)
            except Exception as e:
                print(f"Error moving {filepath}: {e}")

        self.last_backup = moved.copy()
        self.update_status(f"Moved {len(moved)} files.")
        self.start_scan_thread()

    def backup_selected(self):
        selected_files = self.get_selected_files()
        if not selected_files:
            mb.showinfo("Info", "No files selected.")
            return

        backed_up = []
        for filepath in selected_files:
            try:
                dest = os.path.join(self.backup_folder, os.path.basename(filepath))
                shutil.copy2(filepath, dest)
                backed_up.append(filepath)
            except Exception as e:
                print(f"Error backing up {filepath}: {e}")

        self.last_backup = backed_up.copy()
        self.update_status(f"Backed up {len(backed_up)} files to {self.backup_folder}.")

    
    def undo_last(self):
        if not hasattr(self, 'last_organization_map') or not self.last_organization_map:
            mb.showinfo("Info", "No previous organization to undo.")
            return

        restored = 0
        for src, dest in self.last_organization_map.items():
            try:
                if os.path.exists(dest):
                    os.makedirs(os.path.dirname(src), exist_ok=True)
                    shutil.move(dest, src)
                    restored += 1
                    # After restoring, if the destination folder is empty, try removing it
                    dest_folder = os.path.dirname(dest)
                    if not os.listdir(dest_folder):
                        os.rmdir(dest_folder)
            except Exception as e:
                print(f"Error restoring {dest} → {src}: {e}")

        self.update_status(f"Restored {restored} files to original locations.")
        self.start_scan_thread()
        self.last_organization_map.clear()

    def export_csv(self):
        if not self.duplicates:
            mb.showinfo("Info", "No duplicates to export.")
            return

        file_path = fd.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV Files", "*.csv")])
        if not file_path:
            return

        try:
            with open(file_path, "w", newline='', encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(["Hash", "File Path"])
                for h, files in self.duplicates.items():
                    for fp in files:
                        writer.writerow([h, fp])
            self.update_status(f"Exported CSV to {file_path}")
        except Exception as e:
            mb.showerror("Error", f"Failed to export CSV:\n{e}")

    def export_pdf(self):
        if not self.duplicates:
            mb.showinfo("Info", "No duplicates to export.")
            return

        file_path = fd.asksaveasfilename(defaultextension=".pdf", filetypes=[("PDF Files", "*.pdf")])
        if not file_path:
            return

        try:
            pdf = FPDF()
            pdf.add_page()
            pdf.set_font("Arial", size=10)

            for h, files in self.duplicates.items():
                pdf.set_text_color(0, 0, 255)
                pdf.cell(0, 10, f"Hash: {h}", ln=True)
                pdf.set_text_color(0, 0, 0)
                for fp in files:
                    pdf.multi_cell(0, 8, fp)

            pdf.output(file_path)
            self.update_status(f"Exported PDF to {file_path}")
        except Exception as e:
            mb.showerror("Error", f"Failed to export PDF:\n{e}")


    def organize_files_physically(self):
        print("DEBUG: Organize button clicked")
        folder = self.folder_var.get()
        if not folder or not os.path.isdir(folder):
            mb.showerror("Error", "Please select a valid folder.")
            return

        files = [os.path.join(folder, f) for f in os.listdir(folder) if os.path.isfile(os.path.join(folder, f))]
        print(f"DEBUG: Found {len(files)} files in folder {folder}")
        self.last_backup = files.copy()
        self.last_organization_map = {}
        criteria = self.sort_criteria.get().lower()
        print(f"DEBUG: Selected criteria = {criteria}")

        moved = 0
        for fpath in files:
            try:
                if "date" in criteria:
                    mod_time = datetime.fromtimestamp(os.path.getmtime(fpath))
                    subfolder = os.path.join(folder, f"{mod_time.year}-{mod_time.month:02d}")
                elif "type" in criteria:
                    ext = os.path.splitext(fpath)[1][1:] or "senza_estensione"
                    subfolder = os.path.join(folder, ext.upper())
                elif "name" in criteria:
                    initial = os.path.basename(fpath)[0].upper()
                    if not initial.isalpha():
                        initial = "#"
                    subfolder = os.path.join(folder, initial)
                else:
                    continue  # unsupported criterion

                os.makedirs(subfolder, exist_ok=True)
                dest_path = os.path.join(subfolder, os.path.basename(fpath))
                shutil.move(fpath, dest_path)
                self.last_organization_map[fpath] = dest_path
                moved += 1
                print(f"DEBUG: Moved file {fpath} → {subfolder}")
            except Exception as e:
                print(f"Error nel muovere {fpath}: {e}")

        self.update_status(f"Organized {moved} file in base al criterio: {criteria}")
        mb.showinfo("Completed", f"Organized {moved} files in the folder '{folder}'")
        self.start_scan_thread()

if __name__ == "__main__":
    app = DuplicateManagerApp()
    app.mainloop()

