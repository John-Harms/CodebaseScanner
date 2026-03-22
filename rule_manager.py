# rule_manager.py

import os
import configparser

# ---------------------------------------------------------------------------
# .scanIgnore INI Format
# ---------------------------------------------------------------------------
# The .scanIgnore file uses Python's configparser with three sections:
#
#   [Files]
#   relative\path\to\file.py =
#
#   [Folders]
#   relative\path\to\folder =
#
#   [TreeBlacklist]
#   relative\path\to\folder =
#
# Keys are relative paths (relative to the .scanIgnore file's directory).
# Values are always empty.  configparser's allow_no_value=True lets us
# write bare keys without the trailing " = " if preferred, but we
# normalise to "<key> = " on write for clarity.
# ---------------------------------------------------------------------------

_SECTIONS = ("Files", "Folders", "TreeBlacklist")


def _make_parser() -> configparser.ConfigParser:
    """Returns a ConfigParser instance pre-configured for .scanIgnore files."""
    parser = configparser.ConfigParser(
        allow_no_value=True,
        delimiters=("=",),
    )
    # Preserve case in keys (paths are case-sensitive on most OSes)
    parser.optionxform = str
    return parser


def load_ignore_rules(ignore_file_path: str) -> tuple[list, list, list]:
    """
    Loads scan rules from an INI-style .scanIgnore file.

    Returns a 3-tuple:  (abs_files, abs_folders, abs_tree_blacklist)

    All paths are returned as absolute, resolved relative to the directory
    that contains the .scanIgnore file.
    """
    abs_files: list[str] = []
    abs_folders: list[str] = []
    abs_tree_blacklist: list[str] = []

    if not ignore_file_path or not os.path.exists(ignore_file_path):
        return abs_files, abs_folders, abs_tree_blacklist

    base_dir = os.path.dirname(os.path.abspath(ignore_file_path))

    try:
        parser = _make_parser()
        # Ensure all three sections exist so reads don't throw NoSectionError
        for section in _SECTIONS:
            parser.add_section(section)

        parser.read(ignore_file_path, encoding="utf-8")

        def _resolve(rel_path: str) -> str:
            return os.path.normpath(os.path.join(base_dir, rel_path))

        for rel in parser.options("Files"):
            abs_path = _resolve(rel)
            if abs_path not in abs_files:
                abs_files.append(abs_path)

        for rel in parser.options("Folders"):
            abs_path = _resolve(rel)
            if abs_path not in abs_folders:
                abs_folders.append(abs_path)

        for rel in parser.options("TreeBlacklist"):
            abs_path = _resolve(rel)
            if abs_path not in abs_tree_blacklist:
                abs_tree_blacklist.append(abs_path)

    except Exception as e:
        print(f"Error loading or parsing ignore file '{ignore_file_path}': {e}")
        raise  # Re-raise so the GUI can display the error

    abs_files.sort()
    abs_folders.sort()
    abs_tree_blacklist.sort()

    return abs_files, abs_folders, abs_tree_blacklist


def save_ignore_rules(
    ignore_file_path: str,
    ignore_files: list[str],
    ignore_folders: list[str],
    tree_blacklist: list[str],
) -> None:
    """
    Saves scan rules to an INI-style .scanIgnore file.

    Absolute paths are converted to paths relative to the .scanIgnore
    file's directory before writing, enabling portability across machines.
    """
    if not ignore_file_path:
        raise ValueError("Cannot save ignore rules: No file path specified.")

    base_dir = os.path.dirname(os.path.abspath(ignore_file_path))

    def _make_relative(abs_path: str) -> str:
        try:
            return os.path.relpath(abs_path, base_dir)
        except ValueError:
            # relpath fails on Windows when paths are on different drives
            return abs_path

    try:
        parent_dir = os.path.dirname(ignore_file_path)
        if parent_dir and not os.path.exists(parent_dir):
            os.makedirs(parent_dir, exist_ok=True)

        parser = _make_parser()
        for section in _SECTIONS:
            parser.add_section(section)

        for abs_path in sorted(ignore_files):
            parser.set("Files", _make_relative(abs_path), None)

        for abs_path in sorted(ignore_folders):
            parser.set("Folders", _make_relative(abs_path), None)

        for abs_path in sorted(tree_blacklist):
            parser.set("TreeBlacklist", _make_relative(abs_path), None)

        with open(ignore_file_path, "w", encoding="utf-8") as f:
            parser.write(f)

    except Exception as e:
        print(f"Error saving ignore file '{ignore_file_path}': {e}")
        raise  # Re-raise so the GUI can display the error


def create_empty_file(filepath: str) -> bool:
    """
    Creates an empty .scanIgnore file with the INI skeleton.
    Returns True on success, raises OSError on failure.
    """
    try:
        parent_dir = os.path.dirname(filepath)
        if parent_dir and not os.path.exists(parent_dir):
            os.makedirs(parent_dir, exist_ok=True)

        parser = _make_parser()
        for section in _SECTIONS:
            parser.add_section(section)

        with open(filepath, "w", encoding="utf-8") as f:
            parser.write(f)

        print(f"Created empty .scanIgnore file: {filepath}")
        return True
    except OSError as e:
        print(f"Error creating empty .scanIgnore '{filepath}': {e}")
        raise