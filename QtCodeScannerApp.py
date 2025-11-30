# CodebaseScanner/QtCodeScannerApp.py

import os
import sys
import fnmatch
import traceback
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QLineEdit, QPushButton, QFileDialog, QMessageBox, QCheckBox,
    QTreeWidget, QTreeWidgetItem, QHeaderView, QMenuBar, QStatusBar, QFrame,
    QInputDialog, QAbstractItemView, QTreeWidgetItemIterator, QGroupBox, QSplitter,
    QStyle
)
from PySide6.QtCore import QThread, QObject, Signal, Qt

# --- Local Module Imports ---
import app_config
import profile_handler
import rule_manager
import scan_engine
from dialogs_qt.QtEditDefaultsDialog import QtEditDefaultsDialog
from dialogs_qt.QtManageProfilesDialog import QtManageProfilesDialog

DARK_THEME_STYLESHEET = """
QWidget {
    background-color: #2e2e2e;
    color: #e0e0e0;
    font-size: 10pt;
}
QMainWindow, QDialog {
    background-color: #2e2e2e;
}
QGroupBox {
    background-color: #3c3c3c;
    border: 1px solid #555;
    border-radius: 6px;
    margin-top: 12px;
    font-weight: bold;
}
QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top center;
    padding: 2px 8px;
    background-color: #505050;
    border: 1px solid #555;
    border-radius: 6px;
}
QLineEdit, QTreeWidget, QListWidget {
    background-color: #252525;
    border: 1px solid #555;
    border-radius: 4px;
    padding: 5px;
    selection-background-color: #004080; /* Changed selection color */
    selection-color: #e0e0e0;
}
/* Added this new rule for the hover effect */
QTreeWidget::item:hover {
    background-color: #4a4a4a; 
}
QTreeWidget::item:selected {
    background-color: #0050a0; /* This color will always show for selected items */
    color: white;
}
QPushButton {
    background-color: #555;
    border: 1px solid #666;
    padding: 6px 12px;
    border-radius: 4px;
    min-height: 20px;
}
QPushButton:hover {
    background-color: #666;
    border-color: #777;
}
QPushButton:pressed {
    background-color: #444;
}
QPushButton:disabled {
    background-color: #404040;
    color: #888;
}
QCheckBox {
    spacing: 8px;
}
QCheckBox::indicator {
    width: 18px;
    height: 18px;
}
QMenuBar {
    background-color: #3c3c3c;
}
QMenuBar::item {
    background-color: transparent;
    padding: 4px 8px;
}
QMenuBar::item:selected {
    background-color: #555;
}
QMenu {
    background-color: #3c3c3c;
    border: 1px solid #555;
}
QMenu::item:selected {
    background-color: #555;
}
QHeaderView::section {
    background-color: #3c3c3c;
    padding: 6px;
    border: 1px solid #555;
    font-weight: bold;
}
QStatusBar {
    background-color: #3c3c3c;
    font-weight: bold;
}
QSplitter::handle {
    background-color: #3c3c3c;
    border: 1px solid #555;
}
QSplitter::handle:vertical {
    height: 8px;
}
QSplitter::handle:hover {
    background-color: #555;
}
"""

class ScanWorker(QObject):
    """Worker object to run the scan in a separate thread."""
    status_update = Signal(str)
    scan_finished = Signal(str)
    scan_error = Signal(str, str)

    def __init__(self, scan_params):
        super().__init__()
        self.scan_params = scan_params

    def run(self):
        try:
            p = self.scan_params
            scan_dir_norm = p['scan_dir_norm']
            save_path_norm = p['save_path_norm']
            rules_files = p['rules_files']
            rules_folders = p['rules_folders']
            filter_mode = p['filter_mode']
            rules_path_display = p['rules_path_display']
            rules_dirty = p['rules_dirty']
            generate_tree = p['generate_tree']
            tree_blacklist = p['tree_blacklist']

            with open(save_path_norm, "w", encoding="utf-8") as output_file:
                if generate_tree:
                    self.status_update.emit("Generating directory tree...")
                    tree_header = f"# Directory Tree for: {os.path.basename(scan_dir_norm)}\n\n"
                    normalized_tree_blacklist = [os.path.normpath(p) for p in tree_blacklist]
                    tree_structure = scan_engine.generate_directory_tree_text(scan_dir_norm, normalized_tree_blacklist)
                    output_file.write(tree_header)
                    output_file.write(tree_structure or f"{os.path.basename(scan_dir_norm)}/\n (No subdirectories found or all were blacklisted)\n")
                    output_file.write("\n\n---\n\n")

                output_file.write(f"# Codebase Scan: {os.path.basename(scan_dir_norm)}\n\n")
                mode_desc = "Whitelist (Including only listed paths)" if filter_mode == app_config.FILTER_WHITELIST else "Blacklist (Excluding listed paths)"
                output_file.write(f"**Mode:** `{mode_desc}`\n")

                rules_source_display = ""
                if rules_path_display:
                    rules_source_display = f"`{os.path.basename(rules_path_display)}` (from `{rules_path_display}`)"
                    if rules_dirty:
                        rules_source_display += " - with unsaved modifications in GUI"
                else:
                    rules_source_display = "`Current GUI rules (No file or unsaved changes to a file)`"
                output_file.write(f"**Rules From:** {rules_source_display}\n\n")

                initial_whitelisted_ancestors = []
                if filter_mode == app_config.FILTER_WHITELIST and scan_dir_norm in rules_folders:
                    initial_whitelisted_ancestors.append(scan_dir_norm)

                scan_engine.process_directory(
                    scan_dir_norm, output_file, rules_files, rules_folders,
                    filter_mode, level=0, status_callback=self.status_update.emit,
                    whitelisted_ancestor_folders=initial_whitelisted_ancestors
                )
            
            self.scan_finished.emit(save_path_norm)
        except Exception as e:
            tb_str = traceback.format_exc()
            self.scan_error.emit(str(e), tb_str)


class CodeScannerApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Codebase Scanner")
        self.setMinimumSize(800, 700)
        self.resize(1100, 850)

        # --- Application State Variables ---
        self.current_rules_filepath = ""
        self.filter_mode = app_config.FILTER_BLACKLIST
        
        self.rules_files = []
        self.rules_folders = []
        self.rules_dirty = False

        self.directory_tree_blacklist = []
        self.directory_tree_blacklist_dirty = False
        
        self.default_ignore_patterns = {'file': [], 'folder': []}
        
        self.profiles, self.last_active_profile_name = profile_handler.load_profiles(app_config.PROFILES_PATH)
        self.active_profile_name = None

        self._setup_ui()
        self._configure_fields_from_initial_profile()
        
        if self.active_profile_name:
            self._update_status(f"Profile '{self.active_profile_name}' loaded. Ready.")
        else:
            self._update_status("Ready. Configure manually or load a profile.")
        self._update_window_title()

    def _setup_ui(self):
        self.setStyleSheet(DARK_THEME_STYLESHEET)
        self._setup_menu()
        
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        
        main_layout = QVBoxLayout(main_widget)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(10)

        # --- Top Configuration Area ---
        top_config_widget = QWidget()
        top_config_layout = QVBoxLayout(top_config_widget)
        top_config_layout.setContentsMargins(0,0,0,0)
        top_config_layout.setSpacing(10)

        # --- Core Paths Group ---
        core_paths_group = QGroupBox("Core Paths")
        core_paths_layout = QGridLayout(core_paths_group)
        
        core_paths_layout.addWidget(QLabel("Scan Directory:"), 0, 0)
        self.scan_dir_entry = QLineEdit()
        scan_dir_btn = QPushButton("Browse...")
        scan_dir_btn.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_DirIcon))
        scan_dir_layout = QHBoxLayout()
        scan_dir_layout.addWidget(self.scan_dir_entry)
        scan_dir_layout.addWidget(scan_dir_btn)
        core_paths_layout.addLayout(scan_dir_layout, 0, 1)

        core_paths_layout.addWidget(QLabel("Save Output As:"), 1, 0)
        self.save_path_entry = QLineEdit()
        save_path_btn = QPushButton("Browse...")
        save_path_btn.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_DirIcon))
        save_path_layout = QHBoxLayout()
        save_path_layout.addWidget(self.save_path_entry)
        save_path_layout.addWidget(save_path_btn)
        core_paths_layout.addLayout(save_path_layout, 1, 1)
        core_paths_layout.setColumnStretch(1, 1)

        # --- Rules Configuration Group ---
        rules_config_group = QGroupBox("Rules Configuration")
        rules_config_layout = QGridLayout(rules_config_group)

        rules_config_layout.addWidget(QLabel("Rules File (.scanIgnore):"), 0, 0)
        self.rules_dir_entry = QLineEdit()
        self.rules_dir_entry.setReadOnly(True)
        rules_dir_btn = QPushButton("Browse...")
        rules_dir_btn.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_DirIcon))
        rules_dir_btn.setToolTip("Select a directory. The app will find or create a .scanIgnore file within it.")
        rules_dir_layout = QHBoxLayout()
        rules_dir_layout.addWidget(self.rules_dir_entry)
        rules_dir_layout.addWidget(rules_dir_btn)
        rules_config_layout.addLayout(rules_dir_layout, 0, 1)

        rules_buttons_layout = QHBoxLayout()
        rules_buttons_layout.addStretch()
        edit_defaults_btn = QPushButton("Edit Default Name Patterns")
        edit_defaults_btn.setToolTip(f"Open editor for {os.path.basename(app_config.DEFAULT_IGNORE_PATH)} which uses name-based patterns (not full paths).")
        save_rules_btn = QPushButton("Save Rules List")
        save_rules_btn.setToolTip("Save current path-based rules to the .scanIgnore file in the selected rules directory.")
        rules_buttons_layout.addWidget(edit_defaults_btn)
        rules_buttons_layout.addWidget(save_rules_btn)
        rules_config_layout.addLayout(rules_buttons_layout, 1, 1)
        rules_config_layout.setColumnStretch(1, 1)

        # --- Scan Options Group ---
        scan_options_group = QGroupBox("Scan Options")
        scan_options_layout = QHBoxLayout(scan_options_group)
        self.filter_mode_check = QCheckBox("Whitelist Mode (Include Only Listed Paths)")
        self.generate_tree_check = QCheckBox("Generate Directory Tree in Output")
        scan_options_layout.addWidget(self.filter_mode_check)
        scan_options_layout.addWidget(self.generate_tree_check)
        scan_options_layout.addStretch()
        
        top_config_layout.addWidget(core_paths_group)
        top_config_layout.addWidget(rules_config_group)
        top_config_layout.addWidget(scan_options_group)

        # --- File Explorer ---
        tree_explorer_frame = self._setup_tree_explorer_ui()
        
        # --- Splitter ---
        splitter = QSplitter(Qt.Orientation.Vertical)
        splitter.addWidget(top_config_widget)
        splitter.addWidget(tree_explorer_frame)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([300, 500])

        # --- Run Button ---
        self.run_scan_btn = QPushButton("Run Scan")
        self.run_scan_btn.setStyleSheet("font-size: 12pt; font-weight: bold; padding: 12px 24px;")
        run_button_layout = QHBoxLayout()
        run_button_layout.addStretch()
        run_button_layout.addWidget(self.run_scan_btn)
        run_button_layout.addStretch()
        
        # --- Status Bar ---
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)

        # --- Layout Assembly ---
        main_layout.addWidget(splitter)
        main_layout.addLayout(run_button_layout)

        # --- Connections ---
        scan_dir_btn.clicked.connect(self._browse_scan_directory)
        save_path_btn.clicked.connect(self._browse_save_file)
        rules_dir_btn.clicked.connect(self._browse_rules_directory)
        edit_defaults_btn.clicked.connect(self._edit_defaults_dialog)
        save_rules_btn.clicked.connect(self._save_rules_list_changes)
        
        self.filter_mode_check.stateChanged.connect(self._on_filter_mode_change)
        self.generate_tree_check.stateChanged.connect(self._on_generate_tree_toggle)
        
        self.run_scan_btn.clicked.connect(self._run_scan)

    def _setup_menu(self):
        menubar = self.menuBar()
        profile_menu = menubar.addMenu("Profiles")
        
        self.update_profile_action = profile_menu.addAction("Update Current Profile", self._update_current_profile)
        profile_menu.addAction("Save Profile As...", self._save_profile_dialog)
        profile_menu.addSeparator()
        profile_menu.addAction("Manage Profiles...", self._manage_profiles_dialog)
    
    def _setup_tree_explorer_ui(self):
        tree_frame = QFrame()
        tree_frame.setFrameShape(QFrame.Shape.StyledPanel)
        tree_layout = QVBoxLayout(tree_frame)
        tree_layout.setContentsMargins(10, 10, 10, 10)
        tree_layout.setSpacing(8)

        controls_layout = QHBoxLayout()
        load_tree_btn = QPushButton("Load/Refresh Directory Tree")
        load_tree_btn.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_BrowserReload))
        load_tree_btn.setToolTip("Load the file structure from the 'Scan Directory' into the explorer below.")
        controls_layout.addWidget(load_tree_btn)
        controls_layout.addStretch()
        tree_layout.addLayout(controls_layout)

        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["Name", "Scan Rule Applied", "Tree Blacklist Applied"])
        self.tree.header().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.tree.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        tree_layout.addWidget(self.tree)

        apply_rules_layout = QHBoxLayout()
        apply_rules_layout.setSpacing(8)
        self.add_scan_rule_btn = QPushButton("Apply Scan Rule")
        self.add_scan_rule_btn.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_DialogApplyButton))
        remove_scan_rule_btn = QPushButton("Remove Scan Rule")
        remove_scan_rule_btn.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_DialogCancelButton))
        add_tree_blacklist_btn = QPushButton("Apply Tree Blacklist")
        add_tree_blacklist_btn.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_DialogApplyButton))
        add_tree_blacklist_btn.setToolTip("Exclude selected folders from the generated directory tree output.")
        remove_tree_blacklist_btn = QPushButton("Remove from Tree Blacklist")
        remove_tree_blacklist_btn.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_DialogCancelButton))
        
        apply_rules_layout.addWidget(self.add_scan_rule_btn)
        apply_rules_layout.addWidget(remove_scan_rule_btn)
        apply_rules_layout.addSpacing(20)
        apply_rules_layout.addWidget(add_tree_blacklist_btn)
        apply_rules_layout.addWidget(remove_tree_blacklist_btn)
        apply_rules_layout.addStretch()
        tree_layout.addLayout(apply_rules_layout)
        
        # Connections
        load_tree_btn.clicked.connect(self._populate_tree_view)
        self.tree.itemExpanded.connect(self._on_tree_item_expanded)
        self.add_scan_rule_btn.clicked.connect(lambda: self._apply_rules_to_selection('scan_rule', 'add'))
        remove_scan_rule_btn.clicked.connect(lambda: self._apply_rules_to_selection('scan_rule', 'remove'))
        add_tree_blacklist_btn.clicked.connect(lambda: self._apply_rules_to_selection('tree_blacklist', 'add'))
        remove_tree_blacklist_btn.clicked.connect(lambda: self._apply_rules_to_selection('tree_blacklist', 'remove'))

        return tree_frame

    # --- UI State and Data Handling ---

    def _configure_fields_from_initial_profile(self):
        profile_to_load = self.profiles.get(self.last_active_profile_name)
        if profile_to_load:
            self._apply_profile_settings(self.last_active_profile_name)
        else:
            self.scan_dir_entry.setText("")
            self.save_path_entry.setText(os.path.join(os.path.expanduser("~"), app_config.DEFAULT_OUTPUT_FILENAME))
            self.rules_dir_entry.setText("")
            self.current_rules_filepath = ""
            self.filter_mode_check.setChecked(False)
            self.directory_tree_blacklist = []
            self.generate_tree_check.setChecked(True)
            self.active_profile_name = None

        self.directory_tree_blacklist_dirty = False
        self.rules_dirty = False
        self._update_profile_menu_state()
        self._on_filter_mode_change() # To set initial state
    
    def _update_status(self, message, clear_after_ms=None):
        self.status_bar.showMessage(message, clear_after_ms or 0)

    def _update_window_title(self):
        title = "Codebase Scanner"
        if self.active_profile_name:
            dirty_indicator = "*" if self.rules_dirty or self.directory_tree_blacklist_dirty else ""
            title += f" - Profile: {self.active_profile_name}{dirty_indicator}"
        elif self.rules_dirty or self.directory_tree_blacklist_dirty:
            title += " - Unsaved Changes*"
        self.setWindowTitle(title)
        
    def _update_profile_menu_state(self):
        self.update_profile_action.setEnabled(bool(self.active_profile_name))

    def _set_dirty_flags_and_update_title(self, rules_dirty=None, tree_dirty=None):
        if rules_dirty is not None:
            self.rules_dirty = rules_dirty
        if tree_dirty is not None:
            self.directory_tree_blacklist_dirty = tree_dirty
        self._update_window_title()

    # --- Event Handlers / Slots ---

    def _on_filter_mode_change(self):
        is_whitelist = self.filter_mode_check.isChecked()
        self.filter_mode = app_config.FILTER_WHITELIST if is_whitelist else app_config.FILTER_BLACKLIST
        mode_text = "Whitelist" if is_whitelist else "Blacklist"
        action_text = "include in" if is_whitelist else "exclude from"
        self._update_status(f"Filter mode changed to {mode_text}.", clear_after_ms=4000)
        self.add_scan_rule_btn.setToolTip(f"Mark selected items to {action_text} the scan.")
    
    def _on_generate_tree_toggle(self):
        if self.active_profile_name:
            self._set_dirty_flags_and_update_title(tree_dirty=True)
        self._update_status(f"Directory tree generation set to: {self.generate_tree_check.isChecked()}", clear_after_ms=3000)

    # --- File/Directory Browsing ---

    def _browse_scan_directory(self):
        directory = QFileDialog.getExistingDirectory(self, "Select Directory to Scan", self.scan_dir_entry.text() or os.path.expanduser("~"))
        if directory:
            self.scan_dir_entry.setText(os.path.normpath(directory))
            self._populate_tree_view()
    
    def _browse_save_file(self):
        initial_dir = os.path.dirname(self.save_path_entry.text()) or self.scan_dir_entry.text() or os.path.expanduser("~")
        filepath, _ = QFileDialog.getSaveFileName(self, "Save Scan Output As", os.path.join(initial_dir, app_config.DEFAULT_OUTPUT_FILENAME), "Text Files (*.txt);;Markdown Files (*.md);;All Files (*.*)")
        if filepath:
            self.save_path_entry.setText(os.path.normpath(filepath))

    def _browse_rules_directory(self):
        initial_dir = self.rules_dir_entry.text() or self.scan_dir_entry.text() or os.path.expanduser("~")
        directory = QFileDialog.getExistingDirectory(self, "Select Rules Directory", initial_dir)
        if not directory: return
        
        norm_dir = os.path.normpath(directory)
        if norm_dir == self.rules_dir_entry.text(): return

        if self.rules_dirty:
            reply = QMessageBox.question(self, "Unsaved Changes", "You have unsaved scan rule changes. Discard them and switch to the new directory?", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No)
            if reply == QMessageBox.StandardButton.No:
                return
        
        self._set_rules_directory_and_load(norm_dir, prompt_create=True)

    # --- Profile Management ---

    def _update_current_profile(self):
        if not self.active_profile_name: return
        reply = QMessageBox.question(self, "Confirm Update", f"Update profile '{self.active_profile_name}' with the current settings?", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.No: return
        
        if self._save_profile(self.active_profile_name):
            self._update_status(f"Profile '{self.active_profile_name}' updated successfully.", clear_after_ms=4000)

    def _save_profile_dialog(self):
        profile_name, ok = QInputDialog.getText(self, "Save Profile As", "Enter a new profile name:")
        if ok and profile_name:
            clean_name = "".join(c for c in profile_name if c.isalnum() or c in (' ', '_', '-')).strip()
            if not clean_name:
                QMessageBox.warning(self, "Invalid Name", "Profile name cannot be empty or only special characters.")
                return

            if clean_name in self.profiles:
                reply = QMessageBox.question(self, "Overwrite Profile", f"Profile '{clean_name}' already exists. Overwrite?", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
                if reply == QMessageBox.StandardButton.No: return
            
            if self._save_profile(clean_name):
                self._update_status(f"Profile '{clean_name}' saved.", clear_after_ms=3000)

    def _save_profile(self, profile_name):
        scan_dir = self.scan_dir_entry.text()
        save_fp = self.save_path_entry.text()
        if not scan_dir or not os.path.isdir(scan_dir):
            QMessageBox.warning(self, "Incomplete Configuration", "Scan directory must be a valid directory."); return False
        if not save_fp:
            QMessageBox.warning(self, "Incomplete Configuration", "Save output path must be set."); return False

        if self.rules_dirty and self.current_rules_filepath:
            reply = QMessageBox.question(self, "Unsaved Rules", "The current scan rules have unsaved changes. Save them before saving the profile?", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No | QMessageBox.StandardButton.Cancel)
            if reply == QMessageBox.StandardButton.Yes:
                if not self._save_rules_list_changes(): return False # Save failed
            elif reply == QMessageBox.StandardButton.Cancel:
                return False
        
        self.profiles[profile_name] = {
            "scan_directory": os.path.normpath(scan_dir),
            "save_filepath": os.path.normpath(save_fp),
            "rules_directory": os.path.normpath(self.rules_dir_entry.text()) if self.rules_dir_entry.text() else "",
            "rules_filepath": os.path.normpath(self.current_rules_filepath) if self.current_rules_filepath else "",
            "filter_mode": self.filter_mode,
            "directory_tree_blacklist": list(self.directory_tree_blacklist),
            "generate_directory_tree": self.generate_tree_check.isChecked()
        }
        self.active_profile_name = profile_name
        self.last_active_profile_name = profile_name

        try:
            profile_handler.save_profiles(self.profiles, self.last_active_profile_name, app_config.PROFILES_PATH)
            self._set_dirty_flags_and_update_title(rules_dirty=False, tree_dirty=False)
            self._update_profile_menu_state()
            return True
        except Exception as e:
            QMessageBox.critical(self, "Profile Save Error", f"Could not save profiles: {e}")
            return False

    def _manage_profiles_dialog(self):
        dialog = QtManageProfilesDialog(self, self.profiles, self.active_profile_name, self)
        dialog.exec()
    
    def _execute_load_profile(self, profile_name):
        return self._apply_profile_settings(profile_name, persist_last_active=True)

    def _apply_profile_settings(self, profile_name, persist_last_active=False):
        profile_data = self.profiles.get(profile_name)
        if not profile_data:
            QMessageBox.critical(self, "Error", f"Profile '{profile_name}' not found.")
            return False

        if self.rules_dirty:
            reply = QMessageBox.question(self, "Unsaved Changes", "You have unsaved changes in the current scan rules list. Discard these changes and load the profile?", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No)
            if reply == QMessageBox.StandardButton.No:
                self._update_status(f"Profile '{profile_name}' load cancelled.", clear_after_ms=3000)
                return False

        self.scan_dir_entry.setText(profile_data.get("scan_directory", ""))
        self.save_path_entry.setText(profile_data.get("save_filepath", os.path.join(os.path.expanduser("~"), app_config.DEFAULT_OUTPUT_FILENAME)))
        self.filter_mode_check.setChecked(profile_data.get("filter_mode", app_config.FILTER_BLACKLIST) == app_config.FILTER_WHITELIST)
        self.directory_tree_blacklist = list(profile_data.get("directory_tree_blacklist", []))
        self.generate_tree_check.setChecked(profile_data.get("generate_directory_tree", True))
        
        self._set_rules_directory_and_load(profile_data.get("rules_directory", ""))
        
        self._set_dirty_flags_and_update_title(rules_dirty=False, tree_dirty=False)
        
        if self.scan_dir_entry.text() and os.path.isdir(self.scan_dir_entry.text()):
            self._populate_tree_view()
        else:
            self.tree.clear()

        self.active_profile_name = profile_name
        if persist_last_active:
            self.last_active_profile_name = profile_name
            try:
                profile_handler.save_profiles(self.profiles, self.last_active_profile_name, app_config.PROFILES_PATH)
            except Exception as e:
                QMessageBox.critical(self, "Profile Save Error", f"Could not persist last active profile setting: {e}")

        self._update_window_title()
        self._update_profile_menu_state()
        self._on_filter_mode_change() # Update UI elements based on new mode
        self._update_status(f"Profile '{profile_name}' loaded.", clear_after_ms=3000)
        return True

    def _execute_delete_profile(self, profile_name):
        if profile_name in self.profiles:
            del self.profiles[profile_name]
            was_active = self.active_profile_name == profile_name
            if self.last_active_profile_name == profile_name:
                self.last_active_profile_name = None
            if was_active:
                self.active_profile_name = None
                self._configure_fields_from_initial_profile() # Reset to defaults
            try:
                profile_handler.save_profiles(self.profiles, self.last_active_profile_name, app_config.PROFILES_PATH)
                self._update_status(f"Profile '{profile_name}' deleted.", clear_after_ms=3000)
                self._update_window_title()
                self._update_profile_menu_state()
                return True
            except Exception as e:
                QMessageBox.critical(self, "Profile Save Error", f"Could not save profile changes after deletion: {e}")
        return False

    # --- Rule Management ---

    def _edit_defaults_dialog(self):
        dialog = QtEditDefaultsDialog(self, app_config.DEFAULT_IGNORE_PATH, self)
        dialog.exec()
    
    def _set_rules_directory_and_load(self, dir_path, prompt_create=False):
        if not dir_path or not os.path.isdir(dir_path):
            self.rules_dir_entry.setText("")
            self.current_rules_filepath = ""
            self._load_rules_from_file()
            return
        
        self.rules_dir_entry.setText(dir_path)
        rules_file = os.path.join(dir_path, ".scanIgnore")
        
        if os.path.isfile(rules_file):
            self.current_rules_filepath = rules_file
        else:
            create = False
            if prompt_create:
                reply = QMessageBox.question(self, "Create Rules File?", f"The file '.scanIgnore' does not exist in:\n{dir_path}\n\nDo you want to create it?", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
                if reply == QMessageBox.StandardButton.Yes: create = True
            
            if create:
                # rule_manager now returns False on error without showing its own message box
                if rule_manager.create_empty_file(rules_file, is_rules_file=True):
                    self.current_rules_filepath = rules_file
                else: 
                    self.current_rules_filepath = ""
                    QMessageBox.critical(self, "File Creation Error", f"Could not create the rules file at:\n{rules_file}")
            else:
                self.current_rules_filepath = ""
        
        self._load_rules_from_file()
    
    def _load_rules_from_file(self):
        if not self.current_rules_filepath:
            self.rules_files, self.rules_folders = [], []
        else:
            try:
                self.rules_files, self.rules_folders = rule_manager.load_ignore_rules(self.current_rules_filepath)
                self._update_status(f"Loaded rules from {os.path.basename(self.current_rules_filepath)}", clear_after_ms=3000)
            except Exception as e:
                QMessageBox.critical(self, "Load Error", f"Could not load scan rules from {os.path.basename(self.current_rules_filepath)}:\n{e}")
                self.rules_files, self.rules_folders = [], []

        self._set_dirty_flags_and_update_title(rules_dirty=False)
        self._update_all_tree_visuals()

    def _save_rules_list_changes(self):
        path_to_save = self.current_rules_filepath
        if not path_to_save and self.rules_dir_entry.text():
            reply = QMessageBox.question(self, "Create and Save?", f"Create and save rules to '.scanIgnore' in the current rules directory?", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            if reply == QMessageBox.StandardButton.Yes:
                path_to_save = os.path.join(self.rules_dir_entry.text(), ".scanIgnore")
                self.current_rules_filepath = path_to_save
            else: return False
        elif not path_to_save:
            QMessageBox.critical(self, "Save Error", "No valid rules directory is selected.")
            return False

        if not self.rules_dirty:
            self._update_status("No unsaved changes to save.", clear_after_ms=3000)
            return True

        try:
            rule_manager.save_ignore_rules(path_to_save, self.rules_files, self.rules_folders)
            self._set_dirty_flags_and_update_title(rules_dirty=False)
            self._update_status(f"Saved scan rules to {os.path.basename(path_to_save)}", clear_after_ms=3000)
            return True
        except Exception as e:
            QMessageBox.critical(self, "Save Error", f"Could not save scan rules:\n{e}")
            return False

    # --- Tree View Logic ---
    
    def _load_default_ignore_patterns(self):
        self.default_ignore_patterns = {'file': [], 'folder': []}
        try:
            with open(app_config.DEFAULT_IGNORE_PATH, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#"): continue
                    if line.lower().startswith("file:"):
                        self.default_ignore_patterns['file'].append(line[len("file:"):].strip())
                    elif line.lower().startswith("folder:"):
                        self.default_ignore_patterns['folder'].append(line[len("folder:"):].strip())
        except Exception as e:
            self._update_status(f"Warning: Could not load default ignore patterns: {e}", clear_after_ms=4000)

    def _populate_tree_view(self):
        scan_dir = self.scan_dir_entry.text()
        if not scan_dir or not os.path.isdir(scan_dir):
            QMessageBox.critical(self, "Input Error", "Please select a valid directory to scan first.")
            return
        
        self.tree.clear()
        self._load_default_ignore_patterns()
        self._update_status("Loading directory tree...")

        root_item = QTreeWidgetItem(self.tree, [f"📁 {os.path.basename(scan_dir)}"])
        root_item.setData(0, Qt.ItemDataRole.UserRole, (scan_dir, True))
        root_item.setExpanded(True)
        self._populate_children(root_item)
        self._update_tree_visuals_for_items([root_item])
        self._update_status("Directory tree loaded.", clear_after_ms=4000)

    def _populate_children(self, parent_item):
        parent_path, _ = parent_item.data(0, Qt.ItemDataRole.UserRole)
        try:
            entries = os.scandir(parent_path)
        except OSError:
            return

        dirs_to_add, files_to_add = [], []
        for entry in entries:
            patterns = self.default_ignore_patterns['folder'] if entry.is_dir() else self.default_ignore_patterns['file']
            if not any(fnmatch.fnmatch(entry.name, p) for p in patterns):
                (dirs_to_add if entry.is_dir() else files_to_add).append(entry)
        
        dirs_to_add.sort(key=lambda e: e.name.lower())
        files_to_add.sort(key=lambda e: e.name.lower())
        
        items_to_update = []
        for entry in dirs_to_add:
            item = QTreeWidgetItem(parent_item, [f"📁 {entry.name}"])
            item.setData(0, Qt.ItemDataRole.UserRole, (entry.path, True))
            QTreeWidgetItem(item, ["..."]) # Placeholder for expansion
            items_to_update.append(item)
        for entry in files_to_add:
            item = QTreeWidgetItem(parent_item, [f"📄 {entry.name}"])
            item.setData(0, Qt.ItemDataRole.UserRole, (entry.path, False))
            items_to_update.append(item)
        
        if items_to_update:
            self._update_tree_visuals_for_items(items_to_update)

    def _on_tree_item_expanded(self, item):
        if item.childCount() == 1 and item.child(0).text(0) == "...":
            item.takeChild(0) # Remove placeholder
            self._populate_children(item)

    def _get_item_and_all_descendants(self, start_item):
        """Iteratively collects a start item and all its descendants."""
        items_to_collect = set()
        # A stack for non-recursive traversal
        stack = [start_item]
        while stack:
            current_item = stack.pop()
            items_to_collect.add(current_item)
            for i in range(current_item.childCount()):
                stack.append(current_item.child(i))
        return items_to_collect

    def _apply_rules_to_selection(self, rule_type, action):
        selected_items = self.tree.selectedItems()
        if not selected_items: return
        
        items_to_process = set()
        for item in selected_items:
            # Collect the selected item and all its descendants.
            # This corrects a bug where iterating would continue to the item's siblings.
            items_to_process.update(self._get_item_and_all_descendants(item))
        
        for item in items_to_process:
            data = item.data(0, Qt.ItemDataRole.UserRole)
            # FIX: Check if data exists. Placeholder items ('...') won't have data.
            if not data:
                continue
            full_path, is_dir = data

            if rule_type == 'scan_rule':
                target_list = self.rules_folders if is_dir else self.rules_files
                if action == 'add' and full_path not in target_list: target_list.append(full_path)
                elif action == 'remove' and full_path in target_list: target_list.remove(full_path)
                self._set_dirty_flags_and_update_title(rules_dirty=True)
            elif rule_type == 'tree_blacklist' and is_dir:
                if action == 'add' and full_path not in self.directory_tree_blacklist: self.directory_tree_blacklist.append(full_path)
                elif action == 'remove' and full_path in self.directory_tree_blacklist: self.directory_tree_blacklist.remove(full_path)
                self._set_dirty_flags_and_update_title(tree_dirty=True)
        
        self._update_tree_visuals_for_items(items_to_process)

    def _update_tree_visuals_for_items(self, items):
        for item in items:
            data = item.data(0, Qt.ItemDataRole.UserRole)
            # FIX: Check if data exists. Placeholder items ('...') won't have data.
            if not data:
                continue
            full_path, is_dir = data
            
            is_scan_rule_applied = (full_path in self.rules_folders) if is_dir else (full_path in self.rules_files)
            item.setText(1, "✓" if is_scan_rule_applied else "")
            
            is_blacklisted = is_dir and full_path in self.directory_tree_blacklist
            item.setText(2, "✓" if is_blacklisted else "")
    
    def _update_all_tree_visuals(self):
        if self.tree.topLevelItemCount() == 0: return
        all_items = []
        iterator = QTreeWidgetItemIterator(self.tree)
        while iterator.value():
            all_items.append(iterator.value())
            iterator += 1
        self._update_tree_visuals_for_items(all_items)

    # --- Scan Execution ---

    def _run_scan(self):
        scan_dir = self.scan_dir_entry.text()
        save_path = self.save_path_entry.text()
        if not scan_dir or not os.path.isdir(scan_dir):
            QMessageBox.critical(self, "Input Error", "Please select a valid directory to scan.")
            return
        if not save_path:
            QMessageBox.critical(self, "Input Error", "Please select a valid output file path.")
            return
        
        save_dir = os.path.dirname(save_path)
        if save_dir and not os.path.exists(save_dir):
            try: os.makedirs(save_dir, exist_ok=True)
            except Exception as e:
                QMessageBox.critical(self, "Input Error", f"Could not create save directory:\n{save_dir}\nError: {e}")
                return
        
        self.run_scan_btn.setEnabled(False)
        self._update_status("Starting scan...")

        scan_params = {
            'scan_dir_norm': os.path.normpath(scan_dir),
            'save_path_norm': os.path.normpath(save_path),
            'rules_files': list(self.rules_files),
            'rules_folders': list(self.rules_folders),
            'filter_mode': self.filter_mode,
            'rules_path_display': self.current_rules_filepath,
            'rules_dirty': self.rules_dirty,
            'generate_tree': self.generate_tree_check.isChecked(),
            'tree_blacklist': list(self.directory_tree_blacklist)
        }
        
        self.thread = QThread()
        self.worker = ScanWorker(scan_params)
        self.worker.moveToThread(self.thread)
        
        self.thread.started.connect(self.worker.run)
        self.worker.scan_finished.connect(self._on_scan_complete)
        self.worker.scan_error.connect(self._on_scan_error)
        self.worker.status_update.connect(self._update_status)
        
        self.worker.scan_finished.connect(self.thread.quit)
        self.worker.scan_error.connect(self.thread.quit)
        self.thread.finished.connect(self.worker.deleteLater)
        self.thread.finished.connect(self.thread.deleteLater)
        
        self.thread.start()

    def _on_scan_complete(self, save_path):
        self.run_scan_btn.setEnabled(True)
        self._update_status(f"Scan complete. Output saved to: {save_path}", 10000)
        QMessageBox.information(self, "Scan Complete", f"Output successfully saved to:\n{save_path}")

    def _on_scan_error(self, error_msg, traceback_str):
        self.run_scan_btn.setEnabled(True)
        self._update_status(f"Error during scan: {error_msg}", 10000)
        print(f"Full scan error details: {traceback_str}")
        QMessageBox.critical(self, "Scan Error", f"An error occurred: {error_msg}\nSee console for more details.")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    # The stylesheet is set on the app instance for global application
    app.setStyleSheet(DARK_THEME_STYLESHEET)
    window = CodeScannerApp()
    window.show()
    sys.exit(app.exec())