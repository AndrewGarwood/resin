"""
*`@module`* `utils/__init__`
"""

from . import winauto, runtime
from .exceptions import *
from ._clipboard import (default_copy_to_clipboard, SUPPORTED_PLATFORMS)