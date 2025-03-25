import os
import os.path  # Explicitly import os.path for splitext
from tkinter import Tk
from tkinter.filedialog import askdirectory, asksaveasfilename

SETTINGS_FILE = ".scan_config.txt"

# Map common file extensions to Markdown language hints
# Add more mappings as needed
LANG_MAP = {
    ".py": "python",
    ".js": "javascript",
    ".jsx": "javascript",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".html": "html",
    ".css": "css",
    ".scss": "scss",
    ".json": "json",
    ".yaml": "yaml",
    ".yml": "yaml",
    ".md": "markdown",
    ".sh": "bash",
    ".java": "java",
    ".cs": "csharp",
    ".cpp": "cpp",
    ".c": "c",
    ".h": "c",
    ".hpp": "cpp",
    ".go": "go",
    ".php": "php",
    ".rb": "ruby",
    ".rs": "rust",
    ".swift": "swift",
    ".kt": "kotlin",
    ".kts": "kotlin",
    ".sql": "sql",
    ".xml": "xml",
    ".dockerfile": "dockerfile",
    ".txt": "text", # Explicitly map txt to text
}

def get_language_hint(filename):
    """
    Determines the Markdown language hint based on the file extension.
    """
    _, ext = os.path.splitext(filename)
    return LANG_MAP.get(ext.lower(), "") # Return empty string if extension not found

def load_settings():
    """
    Load saved directory settings from the settings file.
    Returns a dictionary with 'scan_directory' and 'save_directory'.
    If the settings file does not exist or settings are not found, returns None for those settings.
    """
    settings = {}
    script_dir = os.path.dirname(os.path.abspath(__file__))
    settings_path = os.path.join(script_dir, SETTINGS_FILE)
    if os.path.exists(settings_path):
        try:
            with open(settings_path, "r") as f:
                for line in f:
                    line = line.strip()
                    if "=" in line:
                        key, value = line.split("=", 1)
                        settings[key.strip()] = value.strip()
        except Exception as e:
            print(f"Error loading settings: {e}")
            return {} # Return empty settings to use defaults

    return settings

def save_settings(scan_directory, save_directory):
    """
    Save the directory settings to the settings file.
    """
    script_dir = os.path.dirname(os.path.abspath(__file__))
    settings_path = os.path.join(script_dir, SETTINGS_FILE)
    try:
        with open(settings_path, "w") as f:
            if scan_directory:
                f.write(f"scan_directory={scan_directory}\n")
            if save_directory:
                f.write(f"save_directory={save_directory}\n")
    except Exception as e:
        print(f"Error saving settings: {e}")

