# PyInstaller spec — firefox_antidetect (onedir, cross-platform).
# Build:  pyinstaller packaging/firefox_antidetect.spec
# The patched Firefox binary is NOT bundled — ensure_binary() downloads it on
# first launch. invisible_core's data files (fpforge JSONs, font-map) are
# collected so profile generation works inside the frozen app.
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

block_cipher = None

datas = collect_data_files("invisible_core")  # _fpforge/data/*.json, data/font-map.json
datas += collect_data_files("firefox_antidetect", includes=["**/*.html"])  # ui/web/index.html
hiddenimports = (
    collect_submodules("invisible_core")
    + collect_submodules("firefox_antidetect")
    + collect_submodules("webview")  # pywebview platform backends (edgechromium/gtk/cocoa)
)

a = Analysis(
    ["run_manager.py"],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    runtime_hooks=[],
    excludes=[],
    cipher=block_cipher,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)
exe = EXE(
    pyz, a.scripts, [],
    exclude_binaries=True,
    name="firefox_antidetect",
    console=False,  # GUI app — no console window
)
coll = COLLECT(
    exe, a.binaries, a.zipfiles, a.datas,
    name="firefox_antidetect",
)
