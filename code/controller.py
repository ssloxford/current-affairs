from __future__ import annotations
from abc import ABC, abstractmethod
import math
from typing import Any, List, NamedTuple, Tuple

from .network import states
from .utils.dataevent import DataEvent
import netifaces#type: ignore
from .network.ui_link_inner import UI_Inner
from . import pcap_wrapper
from .network import states
from .network import states_task
from .interface import hal
from .interface import socket_wrapper
import contextlib

from .utils import data_saver 

#import v2g.protocol_version as protocol_version
from .interface.bs_measure import CPMeasurementThread

import asyncio
import socket
import sys
import os
import signal

def get_mac_address(interface):
    mac = netifaces.ifaddresses(interface)[netifaces.AF_LINK][0]['addr']
    mac_bytes = bytes.fromhex(mac.replace(':', ''))
    return mac_bytes

def get_ip_address(interface: str) -> str:
    return netifaces.ifaddresses(interface)[netifaces.AF_INET6][0]['addr'].split("%")[0]

class ExperimentDescription(NamedTuple):
    name: str
    box: str
    plug: str
    gps: Tuple[float, float]

    def to_json(self):
        return {
            "v": 7,
            "name": self.name,
            "box": self.box,
            "plug": self.plug,
            "gps": self.gps,
        }

@contextlib.asynccontextmanager
async def final_cleanup(ctrl: Controller):
    try:
        yield None
    finally:
        await ctrl.do_reset()

#
# Controller base class
#
class Controller:
    logger: data_saver.DataSaver
    interface: str
    mac: bytes

    ui: UI_Inner

    tasks_all: List[states_task.StateTask]
    tasks_run: List[states_task.StateTask]

    run_cache: List[states_task.StateTask]

    sock: socket_wrapper.WrappedSocket | None

    args: Any

    def __init__(self, interface: str, args):
        self.logger = data_saver.DataSaver(args.outpath)
        self.interface = interface
        self.mac = get_mac_address(interface)

        self.basic_signalling = CPMeasurementThread()
        
        self.sock = None

        self.tasks_all = []
        self.tasks_run = []

        self.run_cache = []

        self.ui = UI_Inner()

        self.bs_listener = self.basic_signalling.add_listener(self.ui.state_basic.set_measurement)

        self.args = args

    def add_task(self, task, run):
        self.tasks_all.append(task)
        if run:
            self.tasks_run.append(task)
            self.ui.add_task(task)

    @abstractmethod
    async def do_reset(self):
        pass

    async def wait_should_enable(self):
        try:
            await self.ui.waiter_plug.wait_user()
        except asyncio.CancelledError:
            self.ui.waiter_plug.cancel()
            raise

    async def run_task_manual(self, name: str):
        for exp in self.tasks_all:
            if exp.name == name:
                await exp.run(self, True)
                return

    async def run_session_all(self):
        for exp in self.tasks_run:
            while await exp.run(self, False, cache_policy = -1) == states_task.TaskResultEnum.Failed_Retry:
                print("Retrying experiment")
                pass

    async def run_session_manual(self):
        while True:
            done_state = await self.ui.waiter_done.wait_user()
            print(done_state)
            if done_state == "done":
                return
            else:
                await self.run_task_manual(done_state)
                            
    async def run_session(self) -> bool:
        #Wait till user wants to start
        res = await self.ui.waiter_start.wait_user()
        if res == "exit":
            return True
        latlong = (float(self.args.lat), float(self.args.long))
        desc = ExperimentDescription(
            self.args.name, self.args.box, self.args.plug,
            (latlong[0] if not math.isnan(latlong[0]) else None, latlong[1] if not math.isnan(latlong[1]) else None)
        )

        #Reset
        self.run_cache = []
        for exp in self.tasks_all:
            await exp.reset()

        with self.logger.trace_file_start(f"{desc.name}_{desc.box}_{desc.plug}") as _:
            with self.logger.trace_enter("CHARGER"):
                with pcap_wrapper.pcap_context( self.interface, os.path.join(self.logger.result_subfolder, "pcap.pcap") ) as _:
                    async with final_cleanup(self) as _:

                        self.logger.log_entry("INFO", desc.to_json())
                        await asyncio.sleep(0.5)

                        if res == "start_all":
                            await self.run_session_all()

                        await self.run_session_manual()
                        

        print("Session done")
        return False
            
    async def run_forever(self):
        def sigterm_handler(_signo, _stack_frame):
            # Raises SystemExit(0):
            sys.exit(0)


        signal.signal(signal.SIGTERM, sigterm_handler)

        task_server = asyncio.create_task(self.ui.start_websocket_server())
        task_measure = asyncio.create_task(self.basic_signalling.run_thread())

        def sigint_handler(_signo, _stack_frame):
            pass
        signal.signal(signal.SIGINT, sigint_handler)

        try:
            #while True:
            #print("Run")
            #if 
            await self.run_session()#:
            #    break

        finally:
            task_server.cancel()
            task_measure.cancel()

            await asyncio.gather(task_server, task_measure)

        #exit(0)
        #await asyncio.gather(task_server, task_poll, task_measure)