# Windows onedir bundle: only runtime assets and required package data.
from pathlib import Path
from PyInstaller.utils.hooks import collect_data_files

root = Path(SPECPATH)
datas = collect_data_files("customtkinter") + [
    (str(root / "assets/javeriana_logo.png"), "assets"),
    (str(root / "config/vision.example.yaml"), "config"),
    (str(root / "config/app.example.yaml"), "config"),
]
a = Analysis(
    [str(root / "src/ur_tictactoe/desktop_entry.py")],
    pathex=[str(root / "src")],
    binaries=[], datas=datas, hiddenimports=[],
    hookspath=[], runtime_hooks=[],
    excludes=["pytest", "tests"], noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz, a.scripts, [], exclude_binaries=True, name="RobotTriqui",
    debug=False, bootloader_ignore_signals=False, strip=False, upx=False,
    console=False,
)
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name="RobotTriqui")
