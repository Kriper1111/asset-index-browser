import curses
import textwrap
from contextlib import contextmanager
from enum import Enum
from typing import TYPE_CHECKING, Any, Callable, Dict, List, NamedTuple, Union

from input_manager import IInputListener, InputManager
from logger import logger
from util import clamp, floor

TerminalSize = NamedTuple("TerminalSize", [("height", int), ("width", int)])
Window = NamedTuple("WindowSize", [("width", int), ("height", int), ("left", int), ("top", int)])
Number = Union[float, int]


if TYPE_CHECKING:
    import _curses
    CursesWindow = _curses._CursesWindow

class DisplayManager(IInputListener):
    def __init__(self):
        self.input_manager = InputManager()
        # self.panel_stack: List[DisplayPanel] = []
        self.stdscr: "CursesWindow"

    def start(self):
        self.init_curses()
        self.list_view = ListView(DisplayPanelProperties()
                .set_name("File view")
                .set_constraints(bottom=3)
                .set_size(width=0.4)
                .set_borders(vertical=True))
        self.preview = Panel(DisplayPanelProperties()
                .set_name("File preview")
                .set_constraints(left=0.4, bottom=3)
                .set_size(width=0.6)
                .set_alignment(horizontal=Align.RIGHT))
        self.status_panel = Panel(DisplayPanelProperties()
                .set_name("Status panel")
                .set_constraints(bottom=0)
                .set_alignment(vertical=Align.BOTTOM)
                .set_size(height=3)
                .set_borders(horizontal=True))
        self.title = "Window Title"
        self.recalculate_layout()
        self.input_manager.bind_window(self.stdscr)
        self.input_manager.add_listener(self)
        self.input_manager.start()

    def stop(self):
        self.input_manager.stop()
        self.stop_curses()

    def recalculate_layout(self):
        terminal_size = TerminalSize(*self.stdscr.getmaxyx())
        self.stdscr.refresh()

        self.list_view.recalculate_layout(terminal_size)
        self.preview.recalculate_layout(terminal_size)
        self.status_panel.recalculate_layout(terminal_size)
        self.stdscr.hline("=", terminal_size.width)
        self.stdscr.hline(terminal_size.height - 1, 0, "=", terminal_size.width)

        self.draw_title()

    def on_resize(self):
        self.recalculate_layout()

    def on_key(self, keycode): pass

    def set_title(self, title: str):
        self.title = title
        self.draw_title()

    def draw_title(self):
        title_pos = (self.stdscr.getmaxyx()[1] - len(self.title) - 2) // 2
        terminal_size = TerminalSize(*self.stdscr.getmaxyx())
        self.stdscr.hline(0, 0, "=", terminal_size.width)
        self.stdscr.addstr(0, title_pos, f" {self.title} ")
        self.stdscr.refresh()

    def stop_curses(self):
        self.stdscr.keypad(False)
        curses.echo()
        curses.cbreak()
        curses.endwin()

    def init_curses(self): # Copied from curses.wrapper
        self.stdscr = curses.initscr()
        curses.noecho()
        curses.cbreak()
        self.stdscr.keypad(True)
        try:
            curses.start_color()
            curses.use_default_colors()
        except:
            pass

class Align(Enum):
    _ignore_ = ["offset_getters"]
    LEFT = 0
    TOP = 0
    CENTER = 1
    RIGHT = 2
    BOTTOM = 2

    offset_getters: Dict[int, Callable[[int, int], int]]

    def get_offset(self, length: int, max_size: int):
        offset_getter = self.offset_getters.get(self.value, self.offset_getters[0])
        return offset_getter(length, max_size)

Align.offset_getters = {
    0: lambda length, max_size: 0,
    1: lambda length, max_size: (max_size - length) // 2,
    2: lambda length, max_size: max_size - length
}

class DisplayPanelProperties:
    top: Number = 1
    left: Number = 0
    right: Number = 0
    bottom: Number = 1

    width: Number = 1.0
    height: Number = 1.0

    float_horizontal = Align.LEFT
    float_vertical = Align.TOP

    box_horizontal = False
    box_vertical = False

    registry_name = "DisplayPanel"

    def set_constraints(self, left: Number=None, top: Number=None, bottom: Number=None, right: Number=None):
        if top is not None: self.top = top
        if left is not None: self.left = left
        if right is not None: self.right = right
        if bottom is not None: self.bottom = bottom
        return self
    
    def set_alignment(self, horizontal: Align=None, vertical: Align=None):
        if horizontal: self.float_horizontal = horizontal
        if vertical: self.float_vertical = vertical
        return self
    
    def set_borders(self, vertical: bool=None, horizontal: bool=None):
        if vertical: self.box_vertical = vertical
        if horizontal: self.box_horizontal = horizontal
        return self
    
    def set_size(self, width: Number=None, height: Number=None):
        if width: self.width = width
        if height: self.height = height
        return self
    
    def set_name(self, name: str):
        self.registry_name = name
        return self

