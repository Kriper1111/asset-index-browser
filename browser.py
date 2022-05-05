import json
import pathlib
import shutil
import sys
import traceback
from threading import Event
from typing import Dict, List, Literal, Optional, Tuple, Union, cast

from display import Align, DisplayManager, IListElement
from input_manager import IInputListener
from logger import logger


class AssetIndexBrowser(IInputListener):
    FILE_TYPES = {
        ".mcmeta": "text",
        ".txt": "text",
        ".json": "text",
        ".lang": "text",
        ".png": "image",
        ".ogg": "sound",
    }

    def __init__(self):
        self.asset_folder: pathlib.Path
        self.asset_index_name: str
        self.display_manager: DisplayManager

        self.asset_index_tree: "AssetTreeElement"
        self.termination = Event()

    def load_index(self, asset_index_path):
        asset_index = pathlib.Path(asset_index_path)
        with open(asset_index, "r") as ai:
            asset_index_json = json.load(ai)

        self.asset_folder = asset_index.parent.parent
        self.asset_index_name = asset_index.stem
        self.asset_index_tree = AssetIndex(asset_index_json).get_file_tree()

    def await_termination(self):
        self.display_manager = DisplayManager()
        self.display_manager.start()
        self.display_manager.set_title(f"Asset index: {self.asset_index_name}")
        self.display_manager.preview.set_text("Select a file to preview", horizontal_align=Align.CENTER, vertical_align=Align.CENTER)
        self.display_manager.list_view.set_style("COLOR_BLUE", {"entry_type": "entry:directory"})
        self.display_manager.list_view.set_list(self.asset_index_tree.list_folder())
        self.display_manager.input_manager.add_listener(self)
        self.termination.wait()

    def terminate(self):
        # logger.info("AssetBrowser", "Terminating..")
        self.display_manager.stop()
        self.termination.set()

    def on_key(self, key_code):
        if key_code == "Q":
            self.terminate()
        elif key_code == "KEY_UP":
            self.display_manager.list_view.next()
        elif key_code == "KEY_DOWN":
            self.display_manager.list_view.prev()
        elif key_code == "+" or key_code == " " or key_code == "\n":
            self.display_manager.preview.set_text("Select a file to preview", horizontal_align=Align.CENTER, vertical_align=Align.CENTER)
            selected_file = self.get_selected_file()

            if selected_file.entry_type == 'entry:directory':
                if not selected_file.expanded:
                    self.display_manager.list_view.insert_items(selected_file.list_folder())
                    selected_file.expanded = True
                else:
                    self.display_manager.list_view.collapse_items(selected_file.count_expanded_children())
                    selected_file.expanded = False
            elif selected_file.entry_type == 'entry:file':
                file_preview = self.get_file_preview(selected_file)
                if not file_preview[1]:
                    reason = "This file cannot be previewed "
                    if file_preview[0] == "none": reason += "because this file does not exist."
                    elif file_preview[0] == "unknown": reason += "because it's format is not recognized."
                    else: reason += "because it's not a text file"
                    self.display_manager.preview.set_text(
                        reason,
                        horizontal_align=Align.CENTER,
                        vertical_align=Align.CENTER
                    )
                else:
                    self.display_manager.preview.set_text(file_preview[1])
        elif key_code == "X":
            selected_file = self.get_selected_file()
            self.extract_entry(selected_file)

    def extract_entry(self, asset_file: "AssetTreeElement"):
        for _, _, children in asset_file.walk_tree():
            for file in children:
                version_folder = self.asset_folder.joinpath(self.asset_index_name)
                destination = version_folder.joinpath(file.entry_name)
                if destination.exists(): return # TODO: override prompt?

                version_folder.mkdir(exist_ok=True, parents=True)
                destination.parent.mkdir(exist_ok=True, parents=True)

                entry_path = self.asset_folder.joinpath("objects").joinpath(file.entry_hash[:2]).joinpath(file.entry_hash)
                try: shutil.copy(entry_path, destination)
                except Exception:
                    logger.error("AssetBrowser", f"Real file for {file.entry_name} not found!")
                    # logger.debug("AssetBrowser", f"Real file searched at: {entry_path}")

    def get_selected_file(self) -> "AssetTreeElement":
        selected_file = cast("AssetTreeElement", self.display_manager.list_view.get_value())
        if selected_file.entry_type == "entry:file":
            # It's a file
            asset_hash = selected_file.entry_hash
            selected_file.entry_path = self.asset_folder.joinpath("objects").joinpath(asset_hash[:2]).joinpath(asset_hash)
        return selected_file

    def get_file_preview(self, asset_file: "AssetTreeElement") -> Tuple[str, str]:
        if not asset_file.entry_path.exists():
            logger.warn("AssetBrowser", "Attempted to preview a file but it didn't exist")
            return "none", ""

        file_type = self.FILE_TYPES.get(asset_file.entry_name.suffix, "unknown")
        logger.debug("AssetBrowser", f"Parsed {asset_file.entry_name.suffix} as {file_type}")

        file_preview = ""
        if file_type == "text":
            try:
                with open(asset_file.entry_path, "r") as text_asset: file_preview = text_asset.read(1024)
            except UnicodeDecodeError:
                logger.warn("AssetBrowser", f"Failed to generate a preview for {asset_file.entry_name}")
                file_type = "unknown"
        return file_type, file_preview

    def on_resize(self, key_code):
        pass

