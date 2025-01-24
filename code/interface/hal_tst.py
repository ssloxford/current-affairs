"""
Test mode instead of using real PCB
"""

from .hal_base import Module_Base

class Module_EV(Module_Base):
    def __init__(self):
        pass

    def set_pp_gen_state(self, on: bool):
        pass

    def set_cp_b(self, on: bool):
        pass

    def set_cp_c(self, on: bool):
        pass

    def plug_sniff(self):
        pass

    def plug_connect(self):
        pass

    def unplug(self):
        pass

class _ADC():
    def __init__(self):
        pass

    async def get_cp_measurement(self):
        return (-12, 9, 0.05, 5)

    async def read_adc(self, chan):
        return 0
    
ADC = _ADC()