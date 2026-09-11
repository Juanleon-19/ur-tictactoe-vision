# Windows onedir bundle: only runtime assets and required package data.
from pathlib import Path
import sys
from PyInstaller.utils.hooks import collect_data_files

root = Path(SPECPATH)
sys.path.insert(0, str(root / "scripts"))
from release_support import build_icon
icon = build_icon(root)
datas = collect_data_files("customtkinter") + [
    (str(root / "assets/javeriana_logo.png"), "assets"),
    (str(icon), "assets"),
    (str(root / "config/vision.example.yaml"), "config"),
    (str(root / "config/app.example.yaml"), "config"),
]
a = Analysis(
    [str(root / "src/ur_tictactoe/desktop_entry.py")],
    pathex=[str(root / "src")],
    binaries=[], datas=datas, hiddenimports=["cv2.aruco", "PIL._tkinter_finder", "pymodbus.client"],
    hookspath=[], runtime_hooks=[],
    excludes=["pytest", "tests", "ur_tictactoe.commissioning"], noarchive=False,
)
# Hook data can include cache/test directories; these are not runtime assets.
a.datas = [entry for entry in a.datas if not
           {"tests", "__pycache__", ".pytest_cache", "reports", ".git"}.intersection(Path(entry[0]).parts)]
pyz = PYZ(a.pure)
exe = EXE(
    pyz, a.scripts, [], exclude_binaries=True, name="RobotTriqui",
    debug=False, bootloader_ignore_signals=False, strip=False, upx=False,
    console=False, icon=str(icon), version=str(root / "packaging/version_info.txt"),
)
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name="RobotTriqui")
