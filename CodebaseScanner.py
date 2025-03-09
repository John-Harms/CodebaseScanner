import os
from tkinter import Tk
from tkinter.filedialog import askdirectory, asksaveasfilename

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

def process_directory(directory, output_file, ignore_files, ignore_folders):
    """
    Process a directory:
      - Write a header block with the directory name and its non-ignored items.
      - For each non-ignored file, write its name and contents.
      - Recursively process non-ignored subdirectories.
    """
    try:
        items = os.listdir(directory)
    except Exception as e:
        output_file.write(f"{{Error reading directory {directory}: {e}}}\n")
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

    all_items = non_ignored_files + non_ignored_dirs

    output_file.write("{\n")
    output_file.write(f"  Directory: {directory}\n")
    output_file.write(f"  Items: {', '.join(all_items)}\n")

    # Process each non-ignored file.
    for file in non_ignored_files:
        file_path = os.path.join(directory, file)
        output_file.write(f"  File: {file}\n")
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
            output_file.write(f"    Content: {content}\n")
        except Exception as e:
            output_file.write(f"    Error reading file: {e}\n")
    output_file.write("}\n\n")

    # Recursively process non-ignored subdirectories.
    for dir_name in non_ignored_dirs:
        dir_path = os.path.join(directory, dir_name)
        process_directory(dir_path, output_file, ignore_files, ignore_folders)

def main():
    # Locate the .scanIgnore file in the same directory as this script.
    script_dir = os.path.dirname(os.path.abspath(__file__))
    ignore_file_path = os.path.join(script_dir, ".scanIgnore")
    ignore_files, ignore_folders = load_ignore_lists(ignore_file_path)
    
    # Hide the Tkinter root window.
    Tk().withdraw()
    # Ask the user to select a directory to scan.
    selected_directory = askdirectory(title="Select a Directory")
    if not selected_directory:
        print("No directory selected. Exiting.")
        return

    # Ask the user to choose a location and name for the output file.
    output_filepath = asksaveasfilename(
        title="Save Output File As",
        defaultextension=".txt",
        filetypes=[("Text Files", "*.txt"), ("All Files", "*.*")]
    )
    if not output_filepath:
        print("No output file selected. Exiting.")
        return

    # Process the directory and save the output.
    with open(output_filepath, "w", encoding="utf-8") as output_file:
        process_directory(selected_directory, output_file, ignore_files, ignore_folders)

    print(f"Directory contents written to {output_filepath}")

if __name__ == "__main__":
    main()
