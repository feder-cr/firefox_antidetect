"""PyInstaller entry point — bootstraps the Qt app."""
from antidetect_firefox.ui.app import run

if __name__ == "__main__":
    raise SystemExit(run())
