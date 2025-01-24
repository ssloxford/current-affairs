from __future__ import annotations

from enum import Enum

class SlacProgress(Enum):
    S00_NONE = 0
    S01_RESET = 1
    S02_WIPE_NMK = 2
    S03_PARAM_REQ = 3
    S04_START_ATTEN = 4
    S05_SOUNDING = 5
    S06_ATTEN_CHAR = 6
    S07_SELECT = 7
    S08_MATCH = 8
    S09_SET_NMK = 9
    S10_CONNECT = 10
    S11_DONE = 11


class SlacResult():
    NMK: bytes | None
    NID: bytes | None
    PEV_MAC: bytes | None
    EVSE_MAC: bytes | None
    PEV_ID: bytes | None
    EVSE_ID: bytes | None
    AAG: bytes | None
    NUM_SOUNDS: int | None
    RUN_ID: bytes | None

    def __init__(self):
        self.NMK = None
        self.NID = None
        self.PEV_MAC = None
        self.EVSE_MAC = None
        self.PEV_ID = None
        self.EVSE_ID = None
        self.AAG = None
        self.NUM_SOUNDS = None
        self.RUN_ID = None

    def to_json(self):
        return {
        "NMK": self.NMK.hex() if self.NMK is not None else None,
        "NID": self.NID.hex() if self.NID is not None else None,
        "PEV_MAC": self.PEV_MAC.hex() if self.PEV_MAC is not None else None,
        "EVSE_MAC": self.EVSE_MAC.hex() if self.EVSE_MAC is not None else None,
        "PEV_ID": self.PEV_ID.hex() if self.PEV_ID is not None else None,
        "EVSE_ID": self.EVSE_ID.hex() if self.EVSE_ID is not None else None,
        "AAG": ':'.join('%02x' % b for b in self.AAG) if self.AAG is not None else None,
        "RUN_ID": self.RUN_ID.hex() if self.RUN_ID is not None else None,
    }