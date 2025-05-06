# CodebaseScanner_gui.py

import os
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext, Toplevel
import threading # Import threading for non-blocking scan
import shutil # Potentially useful, though not strictly needed for create empty file
import fnmatch # For potential wildcard matching if needed later (not used for current rules)

# --- Constants and Configuration ---
SETTINGS_FILE = ".scan_config.txt"
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SETTINGS_PATH = os.path.join(SCRIPT_DIR, SETTINGS_FILE)

# Default ignore file configuration
DEFAULT_IGNORE_FILE = ".scanIgnore.defaults"
DEFAULT_IGNORE_PATH = os.path.join(SCRIPT_DIR, DEFAULT_IGNORE_FILE)

# Default Output Filename
DEFAULT_OUTPUT_FILENAME = "ProgramCodebaseContext.txt"

# Filter Modes
FILTER_BLACKLIST = "blacklist"
FILTER_WHITELIST = "whitelist"


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
    """Loads saved directory, ignore file path, and filter mode settings."""
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
    # Set default filter mode if not found
    if 'filter_mode' not in settings:
        settings['filter_mode'] = FILTER_BLACKLIST
    return settings

def save_settings(scan_directory, save_directory, ignore_file_path, filter_mode):
    """Saves the directory, ignore file path, and filter mode settings."""
    try:
        with open(SETTINGS_PATH, "w", encoding="utf-8") as f:
            if scan_directory:
                f.write(f"scan_directory={scan_directory}\n")
            if save_directory:
                f.write(f"save_directory={save_directory}\n")
            if ignore_file_path: # Save the selected ignore file path
                f.write(f"ignore_file_path={ignore_file_path}\n")
            if filter_mode: # Save the filter mode
                f.write(f"filter_mode={filter_mode}\n")
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
            f.write("# Files to ignore/include\n") # Adjusted comment
            # Sort alphabetically before saving for consistency
            for pattern in sorted(ignore_files):
                f.write(f"file: {pattern}\n")

            f.write("\n# Folders to ignore/include\n") # Adjusted comment
            # Sort alphabetically before saving for consistency
            for pattern in sorted(ignore_folders):
                f.write(f"folder: {pattern}\n")
    except Exception as e:
        print(f"Error saving ignore file '{ignore_file_path}': {e}")
        raise # Re-raise to be caught by the GUI save logic

# parse_ignore_lines function (Used by the scan thread - Accepts path)
def parse_ignore_lines(lines):
    """
    Parses lines STRICTLY into file/folder patterns. Used by the background scan process.
    Only lines starting with 'file:' or 'folder:' are considered valid.    """
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


# --- Scan Logic (Revised for Filter Modes) ---

def should_process_item(item_name, item_path, is_file, rules_files, rules_folders, filter_mode, is_whitelisted_folder_content=False):
    """
    Determines if a file or folder should be processed based on the filter mode and rules.
    Args:
        item_name (str): The basename of the file or folder.
        item_path (str): The full path of the item (currently unused, but available).
        is_file (bool): True if the item is a file, False if a folder.
        rules_files (list): List of file patterns from the rules file.
        rules_folders (list): List of folder patterns from the rules file.
        filter_mode (str): Either FILTER_BLACKLIST or FILTER_WHITELIST.
        is_whitelisted_folder_content (bool): True if this item is inside a folder
                                             that was explicitly whitelisted.
    Returns:
        bool: True if the item should be processed, False otherwise.
    """
    rules = rules_files if is_file else rules_folders

    if filter_mode == FILTER_BLACKLIST:
        # Blacklist: Ignore if it matches any rule
        for pattern in rules:
            # Using simple substring matching as per original logic
            if pattern in item_name:
                return False # Ignore if matched
        return True # Include if not matched

    elif filter_mode == FILTER_WHITELIST:
        # Whitelist:
        if is_whitelisted_folder_content:
            # If parent folder was whitelisted, include everything inside it (files and folders)
            # UNLESS a more specific rule for this item type excludes it (not current logic, but for future thought)
            # For now, if parent is whitelisted, item is considered for inclusion.
            # Specific check for file or folder rule matching is still needed.
            pass # Fall through to pattern matching for this item

        # Include only if it *exactly* matches a rule (using substring for now as per original)
        for pattern in rules:
            if pattern in item_name:
                return True # Include if matched
        # If this is content of a whitelisted folder and it's a file, it should be included
        # even if it doesn't match a specific 'file:' rule.
        # Folders inside whitelisted folders are also included to continue recursion.
        if is_whitelisted_folder_content:
            return True

        return False # Exclude if not matched by any whitelist rule (and not in whitelisted folder)

    else:
        # Should not happen, default to blacklist behavior
        print(f"Warning: Unknown filter mode '{filter_mode}'. Defaulting to blacklist.")
        for pattern in rules:
            if pattern in item_name:
                return False
        return True


