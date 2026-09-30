"""
*`@file`* `gui/services/transaction/transaction`
"""

from ...models.transaction import (
    TransactionOptions, 
    TransactionResult, 
    TransactionDetails, 
    TransactionStage
)

from pyqi.models import (Flow)
from pyqi import (Json, Array, fs, String)


class Transaction(Flow[TransactionStage]):
    code: str
    options: TransactionOptions
    ...

    