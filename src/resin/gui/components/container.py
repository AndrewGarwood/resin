"""
*`@file`* `gui/components/container`
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import (TypeVar, Generic)
import lute
from pyqi import export
from ..com.gateway import ComGateway
from ..context import SapContext
from ..exceptions import (
    SapComError,
)
from .component import Component
from .registry import (register_component)
from ..utils.mixin import (FindMixin)
from .factory import (wrap_dispatch)

LogMsg = lute.LogMsg
ComponentT = TypeVar("ComponentT", bound=Component)
ChildT = TypeVar("ChildT", bound=Component)

class Container(Component, FindMixin, Generic[ChildT]):
    """
    Base wrapper for session-bound components supporting FindById.

    This class intentionally represents only component containers. Application
    and Connection should not inherit this class because they are not bound to
    one session and cannot safely use session-based FindById operations.
    """

    def __init__(
        self,
        *,
        gateway: ComGateway,
        context: SapContext,
    ) -> None:
        super().__init__(
            gateway=gateway,
            context=context,
        )

    @property
    def children(self) -> tuple[ChildT, ...]:
        """
        Return wrapped immediate children.

        A tuple is returned so callers do not mistake the result for a live
        mutable SAP GUI collection.
        """
        dispatch = self._resolve()

        try:
            com_children = dispatch.Children
            count = int(com_children.Count)
        except Exception as e:
            raise SapComError(
                f"Unable to enumerate children of component {self.id!r}"
            ) from e

        children: list[ChildT] = []

        for index in range(count):
            try:
                child_dispatch = com_children(index)
            except Exception as e:
                raise SapComError(
                    f"Unable to read child {index} of component {self.id!r}"
                ) from e

            if child_dispatch is None:
                raise SapComError(
                    f"Child {index} of component {self.id!r} was None"
                )

            children.append(wrap_dispatch(
                child_dispatch,
                gateway=self.gateway,
                context=self.context,
            ))

        return tuple(children)

    def iter_children(self) -> Iterator[ChildT]:
        """
        Iterate through the current child snapshot.

        The snapshot behavior avoids holding a live COM collection while user
        code is running.
        """
        yield from self.children


    def exists(
        self,
        component_id: str | None = None,
        /,
    ) -> bool:
        """
        Check this container or one descendant.

        ``container.exists()`` checks whether this container still exists.
        ``container.exists("wnd[0]/usr/...")`` checks a descendant.
        """
        if component_id is None:
            return super().exists()

        if not isinstance(component_id, str) or not component_id.strip():
            raise ValueError(
                "component_id must be a non-empty string"
            )

        return self.gateway.component_exists(
            self.connection_id,
            self.session_id,
            component_id,
        )

class VContainer(Container[ChildT]):
    """
    [SAP GuiVContainer](https://help.sap.com/docs/sap_gui_for_windows/b47d018c3b9b45e897faf66a6c0885a8/76a8c4e46d1d4f8caa5f70b6dcfc5f34.html)
    """ 
    ...

@register_component()
class UserArea(Container):
    """
    [GuiUserArea](https://help.sap.com/docs/sap_gui_for_windows/b47d018c3b9b45e897faf66a6c0885a8/7892da6a9b83433583707d476207badf.html)
    """
    ...

__all__ = export(Container, VContainer, UserArea)