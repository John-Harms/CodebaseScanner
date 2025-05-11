# profile_handler.py

import os
import json
import tkinter.messagebox as messagebox # For showing errors if needed, though typically GUI handles this

def load_profiles(profiles_path):
    """Loads profiles from PROFILES_PATH."""
    if os.path.exists(profiles_path):
        try:
            with open(profiles_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                # Ensure directory_tree_blacklist and generate_directory_tree are present
                profiles_data = data.get("profiles", {})
                for _, profile_content in profiles_data.items():
                    profile_content.setdefault("directory_tree_blacklist", [])
                    profile_content.setdefault("generate_directory_tree", True) # Default to True
                return profiles_data, data.get("last_active_profile_name", None)
        except Exception as e:
            print(f"Error loading profiles from {profiles_path}: {e}")
            # Consider if this should raise an error or be handled by the caller (GUI)
            # For now, matching original behavior of printing and returning defaults
    return {}, None

def save_profiles(profiles, last_active_profile_name, profiles_path):
    """Saves profiles and the last active profile name to PROFILES_PATH."""
    try:
        # Ensure the directory for PROFILES_PATH exists
        profiles_dir = os.path.dirname(profiles_path)
        if not os.path.exists(profiles_dir) and profiles_dir : # Check profiles_dir is not empty string
             os.makedirs(profiles_dir, exist_ok=True)

        with open(profiles_path, "w", encoding="utf-8") as f:
            json.dump({"profiles": profiles, "last_active_profile_name": last_active_profile_name}, f, indent=4)
        print(f"Profiles saved to: {profiles_path}")
    except Exception as e:
        print(f"Error saving profiles to {profiles_path}: {e}")
        # The original showed a messagebox here. GUI should handle UI feedback.
        # This module should ideally just perform the action or raise an error.
        # For strict functional equivalence of side effects, the messagebox could be here,
        # but it's better for GUI to handle GUI. Let's assume GUI will catch and display.
        # To maintain functional equivalence regarding error popups if no GUI is involved,
        # we might need to pass a callback or let the GUI wrap this call.
        # Given the context, the main app will likely catch and show the messagebox.
        # Raising an exception is cleaner for a utility module.
        raise  # Re-raise for the GUI to catch and display.