# app_config.py

import os
import sys
from pathlib import Path

# --- AppData-based persistent storage ---

APP_NAME = "CodebaseScanner"

def get_appdata_dir() -> str:
    """
    Returns the OS-appropriate application data directory for CodebaseScanner.
    - Windows: %APPDATA%\CodebaseScanner
    - Linux/Mac: ~/.config/CodebaseScanner
    Creates the directory if it does not exist.
    """
    if sys.platform == "win32":
        base = os.environ.get("APPDATA", os.path.expanduser("~"))
    else:
        base = os.path.join(os.path.expanduser("~"), ".config")
    appdata_dir = os.path.join(base, APP_NAME)
    os.makedirs(appdata_dir, exist_ok=True)
    return appdata_dir

APPDATA_DIR = get_appdata_dir()

# Profiles JSON lives in AppData
PROFILES_FILE = "profiles.json"
PROFILES_PATH = os.path.join(APPDATA_DIR, PROFILES_FILE)


# --- Resource dir (bundled .scanIgnore.defaults lives here) ---

def get_resource_dir() -> str:
    """
    Returns the directory containing bundled read-only resources such as
    .scanIgnore.defaults. For frozen (PyInstaller) apps this is _MEIPASS.
    """
    if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
        return sys._MEIPASS
    # Running as a normal Python script
    main_module = sys.modules.get('__main__')
    main_file = getattr(main_module, '__file__', None)
    if main_file:
        return os.path.dirname(os.path.abspath(main_file))
    # Fallback: use the directory of this config file
    return os.path.dirname(os.path.abspath(__file__))


APP_RESOURCE_DIR = get_resource_dir()

DEFAULT_IGNORE_FILE = ".scanIgnore.defaults"
DEFAULT_IGNORE_PATH = os.path.join(APP_RESOURCE_DIR, DEFAULT_IGNORE_FILE)


# --- Downloads folder ---

def get_downloads_folder() -> str:
    """Returns the user's Downloads folder, falling back to the home directory."""
    downloads = Path.home() / "Downloads"
    if downloads.is_dir():
        return str(downloads)
    return str(Path.home())


# --- Other Constants ---

DEFAULT_OUTPUT_FILENAME = "ProgramCodebaseContext.txt"

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