def load_ignore_lists(ignore_file_path):
    """
    Load ignore patterns from a .scanIgnore file.
    Each nonempty line is processed as follows:
      - Lines starting with '#' are comments and are skipped.
      - Lines starting with 'file:' add a pattern to ignore files.
      - Lines starting with 'folder:' add a pattern to ignore folders.
      - Lines without a prefix are added to both.
    """
    ignore_files = []
    ignore_folders = []
    if os.path.exists(ignore_file_path):
        with open(ignore_file_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if line.lower().startswith("file:"):
                    pattern = line[len("file:"):].strip()
                    if pattern:
                        ignore_files.append(pattern)
                elif line.lower().startswith("folder:"):
                    pattern = line[len("folder:"):].strip()
                    if pattern:
                        ignore_folders.append(pattern)
                else:
                    # If no prefix, apply to both files and folders.
                    # Ensure empty lines don't add empty patterns
                    if line:
                        ignore_files.append(line)
                        ignore_folders.append(line)
    return ignore_files, ignore_folders

def should_ignore_file(name, ignore_files):
    """
    Check if the file name matches any ignore pattern.
    Now checks for exact match or if the pattern is a substring *if* it's intended
    (current implementation checks substring presence). Let's keep substring for flexibility.
    """
    for pattern in ignore_files:
        if pattern in name:
            return True
    return False

def should_ignore_folder(name, ignore_folders):
    """
    Check if the folder name matches any ignore pattern.
    Now checks for exact match or if the pattern is a substring *if* it's intended
    (current implementation checks substring presence). Let's keep substring for flexibility.
    """
    for pattern in ignore_folders:
        if pattern in name:
            return True
    return False

def process_directory(directory, output_file, ignore_files, ignore_folders, level=0):
    """
    Process a directory and write its structure and contents in Markdown format.
      - Uses Markdown headings for directories, increasing level for nesting.
      - Lists files with their content enclosed in triple-backtick code blocks.
      - Recursively processes non-ignored subdirectories.
    """
    heading_level = level + 2 # Start directory headings at ##
    heading_prefix = "#" * heading_level

    try:
        items = os.listdir(directory)
    except Exception as e:
        # Write error clearly if directory can't be read
        output_file.write(f"{heading_prefix} Error Reading Directory\n\n")
        output_file.write(f"**Path:** `{directory}`\n\n")
        output_file.write(f"**Error:** `{e}`\n\n")
        return

    non_ignored_files = []
    non_ignored_dirs = []

    # Separate files and directories while applying ignore patterns.
    for item in items:
        item_path = os.path.join(directory, item)
        if os.path.isfile(item_path):
            if not should_ignore_file(item, ignore_files):
                non_ignored_files.append(item)
        elif os.path.isdir(item_path):
            if not should_ignore_folder(item, ignore_folders):
                non_ignored_dirs.append(item)

    # Write the directory header.
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
            # Optional: Add full path if needed, e.g.:
            # output_file.write(f"**File:** `{file}` (`{file_path}`)\n")
            lang_hint = get_language_hint(file)
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    content = f.read()
                output_file.write(f"```{lang_hint}\n")
                output_file.write(content)
                output_file.write(f"\n```\n\n") # Ensure newline before closing backticks
            except Exception as e:
                output_file.write(f"**Error reading file:** `{e}`\n\n")
    # else:
        # Optionally indicate no files - decided against for cleaner output
        # output_file.write(f"*No processable files found in this directory.*\n\n")


    # Process Subdirectories Recursively
    # No explicit "Subdirectories" heading needed, the nested structure provides this.
    if non_ignored_dirs:
        for dir_name in non_ignored_dirs:
            sub_dir_path = os.path.join(directory, dir_name)
            # Recursively process each subdirectory with increased level.
            process_directory(sub_dir_path, output_file, ignore_files, ignore_folders, level + 1)
    # else:
         # Optionally indicate no subdirectories - decided against for cleaner output
         # output_file.write(f"*No processable subdirectories found.*\n\n")


def main():
    # Load saved settings
    settings = load_settings()
    last_scan_directory = settings.get('scan_directory')
    last_save_directory = settings.get('save_directory')

    # Locate the .scanIgnore file in the same directory as this script.
    script_dir = os.path.dirname(os.path.abspath(__file__))
    ignore_file_path = os.path.join(script_dir, ".scanIgnore")
    ignore_files, ignore_folders = load_ignore_lists(ignore_file_path)

    # Hide the Tkinter root window.
    Tk().withdraw()
    # Ask the user to select a directory to scan.
    selected_directory = askdirectory(title="Select Directory to Scan", initialdir=last_scan_directory)
    if not selected_directory:
        print("No directory selected. Exiting.")
        return

    # Ask the user to choose a location and name for the output file.
    output_filepath = asksaveasfilename(
        title="Save Scan Output As",
        defaultextension=".md", # Default to Markdown extension
        filetypes=[("Markdown Files", "*.md"), ("Text Files", "*.txt"), ("All Files", "*.*")],
        initialdir=last_save_directory,
        initialfile=f"{os.path.basename(selected_directory)}_scan.md" # Suggest a filename
    )
    if not output_filepath:
        print("No output file selected. Exiting.")
        return

    # Process the directory and save the output.
    try:
        with open(output_filepath, "w", encoding="utf-8") as output_file:
            # Add a top-level heading for the scan
            output_file.write(f"# Codebase Scan: {os.path.basename(selected_directory)}\n\n")
            # Start processing from the selected directory at level 0
            process_directory(selected_directory, output_file, ignore_files, ignore_folders, level=0)

        print(f"Directory contents successfully written to {output_filepath}")

        # Save settings for next run
        save_directory_path = os.path.dirname(output_filepath)
        save_settings(selected_directory, save_directory_path)

    except Exception as e:
        print(f"An error occurred during scanning or writing the file: {e}")


if __name__ == "__main__":
    main()