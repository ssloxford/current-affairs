"""
Load PCB specific calibration for the ADC
"""

import os
from typing import List
import shutil

def load_cal_data_file(name: str) -> List[List[int]]:
    res = []
    with open(name, "r") as f:
        for row in f:
            rowr = row.rstrip()
            if len(rowr):
                res.append([int(x) for x in rowr.split(" ")])
    return res

def load_cal_data() -> List[List[int]]:
    cal_file = os.path.join(os.path.dirname(os.path.realpath(__file__)), "adc_cal.txt")
    if not os.path.isfile(cal_file):
        cal_example_file = os.path.join(os.path.dirname(os.path.realpath(__file__)), "adc_cal.txt.example")
        shutil.copy(cal_example_file, cal_file)

    return load_cal_data_file(cal_file)

ADC_CAL = load_cal_data()