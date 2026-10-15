"""
*`@file`* `utils/winauto/control/types`
"""
from __future__ import annotations
from typing import Any, TypeAlias
from pyqi import BaseStrEnum, export



ControlKey: TypeAlias = tuple[Any | None, Any | None, Any, Any]
""" 
= (
    `BaseWrapper.element_info.control_type,` 
    `BaseWrapper.element_info.handle,` 
    `BaseWrapper.element_info.automation_id,` 
    `BaseWrapper.rectangle()`
)
"""
ControlClass: TypeAlias = "CommonControl | UiaControl | Win32Control | Win32Window"

class ControlState(BaseStrEnum):
    AVAILABLE = "exists visible enabled ready"
    VISIBLE_ENABLED = "visible enabled"

class CommonControl(BaseStrEnum):
    """
    ```
    
    BUTTON = "Button"
    HEADER = "Header"
    EDIT = "Edit"
    COMBO_BOX = "ComboBox"
    STATUS_BAR = "StatusBar"
    ```
    """
    BUTTON = "Button"
    HEADER = "Header"
    EDIT = "Edit"
    COMBO_BOX = "ComboBox"
    STATUS_BAR = "StatusBar"


class UiaControl(BaseStrEnum):
    APP_BAR = "AppBar"
    BUTTON = CommonControl.BUTTON.value
    CALENDAR = "Calendar"
    CHECK_BOX = "CheckBox"
    COMBO_BOX = CommonControl.COMBO_BOX.value
    DATA_GRID = "DataGrid"
    DATA_ITEM = "DataItem"
    DOCUMENT = "Document"
    EDIT = CommonControl.EDIT.value
    GROUP = "Group"
    HEADER = CommonControl.HEADER.value
    HEADER_ITEM = "HeaderItem"
    HYPERLINK = "Hyperlink"
    IMAGE = "Image"
    LIST = "List"
    LIST_ITEM = "ListItem"
    MENU = "Menu"
    MENU_BAR = "MenuBar"
    MENU_ITEM = "MenuItem"
    PANE = "Pane"
    PROGRESS_BAR = "ProgressBar"
    RADIO_BUTTON = "RadioButton"
    SCROLL_BAR = "ScrollBar"
    SEMANTIC_ZOOM = "SemanticZoom"
    SEPARATOR = "Separator"
    SLIDER = "Slider"
    SPINNER = "Spinner"
    SPLIT_BUTTON = "SplitButton"
    STATUS_BAR = CommonControl.STATUS_BAR.value
    TAB = "Tab"
    TAB_ITEM = "TabItem"
    TEXT = "Text"
    THUMB = "Thumb"
    TITLE_BAR = "TitleBar"
    TOOL_BAR = "ToolBar"
    TOOL_TIP = "ToolTip"
    TREE = "Tree"
    TREE_ITEM = "TreeItem"
    WINDOW = "Window"

    
class Win32Control(BaseStrEnum):
    BUTTON = CommonControl.BUTTON.value
    COMBO_BOX = CommonControl.COMBO_BOX.value
    EDIT = CommonControl.EDIT.value
    LIST_BOX = "ListBox"
    LIST_VIEW = "ListView"
    HEADER = CommonControl.HEADER.value
    TOOL_BAR = "Toolbar" # diff case for letter b than uia
    STATUS_BAR = CommonControl.STATUS_BAR.value
    TAB_CONTROL = "TabControl"
    TREE_VIEW = "TreeView"
    DIALOG = "Dialog"

class Win32Window(BaseStrEnum):
    """
    aka `Win32WindowClassId`
    ```
    POPUP = "#32768"
    DIALOG = "#32770"
    ```
    """
    POPUP = "#32768"
    DIALOG = "#32770"



__all__ = export(
    "ControlKey", "ControlClass", ControlState, CommonControl, UiaControl, 
    Win32Control, Win32Window
)