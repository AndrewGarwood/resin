"""
*`@file`* `resin/gui/components/registry`
"""
from __future__ import annotations
from typing import TYPE_CHECKING, TypeVar

if TYPE_CHECKING:
    from .component import Component

ComponentT = TypeVar("ComponentT", bound="Component")
COMPONENT_REGISTRY: dict[str, type["Component"]] = {}

def generate_sap_type(component: type[ComponentT], /):
    """ 
    - assumes `component.__name__` is same as `SapScriptingApi` 
    counterpart without the "Gui" prefix  
    """
    return f"Gui{component.__name__}"

def register_component():
    """
    Register a wrapper class for an SAP GUI Type value.

    Example:
        @register_component() # → SAP_TYPE = "GuiButton"
        class Button(Component):
            ...
    """
    def decorator(wrapper_type: type[ComponentT],) -> type[ComponentT]:
        _wrapper_name = wrapper_type.__name__
        sap_type = (
            f"Gui{_wrapper_name}" if not _wrapper_name.startswith("Gui") 
            else _wrapper_name
        )
        existing = COMPONENT_REGISTRY.get(sap_type)
        if (existing is not None and existing is not wrapper_type):
            raise RuntimeError(
                f"SAP component type {sap_type!r} is already registered "
                f"to {existing.__module__}.{existing.__qualname__}"
            )
        COMPONENT_REGISTRY[sap_type] = wrapper_type
        return wrapper_type
    return decorator


# def wrapper_type_for(sap_type: str, /,) -> type[Component]:
#     return COMPONENT_REGISTRY.get(sap_type, Component)

def registered_components() -> dict[str, type["Component"]]:
    """
    Returns copy of registry
    """
    return dict(COMPONENT_REGISTRY) # Return a copy so callers cannot mutate the live registry.
