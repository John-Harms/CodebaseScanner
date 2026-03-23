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
    QStyle, QTabWidget, QProgressDialog,
)
from PySide6.QtCore import QThread, QObject, Signal, Qt
from PySide6.QtGui import QClipboard, QColor, QBrush

import app_config
import profile_handler
import rule_manager
import scan_engine
from dialogs_qt.QtEditDefaultsDialog import QtEditDefaultsDialog
from dialogs_qt.QtManageProfilesDialog import QtManageProfilesDialog
from dialogs_qt.QtJsonScanDialog import QtJsonScanDialog

# ---------------------------------------------------------------------------
# Stylesheet
# ---------------------------------------------------------------------------

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
    selection-background-color: #004080;
    selection-color: #e0e0e0;
}
QTreeWidget::item:hover { background-color: #4a4a4a; }
QTreeWidget::item:selected { background-color: #0050a0; color: white; }
QPushButton {
    background-color: #555;
    border: 1px solid #666;
    padding: 6px 12px;
    border-radius: 4px;
    min-height: 20px;
}
QPushButton:hover { background-color: #666; border-color: #777; }
QPushButton:pressed { background-color: #444; }
QPushButton:disabled { background-color: #404040; color: #888; }
QCheckBox { spacing: 8px; }
QCheckBox::indicator { width: 18px; height: 18px; }
QMenuBar { background-color: #3c3c3c; }
QMenuBar::item { background-color: transparent; padding: 4px 8px; }
QMenuBar::item:selected { background-color: #555; }
QMenu { background-color: #3c3c3c; border: 1px solid #555; }
QMenu::item:selected { background-color: #555; }
QHeaderView::section {
    background-color: #3c3c3c;
    padding: 6px;
    border: 1px solid #555;
    font-weight: bold;
}
QStatusBar { background-color: #3c3c3c; font-weight: bold; }
QSplitter::handle { background-color: #3c3c3c; border: 1px solid #555; }
QSplitter::handle:vertical { height: 8px; }
QSplitter::handle:hover { background-color: #555; }
QTabWidget::pane { border: 1px solid #555; background-color: #2e2e2e; }
QTabBar::tab {
    background-color: #3c3c3c;
    color: #e0e0e0;
    padding: 6px 16px;
    border: 1px solid #555;
    border-bottom: none;
    border-radius: 4px 4px 0 0;
    min-width: 100px;
}
QTabBar::tab:selected { background-color: #505050; font-weight: bold; }
QTabBar::tab:hover { background-color: #4a4a4a; }
QTabBar::tab:!selected { margin-top: 2px; }
QProgressBar {
    background-color: #252525;
    border: 1px solid #555;
    border-radius: 4px;
    text-align: center;
    color: #e0e0e0;
}
QProgressBar::chunk { background-color: #0050a0; border-radius: 3px; }
QProgressDialog { background-color: #2e2e2e; }
"""

# Token data roles stored on each QTreeWidgetItem
TOKEN_ROLE  = Qt.ItemDataRole.UserRole + 1   # int: token count for this item
HIDDEN_ROLE = Qt.ItemDataRole.UserRole + 2   # bool: True if item is tree-blacklisted (greyed)

# ---------------------------------------------------------------------------
# Scan Worker (runs in thread)
# ---------------------------------------------------------------------------

class ScanWorker(QObject):
    status_update = Signal(str)
    scan_finished = Signal(str)
    scan_error = Signal(str, str)

    def __init__(self, scan_params):
        super().__init__()
        self.scan_params = scan_params

    def run(self):
        try:
            p = self.scan_params
            with open(p['save_path_norm'], "w", encoding="utf-8") as output_file:
                if p['generate_tree']:
                    self.status_update.emit("Generating directory tree...")
                    norm_blacklist =[os.path.normpath(x) for x in p['tree_blacklist']]
                    tree_header = f"# Directory Tree for: {os.path.basename(p['scan_dir_norm'])}\n\n"
                    tree_structure = scan_engine.generate_directory_tree_text(p['scan_dir_norm'], norm_blacklist)
                    output_file.write(tree_header)
                    output_file.write(tree_structure or f"{os.path.basename(p['scan_dir_norm'])}/\n (No subdirectories found or all were blacklisted)\n")
                    output_file.write("\n\n---\n\n")

                output_file.write(f"# Codebase Scan: {os.path.basename(p['scan_dir_norm'])}\n\n")
                mode_desc = "Whitelist (Including only listed paths)" if p['filter_mode'] == app_config.FILTER_WHITELIST else "Blacklist (Excluding listed paths)"
                output_file.write(f"**Mode:** `{mode_desc}`\n")

                if p['rules_path_display']:
                    src = f"`{os.path.basename(p['rules_path_display'])}` (from `{p['rules_path_display']}`)"
                    if p['rules_dirty']:
                        src += " - with unsaved modifications in GUI"
                else:
                    src = "`Current GUI rules (No file or unsaved changes to a file)`"
                output_file.write(f"**Rules From:** {src}\n\n")

                initial_whitelisted = []
                if p['filter_mode'] == app_config.FILTER_WHITELIST and p['scan_dir_norm'] in p['rules_folders']:
                    initial_whitelisted.append(p['scan_dir_norm'])

                scan_engine.process_directory(
                    p['scan_dir_norm'], output_file, p['rules_files'], p['rules_folders'],
                    p['filter_mode'], level=0, status_callback=self.status_update.emit,
                    whitelisted_ancestor_folders=initial_whitelisted
                )
            self.scan_finished.emit(p['save_path_norm'])
        except Exception as e:
            self.scan_error.emit(str(e), traceback.format_exc())


# ---------------------------------------------------------------------------
# Tree Token Worker (runs in thread)
# ---------------------------------------------------------------------------

class TreeTokenWorker(QObject):
    """Traverses the directory tree, counts tokens, emits per-item data."""

    LARGE_DIR_THRESHOLD = 500

    TOKENS_LARGE_DIR   = -1   
    TOKENS_TREE_HIDDEN = -3   

    progress = Signal(int, int)           
    item_ready = Signal(str, bool, int)   
    finished = Signal(int)                
    error = Signal(str)

    def __init__(self, scan_dir, default_ignore_patterns, tree_blacklist,
                 rules_files=None, rules_folders=None, filter_mode=None):
        super().__init__()
        self.scan_dir = scan_dir
        self.default_ignore_patterns = default_ignore_patterns
        self.tree_blacklist = {os.path.normpath(p) for p in tree_blacklist}
        self.rules_files  =[os.path.normpath(p) for p in (rules_files or [])]
        self.rules_folders =[os.path.normpath(p) for p in (rules_folders or [])]
        self.filter_mode  = filter_mode 
        self._cancelled = False

    def cancel(self):
        self._cancelled = True

    def run(self):
        try:
            # Pass 1: collect dirs/files and build subtree file-count map.
            all_files: list[str] = []
            all_dirs:  list[str] =[]
            blacklisted_dirs_to_show: list[str] = []
            direct_count: dict[str, int] = {}

            for root, dirs, files in os.walk(self.scan_dir):
                if self._cancelled:
                    return
                norm_root = os.path.normpath(root)
                folder_patterns = self.default_ignore_patterns.get('folder',[])

                blacklisted_here = sorted([
                        os.path.normpath(os.path.join(norm_root, d))
                        for d in dirs
                        if os.path.normpath(os.path.join(norm_root, d)) in self.tree_blacklist
                        and not any(fnmatch.fnmatch(d, p) for p in folder_patterns)
                    ]
                )
                blacklisted_dirs_to_show.extend(blacklisted_here)

                dirs[:] = sorted([
                        d for d in dirs
                        if os.path.normpath(os.path.join(norm_root, d)) not in self.tree_blacklist
                        and not any(fnmatch.fnmatch(d, p) for p in folder_patterns)
                    ],
                    key=str.lower,
                )
                all_dirs.append(norm_root)
                file_patterns = self.default_ignore_patterns.get('file',[])
                n = 0
                for f in sorted(files, key=str.lower):
                    if not any(fnmatch.fnmatch(f, p) for p in file_patterns):
                        all_files.append(os.path.normpath(os.path.join(norm_root, f)))
                        n += 1
                direct_count[norm_root] = n

            # Pass 1b: compute subtree file counts.
            subtree_count: dict[str, int] = dict(direct_count)
            for d in sorted(all_dirs, key=lambda x: x.count(os.sep), reverse=True):
                parent = os.path.normpath(os.path.dirname(d))
                if parent in subtree_count and parent != d:
                    subtree_count[parent] = subtree_count.get(parent, 0) + subtree_count.get(d, 0)

            large_dirs: set[str] = {
                d for d, cnt in subtree_count.items()
                if cnt > self.LARGE_DIR_THRESHOLD
            }
            skipped_dirs: set[str] = set()
            for d in all_dirs:
                if any(d == ld or d.startswith(ld + os.sep) for ld in large_dirs):
                    skipped_dirs.add(d)

            # Pass 2: emit tree structure.
            for d in all_dirs:
                if self._cancelled:
                    return
                sentinel = self.TOKENS_LARGE_DIR if d in skipped_dirs else 0
                self.item_ready.emit(d, True, sentinel)

            for d in blacklisted_dirs_to_show:
                if self._cancelled:
                    return
                self.item_ready.emit(d, True, self.TOKENS_TREE_HIDDEN)

            # Pass 3: count tokens.
            total = len(all_files)
            whitelisted_parents = list(self.rules_folders) if self.filter_mode is not None else[]

            for i, fpath in enumerate(all_files):
                if self._cancelled:
                    return

                parent_dir = os.path.normpath(os.path.dirname(fpath))

                if parent_dir in skipped_dirs:
                    self.progress.emit(i + 1, total)
                    continue

                if self.filter_mode is not None:
                    included = scan_engine.should_process_item(
                        fpath, True,
                        self.rules_files, self.rules_folders,
                        self.filter_mode, whitelisted_parents
                    )
                    if not included:
                        self.item_ready.emit(fpath, False, 0)
                        self.progress.emit(i + 1, total)
                        continue

                tokens = scan_engine.count_tokens_for_file(fpath)
                self.item_ready.emit(fpath, False, tokens)
                self.progress.emit(i + 1, total)

            tree_tok = scan_engine.estimate_tree_tokens(self.scan_dir, list(self.tree_blacklist))
            self.finished.emit(tree_tok)
        except Exception as e:
            self.error.emit(str(e))



# ---------------------------------------------------------------------------
# WorkspaceTab
# ---------------------------------------------------------------------------

class WorkspaceTab(QWidget):
    """Self-contained workspace: one scan profile, one rules file, one tree."""

    dirty_changed = Signal(bool)

    def __init__(self, profiles_ref, parent=None):
        super().__init__(parent)
        self._profiles_ref = profiles_ref  

        # State
        self.current_rules_filepath = ""
        self.filter_mode = app_config.FILTER_BLACKLIST
        self.rules_files: list[str] = []
        self.rules_folders: list[str] = []
        self.rules_dirty = False
        self.directory_tree_blacklist: list[str] = []
        self.default_ignore_patterns: dict = {'file': [], 'folder':[]}
        self.active_profile_name: str | None = None

        # Threading
        self._token_thread: QThread | None = None
        self._token_worker: TreeTokenWorker | None = None

        # Token tracking
        self._tree_tokens = 0

        # Show/hide tree-blacklisted dirs
        self._show_hidden_dirs: bool = False

        self._setup_ui()

    # ------------------------------------------------------------------
    # UI Build
    # ------------------------------------------------------------------

    def _setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(10)

        # Core Paths
        core_paths_group = QGroupBox("Core Paths")
        gp_layout = QGridLayout(core_paths_group)

        gp_layout.addWidget(QLabel("Scan Directory:"), 0, 0)
        self.scan_dir_entry = QLineEdit()
        scan_dir_btn = QPushButton("Browse...")
        scan_dir_btn.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_DirIcon))
        row0 = QHBoxLayout()
        row0.addWidget(self.scan_dir_entry)
        row0.addWidget(scan_dir_btn)
        gp_layout.addLayout(row0, 0, 1)

        gp_layout.addWidget(QLabel("Save Output As:"), 1, 0)
        self.save_path_entry = QLineEdit()
        save_path_btn = QPushButton("Browse...")
        save_path_btn.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_DirIcon))
        row1 = QHBoxLayout()
        row1.addWidget(self.save_path_entry)
        row1.addWidget(save_path_btn)
        gp_layout.addLayout(row1, 1, 1)
        gp_layout.setColumnStretch(1, 1)

        # Rules Configuration
        rules_config_group = QGroupBox("Rules Configuration")
        rc_layout = QGridLayout(rules_config_group)
        rc_layout.addWidget(QLabel("Rules File (.scanIgnore):"), 0, 0)
        self.rules_dir_entry = QLineEdit()
        self.rules_dir_entry.setReadOnly(True)
        rules_dir_btn = QPushButton("Browse...")
        rules_dir_btn.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_DirIcon))
        row2 = QHBoxLayout()
        row2.addWidget(self.rules_dir_entry)
        row2.addWidget(rules_dir_btn)
        rc_layout.addLayout(row2, 0, 1)

        rb_layout = QHBoxLayout()
        rb_layout.addStretch()
        edit_defaults_btn = QPushButton("Edit Default Name Patterns")
        self.save_rules_btn = QPushButton("Save Rules List")
        rb_layout.addWidget(edit_defaults_btn)
        rb_layout.addWidget(self.save_rules_btn)
        rc_layout.addLayout(rb_layout, 1, 1)
        rc_layout.setColumnStretch(1, 1)

        # Scan Options
        scan_options_group = QGroupBox("Scan Options")
        so_layout = QHBoxLayout(scan_options_group)
        self.filter_mode_check = QCheckBox("Whitelist Mode (Include Only Listed Paths)")
        self.generate_tree_check = QCheckBox("Generate Directory Tree in Output")
        so_layout.addWidget(self.filter_mode_check)
        so_layout.addWidget(self.generate_tree_check)
        so_layout.addStretch()

        top_widget = QWidget()
        top_layout = QVBoxLayout(top_widget)
        top_layout.setContentsMargins(0, 0, 0, 0)
        top_layout.setSpacing(10)
        top_layout.addWidget(core_paths_group)
        top_layout.addWidget(rules_config_group)
        top_layout.addWidget(scan_options_group)

        # Tree explorer
        tree_frame = self._setup_tree_explorer_ui()

        splitter = QSplitter(Qt.Orientation.Vertical)
        splitter.addWidget(top_widget)
        splitter.addWidget(tree_frame)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([300, 500])

        # Token summary bar
        token_bar = QWidget()
        token_bar.setStyleSheet("background-color: #383838; border: 1px solid #555; border-radius: 4px;")
        tb_layout = QHBoxLayout(token_bar)
        tb_layout.setContentsMargins(10, 4, 10, 4)
        lbl_style = "color: #88ccff; font-weight: bold;"
        self.lbl_tree_tokens = QLabel("Tree: — tk")
        self.lbl_scan_tokens = QLabel("Scan: — tk")
        self.lbl_total_tokens = QLabel("Total: — tk")
        for lbl in (self.lbl_tree_tokens, self.lbl_scan_tokens, self.lbl_total_tokens):
            lbl.setStyleSheet(lbl_style)
        tb_layout.addStretch()
        tb_layout.addWidget(QLabel("Tokens →"))
        tb_layout.addSpacing(8)
        tb_layout.addWidget(self.lbl_tree_tokens)
        tb_layout.addSpacing(16)
        tb_layout.addWidget(self.lbl_scan_tokens)
        tb_layout.addSpacing(16)
        tb_layout.addWidget(self.lbl_total_tokens)
        tb_layout.addStretch()

        # Run buttons
        self.run_scan_btn = QPushButton("Run Scan")
        self.run_scan_btn.setStyleSheet("font-size: 12pt; font-weight: bold; padding: 12px 24px;")
        self.run_copy_btn = QPushButton("▶  Run Scan && Copy to Clipboard")
        self.run_copy_btn.setStyleSheet(
            "font-size: 12pt; font-weight: bold; padding: 12px 24px;"
            "background-color: #1a5276; border-color: #2471a3;"
        )
        self.run_json_btn = QPushButton("Targeted JSON Scan")
        self.run_json_btn.setStyleSheet("font-size: 12pt; font-weight: bold; padding: 12px 24px;")

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        btn_layout.addWidget(self.run_scan_btn)
        btn_layout.addSpacing(16)
        btn_layout.addWidget(self.run_copy_btn)
        btn_layout.addSpacing(16)
        btn_layout.addWidget(self.run_json_btn)
        btn_layout.addStretch()

        main_layout.addWidget(splitter, 1)
        main_layout.addWidget(token_bar)
        main_layout.addLayout(btn_layout)

        # Connections
        scan_dir_btn.clicked.connect(self._browse_scan_directory)
        save_path_btn.clicked.connect(self._browse_save_file)
        rules_dir_btn.clicked.connect(self._browse_rules_directory)
        edit_defaults_btn.clicked.connect(self._edit_defaults_dialog)
        self.save_rules_btn.clicked.connect(self._save_rules_list_changes)
        self.filter_mode_check.stateChanged.connect(self._on_filter_mode_change)
        self.generate_tree_check.stateChanged.connect(self._on_generate_tree_toggle)
        self.run_scan_btn.clicked.connect(lambda: self._run_scan(copy_to_clipboard=False))
        self.run_copy_btn.clicked.connect(lambda: self._run_scan(copy_to_clipboard=True))
        self.run_json_btn.clicked.connect(self._run_json_scan)

        # Defaults
        self.save_path_entry.setText(
            os.path.join(app_config.get_downloads_folder(), app_config.DEFAULT_OUTPUT_FILENAME)
        )
        self.generate_tree_check.setChecked(True)
        self._on_filter_mode_change()

    def _setup_tree_explorer_ui(self) -> QFrame:
        tree_frame = QFrame()
        tree_frame.setFrameShape(QFrame.Shape.StyledPanel)
        tl = QVBoxLayout(tree_frame)
        tl.setContentsMargins(10, 10, 10, 10)
        tl.setSpacing(8)

        ctrl_layout = QHBoxLayout()
        self.load_tree_btn = QPushButton("Load/Refresh Directory Tree")
        self.load_tree_btn.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_BrowserReload))
        self.show_hidden_btn = QPushButton("👁 Show Hidden Dirs")
        self.show_hidden_btn.setCheckable(True)
        self.show_hidden_btn.setToolTip(
            "Show directories that are in the Tree Blacklist so you can review or remove them."
        )
        ctrl_layout.addWidget(self.load_tree_btn)
        ctrl_layout.addWidget(self.show_hidden_btn)
        ctrl_layout.addStretch()
        tl.addLayout(ctrl_layout)

        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["Name", "Scan Rule", "Tree Blacklist", "Tokens"])
        self.tree.header().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.tree.header().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.tree.header().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.tree.header().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.tree.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        tl.addWidget(self.tree)

        ar_layout = QHBoxLayout()
        ar_layout.setSpacing(8)
        self.add_scan_rule_btn = QPushButton("Apply Scan Rule")
        self.add_scan_rule_btn.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_DialogApplyButton))
        remove_scan_btn = QPushButton("Remove Scan Rule")
        remove_scan_btn.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_DialogCancelButton))
        add_tree_btn = QPushButton("Apply Tree Blacklist")
        add_tree_btn.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_DialogApplyButton))
        remove_tree_btn = QPushButton("Remove from Tree Blacklist")
        remove_tree_btn.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_DialogCancelButton))

        ar_layout.addWidget(self.add_scan_rule_btn)
        ar_layout.addWidget(remove_scan_btn)
        ar_layout.addSpacing(20)
        ar_layout.addWidget(add_tree_btn)
        ar_layout.addWidget(remove_tree_btn)
        ar_layout.addStretch()
        tl.addLayout(ar_layout)

        self.load_tree_btn.clicked.connect(self._populate_tree_view)
        self.show_hidden_btn.toggled.connect(self._toggle_show_hidden_dirs)
        self.tree.itemExpanded.connect(self._on_tree_item_expanded)
        self.add_scan_rule_btn.clicked.connect(lambda: self._apply_rules_to_selection('scan_rule', 'add'))
        remove_scan_btn.clicked.connect(lambda: self._apply_rules_to_selection('scan_rule', 'remove'))
        add_tree_btn.clicked.connect(lambda: self._apply_rules_to_selection('tree_blacklist', 'add'))
        remove_tree_btn.clicked.connect(lambda: self._apply_rules_to_selection('tree_blacklist', 'remove'))

        return tree_frame

    # ------------------------------------------------------------------
    # State helpers
    # ------------------------------------------------------------------

    def _set_dirty(self, dirty: bool):
        self.rules_dirty = dirty
        self.dirty_changed.emit(dirty)

    def apply_profile_settings(self, profile_name: str, profiles: dict) -> bool:
        profile_data = profiles.get(profile_name)
        if not profile_data:
            QMessageBox.critical(self, "Error", f"Profile '{profile_name}' not found.")
            return False

        if self.rules_dirty:
            reply = QMessageBox.question(
                self, "Unsaved Changes",
                "You have unsaved changes in the current scan rules list. Discard them and load the profile?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if reply == QMessageBox.StandardButton.No:
                return False

        self.scan_dir_entry.setText(profile_data.get("scan_directory", ""))
        down = os.path.join(app_config.get_downloads_folder(), app_config.DEFAULT_OUTPUT_FILENAME)
        self.save_path_entry.setText(profile_data.get("save_filepath", down))
        self.filter_mode_check.setChecked(
            profile_data.get("filter_mode", app_config.FILTER_BLACKLIST) == app_config.FILTER_WHITELIST
        )
        self.generate_tree_check.setChecked(profile_data.get("generate_directory_tree", True))
        self._set_rules_directory_and_load(profile_data.get("rules_directory", ""))
        self._set_dirty(False)

        if self.scan_dir_entry.text() and os.path.isdir(self.scan_dir_entry.text()):
            self._populate_tree_view()
        else:
            self.tree.clear()
            self._reset_token_labels()

        self.active_profile_name = profile_name
        self._on_filter_mode_change()
        return True

    def get_profile_data(self) -> dict:
        return {
            "scan_directory": os.path.normpath(self.scan_dir_entry.text()),
            "save_filepath": os.path.normpath(self.save_path_entry.text()),
            "rules_directory": os.path.normpath(self.rules_dir_entry.text()) if self.rules_dir_entry.text() else "",
            "rules_filepath": os.path.normpath(self.current_rules_filepath) if self.current_rules_filepath else "",
            "filter_mode": self.filter_mode,
            "directory_tree_blacklist": list(self.directory_tree_blacklist),
            "generate_directory_tree": self.generate_tree_check.isChecked(),
        }

    def validate_for_scan(self) -> tuple[bool, str]:
        if not self.scan_dir_entry.text() or not os.path.isdir(self.scan_dir_entry.text()):
            return False, "Please select a valid directory to scan."
        if not self.save_path_entry.text():
            return False, "Please select a valid output file path."
        return True, ""

    # ------------------------------------------------------------------
    # Event handlers
    # ------------------------------------------------------------------

    def _on_filter_mode_change(self):
        is_wl = self.filter_mode_check.isChecked()
        self.filter_mode = app_config.FILTER_WHITELIST if is_wl else app_config.FILTER_BLACKLIST
        self.add_scan_rule_btn.setToolTip(
            f"Mark selected items to {'include in' if is_wl else 'exclude from'} the scan."
        )
        self._recalculate_token_labels()

    def _on_generate_tree_toggle(self):
        if self.active_profile_name:
            self._set_dirty(True)

    # ------------------------------------------------------------------
    # Browse helpers
    # ------------------------------------------------------------------

    def _browse_scan_directory(self):
        d = QFileDialog.getExistingDirectory(self, "Select Directory to Scan",
                                             self.scan_dir_entry.text() or os.path.expanduser("~"))
        if d:
            self.scan_dir_entry.setText(os.path.normpath(d))
            self._populate_tree_view()

    def _browse_save_file(self):
        init = os.path.dirname(self.save_path_entry.text()) or self.scan_dir_entry.text() or os.path.expanduser("~")
        fp, _ = QFileDialog.getSaveFileName(self, "Save Scan Output As",
                                            os.path.join(init, app_config.DEFAULT_OUTPUT_FILENAME),
                                            "Text Files (*.txt);;Markdown Files (*.md);;All Files (*.*)")
        if fp:
            self.save_path_entry.setText(os.path.normpath(fp))

    def _browse_rules_directory(self):
        init = self.rules_dir_entry.text() or self.scan_dir_entry.text() or os.path.expanduser("~")
        d = QFileDialog.getExistingDirectory(self, "Select Rules Directory", init)
        if not d:
            return
        norm = os.path.normpath(d)
        if norm == self.rules_dir_entry.text():
            return
        if self.rules_dirty:
            reply = QMessageBox.question(
                self, "Unsaved Changes",
                "You have unsaved scan rule changes. Discard them and switch to the new directory?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if reply == QMessageBox.StandardButton.No:
                return
        self._set_rules_directory_and_load(norm, prompt_create=True)

    # ------------------------------------------------------------------
    # Rules management
    # ------------------------------------------------------------------

    def _edit_defaults_dialog(self):
        dialog = QtEditDefaultsDialog(self, app_config.DEFAULT_IGNORE_PATH, self)
        dialog.exec()

    def _set_rules_directory_and_load(self, dir_path: str, prompt_create=False):
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
                reply = QMessageBox.question(
                    self, "Create Rules File?",
                    f"'.scanIgnore' does not exist in:\n{dir_path}\n\nCreate it?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                )
                create = (reply == QMessageBox.StandardButton.Yes)
            if create:
                try:
                    rule_manager.create_empty_file(rules_file)
                    self.current_rules_filepath = rules_file
                except OSError as e:
                    self.current_rules_filepath = ""
                    QMessageBox.critical(self, "File Creation Error",
                                        f"Could not create the rules file at:\n{rules_file}\nError: {e}")
            else:
                self.current_rules_filepath = ""

        self._load_rules_from_file()

    def _load_rules_from_file(self):
        if not self.current_rules_filepath:
            self.rules_files, self.rules_folders, self.directory_tree_blacklist = [], [],[]
        else:
            try:
                self.rules_files, self.rules_folders, self.directory_tree_blacklist = (
                    rule_manager.load_ignore_rules(self.current_rules_filepath)
                )
            except Exception as e:
                QMessageBox.critical(self, "Load Error",
                                     f"Could not load scan rules from "
                                     f"{os.path.basename(self.current_rules_filepath)}:\n{e}")
                self.rules_files, self.rules_folders, self.directory_tree_blacklist = [], [],[]

        self._set_dirty(False)
        self._update_all_tree_visuals()

    def _save_rules_list_changes(self) -> bool:
        path = self.current_rules_filepath
        if not path and self.rules_dir_entry.text():
            reply = QMessageBox.question(self, "Create and Save?",
                                         "Create and save rules to '.scanIgnore' in the current rules directory?",
                                         QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            if reply == QMessageBox.StandardButton.Yes:
                path = os.path.join(self.rules_dir_entry.text(), ".scanIgnore")
                self.current_rules_filepath = path
            else:
                return False
        elif not path:
            QMessageBox.critical(self, "Save Error", "No valid rules directory is selected.")
            return False

        if not self.rules_dirty:
            return True

        try:
            rule_manager.save_ignore_rules(path, self.rules_files, self.rules_folders, self.directory_tree_blacklist)
            self._set_dirty(False)
            return True
        except Exception as e:
            QMessageBox.critical(self, "Save Error", f"Could not save scan rules:\n{e}")
            return False

    # ------------------------------------------------------------------
    # Tree population (async)
    # ------------------------------------------------------------------

    def _load_default_ignore_patterns(self):
        self.default_ignore_patterns = {'file': [], 'folder':[]}
        try:
            with open(app_config.DEFAULT_IGNORE_PATH, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue
                    if line.lower().startswith("file:"):
                        self.default_ignore_patterns['file'].append(line[len("file:"):].strip())
                    elif line.lower().startswith("folder:"):
                        self.default_ignore_patterns['folder'].append(line[len("folder:"):].strip())
        except Exception:
            pass

    def _populate_tree_view(self):
        scan_dir = self.scan_dir_entry.text()
        if not scan_dir or not os.path.isdir(scan_dir):
            QMessageBox.critical(self, "Input Error", "Please select a valid directory to scan first.")
            return

        if self._token_worker:
            try:
                self._token_worker.cancel()
            except RuntimeError:
                pass
            for sig in (
                self._token_worker.item_ready,
                self._token_worker.progress,
                self._token_worker.finished,
                self._token_worker.error,
            ):
                try:
                    sig.disconnect()
                except RuntimeError:
                    pass
            self._token_worker = None
        if self._token_thread:
            try:
                if self._token_thread.isRunning():
                    self._token_thread.quit()
                    self._token_thread.wait(2000)
            except RuntimeError:
                pass
            self._token_thread = None

        self.tree.clear()
        self._reset_token_labels()
        self._load_default_ignore_patterns()

        self._progress_dlg = QProgressDialog("Counting tokens…", "Cancel", 0, 0, self)
        self._progress_dlg.setWindowTitle("Loading Directory Tree")
        self._progress_dlg.setWindowModality(Qt.WindowModality.WindowModal)
        self._progress_dlg.setMinimumDuration(300)
        self._progress_dlg.setValue(0)

        self._path_to_item: dict[str, QTreeWidgetItem] = {}

        root_item = QTreeWidgetItem(self.tree, [f"📁 {os.path.basename(scan_dir)}"])
        root_item.setData(0, Qt.ItemDataRole.UserRole, (scan_dir, True))
        root_item.setData(0, TOKEN_ROLE, 0)
        root_item.setExpanded(True)
        self._path_to_item[os.path.normpath(scan_dir)] = root_item

        self._token_thread = QThread(self)
        self._token_worker = TreeTokenWorker(
            scan_dir,
            self.default_ignore_patterns,
            self.directory_tree_blacklist,
            rules_files=list(self.rules_files),
            rules_folders=list(self.rules_folders),
            filter_mode=self.filter_mode,
        )
        self._token_worker.moveToThread(self._token_thread)

        self._token_thread.started.connect(self._token_worker.run)
        self._token_worker.item_ready.connect(self._on_tree_item_ready)
        self._token_worker.progress.connect(self._on_tree_progress)
        self._token_worker.finished.connect(self._on_tree_population_finished)
        self._token_worker.error.connect(self._on_tree_population_error)

        self._token_worker.finished.connect(self._token_thread.quit)
        self._token_worker.error.connect(self._token_thread.quit)
        
        _thread_to_del = self._token_thread
        _worker_to_del = self._token_worker
        def _cleanup_thread():
            try:
                _worker_to_del.deleteLater()
            except RuntimeError:
                pass
            try:
                _thread_to_del.deleteLater()
            except RuntimeError:
                pass
        self._token_thread.finished.connect(_cleanup_thread)

        self._progress_dlg.canceled.connect(self._token_worker.cancel)

        self._token_thread.start()

    def _on_tree_progress(self, current: int, total: int):
        if total > 0:
            self._progress_dlg.setMaximum(total)
            self._progress_dlg.setValue(current)

    def _on_tree_item_ready(self, abs_path: str, is_dir: bool, token_count: int):
        norm = os.path.normpath(abs_path)
        parent_norm = os.path.normpath(os.path.dirname(norm))

        if is_dir:
            if norm in self._path_to_item:
                return  
            parent_item = self._path_to_item.get(parent_norm)
            if parent_item is None:
                return

            if token_count == TreeTokenWorker.TOKENS_TREE_HIDDEN:
                item = QTreeWidgetItem(parent_item,[f"🚫 {os.path.basename(norm)}"])
                item.setData(0, Qt.ItemDataRole.UserRole, (norm, True))
                item.setData(0, TOKEN_ROLE, 0)
                item.setData(0, HIDDEN_ROLE, True)
                item.setForeground(0, item.foreground(0))  
                grey_brush = QBrush(QColor(120, 120, 120))
                for col in range(self.tree.columnCount()):
                    item.setForeground(col, grey_brush)
                item.setText(2, "✓")   
                item.setText(3, "—")
                item.setToolTip(0, "Tree-blacklisted: hidden from directory tree output")
                item.setHidden(not self._show_hidden_dirs)
            elif token_count == TreeTokenWorker.TOKENS_LARGE_DIR:
                item = QTreeWidgetItem(parent_item, [f"📁 {os.path.basename(norm)}"])
                item.setData(0, Qt.ItemDataRole.UserRole, (norm, True))
                item.setData(0, TOKEN_ROLE, 0)
                item.setText(3, "⚠ Large")
                item.setToolTip(3, f"Skipped: >{TreeTokenWorker.LARGE_DIR_THRESHOLD} files in subtree")
                self._path_to_item[norm] = item
            else:
                item = QTreeWidgetItem(parent_item, [f"📁 {os.path.basename(norm)}"])
                item.setData(0, Qt.ItemDataRole.UserRole, (norm, True))
                item.setData(0, TOKEN_ROLE, 0)
                self._path_to_item[norm] = item

        else:
            parent_item = self._path_to_item.get(parent_norm)
            if parent_item is None:
                return

            parent_is_large = (parent_item.text(3) == "⚠ Large")

            ext = os.path.splitext(norm)[1].lower()
            item = QTreeWidgetItem(parent_item, [f"📄 {os.path.basename(norm)}"])
            item.setData(0, Qt.ItemDataRole.UserRole, (norm, False))

            if parent_is_large or token_count == TreeTokenWorker.TOKENS_LARGE_DIR:
                item.setData(0, TOKEN_ROLE, 0)
                item.setText(3, "—")
            else:
                if ext not in app_config.LANG_MAP:
                    token_count = 0
                item.setData(0, TOKEN_ROLE, token_count)
                item.setText(3, f"{token_count:,}" if token_count else "—")

                p = parent_item
                while p is not None:
                    existing = p.data(0, TOKEN_ROLE) or 0
                    p.setData(0, TOKEN_ROLE, existing + token_count)
                    p_tok = p.data(0, TOKEN_ROLE) or 0
                    if p.text(3) != "⚠ Large":
                        p.setText(3, f"{p_tok:,}" if p_tok else "—")
                    p = p.parent()


        self._update_tree_visuals_for_items([item])


    def _on_tree_population_finished(self, tree_tokens: int):
        self._progress_dlg.close()
        self._tree_tokens = tree_tokens
        self._update_all_tree_visuals()
        self._recalculate_token_labels()

    def _on_tree_population_error(self, error_msg: str):
        self._progress_dlg.close()
        QMessageBox.critical(self, "Tree Load Error", f"Error loading directory tree:\n{error_msg}")

    # ------------------------------------------------------------------
    # Legacy lazy expansion (kept for any manual expansions)
    # ------------------------------------------------------------------

    def _on_tree_item_expanded(self, item: QTreeWidgetItem):
        pass

    def _toggle_show_hidden_dirs(self, checked: bool):
        self._show_hidden_dirs = checked
        self.show_hidden_btn.setText("👁 Hide Hidden Dirs" if checked else "👁 Show Hidden Dirs")
        it = QTreeWidgetItemIterator(self.tree)
        while it.value():
            item = it.value()
            if item.data(0, HIDDEN_ROLE):
                item.setHidden(not checked)
            it += 1

    # ------------------------------------------------------------------
    # Rule application
    # ------------------------------------------------------------------

    def _get_item_and_all_descendants(self, start_item: QTreeWidgetItem) -> set:
        result = set()
        stack = [start_item]
        while stack:
            cur = stack.pop()
            result.add(cur)
            for i in range(cur.childCount()):
                stack.append(cur.child(i))
        return result

    def _apply_rules_to_selection(self, rule_type: str, action: str):
        selected = self.tree.selectedItems()
        if not selected:
            return

        if rule_type == 'tree_blacklist':
            changed = False
            for item in selected:
                data = item.data(0, Qt.ItemDataRole.UserRole)
                if not data:
                    continue
                full_path, is_dir = data
                if not is_dir:
                    continue
                if action == 'add' and full_path not in self.directory_tree_blacklist:
                    self.directory_tree_blacklist.append(full_path)
                    changed = True
                elif action == 'remove' and full_path in self.directory_tree_blacklist:
                    self.directory_tree_blacklist.remove(full_path)
                    changed = True
            if changed:
                self._set_dirty(True)
                all_affected: set = set()
                for item in selected:
                    all_affected.update(self._get_item_and_all_descendants(item))
                self._update_tree_visuals_for_items(all_affected)
                self._recalculate_token_labels()
            return

        items_to_process: set = set()
        for item in selected:
            items_to_process.update(self._get_item_and_all_descendants(item))

        for item in items_to_process:
            data = item.data(0, Qt.ItemDataRole.UserRole)
            if not data:
                continue
            full_path, is_dir = data

            target = self.rules_folders if is_dir else self.rules_files
            if action == 'add' and full_path not in target:
                target.append(full_path)
            elif action == 'remove' and full_path in target:
                target.remove(full_path)
            self._set_dirty(True)

        self._update_tree_visuals_for_items(items_to_process)
        self._recalculate_token_labels()

    # ------------------------------------------------------------------
    # Tree visuals
    # ------------------------------------------------------------------

    def _update_tree_visuals_for_items(self, items):
        for item in items:
            data = item.data(0, Qt.ItemDataRole.UserRole)
            if not data:
                continue
            full_path, is_dir = data
            is_rule = (full_path in self.rules_folders) if is_dir else (full_path in self.rules_files)
            item.setText(1, "✓" if is_rule else "")
            is_bl = is_dir and full_path in self.directory_tree_blacklist
            item.setText(2, "✓" if is_bl else "")

    def _update_all_tree_visuals(self):
        if self.tree.topLevelItemCount() == 0:
            return
        all_items =[]
        it = QTreeWidgetItemIterator(self.tree)
        while it.value():
            all_items.append(it.value())
            it += 1
        self._update_tree_visuals_for_items(all_items)

    # ------------------------------------------------------------------
    # Token label helpers
    # ------------------------------------------------------------------

    def _reset_token_labels(self):
        self._tree_tokens = 0
        self.lbl_tree_tokens.setText("Tree: — tk")
        self.lbl_scan_tokens.setText("Scan: — tk")
        self.lbl_total_tokens.setText("Total: — tk")

    def _recalculate_token_labels(self):
        scan_tokens = 0
        it = QTreeWidgetItemIterator(self.tree)
        while it.value():
            item = it.value()
            data = item.data(0, Qt.ItemDataRole.UserRole)
            if data:
                full_path, is_dir = data
                if not is_dir:
                    if scan_engine.should_process_item(
                        full_path, True,
                        self.rules_files, self.rules_folders,
                        self.filter_mode,[]
                    ):
                        tok = item.data(0, TOKEN_ROLE) or 0
                        scan_tokens += tok
            it += 1

        tree_tok = self._tree_tokens if self.generate_tree_check.isChecked() else 0
        total = tree_tok + scan_tokens
        self.lbl_tree_tokens.setText(f"Tree: {tree_tok:,} tk")
        self.lbl_scan_tokens.setText(f"Scan: {scan_tokens:,} tk")
        self.lbl_total_tokens.setText(f"Total: {total:,} tk")

    # ------------------------------------------------------------------
    # Scan execution
    # ------------------------------------------------------------------

    def _run_scan(self, copy_to_clipboard: bool = False):
        ok, msg = self.validate_for_scan()
        if not ok:
            QMessageBox.critical(self, "Input Error", msg)
            return

        save_path = self.save_path_entry.text()
        save_dir = os.path.dirname(save_path)
        if save_dir and not os.path.exists(save_dir):
            try:
                os.makedirs(save_dir, exist_ok=True)
            except Exception as e:
                QMessageBox.critical(self, "Input Error", f"Could not create save directory:\n{save_dir}\nError: {e}")
                return

        self.run_scan_btn.setEnabled(False)
        self.run_copy_btn.setEnabled(False)
        self.run_json_btn.setEnabled(False)

        scan_params = {
            'scan_dir_norm': os.path.normpath(self.scan_dir_entry.text()),
            'save_path_norm': os.path.normpath(save_path),
            'rules_files': list(self.rules_files),
            'rules_folders': list(self.rules_folders),
            'filter_mode': self.filter_mode,
            'rules_path_display': self.current_rules_filepath,
            'rules_dirty': self.rules_dirty,
            'generate_tree': self.generate_tree_check.isChecked(),
            'tree_blacklist': list(self.directory_tree_blacklist),
            'copy_to_clipboard': copy_to_clipboard,
        }

        self._scan_thread = QThread(self)
        self._scan_worker = ScanWorker(scan_params)
        self._scan_worker.moveToThread(self._scan_thread)

        self._scan_thread.started.connect(self._scan_worker.run)
        self._scan_worker.scan_finished.connect(self._on_scan_complete)
        self._scan_worker.scan_error.connect(self._on_scan_error)
        self._scan_worker.status_update.connect(
            lambda msg: self.window()._update_status(msg) if hasattr(self.window(), '_update_status') else None
        )

        self._scan_worker.scan_finished.connect(self._scan_thread.quit)
        self._scan_worker.scan_error.connect(self._scan_thread.quit)
        self._scan_thread.finished.connect(self._scan_worker.deleteLater)
        self._scan_thread.finished.connect(self._scan_thread.deleteLater)

        self._scan_thread.start()

    def _run_json_scan(self):
        """Executes a targeted whitelist scan dynamically populated by parsed JSON filenames."""
        ok, msg = self.validate_for_scan()
        if not ok:
            QMessageBox.critical(self, "Input Error", msg)
            return

        dialog = QtJsonScanDialog(self)
        if not dialog.exec():
            return

        req_files_lower = {f.lower() for f in dialog.req_files}
        found_files = {}

        scan_dir = os.path.normpath(self.scan_dir_entry.text())
        tree_blacklist = {os.path.normpath(p) for p in self.directory_tree_blacklist}
        
        self._load_default_ignore_patterns()
        folder_patterns = self.default_ignore_patterns.get('folder',[])

        # Traverse directory, actively skipping blacklisted/ignored paths in-place
        for root, dirs, files in os.walk(scan_dir):
            norm_root = os.path.normpath(root)
            
            dirs[:] =[
                d for d in dirs
                if os.path.normpath(os.path.join(norm_root, d)) not in tree_blacklist
                and not any(fnmatch.fnmatch(d, p) for p in folder_patterns)
            ]

            for f in files:
                f_lower = f.lower()
                if f_lower in req_files_lower and f_lower not in found_files:
                    found_files[f_lower] = os.path.normpath(os.path.join(norm_root, f))
                    
            if len(found_files) == len(req_files_lower):
                break

        if len(found_files) == 0:
            QMessageBox.critical(self, "Scan Failed", "None of the requested files were found in the scope.")
            return

        missing = req_files_lower - set(found_files.keys())
        if missing:
            missing_str = "\n".join(missing)
            reply = QMessageBox.warning(
                self,
                "Missing Files",
                f"The following requested files were not found:\n{missing_str}\n\nProceed with the found files?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No
            )
            if reply == QMessageBox.StandardButton.No:
                return

        save_path = self.save_path_entry.text()
        save_dir = os.path.dirname(save_path)
        if save_dir and not os.path.exists(save_dir):
            try:
                os.makedirs(save_dir, exist_ok=True)
            except Exception as e:
                QMessageBox.critical(self, "Input Error", f"Could not create save directory:\n{save_dir}\nError: {e}")
                return

        self.run_scan_btn.setEnabled(False)
        self.run_copy_btn.setEnabled(False)
        self.run_json_btn.setEnabled(False)

        # Build scan parameters targeting only the found matches
        scan_params = {
            'scan_dir_norm': scan_dir,
            'save_path_norm': os.path.normpath(save_path),
            'rules_files': list(found_files.values()),
            'rules_folders':[],
            'filter_mode': app_config.FILTER_WHITELIST,
            'rules_path_display': "Targeted JSON Scan",
            'rules_dirty': False,
            'generate_tree': self.generate_tree_check.isChecked(),
            'tree_blacklist': list(self.directory_tree_blacklist),
            'copy_to_clipboard': False,
        }

        self._scan_thread = QThread(self)
        self._scan_worker = ScanWorker(scan_params)
        self._scan_worker.moveToThread(self._scan_thread)

        self._scan_thread.started.connect(self._scan_worker.run)
        self._scan_worker.scan_finished.connect(self._on_scan_complete)
        self._scan_worker.scan_error.connect(self._on_scan_error)
        self._scan_worker.status_update.connect(
            lambda msg: self.window()._update_status(msg) if hasattr(self.window(), '_update_status') else None
        )

        self._scan_worker.scan_finished.connect(self._scan_thread.quit)
        self._scan_worker.scan_error.connect(self._scan_thread.quit)
        self._scan_thread.finished.connect(self._scan_worker.deleteLater)
        self._scan_thread.finished.connect(self._scan_thread.deleteLater)

        self._scan_thread.start()

    def _on_scan_complete(self, save_path: str):
        self.run_scan_btn.setEnabled(True)
        self.run_copy_btn.setEnabled(True)
        self.run_json_btn.setEnabled(True)

        p = self._scan_worker.scan_params
        if hasattr(self.window(), '_update_status'):
            self.window()._update_status(f"Scan complete. Output saved to: {save_path}", 10000)

        if p.get('copy_to_clipboard'):
            try:
                with open(save_path, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()
                QApplication.clipboard().setText(content)
                QMessageBox.information(self, "Scan Complete",
                                        f"Output saved to:\n{save_path}\n\n✅ Contents copied to clipboard!")
            except Exception as e:
                QMessageBox.warning(self, "Clipboard Error",
                                    f"Scan saved successfully but clipboard copy failed:\n{e}")
        else:
            QMessageBox.information(self, "Scan Complete", f"Output successfully saved to:\n{save_path}")

    def _on_scan_error(self, error_msg: str, tb: str):
        self.run_scan_btn.setEnabled(True)
        self.run_copy_btn.setEnabled(True)
        self.run_json_btn.setEnabled(True)
        if hasattr(self.window(), '_update_status'):
            self.window()._update_status(f"Error during scan: {error_msg}", 10000)
        print(f"Full scan error:\n{tb}")
        QMessageBox.critical(self, "Scan Error", f"An error occurred:\n{error_msg}\nSee console for details.")


# ---------------------------------------------------------------------------
# CodeScannerApp – Main Window
# ---------------------------------------------------------------------------

MAX_TABS = 3


class CodeScannerApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Codebase Scanner")
        self.setMinimumSize(900, 750)
        self.resize(1150, 900)

        self.profiles, self.last_active_profile_name = profile_handler.load_profiles(app_config.PROFILES_PATH)
        self.last_active_profile_name: str | None = self.last_active_profile_name

        self._setup_ui()
        self._open_initial_tab()
        self._update_window_title()

    # ------------------------------------------------------------------
    # UI Setup
    # ------------------------------------------------------------------

    def _setup_ui(self):
        self.setStyleSheet(DARK_THEME_STYLESHEET)
        self._setup_menu()

        self.tab_widget = QTabWidget()
        self.tab_widget.setTabsClosable(True)
        self.tab_widget.tabCloseRequested.connect(self._close_tab)
        self.tab_widget.currentChanged.connect(self._on_tab_changed)
        self.setCentralWidget(self.tab_widget)

        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)

    def _setup_menu(self):
        menubar = self.menuBar()

        # Profiles menu
        profile_menu = menubar.addMenu("Profiles")
        self.update_profile_action = profile_menu.addAction("Update Current Profile", self._update_current_profile)
        profile_menu.addAction("Save Profile As…", self._save_profile_dialog)
        profile_menu.addSeparator()
        profile_menu.addAction("Manage Profiles…", self._manage_profiles_dialog)

        # Workspace menu
        ws_menu = menubar.addMenu("Workspace")
        self.new_tab_action = ws_menu.addAction("New Tab", self._add_tab)
        self.new_tab_action.setShortcut("Ctrl+T")

    # ------------------------------------------------------------------
    # Tab helpers
    # ------------------------------------------------------------------

    def _open_initial_tab(self):
        tab = self._create_tab()
        if self.last_active_profile_name and self.last_active_profile_name in self.profiles:
            tab.apply_profile_settings(self.last_active_profile_name, self.profiles)
            self._refresh_tab_title(0)
        self._update_new_tab_action()

    def _create_tab(self) -> "WorkspaceTab":
        tab = WorkspaceTab(self.profiles, parent=self)
        tab.dirty_changed.connect(lambda _: self._refresh_current_tab_title())
        idx = self.tab_widget.addTab(tab, "New Tab")
        self.tab_widget.setCurrentIndex(idx)
        return tab

    def _add_tab(self):
        if self.tab_widget.count() >= MAX_TABS:
            QMessageBox.information(self, "Tab Limit Reached",
                                    f"A maximum of {MAX_TABS} workspace tabs are allowed.")
            return
        self._create_tab()
        self._update_new_tab_action()

    def _close_tab(self, index: int):
        tab = self.tab_widget.widget(index)
        if not isinstance(tab, WorkspaceTab):
            self.tab_widget.removeTab(index)
            return
        if tab.rules_dirty:
            reply = QMessageBox.question(
                self, "Unsaved Changes",
                "This workspace has unsaved rule changes. Close anyway?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if reply == QMessageBox.StandardButton.No:
                return
        self.tab_widget.removeTab(index)
        if self.tab_widget.count() == 0:
            self._create_tab()
        self._update_new_tab_action()

    def _update_new_tab_action(self):
        self.new_tab_action.setEnabled(self.tab_widget.count() < MAX_TABS)

    def _current_tab(self) -> "WorkspaceTab | None":
        w = self.tab_widget.currentWidget()
        return w if isinstance(w, WorkspaceTab) else None

    def _refresh_tab_title(self, index: int):
        tab: WorkspaceTab = self.tab_widget.widget(index)
        if not isinstance(tab, WorkspaceTab):
            return
        name = tab.active_profile_name or "New Tab"
        dirty = " *" if tab.rules_dirty else ""
        self.tab_widget.setTabText(index, f"{name}{dirty}")

    def _refresh_current_tab_title(self):
        idx = self.tab_widget.currentIndex()
        if idx >= 0:
            self._refresh_tab_title(idx)
        self._update_window_title()

    def _on_tab_changed(self, index: int):
        self._update_window_title()
        self._update_profile_menu_state()

    # ------------------------------------------------------------------
    # Status bar
    # ------------------------------------------------------------------

    def _update_status(self, message: str, clear_after_ms: int = 0):
        self.status_bar.showMessage(message, clear_after_ms)

    def _update_window_title(self):
        tab = self._current_tab()
        title = "Codebase Scanner"
        if tab and tab.active_profile_name:
            dirty = "*" if tab.rules_dirty else ""
            title += f" – Profile: {tab.active_profile_name}{dirty}"
        elif tab and tab.rules_dirty:
            title += " – Unsaved Changes*"
        self.setWindowTitle(title)

    # ------------------------------------------------------------------
    # Profile management (delegates to current tab)
    # ------------------------------------------------------------------

    def _update_profile_menu_state(self):
        tab = self._current_tab()
        self.update_profile_action.setEnabled(bool(tab and tab.active_profile_name))

    def _update_current_profile(self):
        tab = self._current_tab()
        if not tab or not tab.active_profile_name:
            return
        reply = QMessageBox.question(
            self, "Confirm Update",
            f"Update profile '{tab.active_profile_name}' with the current settings?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.No:
            return
        if self._save_profile(tab, tab.active_profile_name):
            self._update_status(f"Profile '{tab.active_profile_name}' updated.", 4000)

    def _save_profile_dialog(self):
        tab = self._current_tab()
        if not tab:
            return
        name, ok = QInputDialog.getText(self, "Save Profile As", "Enter a new profile name:")
        if not ok or not name:
            return
        clean = "".join(c for c in name if c.isalnum() or c in (' ', '_', '-')).strip()
        if not clean:
            QMessageBox.warning(self, "Invalid Name", "Profile name cannot be empty or only special characters.")
            return
        if clean in self.profiles:
            reply = QMessageBox.question(self, "Overwrite Profile",
                                         f"Profile '{clean}' already exists. Overwrite?",
                                         QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            if reply == QMessageBox.StandardButton.No:
                return
        if self._save_profile(tab, clean):
            self._update_status(f"Profile '{clean}' saved.", 3000)

    def _save_profile(self, tab: "WorkspaceTab", profile_name: str) -> bool:
        scan_dir = tab.scan_dir_entry.text()
        save_fp = tab.save_path_entry.text()
        if not scan_dir or not os.path.isdir(scan_dir):
            QMessageBox.warning(self, "Incomplete Configuration", "Scan directory must be a valid directory.")
            return False
        if not save_fp:
            QMessageBox.warning(self, "Incomplete Configuration", "Save output path must be set.")
            return False

        if tab.rules_dirty and tab.current_rules_filepath:
            reply = QMessageBox.question(
                self, "Unsaved Rules",
                "The current scan rules have unsaved changes. Save them before saving the profile?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No | QMessageBox.StandardButton.Cancel,
            )
            if reply == QMessageBox.StandardButton.Yes:
                if not tab._save_rules_list_changes():
                    return False
            elif reply == QMessageBox.StandardButton.Cancel:
                return False

        self.profiles[profile_name] = tab.get_profile_data()
        tab.active_profile_name = profile_name
        self.last_active_profile_name = profile_name

        try:
            profile_handler.save_profiles(self.profiles, self.last_active_profile_name, app_config.PROFILES_PATH)
            tab._set_dirty(False)
            self._refresh_current_tab_title()
            self._update_window_title()
            self._update_profile_menu_state()
            return True
        except Exception as e:
            QMessageBox.critical(self, "Profile Save Error", f"Could not save profiles:\n{e}")
            return False

    def _manage_profiles_dialog(self):
        tab = self._current_tab()
        active_name = tab.active_profile_name if tab else None
        dialog = QtManageProfilesDialog(self, self.profiles, active_name, self)
        dialog.exec()

    def _execute_load_profile(self, profile_name: str) -> bool:
        tab = self._current_tab()
        if not tab:
            return False
        result = tab.apply_profile_settings(profile_name, self.profiles)
        if result:
            self.last_active_profile_name = profile_name
            try:
                profile_handler.save_profiles(self.profiles, self.last_active_profile_name, app_config.PROFILES_PATH)
            except Exception:
                pass
            self._refresh_current_tab_title()
            self._update_window_title()
            self._update_profile_menu_state()
            self._update_status(f"Profile '{profile_name}' loaded.", 3000)
        return result

    def _execute_delete_profile(self, profile_name: str) -> bool:
        if profile_name not in self.profiles:
            return False
        del self.profiles[profile_name]
        if self.last_active_profile_name == profile_name:
            self.last_active_profile_name = None

        for i in range(self.tab_widget.count()):
            tab: WorkspaceTab = self.tab_widget.widget(i)
            if isinstance(tab, WorkspaceTab) and tab.active_profile_name == profile_name:
                tab.active_profile_name = None
                self._refresh_tab_title(i)

        try:
            profile_handler.save_profiles(self.profiles, self.last_active_profile_name, app_config.PROFILES_PATH)
            self._update_status(f"Profile '{profile_name}' deleted.", 3000)
            self._update_window_title()
            self._update_profile_menu_state()
            return True
        except Exception as e:
            QMessageBox.critical(self, "Profile Save Error", f"Could not save profile changes after deletion:\n{e}")
            return False


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyleSheet(DARK_THEME_STYLESHEET)
    window = CodeScannerApp()
    window.show()
    sys.exit(app.exec())