class DisplayPanel:
    properties: DisplayPanelProperties
    window: "CursesWindow"

    max_width: int
    max_height: int

    def __init__(self, properties: DisplayPanelProperties):
        self.properties = properties

        window = self.get_size(TerminalSize(10, 10))
        self.window = curses.newwin(window.height, window.width, window.top, window.left)

        self.max_width = window.width - 2
        self.max_height = window.height - 2

    def get_size(self, terminal_size: TerminalSize) -> Window:
        calculated_top = 0
        calculated_left = 0
        calculated_width = 0
        calculated_height = 0

        top = self.properties.top if isinstance(self.properties.top, int) else floor(self.properties.top * terminal_size.height)
        bottom = self.properties.bottom if isinstance(self.properties.bottom, int) else floor(self.properties.bottom * terminal_size.height)
        height = self.properties.height if isinstance(self.properties.height, int) else floor(self.properties.height * terminal_size.height)

        if self.properties.float_vertical == Align.TOP:
            leftover_height = terminal_size.height - top - bottom
            calculated_height = leftover_height if height == 0 else min(leftover_height, height)
            calculated_top = top
        elif self.properties.float_vertical == Align.CENTER:
            if height == 0: # 0 means 'auto'
                calculated_top = top
                calculated_height = terminal_size.height - top - bottom
            else: # It can resize in range of height..0
                leftover_height = terminal_size.height - top - bottom
                calculated_height = min(leftover_height, height)
                calculated_top = (terminal_size.height - calculated_height) // 2
        elif self.properties.float_vertical == Align.BOTTOM:
            leftover_height = terminal_size.height - top - bottom
            calculated_height = leftover_height if height == 0 else min(leftover_height, height)
            # calculated_height = terminal_size.height - bottom if height == 0 else height
            calculated_top = terminal_size.height - calculated_height

        left = self.properties.left if isinstance(self.properties.left, int) else floor(self.properties.left * terminal_size.width)
        right = self.properties.right if isinstance(self.properties.right, int) else floor(self.properties.right * terminal_size.width)
        width = self.properties.width if isinstance(self.properties.width, int) else floor(self.properties.width * terminal_size.width)

        # Assuming the process is the same for horizontals
        if self.properties.float_horizontal == Align.LEFT:
            calculated_left = left
            leftover_width = terminal_size.width - left - right
            calculated_width = leftover_width if width == 0 else min(leftover_width, width)
        elif self.properties.float_horizontal == Align.CENTER:
            if width == 0: # 0 means 'auto'
                calculated_left = left
                calculated_width = terminal_size.width - left - right
            else: # It can resize in range of width..0
                leftover_width = terminal_size.width - left - right
                calculated_width = min(leftover_width, width)
                calculated_left = (terminal_size.width - calculated_width) // 2
        elif self.properties.float_horizontal == Align.RIGHT:
            calculated_width = terminal_size.width - right if width == 0 else width
            calculated_left = terminal_size.width - calculated_width

        #     logger.debug("DisplayPanel", f"Resizing panel {self.properties.registry_name}")
        #     logger.debug("DisplayPanel", f"""Horizontal layout rules:
        # + Float: {self.properties.float_horizontal}
        # + Left: {self.properties.left}
        # + Right: {self.properties.right}
        # + Width: {self.properties.width}""")
        #     logger.debug("DisplayPanel", f"""Calculated layout:
        # + Width: {calculated_width}
        # + Height: {calculated_height}
        # + Top: {calculated_top}
        # + Left: {calculated_left}""")

        return Window(calculated_width, calculated_height, calculated_left, calculated_top)

    @contextmanager
    def begin_writing(self):
        try:
            self.window.clear()
            yield None
        finally:
            self.box()
            self.window.refresh()
    
    def add_string(self, y: int, x: int, string: str, attrs: int = 0):
        y += int(not self.properties.box_vertical)
        x += int(not self.properties.box_horizontal)
        try: self.window.addstr(y, x, string, attrs)
        except curses.error: pass

    def recalculate_layout(self, terminal_size: TerminalSize):
        window = self.get_size(terminal_size)

        self.window.mvwin(window.top, window.left)
        self.window.resize(window.height, window.width)

        self.max_width = window.width - (2 if self.properties.box_vertical else 0)
        self.max_height = window.height - (2 if self.properties.box_horizontal else 0)

        self.window.clear()
        self.box()
        self.window.refresh()

    def box(self, horizonal: bool=False, vertical: bool=False):
        if horizonal or self.properties.box_horizontal:
            self.window.hline(0, 0, "=", self.max_width + 2)
            self.window.hline(self.max_height + 1, 0, "=", self.max_width + 2)
        if vertical or self.properties.box_vertical:
            self.window.vline(0, 0, "|", self.max_height + 2)
            self.window.vline(0, self.max_width + 1, "|", self.max_height + 2)

    def refresh_contents(self):
        raise NotImplementedError()

