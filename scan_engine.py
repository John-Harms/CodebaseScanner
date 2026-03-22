# CodebaseScanner/scan_engine.py

import os
from app_config import LANG_MAP, FILTER_BLACKLIST, FILTER_WHITELIST

try:
    import tiktoken
    _ENCODER = tiktoken.get_encoding("cl100k_base")
    _TIKTOKEN_AVAILABLE = True
except ImportError:
    _TIKTOKEN_AVAILABLE = False
    _ENCODER = None

TREE_TOKENS_PER_ENTRY = 6  # heuristic: "├── filename\n" ≈ 4–8 tokens


def get_language_hint(filename):
    _, ext = os.path.splitext(filename)
    return LANG_MAP.get(ext.lower(), "")


def count_tokens_for_file(filepath: str) -> int:
    """Returns exact token count for a readable file. Returns 0 on error or if tiktoken unavailable."""
    if not _TIKTOKEN_AVAILABLE:
        return 0
    try:
        with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
            return len(_ENCODER.encode(f.read()))
    except OSError:
        return 0


def estimate_tree_tokens(scan_dir: str, tree_blacklist: list) -> int:
    """Heuristic token count for the rendered directory tree text."""
    if not _TIKTOKEN_AVAILABLE:
        return 0
    norm_blacklist = {os.path.normpath(p) for p in tree_blacklist}
    count = 0
    for root, dirs, files in os.walk(scan_dir):
        norm_root = os.path.normpath(root)
        dirs[:] = [d for d in dirs if os.path.normpath(os.path.join(norm_root, d)) not in norm_blacklist]
        count += (len(dirs) + len(files)) * TREE_TOKENS_PER_ENTRY
    return count


def generate_directory_tree_text(start_path, tree_blacklist, prefix="", is_last=True):
    tree_string = ""
    normalized_start_path = os.path.normpath(start_path)

    if normalized_start_path in tree_blacklist:
        return ""

    tree_string += prefix
    if is_last:
        tree_string += "└── "
        prefix += "    "
    else:
        tree_string += "├── "
        prefix += "│   "

    tree_string += os.path.basename(normalized_start_path) + "/\n"

    try:
        entries = list(os.scandir(normalized_start_path))
        entries.sort(key=lambda e: e.name.lower())
    except OSError:
        entries = []

    count = len(entries)
    for i, entry in enumerate(entries):
        is_last_entry = (i == count - 1)
        if entry.is_dir():
            tree_string += generate_directory_tree_text(entry.path, tree_blacklist, prefix, is_last_entry)
        else:
            tree_string += prefix
            if is_last_entry:
                tree_string += "└── "
            else:
                tree_string += "├── "
            tree_string += entry.name + "\n"

    return tree_string


def should_process_item(item_path, is_file, rules_files, rules_folders, filter_mode, whitelisted_parent_folders):
    normalized_item_path = os.path.normpath(item_path)

    if filter_mode == FILTER_BLACKLIST:
        if is_file:
            if normalized_item_path in rules_files:
                return False
            for folder_rule in rules_folders:
                if normalized_item_path.startswith(folder_rule + os.sep):
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

    print(f"Warning: Unknown filter mode '{filter_mode}'.")
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
                    if rfo_path == normalized_item_path or rfo_path.startswith(normalized_item_path + os.sep):
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
        if files_to_output or processed_subdirs_with_content or (not items and level == 0):
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
        file_heading_prefix = "#" * (heading_level + 1)
        output_file.write(f"{file_heading_prefix} Files\n\n")
        for file_name in files_to_output:
            file_path = os.path.normpath(os.path.join(normalized_directory, file_name))
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
                    status_callback(f"Error reading file: {file_path} - {e}")
    elif not items and not processed_subdirs_with_content:
        if filter_mode == FILTER_BLACKLIST or (filter_mode == FILTER_WHITELIST and is_current_dir_in_whitelisted_scope):
            output_file.write(f"*This folder is empty or all its contents were excluded/not included by rules.*\n\n")

    return content_written_for_this_branch