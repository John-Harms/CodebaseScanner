# CodebaseScanner_gui.py

import os
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
import threading # Import threading for non-blocking scan

# --- Constants and Configuration ---
SETTINGS_FILE = ".scan_config.txt"
IGNORE_FILE = ".scanIgnore"
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SETTINGS_PATH = os.path.join(SCRIPT_DIR, SETTINGS_FILE)
IGNORE_FILE_PATH = os.path.join(SCRIPT_DIR, IGNORE_FILE)

# Map common file extensions to Markdown language hints (Reused)
LANG_MAP = {
    ".py": "python", ".js": "javascript", ".jsx": "javascript", ".ts": "typescript",
    ".tsx": "typescript", ".html": "html", ".css": "css", ".scss": "scss",
    ".json": "json", ".yaml": "yaml", ".yml": "yaml", ".md": "markdown",
    ".sh": "bash", ".java": "java", ".cs": "csharp", ".cpp": "cpp", ".c": "c",
    ".h": "c", ".hpp": "cpp", ".go": "go", ".php": "php", ".rb": "ruby",
    ".rs": "rust", ".swift": "swift", ".kt": "kotlin", ".kts": "kotlin",
    ".sql": "sql", ".xml": "xml", ".dockerfile": "dockerfile", ".txt": "text",
}

# --- Core Logic Functions (Adapted for stricter parsing and saving) ---

def get_language_hint(filename):
    """Determines the Markdown language hint based on the file extension."""
    _, ext = os.path.splitext(filename)
    return LANG_MAP.get(ext.lower(), "")

