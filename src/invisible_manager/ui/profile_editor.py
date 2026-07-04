from __future__ import annotations

from typing import Optional

from PySide6 import QtWidgets

from ..manager.models import Profile
from .fingerprint_panel import FingerprintPanel


class ProfileEditor(QtWidgets.QDialog):
    """Create or edit a profile. Thin — builds/updates a Profile from the form."""

    def __init__(self, profile: Optional[Profile] = None, parent=None):
        super().__init__(parent)
        self._profile = profile
        self.setWindowTitle("Profile" if profile is None else f"Edit {profile.name}")

        self.name = QtWidgets.QLineEdit()
        self.seed = QtWidgets.QLineEdit()
        self.proxy_server = QtWidgets.QLineEdit()
        self.proxy_user = QtWidgets.QLineEdit()
        self.proxy_pass = QtWidgets.QLineEdit()
        self.proxy_pass.setEchoMode(QtWidgets.QLineEdit.EchoMode.Password)
        self.locale = QtWidgets.QLineEdit("auto")
        self.timezone = QtWidgets.QLineEdit("auto")

        form = QtWidgets.QFormLayout()
        form.addRow("Name", self.name)
        form.addRow("Seed", self.seed)
        form.addRow("Proxy server", self.proxy_server)
        form.addRow("Proxy user", self.proxy_user)
        form.addRow("Proxy pass", self.proxy_pass)
        form.addRow("Locale", self.locale)
        form.addRow("Timezone", self.timezone)

        self._fp = FingerprintPanel()
        preview = QtWidgets.QPushButton("Preview fingerprint")
        preview.clicked.connect(self._on_preview)

        buttons = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.StandardButton.Ok
            | QtWidgets.QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        root = QtWidgets.QVBoxLayout(self)
        root.addLayout(form)
        root.addWidget(preview)
        root.addWidget(self._fp)
        root.addWidget(buttons)

        if profile is not None:
            self.set_fields(
                name=profile.name, seed=profile.seed,
                proxy_server=(profile.proxy or {}).get("server", ""),
                proxy_user=(profile.proxy or {}).get("username", ""),
                proxy_pass=(profile.proxy or {}).get("password", ""),
                locale=profile.locale, timezone=profile.timezone,
            )

    def set_fields(self, name="", seed=0, proxy_server="", proxy_user="",
                   proxy_pass="", locale="auto", timezone="auto") -> None:
        self.name.setText(name)
        self.seed.setText(str(seed))
        self.proxy_server.setText(proxy_server)
        self.proxy_user.setText(proxy_user)
        self.proxy_pass.setText(proxy_pass)
        self.locale.setText(locale)
        self.timezone.setText(timezone)

    def _proxy(self) -> Optional[dict]:
        server = self.proxy_server.text().strip()
        if not server:
            return None
        proxy = {"server": server}
        if self.proxy_user.text().strip():
            proxy["username"] = self.proxy_user.text().strip()
        if self.proxy_pass.text():
            proxy["password"] = self.proxy_pass.text()
        return proxy

    def _on_preview(self) -> None:
        try:
            self._fp.show_seed(int(self.seed.text() or "0"))
        except ValueError:
            pass

    def to_profile(self) -> Profile:
        seed = int(self.seed.text() or "0")
        kw = dict(
            name=self.name.text(), seed=seed, proxy=self._proxy(),
            locale=self.locale.text().strip() or "auto",
            timezone=self.timezone.text().strip() or "auto",
        )
        if self._profile is not None:
            # editing: keep id + timestamps, overwrite the rest
            return Profile(
                id=self._profile.id,
                created_at=self._profile.created_at,
                last_used_at=self._profile.last_used_at,
                pin=self._profile.pin,
                binary_ver=self._profile.binary_ver,
                notes=self._profile.notes,
                **kw,
            )
        return Profile.new(**kw)
