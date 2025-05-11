# scan_engine.py

import os
from app_config import LANG_MAP, FILTER_BLACKLIST, FILTER_WHITELIST # Import constants

def get_language_hint(filename):
    """Determines the Markdown language hint based on the file extension."""
    _, ext = os.path.splitext(filename)
    return LANG_MAP.get(ext.lower(), "")

def generate_directory_tree_text(start_path, tree_blacklist, prefix="", is_last=True):
    """
    Generates a text-based directory tree.
    Only includes directory names and respects the tree_blacklist.
    """
    tree_string = ""
    normalized_start_path = os.path.normpath(start_path)

    if normalized_start_path in tree_blacklist:
        return "" # Skip blacklisted directories and their subtrees

    tree_string += prefix
    if is_last:
        tree_string += "└── "
        prefix += "    "
    else:
        tree_string += "├── "
        prefix += "│   "

    tree_string += os.path.basename(normalized_start_path) + "/\n"

    try:
        # Get only directories
        entries = [entry.name for entry in os.scandir(normalized_start_path) if entry.is_dir()]
        entries.sort()
    except OSError:
        entries = [] # Could not list directory, treat as empty

    for i, entry_name in enumerate(entries):
        entry_path = os.path.join(normalized_start_path, entry_name)
        is_last_entry = (i == len(entries) - 1)
        tree_string += generate_directory_tree_text(entry_path, tree_blacklist, prefix, is_last_entry)

    return tree_string

def should_process_item(item_path, is_file, rules_files, rules_folders, filter_mode, whitelisted_parent_folders):
    normalized_item_path = os.path.normpath(item_path)

    if filter_mode == FILTER_BLACKLIST:
        if is_file:
            if normalized_item_path in rules_files:
                return False
            for folder_rule in rules_folders: # Check if file is in a blacklisted folder
                if normalized_item_path.startswith(folder_rule + os.sep):
                    return False
        else: # Is a folder
            if normalized_item_path in rules_folders:
                return False
            for folder_rule in rules_folders: # if it's a subfolder of an excluded one (already covered by the above, but explicit)
                 if normalized_item_path.startswith(folder_rule + os.sep):
                     return False
        return True # Not in any blacklist rule

    elif filter_mode == FILTER_WHITELIST:
        # If item is within any whitelisted parent folder, it's eligible for processing (further checks may apply)
        for whitelisted_folder_path in whitelisted_parent_folders:
            if normalized_item_path.startswith(whitelisted_folder_path + os.sep) or normalized_item_path == whitelisted_folder_path:
                return True # It's content of an explicitly whitelisted folder

        # If not within an already whitelisted parent, check if it's directly whitelisted itself
        if is_file:
             return normalized_item_path in rules_files
        else: # Is a folder
             return normalized_item_path in rules_folders # A folder is processable if it's directly whitelisted
    
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
            if normalized_directory in rules_folders: # Directly whitelisted
                is_dir_in_whitelisted_scope = True
            else: # Check if it's a child of a whitelisted folder
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
            else: # is_folder
                 dirs_to_recurse_info.append({'name': item_name, 'path': normalized_item_path, 'ancestors': list(current_whitelisted_ancestors)})
        elif filter_mode == FILTER_WHITELIST and not is_file: # If a folder is NOT processable itself but MIGHT contain whitelisted items
            can_contain_whitelisted = False
            # Check if any whitelisted file is within this folder
            for rf_path in rules_files:
                if rf_path.startswith(normalized_item_path + os.sep):
                    can_contain_whitelisted = True
                    break
            if not can_contain_whitelisted:
                # Check if any whitelisted folder IS this folder or a subfolder
                 for rfo_path in rules_folders:
                    if rfo_path == normalized_item_path or rfo_path.startswith(normalized_item_path + os.sep) :
                        can_contain_whitelisted = True
                        break
            if can_contain_whitelisted:
                 dirs_to_recurse_info.append({'name': item_name, 'path': normalized_item_path, 'ancestors': list(current_whitelisted_ancestors)})


    files_to_output.sort()
    dirs_to_recurse_info.sort(key=lambda x: x['name'])

    processed_subdirs_with_content = [] # Tracks subdirs that actually led to content being written
    for dir_info in dirs_to_recurse_info:
        next_level_ancestors = list(dir_info['ancestors']) # Pass along the current list
        # If the directory to recurse into is itself a whitelisted folder, ensure it's part of its own ancestor list for its children
        if filter_mode == FILTER_WHITELIST and dir_info['path'] in rules_folders:
            if dir_info['path'] not in next_level_ancestors:
                next_level_ancestors.append(dir_info['path'])

        if process_directory(dir_info['path'], output_file, rules_files, rules_folders, filter_mode, level + 1, status_callback, next_level_ancestors):
            content_written_for_this_branch = True # Mark that this branch (from current level) had content
            processed_subdirs_with_content.append(dir_info['name'])


    should_write_header = False
    is_current_dir_in_whitelisted_scope = False
    if filter_mode == FILTER_WHITELIST:
        if normalized_directory in rules_folders: # current directory is explicitly whitelisted
            is_current_dir_in_whitelisted_scope = True
        else: # current directory is a descendant of an explicitly whitelisted folder
            for wf_ancestor in (whitelisted_ancestor_folders if whitelisted_ancestor_folders else []):
                if normalized_directory.startswith(wf_ancestor + os.sep):
                    is_current_dir_in_whitelisted_scope = True
                    break
    
    if filter_mode == FILTER_BLACKLIST:
        # Write header if there are files to output in this dir, or if subdirs had content,
        # or if it's the root level and completely empty (to indicate it was processed and found empty)
        if files_to_output or processed_subdirs_with_content or (not items and level == 0 and not files_to_output and not processed_subdirs_with_content):
            should_write_header = True
    elif filter_mode == FILTER_WHITELIST:
        # Write header if the current directory is part of the whitelisted scope (either directly or as ancestor)
        # AND it has files to output OR subdirectories that produced content OR it's empty (but in scope)
        if is_current_dir_in_whitelisted_scope and (files_to_output or processed_subdirs_with_content or not items):
            should_write_header = True
        # Also write header if there are files to output, even if dir itself wasn't whitelisted (e.g. file was individually whitelisted)
        elif files_to_output: 
             should_write_header = True
        # Or if subdirectories produced content (meaning they were whitelisted or contained whitelisted items)
        elif processed_subdirs_with_content:
             should_write_header = True


    if not should_write_header:
        return content_written_for_this_branch # Return based on whether subdirectories wrote something

    # If we decided to write a header, this directory itself contributes to content.
    output_file.write(f"{heading_prefix} Directory: {os.path.basename(normalized_directory)}\n\n")
    output_file.write(f"**Path:** `{normalized_directory}`\n\n")
    content_written_for_this_branch = True # Header itself is content for this branch

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
    elif not items and not processed_subdirs_with_content : # If dir is empty AND no subdirs had content AND header was written
        # This message applies if the directory is empty and it was significant enough to write a header for
        # (e.g., it was the root, or it was an explicitly whitelisted empty folder)
        if filter_mode == FILTER_BLACKLIST or (filter_mode == FILTER_WHITELIST and is_current_dir_in_whitelisted_scope):
            output_file.write(f"*This folder is empty or all its contents were excluded/not included by rules.*\n\n")

    return content_written_for_this_branch