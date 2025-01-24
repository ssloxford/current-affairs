"""
Wrapper around the network querying functions in the PLC utils module
"""

from __future__ import annotations
import asyncio
from typing import Any, Dict, List, Tuple

from . import slac_wrapper# type: ignore

from ..utils.async_utils import blocking_to_async

#Hardcoded value all QCA chips should respond to
LOCAL_DEVICE_MAC = b"\x00\xB0\x52\x00\x00\x01"

async def get_version(device_mac: bytes):
    res = await blocking_to_async(slac_wrapper.sw_ver)(device_mac)
    print(res)
    if res is None:
        return None
    if len(res) < 1:
        return None
    return res[0]

async def get_identity(device_mac: bytes):
    res = await blocking_to_async(slac_wrapper.vs_mod)(device_mac)
    print(res)
    if res is None:
        return None
    if len(res) < 1:
        return None
    return res[0]

async def get_network(device_mac: bytes):
    res = await blocking_to_async(slac_wrapper.nw_info)(device_mac)
    print(res)
    if res is None:
        return None
    if len(res) < 1:
        return None
    if len(res[0]) < 1:
        return None
    return res[0][0]

async def get_local_mac() -> bytes | None:
    res = await get_version(LOCAL_DEVICE_MAC)
    if res is None:
        return None
    return res["MAC"]

async def get_network_full(device_mac: bytes):
    res_nw = await get_network(device_mac)
    if res_nw is None:
        return None
    for dev in res_nw["STATIONS"]:
        dev["VERSION"] = await get_version(dev["MAC"])
        dev["IDENTITY"] = await get_identity(dev["MAC"])
    return res_nw

def json_convert_item(obj):
    if isinstance(obj, bytes):
        return obj.hex()
    elif isinstance(obj, list):
        return json_convert_list(obj)
    elif isinstance(obj, tuple):
        return json_convert_tuple(obj)
    elif isinstance(obj, dict):
        return json_convert_dict(obj)
    return obj

def json_convert_dict(dict: Dict[str, Any]):
    res = {}
    for k in list(dict.keys()):
        res[k] = json_convert_item(dict[k])
    return res

def json_convert_list(l: List[Any]):
    return list([json_convert_item(v) for v in l])

def json_convert_tuple(t: Tuple[Any]):
    return tuple(json_convert_item(v) for v in t)


async def main():
    await slac_wrapper.chan_init("eth0")
    while True:
        try:
            exec(input("> "))
        except KeyboardInterrupt:
            raise
        except Exception as e:
            print(e)

if __name__ == "__main__":
    asyncio.run(main())