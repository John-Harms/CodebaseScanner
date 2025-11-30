# dialogs.py

import tkinter as tk
from tkinter import ttk, Toplevel, messagebox, filedialog, simpledialog
import os

# Assuming app_config might be needed for DEFAULT_IGNORE_PATH if not passed directly
from app_config import DEFAULT_IGNORE_PATH, DEFAULT_OUTPUT_FILENAME 
# Note: DEFAULT_IGNORE_PATH from app_config refers to the *name patterns* default file.
# The EditDefaultsDialog specifically manages this.

from ui_widgets import ToolTip # If ToolTips are used within dialogs, though not in original for these.
# EditDefaultsDialog's ToolTips were on its entry/buttons, defined in its __init__

# If rule_manager is needed for save_ignore_rules by EditDefaultsDialog
# (original EditDefaultsDialog handles its own simple file I/O for name patterns)
# from rule_manager import save_ignore_rules, load_ignore_rules # Example if needed

class EditDefaultsDialog(Toplevel):
    def __init__(self, parent, default_filepath_param, app_instance): # default_filepath_param is DEFAULT_IGNORE_PATH
        super().__init__(parent)
        self.default_filepath = default_filepath_param # This is app_config.DEFAULT_IGNORE_PATH
        self.app_instance = app_instance # For status updates

        self.title(f"Edit Default Name Patterns ({os.path.basename(self.default_filepath)})")
        self.geometry("600x500")
        self.transient(parent)
        self.grab_set()

        self.dialog_rule_file_patterns = []
        self.dialog_rule_folder_patterns = []

        main_dialog_frame = ttk.Frame(self, padding="10")
        main_dialog_frame.pack(fill=tk.BOTH, expand=True)
        main_dialog_frame.columnconfigure(0, weight=1)
        main_dialog_frame.rowconfigure(1, weight=1) # List area should expand

        input_frame = ttk.Frame(main_dialog_frame)
        input_frame.grid(row=0, column=0, sticky=tk.EW, pady=(0,10))
        input_frame.columnconfigure(0, weight=1) # Entry should expand

        self.pattern_entry_var = tk.StringVar()
        pattern_entry = ttk.Entry(input_frame, textvariable=self.pattern_entry_var, width=40)
        pattern_entry.grid(row=0, column=0, sticky=tk.EW, padx=(0,5))
        ToolTip(pattern_entry, "Enter a file/folder name or simple pattern (e.g., '*.log', 'temp_folder') to add to defaults.")

        add_file_pattern_btn = ttk.Button(input_frame, text="Add File Pattern", command=lambda: self._dialog_add_name_pattern('file'))
        add_file_pattern_btn.grid(row=0, column=1, padx=5)
        add_folder_pattern_btn = ttk.Button(input_frame, text="Add Folder Pattern", command=lambda: self._dialog_add_name_pattern('folder'))
        add_folder_pattern_btn.grid(row=0, column=2, padx=5)


        dialog_rules_frame = ttk.LabelFrame(main_dialog_frame, text="Default File/Folder Name Patterns List", padding="5")
        dialog_rules_frame.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        dialog_rules_frame.columnconfigure(0, weight=1)
        dialog_rules_frame.rowconfigure(0, weight=1) # Canvas should expand

        self.dialog_rules_canvas = tk.Canvas(dialog_rules_frame, borderwidth=0)
        self.dialog_rules_list_frame = ttk.Frame(self.dialog_rules_canvas) # Frame for widgets
        self.dialog_rules_scrollbar = ttk.Scrollbar(dialog_rules_frame, orient="vertical", command=self.dialog_rules_canvas.yview)
        self.dialog_rules_canvas.configure(yscrollcommand=self.dialog_rules_scrollbar.set)

        self.dialog_rules_canvas.grid(row=0, column=0, sticky="nsew")
        self.dialog_rules_scrollbar.grid(row=0, column=1, sticky="ns")

        self.dialog_canvas_window = self.dialog_rules_canvas.create_window((0, 0), window=self.dialog_rules_list_frame, anchor="nw")

        self.dialog_rules_list_frame.bind("<Configure>", self._on_dialog_list_frame_configure)
        self.dialog_rules_canvas.bind('<Configure>', self._on_dialog_canvas_viewport_configure)
        # Bind mousewheel scrolling to the canvas
        self.dialog_rules_canvas.bind("<MouseWheel>", self._on_dialog_specific_mousewheel) # For Windows/Mac
        self.dialog_rules_canvas.bind("<Button-4>", self._on_dialog_specific_mousewheel) # For Linux scroll up
        self.dialog_rules_canvas.bind("<Button-5>", self._on_dialog_specific_mousewheel) # For Linux scroll down


        action_buttons_frame = ttk.Frame(main_dialog_frame)
        action_buttons_frame.grid(row=2, column=0, sticky=tk.E, pady=(10,0))
        
        # Attempt to use Accent.TButton, fall back if not available (already in original)
        style = ttk.Style(self)
        try:
            save_button = ttk.Button(action_buttons_frame, text="Save Defaults", command=self._save_and_close_name_patterns, style="Accent.TButton")
        except tk.TclError:
            save_button = ttk.Button(action_buttons_frame, text="Save Defaults", command=self._save_and_close_name_patterns)
        save_button.pack(side=tk.LEFT, padx=5)
        
        cancel_button = ttk.Button(action_buttons_frame, text="Cancel", command=self.destroy)
        cancel_button.pack(side=tk.LEFT, padx=5)

        self._load_initial_name_patterns()
        self.wait_window(self) # Modal behavior


    def _on_dialog_list_frame_configure(self, event=None): # Add event=None for direct calls
        self.dialog_rules_canvas.configure(scrollregion=self.dialog_rules_canvas.bbox("all"))

    def _on_dialog_canvas_viewport_configure(self, event):
        self.dialog_rules_canvas.itemconfig(self.dialog_canvas_window, width=event.width)

    def _on_dialog_specific_mousewheel(self, event):
        # Determine scroll direction (platform-agnostic for delta, with num for Linux)
        if event.num == 5 or (hasattr(event, 'delta') and event.delta < 0):
            self.dialog_rules_canvas.yview_scroll(1, "units")
        elif event.num == 4 or (hasattr(event, 'delta') and event.delta > 0):
            self.dialog_rules_canvas.yview_scroll(-1, "units")

    def _load_initial_name_patterns(self):
        self.dialog_rule_file_patterns = []
        self.dialog_rule_folder_patterns = []
        try:
            # Ensure default file exists with some content if it's missing
            if not os.path.exists(self.default_filepath):
                 with open(self.default_filepath, "w", encoding="utf-8") as f:
                    f.write("# Default files to ignore (name patterns, e.g., *.log, specific_file.tmp)\n")
                    f.write("file: .DS_Store\n")
                    f.write("file: thumbs.db\n")
                    f.write("file: desktop.ini\n")
                    f.write("\n# Default folders to ignore (name patterns, e.g., .git, node_modules)\n")
                    f.write("folder: .git\n")
                    f.write("folder: .svn\n")
                    f.write("folder: .hg\n")
                    f.write("folder: .venv\n")
                    f.write("folder: venv\n")
                    f.write("folder: node_modules\n")
                    f.write("folder: __pycache__\n")
                    f.write("folder: build\n")
                    f.write("folder: dist\n")
                 print(f"Created default name patterns file: {self.default_filepath}")

            if os.path.exists(self.default_filepath): # Should always exist now
                with open(self.default_filepath, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if not line or line.startswith("#"): continue
                        if line.lower().startswith("file:"):
                            pattern = line[len("file:"):].strip()
                            if pattern and pattern not in self.dialog_rule_file_patterns:
                                 self.dialog_rule_file_patterns.append(pattern)
                        elif line.lower().startswith("folder:"):
                            pattern = line[len("folder:"):].strip()
                            if pattern and pattern not in self.dialog_rule_folder_patterns:
                                 self.dialog_rule_folder_patterns.append(pattern)
            self.dialog_rule_file_patterns.sort()
            self.dialog_rule_folder_patterns.sort()
        except Exception as e:
            messagebox.showerror("Load Error", f"Could not load default name patterns from\n{self.default_filepath}\n\nError: {e}", parent=self)
        self._rebuild_dialog_name_patterns_list()


    def _rebuild_dialog_name_patterns_list(self):
        for widget in self.dialog_rules_list_frame.winfo_children():
            widget.destroy()
        row_num = 0
        
        style = ttk.Style(self) # For Small.TButton
        try:
            style.configure("Small.TButton", padding=(1, 1), font=('TkDefaultFont', 7))
        except tk.TclError:
            pass # Style might not be applicable on all platforms or themes


        if self.dialog_rule_file_patterns:
            ttk.Label(self.dialog_rules_list_frame, text="File Name Patterns:", font=('TkDefaultFont', 9, 'bold')).grid(row=row_num, column=0, columnspan=2, sticky=tk.W, padx=5, pady=(5,2))
            row_num += 1
            for pattern_name in self.dialog_rule_file_patterns:
                item_f = ttk.Frame(self.dialog_rules_list_frame)
                item_f.grid(row=row_num, column=0, columnspan=2, sticky=tk.EW, padx=5, pady=1); item_f.columnconfigure(0, weight=1)
                ttk.Label(item_f, text=f"file: {pattern_name}", anchor=tk.W).grid(row=0, column=0, sticky=tk.EW)
                ttk.Button(item_f, text="x", width=2, style="Small.TButton", command=lambda p=pattern_name: self._dialog_remove_name_pattern('file', p)).grid(row=0, column=1, sticky=tk.E, padx=(5,0))
                row_num += 1

        if self.dialog_rule_folder_patterns:
            ttk.Label(self.dialog_rules_list_frame, text="Folder Name Patterns:", font=('TkDefaultFont', 9, 'bold')).grid(row=row_num, column=0, columnspan=2, sticky=tk.W, padx=5, pady=(10,2))
            row_num += 1
            for pattern_name in self.dialog_rule_folder_patterns:
                item_f = ttk.Frame(self.dialog_rules_list_frame)
                item_f.grid(row=row_num, column=0, columnspan=2, sticky=tk.EW, padx=5, pady=1); item_f.columnconfigure(0, weight=1)
                ttk.Label(item_f, text=f"folder: {pattern_name}", anchor=tk.W).grid(row=0, column=0, sticky=tk.EW)
                ttk.Button(item_f, text="x", width=2, style="Small.TButton", command=lambda p=pattern_name: self._dialog_remove_name_pattern('folder', p)).grid(row=0, column=1, sticky=tk.E, padx=(5,0))
                row_num += 1

        if not self.dialog_rule_file_patterns and not self.dialog_rule_folder_patterns:
            ttk.Label(self.dialog_rules_list_frame, text="No default name patterns defined.", foreground="grey").grid(row=0,column=0,padx=5,pady=5, sticky=tk.W)
        
        self.dialog_rules_list_frame.update_idletasks() # Important for scrollregion
        self._on_dialog_list_frame_configure() # Update scrollregion


    def _dialog_add_name_pattern(self, item_type_str):
        pattern_to_add = self.pattern_entry_var.get().strip()
        if not pattern_to_add:
            messagebox.showwarning("Input Missing", "Please enter a file or folder name pattern to add.", parent=self)
            return

        pattern_added_successfully = False
        if item_type_str == 'file':
            if pattern_to_add not in self.dialog_rule_file_patterns:
                self.dialog_rule_file_patterns.append(pattern_to_add)
                self.dialog_rule_file_patterns.sort()
                pattern_added_successfully = True
        elif item_type_str == 'folder':
            if pattern_to_add not in self.dialog_rule_folder_patterns:
                self.dialog_rule_folder_patterns.append(pattern_to_add)
                self.dialog_rule_folder_patterns.sort()
                pattern_added_successfully = True

        if pattern_added_successfully:
            self._rebuild_dialog_name_patterns_list()
            self.pattern_entry_var.set("") # Clear entry
        else:
            messagebox.showinfo("Pattern Exists", f"The pattern '{pattern_to_add}' is already in the list for its type.", parent=self)


    def _dialog_remove_name_pattern(self, item_type_str, pattern_to_remove):
        removed_successfully = False
        if item_type_str == 'file':
            if pattern_to_remove in self.dialog_rule_file_patterns:
                self.dialog_rule_file_patterns.remove(pattern_to_remove); removed_successfully = True
        elif item_type_str == 'folder':
            if pattern_to_remove in self.dialog_rule_folder_patterns:
                self.dialog_rule_folder_patterns.remove(pattern_to_remove); removed_successfully = True
        
        if removed_successfully:
            self._rebuild_dialog_name_patterns_list()

    def _save_and_close_name_patterns(self):
        try:
            # Ensure parent directory exists (it should, but good practice)
            parent_dir = os.path.dirname(self.default_filepath)
            if parent_dir and not os.path.exists(parent_dir):
                os.makedirs(parent_dir, exist_ok=True)

            with open(self.default_filepath, "w", encoding="utf-8") as f:
                f.write("# Default files to ignore (name patterns, e.g., *.log, specific_file.tmp)\n")
                for p_name in sorted(self.dialog_rule_file_patterns): f.write(f"file: {p_name}\n")
                f.write("\n# Default folders to ignore (name patterns, e.g., .git, node_modules)\n")
                for p_name in sorted(self.dialog_rule_folder_patterns): f.write(f"folder: {p_name}\n")

            if self.app_instance and hasattr(self.app_instance, '_update_status'):
                self.app_instance._update_status(f"Saved changes to default name patterns file: {os.path.basename(self.default_filepath)}", clear_after_ms=3000)
            self.destroy()
        except Exception as e:
            messagebox.showerror("Save Error", f"Could not save default name patterns to\n{self.default_filepath}\n\nError: {e}", parent=self)


class ManageProfilesDialog(Toplevel):
    def __init__(self, parent, profiles_data, current_active_profile, app_instance, initial_action="load"):
        super().__init__(parent)
        self.profiles_dict = profiles_data # This is a reference to app_instance.profiles
        self.app_instance_ref = app_instance # Reference to the main CodeScannerApp instance
        self.current_active_profile_name = current_active_profile # Name of the currently active profile

        self.title("Manage Scan Profiles")
        self.geometry("450x400") # Increased height for search box
        self.transient(parent) # Show above parent
        self.grab_set() # Modal behavior

        main_frame = ttk.Frame(self, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)
        main_frame.rowconfigure(2, weight=1) # Allow listbox to expand
        main_frame.columnconfigure(0, weight=1)

        # --- Search/Filter UI ---
        search_frame = ttk.Frame(main_frame)
        search_frame.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        search_frame.columnconfigure(1, weight=1)

        ttk.Label(search_frame, text="Filter:").grid(row=0, column=0, padx=(0, 5))
        self.search_var = tk.StringVar()
        search_entry = ttk.Entry(search_frame, textvariable=self.search_var)
        search_entry.grid(row=0, column=1, sticky="ew")
        self.search_var.trace_add("write", self._on_search_change)

        ttk.Label(main_frame, text="Saved Profiles:", font=('TkDefaultFont', 10, 'bold')).grid(row=1, column=0, pady=(0,5), sticky=tk.W)

        self.profile_listbox_widget = tk.Listbox(main_frame, height=10, exportselection=False)
        self.profile_listbox_widget.grid(row=2, column=0, sticky="nsew", pady=5)
        
        # --- Listbox Scrollbar ---
        listbox_scrollbar = ttk.Scrollbar(main_frame, orient="vertical", command=self.profile_listbox_widget.yview)
        listbox_scrollbar.grid(row=2, column=1, sticky="ns", pady=5)
        self.profile_listbox_widget.config(yscrollcommand=listbox_scrollbar.set)
        
        self._populate_profile_listbox() # Initial population

        buttons_frame = ttk.Frame(main_frame)
        buttons_frame.grid(row=3, column=0, columnspan=2, sticky="ew", pady=(5,0))

        self.load_button_widget = ttk.Button(buttons_frame, text="Load Selected", command=self._action_load_selected)
        self.load_button_widget.pack(side=tk.LEFT, padx=5)

        self.delete_button_widget = ttk.Button(buttons_frame, text="Delete Selected", command=self._action_delete_selected)
        self.delete_button_widget.pack(side=tk.LEFT, padx=5)

        close_button_widget = ttk.Button(buttons_frame, text="Close", command=self.destroy)
        close_button_widget.pack(side=tk.RIGHT, padx=5) # Align close to the right

        self._update_button_states() # Set initial button states

        # Set focus based on initial_action
        if initial_action == "delete" and self.profiles_dict:
            self.delete_button_widget.focus_set()
        elif self.profiles_dict: # Default to load if profiles exist
             self.load_button_widget.focus_set()

        # Bind double-click on listbox item to load action
        self.profile_listbox_widget.bind("<Double-1>", lambda e: self._action_load_selected())
        self.wait_window(self) # Wait for dialog to close

    def _on_search_change(self, *args):
        """Called when the user types in the search/filter entry box."""
        self._populate_profile_listbox()
        self._update_button_states()

    def _populate_profile_listbox(self):
        """Populates the listbox with profile names, applying the current search filter."""
        search_term = self.search_var.get().lower()
        self.profile_listbox_widget.delete(0, tk.END) # Clear existing items
        
        # Get and filter profile names based on the search term
        all_profile_names = sorted(self.profiles_dict.keys())
        filtered_names = [name for name in all_profile_names if search_term in name.lower()]

        selection_to_set_idx = -1 # To re-select the active profile if it's in the filtered list

        for idx, name in enumerate(filtered_names):
            display_name = name
            if name == self.current_active_profile_name: # Mark the active profile
                display_name += " (Active)"
                selection_to_set_idx = idx
            self.profile_listbox_widget.insert(tk.END, display_name)
        
        # If an active profile was found in the filtered list, select it.
        # Otherwise, select the first item if the filtered list is not empty.
        if selection_to_set_idx != -1:
             self.profile_listbox_widget.selection_set(selection_to_set_idx)
             self.profile_listbox_widget.see(selection_to_set_idx) # Ensure it's visible
        elif filtered_names: # If no active profile, but list has items, select first
            self.profile_listbox_widget.selection_set(0)
            self.profile_listbox_widget.see(0)


    def _update_button_states(self):
        # Disable load/delete if no profiles exist in the filtered list or none is selected
        has_selection = bool(self.profile_listbox_widget.curselection())
        has_profiles_in_list = self.profile_listbox_widget.size() > 0

        if has_profiles_in_list and has_selection:
            self.load_button_widget.config(state=tk.NORMAL)
            self.delete_button_widget.config(state=tk.NORMAL)
        else:
            self.load_button_widget.config(state=tk.DISABLED)
            self.delete_button_widget.config(state=tk.DISABLED)
        
        # Re-bind selection event to update button states dynamically
        # This ensures buttons enable/disable as user clicks items in the listbox
        self.profile_listbox_widget.bind("<<ListboxSelect>>", lambda e: self._update_button_states_on_select())

    def _update_button_states_on_select(self):
        # Simplified version for the <<ListboxSelect>> event
        has_selection = bool(self.profile_listbox_widget.curselection())
        if has_selection:
            self.load_button_widget.config(state=tk.NORMAL)
            self.delete_button_widget.config(state=tk.NORMAL)
        else:
            self.load_button_widget.config(state=tk.DISABLED)
            self.delete_button_widget.config(state=tk.DISABLED)


    def _get_actual_profile_name_from_listbox_selection(self):
        selection_indices = self.profile_listbox_widget.curselection()
        if not selection_indices: return None # No item selected
        
        selected_display_name = self.profile_listbox_widget.get(selection_indices[0])
        # Remove " (Active)" suffix to get the actual profile name
        actual_name = selected_display_name.replace(" (Active)", "").strip() 
        return actual_name

    def _action_load_selected(self):
        profile_name_to_load = self._get_actual_profile_name_from_listbox_selection()
        if profile_name_to_load and self.app_instance_ref:
            # Call the main app's method to handle profile loading logic
            if hasattr(self.app_instance_ref, '_execute_load_profile'):
                self.app_instance_ref._execute_load_profile(profile_name_to_load)
            self.destroy() # Close dialog after action
        elif not profile_name_to_load:
             messagebox.showwarning("No Selection", "Please select a profile to load.", parent=self)

    def _action_delete_selected(self):
        profile_name_to_delete = self._get_actual_profile_name_from_listbox_selection()
        if profile_name_to_delete:
            if messagebox.askyesno("Confirm Delete", f"Are you sure you want to delete profile '{profile_name_to_delete}'?", parent=self):
                if self.app_instance_ref and hasattr(self.app_instance_ref, '_execute_delete_profile'):
                    # _execute_delete_profile should return True if successful
                    if self.app_instance_ref._execute_delete_profile(profile_name_to_delete):
                        # Refresh local state from app instance after deletion
                        self.profiles_dict = self.app_instance_ref.profiles 
                        self.current_active_profile_name = self.app_instance_ref.active_profile_name
                        self._populate_profile_listbox() # Refresh the listbox with the current filter
                        self._update_button_states() # Update button states (e.g., if list becomes empty)
                        # Status update is handled by _execute_delete_profile in the main app
        elif not profile_name_to_delete: # No profile selected
            messagebox.showwarning("No Selection", "Please select a profile to delete.", parent=self)