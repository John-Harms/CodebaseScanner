# CodebaseScanner/dialogs_qt/QtJsonScanDialog.py

import json
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QLabel, QTextEdit, 
    QDialogButtonBox, QMessageBox
)

class QtJsonScanDialog(QDialog):
    """
    Dialog to accept a JSON payload containing specific filenames for a targeted scan.
    Expected JSON format: {"req_files": ["file1.py", "file2.json"]}
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Targeted JSON Scan")
        self.setMinimumSize(450, 350)
        
        self.req_files =[]

        layout = QVBoxLayout(self)
        
        # --- UI Components ---
        instruction_label = QLabel(
            "Paste JSON payload below:\n"
            "Example:\n"
            "{\n"
            "  \"req_files\":[\n"
            "    \"main.py\",\n"
            "    \"utils.py\"\n"
            "  ]\n"
            "}"
        )
        layout.addWidget(instruction_label)

        self.json_input = QTextEdit()
        self.json_input.setPlaceholderText('{\n  "req_files":["example.py"]\n}')
        layout.addWidget(self.json_input)

        self.button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        layout.addWidget(self.button_box)

        # --- Connections ---
        self.button_box.accepted.connect(self._validate_and_accept)
        self.button_box.rejected.connect(self.reject)

    def _validate_and_accept(self):
        """Validates the input text as JSON and ensures the required structure exists."""
        text = self.json_input.toPlainText().strip()
        if not text:
            QMessageBox.critical(self, "Validation Error", "JSON input cannot be empty.")
            return

        try:
            data = json.loads(text)
        except json.JSONDecodeError as e:
            QMessageBox.critical(self, "Validation Error", f"Invalid JSON format:\n{e}")
            return

        if not isinstance(data, dict):
            QMessageBox.critical(self, "Validation Error", "JSON payload must be a dictionary.")
            return

        if "req_files" not in data:
            QMessageBox.critical(self, "Validation Error", "Missing 'req_files' key in JSON payload.")
            return

        req_files = data["req_files"]
        if not isinstance(req_files, list) or not all(isinstance(item, str) for item in req_files):
            QMessageBox.critical(self, "Validation Error", "'req_files' must be a list of strings.")
            return

        self.req_files = req_files
        self.accept()