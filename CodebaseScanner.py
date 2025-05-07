# CodebaseScanner.py

import os
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext, Toplevel, simpledialog
import threading # Import threading for non-blocking scan
import json # For profiles
import fnmatch # For potential wildcard matching if needed later
import sys # Needed to determine if running as a bundled executable

# --- Constants and Configuration ---
PROFILES_FILE = "profiles.json"
# SCRIPT_DIR is the directory of the script file (or _MEIPASS for bundled apps)
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

def get_application_persistent_path(filename):
    """
    Determines the appropriate path for persistent application data files like profiles.json.
    If running as a bundled executable, it's next to the .exe.
    Otherwise, it's next to the .py script.
    """
    if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
        # Running as a bundled executable (PyInstaller)
        # sys.executable is the path to the .exe file
        application_path = os.path.dirname(sys.executable)
    else:
        # Running as a normal Python script
        application_path = SCRIPT_DIR
    return os.path.join(application_path, filename)

PROFILES_PATH = get_application_persistent_path(PROFILES_FILE)

# Default ignore file configuration - .scanIgnore.defaults is bundled with the script
# and will be found in SCRIPT_DIR (which is sys._MEIPASS for frozen apps)
DEFAULT_IGNORE_FILE = ".scanIgnore.defaults"
DEFAULT_IGNORE_PATH = os.path.join(SCRIPT_DIR, DEFAULT_IGNORE_FILE)


# Default Output Filename
DEFAULT_OUTPUT_FILENAME = "ProgramCodebaseContext.txt"

# Filter Modes
FILTER_BLACKLIST = "blacklist"
FILTER_WHITELIST = "whitelist"


# Map common file extensions to Markdown language hints
LANG_MAP = {
    ".py": "python", ".js": "javascript", ".jsx": "javascript", ".ts": "typescript",
    ".tsx": "typescript", ".html": "html", ".css": "css", ".scss": "scss",
    ".json": "json", ".yaml": "yaml", ".yml": "yaml", ".md": "markdown",
    ".sh": "bash", ".java": "java", ".cs": "csharp", ".cpp": "cpp", ".c": "c",
    ".h": "c", ".hpp": "cpp", ".go": "go", ".php": "php", ".rb": "ruby",
    ".rs": "rust", ".swift": "swift", ".kt": "kotlin", ".kts": "kotlin",
    ".sql": "sql", ".xml": "xml", ".dockerfile": "dockerfile", ".txt": "text",
}

# --- Profile Management ---