class AssetIndex:
    class AssetIndexElement:
        virtual_path: pathlib.PurePath
        asset_hash: str
        asset_size: int

        def __repr__(self) -> str:
            return f"<File of AssetIndex('{self.virtual_path}')>"

    def __init__(self, asset_index_json):
        self.asset_index = asset_index_json["objects"]
        self.asset_list: List[AssetIndex.AssetIndexElement] = []
        for object_name, metadata in self.asset_index.items():
            asset_index_element = self.AssetIndexElement()
            asset_index_element.virtual_path = pathlib.PurePath(object_name)
            asset_index_element.asset_hash = metadata.get("hash")
            asset_index_element.asset_size = metadata.get("size", -1)
            self.asset_list.append(asset_index_element)

    def get_file_tree(self):
        file_tree = AssetTreeElement()
        for asset in self.asset_list:
            current_dir = file_tree
            for part in asset.virtual_path.parts:
                if not current_dir.has_folder(part):
                    current_dir.create_folder(part)
                current_dir = current_dir.get_folder(part)
            current_dir.entry_type = "entry:file"
            current_dir.entry_hash = asset.asset_hash
            current_dir.entry_name = asset.virtual_path
        return file_tree

AssetTreeEntryType = Union[Literal["entry:file"], Literal["entry:directory"]]

# This could be done with dicts.. Maybe I'll revert to them
class AssetTreeElement(IListElement):
    object_name: str = "."
    depth: int = -1
    entry_type: AssetTreeEntryType = "entry:directory"
    children: Dict[str, "AssetTreeElement"]
    entry_hash: str
    entry_name: pathlib.PurePath
    entry_path: pathlib.Path
    expanded: bool = False

    @property
    def name(self):
        return ("  " * self.depth) + self.object_name

    def __init__(self) -> None:
        self.children = {}

    def has_folder(self, name):
        return self.children.get(name) is not None

    def get_folder(self, name):
        return self.children[name]

    def create_folder(self, name):
        folder = AssetTreeElement()
        folder.object_name = name
        folder.entry_type = "entry:directory"
        folder.depth = self.depth + 1
        self.children.update({name: folder})

    def list_folder(self):
        return list(self.children.values())

    def walk_tree(self):
        walk_objects = [self]
        while walk_objects:
            new_walk_objects = []
            for root in walk_objects:
                contents = root.list_folder()
                folders = list(filter(lambda fo: fo.entry_type == "entry:directory", contents))
                files = list(filter(lambda fo: fo.entry_type == "entry:file", contents))
                yield root, folders, files
                new_walk_objects.extend(contents)
            walk_objects.clear()
            walk_objects.extend(new_walk_objects)

    def count_expanded_children(self):
        child_count = 0
        for root, dirs, files in self.walk_tree():
            if root.expanded:
                child_count += len(dirs)
                child_count += len(files)
        return child_count

    def __repr__(self) -> str:
        return f"<{'Folder' if self.entry_type == 'entry:directory' else 'File' } object ('{self.name}')>"

def setup():
    try:
        asset_index = sys.argv[1]
    except IndexError:
        print("Please provide a path to an asset index to browse")
        return

    asset_index_browser = AssetIndexBrowser()
    try:
        asset_index_browser.load_index(asset_index)
        asset_index_browser.await_termination()
    except Exception:
        asset_index_browser.terminate()
        traceback.print_exc()
    except KeyboardInterrupt:
        logger.warn("AssetBrowser", "Keyboard Interrupt!")
        asset_index_browser.terminate()

if __name__ == "__main__":
    setup()
