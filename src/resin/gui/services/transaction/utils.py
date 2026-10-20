"""
*`@file`* `gui/services/transaction/utils`
"""
from typing import (Sequence, Callable)
from pyqi import Result, export
from resin.gui.models.transaction import TransactionDetails



def build_result_dict(
    results: Sequence[Result[TransactionDetails]], 
    *,
    key_normalizer: Callable[[str], str] | None=None,
    require_result_data: bool=False
):
    _result: dict[str, Result[TransactionDetails]] = dict()
    for r in results:
        if not r.data: 
            if (require_result_data): 
                raise ValueError("Encountered Result with undefined data")
            continue
        key = key_normalizer(r.data.txn_id) if key_normalizer is not None else r.data.txn_id
        _result[key] = r
    return _result

__all__ = export(build_result_dict)