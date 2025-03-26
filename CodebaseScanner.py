# CodebaseScanner_gui.py

import os
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext, Toplevel
import threading # Import threading for non-blocking scan
import shutil # Potentially useful, though not strictly needed for create empty file

# --- Constants and Configuration ---
SETTINGS_FILE = ".scan_config.txt"
# IGNORE_FILE is no longer a fixed constant path
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SETTINGS_PATH = os.path.join(SCRIPT_DIR, SETTINGS_FILE)
# IGNORE_FILE_PATH is removed as it's now dynamic

# Default ignore file configuration
DEFAULT_IGNORE_FILE = ".scanIgnore.defaults"
DEFAULT_IGNORE_PATH = os.path.join(SCRIPT_DIR, DEFAULT_IGNORE_FILE)


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
    """Loads saved directory and ignore file path settings from the settings file."""
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

def save_settings(scan_directory, save_directory, ignore_file_path):
    """Saves the directory and ignore file path settings to the settings file."""
    try:
        with open(SETTINGS_PATH, "w", encoding="utf-8") as f:
            if scan_directory:
                f.write(f"scan_directory={scan_directory}\n")
            if save_directory:
                f.write(f"save_directory={save_directory}\n")
            if ignore_file_path: # Save the selected ignore file path
                f.write(f"ignore_file_path={ignore_file_path}\n")
    except Exception as e:
        print(f"Error saving settings: {e}")

# --- Ignore File Handling (Revised to accept path) ---

def load_ignore_rules(ignore_file_path):
    """Loads and strictly parses ignore rules from the specified file."""
    ignore_files = []
    ignore_folders = []
    if ignore_file_path and os.path.exists(ignore_file_path): # Check if path is valid and exists
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
            print(f"Error loading or parsing ignore file '{ignore_file_path}': {e}")
            raise # Re-raise to be caught by GUI load logic
    # If file doesn't exist or path is invalid, return empty lists
    ignore_files.sort() # Keep sorted
    ignore_folders.sort() # Keep sorted
    return ignore_files, ignore_folders

def save_ignore_rules(ignore_file_path, ignore_files, ignore_folders):
    """Saves the ignore rules to the specified file in the predefined format."""
    if not ignore_file_path:
        raise ValueError("Cannot save ignore rules: No file path specified.")
    try:
        # Ensure parent directory exists
        parent_dir = os.path.dirname(ignore_file_path)
        if parent_dir and not os.path.exists(parent_dir):
            os.makedirs(parent_dir) # Create parent dir if it doesn't exist

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
        print(f"Error saving ignore file '{ignore_file_path}': {e}")
        raise # Re-raise to be caught by the GUI save logic

# parse_ignore_lines function (Used by the scan thread - Accepts path)
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

# Helper to load raw lines (accepts path)
def load_raw_ignore_lines(ignore_file_path):
    """Loads raw lines from the specified ignore file."""
    lines = []
    if ignore_file_path and os.path.exists(ignore_file_path):
        try:
            with open(ignore_file_path, "r", encoding="utf-8") as f:
                lines = f.readlines() # Read including newlines initially
        except Exception as e:
            print(f"Error loading ignore file raw lines from '{ignore_file_path}': {e}")
            # Depending on requirements, might want to raise here too
    return lines

# Helper to create an empty file
def create_empty_file(filepath):
    """Creates an empty file at the specified path, creating directories if needed."""
    try:
        parent_dir = os.path.dirname(filepath)
        if parent_dir and not os.path.exists(parent_dir):
            os.makedirs(parent_dir)
        with open(filepath, 'w', encoding='utf-8') as f:
            pass # Just create the file
        print(f"Created empty file: {filepath}")
        return True
    except Exception as e:
        print(f"Error creating empty file '{filepath}': {e}")
        messagebox.showerror("File Creation Error", f"Could not create file:\n{filepath}\nError: {e}")
        return False


# --- Scan Logic (Unchanged core, relies on arguments) ---
def should_ignore_file(name, ignore_files):
    """Checks if the file name matches any ignore pattern."""
    for pattern in ignore_files:
        if pattern in name: # Original substring logic
            return True
    return False

def should_ignore_folder(name, ignore_folders):
    """Checks if the folder name matches any ignore pattern."""
    for pattern in ignore_folders:
        if pattern in name: # Original substring logic
            return True
    return False

def process_directory(directory, output_file, ignore_files, ignore_folders, level=0, status_callback=None):
    """Processes a directory (unchanged core logic)."""
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
            if not should_ignore_file(item, ignore_files):
                non_ignored_files.append(item)
        elif os.path.isdir(item_path):
            if not should_ignore_folder(item, ignore_folders):
                non_ignored_dirs.append(item)

    non_ignored_files.sort()
    non_ignored_dirs.sort()

    output_file.write(f"{heading_prefix} Directory: {os.path.basename(directory)}\n\n")
    output_file.write(f"**Path:** `{directory}`\n\n")

    if non_ignored_files:
        file_heading_level = heading_level + 1
        file_heading_prefix = "#" * file_heading_level
        output_file.write(f"{file_heading_prefix} Files\n\n")
        for file in non_ignored_files:
            file_path = os.path.join(directory, file)
            output_file.write(f"**File:** `{file}`\n")
            lang_hint = get_language_hint(file)
            try:
                with open(file_path, "r", encoding="utf-8", errors='ignore') as f:
                    content = f.read()
                output_file.write(f"```{lang_hint}\n")
                output_file.write(content)
                output_file.write(f"\n```\n\n")
            except Exception as e:
                output_file.write(f"**Error reading file:** `{e}`\n\n")
                if status_callback:
                    status_callback(f"Error reading file: {file_path}")

    if non_ignored_dirs:
        for dir_name in non_ignored_dirs:
            sub_dir_path = os.path.join(directory, dir_name)
            process_directory(sub_dir_path, output_file, ignore_files, ignore_folders, level + 1, status_callback)


