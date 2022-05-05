import pathlib
import json
import sys
from threading import Event

from typing import List, Optional, Tuple
import traceback

from display import DisplayManager, Align
from input_manager import IInputListener
from logger import logger

class AssetIndexBrowser(IInputListener):
    def __init__(self):
        self.asset_folder: pathlib.Path
        self.asset_index_name: str
        self.display_manager: DisplayManager

        self.asset_index_tree = {}
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
        self.display_manager.list_view.set_list(list(self.asset_index_tree.keys()))
        self.display_manager.input_manager.add_listener(self)
        self.termination.wait()
    
    def terminate(self):
        logger.info("AssetBrowser", "Terminating..")
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
            logger.debug("AssetBrowser", f"Selected file {selected_file}")
            if selected_file is not None:
                file_preview = self.get_file_preview(selected_file)
                if file_preview == "":
                    self.display_manager.preview.set_text("This file cannot be previewed", horizontal_align=Align.CENTER, vertical_align=Align.CENTER)
                else:
                    self.display_manager.preview.set_text(file_preview[1])
        # else:
        #     logger.warn("AssetBrowser", f"Unprocessed keypress {key_code}")

    def get_selected_file(self) -> Optional[pathlib.Path]:
        selected_value = self.display_manager.list_view.get_value()
        if selected_value is None: return
        selected_file = self.asset_index_tree[selected_value]
        if selected_file.get("file:hash") is not None:
            # It's a file
            asset_hash: str = selected_file.get("file:hash")
            asset_path = self.asset_folder.joinpath("objects").joinpath(asset_hash[:2]).joinpath(asset_hash)
            return asset_path

    def get_file_preview(self, asset_file: pathlib.Path) -> Tuple[str, str]:
        if not asset_file.exists():
            logger.warn("AssetBrowser", "Attempted to preview a file but it didn't exist")
            return "none", ""
        with open(asset_file, "rb") as asset:
            signature = asset.read(4)
        file_type = "text"
        file_preview = ""
        if signature == b"OggS":
            file_type = "ogg"
        if signature == b"\x89PNG":
            file_type = "png"
        if file_type == "text":
            try:
                with open(asset_file, "r") as text_asset:
                    file_preview = text_asset.read(1024)
            except UnicodeDecodeError:
                file_type = "unknown"
        logger.debug("AssetBrowser", f"File type: {file_type}")
        return file_type, file_preview

    def on_resize(self, key_code):
        pass

class AssetIndex:
    class AssetIndexElement:
        virtual_path: pathlib.PurePath
        asset_hash: str
        asset_size: int

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
        file_tree = {}
        for asset in self.asset_list:
            current_dir = file_tree
            for part in asset.virtual_path.parts:
                if current_dir.get(part) is None:
                    current_dir.update({part: {}})
                current_dir = current_dir[part]
            current_dir.update({"file:hash": str(asset.asset_hash)})
        return file_tree

class AssetTreeElement:
    name = ""
    entry_type = ""
    children = []
    entry_hash = ""

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
