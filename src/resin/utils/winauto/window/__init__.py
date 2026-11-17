"""
*`@module`* `utils/winauto/window/__init__`
"""

from ._legacy import *
from ._process import *
from .window_class import *
from .options import *
from .state import (WindowState)

from ._find import *
from ._find import (by_spec as find_by_spec)