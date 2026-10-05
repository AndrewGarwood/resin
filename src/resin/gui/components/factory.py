"""
*`@file`* `gui/components/factory`
"""
from typing import Any

from resin.gui.com.gateway import ComGateway
from resin.gui.com.types import DispatchLike
from resin.gui.context import SapContext
from resin.gui.exceptions import SapComError

from .registry import COMPONENT_REGISTRY
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .component import Component

def default_component_type():
    from .component import Component
    return Component

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

    wrapper_type = COMPONENT_REGISTRY.get(sap_type)
    if (wrapper_type is None):
        wrapper_type = default_component_type()
    component_context = context.with_component(component_id)
    return wrapper_type(
        gateway=gateway,
        context=component_context,
    )
