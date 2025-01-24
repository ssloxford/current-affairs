"""
SLAC implementation using C module and real PLC modem
"""

from __future__ import annotations

import asyncio
import time
from typing import Any
from . import slac_wrapper # type: ignore
from ..utils.data_saver import DataSaver
from ..utils.async_utils import blocking_to_async
import subprocess

from . import plctools

from . import nid
from .slac_common import *

import subprocess

#from .sdp import sdp_client

import os

slac_interface: str = ""

class SlacError(Exception):
    def __init__(self, message):            
        # Call the base class constructor with the parameters it needs
        super().__init__(message)
           
    @staticmethod
    def decode(res: int | None):
        if res is None:
            pass
        elif res == slac_wrapper.ERROR_OK:
            pass
        elif res == slac_wrapper.ERROR_INTERRUPT:
            raise SlacError("SLAC_ERROR_INTERRUPT")
        elif res == slac_wrapper.ERROR_AGAIN:
            raise SlacError("SLAC_ERROR_AGAIN")
        elif res == slac_wrapper.ERROR_ARGUMENT:
            raise SlacError("SLAC_ERROR_ARGUMENT")
        elif res == slac_wrapper.ERROR_WIPE_KEY:
            raise SlacError("SLAC_ERROR_WIPE_KEY")
        elif res == slac_wrapper.ERROR_SET_KEY:
            raise SlacError("SLAC_ERROR_SET_KEY")
        elif res == slac_wrapper.ERROR_START_ATTEN_CHAR:
            raise SlacError("SLAC_ERROR_START_ATTEN_CHAR")
        elif res == slac_wrapper.ERROR_SOUNDING:
            raise SlacError("SLAC_ERROR_SOUNDING")
        elif res == slac_wrapper.ERROR_ATTEN_CHAR:
            raise SlacError("SLAC_ERROR_ATTEN_CHAR")
        elif res == slac_wrapper.ERROR_CONNECT:
            raise SlacError("SLAC_ERROR_CONNECT")
        elif res == slac_wrapper.ERROR_MATCH:
            raise SlacError("SLAC_ERROR_MATCH")
        else:
            raise SlacError(f"Unknown %i" % res)

async def slac_set_nmk_robust(func):
    wipe_key_res = slac_wrapper.ERROR_WIPE_KEY
    for _ in range(15):
        wipe_key_res = await blocking_to_async(func)()
        if wipe_key_res == slac_wrapper.ERROR_OK:
            return
        await asyncio.sleep(1)
        print("Retrying set NMK")
    await asyncio.sleep(2)
    SlacError.decode(wipe_key_res)

def ev_init(interface: str):
    global slac_interface
    slac_interface = interface
    #Start the system
    slac_wrapper.chan_init(interface)
    res = slac_wrapper.ev_init()
    SlacError.decode(res)

async def ev_prepare(logger: DataSaver, progress: Any):
    #Reset the slac
    await progress(SlacProgress.S01_RESET, False)
    await blocking_to_async(slac_wrapper.ev_reset)()

    nmk_v = os.urandom(16)
    nid_v = nid.to_nid(nmk_v)

    slac_wrapper.set_nmk(nmk_v)
    slac_wrapper.set_nid(nid_v)

    await asyncio.sleep(0.5)

    await progress(SlacProgress.S02_WIPE_NMK, False)
    await slac_set_nmk_robust(slac_wrapper.ev_wipekey)
    await asyncio.sleep(2)
    await progress(SlacProgress.S02_WIPE_NMK, True)

async def ev_run(logger: DataSaver, progress: Any) -> SlacResult:
    slac_res: SlacResult = SlacResult()

    try:
        slac_res.PEV_MAC = slac_wrapper.read_pev_mac()
        slac_res.PEV_ID = slac_wrapper.read_pev_id()
        slac_res.RUN_ID = slac_wrapper.read_run_id()

        #Run the slac process
        await progress(SlacProgress.S03_PARAM_REQ, False)
        res = slac_wrapper.ERROR_AGAIN
        while res == slac_wrapper.ERROR_AGAIN:
            res = await blocking_to_async(slac_wrapper.ev_param)()
        SlacError.decode(res)

        slac_res.NUM_SOUNDS = slac_wrapper.read_num_sounds()
        slac_res.EVSE_MAC = slac_wrapper.read_evse_mac()

        await progress(SlacProgress.S04_START_ATTEN, False)
        SlacError.decode(await blocking_to_async(slac_wrapper.ev_start_atten)())

        await progress(SlacProgress.S05_SOUNDING, False)
        SlacError.decode(await blocking_to_async(slac_wrapper.ev_mnbc_sound)())

        await progress(SlacProgress.S06_ATTEN_CHAR, False)
        res = await blocking_to_async(slac_wrapper.ev_atten_char)()
        SlacError.decode(res)

        slac_res.NUM_SOUNDS = slac_wrapper.read_num_sounds()
        slac_res.EVSE_ID = slac_wrapper.read_evse_id()
        slac_res.AAG = slac_wrapper.read_aag()

        await progress(SlacProgress.S07_SELECT, False)
        SlacError.decode(await blocking_to_async(slac_wrapper.ev_connect)())

        await progress(SlacProgress.S08_MATCH, False)
        res = await blocking_to_async(slac_wrapper.ev_match)()
        SlacError.decode(res)

        slac_res.EVSE_MAC = slac_wrapper.read_evse_mac()
        slac_res.EVSE_ID = slac_wrapper.read_evse_id()
        slac_res.NMK = slac_wrapper.read_nmk()
        slac_res.NID = slac_wrapper.read_nid()

        await progress(SlacProgress.S08_MATCH, True)

        #Log parameters
        

    finally:
        logger.log_entry("SLAC", slac_res.to_json())

    await progress(SlacProgress.S09_SET_NMK, False)
    await slac_set_nmk_robust(slac_wrapper.ev_set_nmk)
    await progress(SlacProgress.S10_CONNECT, False)

    #sdp = asyncio.ensure_future(sdp_client(logger, "eth0", False, 10000))

    t_end = time.time() + 15
    network = None
    local_mac = await plctools.get_local_mac()
    while time.time() < t_end:
        network = await plctools.get_network_full(local_mac)#type: ignore
        if network is not None:
            if len(network["STATIONS"]) > 0:
                break

    print(plctools.json_convert_item(network))
    logger.log_entry("NETWORK", plctools.json_convert_item(network))

    await progress(SlacProgress.S11_DONE, True)

    return slac_res

