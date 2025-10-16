# CodeScannerApp.py (formerly CodebaseScanner.py)

import os
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext, Toplevel, simpledialog
import threading
import sys # For sys.exit and other sys attributes if needed by app_config indirectly
import traceback # For detailed error logging in scan thread
import fnmatch # For name-based pattern matching in tree view
# queue is no longer needed for the tree view

# --- Local Module Imports ---
import app_config
import profile_handler
import rule_manager
import scan_engine
from ui_widgets import ToolTip
from dialogs import EditDefaultsDialog, ManageProfilesDialog


class CodeScannerApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Codebase Scanner")

        self.scan_directory = tk.StringVar()
        self.save_filepath = tk.StringVar()
        self.current_rules_filepath = tk.StringVar()
        self.status_text = tk.StringVar()
        self.status_text.set("Initializing...")
        self.filter_mode_var = tk.StringVar(value=app_config.FILTER_BLACKLIST)
        self.generate_directory_tree_var = tk.BooleanVar(value=True)

        self.rules_files = [] # Full path rules for files
        self.rules_folders = [] # Full path rules for folders
        self.rules_dirty = False # Tracks unsaved changes to the current rules list

        self.directory_tree_blacklist = [] # List of full folder paths to exclude from directory tree
        self.directory_tree_blacklist_dirty = False # Tracks unsaved changes to the tree blacklist
        
        # --- Tree View Specific ---
        self.tree = None # Will be the ttk.Treeview widget
        self.tree_item_paths = {} # Maps tree item ID to its full path
        self.default_ignore_patterns = {'file': [], 'folder': []} # For filtering tree view

        # Load profiles using profile_handler
        self.profiles, self.last_active_profile_name = profile_handler.load_profiles(app_config.PROFILES_PATH)
        self.active_profile_name = None # Will be set by _configure_fields_from_initial_profile

        
        self._configure_fields_from_initial_profile() # Applies last active profile or defaults

        self._setup_ui()

        if self.active_profile_name:
            self.status_text.set(f"Profile '{self.active_profile_name}' loaded. Ready.")
        else:
            self.status_text.set("Ready. Configure manually or load a profile.")
        self._update_window_title()


    def _setup_ui(self):
        menubar = tk.Menu(self.root)
        self.profile_menu = tk.Menu(menubar, tearoff=0)
        self.profile_menu.add_command(label="Update Current Profile", command=self._update_current_profile)
        self.profile_menu.add_command(label="Save Profile As...", command=self._save_profile_dialog)
        self.profile_menu.add_command(label="Load Profile...", command=self._load_profile_dialog) # Opens manage dialog
        self.profile_menu.add_command(label="Delete Profile...", command=self._delete_profile_dialog) # Opens manage dialog
        self.profile_menu.add_separator()
        self.profile_menu.add_command(label="Manage Profiles...", command=self._manage_profiles_dialog)
        menubar.add_cascade(label="Profiles", menu=self.profile_menu)
        self.root.config(menu=menubar)

        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1) # Allow main_frame to expand

        current_row = 0

        # Scan Directory
        ttk.Label(main_frame, text="Scan Directory:").grid(row=current_row, column=0, sticky=tk.W, pady=2)
        scan_entry = ttk.Entry(main_frame, textvariable=self.scan_directory, width=60)
        scan_entry.grid(row=current_row, column=1, sticky=(tk.W, tk.E), padx=5, pady=2)
        scan_button = ttk.Button(main_frame, text="Browse...", command=self._browse_scan_directory)
        scan_button.grid(row=current_row, column=2, sticky=tk.E, padx=5, pady=2)
        current_row += 1

        # Save Output As
        ttk.Label(main_frame, text="Save Output As:").grid(row=current_row, column=0, sticky=tk.W, pady=2)
        save_entry = ttk.Entry(main_frame, textvariable=self.save_filepath, width=60)
        save_entry.grid(row=current_row, column=1, sticky=(tk.W, tk.E), padx=5, pady=2)
        save_button = ttk.Button(main_frame, text="Browse...", command=self._browse_save_file)
        save_button.grid(row=current_row, column=2, sticky=tk.E, padx=5, pady=2)
        current_row += 1

        # Rules File
        ttk.Label(main_frame, text="Rules File:").grid(row=current_row, column=0, sticky=tk.W, pady=2)
        rules_file_entry = ttk.Entry(main_frame, textvariable=self.current_rules_filepath, width=60, state='readonly')
        rules_file_entry.grid(row=current_row, column=1, sticky=(tk.W, tk.E), padx=5, pady=2)
        rules_file_button = ttk.Button(main_frame, text="Browse...", command=self._browse_rules_file)
        rules_file_button.grid(row=current_row, column=2, sticky=tk.E, padx=5, pady=2)
        ToolTip(rules_file_button, "Select or create the path-based rules file (.scanIgnore, etc.)")
        current_row += 1
        
        # --- Buttons Below Rules File (Moved from old UI) ---
        rules_buttons_frame = ttk.Frame(main_frame)
        rules_buttons_frame.grid(row=current_row, column=1, columnspan=2, sticky="ew", padx=5, pady=2)
        edit_defaults_button = ttk.Button(rules_buttons_frame, text="Edit Default Name Patterns", command=self._edit_defaults_dialog)
        edit_defaults_button.pack(side=tk.LEFT, padx=5)
        ToolTip(edit_defaults_button, f"Open editor for {os.path.basename(app_config.DEFAULT_IGNORE_PATH)} which uses name-based patterns (not full paths).")
        save_rules_button = ttk.Button(rules_buttons_frame, text="Save Rules List", command=self._save_rules_list_changes)
        save_rules_button.pack(side=tk.LEFT, padx=5)
        ToolTip(save_rules_button, "Save current path-based rules to the selected rules file.")
        current_row += 1

        # Filter Mode and Directory Tree Toggle Frame
        options_frame = ttk.Frame(main_frame)
        options_frame.grid(row=current_row, column=0, columnspan=3, sticky=tk.W, pady=(5,2))

        self.filter_mode_check = ttk.Checkbutton(
            options_frame,
            text="Whitelist Mode (Include Only Listed Paths)",
            variable=self.filter_mode_var,
            onvalue=app_config.FILTER_WHITELIST,
            offvalue=app_config.FILTER_BLACKLIST,
            command=self._on_filter_mode_change
        )
        self.filter_mode_check.pack(side=tk.LEFT, padx=(0, 20))
        ToolTip(self.filter_mode_check, "Check: Only include items matching full path rules.\nUncheck (Default): Include all items EXCEPT those matching full path rules.")
        
        self.generate_tree_check = ttk.Checkbutton(
            options_frame,
            text="Generate Directory Tree in Output",
            variable=self.generate_directory_tree_var,
            command=self._on_generate_tree_toggle
        )
        self.generate_tree_check.pack(side=tk.LEFT)
        ToolTip(self.generate_tree_check, "Check to include a directory tree at the start of the scan output file.")
        current_row += 1

        # --- New Tree Explorer UI ---
        self._setup_tree_explorer_ui(main_frame, current_row)
        current_row += 1
        
        # Initial load of rules from file if path is set
        self._load_rules_from_file()
        
        # Initial state for profile menu
        self._update_profile_menu_state()

        run_button = ttk.Button(main_frame, text="Run Scan", command=self._run_scan, style="Accent.TButton")
        run_button.grid(row=current_row, column=0, columnspan=3, pady=10)
        
        style = ttk.Style()
        try:
            style.configure("Accent.TButton", font=('TkDefaultFont', 10, 'bold'))
        except tk.TclError:
            print("Could not apply custom button style(s).")

        status_bar = ttk.Label(self.root, textvariable=self.status_text, relief=tk.SUNKEN, anchor=tk.W, padding="2 5")
        status_bar.grid(row=1, column=0, sticky=(tk.W, tk.E))

        main_frame.columnconfigure(1, weight=1)
        main_frame.rowconfigure(current_row -1, weight=1) # Make Treeview area expandable

    def _setup_tree_explorer_ui(self, parent_frame, start_row):
        tree_container = ttk.LabelFrame(parent_frame, text="File Explorer & Rule Manager", padding="5")
        tree_container.grid(row=start_row, column=0, columnspan=3, sticky="nsew", pady=10)
        parent_frame.rowconfigure(start_row, weight=1)
        tree_container.columnconfigure(0, weight=1)
        tree_container.rowconfigure(1, weight=1)

        controls_frame = ttk.Frame(tree_container)
        controls_frame.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 5))

        load_tree_btn = ttk.Button(controls_frame, text="Load/Refresh Directory Tree", command=self._populate_tree_view)
        load_tree_btn.pack(side=tk.LEFT, padx=(0, 10))
        ToolTip(load_tree_btn, "Load the file structure from the 'Scan Directory' into the explorer below.")

        self.tree = ttk.Treeview(tree_container, columns=("scan_rule", "tree_blacklist"), selectmode='extended')
        self.tree.grid(row=1, column=0, sticky="nsew")

        vsb = ttk.Scrollbar(tree_container, orient="vertical", command=self.tree.yview)
        vsb.grid(row=1, column=1, sticky="ns")
        self.tree.configure(yscrollcommand=vsb.set)
        
        # Bind the open event for lazy loading directory contents
        self.tree.bind('<<TreeviewOpen>>', self._on_tree_open)

        self.tree.heading("#0", text="Name")
        self.tree.heading("scan_rule", text="Scan Rule Applied")
        self.tree.heading("tree_blacklist", text="Tree Blacklist Applied")

        self.tree.column("#0", stretch=tk.YES, minwidth=250, width=400)
        self.tree.column("scan_rule", width=120, minwidth=100, anchor=tk.CENTER)
        self.tree.column("tree_blacklist", width=140, minwidth=120, anchor=tk.CENTER)
        
        self.tree.tag_configure('scan_rule_applied', foreground='blue')
        self.tree.tag_configure('tree_blacklist_applied', foreground='red')

        apply_rules_frame = ttk.Frame(tree_container)
        apply_rules_frame.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(5, 0))

        apply_rules_frame.columnconfigure(5, weight=1) # Push remove buttons to the right
        
        add_scan_rule_btn = ttk.Button(apply_rules_frame, text="Apply Scan Rule", command=lambda: self._apply_rules_to_selection('scan_rule', 'add'))
        add_scan_rule_btn.grid(row=0, column=0, padx=(0, 5))
        self.add_scan_rule_tooltip = ToolTip(add_scan_rule_btn, "") # Text set in _on_filter_mode_change

        remove_scan_rule_btn = ttk.Button(apply_rules_frame, text="Remove Scan Rule", command=lambda: self._apply_rules_to_selection('scan_rule', 'remove'))
        remove_scan_rule_btn.grid(row=0, column=1, padx=5)

        ttk.Separator(apply_rules_frame, orient=tk.VERTICAL).grid(row=0, column=2, padx=10, sticky='ns')

        add_tree_blacklist_btn = ttk.Button(apply_rules_frame, text="Apply Tree Blacklist", command=lambda: self._apply_rules_to_selection('tree_blacklist', 'add'))
        add_tree_blacklist_btn.grid(row=0, column=3, padx=5)
        ToolTip(add_tree_blacklist_btn, "Exclude selected folders from the generated directory tree output.")

        remove_tree_blacklist_btn = ttk.Button(apply_rules_frame, text="Remove from Tree Blacklist", command=lambda: self._apply_rules_to_selection('tree_blacklist', 'remove'))
        remove_tree_blacklist_btn.grid(row=0, column=4, padx=5)
        
        # Initial call to set tooltip text
        self._on_filter_mode_change(update_status=False)

    def _on_generate_tree_toggle(self):
        if self.active_profile_name:
            self.directory_tree_blacklist_dirty = True # This action now makes the profile dirty
        self._update_status(f"Directory tree generation set to: {self.generate_directory_tree_var.get()}", clear_after_ms=3000)
        self._update_window_title()

    def _configure_fields_from_initial_profile(self):
        profile_to_load_name = self.last_active_profile_name
        configured_successfully = False
        if profile_to_load_name and profile_to_load_name in self.profiles:
            profile_data = self.profiles.get(profile_to_load_name)
            if profile_data:
                self.scan_directory.set(profile_data.get("scan_directory", ""))
                self.save_filepath.set(profile_data.get("save_filepath", os.path.join(os.path.expanduser("~"), app_config.DEFAULT_OUTPUT_FILENAME)))
                self.current_rules_filepath.set(profile_data.get("rules_filepath", ""))
                self.filter_mode_var.set(profile_data.get("filter_mode", app_config.FILTER_BLACKLIST))
                self.directory_tree_blacklist = list(profile_data.get("directory_tree_blacklist", []))
                self.generate_directory_tree_var.set(profile_data.get("generate_directory_tree", True))
                self.active_profile_name = profile_to_load_name
                configured_successfully = True

        if not configured_successfully:
            self.scan_directory.set("")
            self.save_filepath.set(os.path.join(os.path.expanduser("~"), app_config.DEFAULT_OUTPUT_FILENAME))
            self.current_rules_filepath.set("")
            self.filter_mode_var.set(app_config.FILTER_BLACKLIST)
            self.directory_tree_blacklist = []
            self.generate_directory_tree_var.set(True)
            self.active_profile_name = None
        
        self.directory_tree_blacklist_dirty = False
        self.rules_dirty = False
        if hasattr(self, 'profile_menu'): # Check if UI is initialized
            self._update_profile_menu_state()

    def _update_status(self, message, clear_after_ms=None):
        self.status_text.set(message)
        self.root.update_idletasks()
        if clear_after_ms:
            self.root.after(clear_after_ms, lambda: self.status_text.set("Ready") if self.status_text.get() == message else None)

    def _on_filter_mode_change(self, update_status=True):
        mode = self.filter_mode_var.get()
        mode_text = "Whitelist" if mode == app_config.FILTER_WHITELIST else "Blacklist"
        action_text = "include in" if mode == app_config.FILTER_WHITELIST else "exclude from"
        if update_status:
            self._update_status(f"Filter mode changed to {mode_text}.", clear_after_ms=4000)
        if hasattr(self, 'add_scan_rule_tooltip'): # UI might not be ready on init
             self.add_scan_rule_tooltip.text = f"Mark selected items to {action_text} the scan."

    def _update_window_title(self):
        title = "Codebase Scanner"
        if self.active_profile_name:
            profile_dirty_indicator = ""
            if self.rules_dirty or self.directory_tree_blacklist_dirty:
                profile_dirty_indicator = "*" 
            title += f" - Profile: {self.active_profile_name}{profile_dirty_indicator}"
        elif self.rules_dirty or self.directory_tree_blacklist_dirty:
             title += " - Unsaved Changes*"

        self.root.title(title)

    def _update_profile_menu_state(self):
        """Enables or disables the 'Update Current Profile' menu item based on whether a profile is active."""
        if hasattr(self, 'profile_menu'):
            state = tk.NORMAL if self.active_profile_name else tk.DISABLED
            self.profile_menu.entryconfig("Update Current Profile", state=state)

    def _update_current_profile(self):
        """Saves the current application settings to the currently active profile, overwriting it."""
        if not self.active_profile_name:
            self._update_status("No active profile to update.", clear_after_ms=3000)
            return

        # Confirm with the user before overwriting the profile
        if not messagebox.askyesno("Confirm Update", f"Update profile '{self.active_profile_name}' with the current settings?", parent=self.root):
            self._update_status("Profile update cancelled.", clear_after_ms=3000)
            return
        
        # Gather current settings from the UI
        scan_dir = self.scan_directory.get()
        save_fp = self.save_filepath.get()
        rules_fp = self.current_rules_filepath.get()
        filter_mode = self.filter_mode_var.get()
        current_tree_blacklist = list(self.directory_tree_blacklist)
        current_generate_tree_setting = self.generate_directory_tree_var.get()

        # Validation checks
        if not scan_dir or not os.path.isdir(scan_dir):
            messagebox.showwarning("Incomplete Configuration", "Scan directory must be a valid directory.", parent=self.root); return
        if not save_fp:
             messagebox.showwarning("Incomplete Configuration", "Save output path must be set.", parent=self.root); return
        
        # Handle unsaved changes in the rules list before saving the profile
        if self.rules_dirty and rules_fp:
            save_rules_choice = messagebox.askyesnocancel("Unsaved Rules", f"The current scan rules for '{os.path.basename(rules_fp)}' have unsaved changes. Save them to this rules file before updating the profile?", parent=self.root)
            if save_rules_choice is True: # User clicked "Yes"
                self._save_rules_list_changes()
                if self.rules_dirty: # Check if the save operation failed
                    messagebox.showerror("Profile Update Halted", "Failed to save the scan rules. Profile not updated.", parent=self.root)
                    return
            elif save_rules_choice is None: # User clicked "Cancel"
                self._update_status("Profile update cancelled.", clear_after_ms=3000)
                return
            # If user clicked "No", proceed to save the profile with the in-memory (unsaved) rules.

        # The profile name is the currently active one
        profile_name = self.active_profile_name
        
        # Update the profile data in the main profiles dictionary
        self.profiles[profile_name] = {
            "scan_directory": os.path.normpath(scan_dir),
            "save_filepath": os.path.normpath(save_fp),
            "rules_filepath": os.path.normpath(rules_fp) if rules_fp else "",
            "filter_mode": filter_mode,
            "directory_tree_blacklist": current_tree_blacklist,
            "generate_directory_tree": current_generate_tree_setting
        }
        self.last_active_profile_name = profile_name

        try:
            # Save all profiles and the last active profile name to the JSON file
            profile_handler.save_profiles(self.profiles, self.last_active_profile_name, app_config.PROFILES_PATH)
            
            # Since the profile is now saved, clear the dirty flags
            self.directory_tree_blacklist_dirty = False
            self.rules_dirty = False # The profile reflects the UI state, so it is "saved" from a profile perspective.
            
            self._update_status(f"Profile '{profile_name}' updated successfully.", clear_after_ms=4000)
        except Exception as e:
            messagebox.showerror("Profile Save Error", f"Could not save profile update: {e}", parent=self.root)
            self._update_status(f"Error updating profile '{profile_name}'.", clear_after_ms=5000)
            return

        # Update the window title to remove the dirty indicator (*)
        self._update_window_title()

    def _save_profile_dialog(self):
        profile_name = simpledialog.askstring("Save Profile As", "Enter a new profile name:", parent=self.root)
        if not profile_name:
            self._update_status("Save profile cancelled.", clear_after_ms=3000)
            return
        
        profile_name = "".join(c for c in profile_name if c.isalnum() or c in (' ', '_', '-')).strip()
        if not profile_name:
            messagebox.showwarning("Invalid Name", "Profile name cannot be empty or only special characters.", parent=self.root)
            return

        if profile_name in self.profiles:
            if not messagebox.askyesno("Overwrite Profile", f"Profile '{profile_name}' already exists. Overwrite?", parent=self.root):
                self._update_status("Save profile cancelled.", clear_after_ms=3000)
                return

        scan_dir = self.scan_directory.get()
        save_fp = self.save_filepath.get()
        rules_fp = self.current_rules_filepath.get()
        filter_mode = self.filter_mode_var.get()
        current_tree_blacklist = list(self.directory_tree_blacklist)
        current_generate_tree_setting = self.generate_directory_tree_var.get()

        if not scan_dir or not os.path.isdir(scan_dir):
            messagebox.showwarning("Incomplete Configuration", "Scan directory must be a valid directory.", parent=self.root); return
        if not save_fp :
             messagebox.showwarning("Incomplete Configuration", "Save output path must be set.", parent=self.root); return
        
        if self.rules_dirty and rules_fp:
            # If user cancels this, we should not proceed to save the profile
            save_rules_choice = messagebox.askyesnocancel("Unsaved Rules", f"The current scan rules for '{os.path.basename(rules_fp)}' have unsaved changes. Save them to this rules file before saving the profile?", parent=self.root)
            if save_rules_choice is True: # Yes
                self._save_rules_list_changes()
                if self.rules_dirty:
                    messagebox.showerror("Profile Save Halted", "Failed to save the scan rules. Profile not saved.", parent=self.root)
                    return
            elif save_rules_choice is None or save_rules_choice is False: # Cancel or No
                 self._update_status("Save profile cancelled due to unsaved rule changes.", clear_after_ms=4000)
                 return
        
        self.profiles[profile_name] = {
            "scan_directory": os.path.normpath(scan_dir),
            "save_filepath": os.path.normpath(save_fp),
            "rules_filepath": os.path.normpath(rules_fp) if rules_fp else "",
            "filter_mode": filter_mode,
            "directory_tree_blacklist": current_tree_blacklist,
            "generate_directory_tree": current_generate_tree_setting
        }
        self.last_active_profile_name = profile_name
        self.active_profile_name = profile_name
        
        self.directory_tree_blacklist_dirty = False
        # If rules were required to be saved, self.rules_dirty is now False.
        self.rules_dirty = False
        
        try:
            profile_handler.save_profiles(self.profiles, self.last_active_profile_name, app_config.PROFILES_PATH)
            self._update_status(f"Profile '{profile_name}' saved.", clear_after_ms=3000)
        except Exception as e:
            messagebox.showerror("Profile Save Error", f"Could not save profiles: {e}", parent=self.root)
            self._update_status(f"Error saving profile '{profile_name}'.", clear_after_ms=5000)

        self._update_window_title()
        self._update_profile_menu_state()


    def _apply_profile_settings(self, profile_name, persist_last_active=False):
        profile_data = self.profiles.get(profile_name)
        if not profile_data:
            messagebox.showerror("Error", f"Profile '{profile_name}' not found.", parent=self.root)
            self.active_profile_name = None
            self._update_window_title()
            self._update_profile_menu_state()
            return False

        new_rules_filepath_from_profile = profile_data.get("rules_filepath", "")
        normalized_new_rules_path = os.path.normpath(new_rules_filepath_from_profile) if new_rules_filepath_from_profile else ""
        
        current_gui_rules_path_val = self.current_rules_filepath.get()
        normalized_current_gui_rules_path = os.path.normpath(current_gui_rules_path_val) if current_gui_rules_path_val else ""

        if self.rules_dirty and normalized_new_rules_path != normalized_current_gui_rules_path:
            msg = f"You have unsaved changes in the current scan rules list"
            if normalized_current_gui_rules_path:
                 msg += f" for\n'{os.path.basename(normalized_current_gui_rules_path)}'."
            else:
                 msg += "."
            msg += f"\n\nDiscard these changes to load settings from profile '{profile_name}'?"
            if not messagebox.askyesno("Unsaved Scan Rules", msg, default=messagebox.NO, parent=self.root):
                self._update_status(f"Profile '{profile_name}' load cancelled to keep unsaved scan rule changes.", clear_after_ms=4000)
                return False
            self.rules_dirty = False

        self.scan_directory.set(profile_data.get("scan_directory", ""))
        self.save_filepath.set(os.path.join(os.path.expanduser("~"), app_config.DEFAULT_OUTPUT_FILENAME))
        self.filter_mode_var.set(profile_data.get("filter_mode", app_config.FILTER_BLACKLIST))
        self.directory_tree_blacklist = list(profile_data.get("directory_tree_blacklist", []))
        self.generate_directory_tree_var.set(profile_data.get("generate_directory_tree", True))
        
        self.directory_tree_blacklist_dirty = False
        
        self.current_rules_filepath.set(new_rules_filepath_from_profile)
        self._load_rules_from_file() # This loads rules and sets rules_dirty to False

        if self.tree:
            self.tree.delete(*self.tree.get_children())
            self._update_status("Profile loaded. Refresh the directory tree to see rule associations.", clear_after_ms=5000)


        self.active_profile_name = profile_name
        if persist_last_active:
            self.last_active_profile_name = profile_name
            try:
                profile_handler.save_profiles(self.profiles, self.last_active_profile_name, app_config.PROFILES_PATH)
            except Exception as e:
                 messagebox.showerror("Profile Save Error", f"Could not persist last active profile setting: {e}", parent=self.root)

        self._update_window_title()
        self._on_filter_mode_change(update_status=False)
        self._update_profile_menu_state()
        return True


    def _load_profile_dialog(self):
        self._manage_profiles_dialog(initial_action="load")

    def _delete_profile_dialog(self):
        self._manage_profiles_dialog(initial_action="delete")

    def _manage_profiles_dialog(self, initial_action="load"):
        if not self.profiles and initial_action != "save":
            messagebox.showinfo("No Profiles", "No profiles saved yet to manage.", parent=self.root)
            return
        dialog = ManageProfilesDialog(self.root, self.profiles, 
                                      current_active_profile=self.active_profile_name, 
                                      app_instance=self, 
                                      initial_action=initial_action)

    def _execute_load_profile(self, profile_name_to_load):
        """Called by ManageProfilesDialog to actually load a profile."""
        if self._apply_profile_settings(profile_name_to_load, persist_last_active=True):
            self._update_status(f"Profile '{profile_name_to_load}' loaded.", clear_after_ms=3000)
            return True
        return False

    def _execute_delete_profile(self, profile_name_to_delete):
        """Called by ManageProfilesDialog to actually delete a profile."""
        if profile_name_to_delete in self.profiles:
            del self.profiles[profile_name_to_delete]
            
            was_active_profile = (self.active_profile_name == profile_name_to_delete)
            
            if self.last_active_profile_name == profile_name_to_delete:
                self.last_active_profile_name = None
            
            if was_active_profile:
                self.active_profile_name = None
                self.scan_directory.set("")
                self.save_filepath.set(os.path.join(os.path.expanduser("~"), app_config.DEFAULT_OUTPUT_FILENAME))
                self.current_rules_filepath.set("")
                self.rules_files, self.rules_folders = [], []
                self.filter_mode_var.set(app_config.FILTER_BLACKLIST)
                self.directory_tree_blacklist = []
                self.generate_directory_tree_var.set(True)
        
                if self.tree: self.tree.delete(*self.tree.get_children())
                self.directory_tree_blacklist_dirty = False
                self.rules_dirty = False
                self._update_status("Active profile was deleted. Please configure or load another.", clear_after_ms=5000)
            
            try:
                profile_handler.save_profiles(self.profiles, self.last_active_profile_name, app_config.PROFILES_PATH)
            except Exception as e:
                 messagebox.showerror("Profile Save Error", f"Could not save profile changes after deletion: {e}", parent=self.root)
            
            self._update_window_title()
            self._update_profile_menu_state()
            if not was_active_profile:
                 self._update_status(f"Profile '{profile_name_to_delete}' deleted.", clear_after_ms=3000)
            return True
        return False


    def _browse_scan_directory(self):
        initial_dir = self.scan_directory.get() or os.path.expanduser("~")
        directory = filedialog.askdirectory(title="Select Directory to Scan", initialdir=initial_dir, parent=self.root)
        if directory:
            self.scan_directory.set(os.path.normpath(directory))
            self._update_status("Scan directory selected. You can now load it into the file explorer.")
        else:
            self._update_status("Scan directory selection cancelled.")

    def _browse_save_file(self):
        current_save_path = self.save_filepath.get()
        initial_dir_suggestion = None
        if current_save_path:
            potential_dir = os.path.dirname(current_save_path)
            if os.path.isdir(potential_dir):
                initial_dir_suggestion = potential_dir
        
        if not initial_dir_suggestion:
            scan_dir = self.scan_directory.get()
            if scan_dir and os.path.isdir(scan_dir):
                initial_dir_suggestion = scan_dir
            else:
                initial_dir_suggestion = os.path.expanduser("~")

        initial_file_suggestion = os.path.basename(current_save_path) or app_config.DEFAULT_OUTPUT_FILENAME

        filepath = filedialog.asksaveasfilename(
            title="Save Scan Output As",
            initialdir=initial_dir_suggestion,
            initialfile=initial_file_suggestion,
            defaultextension=".txt",
            filetypes=[("Text Files", "*.txt"), ("Markdown Files", "*.md"), ("All Files", "*.*")],
            parent=self.root
        )
        if filepath:
            self.save_filepath.set(os.path.normpath(filepath))
            self._update_status("Save location selected.")
        else:
            self.save_filepath.set(current_save_path)
            self._update_status("Save location selection cancelled.")

    def _load_rules_from_file(self):
        """Loads rules from the path in current_rules_filepath into memory."""
        filepath = self.current_rules_filepath.get()
        if not filepath:
            self.rules_files, self.rules_folders = [], []
            self.rules_dirty = False
            if self.tree: self._update_all_tree_visuals()
            return
            
        normalized_filepath = os.path.normpath(filepath)
        if os.path.exists(normalized_filepath) and os.path.isfile(normalized_filepath):
            try:
                self.rules_files, self.rules_folders = rule_manager.load_ignore_rules(normalized_filepath)
                self.rules_dirty = False
                self._update_status(f"Loaded {len(self.rules_files) + len(self.rules_folders)} rules from {os.path.basename(normalized_filepath)}", clear_after_ms=4000)
            except Exception as e:
                messagebox.showerror("Load Error", f"Could not load scan rules from {os.path.basename(filepath)}:\n{e}", parent=self.root)
                self.rules_files, self.rules_folders = [], []
        else: # File doesn't exist, treat as empty
            self.rules_files, self.rules_folders = [], []
        
        self.rules_dirty = False
        if self.tree: self._update_all_tree_visuals()
        self._update_window_title()

    def _browse_rules_file(self):
        initial_dir_browse = os.path.dirname(self.current_rules_filepath.get()) or \
                             self.scan_directory.get() or \
                             os.path.expanduser("~")

        filepath_selected = filedialog.asksaveasfilename(
            title="Select or Create Path-Based Rules File",
            initialdir=initial_dir_browse,
            initialfile=".scanIgnore",
            filetypes=[("ScanIgnore Files", ".scanIgnore"), ("Text Files", "*.txt"), ("All Files", "*.*")],
            parent=self.root
        )

        if not filepath_selected:
            self._update_status("Rules file selection cancelled.")
            return

        normalized_new_filepath = os.path.normpath(filepath_selected)
        current_rules_path_val = self.current_rules_filepath.get()
        current_normalized_path = os.path.normpath(current_rules_path_val) if current_rules_path_val else None

        if normalized_new_filepath == current_normalized_path:
            self._update_status("Selected the current rules file. No change.", clear_after_ms=3000)
            return

        if self.rules_dirty:
            msg = f"You have unsaved changes in the current scan rules."
            if current_normalized_path: msg += f" for\n'{os.path.basename(current_normalized_path)}'."
            msg += "\n\nDiscard changes and switch to the new file?"
            if not messagebox.askyesno("Unsaved Changes", msg, default=messagebox.NO, parent=self.root):
                self._update_status("Rules file selection cancelled to keep unsaved changes.")
                return
            self.rules_dirty = False

        self.current_rules_filepath.set(normalized_new_filepath)
        
        # If new file doesn't exist, create it
        if not os.path.exists(normalized_new_filepath):
            try:
                if not rule_manager.create_empty_file(normalized_new_filepath, is_rules_file=True):
                    self.current_rules_filepath.set("") # Clear path if creation failed
            except Exception as e_create:
                messagebox.showerror("File Creation Error", f"Could not create file:\n{normalized_new_filepath}\nError: {e_create}", parent=self.root)
                self.current_rules_filepath.set("")

        self._load_rules_from_file()

    def _save_rules_list_changes(self):
        current_path_to_save = self.current_rules_filepath.get()
        if not current_path_to_save:
            self._update_status("No scan rules file is active. Please select or create one.")
            messagebox.showerror("Save Error", "No scan rules file is currently active to save to.", parent=self.root)
            return

        normalized_current_path_save = os.path.normpath(current_path_to_save)
        if not self.rules_dirty:
            self._update_status(f"No unsaved changes for {os.path.basename(normalized_current_path_save)}.")
            return

        try:
            normalized_files_to_save = sorted([os.path.normpath(p) for p in self.rules_files])
            normalized_folders_to_save = sorted([os.path.normpath(p) for p in self.rules_folders])
            rule_manager.save_ignore_rules(normalized_current_path_save, normalized_files_to_save, normalized_folders_to_save)
            self.rules_dirty = False
            self._update_window_title()
            self._update_status(f"Saved scan rule changes to {os.path.basename(normalized_current_path_save)}", clear_after_ms=3000)
        except Exception as e:
            messagebox.showerror("Save Error", f"Could not save scan rules to {os.path.basename(normalized_current_path_save)}:\n{e}", parent=self.root)
            self._update_status(f"Error saving scan rules {os.path.basename(normalized_current_path_save)}")

    # --- Tree View Logic ---
    
    def _load_default_ignore_patterns(self):
        """Loads name-based ignore patterns from the default file to filter the tree view."""
        self.default_ignore_patterns = {'file': [], 'folder': []}
        try:
            with open(app_config.DEFAULT_IGNORE_PATH, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#"): continue
                    
                    if line.lower().startswith("file:"):
                        pattern = line[len("file:"):].strip()
                        if pattern: self.default_ignore_patterns['file'].append(pattern)
                    elif line.lower().startswith("folder:"):
                        pattern = line[len("folder:"):].strip()
                        if pattern: self.default_ignore_patterns['folder'].append(pattern)
        except Exception as e:
            self._update_status(f"Warning: Could not load default ignore patterns: {e}", clear_after_ms=4000)

    def _populate_tree_view(self):
        """
        Populates the tree view using a lazy-loading approach.
        Only the top-level of the selected directory is loaded initially.
        """
        scan_dir = self.scan_directory.get()
        if not scan_dir or not os.path.isdir(scan_dir):
            messagebox.showerror("Input Error", "Please select a valid directory to scan first.", parent=self.root)
            return
        
        self._load_default_ignore_patterns()
        
        for i in self.tree.get_children(): self.tree.delete(i)
        self.tree_item_paths.clear()

        self._update_status("Loading directory tree...")
        
        # Insert the root node representing the selected directory
        node_text = os.path.basename(scan_dir)
        root_node_id = self.tree.insert('', 'end', text=f"📁 {node_text}", open=True)
        self.tree_item_paths[root_node_id] = (scan_dir, True)

        # Populate its direct children
        self._populate_children(root_node_id)
        
        # Update visuals for the root node itself, as it might have rules applied
        self._update_tree_visuals_for_items([root_node_id])

        self._update_status("Directory tree loaded.", clear_after_ms=4000)

    def _populate_children(self, parent_id):
        """Populates the direct children of a given parent node in the tree."""
        parent_path, _ = self.tree_item_paths.get(parent_id, (None, None))
        if not parent_path:
            return

        # Temporarily unbind the event to prevent recursive calls during population
        self.tree.unbind('<<TreeviewOpen>>')
        try:
            entries = os.scandir(parent_path)
        except (OSError, PermissionError) as e:
            self.tree.insert(parent_id, 'end', text=f"Error: {e.strerror}")
            # Re-bind the event before exiting
            self.tree.bind('<<TreeviewOpen>>', self._on_tree_open)
            return

        # Separate and filter directories and files
        dirs_to_add, files_to_add = [], []
        for entry in entries:
            if entry.is_dir():
                if not any(fnmatch.fnmatch(entry.name, p) for p in self.default_ignore_patterns['folder']):
                    dirs_to_add.append(entry)
            else:
                if not any(fnmatch.fnmatch(entry.name, p) for p in self.default_ignore_patterns['file']):
                    files_to_add.append(entry)

        # Sort alphabetically
        dirs_to_add.sort(key=lambda e: e.name.lower())
        files_to_add.sort(key=lambda e: e.name.lower())
        
        items_to_update_visuals = []

        # Add directories to the tree
        for entry in dirs_to_add:
            full_path = entry.path
            node_text = f"📁 {entry.name}"
            child_id = self.tree.insert(parent_id, 'end', text=node_text, open=False)
            self.tree_item_paths[child_id] = (full_path, True)
            # Add a placeholder child to make the node expandable
            self.tree.insert(child_id, 'end', text='...')
            items_to_update_visuals.append(child_id)

        # Add files to the tree
        for entry in files_to_add:
            full_path = entry.path
            node_text = f"📄 {entry.name}"
            child_id = self.tree.insert(parent_id, 'end', text=node_text, open=False)
            self.tree_item_paths[child_id] = (full_path, False)
            items_to_update_visuals.append(child_id)
        
        # Update the visual indicators (rules, etc.) for all newly added items
        if items_to_update_visuals:
            self._update_tree_visuals_for_items(items_to_update_visuals)
            
        # Re-enable the event binding after population is complete
        self.tree.bind('<<TreeviewOpen>>', self._on_tree_open)
        
    def _on_tree_open(self, event):
        """Event handler called when a user expands a directory in the tree."""
        # The 'focus' method gives the item that is about to be opened
        item_id = self.tree.focus()
        
        children = self.tree.get_children(item_id)
        # Only populate if it has a single placeholder child, indicating it's not yet loaded
        if len(children) == 1 and self.tree.item(children[0], 'text') == '...':
            # Clear the placeholder item
            self.tree.delete(children[0])
            # Populate with the actual directory contents
            self._populate_children(item_id)

    def _apply_rules_to_selection(self, rule_type, action): # rule_type: 'scan_rule' or 'tree_blacklist', action: 'add' or 'remove'
        selected_items = self.tree.selection()
        if not selected_items:
            self._update_status("No items selected in the tree.", clear_after_ms=3000)
            return
        
        items_to_update = set()
        for item_id in selected_items:
            items_to_update.add(item_id)
            # With lazy loading, we can only get currently visible children
            for child_id in self._get_all_children(item_id):
                items_to_update.add(child_id)
        
        for item_id in items_to_update:
            full_path, is_dir = self.tree_item_paths.get(item_id, (None, None))
            if not full_path: continue

            # --- Handle Scan Rules ---
            if rule_type == 'scan_rule':
                target_list = self.rules_folders if is_dir else self.rules_files
                if action == 'add' and full_path not in target_list:
                    target_list.append(full_path)
                    self.rules_dirty = True
                elif action == 'remove' and full_path in target_list:
                    target_list.remove(full_path)
                    self.rules_dirty = True

            # --- Handle Tree Blacklist ---
            elif rule_type == 'tree_blacklist' and is_dir: # Only folders can be blacklisted
                target_list = self.directory_tree_blacklist
                if action == 'add' and full_path not in target_list:
                    target_list.append(full_path)
                    self.directory_tree_blacklist_dirty = True
                elif action == 'remove' and full_path in target_list:
                    target_list.remove(full_path)
                    self.directory_tree_blacklist_dirty = True

        self._update_tree_visuals_for_items(items_to_update)
        self._update_window_title()
        self._update_status(f"Applied rule changes to {len(selected_items)} selected item(s) and their children.", clear_after_ms=4000)
    
    def _get_all_children(self, item_id, children_list=None):
        """Recursively gets all *loaded* children for a given tree item."""
        if children_list is None: children_list = []
        
        children = self.tree.get_children(item_id)
        for child_id in children:
            # Avoid recursing into placeholder items
            if self.tree.item(child_id, 'text') != '...':
                children_list.append(child_id)
                self._get_all_children(child_id, children_list)
        return children_list
        
    def _update_tree_visuals_for_items(self, item_ids):
        for item_id in item_ids:
            full_path, is_dir = self.tree_item_paths.get(item_id, (None, None))
            if not full_path: continue
            
            # Scan rule check
            is_scan_rule_applied = (full_path in self.rules_folders) if is_dir else (full_path in self.rules_files)
            self.tree.set(item_id, 'scan_rule', "✓" if is_scan_rule_applied else "")
            
            # Tree blacklist check (only for folders)
            is_blacklisted = (is_dir and full_path in self.directory_tree_blacklist)
            self.tree.set(item_id, 'tree_blacklist', "✓" if is_blacklisted else "")
    
    def _update_all_tree_visuals(self):
        """Iterates through the entire tree to update visuals based on current rule lists."""
        all_item_ids = list(self.tree_item_paths.keys())
        self._update_tree_visuals_for_items(all_item_ids)

    def _edit_defaults_dialog(self):
        dialog = EditDefaultsDialog(self.root, app_config.DEFAULT_IGNORE_PATH, app_instance=self)
    
    def _run_scan_thread(self, scan_dir_norm, save_path_norm, rules_files_for_scan, rules_folders_for_scan, filter_mode_val, used_rules_file_display_path, generate_tree_flag, tree_blacklist_for_scan):
        try:
            with open(save_path_norm, "w", encoding="utf-8") as output_file:
                if generate_tree_flag:
                    self.root.after(0, lambda: self._update_status("Generating directory tree..."))
                    tree_header = f"# Directory Tree for: {os.path.basename(scan_dir_norm)}\n\n"
                    normalized_tree_blacklist = [os.path.normpath(p) for p in tree_blacklist_for_scan]
                    tree_structure = scan_engine.generate_directory_tree_text(scan_dir_norm, normalized_tree_blacklist)
                    output_file.write(tree_header)
                    if tree_structure:
                        output_file.write(tree_structure)
                    else:
                        output_file.write(f"{os.path.basename(scan_dir_norm)}/\n (No subdirectories found or all were blacklisted)\n")
                    output_file.write("\n\n---\n\n")

                output_file.write(f"# Codebase Scan: {os.path.basename(scan_dir_norm)}\n\n")
                mode_desc = "Whitelist (Including only listed paths)" if filter_mode_val == app_config.FILTER_WHITELIST else "Blacklist (Excluding listed paths)"
                output_file.write(f"**Mode:** `{mode_desc}`\n")
                
                rules_source_display = ""
                if used_rules_file_display_path:
                    rules_source_display = f"`{os.path.basename(used_rules_file_display_path)}` (from `{used_rules_file_display_path}`)"
                    if self.rules_dirty :
                        rules_source_display += " - with unsaved modifications in GUI"
                else:
                    rules_source_display = "`Current GUI rules (No file or unsaved changes to a file)`"
                output_file.write(f"**Rules From:** {rules_source_display}\n\n")

                initial_whitelisted_ancestors = []
                if filter_mode_val == app_config.FILTER_WHITELIST and scan_dir_norm in rules_folders_for_scan:
                    initial_whitelisted_ancestors.append(scan_dir_norm)
                
                def thread_safe_status_update(msg):
                    self.root.after(0, lambda m=msg: self._update_status(m))

                scan_engine.process_directory(
                    scan_dir_norm, output_file, rules_files_for_scan, rules_folders_for_scan,
                    filter_mode_val, level=0, status_callback=thread_safe_status_update,
                    whitelisted_ancestor_folders=initial_whitelisted_ancestors
                )
        
            
            def on_scan_complete_actions():
                self._update_status(f"Scan complete. Output saved to: {save_path_norm}", clear_after_ms=10000)
                messagebox.showinfo("Scan Complete", f"Output successfully saved to:\n{save_path_norm}", parent=self.root)
            self.root.after(0, on_scan_complete_actions)

        except Exception as e:
            tb_str = traceback.format_exc()
            error_message_full = f"An error occurred during scanning or writing:\n{e}\n\nTraceback:\n{tb_str}"
            print(f"Full scan error details: {error_message_full}")
            
            def on_scan_error_actions():
                self._update_status(f"Error during scan: {e}", clear_after_ms=10000)
                messagebox.showerror("Scan Error", f"An error occurred: {e}\nSee console for more details.", parent=self.root)
            self.root.after(0, on_scan_error_actions)


    def _run_scan(self):
        scan_dir_ui = self.scan_directory.get()
        save_path_ui = self.save_filepath.get()
        rules_path_ui_current = self.current_rules_filepath.get()
        filter_mode_selected = self.filter_mode_var.get()
        generate_tree_selected = self.generate_directory_tree_var.get()
        tree_blacklist_current = list(self.directory_tree_blacklist)

        if not scan_dir_ui or not os.path.isdir(scan_dir_ui):
            messagebox.showerror("Input Error", "Please select a valid directory to scan.", parent=self.root)
            self._update_status("Error: Invalid scan directory.", clear_after_ms=5000); return
        if not save_path_ui:
            messagebox.showerror("Input Error", "Please select a valid output file path.", parent=self.root)
            self._update_status("Error: Invalid save location.", clear_after_ms=5000); return

        save_dir_for_output = os.path.dirname(save_path_ui)
        if save_dir_for_output and not os.path.exists(save_dir_for_output):
            try: os.makedirs(save_dir_for_output, exist_ok=True)
            except Exception as e:
                 messagebox.showerror("Input Error", f"Could not create save directory:\n{save_dir_for_output}\nError: {e}", parent=self.root)
                 self._update_status(f"Error: Cannot create save directory.", clear_after_ms=5000); return
        
        scan_rules_files_mem = list(self.rules_files)
        scan_rules_folders_mem = list(self.rules_folders)

        norm_scan_dir_for_thread = os.path.normpath(scan_dir_ui)
        norm_save_path_for_thread = os.path.normpath(save_path_ui)
        
        normalized_rules_path_for_display = os.path.normpath(rules_path_ui_current) if rules_path_ui_current else None

        mode_text_display_scan = "Whitelist" if filter_mode_selected == app_config.FILTER_WHITELIST else "Blacklist"
        status_msg_scan = f"Starting {mode_text_display_scan} scan"
        if normalized_rules_path_for_display:
            status_msg_scan += f" using rules from {os.path.basename(normalized_rules_path_for_display)}"
            if self.rules_dirty:
                status_msg_scan += " (with unsaved modifications)"
        else:
            status_msg_scan += " using current GUI rules (no file associated or rules are in-memory)"
        
        if generate_tree_selected:
            status_msg_scan += ". Directory tree will be generated."
        
        self._update_status(status_msg_scan)
        print(status_msg_scan)

        self._update_status("Scanning in progress...")

        scan_thread = threading.Thread(
            target=self._run_scan_thread,
            args=(norm_scan_dir_for_thread, norm_save_path_for_thread,
                  scan_rules_files_mem, scan_rules_folders_mem,
                  filter_mode_selected, normalized_rules_path_for_display,
                  generate_tree_selected, tree_blacklist_current),
            daemon=True
        )
        scan_thread.start()


# --- Main Execution ---
if __name__ == "__main__":
    root = tk.Tk()
    app = CodeScannerApp(root)
    root.mainloop()