def load_profiles():
    """Loads profiles from PROFILES_PATH."""
    if os.path.exists(PROFILES_PATH):
        try:
            with open(PROFILES_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data.get("profiles", {}), data.get("last_active_profile_name", None)
        except Exception as e:
            print(f"Error loading profiles from {PROFILES_PATH}: {e}")
            # Optionally, attempt to load from SCRIPT_DIR as a fallback for old versions, then migrate.
            # For now, just fails if PROFILES_PATH is problematic.
    return {}, None

def save_profiles(profiles, last_active_profile_name):
    """Saves profiles and the last active profile name to PROFILES_PATH."""
    try:
        # Ensure the directory for PROFILES_PATH exists
        profiles_dir = os.path.dirname(PROFILES_PATH)
        if not os.path.exists(profiles_dir) and profiles_dir : # Check profiles_dir is not empty string
             os.makedirs(profiles_dir, exist_ok=True)

        with open(PROFILES_PATH, "w", encoding="utf-8") as f:
            json.dump({"profiles": profiles, "last_active_profile_name": last_active_profile_name}, f, indent=4)
        print(f"Profiles saved to: {PROFILES_PATH}")
    except Exception as e:
        print(f"Error saving profiles to {PROFILES_PATH}: {e}")
        # Consider showing a messagebox error to the user if saving fails critically
        messagebox.showerror("Profile Save Error", f"Could not save profiles to:\n{PROFILES_PATH}\n\nError: {e}")


# --- Core Logic Functions ---

def get_language_hint(filename):
    """Determines the Markdown language hint based on the file extension."""
    _, ext = os.path.splitext(filename)
    return LANG_MAP.get(ext.lower(), "")

# --- Ignore File Handling (Revised for Full Paths) ---

def load_ignore_rules(ignore_file_path):
    """
    Loads and strictly parses ignore rules from the specified file.
    Rules are now expected to be full paths.
    """
    ignore_files = []
    ignore_folders = []
    if ignore_file_path and os.path.exists(ignore_file_path):
        try:
            with open(ignore_file_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue

                    path_prefix_len = line.find(":") + 1
                    path_to_store = os.path.normpath(line[path_prefix_len:].strip())


                    if line.lower().startswith("file:"):
                        if path_to_store and path_to_store not in ignore_files:
                            ignore_files.append(path_to_store)
                    elif line.lower().startswith("folder:"):
                        if path_to_store and path_to_store not in ignore_folders:
                            ignore_folders.append(path_to_store)
        except Exception as e:
            print(f"Error loading or parsing ignore file '{ignore_file_path}': {e}")
            raise
    ignore_files.sort()
    ignore_folders.sort()
    return ignore_files, ignore_folders

def save_ignore_rules(ignore_file_path, ignore_files, ignore_folders):
    """
    Saves the ignore rules (full paths) to the specified file.
    """
    if not ignore_file_path:
        raise ValueError("Cannot save ignore rules: No file path specified.")
    try:
        parent_dir = os.path.dirname(ignore_file_path)
        if parent_dir and not os.path.exists(parent_dir):
            os.makedirs(parent_dir)

        with open(ignore_file_path, "w", encoding="utf-8") as f:
            f.write("# Files to ignore/include (full paths)\n")
            for path_rule in sorted(ignore_files): 
                f.write(f"file: {os.path.normpath(path_rule)}\n")

            f.write("\n# Folders to ignore/include (full paths)\n")
            for path_rule in sorted(ignore_folders): 
                f.write(f"folder: {os.path.normpath(path_rule)}\n")
    except Exception as e:
        print(f"Error saving ignore file '{ignore_file_path}': {e}")
        raise

# Helper to create an empty file
def create_empty_file(filepath):
    """Creates an empty file at the specified path, creating directories if needed."""
    try:
        parent_dir = os.path.dirname(filepath)
        if parent_dir and not os.path.exists(parent_dir): # Ensure parent_dir is not an empty string
            os.makedirs(parent_dir, exist_ok=True)
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write("# Files to ignore/include (full paths)\n\n")
            f.write("# Folders to ignore/include (full paths)\n\n")
        print(f"Created empty file: {filepath}")
        return True
    except Exception as e:
        print(f"Error creating empty file '{filepath}': {e}")
        messagebox.showerror("File Creation Error", f"Could not create file:\n{filepath}\nError: {e}")
        return False


# --- Scan Logic (Revised for Full Paths and Whitelist Folder Content) ---

def should_process_item(item_path, is_file, rules_files, rules_folders, filter_mode, whitelisted_parent_folders):
    normalized_item_path = os.path.normpath(item_path)

    if filter_mode == FILTER_BLACKLIST:
        if is_file:
            if normalized_item_path in rules_files: 
                return False 
            for folder_rule in rules_folders: 
                if normalized_item_path.startswith(folder_rule + os.sep) or normalized_item_path == folder_rule:
                    return False
        else: 
            if normalized_item_path in rules_folders: 
                return False 
            for folder_rule in rules_folders: 
                 if normalized_item_path.startswith(folder_rule + os.sep):
                    return False
        return True 

    elif filter_mode == FILTER_WHITELIST:
        for whitelisted_folder_path in whitelisted_parent_folders: 
            if normalized_item_path.startswith(whitelisted_folder_path + os.sep) or normalized_item_path == whitelisted_folder_path:
                return True

        if is_file:
            return normalized_item_path in rules_files
        else: 
            return normalized_item_path in rules_folders
    
    print(f"Warning: Unknown filter mode '{filter_mode}'. Defaulting to include item '{normalized_item_path}'.")
    return True


def process_directory(directory, output_file, rules_files, rules_folders, filter_mode, level=0, status_callback=None, whitelisted_ancestor_folders=None):
    heading_level = level + 2
    heading_prefix = "#" * heading_level
    content_written_for_this_branch = False
    normalized_directory = os.path.normpath(directory)

    current_whitelisted_ancestors = list(whitelisted_ancestor_folders) if whitelisted_ancestor_folders else []
    if filter_mode == FILTER_WHITELIST and normalized_directory in rules_folders:
        if normalized_directory not in current_whitelisted_ancestors:
            current_whitelisted_ancestors.append(normalized_directory)


    if status_callback:
        status_callback(f"Processing: {normalized_directory}")

    try:
        items = os.listdir(normalized_directory)
    except Exception as e:
        is_dir_in_whitelisted_scope = False
        if filter_mode == FILTER_WHITELIST:
            if normalized_directory in rules_folders: 
                is_dir_in_whitelisted_scope = True
            else: 
                for wf_ancestor in (whitelisted_ancestor_folders if whitelisted_ancestor_folders else []):
                    if normalized_directory.startswith(wf_ancestor + os.sep):
                        is_dir_in_whitelisted_scope = True
                        break
        
        if filter_mode == FILTER_BLACKLIST or is_dir_in_whitelisted_scope:
            output_file.write(f"{heading_prefix} Error Reading Directory\n\n")
            output_file.write(f"**Path:** `{normalized_directory}`\n\n")
            output_file.write(f"**Error:** `{e}`\n\n")
            content_written_for_this_branch = True 
        if status_callback:
            status_callback(f"Error reading: {normalized_directory} - {e}")
        return content_written_for_this_branch

    files_to_output = []
    dirs_to_recurse_info = [] 

    for item_name in items:
        item_path = os.path.join(normalized_directory, item_name)
        normalized_item_path = os.path.normpath(item_path)
        is_file = os.path.isfile(normalized_item_path)

        if should_process_item(normalized_item_path, is_file, rules_files, rules_folders, filter_mode, current_whitelisted_ancestors):
            if is_file:
                files_to_output.append(item_name)
            else: 
                dirs_to_recurse_info.append({'name': item_name, 'path': normalized_item_path, 'ancestors': list(current_whitelisted_ancestors)})
        elif filter_mode == FILTER_WHITELIST and not is_file:
            can_contain_whitelisted = False
            for rf_path in rules_files:
                if rf_path.startswith(normalized_item_path + os.sep):
                    can_contain_whitelisted = True
                    break
            if not can_contain_whitelisted:
                for rfo_path in rules_folders:
                    if rfo_path == normalized_item_path or rfo_path.startswith(normalized_item_path + os.sep) :
                        can_contain_whitelisted = True
                        break
            if can_contain_whitelisted:
                 dirs_to_recurse_info.append({'name': item_name, 'path': normalized_item_path, 'ancestors': list(current_whitelisted_ancestors)})


    files_to_output.sort()
    dirs_to_recurse_info.sort(key=lambda x: x['name'])

    processed_subdirs_with_content = []
    for dir_info in dirs_to_recurse_info:
        next_level_ancestors = list(dir_info['ancestors']) 
        if filter_mode == FILTER_WHITELIST and dir_info['path'] in rules_folders: 
            if dir_info['path'] not in next_level_ancestors: 
                next_level_ancestors.append(dir_info['path'])

        if process_directory(dir_info['path'], output_file, rules_files, rules_folders, filter_mode, level + 1, status_callback, next_level_ancestors):
            content_written_for_this_branch = True
            processed_subdirs_with_content.append(dir_info['name'])


    should_write_header = False
    is_current_dir_in_whitelisted_scope = False
    if filter_mode == FILTER_WHITELIST:
        if normalized_directory in rules_folders: 
            is_current_dir_in_whitelisted_scope = True
        else: 
            for wf_ancestor in (whitelisted_ancestor_folders if whitelisted_ancestor_folders else []): 
                if normalized_directory.startswith(wf_ancestor + os.sep):
                    is_current_dir_in_whitelisted_scope = True
                    break
    
    if filter_mode == FILTER_BLACKLIST:
        if files_to_output or processed_subdirs_with_content or (not items and level == 0 and not files_to_output and not processed_subdirs_with_content): 
            should_write_header = True
    elif filter_mode == FILTER_WHITELIST:
        if is_current_dir_in_whitelisted_scope and (files_to_output or processed_subdirs_with_content or not items): 
            should_write_header = True
        elif files_to_output: 
             should_write_header = True
        elif processed_subdirs_with_content: 
             should_write_header = True


    if not should_write_header:
        return content_written_for_this_branch

    output_file.write(f"{heading_prefix} Directory: {os.path.basename(normalized_directory)}\n\n")
    output_file.write(f"**Path:** `{normalized_directory}`\n\n")
    content_written_for_this_branch = True

    if files_to_output:
        file_heading_level = heading_level + 1
        file_heading_prefix = "#" * file_heading_level
        output_file.write(f"{file_heading_prefix} Files\n\n")
        for file_name in files_to_output:
            file_path = os.path.join(normalized_directory, file_name)
            normalized_file_path = os.path.normpath(file_path)
            output_file.write(f"**File:** `{file_name}`\n")
            lang_hint = get_language_hint(file_name)
            try:
                with open(normalized_file_path, "r", encoding="utf-8", errors='ignore') as f_content:
                    content = f_content.read()
                output_file.write(f"```{lang_hint}\n")
                output_file.write(content)
                output_file.write(f"\n```\n\n")
            except Exception as e:
                output_file.write(f"**Error reading file:** `{e}`\n\n")
                if status_callback:
                    status_callback(f"Error reading file: {normalized_file_path} - {e}")
    elif not items and not processed_subdirs_with_content : 
        if filter_mode == FILTER_BLACKLIST or (filter_mode == FILTER_WHITELIST and is_current_dir_in_whitelisted_scope):
            output_file.write(f"*This folder is empty or all its contents were excluded/not included by rules.*\n\n")

    return content_written_for_this_branch


# --- GUI Application Class ---

class CodeScannerApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Codebase Scanner")

        self.scan_directory = tk.StringVar()
        self.save_filepath = tk.StringVar()
        self.current_rules_filepath = tk.StringVar() 
        self.status_text = tk.StringVar()
        self.status_text.set("Initializing...")
        self.filter_mode_var = tk.StringVar(value=FILTER_BLACKLIST)

        self.rules_files = [] 
        self.rules_folders = [] 
        self.rules_dirty = False 

        self.profiles, self.last_active_profile_name = load_profiles()
        self.active_profile_name = None 

        self._configure_fields_from_initial_profile()


        menubar = tk.Menu(root)
        profile_menu = tk.Menu(menubar, tearoff=0)
        profile_menu.add_command(label="Save Profile...", command=self._save_profile_dialog)
        profile_menu.add_command(label="Load Profile...", command=self._load_profile_dialog) 
        profile_menu.add_command(label="Delete Profile...", command=self._delete_profile_dialog) 
        profile_menu.add_separator()
        profile_menu.add_command(label="Manage Profiles...", command=self._manage_profiles_dialog)
        menubar.add_cascade(label="Profiles", menu=profile_menu)
        root.config(menu=menubar)


        main_frame = ttk.Frame(root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        root.columnconfigure(0, weight=1)
        root.rowconfigure(0, weight=1)

        current_row = 0

        ttk.Label(main_frame, text="Scan Directory:").grid(row=current_row, column=0, sticky=tk.W, pady=2)
        scan_entry = ttk.Entry(main_frame, textvariable=self.scan_directory, width=60)
        scan_entry.grid(row=current_row, column=1, sticky=(tk.W, tk.E), padx=5, pady=2)
        scan_button = ttk.Button(main_frame, text="Browse...", command=self._browse_scan_directory)
        scan_button.grid(row=current_row, column=2, sticky=tk.E, padx=5, pady=2)
        current_row += 1

        ttk.Label(main_frame, text="Save Output As:").grid(row=current_row, column=0, sticky=tk.W, pady=2)
        save_entry = ttk.Entry(main_frame, textvariable=self.save_filepath, width=60)
        save_entry.grid(row=current_row, column=1, sticky=(tk.W, tk.E), padx=5, pady=2)
        save_button = ttk.Button(main_frame, text="Browse...", command=self._browse_save_file)
        save_button.grid(row=current_row, column=2, sticky=tk.E, padx=5, pady=2)
        current_row += 1

        ttk.Label(main_frame, text="Rules File:").grid(row=current_row, column=0, sticky=tk.W, pady=2)
        rules_file_entry = ttk.Entry(main_frame, textvariable=self.current_rules_filepath, width=60, state='readonly')
        rules_file_entry.grid(row=current_row, column=1, sticky=(tk.W, tk.E), padx=5, pady=2)
        rules_file_button = ttk.Button(main_frame, text="Browse...", command=self._browse_rules_file)
        rules_file_button.grid(row=current_row, column=2, sticky=tk.E, padx=5, pady=2)
        ToolTip(rules_file_button, "Select or create the path-based rules file (.scanIgnore, etc.)")
        current_row += 1

        filter_mode_frame = ttk.Frame(main_frame)
        filter_mode_frame.grid(row=current_row, column=0, columnspan=3, sticky=tk.W, pady=(5, 2))
        self.filter_mode_check = ttk.Checkbutton(
            filter_mode_frame,
            text="Whitelist Mode (Include Only Listed Paths)",
            variable=self.filter_mode_var,
            onvalue=FILTER_WHITELIST,
            offvalue=FILTER_BLACKLIST,
            command=self._on_filter_mode_change
        )
        self.filter_mode_check.pack(side=tk.LEFT)
        ToolTip(self.filter_mode_check, "Check: Only include items matching full path rules.\nUncheck (Default): Include all items EXCEPT those matching full path rules.")
        current_row += 1

        self.rules_frame = ttk.LabelFrame(main_frame, text="Rules List", padding="5") 
        self.rules_frame.grid(row=current_row, column=0, columnspan=3, sticky=(tk.W, tk.E, tk.N, tk.S), pady=10)
        self.rules_frame.columnconfigure(0, weight=1)
        self.rules_frame.rowconfigure(0, weight=1)
        current_row += 1

        self.rules_canvas = tk.Canvas(self.rules_frame, borderwidth=0)
        self.rules_list_frame = ttk.Frame(self.rules_canvas) 
        self.rules_scrollbar = ttk.Scrollbar(self.rules_frame, orient="vertical", command=self.rules_canvas.yview)
        self.rules_canvas.configure(yscrollcommand=self.rules_scrollbar.set)
        self.rules_canvas.grid(row=0, column=0, sticky="nsew")
        self.rules_scrollbar.grid(row=0, column=1, sticky="ns")
        self.canvas_window = self.rules_canvas.create_window((0, 0), window=self.rules_list_frame, anchor="nw")
        self.rules_list_frame.bind("<Configure>", self._on_frame_configure)
        self.rules_canvas.bind('<Configure>', self._on_canvas_configure)
        self.root.bind_all("<MouseWheel>", self._on_mousewheel, add="+")
        self.root.bind_all("<Button-4>", self._on_mousewheel, add="+")
        self.root.bind_all("<Button-5>", self._on_mousewheel, add="+")


        rules_buttons_frame = ttk.Frame(self.rules_frame)
        rules_buttons_frame.grid(row=1, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=5)

        add_file_button = ttk.Button(rules_buttons_frame, text="Add File Rule(s)", command=self._add_file_rules)
        add_file_button.pack(side=tk.LEFT, padx=5)
        ToolTip(add_file_button, "Add one or more files to the rules list by their full path.")


        add_folder_button = ttk.Button(rules_buttons_frame, text="Add Folder Rule", command=self._add_folder_rule)
        add_folder_button.pack(side=tk.LEFT, padx=5)
        ToolTip(add_folder_button, "Add a folder to the rules list by its full path.")

        edit_defaults_button = ttk.Button(rules_buttons_frame, text="Edit Default Name Patterns", command=self._edit_defaults_dialog)
        edit_defaults_button.pack(side=tk.LEFT, padx=5)
        ToolTip(edit_defaults_button, f"Open editor for {DEFAULT_IGNORE_FILE} which uses name-based patterns (not full paths).")

        save_rules_button = ttk.Button(rules_buttons_frame, text="Save Rules List", command=self._save_rules_list_changes)
        save_rules_button.pack(side=tk.LEFT, padx=5)
        ToolTip(save_rules_button, "Save current path-based rules to the selected rules file.")

        self._initialize_rules_file_and_display()


        run_button = ttk.Button(main_frame, text="Run Scan", command=self._run_scan, style="Accent.TButton")
        run_button.grid(row=current_row, column=0, columnspan=3, pady=10)
        current_row += 1
        style = ttk.Style()
        try:
            style.configure("Accent.TButton", font=('TkDefaultFont', 10, 'bold'))
        except tk.TclError:
             print("Could not apply custom button style.")

        status_bar = ttk.Label(root, textvariable=self.status_text, relief=tk.SUNKEN, anchor=tk.W, padding="2 5")
        status_bar.grid(row=1, column=0, sticky=(tk.W, tk.E))

        main_frame.columnconfigure(1, weight=1)
        main_frame.rowconfigure(current_row - 2, weight=1) 

        if self.active_profile_name:
            self.status_text.set(f"Profile '{self.active_profile_name}' loaded. Ready.")
        else:
            self.status_text.set("Ready. Configure manually or load a profile.")
        self._update_window_title()

    def _configure_fields_from_initial_profile(self):
        profile_to_load_name = self.last_active_profile_name
        configured_successfully = False
        if profile_to_load_name and profile_to_load_name in self.profiles:
            profile_data = self.profiles.get(profile_to_load_name)
            if profile_data:
                self.scan_directory.set(profile_data.get("scan_directory", ""))
                self.save_filepath.set(profile_data.get("save_filepath", os.path.join(os.path.expanduser("~"), DEFAULT_OUTPUT_FILENAME)))
                self.current_rules_filepath.set(profile_data.get("rules_filepath", ""))
                self.filter_mode_var.set(profile_data.get("filter_mode", FILTER_BLACKLIST))
                self.active_profile_name = profile_to_load_name 
                configured_successfully = True

        if not configured_successfully:
            self.scan_directory.set("")
            self.save_filepath.set(os.path.join(os.path.expanduser("~"), DEFAULT_OUTPUT_FILENAME))
            self.current_rules_filepath.set("") 
            self.filter_mode_var.set(FILTER_BLACKLIST)
            self.active_profile_name = None


    def _on_frame_configure(self, event=None):
        self.rules_canvas.configure(scrollregion=self.rules_canvas.bbox("all"))

    def _on_canvas_configure(self, event):
        self.rules_canvas.itemconfig(self.canvas_window, width=event.width)

    def _on_mousewheel(self, event):
        canvas_to_scroll = None
        x_root, y_root = event.x_root, event.y_root
        widget_under_mouse = self.root.winfo_containing(x_root, y_root)

        current_widget = widget_under_mouse
        while current_widget is not None:
            if current_widget == self.rules_canvas: 
                canvas_to_scroll = self.rules_canvas
                break
            if isinstance(current_widget, Toplevel): 
                if hasattr(current_widget, 'dialog_rules_canvas') and current_widget.dialog_rules_canvas.winfo_ismapped():
                    dialog_canvas = current_widget.dialog_rules_canvas
                    cx, cy = dialog_canvas.winfo_rootx(), dialog_canvas.winfo_rooty()
                    cw, ch = dialog_canvas.winfo_width(), dialog_canvas.winfo_height()
                    if cx <= x_root < cx + cw and cy <= y_root < cy + ch:
                        canvas_to_scroll = dialog_canvas
                        break
            if current_widget == self.root: break
            current_widget = current_widget.master

        if canvas_to_scroll:
            if event.num == 5 or event.delta < 0: canvas_to_scroll.yview_scroll(1, "units")
            elif event.num == 4 or event.delta > 0: canvas_to_scroll.yview_scroll(-1, "units")


    def _update_status(self, message, clear_after_ms=None):
        self.status_text.set(message)
        self.root.update_idletasks()
        if clear_after_ms:
            self.root.after(clear_after_ms, lambda: self.status_text.set("Ready") if self.status_text.get() == message else None)

    def _on_filter_mode_change(self):
        mode = self.filter_mode_var.get()
        mode_text = "Whitelist" if mode == FILTER_WHITELIST else "Blacklist"
        self._update_status(f"Filter mode changed to {mode_text}.", clear_after_ms=4000)
        self._update_rules_frame_title()
        self._rebuild_rules_list_gui() 

    def _update_window_title(self):
        title = "Codebase Scanner"
        if self.active_profile_name:
            title += f" - Profile: {self.active_profile_name}"
        self.root.title(title)

    def _save_profile_dialog(self):
        profile_name = simpledialog.askstring("Save Profile", "Enter profile name:", parent=self.root)
        if profile_name:
            profile_name = "".join(c for c in profile_name if c.isalnum() or c in (' ', '_', '-')).strip()
            if not profile_name:
                messagebox.showwarning("Invalid Name", "Profile name cannot be empty or only special characters.", parent=self.root)
                return

            if profile_name in self.profiles:
                if not messagebox.askyesno("Overwrite Profile", f"Profile '{profile_name}' already exists. Overwrite?", parent=self.root):
                    self._update_status("Save profile cancelled.", clear_after_ms=3000)
                    return

            scan_dir = self.scan_directory.get()
            save_fp = self.save_filepath.get()
            rules_fp = self.current_rules_filepath.get()
            filter_mode = self.filter_mode_var.get()

            if not scan_dir or not os.path.isdir(scan_dir):
                messagebox.showwarning("Incomplete Configuration", "Scan directory must be a valid directory.", parent=self.root); return
            if not save_fp :
                messagebox.showwarning("Incomplete Configuration", "Save output path must be set.", parent=self.root); return
            if not rules_fp or not os.path.isfile(rules_fp) : 
                messagebox.showwarning("Incomplete Configuration", "Rules file must be a valid existing file.", parent=self.root); return


            self.profiles[profile_name] = {
                "scan_directory": os.path.normpath(scan_dir),
                "save_filepath": os.path.normpath(save_fp),
                "rules_filepath": os.path.normpath(rules_fp),
                "filter_mode": filter_mode
            }
            self.last_active_profile_name = profile_name
            self.active_profile_name = profile_name
            save_profiles(self.profiles, self.last_active_profile_name)
            self._update_status(f"Profile '{profile_name}' saved.", clear_after_ms=3000)
            self._update_window_title()

    def _apply_profile_settings(self, profile_name, persist_last_active=False):
        """Applies settings from a profile to GUI. Does not save profile automatically unless persist_last_active is True."""
        profile_data = self.profiles.get(profile_name)
        if profile_data:
            self.scan_directory.set(profile_data.get("scan_directory", ""))
            self.save_filepath.set(profile_data.get("save_filepath", DEFAULT_OUTPUT_FILENAME))
            new_rules_filepath = profile_data.get("rules_filepath", "")
            self.filter_mode_var.set(profile_data.get("filter_mode", FILTER_BLACKLIST))

            normalized_new_rules_path = os.path.normpath(new_rules_filepath) if new_rules_filepath else ""
            current_rules_path_val = self.current_rules_filepath.get()
            normalized_current_rules_path = os.path.normpath(current_rules_path_val) if current_rules_path_val else ""

            if normalized_new_rules_path != normalized_current_rules_path and self.rules_dirty:
                if messagebox.askyesno("Unsaved Rules", f"You have unsaved changes in the current rules list for\n'{os.path.basename(normalized_current_rules_path if normalized_current_rules_path else 'Untitled Rules')}'.\nDiscard changes to load rules from the new profile?", default=messagebox.NO, parent=self.root):
                    self.rules_dirty = False 
                else:
                    self._update_status(f"Profile '{profile_name}' load cancelled to keep unsaved rule changes.")
                    return False 

            self.current_rules_filepath.set(new_rules_filepath)
            self._initialize_rules_file_and_display() 

            self.active_profile_name = profile_name 
            if persist_last_active: 
                self.last_active_profile_name = profile_name
                save_profiles(self.profiles, self.last_active_profile_name)

            self._update_window_title()
            return True
        else:
            messagebox.showerror("Error", f"Profile '{profile_name}' not found.", parent=self.root)
            self.active_profile_name = None 
            self._update_window_title()
            return False


    def _load_profile_dialog(self):
        self._manage_profiles_dialog(initial_action="load")


    def _delete_profile_dialog(self):
        self._manage_profiles_dialog(initial_action="delete")

    def _manage_profiles_dialog(self, initial_action="load"):
        if not self.profiles and initial_action != "save": 
            messagebox.showinfo("No Profiles", "No profiles saved yet to manage.", parent=self.root)
            return
        dialog = ManageProfilesDialog(self.root, self.profiles, current_active_profile=self.active_profile_name, app_instance=self, initial_action=initial_action)


    def _execute_load_profile(self, profile_name_to_load):
        """Called by ManageProfilesDialog to actually load."""
        if self._apply_profile_settings(profile_name_to_load, persist_last_active=True):
            self._update_status(f"Profile '{profile_name_to_load}' loaded.", clear_after_ms=3000)


    def _execute_delete_profile(self, profile_name_to_delete):
        """Called by ManageProfilesDialog to actually delete."""
        if profile_name_to_delete in self.profiles:
            del self.profiles[profile_name_to_delete]
            if self.last_active_profile_name == profile_name_to_delete:
                self.last_active_profile_name = None
            if self.active_profile_name == profile_name_to_delete:
                self.active_profile_name = None
                self.scan_directory.set("")
                self.save_filepath.set(os.path.join(os.path.expanduser("~"), DEFAULT_OUTPUT_FILENAME))
                self.current_rules_filepath.set("")
                self._clear_and_display_rules_list(None)
                self._update_status("Active profile was deleted. Please configure or load another.", clear_after_ms=5000)

            save_profiles(self.profiles, self.last_active_profile_name)
            self._update_window_title()
            return True 
        return False


    def _browse_scan_directory(self):
        initial_dir = self.scan_directory.get() or os.path.expanduser("~")
        directory = filedialog.askdirectory(title="Select Directory to Scan", initialdir=initial_dir, parent=self.root)
        if directory:
            self.scan_directory.set(os.path.normpath(directory))
            self._update_status("Scan directory selected.")
        else:
            self._update_status("Scan directory selection cancelled.")

    def _browse_save_file(self):
        current_save_path = self.save_filepath.get()
        initial_dir_suggestion = os.path.dirname(current_save_path) if current_save_path and os.path.isdir(os.path.dirname(current_save_path)) else None
        if not initial_dir_suggestion:
            scan_dir = self.scan_directory.get()
            if scan_dir and os.path.isdir(scan_dir):
                initial_dir_suggestion = scan_dir 
            else:
                initial_dir_suggestion = os.path.expanduser("~")

        initial_file_suggestion = os.path.basename(current_save_path) or DEFAULT_OUTPUT_FILENAME

        filepath = filedialog.asksaveasfilename(
            title="Save Scan Output As",
            initialdir=initial_dir_suggestion,
            initialfile=initial_file_suggestion,
            defaultextension=".txt",
            filetypes=[("Text Files", "*.txt"), ("Markdown Files", "*.md"), ("All Files", "*.*")],
            parent=self.root
        )
        if filepath:
            self.save_filepath.set(os.path.normpath(filepath))
            self._update_status("Save location selected.")
        else:
            self._update_status("Save location selection cancelled.")


    def _initialize_rules_file_and_display(self):
        """Checks loaded rules file path, loads rules, and updates GUI. Resets dirty flag."""
        filepath = self.current_rules_filepath.get()
        if filepath:
            normalized_filepath = os.path.normpath(filepath)
            if os.path.exists(normalized_filepath) and os.path.isfile(normalized_filepath):
                self._load_and_display_rules(normalized_filepath) 
            else:
                prompt_create = messagebox.askyesno(
                    "Rules File Not Found",
                    f"Rules file not found or is not a file:\n'{normalized_filepath}'\n\nCreate a new empty rules file there?",
                    parent=self.root
                )
                if prompt_create:
                    if create_empty_file(normalized_filepath):
                        self._clear_and_display_rules_list(normalized_filepath) 
                    else: 
                        self.current_rules_filepath.set("")
                        self._clear_and_display_rules_list(None)
                else: 
                    self.current_rules_filepath.set("")
                    self._clear_and_display_rules_list(None)
        else: 
            self._clear_and_display_rules_list(None) 
        self._update_rules_frame_title()


    def _browse_rules_file(self):
        """Allows user to select or create a rules file. Handles unsaved changes confirmation."""
        initial_dir_browse = os.path.dirname(self.current_rules_filepath.get()) or \
                             self.scan_directory.get() or \
                             os.path.expanduser("~")

        filepath_selected = filedialog.asksaveasfilename( 
            title="Select or Create Path-Based Rules File",
            initialdir=initial_dir_browse,
            initialfile=".scanIgnore", 
            filetypes=[("ScanIgnore Files", ".scanIgnore"), ("Text Files", "*.txt"), ("All Files", "*.*")],
            parent=self.root
        )

        if filepath_selected:
            normalized_new_filepath = os.path.normpath(filepath_selected)
            current_rules_path_val = self.current_rules_filepath.get()
            current_normalized_path = os.path.normpath(current_rules_path_val) if current_rules_path_val else None


            if normalized_new_filepath == current_normalized_path:
                self._update_status("Selected the current rules file. No change.", clear_after_ms=3000)
                return

            if self.rules_dirty: 
                confirm_discard = messagebox.askyesno(
                    "Unsaved Changes",
                    f"You have unsaved changes in the current rules list for\n'{os.path.basename(current_normalized_path if current_normalized_path else 'Untitled Rules')}'.\n\nDiscard changes and switch to the new file?",
                    default=messagebox.NO, parent=self.root
                )
                if not confirm_discard:
                    self._update_status("Rules file selection cancelled to keep unsaved changes.")
                    return
                self.rules_dirty = False 

            self.current_rules_filepath.set(normalized_new_filepath) 
            if os.path.exists(normalized_new_filepath) and os.path.isfile(normalized_new_filepath):
                self._load_and_display_rules(normalized_new_filepath) 
            else: 
                if create_empty_file(normalized_new_filepath): 
                    self._clear_and_display_rules_list(normalized_new_filepath) 
                else: 
                    self.current_rules_filepath.set(current_normalized_path if current_normalized_path else "") 
                    self._initialize_rules_file_and_display() 
                    self._update_status("Failed to create new rules file. Selection reverted.", clear_after_ms=4000)
            self._update_rules_frame_title()
        else:
            self._update_status("Rules file selection cancelled.")


    def _update_rules_frame_title(self):
        filepath = self.current_rules_filepath.get()
        mode = self.filter_mode_var.get()
        mode_text = "(Whitelist - Include Paths)" if mode == FILTER_WHITELIST else "(Blacklist - Exclude Paths)"
        dirty_star = "*" if self.rules_dirty else "" 

        if filepath:
            title = f"Rules: {os.path.basename(filepath)}{dirty_star} {mode_text}"
        else:
            title = f"Rules (No file selected){dirty_star} {mode_text}"
        self.rules_frame.config(text=title)

    def _load_and_display_rules(self, filepath):
        """Loads rules (full paths) from file, updates state, rebuilds GUI list. Resets dirty flag."""
        if not filepath:
            self._clear_and_display_rules_list(None)
            self._update_status("No rules file selected.")
            return
        try:
            normalized_filepath = os.path.normpath(filepath)
            self.rules_files, self.rules_folders = load_ignore_rules(normalized_filepath)
            self.rules_dirty = False 
            self._rebuild_rules_list_gui()
            self._update_status(f"Loaded {len(self.rules_files) + len(self.rules_folders)} rules from {os.path.basename(normalized_filepath)}")
        except Exception as e:
            messagebox.showerror("Load Error", f"Could not load or parse {os.path.basename(filepath)}:\n{e}", parent=self.root)
            self._update_status(f"Error loading {os.path.basename(filepath)}")
            self._clear_and_display_rules_list(filepath) 
        finally:
            self._update_rules_frame_title() 

    def _clear_and_display_rules_list(self, filepath_context):
        """Clears state, rebuilds GUI list. Resets dirty flag."""
        self.rules_files, self.rules_folders = [], []
        self.rules_dirty = False 
        self._rebuild_rules_list_gui()

        if filepath_context: 
            self._update_status(f"Rules list for {os.path.basename(filepath_context)} is now empty. Ready.", clear_after_ms=4000)

        else: 
            self._update_status("No rules file loaded. Rules list cleared.")
        self._update_rules_frame_title() 


    def _rebuild_rules_list_gui(self):
        if not hasattr(self, 'rules_list_frame'):
            print("Warning: _rebuild_rules_list_gui called before rules_list_frame was initialized.")
            return

        for widget in self.rules_list_frame.winfo_children():
            widget.destroy()

        row_num = 0
        current_file_path = self.current_rules_filepath.get()
        mode = self.filter_mode_var.get()
        rule_action_text = "Include Path" if mode == FILTER_WHITELIST else "Exclude Path"

        if self.rules_files: 
            ttk.Label(self.rules_list_frame, text=f"Files to {rule_action_text}:", font=('TkDefaultFont', 9, 'bold')).grid(row=row_num, column=0, columnspan=2, sticky=tk.W, padx=5, pady=(5,2))
            row_num += 1
            for path_rule in sorted(self.rules_files):
                item_frame = ttk.Frame(self.rules_list_frame)
                item_frame.grid(row=row_num, column=0, columnspan=2, sticky=tk.EW, padx=5, pady=1)
                item_frame.columnconfigure(0, weight=1)

                label_text = f"file: {path_rule}" 
                max_len = 75
                display_text = label_text if len(label_text) <= max_len else "..." + label_text[-(max_len-3):]
                tooltip_text = label_text if len(label_text) > max_len else None

                lbl = ttk.Label(item_frame, text=display_text, anchor=tk.W)
                lbl.grid(row=0, column=0, sticky=tk.EW)
                if tooltip_text: ToolTip(lbl, tooltip_text)

                remove_button = ttk.Button(item_frame, text="x", width=2, style="Small.TButton",
                                           command=lambda p=path_rule: self._remove_rule_item('file', p))
                remove_button.grid(row=0, column=1, sticky=tk.E, padx=(5, 0))
                row_num += 1

        if self.rules_folders: 
            ttk.Label(self.rules_list_frame, text=f"Folders to {rule_action_text}:", font=('TkDefaultFont', 9, 'bold')).grid(row=row_num, column=0, columnspan=2, sticky=tk.W, padx=5, pady=(10,2))
            row_num += 1
            for path_rule in sorted(self.rules_folders):
                item_frame = ttk.Frame(self.rules_list_frame)
                item_frame.grid(row=row_num, column=0, columnspan=2, sticky=tk.EW, padx=5, pady=1)
                item_frame.columnconfigure(0, weight=1)

                label_text = f"folder: {path_rule}" 
                max_len = 75
                display_text = label_text if len(label_text) <= max_len else "..." + label_text[-(max_len-3):]
                tooltip_text = label_text if len(label_text) > max_len else None

                lbl = ttk.Label(item_frame, text=display_text, anchor=tk.W)
                lbl.grid(row=0, column=0, sticky=tk.EW)
                if tooltip_text: ToolTip(lbl, tooltip_text)

                remove_button = ttk.Button(item_frame, text="x", width=2, style="Small.TButton",
                                           command=lambda p=path_rule: self._remove_rule_item('folder', p))
                remove_button.grid(row=0, column=1, sticky=tk.E, padx=(5, 0))
                row_num += 1

        style = ttk.Style()
        try: style.configure("Small.TButton", padding=(1, 1), font=('TkDefaultFont', 7))
        except tk.TclError: pass

        if not self.rules_files and not self.rules_folders:
            placeholder_text = "No rules defined." if current_file_path else "No rules file selected or rules defined."
            ttk.Label(self.rules_list_frame, text=placeholder_text, foreground="grey").grid(row=0, column=0, columnspan=2, padx=5, pady=5)

        self.rules_list_frame.update_idletasks()
        self._on_frame_configure()
        self._update_rules_frame_title() 


    def _remove_rule_item(self, item_type, path_pattern):
        """Removes a full path rule from internal list and refreshes GUI. Path_pattern is assumed normalized."""
        removed = False
        if item_type == 'file':
            if path_pattern in self.rules_files:
                self.rules_files.remove(path_pattern)
                removed = True
        elif item_type == 'folder':
            if path_pattern in self.rules_folders:
                self.rules_folders.remove(path_pattern)
                removed = True

        if removed:
            self.rules_dirty = True
            self._rebuild_rules_list_gui() 
            self._update_status(f"Removed rule for '{os.path.basename(path_pattern)}'. Save changes to persist.", clear_after_ms=4000)
        else: 
            self._update_status(f"Rule for '{os.path.basename(path_pattern)}' not found for removal.", clear_after_ms=4000)


    def _add_file_rules(self):
        """Adds selected files by their full absolute path as rules."""
        if not self.current_rules_filepath.get(): 
            messagebox.showwarning("No Rules File Active", "Please select or create a rules file first before adding rules to it.", parent=self.root)
            return

        initial_dir_add = self.scan_directory.get() if self.scan_directory.get() and os.path.isdir(self.scan_directory.get()) else os.path.expanduser("~")
        filepaths_to_add = filedialog.askopenfilenames(
            title="Select File(s) to Add Rule For (Full Path)",
            initialdir=initial_dir_add, parent=self.root
        )
        if not filepaths_to_add:
            self._update_status("Add file rule(s) cancelled.")
            return

        added_count = 0
        for fp_raw in filepaths_to_add:
            normalized_fp_add = os.path.normpath(fp_raw) 
            if normalized_fp_add and normalized_fp_add not in self.rules_files:
                self.rules_files.append(normalized_fp_add)
                added_count += 1

        if added_count > 0:
            self.rules_files.sort()
            self.rules_dirty = True
            self._rebuild_rules_list_gui() 
            self._update_status(f"Added {added_count} file rule(s). Save changes to persist.", clear_after_ms=4000)
        elif filepaths_to_add : 
            self._update_status("Selected file rule(s) already in list or invalid.")

    def _add_folder_rule(self):
        """Adds a selected folder by its full absolute path as a rule."""
        if not self.current_rules_filepath.get():
            messagebox.showwarning("No Rules File Active", "Please select or create a rules file first before adding rules to it.", parent=self.root)
            return

        initial_dir_add_folder = self.scan_directory.get() if self.scan_directory.get() and os.path.isdir(self.scan_directory.get()) else os.path.expanduser("~")
        folderpath_to_add = filedialog.askdirectory(
            title="Select Folder to Add Rule For (Full Path)",
            initialdir=initial_dir_add_folder, parent=self.root
        )
        if not folderpath_to_add:
            self._update_status("Add folder rule cancelled.")
            return

        normalized_fp_add_folder = os.path.normpath(folderpath_to_add) 
        if normalized_fp_add_folder and normalized_fp_add_folder not in self.rules_folders:
            self.rules_folders.append(normalized_fp_add_folder)
            self.rules_folders.sort()
            self.rules_dirty = True
            self._rebuild_rules_list_gui() 
            self._update_status(f"Added folder rule for '{os.path.basename(normalized_fp_add_folder)}'. Save changes to persist.", clear_after_ms=4000)
        elif normalized_fp_add_folder: 
            self._update_status(f"Folder rule for '{os.path.basename(normalized_fp_add_folder)}' already in list.")


    def _save_rules_list_changes(self):
        """Saves the current internal rules lists (full paths) to the selected rules file."""
        current_path_to_save = self.current_rules_filepath.get()
        if not current_path_to_save: 
            self._update_status("No rules file is active. Please select or create one.")
            messagebox.showerror("Save Error", "No rules file is currently active to save to.", parent=self.root)
            return

        normalized_current_path_save = os.path.normpath(current_path_to_save)
        if not self.rules_dirty:
            self._update_status(f"No unsaved changes in {os.path.basename(normalized_current_path_save)}.")
            return

        try:
            normalized_files_to_save = sorted([os.path.normpath(p) for p in self.rules_files])
            normalized_folders_to_save = sorted([os.path.normpath(p) for p in self.rules_folders])
            save_ignore_rules(normalized_current_path_save, normalized_files_to_save, normalized_folders_to_save)
            self.rules_dirty = False 
            self._rebuild_rules_list_gui() 
            self._update_status(f"Saved changes to {os.path.basename(normalized_current_path_save)}", clear_after_ms=3000)
        except Exception as e:
            messagebox.showerror("Save Error", f"Could not save rules to {os.path.basename(normalized_current_path_save)}:\n{e}", parent=self.root)
            self._update_status(f"Error saving {os.path.basename(normalized_current_path_save)}")


    def _edit_defaults_dialog(self):
        """Opens modal to edit .scanIgnore.defaults (name-based patterns)."""
        dialog = EditDefaultsDialog(self.root, DEFAULT_IGNORE_PATH, app_instance=self)


    def _run_scan_thread(self, scan_dir_norm, save_path_norm, rules_files_for_scan, rules_folders_for_scan, filter_mode_val, used_rules_file_display_path):
        try:
            with open(save_path_norm, "w", encoding="utf-8") as output_file:
                output_file.write(f"# Codebase Scan: {os.path.basename(scan_dir_norm)}\n\n")
                mode_desc = "Whitelist (Including only listed paths)" if filter_mode_val == FILTER_WHITELIST else "Blacklist (Excluding listed paths)"
                output_file.write(f"**Mode:** `{mode_desc}`\n")
                rules_source_display = f"`{os.path.basename(used_rules_file_display_path)}` (from `{used_rules_file_display_path}`)" if used_rules_file_display_path else "`None (No rules file specified)`"
                output_file.write(f"**Rules From:** {rules_source_display}\n\n")

                initial_whitelisted_ancestors = []
                if filter_mode_val == FILTER_WHITELIST and scan_dir_norm in rules_folders_for_scan:
                    initial_whitelisted_ancestors.append(scan_dir_norm)
                
                process_directory(
                    scan_dir_norm, output_file, rules_files_for_scan, rules_folders_for_scan,
                    filter_mode_val, level=0, status_callback=self._update_status,
                    whitelisted_ancestor_folders=initial_whitelisted_ancestors
                )

            def on_scan_complete(): 
                self._update_status(f"Scan complete. Output saved to: {save_path_norm}", clear_after_ms=10000)
                messagebox.showinfo("Scan Complete", f"Output successfully saved to:\n{save_path_norm}", parent=self.root)
            self.root.after(0, on_scan_complete)

        except Exception as e:
            def on_scan_error(): 
                error_message = f"An error occurred during scanning or writing: {e}"
                print(f"Full scan error details: {error_message}")
                import traceback
                traceback.print_exc() 
                self._update_status(f"Error during scan: {e}", clear_after_ms=10000)
                messagebox.showerror("Scan Error", error_message, parent=self.root)
            self.root.after(0, on_scan_error)


    def _run_scan(self):
        scan_dir_ui = self.scan_directory.get()
        save_path_ui = self.save_filepath.get()
        rules_path_ui_current = self.current_rules_filepath.get() 
        filter_mode_selected = self.filter_mode_var.get()

        if not scan_dir_ui or not os.path.isdir(scan_dir_ui):
            messagebox.showerror("Input Error", "Please select a valid directory to scan.", parent=self.root)
            self._update_status("Error: Invalid scan directory.", clear_after_ms=5000); return
        if not save_path_ui:
            messagebox.showerror("Input Error", "Please select a valid output file path.", parent=self.root)
            self._update_status("Error: Invalid save location.", clear_after_ms=5000); return

        if not rules_path_ui_current: 
            messagebox.showerror("Input Error", "Please select or create a rules file using the 'Browse...' button before scanning.", parent=self.root)
            self._update_status("Error: No rules file selected.", clear_after_ms=5000); return

        normalized_rules_path_for_scan = os.path.normpath(rules_path_ui_current)
        if not os.path.exists(normalized_rules_path_for_scan) or not os.path.isfile(normalized_rules_path_for_scan):
             messagebox.showerror("Input Error", f"The selected rules file does not exist or is not a file:\n{normalized_rules_path_for_scan}\nPlease select a valid file.", parent=self.root)
             self._update_status("Error: Selected rules file not found or invalid.", clear_after_ms=5000); return

        save_dir_for_output = os.path.dirname(save_path_ui)
        if not os.path.exists(save_dir_for_output):
            try: os.makedirs(save_dir_for_output, exist_ok=True) 
            except Exception as e:
                 messagebox.showerror("Input Error", f"Could not create save directory:\n{save_dir_for_output}\nError: {e}", parent=self.root)
                 self._update_status(f"Error: Cannot create save directory.", clear_after_ms=5000); return

        if self.rules_dirty: 
            confirm_save = messagebox.askyesno(
                "Unsaved Rule Changes",
                f"You have unsaved changes in the rules list for\n'{os.path.basename(normalized_rules_path_for_scan)}'.\n\nSave them before scanning?",
                default=messagebox.YES, parent=self.root
            )
            if confirm_save:
                self._save_rules_list_changes() 
                if self.rules_dirty: 
                     messagebox.showerror("Save Failed", f"Could not save rule changes to {os.path.basename(normalized_rules_path_for_scan)}. Aborting scan.", parent=self.root)
                     self._update_status("Save failed. Scan aborted.", clear_after_ms=5000); return

        try:
            scan_rules_files_from_file_norm, scan_rules_folders_from_file_norm = load_ignore_rules(normalized_rules_path_for_scan)
            norm_scan_dir_for_thread = os.path.normpath(scan_dir_ui)
            norm_save_path_for_thread = os.path.normpath(save_path_ui)

            mode_text_display_scan = "Whitelist" if filter_mode_selected == FILTER_WHITELIST else "Blacklist"
            status_msg_scan = f"Starting {mode_text_display_scan} scan. Using rules from: {normalized_rules_path_for_scan}."
            self._update_status(status_msg_scan)
            print(status_msg_scan) 
        except Exception as e:
            messagebox.showerror("Rules File Error", f"Could not read or parse rules from {os.path.basename(normalized_rules_path_for_scan)} for scanning:\n{e}", parent=self.root)
            self._update_status(f"Error loading rules file for scan. Scan aborted.", clear_after_ms=5000); return

        self._update_status("Scanning in progress...")
        scan_thread = threading.Thread(
            target=self._run_scan_thread,
            args=(norm_scan_dir_for_thread, norm_save_path_for_thread,
                  scan_rules_files_from_file_norm, scan_rules_folders_from_file_norm, 
                  filter_mode_selected, normalized_rules_path_for_scan), 
            daemon=True
        )
        scan_thread.start()


# --- Edit Defaults Dialog Class (Manages name-based .scanIgnore.defaults) ---
class EditDefaultsDialog(Toplevel):
    def __init__(self, parent, default_filepath, app_instance):
        super().__init__(parent)
        self.default_filepath = default_filepath 
        self.app_instance = app_instance

        self.title(f"Edit Default Name Patterns ({os.path.basename(default_filepath)})")
        self.geometry("600x500") 
        self.transient(parent)
        self.grab_set() 

        self.dialog_rule_file_patterns = []
        self.dialog_rule_folder_patterns = []

        main_dialog_frame = ttk.Frame(self, padding="10")
        main_dialog_frame.pack(fill=tk.BOTH, expand=True)
        main_dialog_frame.columnconfigure(0, weight=1)
        main_dialog_frame.rowconfigure(1, weight=1) 

        input_frame = ttk.Frame(main_dialog_frame)
        input_frame.grid(row=0, column=0, sticky=tk.EW, pady=(0,10))
        input_frame.columnconfigure(0, weight=1)

        self.pattern_entry_var = tk.StringVar()
        pattern_entry = ttk.Entry(input_frame, textvariable=self.pattern_entry_var, width=40)
        pattern_entry.grid(row=0, column=0, sticky=tk.EW, padx=(0,5))
        ToolTip(pattern_entry, "Enter a file/folder name or simple pattern (e.g., '*.log', 'temp_folder') to add to defaults.")

        add_file_pattern_btn = ttk.Button(input_frame, text="Add File Pattern", command=lambda: self._dialog_add_name_pattern('file'))
        add_file_pattern_btn.grid(row=0, column=1, padx=5)
        add_folder_pattern_btn = ttk.Button(input_frame, text="Add Folder Pattern", command=lambda: self._dialog_add_name_pattern('folder'))
        add_folder_pattern_btn.grid(row=0, column=2, padx=5)


        dialog_rules_frame = ttk.LabelFrame(main_dialog_frame, text="Default File/Folder Name Patterns List", padding="5")
        dialog_rules_frame.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        dialog_rules_frame.columnconfigure(0, weight=1)
        dialog_rules_frame.rowconfigure(0, weight=1) 

        self.dialog_rules_canvas = tk.Canvas(dialog_rules_frame, borderwidth=0)
        self.dialog_rules_list_frame = ttk.Frame(self.dialog_rules_canvas) 
        self.dialog_rules_scrollbar = ttk.Scrollbar(dialog_rules_frame, orient="vertical", command=self.dialog_rules_canvas.yview)
        self.dialog_rules_canvas.configure(yscrollcommand=self.dialog_rules_scrollbar.set)

        self.dialog_rules_canvas.grid(row=0, column=0, sticky="nsew") 
        self.dialog_rules_scrollbar.grid(row=0, column=1, sticky="ns") 

        self.dialog_canvas_window = self.dialog_rules_canvas.create_window((0, 0), window=self.dialog_rules_list_frame, anchor="nw")

        self.dialog_rules_list_frame.bind("<Configure>", self._on_dialog_list_frame_configure) 
        self.dialog_rules_canvas.bind('<Configure>', self._on_dialog_canvas_viewport_configure) 
        self.dialog_rules_canvas.bind("<MouseWheel>", self._on_dialog_specific_mousewheel)
        self.dialog_rules_canvas.bind("<Button-4>", self._on_dialog_specific_mousewheel) 
        self.dialog_rules_canvas.bind("<Button-5>", self._on_dialog_specific_mousewheel) 

        action_buttons_frame = ttk.Frame(main_dialog_frame)
        action_buttons_frame.grid(row=2, column=0, sticky=tk.E, pady=(10,0))
        save_button = ttk.Button(action_buttons_frame, text="Save Defaults", command=self._save_and_close_name_patterns, style="Accent.TButton")
        save_button.pack(side=tk.LEFT, padx=5)
        cancel_button = ttk.Button(action_buttons_frame, text="Cancel", command=self.destroy)
        cancel_button.pack(side=tk.LEFT, padx=5)

        self._load_initial_name_patterns() 
        self.wait_window(self) 


    def _on_dialog_list_frame_configure(self, event=None):
        self.dialog_rules_canvas.configure(scrollregion=self.dialog_rules_canvas.bbox("all"))
    def _on_dialog_canvas_viewport_configure(self, event):
        self.dialog_rules_canvas.itemconfig(self.dialog_canvas_window, width=event.width)

    def _on_dialog_specific_mousewheel(self, event):
        if event.num == 5 or event.delta < 0: 
            self.dialog_rules_canvas.yview_scroll(1, "units")
        elif event.num == 4 or event.delta > 0: 
            self.dialog_rules_canvas.yview_scroll(-1, "units")


    def _load_initial_name_patterns(self):
        self.dialog_rule_file_patterns = []
        self.dialog_rule_folder_patterns = []
        try:
            if not os.path.exists(self.default_filepath): 
                with open(self.default_filepath, "w", encoding="utf-8") as f:
                    f.write("# Default files to ignore (name patterns, e.g., *.log, specific_file.tmp)\n")
                    f.write("file: .DS_Store\n")
                    f.write("file: thumbs.db\n")
                    f.write("file: desktop.ini\n")
                    f.write("\n# Default folders to ignore (name patterns, e.g., .git, node_modules)\n")
                    f.write("folder: .git\n")
                    f.write("folder: .svn\n")
                    f.write("folder: .hg\n")
                    f.write("folder: .venv\n")
                    f.write("folder: venv\n")
                    f.write("folder: node_modules\n")
                    f.write("folder: __pycache__\n")
                    f.write("folder: build\n")
                    f.write("folder: dist\n")
                print(f"Created default name patterns file: {self.default_filepath}")

            if os.path.exists(self.default_filepath):
                with open(self.default_filepath, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if not line or line.startswith("#"): continue
                        if line.lower().startswith("file:"):
                            pattern = line[len("file:"):].strip()
                            if pattern and pattern not in self.dialog_rule_file_patterns:
                                self.dialog_rule_file_patterns.append(pattern)
                        elif line.lower().startswith("folder:"):
                            pattern = line[len("folder:"):].strip()
                            if pattern and pattern not in self.dialog_rule_folder_patterns:
                                self.dialog_rule_folder_patterns.append(pattern)
            self.dialog_rule_file_patterns.sort()
            self.dialog_rule_folder_patterns.sort()
        except Exception as e:
            messagebox.showerror("Load Error", f"Could not load default name patterns from\n{self.default_filepath}\n\nError: {e}", parent=self)
        self._rebuild_dialog_name_patterns_list()


    def _rebuild_dialog_name_patterns_list(self):
        for widget in self.dialog_rules_list_frame.winfo_children(): 
            widget.destroy()
        row_num = 0

        if self.dialog_rule_file_patterns:
            ttk.Label(self.dialog_rules_list_frame, text="File Name Patterns:", font=('TkDefaultFont', 9, 'bold')).grid(row=row_num, column=0, columnspan=2, sticky=tk.W, padx=5, pady=(5,2))
            row_num += 1
            for pattern_name in self.dialog_rule_file_patterns: 
                item_f = ttk.Frame(self.dialog_rules_list_frame)
                item_f.grid(row=row_num, column=0, columnspan=2, sticky=tk.EW, padx=5, pady=1); item_f.columnconfigure(0, weight=1)
                ttk.Label(item_f, text=f"file: {pattern_name}", anchor=tk.W).grid(row=0, column=0, sticky=tk.EW)
                ttk.Button(item_f, text="x", width=2, style="Small.TButton", command=lambda p=pattern_name: self._dialog_remove_name_pattern('file', p)).grid(row=0, column=1, sticky=tk.E, padx=(5,0))
                row_num += 1

        if self.dialog_rule_folder_patterns:
            ttk.Label(self.dialog_rules_list_frame, text="Folder Name Patterns:", font=('TkDefaultFont', 9, 'bold')).grid(row=row_num, column=0, columnspan=2, sticky=tk.W, padx=5, pady=(10,2))
            row_num += 1
            for pattern_name in self.dialog_rule_folder_patterns: 
                item_f = ttk.Frame(self.dialog_rules_list_frame)
                item_f.grid(row=row_num, column=0, columnspan=2, sticky=tk.EW, padx=5, pady=1); item_f.columnconfigure(0, weight=1)
                ttk.Label(item_f, text=f"folder: {pattern_name}", anchor=tk.W).grid(row=0, column=0, sticky=tk.EW)
                ttk.Button(item_f, text="x", width=2, style="Small.TButton", command=lambda p=pattern_name: self._dialog_remove_name_pattern('folder', p)).grid(row=0, column=1, sticky=tk.E, padx=(5,0))
                row_num += 1

        if not self.dialog_rule_file_patterns and not self.dialog_rule_folder_patterns:
            ttk.Label(self.dialog_rules_list_frame, text="No default name patterns defined.", foreground="grey").grid(row=0,column=0,padx=5,pady=5, sticky=tk.W)
        
        self.dialog_rules_list_frame.update_idletasks() 
        self._on_dialog_list_frame_configure() 

    def _dialog_add_name_pattern(self, item_type_str):
        pattern_to_add = self.pattern_entry_var.get().strip()
        if not pattern_to_add:
            messagebox.showwarning("Input Missing", "Please enter a file or folder name pattern to add.", parent=self)
            return

        pattern_added_successfully = False
        if item_type_str == 'file':
            if pattern_to_add not in self.dialog_rule_file_patterns:
                self.dialog_rule_file_patterns.append(pattern_to_add)
                self.dialog_rule_file_patterns.sort()
                pattern_added_successfully = True
        elif item_type_str == 'folder':
            if pattern_to_add not in self.dialog_rule_folder_patterns:
                self.dialog_rule_folder_patterns.append(pattern_to_add)
                self.dialog_rule_folder_patterns.sort()
                pattern_added_successfully = True

        if pattern_added_successfully:
            self._rebuild_dialog_name_patterns_list()
            self.pattern_entry_var.set("") 
        else: 
            messagebox.showinfo("Pattern Exists", f"The pattern '{pattern_to_add}' is already in the list for its type.", parent=self)


    def _dialog_remove_name_pattern(self, item_type_str, pattern_to_remove):
        removed_successfully = False
        if item_type_str == 'file':
            if pattern_to_remove in self.dialog_rule_file_patterns:
                self.dialog_rule_file_patterns.remove(pattern_to_remove); removed_successfully = True
        elif item_type_str == 'folder':
            if pattern_to_remove in self.dialog_rule_folder_patterns:
                self.dialog_rule_folder_patterns.remove(pattern_to_remove); removed_successfully = True
        
        if removed_successfully:
            self._rebuild_dialog_name_patterns_list()

    def _save_and_close_name_patterns(self):
        try:
            with open(self.default_filepath, "w", encoding="utf-8") as f:
                f.write("# Default files to ignore (name patterns, e.g., *.log, specific_file.tmp)\n")
                for p_name in sorted(self.dialog_rule_file_patterns): f.write(f"file: {p_name}\n")
                f.write("\n# Default folders to ignore (name patterns, e.g., .git, node_modules)\n")
                for p_name in sorted(self.dialog_rule_folder_patterns): f.write(f"folder: {p_name}\n")

            if self.app_instance and hasattr(self.app_instance, '_update_status'): 
                self.app_instance._update_status(f"Saved changes to default name patterns file: {os.path.basename(self.default_filepath)}", clear_after_ms=3000)
            self.destroy() 
        except Exception as e:
            messagebox.showerror("Save Error", f"Could not save default name patterns to\n{self.default_filepath}\n\nError: {e}", parent=self)


# --- Manage Profiles Dialog ---
class ManageProfilesDialog(Toplevel):
    def __init__(self, parent, profiles_data, current_active_profile, app_instance, initial_action="load"):
        super().__init__(parent)
        self.profiles_dict = profiles_data 
        self.app_instance_ref = app_instance
        self.current_active_profile_name = current_active_profile

        self.title("Manage Scan Profiles")
        self.geometry("450x350")
        self.transient(parent) 
        self.grab_set() 

        main_frame = ttk.Frame(self, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(main_frame, text="Saved Profiles:", font=('TkDefaultFont', 10, 'bold')).pack(pady=(0,5), anchor=tk.W)

        self.profile_listbox_widget = tk.Listbox(main_frame, height=10, exportselection=False) 
        self.profile_listbox_widget.pack(fill=tk.BOTH, expand=True, pady=5)
        self._populate_profile_listbox() 

        buttons_frame = ttk.Frame(main_frame)
        buttons_frame.pack(fill=tk.X, pady=5)

        self.load_button_widget = ttk.Button(buttons_frame, text="Load Selected", command=self._action_load_selected)
        self.load_button_widget.pack(side=tk.LEFT, padx=5)

        self.delete_button_widget = ttk.Button(buttons_frame, text="Delete Selected", command=self._action_delete_selected)
        self.delete_button_widget.pack(side=tk.LEFT, padx=5)

        close_button_widget = ttk.Button(buttons_frame, text="Close", command=self.destroy)
        close_button_widget.pack(side=tk.RIGHT, padx=5) 

        self._update_button_states() 

        if initial_action == "delete" and self.profiles_dict:
            self.delete_button_widget.focus_set()
        elif self.profiles_dict: 
             self.load_button_widget.focus_set()

        self.profile_listbox_widget.bind("<Double-1>", lambda e: self._action_load_selected()) 
        self.wait_window(self)


    def _populate_profile_listbox(self):
        self.profile_listbox_widget.delete(0, tk.END) 
        sorted_profile_names = sorted(self.profiles_dict.keys())
        
        selection_to_set_idx = -1 

        for idx, name in enumerate(sorted_profile_names):
            display_name = name
            if name == self.current_active_profile_name:
                display_name += " (Active)"
                selection_to_set_idx = idx 
            self.profile_listbox_widget.insert(tk.END, display_name)
        
        if selection_to_set_idx != -1: 
             self.profile_listbox_widget.selection_set(selection_to_set_idx)
             self.profile_listbox_widget.see(selection_to_set_idx) 
        elif sorted_profile_names: 
            self.profile_listbox_widget.selection_set(0)
            self.profile_listbox_widget.see(0)


    def _update_button_states(self):
        if not self.profiles_dict: 
            self.load_button_widget.config(state=tk.DISABLED)
            self.delete_button_widget.config(state=tk.DISABLED)
        else:
            self.load_button_widget.config(state=tk.NORMAL)
            self.delete_button_widget.config(state=tk.NORMAL)

    def _get_actual_profile_name_from_listbox_selection(self):
        selection_indices = self.profile_listbox_widget.curselection()
        if not selection_indices: return None 
        
        selected_display_name = self.profile_listbox_widget.get(selection_indices[0])
        actual_name = selected_display_name.replace(" (Active)", "").strip() 
        return actual_name

    def _action_load_selected(self):
        profile_name_to_load = self._get_actual_profile_name_from_listbox_selection()
        if profile_name_to_load and self.app_instance_ref:
            self.app_instance_ref._execute_load_profile(profile_name_to_load)
            self.destroy() 
        elif not profile_name_to_load:
             messagebox.showwarning("No Selection", "Please select a profile to load.", parent=self)

    def _action_delete_selected(self):
        profile_name_to_delete = self._get_actual_profile_name_from_listbox_selection()
        if profile_name_to_delete:
            if messagebox.askyesno("Confirm Delete", f"Are you sure you want to delete profile '{profile_name_to_delete}'?", parent=self):
                if self.app_instance_ref and self.app_instance_ref._execute_delete_profile(profile_name_to_delete):
                    self.profiles_dict = self.app_instance_ref.profiles 
                    self.current_active_profile_name = self.app_instance_ref.active_profile_name 
                    self._populate_profile_listbox() 
                    self._update_button_states() 
                    self.app_instance_ref._update_status(f"Profile '{profile_name_to_delete}' deleted.", clear_after_ms=4000)
        elif not profile_name_to_delete:
            messagebox.showwarning("No Selection", "Please select a profile to delete.", parent=self)


# --- ToolTip Class ---
class ToolTip:
    def __init__(self, widget, text):
        self.widget = widget
        self.text = text
        self.tooltip_window = None 
        self.id_after = None       
        self.widget.bind("<Enter>", self.on_enter)
        self.widget.bind("<Leave>", self.on_leave)
        self.widget.bind("<ButtonPress>", self.on_leave) 

    def on_enter(self, event=None):
        self.schedule_tooltip()

    def on_leave(self, event=None):
        self.cancel_scheduled_tooltip()
        self.hide_tooltip()

    def schedule_tooltip(self):
        self.cancel_scheduled_tooltip() 
        self.id_after = self.widget.after(700, self.show_tooltip) 

    def cancel_scheduled_tooltip(self):
        if self.id_after:
            self.widget.after_cancel(self.id_after)
            self.id_after = None

    def show_tooltip(self):
        if self.tooltip_window or not self.text: return 

        x_root = self.widget.winfo_rootx() + 20 
        y_root = self.widget.winfo_rooty() + self.widget.winfo_height() + 5 

        self.tooltip_window = tk.Toplevel(self.widget)
        self.tooltip_window.wm_overrideredirect(True) 
        self.tooltip_window.wm_geometry(f"+{int(x_root)}+{int(y_root)}")

        label = tk.Label(self.tooltip_window, text=self.text, justify='left',
                         background="#ffffe0", relief='solid', borderwidth=1,
                         wraplength=350, 
                         font=("tahoma", "8", "normal"))
        label.pack(ipadx=2, ipady=2)

        self.tooltip_window.update_idletasks() 
        tip_width = self.tooltip_window.winfo_width()
        tip_height = self.tooltip_window.winfo_height()
        screen_width = self.widget.winfo_screenwidth()
        screen_height = self.widget.winfo_screenheight()

        if x_root + tip_width > screen_width: 
            x_root = screen_width - tip_width - 5 
        if x_root < 0: x_root = 5 

        if y_root + tip_height > screen_height: 
            y_root = self.widget.winfo_rooty() - tip_height - 5 
        if y_root < 0: y_root = 5 

        self.tooltip_window.wm_geometry(f"+{int(x_root)}+{int(y_root)}") 

    def hide_tooltip(self):
        if self.tooltip_window:
            try:
                self.tooltip_window.destroy()
            except tk.TclError:
                pass 
            self.tooltip_window = None

# --- Main Execution ---
if __name__ == "__main__":
    root = tk.Tk()
    app = CodeScannerApp(root)
    root.mainloop()