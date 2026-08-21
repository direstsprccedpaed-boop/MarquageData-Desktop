import sys
import os
from pathlib import Path


def resource_path(relative_path: str) -> Path:
    """Resolve asset path both in dev mode and PyInstaller frozen mode (_MEIPASS)."""
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        base_path = Path(sys._MEIPASS)
    else:
        base_path = Path(__file__).resolve().parent.parent.parent
    return base_path / relative_path


def app_data_dir() -> Path:
    """Persistent local storage directory: %APPDATA%/MarquageDataApp/ on Windows,
    fallback to home directory on other OS."""
    appdata = os.environ.get("APPDATA")
    base = Path(appdata) if appdata else Path.home() / ".marquagedata"
    target = base / "MarquageDataApp"
    (target / "staging" / "raw_texts").mkdir(parents=True, exist_ok=True)
    (target / "data").mkdir(parents=True, exist_ok=True)
    (target / "output").mkdir(parents=True, exist_ok=True)
    return target
