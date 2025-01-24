"""
Fake SLAC implementation for testing
"""

from __future__ import annotations

import asyncio
from typing import Any
from ..utils.data_saver import DataSaver
from ..utils.async_utils import blocking_to_async

from .slac_common import *

class SlacError(Exception):
    def __init__(self, message):            
        # Call the base class constructor with the parameters it needs
        super().__init__(message)

def ev_init(interface: str):
    pass

async def ev_prepare(logger: DataSaver, progress: Any):
    #Reset the slac
    await progress(SlacProgress.S01_RESET, False)
    await asyncio.sleep(0.5)

    await asyncio.sleep(0.5)
    await progress(SlacProgress.S02_WIPE_NMK, False)
    await asyncio.sleep(1.5)
    await progress(SlacProgress.S02_WIPE_NMK, True)

async def ev_run(logger: DataSaver, progress: Any) -> SlacResult:
    slac_res: SlacResult = SlacResult()

    try:

        #Run the slac process
        await progress(SlacProgress.S03_PARAM_REQ, False)
        await asyncio.sleep(1)

        await progress(SlacProgress.S04_START_ATTEN, False)
        await asyncio.sleep(0.5)

        await progress(SlacProgress.S05_SOUNDING, False)
        await asyncio.sleep(0.5)

        await progress(SlacProgress.S06_ATTEN_CHAR, False)
        await asyncio.sleep(0.5)

        slac_res.AAG = b"012345678"

        await progress(SlacProgress.S07_SELECT, False)
        await asyncio.sleep(0.5)

        await progress(SlacProgress.S08_MATCH, False)
        await asyncio.sleep(0.5)
        await progress(SlacProgress.S08_MATCH, True)

        #Log parameters
        
        slac_res.NMK = b"0123456789ABCDEF"
        slac_res.NID = b"ABCDEFG"
        slac_res.PEV_MAC = b"MACPEV"
        slac_res.EVSE_MAC = b"MACSEE"
        slac_res.PEV_ID = b"000000"
        slac_res.EVSE_ID = b"00000000"
        slac_res.AAG = b"012345678"
        slac_res.NUM_SOUNDS = 10

    finally:
        logger.log_entry("SLAC", slac_res.to_json())

    await progress(SlacProgress.S09_SET_NMK, False)
    await asyncio.sleep(1)
    await progress(SlacProgress.S10_CONNECT, False)
    await asyncio.sleep(1)
    #await progress(SlacProgress.S09_SET_NMK, True)
  
    await progress(SlacProgress.S11_DONE, True)
    return slac_res
