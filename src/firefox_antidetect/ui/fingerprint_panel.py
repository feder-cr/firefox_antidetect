from __future__ import annotations

from PySide6 import QtWidgets

from ..manager.fingerprint import fingerprint_summary


class FingerprintPanel(QtWidgets.QWidget):
    """Read-only view of a seed's fingerprint (GPU/screen/hw/fonts)."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._form = QtWidgets.QFormLayout(self)
        self._rows: dict[str, QtWidgets.QLabel] = {}

    def show_seed(self, seed: int, pin=None) -> None:
        summary = fingerprint_summary(seed, pin)
        while self._form.rowCount():
            self._form.removeRow(0)
        self._rows.clear()
        for k, v in summary.items():
            lbl = QtWidgets.QLabel(str(v))
            self._rows[k] = lbl
            self._form.addRow(k, lbl)

    def text_dump(self) -> str:
        return "\n".join(f"{k}: {lbl.text()}" for k, lbl in self._rows.items())
