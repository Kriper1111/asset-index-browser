# Minecraft Asset Index Browser

*Powered by Python `curses` binding*

TUI-based asset index browser for Minecraft asset lists (json files in `assets/indexes/$version.json`). Supports very basic text preview and file/folder "extraction". By extraction I mean copying the file from objects to `assets/$version/` with proper paths.

## Requirements:
* Python 3.7 at least?
* `windows-curses` on Windows.

*I'm not sure whether 3.7 is the minimum, but it seems like the safest bet.*

## Usage:
Run `browser.py` with the *preferrably* absolute path to the asset index JSON.

In the application:
* [Arrow Up] and [Arrow Down] to move selection
* [Space], [Enter] or [+] to expand selection
* [Key X] to extract the selection
* [Key Q] to exit
