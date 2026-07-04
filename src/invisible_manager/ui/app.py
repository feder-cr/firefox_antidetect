from __future__ import annotations

import sys

from PySide6 import QtWidgets

from ..manager.store import ProfileStore
from ..manager import launcher as _launcher
from ..manager import paths
from .main_window import MainWindow


def build_main_window(store, launcher) -> QtWidgets.QMainWindow:
    return MainWindow(store, launcher)


def run() -> int:
    app = QtWidgets.QApplication(sys.argv)
    app.setApplicationName("invisible_manager")
    store = ProfileStore(paths.db_path())
    win = build_main_window(store, _launcher)
    win.show()
    return app.exec()
