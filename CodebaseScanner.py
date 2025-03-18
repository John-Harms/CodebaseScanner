import os
from tkinter import Tk
from tkinter.filedialog import askdirectory, asksaveasfilename

SETTINGS_FILE = ".scan_config.txt"

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
                    ignore_files.append(line)
                    ignore_folders.append(line)
    return ignore_files, ignore_folders

def should_ignore_file(name, ignore_files):
    """
    Check if the file name contains any ignore pattern as a substring.
    """
    for pattern in ignore_files:
        if pattern in name:
            return True
    return False

def should_ignore_folder(name, ignore_folders):
    """
    Check if the folder name contains any ignore pattern as a substring.
    """
    for pattern in ignore_folders:
        if pattern in name:
            return True
    return False

def process_directory(directory, output_file, ignore_files, ignore_folders, indent_level=0):
    """
    Process a directory:
      - Write a header with the directory name.
      - List files (with their content) and subdirectories in separate sections.
      - Each nested directory is indented for clarity.
    """
    indent = " " * (indent_level * 4)  # 4 spaces per indent level
    try:
        items = os.listdir(directory)
    except Exception as e:
        output_file.write(f"{indent}Error reading directory {directory}: {e}\n")
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
    output_file.write(f"{indent}Directory: {directory}\n")

    # List Files
    if non_ignored_files:
        output_file.write(f"{indent}  Files:\n")
        for file in non_ignored_files:
            output_file.write(f"{indent}    {file}:\n")
            file_path = os.path.join(directory, file)
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    content = f.read()
                # Split content into lines and indent each line.
                content_lines = content.splitlines() or [""]
                output_file.write(f"{indent}      Content:\n")
                for line in content_lines:
                    output_file.write(f"{indent}        {line}\n")
            except Exception as e:
                output_file.write(f"{indent}      Error reading file: {e}\n")
    else:
        output_file.write(f"{indent}  No Files Found.\n")

    # List Subdirectories
    if non_ignored_dirs:
        output_file.write(f"{indent}  Subdirectories:\n")
        for dir_name in non_ignored_dirs:
            output_file.write(f"{indent}    {dir_name}:\n")
            sub_dir_path = os.path.join(directory, dir_name)
            # Recursively process each subdirectory with increased indentation.
            process_directory(sub_dir_path, output_file, ignore_files, ignore_folders, indent_level + 1)
    else:
        output_file.write(f"{indent}  No Subdirectories Found.\n")

    output_file.write("\n")

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
    selected_directory = askdirectory(title="Select a Directory", initialdir=last_scan_directory)
    if not selected_directory:
        print("No directory selected. Exiting.")
        return

    # Ask the user to choose a location and name for the output file.
    output_filepath = asksaveasfilename(
        title="Save Output File As",
        defaultextension=".txt",
        filetypes=[("Text Files", "*.txt"), ("All Files", "*.*")],
        initialdir=last_save_directory
    )
    if not output_filepath:
        print("No output file selected. Exiting.")
        return

    # Process the directory and save the output.
    with open(output_filepath, "w", encoding="utf-8") as output_file:
        process_directory(selected_directory, output_file, ignore_files, ignore_folders)

    print(f"Directory contents written to {output_filepath}")

    # Save settings for next run
    save_directory_path = os.path.dirname(output_filepath)
    save_settings(selected_directory, save_directory_path)


if __name__ == "__main__":
    main()