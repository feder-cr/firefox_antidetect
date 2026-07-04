"""PyInstaller entry point — bootstraps the Qt app."""
from invisible_manager.ui.app import run

if __name__ == "__main__":
    raise SystemExit(run())
