"""
*`@file`* `resin/gui/components/registry`
"""
from __future__ import annotations

from typing import Any, TypeVar

from ..com.gateway import ComGateway
from ..com.types import DispatchLike
from ..context import SapContext
from ..exceptions import SapComError

from .component import Component



ComponentT = TypeVar("ComponentT", bound=Component)
_REGISTRY: dict[str, type[Component]] = {}


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
        sap_type = f"Gui{wrapper_type.__name__}"
        existing = _REGISTRY.get(sap_type)
        if existing is not None and existing is not wrapper_type:
            raise RuntimeError(
                f"SAP component type {sap_type!r} is already registered "
                f"to {existing.__module__}.{existing.__qualname__}"
            )

        _REGISTRY[sap_type] = wrapper_type
        return wrapper_type

    return decorator


def wrapper_type_for(sap_type: str, /,) -> type[Component]:
    return _REGISTRY.get(sap_type, Component)


def wrap_dispatch(
    dispatch: DispatchLike,
    /,
    gateway: ComGateway,
    context: SapContext,
) -> Any:
    try:
        sap_type = str(dispatch.Type)
        component_id = str(dispatch.Id)
    except Exception as e:
        raise SapComError(
            "Cannot wrap a COM object without usable Type and Id properties"
        ) from e

    wrapper_type = _REGISTRY.get(sap_type, Component)
    component_context = context.with_component(component_id)

    return wrapper_type(
        gateway=gateway,
        context=component_context,
    )


def registered_components() -> dict[str, type[Component]]:
    """
    Returns copy of registry
    """
    return dict(_REGISTRY) # Return a copy so callers cannot mutate the live registry.