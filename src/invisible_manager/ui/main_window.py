from PySide6 import QtWidgets


class MainWindow(QtWidgets.QMainWindow):
    """Placeholder — replaced with the full list+toolbar in Task 3.4."""

    def __init__(self, store, launcher):
        super().__init__()
        self._store = store
        self._launcher = launcher
        self.setWindowTitle("invisible_manager")