def process_directory(directory, output_file, rules_files, rules_folders, filter_mode, level=0, status_callback=None, is_whitelisted_content=False):
    """
    Processes a directory recursively based on the selected filter mode.
    Returns True if this directory or any of its children contained whitelisted content, False otherwise.
    This return value is used in WHITELIST mode to determine if a parent directory header should be printed.
    """
    heading_level = level + 2
    heading_prefix = "#" * heading_level
    found_whitelisted_content_in_this_branch = False

    if status_callback:
        status_callback(f"Processing: {directory}")

    try:
        items = os.listdir(directory)
    except Exception as e:
        if filter_mode == FILTER_BLACKLIST or is_whitelisted_content:
            output_file.write(f"{heading_prefix} Error Reading Directory\n\n")
            output_file.write(f"**Path:** `{directory}`\n\n")
            output_file.write(f"**Error:** `{e}`\n\n")
        if status_callback:
            status_callback(f"Error reading: {directory}")
        return False # No content found or processed

    # --- Item Categorization ---
    # files_to_consider and dirs_to_recurse will hold items that *might* be processed
    # based on initial rule checks or mode specifics.
    files_to_consider = []
    dirs_to_recurse = []
    
    # In WHITELIST mode, we need to track if a subdirectory itself matches a folder: rule
    # to correctly pass down the is_whitelisted_content flag.
    explicitly_whitelisted_subdirs = [] 

    for item in items:
        item_path = os.path.join(directory, item)
        is_file = os.path.isfile(item_path)

        if filter_mode == FILTER_BLACKLIST:
            # Blacklist mode: if item passes should_process_item, add it.
            if should_process_item(item, item_path, is_file, rules_files, rules_folders, filter_mode, is_whitelisted_content):
                if is_file:
                    files_to_consider.append(item)
                else:
                    dirs_to_recurse.append(item)
        
        elif filter_mode == FILTER_WHITELIST:
            # Whitelist mode:
            # 1. All directories are initially added for recursion to find whitelisted files within them.
            # 2. Files are added if they match a file: rule OR if they are within an already whitelisted folder stream.
            # 3. We also track if a directory *itself* matches a folder: rule.
            if is_file:
                # A file is processed if it's in whitelisted content OR it matches a 'file:' rule directly.
                if should_process_item(item, item_path, True, rules_files, rules_folders, filter_mode, is_whitelisted_content):
                    files_to_consider.append(item)
            else: # Is directory
                # ALWAYS add subdirectories to the recursion list in WHITELIST mode to check for nested whitelisted files.
                dirs_to_recurse.append(item)
                # Check if this directory itself matches a 'folder:' rule to set 'is_whitelisted_content' for the next level.
                # This uses should_process_item, but specifically for a directory match, not for general content.
                if not is_whitelisted_content: # Only check if not already in whitelisted stream
                    for pattern in rules_folders:
                        if pattern in item: # Current directory name matches a folder rule
                            explicitly_whitelisted_subdirs.append(item)
                            break
    
    files_to_consider.sort()
    dirs_to_recurse.sort()

    # --- Recursive Processing for Subdirectories ---
    # Stores subdirectory names that, after recursion, were found to contain whitelisted content
    # or were themselves whitelisted.
    subdirs_with_content = [] 

    for dir_name in dirs_to_recurse:
        sub_dir_path = os.path.join(directory, dir_name)
        
        # Determine if the next level of recursion is considered whitelisted content.
        # It is if:
        #   a) The current directory (self) is part of a whitelisted content stream (is_whitelisted_content is True).
        #   OR
        #   b) This specific sub_dir_path (dir_name) matched a 'folder:' rule.
        next_level_is_whitelisted = is_whitelisted_content or (dir_name in explicitly_whitelisted_subdirs)

        if process_directory(sub_dir_path, output_file, rules_files, rules_folders, filter_mode, level + 1, status_callback, next_level_is_whitelisted):
            found_whitelisted_content_in_this_branch = True
            subdirs_with_content.append(dir_name) # This subdir (or its children) has content

    # --- Output Logic ---
    # Determine if this directory's header should be written.

    # Is the current directory itself explicitly whitelisted by a folder rule?
    current_dir_is_explicitly_whitelisted = False
    if filter_mode == FILTER_WHITELIST and not is_whitelisted_content: # if not is_whitelisted_content, it means this dir's parent was not a whitelisted folder
        dir_basename = os.path.basename(directory)
        for pattern in rules_folders:
            if pattern in dir_basename:
                current_dir_is_explicitly_whitelisted = True
                break
    
    # In WHITELIST mode, found_whitelisted_content_in_this_branch is True if any whitelisted file was found directly
    # in this directory, or if any subdirectory processed contained whitelisted content.
    # If files_to_consider is not empty, it means whitelisted files were found directly in this directory.
    if files_to_consider: # This implies whitelisted files are directly in this folder
        found_whitelisted_content_in_this_branch = True


    should_write_dir_header = False
    if filter_mode == FILTER_BLACKLIST:
        # In Blacklist mode, write header if there are any items (files or dirs) to process,
        # or if the directory is empty but not ignored (empty dir listing).
        # The check for ignored directories happens before process_directory is called for them.
        should_write_dir_header = bool(files_to_consider or dirs_to_recurse or not items) # items refers to os.listdir
    elif filter_mode == FILTER_WHITELIST:
        # In Whitelist mode, write header if:
        # 1. The directory itself is explicitly whitelisted by a 'folder:' rule.
        # OR
        # 2. It contains (directly or via subdirectories) any files whitelisted by 'file:' rules.
        #    (tracked by found_whitelisted_content_in_this_branch)
        # OR (edge case for whitelisted folder content)
        # 3. If `is_whitelisted_content` is true, and this directory has *any* content to show (files_to_consider or subdirs_with_content)
        if current_dir_is_explicitly_whitelisted:
            should_write_dir_header = True
        elif found_whitelisted_content_in_this_branch: # This covers files in current dir or whitelisted content in subdirs
             should_write_dir_header = True
        elif is_whitelisted_content and (files_to_consider or subdirs_with_content): # Content of an already whitelisted folder
             should_write_dir_header = True


    if not should_write_dir_header:
        return found_whitelisted_content_in_this_branch # Still return if any whitelisted items were found for parent's sake

    # --- Write Directory Header and Files ---
    output_file.write(f"{heading_prefix} Directory: {os.path.basename(directory)}\n\n")
    output_file.write(f"**Path:** `{directory}`\n\n")

    if files_to_consider:
        file_heading_level = heading_level + 1
        file_heading_prefix = "#" * file_heading_level
        output_file.write(f"{file_heading_prefix} Files\n\n")
        for file_name in files_to_consider:
            file_path = os.path.join(directory, file_name)
            output_file.write(f"**File:** `{file_name}`\n")
            lang_hint = get_language_hint(file_name)
            try:
                with open(file_path, "r", encoding="utf-8", errors='ignore') as f_content:
                    content = f_content.read()
                output_file.write(f"```{lang_hint}\n")
                output_file.write(content)
                output_file.write(f"\n```\n\n")
            except Exception as e:
                output_file.write(f"**Error reading file:** `{e}`\n\n")
                if status_callback:
                    status_callback(f"Error reading file: {file_path}")
    
    # The recursive calls to process_directory for subdirectories that *should* be outputted
    # have already happened and written their content. We don't re-iterate here for output,
    # only for logic to decide if THIS directory's header was needed.

    return found_whitelisted_content_in_this_branch or current_dir_is_explicitly_whitelisted or (is_whitelisted_content and (files_to_consider or subdirs_with_content))


