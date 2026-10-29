"""
*`@module`* `models/_field/__init__`
"""
from ._sentinel import *
from .value_options import *
from ._resolve import (
    resolve_sentinel_value_dict, 
    resolve_field_value, 
    resolve_field_dict
)
from .registry import SENTINEL_FUNCTION_REGISTRY

# TODO: allow user to declare sentinel k:v entries in config json, 
# then use if encounter k in fields
# might have to pass cache to resolve or have it be global var