"""
*`@file`* `gui/models/transaction/options`
"""
from datetime import date
from pathlib import Path
from dataclasses import dataclass, replace
from typing import (Self, TypedDict, Required, NotRequired, Any, Optional, Mapping, TypeAlias, Literal)
from pyqi import (String, Json, export, Result, dt, fs)
from lute import LogMsg
from ...utils import gui_id as GUI