# --- GUI Application Class ---

class CodeScannerApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Codebase Scanner")
        # self.root.geometry("700x700") # Adjust size if needed

        # --- Variables ---
        self.scan_directory = tk.StringVar()
        self.save_filepath = tk.StringVar()
        self.current_ignore_file_path = tk.StringVar() # NEW: Holds path to active ignore file
        self.status_text = tk.StringVar()
        self.status_text.set("Initializing...")

        # --- Revised Internal Ignore State ---
        self.ignore_files = [] # List of file patterns (strings) in UI
        self.ignore_folders = [] # List of folder patterns (strings) in UI
        self.ignore_dirty = False # Flag to track unsaved changes in UI

        # --- Load Initial Settings ---
        settings = load_settings()
        self.scan_directory.set(settings.get('scan_directory', ''))
        initial_save_dir = settings.get('save_directory', '')
        self.current_ignore_file_path.set(settings.get('ignore_file_path', '')) # Load ignore file path

        if self.scan_directory.get() and initial_save_dir:
             suggested_name = f"{os.path.basename(self.scan_directory.get())}_scan.md"
             self.save_filepath.set(os.path.join(initial_save_dir, suggested_name))
        elif initial_save_dir:
             self.save_filepath.set(initial_save_dir) # Keep only dir if scan dir not set
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

        # --- NEW: Ignore File Path Row ---
        ttk.Label(main_frame, text="Ignore File:").grid(row=2, column=0, sticky=tk.W, pady=2)
        ignore_file_entry = ttk.Entry(main_frame, textvariable=self.current_ignore_file_path, width=60, state='readonly') # Read-only display
        ignore_file_entry.grid(row=2, column=1, sticky=(tk.W, tk.E), padx=5, pady=2)
        ignore_file_button = ttk.Button(main_frame, text="Browse...", command=self._browse_ignore_file)
        ignore_file_button.grid(row=2, column=2, sticky=tk.E, padx=5, pady=2)
        ToolTip(ignore_file_button, "Select or create the .scanIgnore file to use.")


        # --- Ignore List Section (Revised Label) ---
        self.ignore_frame = ttk.LabelFrame(main_frame, text="Ignore Rules", padding="5") # Label updated dynamically later
        self.ignore_frame.grid(row=3, column=0, columnspan=3, sticky=(tk.W, tk.E, tk.N, tk.S), pady=10)
        self.ignore_frame.columnconfigure(0, weight=1)
        self.ignore_frame.rowconfigure(0, weight=1) # Allow canvas/list to expand

        # Canvas, Frame, Scrollbar for ignore list (unchanged structure)
        self.ignore_canvas = tk.Canvas(self.ignore_frame, borderwidth=0)
        self.ignore_list_frame = ttk.Frame(self.ignore_canvas)
        self.ignore_scrollbar = ttk.Scrollbar(self.ignore_frame, orient="vertical", command=self.ignore_canvas.yview)
        self.ignore_canvas.configure(yscrollcommand=self.ignore_scrollbar.set)
        self.ignore_canvas.grid(row=0, column=0, sticky="nsew")
        self.ignore_scrollbar.grid(row=0, column=1, sticky="ns")
        self.canvas_window = self.ignore_canvas.create_window((0, 0), window=self.ignore_list_frame, anchor="nw")
        self.ignore_list_frame.bind("<Configure>", self._on_frame_configure)
        self.ignore_canvas.bind('<Configure>', self._on_canvas_configure)
        self.ignore_canvas.bind_all("<MouseWheel>", self._on_mousewheel)
        self.ignore_canvas.bind_all("<Button-4>", self._on_mousewheel)
        self.ignore_canvas.bind_all("<Button-5>", self._on_mousewheel)


        # Ignore Buttons Frame (Below the list)
        ignore_buttons_frame = ttk.Frame(self.ignore_frame)
        ignore_buttons_frame.grid(row=1, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=5)

        add_file_button = ttk.Button(ignore_buttons_frame, text="Add File(s) to Ignore", command=self._add_files_to_ignore)
        add_file_button.pack(side=tk.LEFT, padx=5)

        add_folder_button = ttk.Button(ignore_buttons_frame, text="Add Folder to Ignore", command=self._add_folder_to_ignore)
        add_folder_button.pack(side=tk.LEFT, padx=5)

        # --- NEW Default Buttons ---
        load_defaults_button = ttk.Button(ignore_buttons_frame, text="Load Defaults", command=self._load_defaults)
        load_defaults_button.pack(side=tk.LEFT, padx=5)
        ToolTip(load_defaults_button, f"Merge rules from {DEFAULT_IGNORE_FILE}")

        edit_defaults_button = ttk.Button(ignore_buttons_frame, text="Edit Defaults", command=self._edit_defaults_dialog)
        edit_defaults_button.pack(side=tk.LEFT, padx=5)
        ToolTip(edit_defaults_button, f"Open editor for {DEFAULT_IGNORE_FILE}")

        # Save Button (Existing)
        save_ignore_button = ttk.Button(ignore_buttons_frame, text="Save Ignore List", command=self._save_ignore_changes)
        save_ignore_button.pack(side=tk.LEFT, padx=5) # Explicit save button
        ToolTip(save_ignore_button, "Save current rules to the selected ignore file.")


        # --- Initial Load/Prompt for Ignore File ---
        self._initialize_ignore_file()


        # Run Scan Button
        # *** CRITICAL: Ensure self._run_scan is correctly referenced ***
        run_button = ttk.Button(main_frame, text="Run Scan", command=self._run_scan, style="Accent.TButton")
        run_button.grid(row=4, column=0, columnspan=3, pady=10) # Row index increased
        style = ttk.Style()
        try:
            style.configure("Accent.TButton", font=('TkDefaultFont', 10, 'bold'))
        except tk.TclError:
             print("Could not apply custom button style.")

        # Status Bar
        status_bar = ttk.Label(root, textvariable=self.status_text, relief=tk.SUNKEN, anchor=tk.W, padding="2 5")
        status_bar.grid(row=1, column=0, sticky=(tk.W, tk.E)) # Grid row updated

        # Configure resizing behavior
        main_frame.columnconfigure(1, weight=1) # Allow entry fields to expand horizontally
        main_frame.rowconfigure(3, weight=1) # Allow ignore list section to expand vertically (Row index increased)

        self.status_text.set("Ready") # Set status after init


    # --- Canvas/Scrollbar Helpers (Unchanged) ---
    def _on_frame_configure(self, event=None):
        self.ignore_canvas.configure(scrollregion=self.ignore_canvas.bbox("all"))
    def _on_canvas_configure(self, event):
        self.ignore_canvas.itemconfig(self.canvas_window, width=event.width)
    def _on_mousewheel(self, event):
        if event.num == 5 or event.delta < 0: self.ignore_canvas.yview_scroll(1, "units")
        elif event.num == 4 or event.delta > 0: self.ignore_canvas.yview_scroll(-1, "units")

    # --- Status Update (Unchanged) ---
    def _update_status(self, message, clear_after_ms=None):
        self.status_text.set(message)
        self.root.update_idletasks()
        if clear_after_ms:
            self.root.after(clear_after_ms, lambda: self.status_text.set("Ready") if self.status_text.get() == message else None)

    # --- Browse Functions (Updated for Save Path Suggestion) ---
    def _browse_scan_directory(self):
        initial_dir = self.scan_directory.get() or os.path.expanduser("~")
        directory = filedialog.askdirectory(title="Select Directory to Scan", initialdir=initial_dir)
        if directory:
            self.scan_directory.set(directory)
            self._suggest_save_filename() # Suggest filename when scan dir changes
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
         save_dir = os.path.dirname(current_save_path) if current_save_path else ''

         # If save_dir is not set or invalid, try loading from settings or default
         if not save_dir or not os.path.isdir(save_dir):
             settings = load_settings()
             save_dir = settings.get('save_directory', '') # Use saved dir first
             if not save_dir or not os.path.isdir(save_dir):
                 # Fallback to scan dir's parent or user home
                 save_dir_parent = os.path.dirname(scan_dir)
                 save_dir = save_dir_parent if os.path.isdir(save_dir_parent) else os.path.expanduser("~")

         suggested_name = f"{os.path.basename(scan_dir)}_scan.md"
         self.save_filepath.set(os.path.join(save_dir, suggested_name))

    # --- NEW: Ignore File Path Management ---

    def _initialize_ignore_file(self):
        """Checks the loaded ignore file path and prompts/loads accordingly."""
        filepath = self.current_ignore_file_path.get()
        if filepath:
            if os.path.exists(filepath):
                self._load_and_display_ignore_rules(filepath)
                # Update frame label
                self.ignore_frame.config(text=f"Ignore Rules ({os.path.basename(filepath)})")
            else:
                create = messagebox.askyesno(
                    "Ignore File Not Found",
                    f"Ignore file not found at:\n'{filepath}'\n\nCreate a new empty file there?"
                )
                if create:
                    if create_empty_file(filepath):
                         self._clear_and_display_ignore_rules(filepath) # Show empty list
                         # Update frame label
                         self.ignore_frame.config(text=f"Ignore Rules ({os.path.basename(filepath)})")
                    else:
                        # Error handled in create_empty_file
                        self.current_ignore_file_path.set("")
                        self._clear_and_display_ignore_rules(None) # Show empty list, no file loaded
                else:
                    self.current_ignore_file_path.set("")
                    self._clear_and_display_ignore_rules(None) # Show empty list, no file loaded
        else:
            self._clear_and_display_ignore_rules(None) # No path set, show empty list


    def _browse_ignore_file(self):
        """Allows user to select or create an ignore file."""
        initial_dir = os.path.dirname(self.current_ignore_file_path.get()) or \
                      self.scan_directory.get() or \
                      os.path.expanduser("~")

        filepath = filedialog.asksaveasfilename(
            title="Select or Create Ignore File",
            initialdir=initial_dir,
            initialfile=".scanIgnore",
            # defaultextension=".scanIgnore", # Not standard, maybe avoid enforcing?
            filetypes=[("Ignore Files", ".scanIgnore"), ("All Files", "*.*")]
        )

        if filepath:
            self.current_ignore_file_path.set(filepath)
            if os.path.exists(filepath):
                self._load_and_display_ignore_rules(filepath)
                self.ignore_frame.config(text=f"Ignore Rules ({os.path.basename(filepath)})")
            else:
                create = messagebox.askyesno(
                    "Create Ignore File?",
                    f"File '{os.path.basename(filepath)}' does not exist.\n\nCreate it at this location?"
                )
                if create:
                     if create_empty_file(filepath):
                         self._clear_and_display_ignore_rules(filepath) # Show empty list for new file
                         self.ignore_frame.config(text=f"Ignore Rules ({os.path.basename(filepath)})")
                     else:
                         # Error handled in create_empty_file
                         self.current_ignore_file_path.set("")
                         self._clear_and_display_ignore_rules(None)
                else:
                    # User chose not to create, clear the selection
                    self.current_ignore_file_path.set("")
                    self._clear_and_display_ignore_rules(None)
        else:
            self._update_status("Ignore file selection cancelled.")


    # --- Ignore List Management (Revised) ---

    def _load_and_display_ignore_rules(self, filepath):
        """Loads rules from the specified file, updates internal state, and rebuilds the GUI list."""
        if not filepath:
             self._clear_and_display_ignore_rules(None)
             self._update_status("No ignore file selected.")
             return
        try:
            self.ignore_files, self.ignore_folders = load_ignore_rules(filepath)
            self.ignore_dirty = False
            self._rebuild_ignore_list_gui()
            self._update_status(f"Loaded {len(self.ignore_files) + len(self.ignore_folders)} rules from {os.path.basename(filepath)}")
            self.ignore_frame.config(text=f"Ignore Rules ({os.path.basename(filepath)})")
        except Exception as e:
            messagebox.showerror("Load Error", f"Could not load or parse {os.path.basename(filepath)}:\n{e}")
            self._update_status(f"Error loading {os.path.basename(filepath)}")
            self._clear_and_display_ignore_rules(filepath) # Show empty list but keep path association

    def _clear_and_display_ignore_rules(self, filepath):
        """Clears internal state and rebuilds GUI list, optionally updating frame title."""
        self.ignore_files, self.ignore_folders = [], []
        self.ignore_dirty = False
        self._rebuild_ignore_list_gui()
        if filepath:
             self.ignore_frame.config(text=f"Ignore Rules ({os.path.basename(filepath)})")
             self._update_status(f"Cleared rules for {os.path.basename(filepath)}. File ready.", clear_after_ms=4000)
        else:
             self.ignore_frame.config(text="Ignore Rules (No file selected)")
             self._update_status("No ignore file loaded.")


    def _rebuild_ignore_list_gui(self):
        """Clears and rebuilds the visual list of ignore rules in the scrollable frame."""
        # Destroy existing widgets in the frame
        for widget in self.ignore_list_frame.winfo_children():
            widget.destroy()

        row_num = 0
        current_file = self.current_ignore_file_path.get()

        # Add file rules
        if self.ignore_files:
            ttk.Label(self.ignore_list_frame, text="Files:", font=('TkDefaultFont', 9, 'bold')).grid(row=row_num, column=0, columnspan=2, sticky=tk.W, padx=5, pady=(5,2))
            row_num += 1
            for pattern in self.ignore_files: # Assumes already sorted by load/add
                item_frame = ttk.Frame(self.ignore_list_frame)
                item_frame.grid(row=row_num, column=0, columnspan=2, sticky=tk.EW, padx=5, pady=1)
                item_frame.columnconfigure(0, weight=1)

                label_text = f"file: {pattern}"
                max_len = 60
                display_text = label_text if len(label_text) <= max_len else label_text[:max_len-3] + "..."
                tooltip_text = label_text if len(label_text) > max_len else None

                lbl = ttk.Label(item_frame, text=display_text, anchor=tk.W)
                lbl.grid(row=0, column=0, sticky=tk.EW)
                if tooltip_text:
                    ToolTip(lbl, tooltip_text) # Use ToolTip class

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
                tooltip_text = label_text if len(label_text) > max_len else None

                lbl = ttk.Label(item_frame, text=display_text, anchor=tk.W)
                lbl.grid(row=0, column=0, sticky=tk.EW)
                if tooltip_text:
                    ToolTip(lbl, tooltip_text) # Use ToolTip class

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
             placeholder_text = "No ignore rules defined." if current_file else "No ignore file selected or rules defined."
             ttk.Label(self.ignore_list_frame, text=placeholder_text, foreground="grey").grid(row=0, column=0, columnspan=2, padx=5, pady=5)


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
             self._update_status(f"Item '{pattern}' not found for removal.", clear_after_ms=4000)


    def _add_files_to_ignore(self):
        """Adds selected files to the internal ignore list and refreshes GUI."""
        # Check if an ignore file is selected
        if not self.current_ignore_file_path.get():
             messagebox.showwarning("No Ignore File", "Please select or create an ignore file first using 'Browse...'.")
             return

        initial_dir = self.scan_directory.get() or os.path.dirname(self.current_ignore_file_path.get()) or os.path.expanduser("~")
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
        # Check if an ignore file is selected
        if not self.current_ignore_file_path.get():
             messagebox.showwarning("No Ignore File", "Please select or create an ignore file first using 'Browse...'.")
             return

        initial_dir = self.scan_directory.get() or os.path.dirname(self.current_ignore_file_path.get()) or os.path.expanduser("~")
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
        """Saves the current internal ignore lists to the selected .scanIgnore file."""
        current_path = self.current_ignore_file_path.get()

        if not current_path:
            # If no path is set, force user to select one now
            self._update_status("Please select save location for ignore rules.")
            self._browse_ignore_file()
            current_path = self.current_ignore_file_path.get() # Re-check path after browse
            if not current_path:
                 self._update_status("Save cancelled: No ignore file selected.")
                 return # Abort save if browse was cancelled

        # Proceed only if a path is now set
        if not self.ignore_dirty:
             self._update_status(f"No changes to save in {os.path.basename(current_path)}.")
             return

        try:
            save_ignore_rules(current_path, self.ignore_files, self.ignore_folders)
            self.ignore_dirty = False
            # Persist the path used for saving
            save_settings(self.scan_directory.get(), os.path.dirname(self.save_filepath.get()), current_path)
            self._update_status(f"Saved changes to {os.path.basename(current_path)}", clear_after_ms=3000)
        except Exception as e:
            messagebox.showerror("Save Error", f"Could not save {os.path.basename(current_path)}:\n{e}")
            self._update_status(f"Error saving {os.path.basename(current_path)}")


    # --- Default Ignore Rules Handling ---

    def _load_defaults(self):
        """Loads rules from .scanIgnore.defaults and merges them into the current UI lists."""
        if not self.current_ignore_file_path.get():
             messagebox.showwarning("No Ignore File", "Please select or create an ignore file first before loading defaults.")
             return

        try:
            default_files, default_folders = load_ignore_rules(DEFAULT_IGNORE_PATH)
        except Exception as e:
             # Log error but proceed as if defaults were empty
             print(f"Could not load default ignore rules from {DEFAULT_IGNORE_PATH}: {e}")
             default_files, default_folders = [], []
             if not os.path.exists(DEFAULT_IGNORE_PATH):
                  self._update_status(f"Default file {DEFAULT_IGNORE_FILE} not found. No defaults loaded.", clear_after_ms=4000)
             else:
                  self._update_status(f"Error loading defaults from {DEFAULT_IGNORE_FILE}. No defaults loaded.", clear_after_ms=4000)


        merged_files_count = 0
        for f_pattern in default_files:
            if f_pattern not in self.ignore_files:
                self.ignore_files.append(f_pattern)
                merged_files_count += 1

        merged_folders_count = 0
        for f_pattern in default_folders:
            if f_pattern not in self.ignore_folders:
                self.ignore_folders.append(f_pattern)
                merged_folders_count += 1

        total_merged = merged_files_count + merged_folders_count
        if total_merged > 0:
            self.ignore_files.sort()
            self.ignore_folders.sort()
            self.ignore_dirty = True
            self._rebuild_ignore_list_gui()
            self._update_status(f"Merged {total_merged} default rule(s). Save changes to persist.", clear_after_ms=5000)
        else:
            self._update_status(f"No new rules merged from {DEFAULT_IGNORE_FILE}.", clear_after_ms=3000)

    # Inside CodeScannerApp class
    def _edit_defaults_dialog(self):
        """Opens a modal dialog to edit the .scanIgnore.defaults file."""
        # Pass 'self' (the CodeScannerApp instance) to the dialog constructor
        dialog = EditDefaultsDialog(self.root, DEFAULT_IGNORE_PATH, app_instance=self)
        # The dialog handles its own loading/saving logic and modality

    # --- Scan Execution (Threaded, Revised Pre-checks and Loading) ---
    # *** CORRECT INDENTATION ***
    def _run_scan_thread(self, scan_dir, save_path, ignore_files, ignore_folders, used_ignore_file):
         """Target function for the scanning thread. Uses strictly parsed ignores."""
         try:
             with open(save_path, "w", encoding="utf-8") as output_file:
                 output_file.write(f"# Codebase Scan: {os.path.basename(scan_dir)}\n\n")
                 output_file.write(f"**Ignored Rules From:** `{used_ignore_file}`\n\n") # Add which file was used
                 process_directory(scan_dir, output_file, ignore_files, ignore_folders, level=0, status_callback=self._update_status)

             # Post-scan actions (back on main thread)
             def on_scan_complete():
                 save_dir = os.path.dirname(save_path)
                 # Save settings including the *currently selected* ignore file path after scan
                 save_settings(scan_dir, save_dir, self.current_ignore_file_path.get())
                 self._update_status(f"Scan complete. Output saved to: {save_path}", clear_after_ms=10000)
                 messagebox.showinfo("Scan Complete", f"Output successfully saved to:\n{save_path}")

             self.root.after(0, on_scan_complete)

         except Exception as e:
             # Error handling (back on main thread)
             def on_scan_error():
                 error_message = f"An error occurred during scanning or writing: {e}"
                 print(error_message) # Log detailed error
                 self._update_status(f"Error during scan: {e}", clear_after_ms=10000)
                 messagebox.showerror("Scan Error", error_message)

             self.root.after(0, on_scan_error)

    # *** CORRECT INDENTATION ***
    def _run_scan(self):
        """Validates inputs and starts the scan process in a thread."""
        scan_dir = self.scan_directory.get()
        save_path = self.save_filepath.get()
        ignore_path = self.current_ignore_file_path.get() # Get selected ignore file

        # --- Input Validation ---
        if not scan_dir or not os.path.isdir(scan_dir):
            messagebox.showerror("Input Error", "Please select a valid directory to scan.")
            self._update_status("Error: Invalid scan directory.", clear_after_ms=5000)
            return
        if not save_path:
            messagebox.showerror("Input Error", "Please select a valid output file path.")
            self._update_status("Error: Invalid save location.", clear_after_ms=5000)
            return

        # --- NEW: Ignore File Path Check ---
        if not ignore_path:
            messagebox.showerror("Input Error", "Please select or create an ignore file using the 'Browse...' button before scanning.")
            self._update_status("Error: No ignore file selected.", clear_after_ms=5000)
            return
        if not os.path.exists(ignore_path):
             messagebox.showerror("Input Error", f"The selected ignore file does not exist:\n{ignore_path}\nPlease select a valid file.")
             self._update_status("Error: Selected ignore file not found.", clear_after_ms=5000)
             return


        save_dir = os.path.dirname(save_path)
        if not os.path.exists(save_dir):
            try:
                os.makedirs(save_dir)
            except Exception as e:
                 messagebox.showerror("Input Error", f"Could not create save directory:\n{save_dir}\nError: {e}")
                 self._update_status(f"Error: Cannot create save directory.", clear_after_ms=5000)
                 return

        # --- Check for Unsaved Ignore Changes ---
        if self.ignore_dirty:
            confirm = messagebox.askyesno(
                "Unsaved Changes",
                f"You have unsaved changes in the ignore list for\n'{os.path.basename(ignore_path)}'.\n\nSave them before scanning?",
                default=messagebox.YES
            )
            if confirm:
                self._save_ignore_changes()
                if self.ignore_dirty: # Check if save failed (e.g., permission error)
                     messagebox.showerror("Save Failed", f"Could not save {os.path.basename(ignore_path)}. Aborting scan.")
                     self._update_status("Save failed. Scan aborted.", clear_after_ms=5000)
                     return
            else:
                 # User chose not to save. Scan will use the rules currently *in the file*.
                 self._update_status(f"Proceeding with scan using saved rules from {os.path.basename(ignore_path)} (unsaved changes ignored).", clear_after_ms=5000)
                 # No need to reload UI here, just proceed to load for scan thread


        # --- Prepare ignore lists for the scan thread ---
        # ALWAYS load the rules directly from the specified ignore file *at this moment* for the scan.
        try:
            raw_ignore_lines = load_raw_ignore_lines(ignore_path)
            scan_ignore_files, scan_ignore_folders = parse_ignore_lines(raw_ignore_lines)
            status_msg = f"Starting scan, using {len(scan_ignore_files)} file / {len(scan_ignore_folders)} folder patterns from {os.path.basename(ignore_path)}."
            self._update_status(status_msg)
            print(status_msg) # Also log which file is used
        except Exception as e:
            messagebox.showerror("Ignore File Error", f"Could not read or parse {os.path.basename(ignore_path)} for scanning:\n{e}")
            self._update_status(f"Error loading ignore file for scan.", clear_after_ms=5000)
            return

        # --- Start scan in a separate thread ---
        self._update_status("Scanning...")
        scan_thread = threading.Thread(
            target=self._run_scan_thread,
            args=(scan_dir, save_path, scan_ignore_files, scan_ignore_folders, ignore_path), # Pass path for logging
            daemon=True
        )
        scan_thread.start()


