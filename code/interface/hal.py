from ..utils import settings

from . import hal_base

if settings.SKIP_BASIC:
    from .hal_tst import *
else:
    from .hal_v2 import *