"""PyInstaller entry point — bootstraps the Qt app."""
from firefox_antidetect.ui.app import run

if __name__ == "__main__":
    raise SystemExit(run())
