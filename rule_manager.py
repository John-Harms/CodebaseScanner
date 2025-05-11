# rule_manager.py

import os
import tkinter.messagebox as messagebox # For error popups, similar consideration as profile_handler

def load_ignore_rules(ignore_file_path):
    """
    Loads and strictly parses ignore rules from the specified file. Rules are now expected to be full paths.
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
            raise # Re-raise for the GUI to catch and display.
    ignore_files.sort()
    ignore_folders.sort()
    return ignore_files, ignore_folders

def save_ignore_rules(ignore_file_path, ignore_files, ignore_folders):
    """
    Saves the ignore rules (full paths) to the specified file.
    """
    if not ignore_file_path:
        # This case should ideally be prevented by the GUI calling this function.
        # Raising ValueError is appropriate.
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
        raise # Re-raise for the GUI to catch and display.

def create_empty_file(filepath, is_rules_file=True):
    """Creates an empty file at the specified path, creating directories if needed."""
    try:
        parent_dir = os.path.dirname(filepath)
        if parent_dir and not os.path.exists(parent_dir): # Ensure parent_dir is not an empty string
            os.makedirs(parent_dir, exist_ok=True)
        with open(filepath, 'w', encoding='utf-8') as f:
            if is_rules_file:
                f.write("# Files to ignore/include (full paths)\n\n")
                f.write("# Folders to ignore/include (full paths)\n\n")
            else: # For other file types, just create empty.
                pass
        print(f"Created empty file: {filepath}")
        return True # Original returned True on success
    except Exception as e:
        print(f"Error creating empty file '{filepath}': {e}")
        # Original showed messagebox here. Let GUI handle it.
        # Re-raise the exception or return False and let GUI decide.
        # For now, let's keep the messagebox to maintain exact side-effect for this specific function
        # if it's called in a context where the GUI isn't directly wrapping it with a try-except for messageboxes.
        # However, the better design is for GUI to handle this.
        # For now, to stick to "functional equivalence" including side-effects of this specific function:
        messagebox.showerror("File Creation Error", f"Could not create file:\n{filepath}\nError: {e}")
        return False