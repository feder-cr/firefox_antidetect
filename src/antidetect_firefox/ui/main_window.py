from __future__ import annotations

from typing import Dict, List, Optional

from PySide6 import QtCore, QtGui, QtWidgets

from ..manager.models import Profile
from .profile_editor import ProfileEditor

try:  # optional import — the manager may be constructed with launcher=None in tests
    from invisible_core import GeoTimezoneError
except Exception:  # pragma: no cover
    class GeoTimezoneError(Exception):
        pass

_COLUMNS = ["Name", "Proxy", "Timezone", "Last used"]


class MainWindow(QtWidgets.QMainWindow):
    """Profile list + toolbar. Thin: every action calls the store/launcher."""

    def __init__(self, store, launcher):
        super().__init__()
        self._store = store
        self._launcher = launcher
        self._profiles: List[Profile] = []
        self._running: Dict[str, object] = {}  # profile_id -> LaunchHandle
        self.setWindowTitle("antidetect_firefox")
        self.resize(720, 420)

        self.table = QtWidgets.QTableWidget(0, len(_COLUMNS))
        self.table.setHorizontalHeaderLabels(_COLUMNS)
        self.table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.setCentralWidget(self.table)

        tb = self.addToolBar("actions")
        self._act("New", tb, self._on_new)
        self._act("Launch", tb, self._on_launch)
        self._act("Edit", tb, self._on_edit)
        self._act("Delete", tb, self._on_delete)

        self.refresh()

    def _act(self, label, toolbar, slot) -> QtGui.QAction:
        a = QtGui.QAction(label, self)
        a.triggered.connect(slot)
        toolbar.addAction(a)
        return a

    # ── data ────────────────────────────────────────────────────────────
    def refresh(self) -> None:
        self._profiles = self._store.list()
        self.table.setRowCount(len(self._profiles))
        for row, p in enumerate(self._profiles):
            running = " (running)" if p.id in self._running else ""
            cells = [
                p.name + running,
                (p.proxy or {}).get("server", "") if p.proxy else "—",
                p.timezone,
                p.last_used_at or "—",
            ]
            for col, text in enumerate(cells):
                self.table.setItem(row, col, QtWidgets.QTableWidgetItem(str(text)))

    def _selected(self) -> Optional[Profile]:
        row = self.table.currentRow()
        if 0 <= row < len(self._profiles):
            return self._profiles[row]
        return None

    # ── actions ─────────────────────────────────────────────────────────
    def _on_new(self) -> None:
        dlg = ProfileEditor(parent=self)
        if dlg.exec() == QtWidgets.QDialog.DialogCode.Accepted:
            self._store.create(dlg.to_profile())
            self.refresh()

    def _on_edit(self) -> None:
        p = self._selected()
        if p is None:
            return
        dlg = ProfileEditor(profile=p, parent=self)
        if dlg.exec() == QtWidgets.QDialog.DialogCode.Accepted:
            self._store.update(dlg.to_profile())
            self.refresh()

    def _on_launch(self) -> None:
        p = self._selected()
        if p is None or self._launcher is None:
            return
        if p.id in self._running:
            QtWidgets.QMessageBox.information(self, "Already running",
                                             f"'{p.name}' is already running.")
            return
        try:
            handle = self._launcher.launch(p)
        except GeoTimezoneError:
            QtWidgets.QMessageBox.warning(
                self, "Proxy unreachable",
                f"Could not reach the proxy for '{p.name}'. "
                "Fix the proxy or clear it, then try again.")
            return
        self._running[p.id] = handle
        self._store.touch(p.id)
        self.refresh()

    def _on_delete(self) -> None:
        p = self._selected()
        if p is None:
            return
        if QtWidgets.QMessageBox.question(
            self, "Delete profile", f"Delete '{p.name}'?"
        ) == QtWidgets.QMessageBox.StandardButton.Yes:
            self._delete_id(p.id)
            self.refresh()

    def _delete_id(self, profile_id: str) -> None:
        self._running.pop(profile_id, None)
        self._store.delete(profile_id)