# --- GUI Application Class ---

class CodeScannerApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Codebase Scanner")
        # self.root.geometry("700x750") # Increased height slightly for filter mode toggle

        # --- Variables ---
        self.scan_directory = tk.StringVar()
        self.save_filepath = tk.StringVar()
        self.current_ignore_file_path = tk.StringVar() # Holds path to active ignore file
        self.status_text = tk.StringVar()
        self.status_text.set("Initializing...")
        self.filter_mode_var = tk.StringVar() # Variable for filter mode (blacklist/whitelist)

        # --- Revised Internal Ignore State ---
        self.ignore_files = [] # List of file patterns (strings) in UI
        self.ignore_folders = [] # List of folder patterns (strings) in UI
        self.ignore_dirty = False # Flag to track unsaved changes in UI

        # --- Load Initial Settings ---
        settings = load_settings()
        self.scan_directory.set(settings.get('scan_directory', ''))
        initial_save_dir = settings.get('save_directory', '')
        self.current_ignore_file_path.set(settings.get('ignore_file_path', '')) # Load ignore file path
        self.filter_mode_var.set(settings.get('filter_mode', FILTER_BLACKLIST)) # Load filter mode

        # Set default save path using the constant filename
        if initial_save_dir:
            # Use loaded save directory but always the default filename
            self.save_filepath.set(os.path.join(initial_save_dir, DEFAULT_OUTPUT_FILENAME))
        elif self.scan_directory.get():
             # Suggest save in parent of scan dir if save dir wasn't loaded
             self._suggest_save_filename()
        else:
             # Fallback to just the filename if no dirs are set
             self.save_filepath.set(DEFAULT_OUTPUT_FILENAME)


        # --- GUI Layout ---
        main_frame = ttk.Frame(root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        root.columnconfigure(0, weight=1)
        root.rowconfigure(0, weight=1) # Allow main frame to expand

        # Row indices will be updated as we add the filter mode toggle
        current_row = 0

        # Scan Directory Row
        ttk.Label(main_frame, text="Scan Directory:").grid(row=current_row, column=0, sticky=tk.W, pady=2)
        scan_entry = ttk.Entry(main_frame, textvariable=self.scan_directory, width=60)
        scan_entry.grid(row=current_row, column=1, sticky=(tk.W, tk.E), padx=5, pady=2)
        scan_button = ttk.Button(main_frame, text="Browse...", command=self._browse_scan_directory)
        scan_button.grid(row=current_row, column=2, sticky=tk.E, padx=5, pady=2)
        current_row += 1

        # Save File Row
        ttk.Label(main_frame, text="Save Output As:").grid(row=current_row, column=0, sticky=tk.W, pady=2)
        save_entry = ttk.Entry(main_frame, textvariable=self.save_filepath, width=60)
        save_entry.grid(row=current_row, column=1, sticky=(tk.W, tk.E), padx=5, pady=2)
        save_button = ttk.Button(main_frame, text="Browse...", command=self._browse_save_file)
        save_button.grid(row=current_row, column=2, sticky=tk.E, padx=5, pady=2)
        current_row += 1

        # Ignore File Path Row
        ttk.Label(main_frame, text="Rules File:").grid(row=current_row, column=0, sticky=tk.W, pady=2) # Renamed label slightly
        ignore_file_entry = ttk.Entry(main_frame, textvariable=self.current_ignore_file_path, width=60, state='readonly') # Read-only display
        ignore_file_entry.grid(row=current_row, column=1, sticky=(tk.W, tk.E), padx=5, pady=2)
        ignore_file_button = ttk.Button(main_frame, text="Browse...", command=self._browse_ignore_file)
        ignore_file_button.grid(row=current_row, column=2, sticky=tk.E, padx=5, pady=2)
        ToolTip(ignore_file_button, "Select or create the rules file (.scanIgnore, etc.)")
        current_row += 1

        # --- NEW: Filter Mode Toggle Row ---
        filter_mode_frame = ttk.Frame(main_frame)
        filter_mode_frame.grid(row=current_row, column=0, columnspan=3, sticky=tk.W, pady=(5, 2))
        self.filter_mode_check = ttk.Checkbutton(
            filter_mode_frame,
            text="Whitelist Mode (Include Only Listed Items)",
            variable=self.filter_mode_var,
            onvalue=FILTER_WHITELIST,
            offvalue=FILTER_BLACKLIST,
            command=self._on_filter_mode_change # Add command to update settings potentially
        )
        self.filter_mode_check.pack(side=tk.LEFT)
        ToolTip(self.filter_mode_check, "Check: Only include items matching rules.\nUncheck (Default): Include all items EXCEPT those matching rules.")
        current_row += 1


        # --- Ignore List Section (Label updated dynamically) ---
        self.ignore_frame = ttk.LabelFrame(main_frame, text="Rules List", padding="5") # Generic name
        self.ignore_frame.grid(row=current_row, column=0, columnspan=3, sticky=(tk.W, tk.E, tk.N, tk.S), pady=10)
        self.ignore_frame.columnconfigure(0, weight=1)
        self.ignore_frame.rowconfigure(0, weight=1) # Allow canvas/list to expand
        current_row += 1 # Increment row index for next element

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

        add_file_button = ttk.Button(ignore_buttons_frame, text="Add File Rule(s)", command=self._add_files_to_ignore)
        add_file_button.pack(side=tk.LEFT, padx=5)

        add_folder_button = ttk.Button(ignore_buttons_frame, text="Add Folder Rule", command=self._add_folder_to_ignore)
        add_folder_button.pack(side=tk.LEFT, padx=5)

        # Default Buttons
        load_defaults_button = ttk.Button(ignore_buttons_frame, text="Load Defaults", command=self._load_defaults)
        load_defaults_button.pack(side=tk.LEFT, padx=5)
        ToolTip(load_defaults_button, f"Merge rules from {DEFAULT_IGNORE_FILE}")

        edit_defaults_button = ttk.Button(ignore_buttons_frame, text="Edit Defaults", command=self._edit_defaults_dialog)
        edit_defaults_button.pack(side=tk.LEFT, padx=5)
        ToolTip(edit_defaults_button, f"Open editor for {DEFAULT_IGNORE_FILE}")

        # Save Button (Existing)
        save_ignore_button = ttk.Button(ignore_buttons_frame, text="Save Rules List", command=self._save_ignore_changes)
        save_ignore_button.pack(side=tk.LEFT, padx=5) # Explicit save button
        ToolTip(save_ignore_button, "Save current rules to the selected rules file.")


        # --- Initial Load/Prompt for Ignore File ---
        self._initialize_ignore_file() # This also updates the frame title


        # Run Scan Button
        run_button = ttk.Button(main_frame, text="Run Scan", command=self._run_scan, style="Accent.TButton")
        run_button.grid(row=current_row, column=0, columnspan=3, pady=10) # Use updated row index
        current_row += 1
        style = ttk.Style()
        try:
            style.configure("Accent.TButton", font=('TkDefaultFont', 10, 'bold'))
        except tk.TclError:
             print("Could not apply custom button style.")

        # Status Bar
        status_bar = ttk.Label(root, textvariable=self.status_text, relief=tk.SUNKEN, anchor=tk.W, padding="2 5")
        status_bar.grid(row=1, column=0, sticky=(tk.W, tk.E)) # Grid row for status bar is outside main_frame

        # Configure resizing behavior
        main_frame.columnconfigure(1, weight=1) # Allow entry fields to expand horizontally
        main_frame.rowconfigure(current_row - 2, weight=1) # Allow ignore list section (row just before Run button) to expand vertically

        self.status_text.set("Ready") # Set status after init


    # --- Canvas/Scrollbar Helpers (Unchanged) ---
    def _on_frame_configure(self, event=None):
        self.ignore_canvas.configure(scrollregion=self.ignore_canvas.bbox("all"))
    def _on_canvas_configure(self, event):
        self.ignore_canvas.itemconfig(self.canvas_window, width=event.width)
    def _on_mousewheel(self, event):
        # Determine the canvas to scroll based on where the mouse is
        canvas_to_scroll = None
        widget_under_mouse = event.widget.winfo_containing(event.x_root, event.y_root)
        if widget_under_mouse:
            # Check if mouse is over the main ignore list canvas or its children
            parent_widget = widget_under_mouse
            while parent_widget is not None:
                 if parent_widget == self.ignore_canvas:
                     canvas_to_scroll = self.ignore_canvas
                     break
                 # Add checks here if other scrollable areas are added later
                 parent_widget = parent_widget.master # Check parent widget

        if canvas_to_scroll: # Only scroll if we identified the correct canvas
             if event.num == 5 or event.delta < 0: canvas_to_scroll.yview_scroll(1, "units")
             elif event.num == 4 or event.delta > 0: canvas_to_scroll.yview_scroll(-1, "units")

    # --- Status Update (Unchanged) ---
    def _update_status(self, message, clear_after_ms=None):
        self.status_text.set(message)
        self.root.update_idletasks()
        if clear_after_ms:
            self.root.after(clear_after_ms, lambda: self.status_text.set("Ready") if self.status_text.get() == message else None)

    # --- NEW: Filter Mode Change Handler ---
    def _on_filter_mode_change(self):
        """Called when the filter mode checkbutton is toggled."""
        mode = self.filter_mode_var.get()
        # Persist the change immediately
        self._save_current_settings()
        mode_text = "Whitelist" if mode == FILTER_WHITELIST else "Blacklist"
        self._update_status(f"Filter mode changed to {mode_text}.", clear_after_ms=4000)
        self._update_ignore_frame_title() # Update title to reflect mode potentially

    # --- Helper to Save All Current Settings ---
    def _save_current_settings(self):
        """Saves all configurable settings to the config file."""
        scan_dir = self.scan_directory.get()
        # Extract save directory from the full save path
        save_path = self.save_filepath.get()
        save_dir = os.path.dirname(save_path) if save_path else ''
        ignore_path = self.current_ignore_file_path.get()
        filter_mode = self.filter_mode_var.get()
        save_settings(scan_dir, save_dir, ignore_path, filter_mode)


    # --- Browse Functions (Updated for Save Path Suggestion) ---
    def _browse_scan_directory(self):
        initial_dir = self.scan_directory.get() or os.path.expanduser("~")
        directory = filedialog.askdirectory(title="Select Directory to Scan", initialdir=initial_dir)
        if directory:
            self.scan_directory.set(directory)
            # Don't auto-suggest save filename here, keep the user's chosen/default name
            # self._suggest_save_filename() # Removed auto-suggestion on scan dir change
            self._update_status("Scan directory selected.")
            self._save_current_settings() # Save settings on change
        else:
            self._update_status("Scan directory selection cancelled.")

    def _browse_save_file(self):
        initial_dir = os.path.dirname(self.save_filepath.get()) or \
                      settings.get('save_directory', '') or \
                      os.path.expanduser("~") # Use saved dir as primary initial
        initial_file = os.path.basename(self.save_filepath.get()) or DEFAULT_OUTPUT_FILENAME

        filepath = filedialog.asksaveasfilename(
            title="Save Scan Output As",
            initialdir=initial_dir,
            initialfile=initial_file,
            defaultextension=".txt", # Changed default extension
            filetypes=[("Text Files", "*.txt"), ("Markdown Files", "*.md"), ("All Files", "*.*")] # Default to TXT
        )
        if filepath:
            self.save_filepath.set(filepath)
            self._update_status("Save location selected.")
            self._save_current_settings() # Save settings on change
        else:
            self._update_status("Save location selection cancelled.")

    def _suggest_save_filename(self):
         """Suggests the default save filename in an appropriate directory."""
         scan_dir = self.scan_directory.get()
         current_save_path = self.save_filepath.get()
         save_dir = os.path.dirname(current_save_path) if current_save_path else ''

         # If save_dir is not set or invalid, try loading from settings or derive intelligently
         if not save_dir or not os.path.isdir(save_dir):
             settings = load_settings()
             save_dir = settings.get('save_directory', '') # Use saved dir first
             if not save_dir or not os.path.isdir(save_dir):
                 # Fallback: Use scan directory if available, otherwise user home
                 save_dir = scan_dir if scan_dir and os.path.isdir(scan_dir) else os.path.expanduser("~")

         # Always use the default filename
         self.save_filepath.set(os.path.join(save_dir, DEFAULT_OUTPUT_FILENAME))


    # --- Ignore File Path Management ---

    def _initialize_ignore_file(self):
        """Checks the loaded ignore file path and prompts/loads accordingly."""
        filepath = self.current_ignore_file_path.get()
        if filepath:
            if os.path.exists(filepath):
                self._load_and_display_ignore_rules(filepath)
                # Title updated in _load_and_display_ignore_rules
            else:
                create = messagebox.askyesno(
                    "Rules File Not Found",
                    f"Rules file not found at:\n'{filepath}'\n\nCreate a new empty file there?"
                )
                if create:
                    if create_empty_file(filepath):
                         self._clear_and_display_ignore_rules(filepath) # Show empty list
                    else:
                        # Error handled in create_empty_file
                        self.current_ignore_file_path.set("")
                        self._clear_and_display_ignore_rules(None) # Show empty list, no file loaded
                else:
                    self.current_ignore_file_path.set("")
                    self._clear_and_display_ignore_rules(None) # Show empty list, no file loaded
        else:
            self._clear_and_display_ignore_rules(None) # No path set, show empty list

        self._update_ignore_frame_title() # Ensure title is set correctly based on file and mode


    def _browse_ignore_file(self):
        """Allows user to select or create an ignore file."""
        initial_dir = os.path.dirname(self.current_ignore_file_path.get()) or \
                      self.scan_directory.get() or \
                      os.path.expanduser("~")

        filepath = filedialog.asksaveasfilename(
            title="Select or Create Rules File",
            initialdir=initial_dir,
            initialfile=".scanIgnore",
            filetypes=[("ScanIgnore Files", ".scanIgnore"), ("Text Files", "*.txt"), ("All Files", "*.*")] # More flexible types
        )

        if filepath:
            # Check if the user is selecting the *same* file path that's already loaded
            # Avoid unnecessary reloading/prompts if the path hasn't actually changed.
            if filepath == self.current_ignore_file_path.get():
                self._update_status("Selected the current rules file.", clear_after_ms=3000)
                return # No change needed

            # Check for unsaved changes *before* switching files
            if self.ignore_dirty:
                confirm_discard = messagebox.askyesno(
                    "Unsaved Changes",
                    f"You have unsaved changes in the current rules list for\n'{os.path.basename(self.current_ignore_file_path.get())}'.\n\nDiscard changes and load the new file?",
                    default=messagebox.NO # Default to not discarding
                )
                if not confirm_discard:
                    self._update_status("Rules file selection cancelled to keep unsaved changes.")
                    return # User cancelled the switch

            # Proceed with the new file path
            self.current_ignore_file_path.set(filepath)
            if os.path.exists(filepath):
                self._load_and_display_ignore_rules(filepath) # This updates title and resets dirty flag
            else:
                create = messagebox.askyesno(
                    "Create Rules File?",
                    f"File '{os.path.basename(filepath)}' does not exist.\n\nCreate it at this location?"
                )
                if create:
                    if create_empty_file(filepath):
                         self._clear_and_display_ignore_rules(filepath) # Show empty list for new file
                    else:
                         # Error handled in create_empty_file, clear the path
                         self.current_ignore_file_path.set("")
                         self._clear_and_display_ignore_rules(None)
                else:
                     # User chose not to create, clear the selection
                    self.current_ignore_file_path.set("")
                    self._clear_and_display_ignore_rules(None)

            self._save_current_settings() # Persist the newly selected ignore file path
        else:
            self._update_status("Rules file selection cancelled.")


    # --- Ignore List Management (Revised) ---

    def _update_ignore_frame_title(self):
        """Updates the LabelFrame title based on loaded file and filter mode."""
        filepath = self.current_ignore_file_path.get()
        mode = self.filter_mode_var.get()
        mode_text = "(Whitelist Mode)" if mode == FILTER_WHITELIST else "(Blacklist Mode)"

        if filepath:
            title = f"Rules List: {os.path.basename(filepath)} {mode_text}"
        else:
            title = f"Rules List (No file selected) {mode_text}"
        self.ignore_frame.config(text=title)


    def _load_and_display_ignore_rules(self, filepath):
        """Loads rules from the specified file, updates internal state, and rebuilds the GUI list."""
        if not filepath:
            self._clear_and_display_ignore_rules(None)
            self._update_status("No rules file selected.")
            return
        try:
            self.ignore_files, self.ignore_folders = load_ignore_rules(filepath)
            self.ignore_dirty = False # Reset dirty flag on successful load
            self._rebuild_ignore_list_gui()
            self._update_status(f"Loaded {len(self.ignore_files) + len(self.ignore_folders)} rules from {os.path.basename(filepath)}")
            self._update_ignore_frame_title() # Update title after load
        except Exception as e:
            messagebox.showerror("Load Error", f"Could not load or parse {os.path.basename(filepath)}:\n{e}")
            self._update_status(f"Error loading {os.path.basename(filepath)}")
            self._clear_and_display_ignore_rules(filepath) # Show empty list but keep path association if load fails
            self._update_ignore_frame_title() # Update title even on error

    def _clear_and_display_ignore_rules(self, filepath):
        """Clears internal state and rebuilds GUI list, optionally updating frame title."""
        self.ignore_files, self.ignore_folders = [], []
        self.ignore_dirty = False # Reset dirty flag
        self._rebuild_ignore_list_gui()
        self._update_ignore_frame_title() # Update title

        if filepath:
            self._update_status(f"Cleared rules list for {os.path.basename(filepath)}. File ready.", clear_after_ms=4000)
        else:
             self._update_status("No rules file loaded.")


    def _rebuild_ignore_list_gui(self):
        """Clears and rebuilds the visual list of ignore rules in the scrollable frame."""
        # Destroy existing widgets in the frame
        for widget in self.ignore_list_frame.winfo_children():
             widget.destroy()

        row_num = 0
        current_file = self.current_ignore_file_path.get()
        mode = self.filter_mode_var.get()
        rule_type_text = "Include" if mode == FILTER_WHITELIST else "Ignore"

        # Add file rules
        if self.ignore_files:
            ttk.Label(self.ignore_list_frame, text=f"Files to {rule_type_text}:", font=('TkDefaultFont', 9, 'bold')).grid(row=row_num, column=0, columnspan=2, sticky=tk.W, padx=5, pady=(5,2))
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
            ttk.Label(self.ignore_list_frame, text=f"Folders to {rule_type_text}:", font=('TkDefaultFont', 9, 'bold')).grid(row=row_num, column=0, columnspan=2, sticky=tk.W, padx=5, pady=(10,2))
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
             placeholder_text = "No rules defined." if current_file else "No rules file selected or rules defined."
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
            self.ignore_dirty = True # Mark changes as dirty
            self._rebuild_ignore_list_gui() # Update display
            self._update_status(f"Removed rule '{pattern}'. Save changes to persist.", clear_after_ms=4000)
        else:
             self._update_status(f"Rule '{pattern}' not found for removal.", clear_after_ms=4000)


    def _add_files_to_ignore(self):
        """Adds selected file basenames as rules to the internal list."""
        if not self.current_ignore_file_path.get():
             messagebox.showwarning("No Rules File", "Please select or create a rules file first using 'Browse...'.")
             return

        initial_dir = self.scan_directory.get() or os.path.dirname(self.current_ignore_file_path.get()) or os.path.expanduser("~")
        filenames = filedialog.askopenfilenames(
            title="Select File(s) to Add Rule For",
            initialdir=initial_dir
        )
        if not filenames:
            self._update_status("Add file rule(s) cancelled.")
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
            self.ignore_dirty = True # Mark changes as dirty
            self._rebuild_ignore_list_gui()
            self._update_status(f"Added {added_count} file rule(s). Save changes to persist.", clear_after_ms=4000)
        else:
            self._update_status("Selected file rule(s) already in list or invalid.")


    def _add_folder_to_ignore(self):
        """Adds a selected folder basename as a rule to the internal list."""
        if not self.current_ignore_file_path.get():
             messagebox.showwarning("No Rules File", "Please select or create a rules file first using 'Browse...'.")
             return

        initial_dir = self.scan_directory.get() or os.path.dirname(self.current_ignore_file_path.get()) or os.path.expanduser("~")
        foldername = filedialog.askdirectory(
            title="Select Folder to Add Rule For",
            initialdir=initial_dir
        )
        if not foldername:
            self._update_status("Add folder rule cancelled.")
            return

        basename = os.path.basename(foldername)
        if basename and basename not in self.ignore_folders:
            self.ignore_folders.append(basename)
            self.ignore_folders.sort() # Keep sorted
            self.ignore_dirty = True # Mark changes as dirty
            self._rebuild_ignore_list_gui()
            self._update_status(f"Added folder rule '{basename}'. Save changes to persist.", clear_after_ms=4000)
        elif basename:
             self._update_status(f"Folder rule '{basename}' already in list.")
        else:
             self._update_status("Invalid folder selected.")


    def _save_ignore_changes(self):
        """Saves the current internal rules lists to the selected rules file."""
        current_path = self.current_ignore_file_path.get()

        if not current_path:
            # If no path is set, force user to select one now
            self._update_status("Please select save location for rules list.")
            self._browse_ignore_file()
            current_path = self.current_ignore_file_path.get() # Re-check path after browse
            if not current_path:
                 self._update_status("Save cancelled: No rules file selected.")
                 return # Abort save if browse was cancelled

        # Proceed only if a path is now set
        if not self.ignore_dirty:
             self._update_status(f"No changes to save in {os.path.basename(current_path)}.")
             return

        try:
            save_ignore_rules(current_path, self.ignore_files, self.ignore_folders)
            self.ignore_dirty = False # Reset dirty flag on successful save
            # Persist the path *and other settings* used for saving
            self._save_current_settings()
            self._update_status(f"Saved changes to {os.path.basename(current_path)}", clear_after_ms=3000)
        except Exception as e:
            messagebox.showerror("Save Error", f"Could not save {os.path.basename(current_path)}:\n{e}")
            self._update_status(f"Error saving {os.path.basename(current_path)}")


    # --- Default Ignore Rules Handling ---

    def _load_defaults(self):
        """Loads rules from .scanIgnore.defaults and merges them into the current UI lists."""
        if not self.current_ignore_file_path.get():
             messagebox.showwarning("No Rules File", "Please select or create a rules file first before loading defaults.")
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
            self.ignore_dirty = True # Mark as dirty after merging
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
    def _run_scan_thread(self, scan_dir, save_path, rules_files, rules_folders, filter_mode, used_rules_file):
         """Target function for the scanning thread. Uses provided rules and mode."""
         try:
             with open(save_path, "w", encoding="utf-8") as output_file:
                 # Write Header Info
                 output_file.write(f"# Codebase Scan: {os.path.basename(scan_dir)}\n\n")
                 mode_desc = "Whitelist (Including only listed)" if filter_mode == FILTER_WHITELIST else "Blacklist (Excluding listed)"
                 output_file.write(f"**Mode:** `{mode_desc}`\n")
                 rules_source = f"`{used_rules_file}`" if used_rules_file else "`None`"
                 output_file.write(f"**Rules From:** {rules_source}\n\n")

                 # Start processing from the root scan directory
                 process_directory(
                     scan_dir, output_file, rules_files, rules_folders,
                     filter_mode, level=0, status_callback=self._update_status,
                     is_whitelisted_content=False # Root level is never whitelisted content initially
                 )

             # Post-scan actions (back on main thread)
             def on_scan_complete():
                 # Save settings AFTER scan completes successfully
                 self._save_current_settings()
                 self._update_status(f"Scan complete. Output saved to: {save_path}", clear_after_ms=10000)
                 messagebox.showinfo("Scan Complete", f"Output successfully saved to:\n{save_path}")

             self.root.after(0, on_scan_complete)

         except Exception as e:
             # Error handling (back on main thread)
             def on_scan_error():
                 error_message = f"An error occurred during scanning or writing: {e}"
                 print(error_message) # Log detailed error
                 import traceback
                 traceback.print_exc() # Print stack trace for debugging
                 self._update_status(f"Error during scan: {e}", clear_after_ms=10000)
                 messagebox.showerror("Scan Error", error_message)

             self.root.after(0, on_scan_error)

    def _run_scan(self):
        """Validates inputs and starts the scan process in a thread."""
        scan_dir = self.scan_directory.get()
        save_path = self.save_filepath.get()
        rules_path = self.current_ignore_file_path.get() # Get selected rules file
        filter_mode = self.filter_mode_var.get() # Get selected filter mode

        # --- Input Validation ---
        if not scan_dir or not os.path.isdir(scan_dir):
            messagebox.showerror("Input Error", "Please select a valid directory to scan.")
            self._update_status("Error: Invalid scan directory.", clear_after_ms=5000)
            return
        if not save_path:
            messagebox.showerror("Input Error", "Please select a valid output file path.")
            self._update_status("Error: Invalid save location.", clear_after_ms=5000)
            return

        # --- Rules File Path Check ---
        if not rules_path:
            messagebox.showerror("Input Error", "Please select or create a rules file using the 'Browse...' button before scanning.")
            self._update_status("Error: No rules file selected.", clear_after_ms=5000)
            return
        if not os.path.exists(rules_path):
             messagebox.showerror("Input Error", f"The selected rules file does not exist:\n{rules_path}\nPlease select a valid file.")
             self._update_status("Error: Selected rules file not found.", clear_after_ms=5000)
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
                f"You have unsaved changes in the rules list for\n'{os.path.basename(rules_path)}'.\n\nSave them before scanning?",
                default=messagebox.YES
            )
            if confirm:
                self._save_ignore_changes()
                if self.ignore_dirty: # Check if save failed (e.g., permission error)
                     messagebox.showerror("Save Failed", f"Could not save {os.path.basename(rules_path)}. Aborting scan.")
                     self._update_status("Save failed. Scan aborted.", clear_after_ms=5000)
                     return
            else:
                 # User chose not to save. Scan will use the rules currently *in the file*.
                 self._update_status(f"Proceeding with scan using saved rules from {os.path.basename(rules_path)} (unsaved changes ignored).", clear_after_ms=5000)
                 # No need to reload UI here, just proceed to load for scan thread


        # --- Prepare rules lists for the scan thread ---
        # ALWAYS load the rules directly from the specified rules file *at this moment* for the scan.
        scan_rules_files, scan_rules_folders = [], [] # Initialize
        try:
            # Load strictly parsed rules for the scan
            scan_rules_files, scan_rules_folders = load_ignore_rules(rules_path)
            mode_text = "Whitelist" if filter_mode == FILTER_WHITELIST else "Blacklist"
            status_msg = f"Starting {mode_text} scan, using {len(scan_rules_files)} file / {len(scan_rules_folders)} folder patterns from {os.path.basename(rules_path)}."
            self._update_status(status_msg)
            print(status_msg) # Also log which file is used
        except Exception as e:
            messagebox.showerror("Rules File Error", f"Could not read or parse {os.path.basename(rules_path)} for scanning:\n{e}")
            self._update_status(f"Error loading rules file for scan.", clear_after_ms=5000)
            return

        # --- Start scan in a separate thread ---
        self._update_status("Scanning...")
        scan_thread = threading.Thread(
            target=self._run_scan_thread,
            args=(scan_dir, save_path, scan_rules_files, scan_rules_folders, filter_mode, rules_path), # Pass rules path for logging
            daemon=True
        )
        scan_thread.start()


