# Codebase Scanner

## Overview

Codebase Scanner is a Python application with a graphical user interface (GUI) designed to scan a specified directory. It reads the content of non-ignored files within that directory and its subdirectories, concatenating them into a single Markdown file. The tool respects ignore rules defined in configuration files (like `.scanIgnore`) to exclude specific files and folders from the scan. This is useful for creating context files for large language models or generating documentation snapshots.

The main application logic and GUI are implemented in `CodebaseScanner.py`.

---

## Features

*   **User-friendly GUI:** Built with Tkinter for ease of use.
*   **Configurable Scan Directory:** Select any directory on your system to scan.
*   **Configurable Output File:** Choose where to save the resulting Markdown file. The application suggests a filename based on the scanned directory.
*   **Customizable Ignore Rules:**
    *   Select or create specific `.scanIgnore` files to define which files and folders should be skipped.
    *   Manage rules directly through the GUI (add files/folders, remove entries).
*   **Default Ignore Rules:** Comes bundled with a `.scanIgnore.defaults` file containing common patterns to ignore (e.g., `.git`, `node_modules`). These defaults can be loaded into the current session or edited directly via the GUI.
*   **Settings Persistence:** Remembers the last used scan directory, save directory, and ignore file path between sessions via a `.scan_config.txt` file saved in the application's directory.
*   **Syntax Highlighting Hints:** Adds language hints (e.g., `python`, `javascript`) to Markdown code blocks based on file extensions for better rendering.
*   **Output Metadata:** The generated Markdown file includes a header indicating which ignore file was used during the scan.
*   **Responsive UI:** Performs the scanning process in a background thread to prevent the GUI from freezing.

---

## Usage (For End Users)

These instructions guide you on how to use the pre-built executable (e.g., `CodebaseScannerApp.exe`).

1.  **Launch the Application:** Double-click the `CodebaseScannerApp.exe` file.
2.  **Select Scan Directory:**
    *   Click the "Browse..." button next to "Scan Directory".
    *   Navigate to and select the root folder of the codebase you want to scan.
3.  **Select Save Location:**
    *   Click the "Browse..." button next to "Save Output As".
    *   Choose a directory and enter a filename for the output Markdown file (e.g., `my_project_scan.md`). The application will suggest a name based on the scan directory.
4.  **Select Ignore File:**
    *   Click the "Browse..." button next to "Ignore File".
    *   **Select Existing:** Navigate to and choose an existing `.scanIgnore` file if you have one.
    *   **Create New:** Navigate to the desired directory (e.g., your project root), type a filename (conventionally `.scanIgnore`), and click "Save". The application will ask if you want to create the empty file.
    *   **Use Defaults:** You can select the bundled `.scanIgnore.defaults` file, or load its rules into your custom file later.
    *   *Note:* An ignore file **must** be selected before scanning.
5.  **Manage Ignore Rules (Optional):**
    *   The "Ignore Rules" list displays the rules loaded from the selected "Ignore File".
    *   **Add File(s) to Ignore:** Click this button, browse to select one or more files whose names should be ignored (e.g., `config.secret.json`).
    *   **Add Folder to Ignore:** Click this button, browse to select a folder whose name should be ignored (e.g., `temp_files`).
    *   **Load Defaults:** Merges rules from the application's `.scanIgnore.defaults` into the currently displayed list. Useful for starting a new project-specific ignore file.
    *   **Edit Defaults:** Opens a separate window to directly view and modify the `.scanIgnore.defaults` file.
    *   **Save Ignore List:** Saves any additions or removals you've made in the GUI list back to the selected "Ignore File". You'll be prompted to save if you try to scan with unsaved changes.
6.  **Run Scan:**
    *   Click the "Run Scan" button.
    *   The application will scan the selected directory, skipping files and folders specified in the *currently saved state* of the selected ignore file.
    *   The status bar at the bottom will show progress.
    *   Once complete, a confirmation message will appear.
7.  **Output File:**
    *   Open the saved Markdown file.
    *   It will contain:
        *   A main title indicating the scanned directory.
        *   A line showing which ignore file was used (`**Ignored Rules From:** ...`).
        *   Sections for each directory, listing the files within.
        *   The full content of each non-ignored file, enclosed in Markdown code blocks with appropriate language hints (e.g., ```python ... ```).

---

## Ignore File Format

Ignore files (`.scanIgnore`, `.scanIgnore.defaults`) use a simple text-based format:

*   Lines starting with `file:` specify a file name *pattern* to ignore. The application currently checks if the pattern is a *substring* of the filename.
    *   Example: `file: .env`
    *   Example: `file: package-lock.json`
*   Lines starting with `folder:` specify a folder name *pattern* to ignore. The application currently checks if the pattern is a *substring* of the folder name.
    *   Example: `folder: .git`
    *   Example: `folder: node_modules`
*   Lines starting with `#` are treated as comments and are ignored.
*   Blank lines are ignored.

---

## Building from Source (For Developers)

### Prerequisites

*   Python 3.x (Tkinter support is usually included, but ensure it's available in your installation).
*   `pip` (Python package installer).

### Installation

1.  **Clone/Download:** Obtain the source code, including `CodebaseScanner.py` and `.scanIgnore.defaults`.
2.  **Install PyInstaller:** PyInstaller is used to bundle the application into an executable. Open your terminal or command prompt and run:
    ```bash
    pip install pyinstaller
    ```

### Build Command

Navigate to the directory containing `CodebaseScanner.py` and `.scanIgnore.defaults` in your terminal and run the following command:

```bash
~pyinstaller --name CodeScannerApp --onefile --windowed --add-data ".scanIgnore.defaults:." CodeScannerApp.py~