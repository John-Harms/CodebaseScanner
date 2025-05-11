# CodeScannerApp.py (formerly CodebaseScanner.py)

import os
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext, Toplevel, simpledialog
import threading
import sys # For sys.exit and other sys attributes if needed by app_config indirectly
import traceback # For detailed error logging in scan thread

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

        self.rules_files = []  # Full path rules for files
        self.rules_folders = [] # Full path rules for folders
        self.rules_dirty = False # Tracks unsaved changes to the current rules list

        self.directory_tree_blacklist = [] # List of full folder paths to exclude from directory tree
        self.directory_tree_blacklist_dirty = False # Tracks unsaved changes to the tree blacklist

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
        profile_menu = tk.Menu(menubar, tearoff=0)
        profile_menu.add_command(label="Save Profile...", command=self._save_profile_dialog)
        profile_menu.add_command(label="Load Profile...", command=self._load_profile_dialog) # Opens manage dialog
        profile_menu.add_command(label="Delete Profile...", command=self._delete_profile_dialog) # Opens manage dialog
        profile_menu.add_separator()
        profile_menu.add_command(label="Manage Profiles...", command=self._manage_profiles_dialog)
        menubar.add_cascade(label="Profiles", menu=profile_menu)
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

        # PanedWindow for resizeable sections
        self.paned_window = ttk.PanedWindow(main_frame, orient=tk.VERTICAL)
        self.paned_window.grid(row=current_row, column=0, columnspan=3, sticky=(tk.W, tk.E, tk.N, tk.S), pady=10)
        main_frame.rowconfigure(current_row, weight=1) # Make paned window area expandable
        

        # --- Rules List Frame (Scrollable) ---
        self.rules_outer_frame = ttk.Frame(self.paned_window)
        self.rules_frame = ttk.LabelFrame(self.rules_outer_frame, text="Scan Rules List", padding="5") # Title updated by _update_rules_frame_title
        self.rules_frame.pack(fill=tk.BOTH, expand=True)
        self.rules_outer_frame.columnconfigure(0, weight=1)
        self.rules_outer_frame.rowconfigure(0, weight=1)
        self.rules_frame.columnconfigure(0, weight=1)
        self.rules_frame.rowconfigure(0, weight=1) # Canvas/list area should expand

        self.rules_canvas = tk.Canvas(self.rules_frame, borderwidth=0)
        self.rules_list_frame_inner = ttk.Frame(self.rules_canvas) # Holds rule widgets
        self.rules_scrollbar = ttk.Scrollbar(self.rules_frame, orient="vertical", command=self.rules_canvas.yview)
        self.rules_canvas.configure(yscrollcommand=self.rules_scrollbar.set)
        self.rules_canvas.grid(row=0, column=0, sticky="nsew")
        self.rules_scrollbar.grid(row=0, column=1, sticky="ns")
        self.canvas_window_rules = self.rules_canvas.create_window((0, 0), window=self.rules_list_frame_inner, anchor="nw")
        
        self.rules_list_frame_inner.bind("<Configure>", lambda e, c=self.rules_canvas: self._on_frame_configure(e, c))
        self.rules_canvas.bind('<Configure>', lambda e, c=self.rules_canvas, cw=self.canvas_window_rules: self._on_canvas_configure(e, c, cw))

        rules_buttons_frame = ttk.Frame(self.rules_frame)
        rules_buttons_frame.grid(row=1, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=5)
        add_file_button = ttk.Button(rules_buttons_frame, text="Add File Rule(s)", command=self._add_file_rules)
        add_file_button.pack(side=tk.LEFT, padx=5)
        ToolTip(add_file_button, "Add one or more files to the rules list by their full path.")
        add_folder_button = ttk.Button(rules_buttons_frame, text="Add Folder Rule", command=self._add_folder_rule)
        add_folder_button.pack(side=tk.LEFT, padx=5)
        ToolTip(add_folder_button, "Add a folder to the rules list by its full path.")
        edit_defaults_button = ttk.Button(rules_buttons_frame, text="Edit Default Name Patterns", command=self._edit_defaults_dialog)
        edit_defaults_button.pack(side=tk.LEFT, padx=5)
        ToolTip(edit_defaults_button, f"Open editor for {os.path.basename(app_config.DEFAULT_IGNORE_PATH)} which uses name-based patterns (not full paths).")
        save_rules_button = ttk.Button(rules_buttons_frame, text="Save Rules List", command=self._save_rules_list_changes)
        save_rules_button.pack(side=tk.LEFT, padx=5)
        ToolTip(save_rules_button, "Save current path-based rules to the selected rules file.")

        self.paned_window.add(self.rules_outer_frame, weight=1)

        # --- Directory Tree Blacklist Frame (Scrollable) ---
        self.tree_blacklist_outer_frame = ttk.Frame(self.paned_window)
        self.tree_blacklist_frame = ttk.LabelFrame(self.tree_blacklist_outer_frame, text="Directory Tree Blacklist", padding="5")
        self.tree_blacklist_frame.pack(fill=tk.BOTH, expand=True)
        self.tree_blacklist_outer_frame.columnconfigure(0, weight=1)
        self.tree_blacklist_outer_frame.rowconfigure(0, weight=1)
        self.tree_blacklist_frame.columnconfigure(0, weight=1)
        self.tree_blacklist_frame.rowconfigure(0, weight=1) # Canvas/list area

        self.tree_blacklist_canvas = tk.Canvas(self.tree_blacklist_frame, borderwidth=0)
        self.tree_blacklist_list_frame_inner = ttk.Frame(self.tree_blacklist_canvas)
        self.tree_blacklist_scrollbar = ttk.Scrollbar(self.tree_blacklist_frame, orient="vertical", command=self.tree_blacklist_canvas.yview)
        self.tree_blacklist_canvas.configure(yscrollcommand=self.tree_blacklist_scrollbar.set)
        self.tree_blacklist_canvas.grid(row=0, column=0, sticky="nsew")
        self.tree_blacklist_scrollbar.grid(row=0, column=1, sticky="ns")
        self.canvas_window_tree_blacklist = self.tree_blacklist_canvas.create_window((0, 0), window=self.tree_blacklist_list_frame_inner, anchor="nw")

        self.tree_blacklist_list_frame_inner.bind("<Configure>", lambda e, c=self.tree_blacklist_canvas: self._on_frame_configure(e, c))
        self.tree_blacklist_canvas.bind('<Configure>', lambda e, c=self.tree_blacklist_canvas, cw=self.canvas_window_tree_blacklist: self._on_canvas_configure(e, c, cw))
        
        tree_blacklist_buttons_frame = ttk.Frame(self.tree_blacklist_frame)
        tree_blacklist_buttons_frame.grid(row=1, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=5)
        add_tree_blacklist_folder_button = ttk.Button(tree_blacklist_buttons_frame, text="Add Folder to Tree Blacklist", command=self._add_tree_blacklist_folder_rule)
        add_tree_blacklist_folder_button.pack(side=tk.LEFT, padx=5)
        ToolTip(add_tree_blacklist_folder_button, "Select a folder (full path) to exclude from the directory tree output.")
        
        self.paned_window.add(self.tree_blacklist_outer_frame, weight=1)
        current_row += 1 # After PanedWindow

        self._initialize_rules_file_and_display() # Loads or prepares rules file
        self._rebuild_tree_blacklist_gui() # Initial display for tree blacklist

        run_button = ttk.Button(main_frame, text="Run Scan", command=self._run_scan, style="Accent.TButton")
        run_button.grid(row=current_row, column=0, columnspan=3, pady=10)
        
        style = ttk.Style()
        try:
            style.configure("Accent.TButton", font=('TkDefaultFont', 10, 'bold'))
            style.configure("Small.TButton", padding=(1,1), font=('TkDefaultFont', 7)) # For remove buttons
        except tk.TclError:
            print("Could not apply custom button style(s).")

        status_bar = ttk.Label(self.root, textvariable=self.status_text, relief=tk.SUNKEN, anchor=tk.W, padding="2 5")
        status_bar.grid(row=1, column=0, sticky=(tk.W, tk.E)) # Status bar below main_frame

        main_frame.columnconfigure(1, weight=1) # Allow middle column with entries to expand

        # Mouse wheel scrolling for all relevant canvases
        self.root.bind_all("<MouseWheel>", self._on_mousewheel, add="+")
        self.root.bind_all("<Button-4>", self._on_mousewheel, add="+") # Linux scroll up
        self.root.bind_all("<Button-5>", self._on_mousewheel, add="+") # Linux scroll down

    def _on_generate_tree_toggle(self):
        if self.active_profile_name:
            # Mark profile as "dirty" by simply saving it; actual dirty flag for profiles is complex
            # For now, this action makes the profile different from its saved state.
            # A general profile_dirty flag could be added if more granular control is needed.
            self._update_status(f"Directory tree generation set to: {self.generate_directory_tree_var.get()}", clear_after_ms=3000)
            # Consider making profile dirty here, for now, saving profile will pick up current state.
            # self.profile_dirty = True (if such a flag existed)
            self._update_window_title() # Title might show generic dirty state if we implement that

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
        
        # Ensure GUI reflects loaded tree blacklist state
        self._rebuild_tree_blacklist_gui() # Call after directory_tree_blacklist is set
        self.directory_tree_blacklist_dirty = False # Reset dirty flag after loading profile
        self.rules_dirty = False # Reset rules dirty flag too

    def _on_frame_configure(self, event, canvas): # event can be None
        canvas.configure(scrollregion=canvas.bbox("all"))

    def _on_canvas_configure(self, event, canvas, canvas_window): # event can be None
        canvas.itemconfig(canvas_window, width=event.width) # Make inner frame fill canvas width

    def _on_mousewheel(self, event):
        # Determine which canvas is under the mouse pointer
        canvas_to_scroll = None
        x_root, y_root = event.x_root, event.y_root
        widget_under_mouse = self.root.winfo_containing(x_root, y_root)

        # Traverse up from the widget under mouse to find a known canvas
        current_widget = widget_under_mouse
        while current_widget is not None:
            if current_widget == self.rules_canvas:
                canvas_to_scroll = self.rules_canvas
                break
            if current_widget == self.tree_blacklist_canvas:
                canvas_to_scroll = self.tree_blacklist_canvas
                break
            # Check for dialog canvases if a dialog is active (more complex, simplified here)
            # This check might be better inside the dialog classes themselves if they are modal
            if isinstance(current_widget, Toplevel): # Could be a dialog
                # Check if this Toplevel has a known canvas attribute (e.g., from EditDefaultsDialog)
                if hasattr(current_widget, 'dialog_rules_canvas') and current_widget.dialog_rules_canvas.winfo_ismapped():
                    # Check if mouse is within this dialog's canvas bounds
                    dialog_canvas = current_widget.dialog_rules_canvas
                    dcx, dcy = dialog_canvas.winfo_rootx(), dialog_canvas.winfo_rooty()
                    dcw, dch = dialog_canvas.winfo_width(), dialog_canvas.winfo_height()
                    if dcx <= x_root < dcx + dcw and dcy <= y_root < dcy + dch:
                        canvas_to_scroll = dialog_canvas
                        break
                # Add similar checks for other dialogs if they have scrollable canvases
            if current_widget == self.root: # Stop if we reach the main root window
                break
            current_widget = current_widget.master # Go to parent widget

        if canvas_to_scroll:
            # Scroll direction (platform-agnostic for delta, with num for Linux)
            if event.num == 5 or (hasattr(event, 'delta') and event.delta < 0): # Scroll down
                canvas_to_scroll.yview_scroll(1, "units")
            elif event.num == 4 or (hasattr(event, 'delta') and event.delta > 0): # Scroll up
                canvas_to_scroll.yview_scroll(-1, "units")

    def _update_status(self, message, clear_after_ms=None):
        self.status_text.set(message)
        self.root.update_idletasks() # Ensure message updates immediately
        if clear_after_ms:
            # If a new message comes before clear_after_ms, the old timer might clear the new message.
            # This is a common issue. For simplicity, we keep it as is.
            # A more robust solution would involve cancelling previous timers.
            self.root.after(clear_after_ms, lambda: self.status_text.set("Ready") if self.status_text.get() == message else None)

    def _on_filter_mode_change(self):
        mode = self.filter_mode_var.get()
        mode_text = "Whitelist" if mode == app_config.FILTER_WHITELIST else "Blacklist"
        self._update_status(f"Filter mode changed to {mode_text}.", clear_after_ms=4000)
        self._update_rules_frame_title() # Title includes mode
        self._rebuild_rules_list_gui() # Labels in list change based on mode

    def _update_window_title(self):
        title = "Codebase Scanner"
        if self.active_profile_name:
            profile_dirty_indicator = ""
            # Combine dirty flags for a general profile dirty state
            if self.rules_dirty or self.directory_tree_blacklist_dirty: # Add other checks if profile tracks more
                # This indicates that the *active profile's settings in the GUI* are unsaved.
                # It doesn't mean the profile file itself is dirty.
                 profile_dirty_indicator = "*" 
            title += f" - Profile: {self.active_profile_name}{profile_dirty_indicator}"
        self.root.title(title)


    def _save_profile_dialog(self):
        profile_name = simpledialog.askstring("Save Profile", "Enter profile name:", parent=self.root)
        if not profile_name: # User cancelled or entered empty
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
        rules_fp = self.current_rules_filepath.get() # This is the path to the .scanIgnore file
        filter_mode = self.filter_mode_var.get()
        current_tree_blacklist = list(self.directory_tree_blacklist) # Save a copy
        current_generate_tree_setting = self.generate_directory_tree_var.get()

        if not scan_dir or not os.path.isdir(scan_dir):
            messagebox.showwarning("Incomplete Configuration", "Scan directory must be a valid directory.", parent=self.root); return
        if not save_fp :
             messagebox.showwarning("Incomplete Configuration", "Save output path must be set.", parent=self.root); return
        
        # Save current rules list if dirty and a rules file is active
        if self.rules_dirty and rules_fp:
            if messagebox.askyesnocancel("Unsaved Rules", f"The current scan rules for '{os.path.basename(rules_fp)}' have unsaved changes. Save them to this rules file before saving the profile?", parent=self.root) is True: # Yes
                self._save_rules_list_changes() # This will clear self.rules_dirty if successful
                if self.rules_dirty: # If save failed
                    messagebox.showerror("Profile Save Halted", "Failed to save the scan rules. Profile not saved.", parent=self.root)
                    return
            # If No or Cancel, profile will save with the *current rules_fp path*, but the rules themselves might be out of sync if not saved.
            # This behavior is complex. For simplicity, we assume if they save profile, associated files should be what they see or are warned.
            # Current implementation means profile saves a *pointer* to the rules file.

        self.profiles[profile_name] = {
            "scan_directory": os.path.normpath(scan_dir),
            "save_filepath": os.path.normpath(save_fp),
            "rules_filepath": os.path.normpath(rules_fp) if rules_fp else "", # Store empty if no rules file
            "filter_mode": filter_mode,
            "directory_tree_blacklist": current_tree_blacklist,
            "generate_directory_tree": current_generate_tree_setting
        }
        self.last_active_profile_name = profile_name
        self.active_profile_name = profile_name
        
        # Mark GUI state as clean with respect to this newly saved/overwritten profile
        self.directory_tree_blacklist_dirty = False 
        # If rules were just saved as part of this, rules_dirty is already False.
        # If rules were not saved, rules_dirty remains, reflecting state of the rules file, not profile.
        
        try:
            profile_handler.save_profiles(self.profiles, self.last_active_profile_name, app_config.PROFILES_PATH)
            self._update_status(f"Profile '{profile_name}' saved.", clear_after_ms=3000)
        except Exception as e:
            messagebox.showerror("Profile Save Error", f"Could not save profiles: {e}", parent=self.root)
            self._update_status(f"Error saving profile '{profile_name}'.", clear_after_ms=5000)

        self._update_window_title()


    def _apply_profile_settings(self, profile_name, persist_last_active=False):
        profile_data = self.profiles.get(profile_name)
        if not profile_data:
            messagebox.showerror("Error", f"Profile '{profile_name}' not found.", parent=self.root)
            self.active_profile_name = None # Clear active profile if load fails
            self._update_window_title()
            return False

        # --- Before changing settings, check for unsaved rules changes ---
        new_rules_filepath_from_profile = profile_data.get("rules_filepath", "")
        normalized_new_rules_path = os.path.normpath(new_rules_filepath_from_profile) if new_rules_filepath_from_profile else ""
        
        current_gui_rules_path_val = self.current_rules_filepath.get()
        normalized_current_gui_rules_path = os.path.normpath(current_gui_rules_path_val) if current_gui_rules_path_val else ""

        if self.rules_dirty and normalized_new_rules_path != normalized_current_gui_rules_path:
            # If rules are dirty AND the profile wants to load a DIFFERENT rules file
            msg = f"You have unsaved changes in the current scan rules list"
            if normalized_current_gui_rules_path:
                 msg += f" for\n'{os.path.basename(normalized_current_gui_rules_path)}'."
            else:
                 msg += "."
            msg += f"\n\nDiscard these changes to load settings from profile '{profile_name}'?"
            if not messagebox.askyesno("Unsaved Scan Rules", msg, default=messagebox.NO, parent=self.root):
                self._update_status(f"Profile '{profile_name}' load cancelled to keep unsaved scan rule changes.", clear_after_ms=4000)
                return False # Cancel loading profile
            self.rules_dirty = False # User chose to discard

        # --- Apply settings from profile ---
        self.scan_directory.set(profile_data.get("scan_directory", ""))
        self.save_filepath.set(profile_data.get("save_filepath", os.path.join(os.path.expanduser("~"), app_config.DEFAULT_OUTPUT_FILENAME)))
        self.filter_mode_var.set(profile_data.get("filter_mode", app_config.FILTER_BLACKLIST))
        self.directory_tree_blacklist = list(profile_data.get("directory_tree_blacklist", []))
        self.generate_directory_tree_var.set(profile_data.get("generate_directory_tree", True))
        
        self._rebuild_tree_blacklist_gui() # Update GUI for tree blacklist
        self.directory_tree_blacklist_dirty = False # Reset dirty flag for tree blacklist

        # Set the rules file path from profile *then* initialize/load it
        self.current_rules_filepath.set(new_rules_filepath_from_profile)
        self._initialize_rules_file_and_display() # This loads rules and sets rules_dirty to False

        self.active_profile_name = profile_name
        if persist_last_active:
            self.last_active_profile_name = profile_name
            try:
                profile_handler.save_profiles(self.profiles, self.last_active_profile_name, app_config.PROFILES_PATH)
            except Exception as e: # Catch error from saving profiles
                messagebox.showerror("Profile Save Error", f"Could not persist last active profile setting: {e}", parent=self.root)
                # Continue with profile load even if save_profiles fails here

        self._update_window_title()
        self._on_filter_mode_change() # Ensure UI (like rule list labels) updates based on loaded filter mode.
        return True


    def _load_profile_dialog(self):
        self._manage_profiles_dialog(initial_action="load")

    def _delete_profile_dialog(self):
        self._manage_profiles_dialog(initial_action="delete")

    def _manage_profiles_dialog(self, initial_action="load"):
        if not self.profiles and initial_action != "save": # "save" isn't an action for this dialog
            messagebox.showinfo("No Profiles", "No profiles saved yet to manage.", parent=self.root)
            return
        # Pass self (CodeScannerApp instance) as app_instance to the dialog
        dialog = ManageProfilesDialog(self.root, self.profiles, 
                                      current_active_profile=self.active_profile_name, 
                                      app_instance=self, 
                                      initial_action=initial_action)
        # Dialog is modal (wait_window), logic continues after it closes.
        # _execute_load_profile or _execute_delete_profile are called from the dialog.

    def _execute_load_profile(self, profile_name_to_load):
        """Called by ManageProfilesDialog to actually load a profile."""
        if self._apply_profile_settings(profile_name_to_load, persist_last_active=True):
            self._update_status(f"Profile '{profile_name_to_load}' loaded.", clear_after_ms=3000)
            return True # Indicate success to dialog
        return False

    def _execute_delete_profile(self, profile_name_to_delete):
        """Called by ManageProfilesDialog to actually delete a profile."""
        if profile_name_to_delete in self.profiles:
            del self.profiles[profile_name_to_delete]
            
            was_active_profile = (self.active_profile_name == profile_name_to_delete)
            
            if self.last_active_profile_name == profile_name_to_delete:
                self.last_active_profile_name = None # Clear last active if it was the one deleted
            
            if was_active_profile:
                self.active_profile_name = None
                # Reset main UI fields to defaults if the active profile was deleted
                self.scan_directory.set("")
                self.save_filepath.set(os.path.join(os.path.expanduser("~"), app_config.DEFAULT_OUTPUT_FILENAME))
                self.current_rules_filepath.set("") # Clear rules file path
                self._clear_and_display_rules_list(None) # Clear rules from GUI
                self.filter_mode_var.set(app_config.FILTER_BLACKLIST) # Reset filter mode
                self.directory_tree_blacklist = []
                self.generate_directory_tree_var.set(True)
                self._rebuild_tree_blacklist_gui()
                self.directory_tree_blacklist_dirty = False
                self.rules_dirty = False
                self._update_status("Active profile was deleted. Please configure or load another.", clear_after_ms=5000)
            
            try:
                profile_handler.save_profiles(self.profiles, self.last_active_profile_name, app_config.PROFILES_PATH)
            except Exception as e:
                 messagebox.showerror("Profile Save Error", f"Could not save profile changes after deletion: {e}", parent=self.root)
                 # Deletion from memory still occurred.
            
            self._update_window_title()
            if not was_active_profile: # If a non-active profile was deleted
                 self._update_status(f"Profile '{profile_name_to_delete}' deleted.", clear_after_ms=3000)
            return True # Indicate success to dialog
        return False


    def _browse_scan_directory(self):
        initial_dir = self.scan_directory.get() or os.path.expanduser("~")
        directory = filedialog.askdirectory(title="Select Directory to Scan", initialdir=initial_dir, parent=self.root)
        if directory:
            self.scan_directory.set(os.path.normpath(directory))
            self._update_status("Scan directory selected.")
        else:
            self._update_status("Scan directory selection cancelled.")

    def _browse_save_file(self):
        current_save_path = self.save_filepath.get()
        initial_dir_suggestion = None
        if current_save_path:
            potential_dir = os.path.dirname(current_save_path)
            if os.path.isdir(potential_dir):
                initial_dir_suggestion = potential_dir
        
        if not initial_dir_suggestion: # Fallback logic
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
            self.save_filepath.set(current_save_path) # Restore if cancelled
            self._update_status("Save location selection cancelled.")


    def _initialize_rules_file_and_display(self):
        """Handles loading rules from current_rules_filepath or setting up an empty list."""
        filepath = self.current_rules_filepath.get()
        if filepath:
            normalized_filepath = os.path.normpath(filepath)
            if os.path.exists(normalized_filepath) and os.path.isfile(normalized_filepath):
                self._load_and_display_rules(normalized_filepath)
            else: # File doesn't exist or is not a file
                prompt_create = messagebox.askyesno(
                    "Rules File Not Found",
                    f"Rules file not found or is not a file:\n'{normalized_filepath}'\n\nCreate a new empty rules file there?",
                    parent=self.root
                )
                if prompt_create:
                    try:
                        # Use rule_manager.create_empty_file
                        if rule_manager.create_empty_file(normalized_filepath, is_rules_file=True):
                            self._clear_and_display_rules_list(normalized_filepath) # Path exists, list is empty
                        else: # create_empty_file failed (e.g., permission error, showed its own messagebox)
                            self.current_rules_filepath.set("") # Clear path if creation failed
                            self._clear_and_display_rules_list(None)
                    except Exception as e_create: # Should be caught by create_empty_file, but as safeguard
                        messagebox.showerror("File Creation Error", f"Could not create file:\n{normalized_filepath}\nError: {e_create}", parent=self.root)
                        self.current_rules_filepath.set("")
                        self._clear_and_display_rules_list(None)
                else: # User chose not to create
                    self.current_rules_filepath.set("") # Clear the path
                    self._clear_and_display_rules_list(None)
        else: # No filepath set
            self._clear_and_display_rules_list(None)
        
        self._update_rules_frame_title() # Update title based on new state
        # self.rules_dirty should be False after this, as we've either loaded or cleared.


    def _browse_rules_file(self):
        initial_dir_browse = os.path.dirname(self.current_rules_filepath.get()) or \
                             self.scan_directory.get() or \
                             os.path.expanduser("~")

        filepath_selected = filedialog.asksaveasfilename( # asksaveasfilename allows creating new
            title="Select or Create Path-Based Rules File",
            initialdir=initial_dir_browse,
            initialfile=".scanIgnore", # Suggest common name
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
            msg = f"You have unsaved changes in the current scan rules list"
            if current_normalized_path: msg += f" for\n'{os.path.basename(current_normalized_path)}'."
            else: msg += "."
            msg += "\n\nDiscard changes and switch to the new file?"
            if not messagebox.askyesno("Unsaved Changes", msg, default=messagebox.NO, parent=self.root):
                self._update_status("Rules file selection cancelled to keep unsaved changes.")
                return
            self.rules_dirty = False # User chose to discard

        self.current_rules_filepath.set(normalized_new_filepath)
        self._initialize_rules_file_and_display() # This will load or create and clear dirty flag.
        # _update_rules_frame_title is called by _initialize_rules_file_and_display


    def _update_rules_frame_title(self):
        filepath = self.current_rules_filepath.get()
        mode = self.filter_mode_var.get()
        mode_text = "(Whitelist - Include Paths)" if mode == app_config.FILTER_WHITELIST else "(Blacklist - Exclude Paths)"
        dirty_star = "*" if self.rules_dirty else ""

        if filepath:
            title = f"Scan Rules: {os.path.basename(filepath)}{dirty_star} {mode_text}"
        else:
            title = f"Scan Rules (No file selected){dirty_star} {mode_text}"
        if hasattr(self, 'rules_frame'): # Ensure frame exists
            self.rules_frame.config(text=title)

    def _load_and_display_rules(self, filepath):
        if not filepath: # Should not happen if called from _initialize_rules_file_and_display correctly
            self._clear_and_display_rules_list(None)
            self._update_status("No rules file selected.")
            return
        try:
            normalized_filepath = os.path.normpath(filepath)
            # Use rule_manager.load_ignore_rules
            self.rules_files, self.rules_folders = rule_manager.load_ignore_rules(normalized_filepath)
            self.rules_dirty = False # Freshly loaded, so not dirty
            self._rebuild_rules_list_gui()
            self._update_status(f"Loaded {len(self.rules_files) + len(self.rules_folders)} scan rules from {os.path.basename(normalized_filepath)}", clear_after_ms=4000)
        except Exception as e:
            messagebox.showerror("Load Error", f"Could not load or parse scan rules from {os.path.basename(filepath)}:\n{e}", parent=self.root)
            self._update_status(f"Error loading scan rules from {os.path.basename(filepath)}", clear_after_ms=5000)
            self._clear_and_display_rules_list(filepath) # Clear list but keep filepath context for title
        finally:
            self._update_rules_frame_title() # Ensure title is updated

    def _clear_and_display_rules_list(self, filepath_context):
        """Clears internal rules and GUI. filepath_context is for status message."""
        self.rules_files, self.rules_folders = [], []
        self.rules_dirty = False
        self._rebuild_rules_list_gui()

        if filepath_context: # e.g. new empty file created, or load error for a file
            self._update_status(f"Scan rules list for {os.path.basename(filepath_context)} is now empty. Ready.", clear_after_ms=4000)
        else: # No file association
            self._update_status("No scan rules file loaded. Scan rules list cleared.")
        self._update_rules_frame_title()


    def _rebuild_rules_list_gui(self):
        if not hasattr(self, 'rules_list_frame_inner'): return # UI not ready

        for widget in self.rules_list_frame_inner.winfo_children():
            widget.destroy()

        row_num = 0
        current_file_path_active = self.current_rules_filepath.get() # Is a rules file active?
        mode = self.filter_mode_var.get()
        # Rule action text depends on mode (Include for Whitelist, Exclude for Blacklist)
        rule_action_text = "Include Path" if mode == app_config.FILTER_WHITELIST else "Exclude Path"

        # Display File Rules
        if self.rules_files:
            ttk.Label(self.rules_list_frame_inner, text=f"Files to {rule_action_text}:", font=('TkDefaultFont', 9, 'bold')).grid(row=row_num, column=0, columnspan=2, sticky=tk.W, padx=5, pady=(5,2))
            row_num += 1
            for path_rule in sorted(self.rules_files): # Display sorted
                item_frame = ttk.Frame(self.rules_list_frame_inner)
                item_frame.grid(row=row_num, column=0, columnspan=2, sticky=tk.EW, padx=5, pady=1)
                item_frame.columnconfigure(0, weight=1) # Label expands

                label_text = f"file: {path_rule}"
                max_len = 75 # Max length for display in GUI
                display_text = (label_text[:max_len-3] + "...") if len(label_text) > max_len else label_text
                
                lbl = ttk.Label(item_frame, text=display_text, anchor=tk.W)
                lbl.grid(row=0, column=0, sticky=tk.EW)
                if len(label_text) > max_len: ToolTip(lbl, label_text) # Full path in tooltip

                remove_button = ttk.Button(item_frame, text="x", width=2, style="Small.TButton",
                                           command=lambda p=path_rule: self._remove_rule_item('file', p))
                remove_button.grid(row=0, column=1, sticky=tk.E, padx=(5, 0))
                row_num += 1

        # Display Folder Rules
        if self.rules_folders:
            ttk.Label(self.rules_list_frame_inner, text=f"Folders to {rule_action_text}:", font=('TkDefaultFont', 9, 'bold')).grid(row=row_num, column=0, columnspan=2, sticky=tk.W, padx=5, pady=(10,2))
            row_num += 1
            for path_rule in sorted(self.rules_folders): # Display sorted
                item_frame = ttk.Frame(self.rules_list_frame_inner)
                item_frame.grid(row=row_num, column=0, columnspan=2, sticky=tk.EW, padx=5, pady=1)
                item_frame.columnconfigure(0, weight=1) # Label expands

                label_text = f"folder: {path_rule}"
                max_len = 75
                display_text = (label_text[:max_len-3] + "...") if len(label_text) > max_len else label_text

                lbl = ttk.Label(item_frame, text=display_text, anchor=tk.W)
                lbl.grid(row=0, column=0, sticky=tk.EW)
                if len(label_text) > max_len: ToolTip(lbl, label_text)

                remove_button = ttk.Button(item_frame, text="x", width=2, style="Small.TButton",
                                           command=lambda p=path_rule: self._remove_rule_item('folder', p))
                remove_button.grid(row=0, column=1, sticky=tk.E, padx=(5, 0))
                row_num += 1
        
        if not self.rules_files and not self.rules_folders:
            placeholder_text = "No scan rules defined." if current_file_path_active else "No scan rules file selected or rules defined."
            ttk.Label(self.rules_list_frame_inner, text=placeholder_text, foreground="grey").grid(row=0, column=0, columnspan=2, padx=5, pady=5, sticky=tk.W)

        self.rules_list_frame_inner.update_idletasks() # Crucial for scrollbar
        self._on_frame_configure(None, self.rules_canvas) # Update scroll region
        self._update_rules_frame_title() # Update title which might include dirty status


    def _remove_rule_item(self, item_type, path_pattern):
        removed = False
        if item_type == 'file':
            if path_pattern in self.rules_files:
                self.rules_files.remove(path_pattern)
                removed = True
        elif item_type == 'folder':
            if path_pattern in self.rules_folders:
                self.rules_folders.remove(path_pattern)
                removed = True

        if removed:
            self.rules_dirty = True # Mark as dirty
            self._rebuild_rules_list_gui() # This will also update title via its call chain
            self._update_status(f"Removed scan rule for '{os.path.basename(path_pattern)}'. Save changes to persist.", clear_after_ms=4000)
        else: # Should not happen if UI is in sync with data
            self._update_status(f"Scan rule for '{os.path.basename(path_pattern)}' not found for removal.", clear_after_ms=4000)


    def _add_file_rules(self):
        if not self.current_rules_filepath.get(): # Check if a rules file is active
            messagebox.showwarning("No Rules File Active", "Please select or create a scan rules file first before adding rules to it.", parent=self.root)
            return

        initial_dir_add = self.scan_directory.get() if self.scan_directory.get() and os.path.isdir(self.scan_directory.get()) else os.path.expanduser("~")
        filepaths_to_add = filedialog.askopenfilenames(
            title="Select File(s) to Add Scan Rule For (Full Path)",
            initialdir=initial_dir_add, parent=self.root
        )
        if not filepaths_to_add: # User cancelled
            self._update_status("Add file scan rule(s) cancelled.")
            return

        added_count = 0
        for fp_raw in filepaths_to_add:
            normalized_fp_add = os.path.normpath(fp_raw)
            if normalized_fp_add and normalized_fp_add not in self.rules_files:
                 self.rules_files.append(normalized_fp_add)
                 added_count += 1

        if added_count > 0:
            self.rules_files.sort() # Keep the list sorted
            self.rules_dirty = True
            self._rebuild_rules_list_gui()
            self._update_status(f"Added {added_count} file scan rule(s). Save changes to persist.", clear_after_ms=4000)
        elif filepaths_to_add : # Files were selected but none were new
            self._update_status("Selected file scan rule(s) already in list or invalid.")


    def _add_folder_rule(self):
        if not self.current_rules_filepath.get(): # Check if a rules file is active
            messagebox.showwarning("No Rules File Active", "Please select or create a scan rules file first before adding rules to it.", parent=self.root)
            return

        initial_dir_add_folder = self.scan_directory.get() if self.scan_directory.get() and os.path.isdir(self.scan_directory.get()) else os.path.expanduser("~")
        folderpath_to_add = filedialog.askdirectory(
            title="Select Folder to Add Scan Rule For (Full Path)",
            initialdir=initial_dir_add_folder, parent=self.root
        )
        if not folderpath_to_add: # User cancelled
            self._update_status("Add folder scan rule cancelled.")
            return

        normalized_fp_add_folder = os.path.normpath(folderpath_to_add)
        if normalized_fp_add_folder and normalized_fp_add_folder not in self.rules_folders:
            self.rules_folders.append(normalized_fp_add_folder)
            self.rules_folders.sort() # Keep sorted
            self.rules_dirty = True
            self._rebuild_rules_list_gui()
            self._update_status(f"Added folder scan rule for '{os.path.basename(normalized_fp_add_folder)}'. Save changes to persist.", clear_after_ms=4000)
        elif normalized_fp_add_folder: # Folder was selected but already in list
            self._update_status(f"Folder scan rule for '{os.path.basename(normalized_fp_add_folder)}' already in list.")


    def _save_rules_list_changes(self):
        current_path_to_save = self.current_rules_filepath.get()
        if not current_path_to_save:
            self._update_status("No scan rules file is active. Please select or create one.")
            messagebox.showerror("Save Error", "No scan rules file is currently active to save to.", parent=self.root)
            return

        normalized_current_path_save = os.path.normpath(current_path_to_save)
        if not self.rules_dirty:
            self._update_status(f"No unsaved changes in {os.path.basename(normalized_current_path_save)}.")
            return

        try:
            # Normalize paths before saving (though they should be already)
            normalized_files_to_save = sorted([os.path.normpath(p) for p in self.rules_files])
            normalized_folders_to_save = sorted([os.path.normpath(p) for p in self.rules_folders])
            # Use rule_manager.save_ignore_rules
            rule_manager.save_ignore_rules(normalized_current_path_save, normalized_files_to_save, normalized_folders_to_save)
            self.rules_dirty = False # Mark as clean
            self._rebuild_rules_list_gui() # Updates title via its call chain
            self._update_status(f"Saved scan rule changes to {os.path.basename(normalized_current_path_save)}", clear_after_ms=3000)
        except Exception as e:
            messagebox.showerror("Save Error", f"Could not save scan rules to {os.path.basename(normalized_current_path_save)}:\n{e}", parent=self.root)
            self._update_status(f"Error saving scan rules {os.path.basename(normalized_current_path_save)}")


    # --- Directory Tree Blacklist GUI Methods ---
    def _rebuild_tree_blacklist_gui(self):
        if not hasattr(self, 'tree_blacklist_list_frame_inner'): return

        for widget in self.tree_blacklist_list_frame_inner.winfo_children():
            widget.destroy()

        row_num = 0
        if self.directory_tree_blacklist:
            ttk.Label(self.tree_blacklist_list_frame_inner, text="Folders Blacklisted from Directory Tree:", font=('TkDefaultFont', 9, 'bold')).grid(row=row_num, column=0, columnspan=2, sticky=tk.W, padx=5, pady=(5,2))
            row_num += 1
            for path_rule in sorted(self.directory_tree_blacklist):
                item_frame = ttk.Frame(self.tree_blacklist_list_frame_inner)
                item_frame.grid(row=row_num, column=0, columnspan=2, sticky=tk.EW, padx=5, pady=1)
                item_frame.columnconfigure(0, weight=1)

                label_text = f"{path_rule}" # Just the path
                max_len = 80
                display_text = (label_text[:max_len-3] + "...") if len(label_text) > max_len else label_text
                
                lbl = ttk.Label(item_frame, text=display_text, anchor=tk.W)
                lbl.grid(row=0, column=0, sticky=tk.EW)
                if len(label_text) > max_len: ToolTip(lbl, label_text)

                remove_button = ttk.Button(item_frame, text="x", width=2, style="Small.TButton",
                                           command=lambda p=path_rule: self._remove_tree_blacklist_item(p))
                remove_button.grid(row=0, column=1, sticky=tk.E, padx=(5, 0))
                row_num += 1
        else:
            ttk.Label(self.tree_blacklist_list_frame_inner, text="No directories blacklisted from tree.", foreground="grey").grid(row=0, column=0, columnspan=2, padx=5, pady=5, sticky=tk.W)

        self.tree_blacklist_list_frame_inner.update_idletasks()
        self._on_frame_configure(None, self.tree_blacklist_canvas)
        self._update_tree_blacklist_frame_title() # In original, this did 'pass'
        self._update_window_title() # Main window title reflects dirty state

    def _add_tree_blacklist_folder_rule(self):
        initial_dir_add = self.scan_directory.get() if self.scan_directory.get() and os.path.isdir(self.scan_directory.get()) else os.path.expanduser("~")
        folderpath_to_add = filedialog.askdirectory(
            title="Select Folder to Blacklist from Directory Tree (Full Path)",
            initialdir=initial_dir_add, parent=self.root
        )
        if not folderpath_to_add:
            self._update_status("Add folder to tree blacklist cancelled.")
            return

        normalized_fp_add = os.path.normpath(folderpath_to_add)
        if normalized_fp_add and normalized_fp_add not in self.directory_tree_blacklist:
            self.directory_tree_blacklist.append(normalized_fp_add)
            self.directory_tree_blacklist.sort()
            self.directory_tree_blacklist_dirty = True
            self._rebuild_tree_blacklist_gui() # Will call _update_window_title via its chain
            self._update_status(f"Added '{os.path.basename(normalized_fp_add)}' to tree blacklist. Save profile to persist.", clear_after_ms=4000)
        elif normalized_fp_add:
            self._update_status(f"Folder '{os.path.basename(normalized_fp_add)}' already in tree blacklist.")

    def _remove_tree_blacklist_item(self, path_to_remove):
        normalized_path_remove = os.path.normpath(path_to_remove)
        if normalized_path_remove in self.directory_tree_blacklist:
            self.directory_tree_blacklist.remove(normalized_path_remove)
            self.directory_tree_blacklist_dirty = True
            self._rebuild_tree_blacklist_gui() # Will call _update_window_title via its chain
            self._update_status(f"Removed '{os.path.basename(normalized_path_remove)}' from tree blacklist. Save profile to persist.", clear_after_ms=4000)
        else:
            self._update_status(f"Folder '{os.path.basename(normalized_path_remove)}' not found in tree blacklist.", clear_after_ms=4000)

    def _update_tree_blacklist_frame_title(self):
        # Original method was 'pass'. Title is static. Dirty state reflected in main window title.
        pass


    def _edit_defaults_dialog(self):
        # Pass app_config.DEFAULT_IGNORE_PATH which is the path to ".scanIgnore.defaults"
        dialog = EditDefaultsDialog(self.root, app_config.DEFAULT_IGNORE_PATH, app_instance=self)
        # Dialog is modal, waits for it to close.


    def _run_scan_thread(self, scan_dir_norm, save_path_norm, rules_files_for_scan, rules_folders_for_scan, filter_mode_val, used_rules_file_display_path, generate_tree_flag, tree_blacklist_for_scan):
        try:
            with open(save_path_norm, "w", encoding="utf-8") as output_file:
                # Directory Tree Generation
                if generate_tree_flag:
                    self.root.after(0, lambda: self._update_status("Generating directory tree..."))
                    tree_header = f"# Directory Tree for: {os.path.basename(scan_dir_norm)}\n\n"
                    normalized_tree_blacklist = [os.path.normpath(p) for p in tree_blacklist_for_scan]
                    # Use scan_engine.generate_directory_tree_text
                    tree_structure = scan_engine.generate_directory_tree_text(scan_dir_norm, normalized_tree_blacklist)
                    output_file.write(tree_header)
                    if tree_structure:
                        output_file.write(tree_structure)
                    else:
                        output_file.write(f"{os.path.basename(scan_dir_norm)}/\n (No subdirectories found or all were blacklisted)\n")
                    output_file.write("\n\n---\n\n")

                # Main Scan Content Header
                output_file.write(f"# Codebase Scan: {os.path.basename(scan_dir_norm)}\n\n")
                mode_desc = "Whitelist (Including only listed paths)" if filter_mode_val == app_config.FILTER_WHITELIST else "Blacklist (Excluding listed paths)"
                output_file.write(f"**Mode:** `{mode_desc}`\n")
                
                rules_source_display = ""
                if used_rules_file_display_path:
                    rules_source_display = f"`{os.path.basename(used_rules_file_display_path)}` (from `{used_rules_file_display_path}`)"
                    if self.rules_dirty : # Check if the rules file associated in GUI is dirty
                         rules_source_display += " - with unsaved modifications in GUI"
                else:
                    rules_source_display = "`Current GUI rules (No file or unsaved changes to a file)`"
                output_file.write(f"**Rules From:** {rules_source_display}\n\n")

                initial_whitelisted_ancestors = []
                if filter_mode_val == app_config.FILTER_WHITELIST and scan_dir_norm in rules_folders_for_scan:
                    initial_whitelisted_ancestors.append(scan_dir_norm)
                
                # Use scan_engine.process_directory
                # Ensure status_callback is thread-safe for Tkinter (use root.after)
                def thread_safe_status_update(msg):
                    self.root.after(0, lambda m=msg: self._update_status(m))

                scan_engine.process_directory(
                    scan_dir_norm, output_file, rules_files_for_scan, rules_folders_for_scan,
                    filter_mode_val, level=0, status_callback=thread_safe_status_update,
                    whitelisted_ancestor_folders=initial_whitelisted_ancestors
                )
            
            # Scan complete actions (run in main GUI thread)
            def on_scan_complete_actions():
                self._update_status(f"Scan complete. Output saved to: {save_path_norm}", clear_after_ms=10000)
                messagebox.showinfo("Scan Complete", f"Output successfully saved to:\n{save_path_norm}", parent=self.root)
            self.root.after(0, on_scan_complete_actions)

        except Exception as e:
            # Scan error actions (run in main GUI thread)
            tb_str = traceback.format_exc()
            error_message_full = f"An error occurred during scanning or writing:\n{e}\n\nTraceback:\n{tb_str}"
            print(f"Full scan error details: {error_message_full}") # Log full error to console
            
            def on_scan_error_actions():
                self._update_status(f"Error during scan: {e}", clear_after_ms=10000)
                # Show a simpler error to user, full traceback in console
                messagebox.showerror("Scan Error", f"An error occurred: {e}\nSee console for more details.", parent=self.root)
            self.root.after(0, on_scan_error_actions)


    def _run_scan(self):
        scan_dir_ui = self.scan_directory.get()
        save_path_ui = self.save_filepath.get()
        rules_path_ui_current = self.current_rules_filepath.get() # Path to .scanIgnore file
        filter_mode_selected = self.filter_mode_var.get()
        generate_tree_selected = self.generate_directory_tree_var.get()
        tree_blacklist_current = list(self.directory_tree_blacklist) # Use a copy

        if not scan_dir_ui or not os.path.isdir(scan_dir_ui):
            messagebox.showerror("Input Error", "Please select a valid directory to scan.", parent=self.root)
            self._update_status("Error: Invalid scan directory.", clear_after_ms=5000); return
        if not save_path_ui:
            messagebox.showerror("Input Error", "Please select a valid output file path.", parent=self.root)
            self._update_status("Error: Invalid save location.", clear_after_ms=5000); return

        # Ensure save directory exists
        save_dir_for_output = os.path.dirname(save_path_ui)
        if save_dir_for_output and not os.path.exists(save_dir_for_output): # Check if save_dir is not empty
            try: os.makedirs(save_dir_for_output, exist_ok=True)
            except Exception as e:
                 messagebox.showerror("Input Error", f"Could not create save directory:\n{save_dir_for_output}\nError: {e}", parent=self.root)
                 self._update_status(f"Error: Cannot create save directory.", clear_after_ms=5000); return
        
        # Use copies of rules lists for the thread
        scan_rules_files_mem = list(self.rules_files)
        scan_rules_folders_mem = list(self.rules_folders)

        norm_scan_dir_for_thread = os.path.normpath(scan_dir_ui)
        norm_save_path_for_thread = os.path.normpath(save_path_ui)
        
        # Path for display in the output file header (could be None)
        normalized_rules_path_for_display = os.path.normpath(rules_path_ui_current) if rules_path_ui_current else None

        mode_text_display_scan = "Whitelist" if filter_mode_selected == app_config.FILTER_WHITELIST else "Blacklist"
        status_msg_scan = f"Starting {mode_text_display_scan} scan"
        if normalized_rules_path_for_display:
            status_msg_scan += f" using rules from {os.path.basename(normalized_rules_path_for_display)}"
            if self.rules_dirty: # If GUI rules for this file are unsaved
                status_msg_scan += " (with unsaved modifications)"
        else:
            status_msg_scan += " using current GUI rules (no file associated or rules are in-memory)"
        
        if generate_tree_selected:
            status_msg_scan += ". Directory tree will be generated."
        
        self._update_status(status_msg_scan) # Initial status before thread start
        print(status_msg_scan) # Log to console as well

        # Update status for "Scanning in progress..." after the print and initial update
        self._update_status("Scanning in progress...")

        scan_thread = threading.Thread(
            target=self._run_scan_thread,
            args=(norm_scan_dir_for_thread, norm_save_path_for_thread,
                  scan_rules_files_mem, scan_rules_folders_mem,
                  filter_mode_selected, normalized_rules_path_for_display,
                  generate_tree_selected, tree_blacklist_current),
            daemon=True # Allows main program to exit even if thread is running
        )
        scan_thread.start()


# --- Main Execution ---
if __name__ == "__main__":
    root = tk.Tk()
    app = CodeScannerApp(root)
    root.mainloop()