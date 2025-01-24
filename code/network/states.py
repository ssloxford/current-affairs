from __future__ import annotations

import asyncio
import json
import signal
import subprocess
from typing import Any, Dict, List, TYPE_CHECKING, NamedTuple, Tuple

from ..utils import settings

from ..interface.bs_measure import CPMeasurement
import websockets.client as wsc

import datetime

import os

if TYPE_CHECKING:
    from . import ui_link

from .state_base import StateBaseClass, StateWaiter


class StateInfo(StateBaseClass):
    name: str
    box: str
    plug: str
    gps: Tuple[Any, Any]

    exp_start_waiter: StateWaiter
    #exp_done_waiter: StateWaiter

    def __init__(self, ws: "ui_link.UI_Link"):
        super().__init__(ws)

        self.name = ""
        self.box = ""
        self.plug = ""
        self.gps = (None, None)
        

    def get_state(self):
        return {
            "type": "info",
            "name": self.name,
            "box": self.box,
            "plug": self.plug,
            "gps": self.gps
        }

    async def send_state_update(self):
        await self.ws.send_broadcast(self.get_state())

    async def on_user_name(self, new):
        self.name = new
        await self.send_state_update()

    async def on_user_box(self, new):
        self.box = new
        await self.send_state_update()

    async def on_user_plug(self, new):
        self.plug = new
        await self.send_state_update()

    async def on_user_location(self, new_gps):
        self.gps = new_gps
        await self.send_state_update()

    async def on_message(self, message):
        if message["type"] == "name":
            await self.on_user_name(message["name"])
        if message["type"] == "box":
            await self.on_user_box(message["box"])
        if message["type"] == "plug":
            await self.on_user_plug(message["plug"])
        if message["type"] == "gps":
            await self.on_user_location(message["gps"])

    async def send_state_init(self, client):
        await self.ws.send_client(client, self.get_state())


class StateSubprocess(StateBaseClass):
    #run_id: int
    process_lock: asyncio.Lock

    process: None | subprocess.Popen = None
    #forward_socket: None | wsc.WebSocketClientProtocol = None

    state_info: StateInfo
    results_folder: str

    def __init__(self, ws: "ui_link.UI_Link", state_info, results_folder):
        super().__init__(ws)
    
        #self.run_id = 0
        self.process_lock = asyncio.Lock()

        self.process = None

        self.state_info = state_info

        self.results_folder = results_folder

        #self.forward_socket = None

    def check_running_impl(self):
        if self.process is not None:
            if self.process.poll() is None:
                return True
            else:
                self.process = None
        return False

    async def check_running(self):
        async with self.process_lock:
            return self.check_running_impl()

    async def get_state(self):
        return {
            "type": "process",
            "running": await self.check_running()
        }

    async def send_state_update(self):
        await self.ws.send_broadcast(await self.get_state())

    async def on_message(self, message):
        if message["type"] == "start":
            #new_run_id = 0
            async with self.process_lock:
                #self.run_id += 1
                #new_run_id = self.run_id
                if self.process is None:
                    my_env = os.environ.copy()
                    my_env["OPENSSL_CONF"] = os.path.join(os.path.dirname(os.path.realpath(__file__)), "../../openssl.conf")

                    self.process = subprocess.Popen(
                        ["python",
                        "-m", "code.main_ev",
                        "--name", self.state_info.name,
                        "--box", self.state_info.box,
                        "--plug", self.state_info.plug,
                        "--lat", str(self.state_info.gps[0]) if self.state_info.gps[0] is not None else "nan",
                        "--long", str(self.state_info.gps[1]) if self.state_info.gps[1] is not None else "nan",
                        os.path.join(self.results_folder, datetime.datetime.now(datetime.timezone.utc).strftime("%Y_%m_%d_%H_%M_%S"))
                        ],
                        cwd=os.path.join(os.path.dirname(os.path.realpath(__file__)), "../../"), env=my_env
                    )
                
            #asyncio.ensure_future(self.thread_runner(new_run_id))

        if message["type"] == "sigint":
            async with self.process_lock:
                if self.process is not None:
                    self.process.send_signal(signal.SIGINT)
        if message["type"] == "sigterm":
            async with self.process_lock:
                if self.process is not None:
                    self.process.send_signal(signal.SIGTERM)
        if message["type"] == "sigkill":
            async with self.process_lock:
                if self.process is not None:
                    self.process.kill()
                    self.process = None
                    
    async def send_state_init(self, client):
        await self.ws.send_client(client, await self.get_state())


class StateBasic(StateBaseClass):
    last_measurement: CPMeasurement | None

    def __init__(self, ws: "ui_link.UI_Link"):
        super().__init__(ws)

        self.last_measurement = None

    def get_state(self):
        return {
            "type": "basic_signaling",
            "state": self.last_measurement.to_json() if self.last_measurement is not None else None
        }

    async def send_state_update(self):
        await self.ws.send_broadcast(self.get_state())

    async def send_state_init(self, client):
        await self.ws.send_client(client, self.get_state())

    async def set_measurement(self, meas):
        self.last_measurement = meas
        await self.send_state_update()



class StateProto(StateBaseClass):
    results: Dict[str, bool | None]

    def __init__(self, ws: "ui_link.UI_Link"):
        super().__init__(ws)

        self.results = {
            "DIN": None,
            "V2V10": None,
            "V2V13": None,
            "V20DC": None,
        }

    async def send_state_update(self):
        await self.ws.send_broadcast({
            "type": "Proto",
            "result": self.results
        })

    async def send_state_init(self, client):
        await self.ws.send_client(client, {
            "type": "Proto",
            "result": self.results
        })

    async def reset(self):
        for key in self.results.keys():
            self.results[key] = None

    async def set_result(self, proto: str, result: bool | None):
        self.results[proto] = result
        await self.send_state_update()

    async def set_results(self, results: Dict[str, bool | None]):
        self.results = results
        await self.send_state_update()



class StateV2G(StateBaseClass):
    session_id: str
    service_discovery: str

    def __init__(self, ws: "ui_link.UI_Link"):
        super().__init__(ws)
        self.session_id = ""
        self.service_discovery = ""

    async def send_state_update(self):
        await self.ws.send_broadcast({
            "type": "V2G",
            "session_id": self.session_id,
            "service_discovery": self.service_discovery
        })

    async def send_state_init(self, client):
        await self.ws.send_client(client, {
            "type": "V2G",
            "session_id": self.session_id,
            "service_discovery": self.service_discovery
        })

    async def set_session_id(self, session_id):
        self.session_id = session_id
        await self.send_state_update()

    async def set_service_discovery(self, service_discovery):
        self.service_discovery = service_discovery
        await self.send_state_update()