# --- Edit Defaults Dialog Class ---
class EditDefaultsDialog(Toplevel):
    def __init__(self, parent, default_filepath, app_instance): # Added app_instance
        super().__init__(parent)
        self.default_filepath = default_filepath
        # self.parent = parent # No longer strictly needed if we have app_instance
        self.app_instance = app_instance # Store the reference to the main app

        self.title(f"Edit Defaults ({os.path.basename(default_filepath)})")
        self.geometry("500x450") # Adjust size as needed
        self.transient(parent) # Associate with parent window
        self.grab_set() # Make modal

        # --- State for Dialog ---
        self.dialog_ignore_files = []
        self.dialog_ignore_folders = []

        # --- Layout ---
        main_dialog_frame = ttk.Frame(self, padding="10")
        main_dialog_frame.pack(fill=tk.BOTH, expand=True)
        main_dialog_frame.columnconfigure(0, weight=1)
        main_dialog_frame.rowconfigure(0, weight=1) # List area expands

        # --- Ignore List Section (Replicated from main app) ---
        dialog_ignore_frame = ttk.LabelFrame(main_dialog_frame, text="Default Ignore Rules", padding="5")
        dialog_ignore_frame.grid(row=0, column=0, columnspan=2, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(0, 10))
        dialog_ignore_frame.columnconfigure(0, weight=1)
        dialog_ignore_frame.rowconfigure(0, weight=1)

        self.dialog_ignore_canvas = tk.Canvas(dialog_ignore_frame, borderwidth=0)
        self.dialog_ignore_list_frame = ttk.Frame(self.dialog_ignore_canvas)
        self.dialog_ignore_scrollbar = ttk.Scrollbar(dialog_ignore_frame, orient="vertical", command=self.dialog_ignore_canvas.yview)
        self.dialog_ignore_canvas.configure(yscrollcommand=self.dialog_ignore_scrollbar.set)

        self.dialog_ignore_canvas.grid(row=0, column=0, sticky="nsew")
        self.dialog_ignore_scrollbar.grid(row=0, column=1, sticky="ns")

        self.dialog_canvas_window = self.dialog_ignore_canvas.create_window((0, 0), window=self.dialog_ignore_list_frame, anchor="nw")

        self.dialog_ignore_list_frame.bind("<Configure>", self._on_dialog_frame_configure)
        self.dialog_ignore_canvas.bind('<Configure>', self._on_dialog_canvas_configure)
        # Bind mouse wheel for dialog canvas
        self.dialog_ignore_canvas.bind("<MouseWheel>", self._on_dialog_mousewheel)
        self.dialog_ignore_canvas.bind("<Button-4>", self._on_dialog_mousewheel)
        self.dialog_ignore_canvas.bind("<Button-5>", self._on_dialog_mousewheel)

        # --- Dialog Buttons Frame ---
        dialog_buttons_frame = ttk.Frame(dialog_ignore_frame)
        dialog_buttons_frame.grid(row=1, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=5)

        add_file_button = ttk.Button(dialog_buttons_frame, text="Add File(s)", command=self._dialog_add_files)
        add_file_button.pack(side=tk.LEFT, padx=5)

        add_folder_button = ttk.Button(dialog_buttons_frame, text="Add Folder", command=self._dialog_add_folder)
        add_folder_button.pack(side=tk.LEFT, padx=5)

        # --- Save/Cancel Buttons ---
        action_buttons_frame = ttk.Frame(main_dialog_frame)
        action_buttons_frame.grid(row=1, column=0, columnspan=2, sticky=tk.E, pady=5)

        save_button = ttk.Button(action_buttons_frame, text="Save Defaults", command=self._save_and_close, style="Accent.TButton")
        save_button.pack(side=tk.LEFT, padx=5)

        cancel_button = ttk.Button(action_buttons_frame, text="Cancel", command=self.destroy)
        cancel_button.pack(side=tk.LEFT, padx=5)

        # --- Load Initial Data ---
        self._load_initial_defaults()

        # Wait for the dialog to close
        self.wait_window(self)

    # --- Dialog Canvas/Scrollbar Helpers ---
    def _on_dialog_frame_configure(self, event=None):
        self.dialog_ignore_canvas.configure(scrollregion=self.dialog_ignore_canvas.bbox("all"))
    def _on_dialog_canvas_configure(self, event):
        self.dialog_ignore_canvas.itemconfig(self.dialog_canvas_window, width=event.width)
    def _on_dialog_mousewheel(self, event):
         # Needs to scroll the *dialog's* canvas
        if event.num == 5 or event.delta < 0: self.dialog_ignore_canvas.yview_scroll(1, "units")
        elif event.num == 4 or event.delta > 0: self.dialog_ignore_canvas.yview_scroll(-1, "units")

    # --- Dialog Data Loading ---
    def _load_initial_defaults(self):
        try:
            # Ensure file exists before loading, create if not
            if not os.path.exists(self.default_filepath):
                print(f"Default ignore file '{self.default_filepath}' not found, creating empty one.")
                create_empty_file(self.default_filepath) # Attempt creation
                # Proceed with empty lists if creation fails or file is empty

            # Now load (will return empty lists if file doesn't exist or is empty/unparseable)
            self.dialog_ignore_files, self.dialog_ignore_folders = load_ignore_rules(self.default_filepath)
            self._rebuild_dialog_ignore_list()
        except Exception as e:
            messagebox.showerror("Load Error", f"Could not load default ignore rules from\n{self.default_filepath}\n\nError: {e}", parent=self)
            # Keep dialog open with empty lists
            self.dialog_ignore_files, self.dialog_ignore_folders = [], []
            self._rebuild_dialog_ignore_list()


    # --- Dialog UI Rebuilding ---
    def _rebuild_dialog_ignore_list(self):
        # Similar to main app's _rebuild_ignore_list_gui, but uses dialog's widgets and state
        for widget in self.dialog_ignore_list_frame.winfo_children():
            widget.destroy()

        row_num = 0
        # Add file rules
        if self.dialog_ignore_files:
            ttk.Label(self.dialog_ignore_list_frame, text="Files:", font=('TkDefaultFont', 9, 'bold')).grid(row=row_num, column=0, columnspan=2, sticky=tk.W, padx=5, pady=(5,2))
            row_num += 1
            for pattern in self.dialog_ignore_files: # Assumes sorted
                item_frame = ttk.Frame(self.dialog_ignore_list_frame)
                item_frame.grid(row=row_num, column=0, columnspan=2, sticky=tk.EW, padx=5, pady=1)
                item_frame.columnconfigure(0, weight=1)
                lbl = ttk.Label(item_frame, text=f"file: {pattern}", anchor=tk.W) # Simplified label for dialog
                lbl.grid(row=0, column=0, sticky=tk.EW)
                remove_button = ttk.Button(item_frame, text="x", width=2, style="Small.TButton",
                                           command=lambda p=pattern: self._dialog_remove_item('file', p))
                remove_button.grid(row=0, column=1, sticky=tk.E, padx=(5, 0))
                row_num += 1

        # Add folder rules
        if self.dialog_ignore_folders:
            ttk.Label(self.dialog_ignore_list_frame, text="Folders:", font=('TkDefaultFont', 9, 'bold')).grid(row=row_num, column=0, columnspan=2, sticky=tk.W, padx=5, pady=(10,2))
            row_num += 1
            for pattern in self.dialog_ignore_folders: # Assumes sorted
                item_frame = ttk.Frame(self.dialog_ignore_list_frame)
                item_frame.grid(row=row_num, column=0, columnspan=2, sticky=tk.EW, padx=5, pady=1)
                item_frame.columnconfigure(0, weight=1)
                lbl = ttk.Label(item_frame, text=f"folder: {pattern}", anchor=tk.W) # Simplified label for dialog
                lbl.grid(row=0, column=0, sticky=tk.EW)
                remove_button = ttk.Button(item_frame, text="x", width=2, style="Small.TButton",
                                           command=lambda p=pattern: self._dialog_remove_item('folder', p))
                remove_button.grid(row=0, column=1, sticky=tk.E, padx=(5, 0))
                row_num += 1

        if not self.dialog_ignore_files and not self.dialog_ignore_folders:
             ttk.Label(self.dialog_ignore_list_frame, text="No default rules defined.", foreground="grey").grid(row=0, column=0, padx=5, pady=5)

        self.dialog_ignore_list_frame.update_idletasks()
        self._on_dialog_frame_configure()

    # --- Dialog Item Management ---
    def _dialog_remove_item(self, item_type, pattern):
        removed = False
        if item_type == 'file':
            if pattern in self.dialog_ignore_files:
                self.dialog_ignore_files.remove(pattern)
                removed = True
        elif item_type == 'folder':
             if pattern in self.dialog_ignore_folders:
                self.dialog_ignore_folders.remove(pattern)
                removed = True
        if removed:
            self._rebuild_dialog_ignore_list() # Update display

    def _dialog_add_files(self):
        initial_dir = os.path.dirname(self.default_filepath) or os.path.expanduser("~")
        filenames = filedialog.askopenfilenames(title="Select File(s) for Default Ignore", initialdir=initial_dir, parent=self)
        if not filenames: return

        added_count = 0
        for fname in filenames:
            basename = os.path.basename(fname)
            if basename and basename not in self.dialog_ignore_files:
                self.dialog_ignore_files.append(basename)
                added_count += 1
        if added_count > 0:
            self.dialog_ignore_files.sort()
            self._rebuild_dialog_ignore_list()

    def _dialog_add_folder(self):
        initial_dir = os.path.dirname(self.default_filepath) or os.path.expanduser("~")
        foldername = filedialog.askdirectory(title="Select Folder for Default Ignore", initialdir=initial_dir, parent=self)
        if not foldername: return

        basename = os.path.basename(foldername)
        if basename and basename not in self.dialog_ignore_folders:
            self.dialog_ignore_folders.append(basename)
            self.dialog_ignore_folders.sort()
            self._rebuild_dialog_ignore_list()

    # --- Dialog Save Action ---
    def _save_and_close(self):
        try:
            save_ignore_rules(self.default_filepath, self.dialog_ignore_files, self.dialog_ignore_folders)

            # Use the stored self.app_instance to update status
            if self.app_instance and hasattr(self.app_instance, '_update_status'):
                self.app_instance._update_status(f"Saved changes to {os.path.basename(self.default_filepath)}", clear_after_ms=3000)

            self.destroy() # Close the dialog
        except Exception as e:
            messagebox.showerror("Save Error", f"Could not save default ignore rules to\n{self.default_filepath}\n\nError: {e}", parent=self)
            # Keep dialog open on error

