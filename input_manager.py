import curses
import traceback
from typing import TYPE_CHECKING, Dict

from logger import logger

if TYPE_CHECKING:
    import _curses
    CursesWindow = _curses._CursesWindow

class IInputListener:
    def on_key(self, key: str) -> None: ...
    def on_resize(self) -> None: ...

class InputManager:
    def __init__(self):
        self.curse: "CursesWindow"
        self.listeners: Dict[int, IInputListener] = {}
        self.running = True

    # NOTE: Does not convert keys to key codes, i.e. layout-sensitive
    def dispatch_event(self):
        char = self.curse.get_wch()
        if isinstance(char, int):
            key_name = curses.keyname(char).decode()
        else: key_name = char.upper()

        for listener in self.listeners.values():
            try:
                if key_name == "KEY_RESIZE":
                    listener.on_resize()
                else:
                    listener.on_key(key_name)
            except:
                logger.warn("InputManager", f"Listener {type(listener)} has caused an error")
                logger.warn("InputManager", traceback.format_exc())

    def bind_window(self, stdscr: "CursesWindow"):
        self.curse = stdscr

    def remove_listener(self, listener):
        listener_hash = hash(listener)
        self.listeners.pop(listener_hash)

    def add_listener(self, listener: IInputListener):
        listener_hash = hash(listener)
        if self.listeners.get(listener_hash) is not None:
            raise KeyError("Listener already bound!")
        self.listeners.update({listener_hash: listener})