# --- Edit Defaults Dialog Class ---
class EditDefaultsDialog(Toplevel):
    def __init__(self, parent, default_filepath, app_instance): # Added app_instance
        super().__init__(parent)
        self.default_filepath = default_filepath
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
        dialog_ignore_frame = ttk.LabelFrame(main_dialog_frame, text="Default Ignore/Include Rules", padding="5") # Adjusted title
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

        add_file_button = ttk.Button(dialog_buttons_frame, text="Add File Rule(s)", command=self._dialog_add_files)
        add_file_button.pack(side=tk.LEFT, padx=5)

        add_folder_button = ttk.Button(dialog_buttons_frame, text="Add Folder Rule", command=self._dialog_add_folder)
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
        # Check if the event originated from within the dialog's scrollable area
        canvas_to_scroll = None
        widget_under_mouse = event.widget.winfo_containing(event.x_root, event.y_root)
        if widget_under_mouse:
            parent_widget = widget_under_mouse
            while parent_widget is not None:
                if parent_widget == self.dialog_ignore_canvas:
                    canvas_to_scroll = self.dialog_ignore_canvas
                    break
                if parent_widget == self: # Stop if we reach the Toplevel window itself
                    break
                parent_widget = parent_widget.master

        if canvas_to_scroll:
            if event.num == 5 or event.delta < 0: self.dialog_ignore_canvas.yview_scroll(1, "units")
            elif event.num == 4 or event.delta > 0: self.dialog_ignore_canvas.yview_scroll(-1, "units")


    # --- Dialog Data Loading ---
    def _load_initial_defaults(self):
        try:
            # Ensure file exists before loading, create if not
            if not os.path.exists(self.default_filepath):
                print(f"Default rules file '{self.default_filepath}' not found, creating empty one.")
                if not create_empty_file(self.default_filepath): # Attempt creation
                    messagebox.showwarning("File Creation Failed", f"Could not create the default rules file:\n{self.default_filepath}\nProceeding with an empty list.", parent=self)
                   # Keep dialog open with empty lists even if creation failed

            # Now load (will return empty lists if file doesn't exist or is empty/unparseable)
            self.dialog_ignore_files, self.dialog_ignore_folders = load_ignore_rules(self.default_filepath)
            self._rebuild_dialog_ignore_list()
        except Exception as e:
            messagebox.showerror("Load Error", f"Could not load default rules from\n{self.default_filepath}\n\nError: {e}", parent=self)
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
            ttk.Label(self.dialog_ignore_list_frame, text="File Rules:", font=('TkDefaultFont', 9, 'bold')).grid(row=row_num, column=0, columnspan=2, sticky=tk.W, padx=5, pady=(5,2))
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
            ttk.Label(self.dialog_ignore_list_frame, text="Folder Rules:", font=('TkDefaultFont', 9, 'bold')).grid(row=row_num, column=0, columnspan=2, sticky=tk.W, padx=5, pady=(10,2))
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
        filenames = filedialog.askopenfilenames(title="Select File(s) for Default Rule", initialdir=initial_dir, parent=self)
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
        foldername = filedialog.askdirectory(title="Select Folder for Default Rule", initialdir=initial_dir, parent=self)
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
            messagebox.showerror("Save Error", f"Could not save default rules to\n{self.default_filepath}\n\nError: {e}", parent=self)
            # Keep dialog open on error

