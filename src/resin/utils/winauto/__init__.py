"""
*`@module`* `utils/winauto/__init__`
"""

# might be worth it moving this to separate package
from .debug import *
from .exceptions import *

from .control import *
from .control import (
    is_available as control_is_available, 
    generate_key as generate_control_key
)
from .types import *
from .watcher import *
from .window import *