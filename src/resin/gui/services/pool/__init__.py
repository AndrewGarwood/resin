"""
*`@module`* `gui/services/pool/__init__`


### Phase 1: Prepare
    - open()
    - populate_selection_screen()
    - transaction reaches READY_TO_EXECUTE

    - #### Barrier: 
        - all active workers reach READY_TO_EXECUTE

### Phase 2: Execute
    - execute()
    - each worker independently enters EXECUTION_RUNNING
    - execute may block its own worker, but not other workers

    - #### Barrier: 
        - wait until all active transactions reach POST_EXECUTE

### Phase 3: Post-execute
    - handle_post_execute()
    - transaction reaches READY_TO_EXPORT or COMPLETED

    - #### Barrier: 
        - wait until all transactions reach READY_TO_EXPORT or COMPLETED

### Phase 4: Export
    - export READY_TO_EXPORT transactions sequentially

    - #### Final: 
        - each transaction is COMPLETED or FAILED
"""

from .options import *
from .types import *
from .utils import *
from .provisioner_types import *
from .provisioner import *
from .session_pool import *
from .session_locator import *
from .session_binding import *
from .exceptions import *
from .connection import *
# from .assignment import *
# from .command import *