def load_settings():
    """Loads saved directory settings from the settings file."""
    settings = {}
    if os.path.exists(SETTINGS_PATH):
        try:
            with open(SETTINGS_PATH, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if "=" in line:
                        key, value = line.split("=", 1)
                        settings[key.strip()] = value.strip()
        except Exception as e:
            print(f"Error loading settings: {e}") # Keep console log for debugging
    return settings

def save_settings(scan_directory, save_directory):
    """Saves the directory settings to the settings file."""
    try:
        with open(SETTINGS_PATH, "w", encoding="utf-8") as f:
            if scan_directory:
                f.write(f"scan_directory={scan_directory}\n")
            if save_directory:
                f.write(f"save_directory={save_directory}\n")
    except Exception as e:
        print(f"Error saving settings: {e}")

# --- Ignore File Handling (Revised) ---

def load_ignore_rules(ignore_file_path):
    """Loads and strictly parses ignore rules from the file."""
    ignore_files = []
    ignore_folders = []
    if os.path.exists(ignore_file_path):
        try:
            with open(ignore_file_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue # Skip comments and blank lines

                    if line.lower().startswith("file:"):
                        pattern = line[len("file:"):].strip()
                        if pattern and pattern not in ignore_files: # Prevent duplicates on load
                            ignore_files.append(pattern)
                    elif line.lower().startswith("folder:"):
                        pattern = line[len("folder:"):].strip()
                        if pattern and pattern not in ignore_folders: # Prevent duplicates on load
                            ignore_folders.append(pattern)
                    # Ignore lines without a valid prefix
        except Exception as e:
            print(f"Error loading or parsing ignore file: {e}")
            # Optionally show error in GUI status later
    ignore_files.sort() # Keep sorted
    ignore_folders.sort() # Keep sorted
    return ignore_files, ignore_folders

def save_ignore_rules(ignore_file_path, ignore_files, ignore_folders):
    """Saves the ignore rules to the file in the predefined format."""
    try:
        with open(ignore_file_path, "w", encoding="utf-8") as f:
            f.write("# Files to ignore\n")
            # Sort alphabetically before saving for consistency
            for pattern in sorted(ignore_files):
                f.write(f"file: {pattern}\n")

            f.write("\n# Folders to ignore\n")
             # Sort alphabetically before saving for consistency
            for pattern in sorted(ignore_folders):
                f.write(f"folder: {pattern}\n")
    except Exception as e:
        print(f"Error saving ignore file: {e}")
        raise # Re-raise to be caught by the GUI save logic

# parse_ignore_lines function (Used by the scan thread - **CRITICAL UPDATE**)
def parse_ignore_lines(lines):
    """
    Parses lines STRICTLY into file/folder patterns.
    Used by the background scan process.
    Only lines starting with 'file:' or 'folder:' are considered valid.
    """
    ignore_files = []
    ignore_folders = []
    for line in lines:
        line = line.strip()
        if not line or line.startswith("#"):
            continue # Skip comments and blank lines

        if line.lower().startswith("file:"):
            pattern = line[len("file:"):].strip()
            if pattern:
                ignore_files.append(pattern)
        elif line.lower().startswith("folder:"):
            pattern = line[len("folder:"):].strip()
            if pattern:
                ignore_folders.append(pattern)
        # Lines without a valid prefix are strictly ignored here
    return ignore_files, ignore_folders

# Helper to load raw lines (used only by parse_ignore_lines for the scan)
def load_raw_ignore_lines(ignore_file_path):
    """Loads raw lines from the ignore file."""
    lines = []
    if os.path.exists(ignore_file_path):
        try:
            with open(ignore_file_path, "r", encoding="utf-8") as f:
                lines = f.readlines() # Read including newlines initially
        except Exception as e:
            print(f"Error loading ignore file raw lines: {e}")
    return lines


# --- Scan Logic (Mostly Unchanged, but relies on updated parse_ignore_lines) ---

def should_ignore_file(name, ignore_files):
    """Checks if the file name matches any ignore pattern."""
    for pattern in ignore_files:
        # Using 'in' for substring matching as per original logic.
        # For exact match use: if pattern == name:
        # For glob matching use: import fnmatch; if fnmatch.fnmatch(name, pattern):
        if pattern in name:
            return True
    return False

def should_ignore_folder(name, ignore_folders):
    """Checks if the folder name matches any ignore pattern."""
    for pattern in ignore_folders:
        # Using 'in' for substring matching as per original logic.
        if pattern in name:
            return True
    return False

def process_directory(directory, output_file, ignore_files, ignore_folders, level=0, status_callback=None):
    """
    Processes a directory and writes its structure and contents in Markdown format.
    (Relies on the strictly parsed ignore_files/ignore_folders)
    """
    heading_level = level + 2
    heading_prefix = "#" * heading_level

    if status_callback:
        status_callback(f"Processing: {directory}")

    try:
        items = os.listdir(directory)
    except Exception as e:
        output_file.write(f"{heading_prefix} Error Reading Directory\n\n")
        output_file.write(f"**Path:** `{directory}`\n\n")
        output_file.write(f"**Error:** `{e}`\n\n")
        if status_callback:
            status_callback(f"Error reading: {directory}")
        return

    non_ignored_files = []
    non_ignored_dirs = []

    for item in items:
        item_path = os.path.join(directory, item)
        if os.path.isfile(item_path):
            # Use updated should_ignore_file which uses strictly parsed patterns
            if not should_ignore_file(item, ignore_files):
                non_ignored_files.append(item)
        elif os.path.isdir(item_path):
             # Use updated should_ignore_folder which uses strictly parsed patterns
            if not should_ignore_folder(item, ignore_folders):
                non_ignored_dirs.append(item)

    # Sort for consistent output
    non_ignored_files.sort()
    non_ignored_dirs.sort()

    # Write Directory Header
    output_file.write(f"{heading_prefix} Directory: {os.path.basename(directory)}\n\n")
    output_file.write(f"**Path:** `{directory}`\n\n")

    # List Files
    if non_ignored_files:
        file_heading_level = heading_level + 1
        file_heading_prefix = "#" * file_heading_level
        output_file.write(f"{file_heading_prefix} Files\n\n")
        for file in non_ignored_files:
            file_path = os.path.join(directory, file)
            output_file.write(f"**File:** `{file}`\n")
            lang_hint = get_language_hint(file)
            try:
                # Use 'ignore' for errors to handle potential binary files gracefully
                with open(file_path, "r", encoding="utf-8", errors='ignore') as f:
                    content = f.read()
                output_file.write(f"```{lang_hint}\n")
                output_file.write(content)
                output_file.write(f"\n```\n\n")
            except Exception as e:
                output_file.write(f"**Error reading file:** `{e}`\n\n")
                if status_callback:
                    status_callback(f"Error reading file: {file_path}")

    # Process Subdirectories Recursively
    if non_ignored_dirs:
        for dir_name in non_ignored_dirs:
            sub_dir_path = os.path.join(directory, dir_name)
            process_directory(sub_dir_path, output_file, ignore_files, ignore_folders, level + 1, status_callback)


# --- GUI Application Class ---

class CodeScannerApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Codebase Scanner")
        # self.root.geometry("700x650") # Adjust size if needed

        # --- Variables ---
        self.scan_directory = tk.StringVar()
        self.save_filepath = tk.StringVar()
        self.status_text = tk.StringVar()
        self.status_text.set("Ready")

        # --- Revised Internal Ignore State ---
        self.ignore_files = [] # List of file patterns (strings)
        self.ignore_folders = [] # List of folder patterns (strings)
        self.ignore_dirty = False # Flag to track unsaved changes

        # --- Load Initial Settings ---
        settings = load_settings()
        self.scan_directory.set(settings.get('scan_directory', ''))
        initial_save_dir = settings.get('save_directory', '')
        if self.scan_directory.get() and initial_save_dir:
             suggested_name = f"{os.path.basename(self.scan_directory.get())}_scan.md"
             self.save_filepath.set(os.path.join(initial_save_dir, suggested_name))
        elif initial_save_dir:
             self.save_filepath.set(initial_save_dir)
        else:
             self.save_filepath.set("")

        # --- GUI Layout ---
        main_frame = ttk.Frame(root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        root.columnconfigure(0, weight=1)
        root.rowconfigure(0, weight=1) # Allow main frame to expand

        # Scan Directory Row
        ttk.Label(main_frame, text="Scan Directory:").grid(row=0, column=0, sticky=tk.W, pady=2)
        scan_entry = ttk.Entry(main_frame, textvariable=self.scan_directory, width=60)
        scan_entry.grid(row=0, column=1, sticky=(tk.W, tk.E), padx=5, pady=2)
        scan_button = ttk.Button(main_frame, text="Browse...", command=self._browse_scan_directory)
        scan_button.grid(row=0, column=2, sticky=tk.E, padx=5, pady=2)

        # Save File Row
        ttk.Label(main_frame, text="Save Output As:").grid(row=1, column=0, sticky=tk.W, pady=2)
        save_entry = ttk.Entry(main_frame, textvariable=self.save_filepath, width=60)
        save_entry.grid(row=1, column=1, sticky=(tk.W, tk.E), padx=5, pady=2)
        save_button = ttk.Button(main_frame, text="Browse...", command=self._browse_save_file)
        save_button.grid(row=1, column=2, sticky=tk.E, padx=5, pady=2)

        # --- Ignore List Section (Revised) ---
        ignore_frame = ttk.LabelFrame(main_frame, text="Ignore Rules (.scanIgnore)", padding="5")
        ignore_frame.grid(row=2, column=0, columnspan=3, sticky=(tk.W, tk.E, tk.N, tk.S), pady=10)
        ignore_frame.columnconfigure(0, weight=1)
        ignore_frame.rowconfigure(0, weight=1) # Allow canvas/list to expand

        # Create a Canvas and a Scrollbar
        self.ignore_canvas = tk.Canvas(ignore_frame, borderwidth=0)
        self.ignore_list_frame = ttk.Frame(self.ignore_canvas) # Frame to hold the list items
        self.ignore_scrollbar = ttk.Scrollbar(ignore_frame, orient="vertical", command=self.ignore_canvas.yview)
        self.ignore_canvas.configure(yscrollcommand=self.ignore_scrollbar.set)

        # Grid the canvas and scrollbar
        self.ignore_canvas.grid(row=0, column=0, sticky="nsew")
        self.ignore_scrollbar.grid(row=0, column=1, sticky="ns")

        # Create a window in the canvas for the frame
        self.canvas_window = self.ignore_canvas.create_window((0, 0), window=self.ignore_list_frame, anchor="nw")

        # Bind canvas/frame resizing and mouse wheel
        self.ignore_list_frame.bind("<Configure>", self._on_frame_configure)
        self.ignore_canvas.bind('<Configure>', self._on_canvas_configure)
        # Bind mouse wheel scrolling (platform-dependent)
        self.ignore_canvas.bind_all("<MouseWheel>", self._on_mousewheel) # Windows/Mac
        self.ignore_canvas.bind_all("<Button-4>", self._on_mousewheel)    # Linux Up
        self.ignore_canvas.bind_all("<Button-5>", self._on_mousewheel)    # Linux Down


        # Ignore Buttons Frame (Below the list)
        ignore_buttons_frame = ttk.Frame(ignore_frame)
        ignore_buttons_frame.grid(row=1, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=5)

        add_file_button = ttk.Button(ignore_buttons_frame, text="Add File(s) to Ignore", command=self._add_files_to_ignore)
        add_file_button.pack(side=tk.LEFT, padx=5)

        add_folder_button = ttk.Button(ignore_buttons_frame, text="Add Folder to Ignore", command=self._add_folder_to_ignore)
        add_folder_button.pack(side=tk.LEFT, padx=5)

        save_ignore_button = ttk.Button(ignore_buttons_frame, text="Save Ignore List", command=self._save_ignore_changes)
        save_ignore_button.pack(side=tk.LEFT, padx=5) # Explicit save button

        # Load initial ignore rules
        self._load_and_display_ignore_rules()

        # Run Scan Button
        run_button = ttk.Button(main_frame, text="Run Scan", command=self._run_scan, style="Accent.TButton")
        run_button.grid(row=3, column=0, columnspan=3, pady=10)
        style = ttk.Style()
        try:
            style.configure("Accent.TButton", font=('TkDefaultFont', 10, 'bold'))
        except tk.TclError:
             print("Could not apply custom button style.")

        # Status Bar
        status_bar = ttk.Label(root, textvariable=self.status_text, relief=tk.SUNKEN, anchor=tk.W, padding="2 5")
        status_bar.grid(row=1, column=0, sticky=(tk.W, tk.E))

        # Configure resizing behavior
        main_frame.columnconfigure(1, weight=1) # Allow entry fields to expand horizontally
        main_frame.rowconfigure(2, weight=1) # Allow ignore list section to expand vertically


    # --- Canvas/Scrollbar Helpers ---
    def _on_frame_configure(self, event=None):
        """Reset the scroll region to encompass the inner frame."""
        self.ignore_canvas.configure(scrollregion=self.ignore_canvas.bbox("all"))

    def _on_canvas_configure(self, event):
        """Set the width of the inner frame to match the canvas"""
        self.ignore_canvas.itemconfig(self.canvas_window, width=event.width)

    def _on_mousewheel(self, event):
        """Handle mouse wheel scrolling for the ignore list canvas."""
        # Determine scroll direction (platform differences)
        if event.num == 5 or event.delta < 0: # Scroll down (Linux button 5, Windows/Mac negative delta)
            self.ignore_canvas.yview_scroll(1, "units")
        elif event.num == 4 or event.delta > 0: # Scroll up (Linux button 4, Windows/Mac positive delta)
            self.ignore_canvas.yview_scroll(-1, "units")

    # --- Status Update ---
    def _update_status(self, message, clear_after_ms=None):
        """Updates the status bar."""
        self.status_text.set(message)
        self.root.update_idletasks()
        if clear_after_ms:
            self.root.after(clear_after_ms, lambda: self.status_text.set("Ready") if self.status_text.get() == message else None)

    # --- Browse Functions (Unchanged) ---
    def _browse_scan_directory(self):
        initial_dir = self.scan_directory.get() or os.path.expanduser("~")
        directory = filedialog.askdirectory(title="Select Directory to Scan", initialdir=initial_dir)
        if directory:
            self.scan_directory.set(directory)
            self._suggest_save_filename()
            self._update_status("Scan directory selected.")
        else:
            self._update_status("Scan directory selection cancelled.")

    def _browse_save_file(self):
        initial_dir = os.path.dirname(self.save_filepath.get()) or os.path.expanduser("~")
        initial_file = os.path.basename(self.save_filepath.get()) or ""
        if not initial_file and self.scan_directory.get():
             initial_file = f"{os.path.basename(self.scan_directory.get())}_scan.md"

        filepath = filedialog.asksaveasfilename(
            title="Save Scan Output As",
            initialdir=initial_dir,
            initialfile=initial_file,
            defaultextension=".md",
            filetypes=[("Markdown Files", "*.md"), ("Text Files", "*.txt"), ("All Files", "*.*")]
        )
        if filepath:
            self.save_filepath.set(filepath)
            self._update_status("Save location selected.")
        else:
            self._update_status("Save location selection cancelled.")

    def _suggest_save_filename(self):
         scan_dir = self.scan_directory.get()
         if not scan_dir: return
         current_save_path = self.save_filepath.get()
         save_dir = os.path.dirname(current_save_path)
         if not save_dir or not os.path.isdir(save_dir):
             settings = load_settings()
             save_dir = settings.get('save_directory', os.path.dirname(scan_dir))
             if not save_dir or not os.path.isdir(save_dir):
                 save_dir = os.path.expanduser("~")
         suggested_name = f"{os.path.basename(scan_dir)}_scan.md"
         self.save_filepath.set(os.path.join(save_dir, suggested_name))

    # --- Ignore List Management (Revised) ---

    def _load_and_display_ignore_rules(self):
        """Loads rules from file, updates internal state, and rebuilds the GUI list."""
        try:
            self.ignore_files, self.ignore_folders = load_ignore_rules(IGNORE_FILE_PATH)
            self.ignore_dirty = False
            self._rebuild_ignore_list_gui()
            self._update_status(f"Loaded {len(self.ignore_files) + len(self.ignore_folders)} rules from {IGNORE_FILE}")
        except Exception as e:
            messagebox.showerror("Load Error", f"Could not load or parse {IGNORE_FILE}:\n{e}")
            self._update_status(f"Error loading {IGNORE_FILE}")
            self.ignore_files, self.ignore_folders = [], [] # Ensure lists are empty on error
            self.ignore_dirty = False
            self._rebuild_ignore_list_gui() # Display empty list


    def _rebuild_ignore_list_gui(self):
        """Clears and rebuilds the visual list of ignore rules in the scrollable frame."""
        # Destroy existing widgets in the frame
        for widget in self.ignore_list_frame.winfo_children():
            widget.destroy()

        row_num = 0

        # Add file rules
        if self.ignore_files:
            ttk.Label(self.ignore_list_frame, text="Files:", font=('TkDefaultFont', 9, 'bold')).grid(row=row_num, column=0, columnspan=2, sticky=tk.W, padx=5, pady=(5,2))
            row_num += 1
            for pattern in self.ignore_files: # Assumes already sorted
                item_frame = ttk.Frame(self.ignore_list_frame)
                item_frame.grid(row=row_num, column=0, columnspan=2, sticky=tk.EW, padx=5, pady=1)
                item_frame.columnconfigure(0, weight=1) # Label expands

                label_text = f"file: {pattern}"
                # Truncate long labels if necessary for display
                max_len = 60
                display_text = label_text if len(label_text) <= max_len else label_text[:max_len-3] + "..."
                tooltip_text = label_text if len(label_text) > max_len else "" # Store potential tooltip text

                # --- CORRECTION START ---
                # Create the Label *without* the tooltip argument
                lbl = ttk.Label(item_frame, text=display_text, anchor=tk.W)
                lbl.grid(row=0, column=0, sticky=tk.EW)
                # Call the monkey-patched method *after* creation if needed
                if tooltip_text:
                    lbl.tooltip(tooltip_text)
                # --- CORRECTION END ---

                # Use a lambda with default argument to capture the current pattern
                remove_button = ttk.Button(item_frame, text="x", width=2, style="Small.TButton",
                                           command=lambda p=pattern: self._remove_ignore_item('file', p))
                remove_button.grid(row=0, column=1, sticky=tk.E, padx=(5, 0))
                row_num += 1

        # Add folder rules
        if self.ignore_folders:
            ttk.Label(self.ignore_list_frame, text="Folders:", font=('TkDefaultFont', 9, 'bold')).grid(row=row_num, column=0, columnspan=2, sticky=tk.W, padx=5, pady=(10,2))
            row_num += 1
            for pattern in self.ignore_folders: # Assumes already sorted
                item_frame = ttk.Frame(self.ignore_list_frame)
                item_frame.grid(row=row_num, column=0, columnspan=2, sticky=tk.EW, padx=5, pady=1)
                item_frame.columnconfigure(0, weight=1)

                label_text = f"folder: {pattern}"
                max_len = 60
                display_text = label_text if len(label_text) <= max_len else label_text[:max_len-3] + "..."
                tooltip_text = label_text if len(label_text) > max_len else "" # Store potential tooltip text

                # --- CORRECTION START ---
                # Create the Label *without* the tooltip argument
                lbl = ttk.Label(item_frame, text=display_text, anchor=tk.W)
                lbl.grid(row=0, column=0, sticky=tk.EW)
                 # Call the monkey-patched method *after* creation if needed
                if tooltip_text:
                    lbl.tooltip(tooltip_text)
                # --- CORRECTION END ---

                remove_button = ttk.Button(item_frame, text="x", width=2, style="Small.TButton",
                                           command=lambda p=pattern: self._remove_ignore_item('folder', p))
                remove_button.grid(row=0, column=1, sticky=tk.E, padx=(5, 0))
                row_num += 1

        # Define a smaller button style if possible
        style = ttk.Style()
        try:
            style.configure("Small.TButton", padding=(1, 1), font=('TkDefaultFont', 7))
        except tk.TclError:
            pass # Ignore if style cannot be applied

        # Add placeholder if list is empty
        if not self.ignore_files and not self.ignore_folders:
             ttk.Label(self.ignore_list_frame, text="No ignore rules defined.", foreground="grey").grid(row=0, column=0, padx=5, pady=5)


        # Update scroll region after adding items
        self.ignore_list_frame.update_idletasks() # Ensure frame size is calculated
        self._on_frame_configure()


    def _remove_ignore_item(self, item_type, pattern):
        """Removes an item from the internal list and refreshes the GUI."""
        removed = False
        if item_type == 'file':
            if pattern in self.ignore_files:
                self.ignore_files.remove(pattern)
                removed = True
        elif item_type == 'folder':
            if pattern in self.ignore_folders:
                self.ignore_folders.remove(pattern)
                removed = True

        if removed:
            self.ignore_dirty = True
            self._rebuild_ignore_list_gui() # Update display
            self._update_status(f"Removed '{pattern}'. Save changes to persist.", clear_after_ms=4000)
        else:
            # This shouldn't happen if GUI is in sync, but good failsafe
             self._update_status(f"Item '{pattern}' not found for removal.", clear_after_ms=4000)


    def _add_files_to_ignore(self):
        """Adds selected files to the internal ignore list and refreshes GUI."""
        initial_dir = self.scan_directory.get() or os.path.expanduser("~")
        filenames = filedialog.askopenfilenames(
            title="Select File(s) to Ignore",
            initialdir=initial_dir
        )
        if not filenames:
            self._update_status("Add files cancelled.")
            return

        added_count = 0
        newly_added = []
        for fname in filenames:
            basename = os.path.basename(fname)
            if basename and basename not in self.ignore_files:
                self.ignore_files.append(basename)
                newly_added.append(basename)
                added_count += 1

        if added_count > 0:
            self.ignore_files.sort() # Keep sorted
            self.ignore_dirty = True
            self._rebuild_ignore_list_gui()
            self._update_status(f"Added {added_count} file pattern(s). Save changes to persist.", clear_after_ms=4000)
        else:
            self._update_status("Selected file pattern(s) already in ignore list or invalid.")


    def _add_folder_to_ignore(self):
        """Adds a selected folder to the internal ignore list and refreshes GUI."""
        initial_dir = self.scan_directory.get() or os.path.expanduser("~")
        foldername = filedialog.askdirectory(
            title="Select Folder to Ignore",
            initialdir=initial_dir
        )
        if not foldername:
            self._update_status("Add folder cancelled.")
            return

        basename = os.path.basename(foldername)
        if basename and basename not in self.ignore_folders:
            self.ignore_folders.append(basename)
            self.ignore_folders.sort() # Keep sorted
            self.ignore_dirty = True
            self._rebuild_ignore_list_gui()
            self._update_status(f"Added folder pattern '{basename}'. Save changes to persist.", clear_after_ms=4000)
        elif basename:
             self._update_status(f"Folder pattern '{basename}' already in ignore list.")
        else:
             self._update_status("Invalid folder selected.")


    def _save_ignore_changes(self):
        """Saves the current internal ignore lists to the .scanIgnore file."""
        if not self.ignore_dirty:
             self._update_status("No changes to save in ignore list.")
             return

        try:
            # Pass the current internal lists to the saving function
            save_ignore_rules(IGNORE_FILE_PATH, self.ignore_files, self.ignore_folders)
            self.ignore_dirty = False
            self._update_status(f"Saved changes to {IGNORE_FILE}", clear_after_ms=3000)
        except Exception as e:
            messagebox.showerror("Save Error", f"Could not save {IGNORE_FILE}:\n{e}")
            self._update_status(f"Error saving {IGNORE_FILE}")


    # --- Scan Execution (Threaded) ---

    def _run_scan_thread(self, scan_dir, save_path, ignore_files, ignore_folders):
         """Target function for the scanning thread. Uses strictly parsed ignores."""
         try:
             with open(save_path, "w", encoding="utf-8") as output_file:
                 output_file.write(f"# Codebase Scan: {os.path.basename(scan_dir)}\n\n")
                 # Pass the strictly parsed lists directly
                 process_directory(scan_dir, output_file, ignore_files, ignore_folders, level=0, status_callback=self._update_status)

             # Post-scan actions (back on main thread)
             def on_scan_complete():
                 save_dir = os.path.dirname(save_path)
                 save_settings(scan_dir, save_dir)
                 self._update_status(f"Scan complete. Output saved to: {save_path}", clear_after_ms=10000)
                 messagebox.showinfo("Scan Complete", f"Output successfully saved to:\n{save_path}")

             self.root.after(0, on_scan_complete)

         except Exception as e:
             # Error handling (back on main thread)
             def on_scan_error():
                 error_message = f"An error occurred during scanning or writing: {e}"
                 print(error_message)
                 self._update_status(f"Error during scan: {e}", clear_after_ms=10000)
                 messagebox.showerror("Scan Error", error_message)

             self.root.after(0, on_scan_error)


    def _run_scan(self):
        """Validates inputs and starts the scan process in a thread."""
        scan_dir = self.scan_directory.get()
        save_path = self.save_filepath.get()

        if not scan_dir or not os.path.isdir(scan_dir):
            messagebox.showerror("Input Error", "Please select a valid directory to scan.")
            self._update_status("Error: Invalid scan directory.", clear_after_ms=5000)
            return
        if not save_path:
            messagebox.showerror("Input Error", "Please select a valid output file path.")
            self._update_status("Error: Invalid save location.", clear_after_ms=5000)
            return

        save_dir = os.path.dirname(save_path)
        if not os.path.exists(save_dir):
            try:
                os.makedirs(save_dir)
            except Exception as e:
                 messagebox.showerror("Input Error", f"Could not create save directory:\n{save_dir}\nError: {e}")
                 self._update_status(f"Error: Cannot create save directory.", clear_after_ms=5000)
                 return

        # --- CRITICAL: Save pending ignore changes BEFORE scanning ---
        if self.ignore_dirty:
            confirm = messagebox.askyesno("Unsaved Changes", f"You have unsaved changes in the ignore list.\nSave them to {IGNORE_FILE} before scanning?", default=messagebox.YES)
            if confirm:
                self._save_ignore_changes()
                if self.ignore_dirty: # Check if save failed
                     messagebox.showerror("Save Failed", f"Could not save {IGNORE_FILE}. Aborting scan.")
                     return
            else:
                 # User chose not to save. We proceed BUT use the rules currently in the file.
                 self._update_status("Proceeding with scan using ignore rules from file (unsaved changes ignored).", clear_after_ms=5000)
                 # Reload from file to ensure scan uses the saved version
                 self._load_and_display_ignore_rules()
                 if self.ignore_dirty: # Should be false now unless load failed
                     messagebox.showerror("Load Failed", f"Could not reload {IGNORE_FILE}. Aborting scan.")
                     return


        # --- Prepare ignore lists for the scan thread ---
        # Reload raw lines and parse STRICTLY for the scan process.
        # This ensures the scan uses exactly what's in the file at the moment it starts.
        try:
            raw_ignore_lines = load_raw_ignore_lines(IGNORE_FILE_PATH)
            scan_ignore_files, scan_ignore_folders = parse_ignore_lines(raw_ignore_lines)
            self._update_status(f"Starting scan, using {len(scan_ignore_files)} file / {len(scan_ignore_folders)} folder patterns from {IGNORE_FILE}.")
        except Exception as e:
            messagebox.showerror("Ignore File Error", f"Could not read or parse {IGNORE_FILE} for scanning:\n{e}")
            self._update_status(f"Error loading ignore file for scan.", clear_after_ms=5000)
            return

        # --- Start scan in a separate thread ---
        self._update_status("Scanning...")
        scan_thread = threading.Thread(
            target=self._run_scan_thread,
            # Pass the strictly parsed lists intended for *this specific scan*
            args=(scan_dir, save_path, scan_ignore_files, scan_ignore_folders),
            daemon=True
        )
        scan_thread.start()


# --- Main Execution ---
if __name__ == "__main__":
    root = tk.Tk()
    # Add basic tooltip support (simple implementation)
    class ToolTip:
        def __init__(self, widget, text):
            self.widget = widget
            self.text = text
            self.tooltip = None
            widget.bind("<Enter>", self.enter)
            widget.bind("<Leave>", self.leave)
        def enter(self, event=None):
            x = y = 0
            x, y, _, _ = self.widget.bbox("insert")
            x += self.widget.winfo_rootx() + 25
            y += self.widget.winfo_rooty() + 20
            self.tooltip = tk.Toplevel(self.widget)
            self.tooltip.wm_overrideredirect(True)
            self.tooltip.wm_geometry(f"+{x}+{y}")
            label = tk.Label(self.tooltip, text=self.text, justify='left',
                             background="#ffffe0", relief='solid', borderwidth=1,
                             font=("tahoma", "8", "normal"))
            label.pack(ipadx=1)
        def leave(self, event=None):
            if self.tooltip:
                self.tooltip.destroy()
            self.tooltip = None

    # Monkey patch ttk.Label to add a tooltip property easily
    def set_tooltip(self, text):
        if text:
            ToolTip(self, text)
        # else: # Optionally remove existing tooltip if text is empty
        #     pass # Need more complex tracking if removal is needed
    ttk.Label.tooltip = set_tooltip

    app = CodeScannerApp(root)
    root.mainloop()