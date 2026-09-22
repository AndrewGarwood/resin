"""
*`@file`* `resin/gui/components/_collection.py`
- [SAP GuiCollection](https://help.sap.com/docs/sap_gui_for_windows/b47d018c3b9b45e897faf66a6c0885a8/e65366f29e3d45c8b5ff0f05690aff78.html)
"""

from typing import (Optional, Any, TypeVar, Type, Generic)
from ._proxy import ComProxy
U = TypeVar('U')



class Collection(ComProxy, Generic[U]):
    """ 
    *`@extends`* `ComProxy, Generic[U]`
    """
    def __getattr__(self, name) -> Any:
        return getattr(self._resolve(), name)
    
    def add(self, item: Type[U]):
        self._resolve().Add(item)
    
    def element_at(self, index: int) -> Optional[U]:
        if index > 0 and index < self.count - 1:
            return self._resolve().ElementAt(index)
        return None
    
    def item(self, index: int) -> Optional[U]:
        """ It has been added for compatibility with Microsoft Visual Basic collections. """
        return self.element_at(index)

    @property
    def count(self) -> int:
        """ 
        'The number of elements in the collection. 
        This property has been added for compatibility with Microsoft Visual Basic collections' 
        """
        return self._resolve().Count
    
    @property
    def length(self) -> int:
        """ The number of elements in the collection. """
        return self._resolve().Length
    
    @property
    def type(self) -> str:
        return self._resolve().Type
    
    @property
    def type_as_number(self) -> int:
        return self._resolve().TypeAsNumber

    def __len__(self) -> int:
        return self.length