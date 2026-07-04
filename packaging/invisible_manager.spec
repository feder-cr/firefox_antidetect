# PyInstaller spec — invisible_manager (onedir, cross-platform).
# Build:  pyinstaller packaging/invisible_manager.spec
# The patched Firefox binary is NOT bundled — ensure_binary() downloads it on
# first launch. invisible_core's data files (fpforge JSONs, font-map) are
# collected so profile generation works inside the frozen app.
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

block_cipher = None

datas = collect_data_files("invisible_core")  # _fpforge/data/*.json, data/font-map.json
hiddenimports = (
    collect_submodules("invisible_core")
    + collect_submodules("invisible_manager")
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
    name="invisible_manager",
    console=False,  # GUI app — no console window
)
coll = COLLECT(
    exe, a.binaries, a.zipfiles, a.datas,
    name="invisible_manager",
)
