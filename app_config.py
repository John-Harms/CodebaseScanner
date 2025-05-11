# app_config.py

import os
import sys

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
        # Adjust SCRIPT_DIR if this file is in a subdirectory of the main script's original location
        # Assuming app_config.py is in the same directory as the main CodeScannerApp.py script
        application_path = os.path.dirname(os.path.abspath(sys.modules['__main__'].__file__))
    return os.path.join(application_path, filename)

PROFILES_PATH = get_application_persistent_path(PROFILES_FILE)

# Default ignore file configuration - .scanIgnore.defaults is bundled with the script
# and will be found in SCRIPT_DIR (which is sys._MEIPASS for frozen apps)
DEFAULT_IGNORE_FILE = ".scanIgnore.defaults"

# If SCRIPT_DIR needs to point to where the original CodebaseScanner.py was,
# and app_config.py is in the same directory, this SCRIPT_DIR definition is fine.
# However, for bundled apps, sys._MEIPASS is the key.
# Let's refine DEFAULT_IGNORE_PATH to be more robust for bundled vs. script scenarios.

def get_script_or_exe_dir():
    if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
        # Running as a bundled executable
        return sys._MEIPASS # Resources are here
    else:
        # Running as a normal Python script
        # Assumes app_config.py is in the same directory as the main script
        return os.path.dirname(os.path.abspath(sys.modules['__main__'].__file__))

APP_RESOURCE_DIR = get_script_or_exe_dir()
DEFAULT_IGNORE_PATH = os.path.join(APP_RESOURCE_DIR, DEFAULT_IGNORE_FILE)


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