class Panel(DisplayPanel):
    def __init__(self, properties: DisplayPanelProperties):
        super().__init__(properties)
        self.contents: str = ""

    def refresh_contents(self, horizontal_align: Align, vertical_align: Align):
        viewport = []

        for line in self.contents.splitlines()[:self.max_height]:
            viewport.extend(textwrap.wrap(line, self.max_width))

        viewport = viewport[:self.max_height]

        with self.begin_writing():
            lineno = vertical_align.get_offset(len(viewport), self.max_height)
            for line in viewport:
                line_offset = horizontal_align.get_offset(len(line), self.max_width)
                self.add_string(lineno, line_offset, line)
                lineno += 1

    def set_text(self, new_text: str, horizontal_align: Align = Align.LEFT, vertical_align: Align = Align.TOP):
        self.contents = new_text
        self.refresh_contents(horizontal_align, vertical_align)

class IListElement:
    name: str

class Colors:
    color_pair_count = 1 # 0th pair is the default color
    color_registry: Dict[str, int] = {}

    @classmethod
    def get_color(cls, forgeround=-1, background=-1):
        if forgeround == -1 and background == -1:
            raise ValueError("Invalid color pair!")

        color_pair_hash = f"{forgeround}:{background}"
        color_pair = cls.color_registry.get(color_pair_hash)
        if color_pair is None:
            if cls.color_pair_count + 1 > curses.COLOR_PAIRS:
                raise IndexError("Too many colors registered!")
            curses.init_pair(cls.color_pair_count, forgeround, background)
            color_pair = cls.color_pair_count
            cls.color_registry.update({color_pair_hash: color_pair})
            cls.color_pair_count += 1

        return color_pair

class ListView(DisplayPanel):
    class StyleRule:
        def __init__(self, color: int, predicate: Dict[str, Any]) -> None:
            self.color = Colors.get_color(color)
            self.predicate = predicate

        def match(self, target_object) -> bool:
            matches = True
            try:
                for key, value in self.predicate.items():
                    if getattr(target_object, key) != value:
                        matches = False
                        break
            except AttributeError:
                matches = False
            return matches

    def __init__(self, properties: DisplayPanelProperties):
        super().__init__(properties)
        self.cursor = 0
        self.scroll_offset = 0
        self.list: List[IListElement] = []
        self.styles: List["ListView.StyleRule"] = []

    def refresh_contents(self):
        with self.begin_writing():
            for index, entry in enumerate(self.list[self.scroll_offset:self.scroll_offset+self.max_height]):
                object_color = 0

                for rule in self.styles:
                    if rule.match(entry):
                        object_color = rule.color
                        break

                attribute = curses.A_REVERSE if index == (self.cursor - self.scroll_offset) else curses.color_pair(object_color)
                self.add_string(index, 0, entry.name, attribute)

    def set_style(self, color_name: str, predicate):
        color: int = getattr(curses, color_name)
        self.styles.append(self.StyleRule(color, predicate))

    def set_list(self, new_list):
        self.list = new_list
        self.cursor = clamp(self.cursor, 0, len(new_list) - 1)
        self.refresh_contents()

    def insert_items(self, new_list):
        for offset, item in enumerate(new_list, start=1):
            self.list.insert(self.cursor + offset, item)
        self.cursor = clamp(self.cursor, 0, len(self.list) - 1)
        self.refresh_contents()

    def collapse_items(self, item_count):
        before = len(self.list)
        self.list = self.list[:self.cursor + 1] + self.list[self.cursor + 1 + item_count:]
        after = len(self.list)
        logger.debug("ListView", f"Collapsed {before - after} items of {item_count}")
        self.cursor = clamp(self.cursor, 0, len(self.list) - 1)
        self.refresh_contents()

    def prev(self):
        if self.list:
            if self.cursor + 1 >= len(self.list): return
            self.cursor += 1
            if self.cursor - self.scroll_offset >= self.max_height:
                self.scroll_offset += 1
        self.refresh_contents()

    def next(self):
        if self.list:
            if self.cursor - 1 < 0: return
            self.cursor -= 1
            if self.cursor - self.scroll_offset < 0:
                self.scroll_offset -= 1
        self.refresh_contents()

    def get_value(self):
        if not self.list: raise IndexError("List is empty!")
        return self.list[self.cursor]
