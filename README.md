🔁 TwinBin

TwinBin is a Python-based desktop application built with customtkinter that helps users scan, organize, preview, and manage duplicate files within a chosen directory. It features a modern dark-themed interface and multiple tools for file management and export.

🧰 Features

🔍 Scan for Duplicates
Scans a selected folder recursively to find duplicate files using MD5 hashing.

Runs in a background thread to avoid UI freezing.

Displays results grouped by hash, with metadata like file size and modification date.

🧠 Sorting Options

Sort detected duplicates by:

File size (largest/smallest first)

File name (A→Z / Z→A)

Physical reorganization (by date, type, or name initials)

🗃️ File Actions

Delete Selected: Permanently removes selected duplicate files.

Move Selected: Relocates selected files to a chosen folder.

Backup Selected: Copies selected files to a dedicated backup folder.

Undo Last: Restores files that were moved or organized during the last operation.

📂 Physical File Organizer

Organizes files in the folder into subfolders based on:

Modification date (YYYY-MM)

File type (by extension)

First letter of file name

👁️ File Preview

Live file preview for selected files:

Images: PNG, JPEG, BMP, GIF

Text: TXT, CSV, LOG, MD, PY

Others show a “No preview available” message

📤 Exporting Tools

CSV Export: Saves duplicate information (hash and file paths) into a .csv file.

PDF Export: Generates a .pdf document listing all detected duplicates.

🧾 Status Display

A real-time status bar that keeps users informed about current operations and outcomes.

🧱 Technologies Used

Python 3

CustomTkinter

FPDF for PDF export

PIL (Pillow) for image handling

hashlib, os, shutil, threading, and concurrent.futures for backend operations



















