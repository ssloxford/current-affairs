"""
Basic Signalling measurement
"""

from __future__ import annotations

from ..utils import settings
from ..utils.dataevent import DataEvent

from . import hal
from . import adc_cal

import time

from typing import Any, List
from enum import IntFlag
import asyncio
import math

class CPState(IntFlag):
    """CP State as bit flag for select"""
    CP_STATE_A1 = 1
    CP_STATE_A2 = 2
    CP_STATE_B1 = 4
    CP_STATE_B2 = 8
    CP_STATE_C1 = 16
    CP_STATE_C2 = 32
    CP_STATE_D1 = 64
    CP_STATE_D2 = 128
    CP_STATE_E  = 256
    CP_STATE_F  = 512
    CP_STATE_UB = 0
    def __str__(self):
        return str(self.name)

class CPMeasurement():
    """Class representing the CP measurement result"""
    level_low: float
    level_high: float
    duty: float
    pp: float

    detected: CPState
    same_count: int

    def __init__(self, level_low: float, level_high: float, duty: float, pp: float, same_count: int = 1):
        self.level_low = level_low
        self.level_high = level_high
        self.duty = duty
        self.pp = pp

        self.detected = self._detect()
        self.same_count = same_count

    def _detect(self) -> CPState:
        """Detect state from measurement"""
        if (self.duty > 0.999):
            #x1 state
            if (11 <= self.level_high and self.level_high <= 13):
                return CPState.CP_STATE_A1

            elif (8 <= self.level_high and self.level_high <= 10):
                return CPState.CP_STATE_B1

            elif (5 <= self.level_high and self.level_high <= 7):
                return CPState.CP_STATE_C1

            elif (2 <= self.level_high and self.level_high <= 4):
                return CPState.CP_STATE_D1

            elif (self.level_high <= 1):
                return CPState.CP_STATE_E

            else:
                return CPState.CP_STATE_UB
        elif (self.duty > 0.01):
            #x2 state
            if (-13 <= self.level_low and self.level_low <= -11):
                if (11 <= self.level_high and self.level_high <= 13):
                    return CPState.CP_STATE_A2

                elif (8 <= self.level_high and self.level_high <= 10):
                    return CPState.CP_STATE_B2

                elif (5 <= self.level_high and self.level_high <= 7):
                    return CPState.CP_STATE_C2
                
                elif (2 <= self.level_high and self.level_high <= 4):
                    return CPState.CP_STATE_D2
                
                else:
                    return CPState.CP_STATE_UB
                
            
            elif (-1 <= self.level_low and self.level_high <= 1):
                return CPState.CP_STATE_E
            
            else:
                return CPState.CP_STATE_UB
            
        
        else:
            #F state
            if (-13 <= self.level_low and self.level_low <= -11):
                return CPState.CP_STATE_F
            
            elif (-1 <= self.level_low):
                return CPState.CP_STATE_E
            
            else:
                return CPState.CP_STATE_UB
            
        return CPState.CP_STATE_UB

    @staticmethod
    async def measure() -> "CPMeasurement":
        """Get value async from C module"""
        meas = await hal.ADC.get_cp_measurement()
        return CPMeasurement(
                level_low = meas[0],
                level_high = meas[1],
                duty = meas[2],
                pp = meas[3]
        )

    def to_json(self):
        return {
            "l": None if math.isnan(self.level_low) else self.level_low,
            "h": None if math.isnan(self.level_high) else self.level_high,
            "d": self.duty,
            "s": self.detected.value,
            "p": self.pp
        }

class WrappedListener():

    def __init__(self, coroutine, thread: CPMeasurementThread):
        self.coroutine = coroutine
        self.thread = thread

    def remove(self):
        if self.thread is not None:
            self.thread.remove_listener(self.coroutine)
            self.coroutine = None
            self.thread = None

    def __del__(self):
        self.remove()

class CPMeasurementThread():
    _listeners: List[Any]

    def __init__(self):
        self._last_state_i = CPState.CP_STATE_UB
        self._last_state = None
        self._same_count = 0
        self._listeners = []

    def add_listener(self, coroutine) -> WrappedListener:
        """
        Add coroutine as a listener to each new measurement value.
        Call .remove() of return value when done
        """

        self._listeners.append(coroutine)
        #print("Added listener ", coroutine)
        return WrappedListener(coroutine, self)

    def remove_listener(self, coroutine):
        #print("Removed listener ", coroutine)
        self._listeners.remove(coroutine)

    async def run_thread(self):
        _last_state = None
        _last_state_i = CPState.CP_STATE_UB

        while True:
            new_state = await CPMeasurement.measure()

            # Count how long without a change
            if(new_state.detected == _last_state_i):
                if _last_state is not None:
                    new_state.same_count = _last_state.same_count + 1
            
            _last_state = new_state
            _last_state_i = _last_state.detected

            # Update listeners
            await asyncio.gather(*[l(_last_state) for l in self._listeners])
        
    async def wait(self, wait_state: CPState, fn = None) -> CPState:
        """Wait for any of the CP states set in the bit flags, return detected value"""

        listener = DataEvent()
        listener_delete_handle = self.add_listener(listener.set)

        try:
            start_time = time.time()
            while True:
                measured_state: CPMeasurement = await listener.wait_get()
                if fn is not None:
                    await fn(measured_state)
                if (measured_state.detected & wait_state) and measured_state.same_count > 2:
                    return measured_state.detected
                if settings.SKIP_BASIC and (start_time + 2 < time.time()):
                    return measured_state.detected
        finally:
            listener_delete_handle.remove()

    async def wait_ev_charger_connected(self, fn = None) -> CPState:
        return await self.wait(CPState.CP_STATE_A1, fn)
    
    async def wait_ev_charger_ready(self, fn = None) -> CPState:
        return await self.wait(CPState.CP_STATE_B2, fn)