# --- ToolTip Class (Moved outside CodeScannerApp) ---
class ToolTip:
    def __init__(self, widget, text):
        self.widget = widget
        self.text = text
        self.tooltip = None
        self.id = None # Add id attribute for schedule/unschedule
        self.widget.bind("<Enter>", self.enter)
        self.widget.bind("<Leave>", self.leave)
        self.widget.bind("<ButtonPress>", self.leave) # Hide on click too

    def enter(self, event=None):
        # Small delay before showing
        self.schedule()

    def leave(self, event=None):
        self.unschedule()
        self.hidetip()

    def schedule(self):
        self.unschedule()
        self.id = self.widget.after(500, self.showtip) # 500ms delay

    def unschedule(self):
        # Use getattr to safely access id
        scheduled_id = getattr(self, 'id', None)
        if scheduled_id:
            self.widget.after_cancel(scheduled_id)
            self.id = None

    def showtip(self):
        if self.tooltip: return # Already shown

        x = y = 0
        try: # Add try-except for bbox in case widget is destroyed
            bbox = self.widget.bbox("insert")
            if not bbox: # Handle empty bbox
                 bbox = (0, 0, self.widget.winfo_width(), self.widget.winfo_height())
            x, y, _, _ = bbox
        except tk.TclError: # Widget might not exist anymore
            return

        # Adjust position relative to widget
        root_x = self.widget.winfo_rootx()
        root_y = self.widget.winfo_rooty()
        widget_height = self.widget.winfo_height()
        widget_width = self.widget.winfo_width()

        x = root_x + widget_width // 2
        y = root_y + widget_height + 5 # Default below widget

        self.tooltip = tk.Toplevel(self.widget)
        self.tooltip.wm_overrideredirect(True) # No window decorations
        # Geometry set later after size calculation

        label = tk.Label(self.tooltip, text=self.text, justify='left',
                         background="#ffffe0", relief='solid', borderwidth=1,
                         wraplength=300, # Wrap long tooltips
                         font=("tahoma", "8", "normal"))
        label.pack(ipadx=2, ipady=2)

        # Position tooltip centered below widget if possible
        self.tooltip.update_idletasks() # Ensure size is calculated
        tip_width = self.tooltip.winfo_width()
        tip_height = self.tooltip.winfo_height()

        # Recalculate x to center it
        x = root_x + (widget_width - tip_width) // 2


        # Basic screen boundary check
        screen_width = self.widget.winfo_screenwidth()
        screen_height = self.widget.winfo_screenheight()

        if x + tip_width > screen_width:
            x = screen_width - tip_width - 5
        if x < 0 :
            x = 5
        if y + tip_height > screen_height:
            y = root_y - tip_height - 5 # Try above widget
            if y < 0: # If still off-screen above, place beside
                 y = root_y + 5
                 x = root_x + widget_width + 5 # To the right
                 if x + tip_width > screen_width: # Check again if right is off-screen
                      x = root_x - tip_width - 5 # Place to the left

        self.tooltip.wm_geometry(f"+{int(x)}+{int(y)}")


    def hidetip(self):
        if self.tooltip:
            try: # Add try-except in case tooltip is already destroyed
                 self.tooltip.destroy()
            except tk.TclError:
                 pass
        self.tooltip = None

# --- Main Execution ---
if __name__ == "__main__":
    root = tk.Tk()
    # Monkey patching removed, ToolTip class used directly where needed.
    app = CodeScannerApp(root)
    # Set the app instance name for potential access from dialog
    root.mainloop()