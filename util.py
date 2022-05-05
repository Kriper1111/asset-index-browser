import pathlib
from math import floor

def clamp(value, value_min, value_max):
    return min(max(value, value_min), value_max)

SCRIPT_DIRECTORY = pathlib.Path(__file__).parent