# --- ToolTip Class (Moved outside CodeScannerApp) ---
class ToolTip:
    """ Standard Tooltip implementation """
    def __init__(self, widget, text):
        self.widget = widget
        self.text = text
        self.tooltip = None
        self.id = None # Add id attribute for schedule/unschedule
        self.x = self.y = 0 # Store position
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

        # Get widget position relative to screen
        x = self.widget.winfo_rootx() + 20 # Offset slightly from mouse
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + 5 # Below widget

        self.tooltip = tk.Toplevel(self.widget)
        self.tooltip.wm_overrideredirect(True) # No window decorations
        self.tooltip.wm_geometry(f"+{int(x)}+{int(y)}")

        label = tk.Label(self.tooltip, text=self.text, justify='left',
                         background="#ffffe0", relief='solid', borderwidth=1,
                         wraplength=300, # Wrap long tooltips
                         font=("tahoma", "8", "normal"))
        label.pack(ipadx=2, ipady=2)

        # Basic screen boundary adjustment (simplified)
        self.tooltip.update_idletasks()
        tip_width = self.tooltip.winfo_width()
        tip_height = self.tooltip.winfo_height()
        screen_width = self.widget.winfo_screenwidth()
        screen_height = self.widget.winfo_screenheight()

        if x + tip_width > screen_width:
             x = screen_width - tip_width - 5
        if x < 0: x= 5

        if y + tip_height > screen_height:
             y = self.widget.winfo_rooty() - tip_height - 5 # Try above
        if y < 0: y = 5

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
    # Load settings once at the start if needed elsewhere, though app loads its own
    settings = load_settings()
    app = CodeScannerApp(root)
    # Set the app instance name for potential access from dialog (already done via constructor)
    root.mainloop()