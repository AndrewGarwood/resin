"""
*`@module`* `utils/winauto/__init__`
"""

# should make separate package
from .debug import *
from .exceptions import *

from .control import (
    is_available as control_is_available, 
    generate_key as generate_control_key,
)
from .control.types import *
from .control.options import *
from .types import *
from .watcher import *
from . import (
    window, 
    control,
    )
from .window import (
    WindowOptionsDict, 
    WindowState,
    )
from .window._find import (
    find as find_window,
    by_spec as find_window_by_spec
)
from .window._process import (
    attach_process as attach_process_to_window
)
from .ownership import *