# CodebaseScanner/dialogs_qt/QtManageProfilesDialog.py

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLineEdit, QPushButton,
    QListWidget, QListWidgetItem, QLabel, QMessageBox
)
from PySide6.QtCore import Qt

class QtManageProfilesDialog(QDialog):
    def __init__(self, parent, profiles_data, current_active_profile, app_instance, initial_action="load"):
        super().__init__(parent)
        self.profiles_dict = profiles_data
        self.app_instance_ref = app_instance
        self.current_active_profile_name = current_active_profile

        self.setWindowTitle("Manage Scan Profiles")
        self.setMinimumSize(450, 400)

        # --- Layouts ---
        main_layout = QVBoxLayout(self)
        filter_layout = QHBoxLayout()
        buttons_layout = QHBoxLayout()

        # --- Widgets ---
        filter_layout.addWidget(QLabel("Filter:"))
        self.search_entry = QLineEdit()
        filter_layout.addWidget(self.search_entry)

        self.profile_list_widget = QListWidget()
        self.profile_list_widget.setSortingEnabled(True)

        self.load_button = QPushButton("Load Selected")
        self.delete_button = QPushButton("Delete Selected")
        close_button = QPushButton("Close")
        
        buttons_layout.addWidget(self.load_button)
        buttons_layout.addWidget(self.delete_button)
        buttons_layout.addStretch()
        buttons_layout.addWidget(close_button)

        # --- Assembly ---
        main_layout.addLayout(filter_layout)
        main_layout.addWidget(QLabel("Saved Profiles:"))
        main_layout.addWidget(self.profile_list_widget)
        main_layout.addLayout(buttons_layout)
        
        # --- Connections ---
        self.search_entry.textChanged.connect(self._populate_profile_list)
        self.profile_list_widget.itemSelectionChanged.connect(self._update_button_states)
        self.profile_list_widget.itemDoubleClicked.connect(self._action_load_selected)
        
        self.load_button.clicked.connect(self._action_load_selected)
        self.delete_button.clicked.connect(self._action_delete_selected)
        close_button.clicked.connect(self.reject)

        self._populate_profile_list()
        self._update_button_states()

        if initial_action == "delete" and self.profiles_dict:
            self.delete_button.setFocus()
        elif self.profiles_dict:
            self.load_button.setFocus()

    def _populate_profile_list(self):
        self.profile_list_widget.clear()
        search_term = self.search_entry.text().lower()
        
        filtered_names = [name for name in self.profiles_dict if search_term in name.lower()]
        
        item_to_select = None
        for name in filtered_names:
            display_text = name
            if name == self.current_active_profile_name:
                display_text += " (Active)"
            
            item = QListWidgetItem(display_text)
            item.setData(Qt.ItemDataRole.UserRole, name) # Store actual name
            self.profile_list_widget.addItem(item)
            
            if name == self.current_active_profile_name:
                item_to_select = item

        if item_to_select:
            self.profile_list_widget.setCurrentItem(item_to_select)
        elif self.profile_list_widget.count() > 0:
            self.profile_list_widget.setCurrentRow(0)
            
    def _update_button_states(self):
        has_selection = bool(self.profile_list_widget.selectedItems())
        self.load_button.setEnabled(has_selection)
        self.delete_button.setEnabled(has_selection)

    def _get_selected_profile_name(self):
        selected_items = self.profile_list_widget.selectedItems()
        if not selected_items:
            return None
        return selected_items[0].data(Qt.ItemDataRole.UserRole)

    def _action_load_selected(self):
        profile_name = self._get_selected_profile_name()
        if profile_name and self.app_instance_ref:
            if hasattr(self.app_instance_ref, '_execute_load_profile'):
                if self.app_instance_ref._execute_load_profile(profile_name):
                    self.accept() # Close dialog on successful load
        elif not profile_name:
            QMessageBox.warning(self, "No Selection", "Please select a profile to load.")

    def _action_delete_selected(self):
        profile_name = self._get_selected_profile_name()
        if profile_name:
            reply = QMessageBox.question(self, "Confirm Delete", 
                                         f"Are you sure you want to delete profile '{profile_name}'?",
                                         QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                         QMessageBox.StandardButton.No)
            if reply == QMessageBox.StandardButton.Yes:
                if self.app_instance_ref and hasattr(self.app_instance_ref, '_execute_delete_profile'):
                    if self.app_instance_ref._execute_delete_profile(profile_name):
                        # Refresh dialog state from app
                        self.profiles_dict = self.app_instance_ref.profiles
                        self.current_active_profile_name = self.app_instance_ref.active_profile_name
                        self._populate_profile_list()
                        self._update_button_states()
        elif not profile_name:
            QMessageBox.warning(self, "No Selection", "Please select a profile to delete.")