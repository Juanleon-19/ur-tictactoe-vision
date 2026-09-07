"""Desktop application layer and Tkinter entry point."""

from ur_tictactoe.desktop.application import (
    AppConfig,
    ApplicationSnapshot,
    GameApplication,
)
from ur_tictactoe.desktop.real_backend import RealGameBackend

__all__ = ["AppConfig", "ApplicationSnapshot", "GameApplication", "RealGameBackend"]
