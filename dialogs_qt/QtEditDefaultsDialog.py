# CodebaseScanner/dialogs_qt/QtEditDefaultsDialog.py

import os
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLineEdit, QPushButton,
    QListWidget, QListWidgetItem, QLabel, QMessageBox, QDialogButtonBox,
    QFrame, QAbstractItemView
)
from PySide6.QtCore import Qt

class QtEditDefaultsDialog(QDialog):
    def __init__(self, parent, default_filepath_param, app_instance):
        super().__init__(parent)
        self.default_filepath = default_filepath_param
        self.app_instance = app_instance

        self.setWindowTitle(f"Edit Default Name Patterns ({os.path.basename(self.default_filepath)})")
        self.setMinimumSize(600, 500)

        self.dialog_rule_file_patterns = []
        self.dialog_rule_folder_patterns = []

        # --- Layouts ---
        main_layout = QVBoxLayout(self)
        input_layout = QHBoxLayout()
        lists_layout = QHBoxLayout()
        file_list_layout = QVBoxLayout()
        folder_list_layout = QVBoxLayout()

        # --- Input Widgets ---
        self.pattern_entry = QLineEdit()
        self.pattern_entry.setPlaceholderText("Enter a name or pattern (e.g., '*.log')")
        self.pattern_entry.setToolTip("Enter a file/folder name or simple pattern (e.g., '*.log', 'temp_folder') to add to defaults.")
        
        add_file_btn = QPushButton("Add File Pattern")
        add_folder_btn = QPushButton("Add Folder Pattern")

        input_layout.addWidget(self.pattern_entry)
        input_layout.addWidget(add_file_btn)
        input_layout.addWidget(add_folder_btn)

        # --- List Widgets ---
        file_list_layout.addWidget(QLabel("File Name Patterns:"))
        self.file_list_widget = QListWidget()
        self.file_list_widget.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        file_list_layout.addWidget(self.file_list_widget)
        remove_file_btn = QPushButton("Remove Selected File Pattern(s)")
        file_list_layout.addWidget(remove_file_btn)
        
        folder_list_layout.addWidget(QLabel("Folder Name Patterns:"))
        self.folder_list_widget = QListWidget()
        self.folder_list_widget.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        folder_list_layout.addWidget(self.folder_list_widget)
        remove_folder_btn = QPushButton("Remove Selected Folder Pattern(s)")
        folder_list_layout.addWidget(remove_folder_btn)
        
        lists_layout.addLayout(file_list_layout)
        lists_layout.addLayout(folder_list_layout)

        # --- Dialog Buttons (Save/Cancel) ---
        self.button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)

        # --- Assembly ---
        main_layout.addLayout(input_layout)
        
        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.HLine)
        separator.setFrameShadow(QFrame.Shadow.Sunken)
        main_layout.addWidget(separator)
        
        main_layout.addLayout(lists_layout)
        main_layout.addWidget(self.button_box)

        # --- Connections ---
        add_file_btn.clicked.connect(lambda: self._add_name_pattern('file'))
        add_folder_btn.clicked.connect(lambda: self._add_name_pattern('folder'))
        remove_file_btn.clicked.connect(lambda: self._remove_selected_patterns('file'))
        remove_folder_btn.clicked.connect(lambda: self._remove_selected_patterns('folder'))
        
        self.button_box.accepted.connect(self._save_and_close_name_patterns)
        self.button_box.rejected.connect(self.reject)
        
        self.pattern_entry.returnPressed.connect(add_file_btn.click)

        self._load_initial_name_patterns()

    def _load_initial_name_patterns(self):
        self.dialog_rule_file_patterns = []
        self.dialog_rule_folder_patterns = []
        try:
            if not os.path.exists(self.default_filepath):
                with open(self.default_filepath, "w", encoding="utf-8") as f:
                    f.write("# Default files to ignore (name patterns, e.g., *.log, specific_file.tmp)\n")
                    f.write("file: .DS_Store\nfile: thumbs.db\nfile: desktop.ini\n\n")
                    f.write("# Default folders to ignore (name patterns, e.g., .git, node_modules)\n")
                    f.write("folder: .git\nfolder: .svn\nfolder: .hg\nfolder: .venv\nfolder: venv\n")
                    f.write("folder: node_modules\nfolder: __pycache__\nfolder: build\nfolder: dist\n")
                print(f"Created default name patterns file: {self.default_filepath}")

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
            QMessageBox.critical(self, "Load Error", f"Could not load default name patterns from\n{self.default_filepath}\n\nError: {e}")
        self._populate_lists()

    def _populate_lists(self):
        self.file_list_widget.clear()
        self.folder_list_widget.clear()
        self.file_list_widget.addItems(self.dialog_rule_file_patterns)
        self.folder_list_widget.addItems(self.dialog_rule_folder_patterns)
        
    def _add_name_pattern(self, item_type):
        pattern = self.pattern_entry.text().strip()
        if not pattern:
            QMessageBox.warning(self, "Input Missing", "Please enter a file or folder name pattern to add.")
            return

        target_list = self.dialog_rule_file_patterns if item_type == 'file' else self.dialog_rule_folder_patterns
        if pattern in target_list:
            QMessageBox.information(self, "Pattern Exists", f"The pattern '{pattern}' is already in the list.")
            return
            
        target_list.append(pattern)
        target_list.sort()
        self._populate_lists()
        self.pattern_entry.clear()
        
    def _remove_selected_patterns(self, item_type):
        list_widget = self.file_list_widget if item_type == 'file' else self.folder_list_widget
        target_list = self.dialog_rule_file_patterns if item_type == 'file' else self.dialog_rule_folder_patterns
        
        selected_items = list_widget.selectedItems()
        if not selected_items:
            return
            
        for item in selected_items:
            if item.text() in target_list:
                target_list.remove(item.text())
        
        self._populate_lists()

    def _save_and_close_name_patterns(self):
        try:
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
            self.accept()
        except Exception as e:
            QMessageBox.critical(self, "Save Error", f"Could not save default name patterns to\n{self.default_filepath}\n\nError: {e}")