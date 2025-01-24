from __future__ import annotations

import RPi.GPIO as GPIO# type: ignore
import spidev# type: ignore

from .hal_base import Module_Base
from . import slac_wrapper# type: ignore
from . import adc_cal

from ..utils.async_utils import blocking_to_async

#EV PP
GPIO_EV_PP_GEN_PIN = 16

#EV CP
GPIO_EV_CP_B_PIN = 23
GPIO_EV_CP_C_PIN = 24

class Module_EV(Module_Base):
    def __init__(self):
        GPIO.setmode(GPIO.BCM)
        GPIO.setwarnings(False)

        #PP
        GPIO.setup(GPIO_EV_PP_GEN_PIN, GPIO.OUT, initial=GPIO.LOW)

        #CP
        GPIO.setup(GPIO_EV_CP_C_PIN, GPIO.OUT, initial=GPIO.LOW)
        GPIO.setup(GPIO_EV_CP_B_PIN, GPIO.OUT, initial=GPIO.LOW)

    def set_pp_gen_state(self, on: bool):
        if on:
            GPIO.output(GPIO_EV_PP_GEN_PIN, True)
        else:
            GPIO.output(GPIO_EV_PP_GEN_PIN, False)

    def set_cp_b(self, on: bool):
        if on:
            GPIO.output(GPIO_EV_CP_B_PIN, True)
        else:
            GPIO.output(GPIO_EV_CP_C_PIN, False)
            GPIO.output(GPIO_EV_CP_B_PIN, False)

    def set_cp_c(self, on: bool):
        if on:
            GPIO.output(GPIO_EV_CP_B_PIN, True)
            GPIO.output(GPIO_EV_CP_C_PIN, True)
        else:
            GPIO.output(GPIO_EV_CP_C_PIN, False)

    def plug(self):
        self.set_pp_gen_state(True)
        self.set_cp_b(False)
        self.set_cp_c(False)
        

    def unplug(self):
        self.set_pp_gen_state(True)
        self.set_cp_b(False)
        self.set_cp_c(False)

class _ADC():
    def __init__(self):
        slac_wrapper.init_adc(adc_cal.ADC_CAL[1])

    async def get_cp_measurement(self):
        return await blocking_to_async(slac_wrapper.measure_cp_stat)() + (await self.read_adc(0),)

    async def read_adc(self, chan):
        raw_val = await blocking_to_async(slac_wrapper.measure_raw)(chan)
        if raw_val < 0:
            raise ValueError("ADC read failed")

        if raw_val < adc_cal.ADC_CAL[chan][1]:
            return -12 + 12 * (raw_val - adc_cal.ADC_CAL[chan][0]) / (adc_cal.ADC_CAL[chan][1] - adc_cal.ADC_CAL[chan][0])
        return 12 * (raw_val - adc_cal.ADC_CAL[chan][1]) / (adc_cal.ADC_CAL[chan][2] - adc_cal.ADC_CAL[chan][1])
    
ADC = _ADC()