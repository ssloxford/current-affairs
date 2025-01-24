import websockets.server as ws
import websockets.exceptions as wse
import traceback
import asyncio
import logging
from typing import List
from . import states
from . import states_task
from ..utils import settings
import json
import ssl
import os

from . import ui_link

from ..interface import slac
from ..interface import sdp

class UI_Inner(ui_link.UI_Link):
    clients: List[ws.WebSocketServerProtocol]
    client_lock: asyncio.Lock

    state_tasks: List[states_task.StateTask]
    state_basic: states.StateBasic
    waiter_start: states.StateWaiter
    state_slac: slac.StateSLAC
    state_sdp: sdp.StateSDPClient
    state_proto: states.StateProto
    state_v2g: states.StateV2G
    
    def __init__(self):
        self.clients = []
        self.client_lock = asyncio.Lock()

        self.state_tasks = []
        self.state_basic = states.StateBasic(self)
        self.waiter_start = states.StateWaiter(self, "waiter_start")
        self.waiter_plug = states.StateWaiter(self, "waiter_plug")
        self.waiter_done = states.StateWaiter(self, "waiter_done")
        self.state_slac = slac.StateSLAC(self)
        self.state_sdp = sdp.StateSDPClient(self)
        self.state_proto = states.StateProto(self)
        self.state_v2g = states.StateV2G(self)

    def add_task(self, task: states_task.StateTask):
        if task not in self.state_tasks:
            if task.requires is not None:
                self.add_task(task.requires.task)
            self.state_tasks.append(task)

    async def on_websocket_message(self, message_s):
        try:
            message = json.loads(message_s)
            #print(message)
            
            if message["type"] == "waiter_start":
                await self.waiter_start.on_message(message["data"])
            elif message["type"] == "waiter_plug":
                await self.waiter_plug.on_message(message["data"])
            elif message["type"] == "waiter_done":
                await self.waiter_done.on_message(message["data"])
            else:
                print("Unknown type")
        except KeyboardInterrupt:
            raise
        except:
            logging.error(traceback.format_exc())
            pass

    async def on_websocket_client(self, client):
        print("Client connected")
        async with self.client_lock:
            self.clients.append(client)
        
        try:
            #Send all tasks
            await self.send_client(client, {
                "type": "init_tasks",
                "tasks": [ t.get_state_init() for t in self.state_tasks ]
            })

            await self.state_basic.send_state_init(client)
            await self.waiter_start.send_state_init(client)
            await self.waiter_plug.send_state_init(client)
            await self.waiter_done.send_state_init(client)
            await self.state_slac.send_state_init(client)
            await self.state_sdp.send_state_init(client)
            await self.state_proto.send_state_init(client)
            await self.state_v2g.send_state_init(client)
            await self.send_client(client, {
                "type": "init_done"
            })

            async for message in client:
                await self.on_websocket_message(message)
        except wse.ConnectionClosedError:
            print("Client crash")
        except:
            print("Client unexpected crash")
            raise
        finally:
            async with self.client_lock:
                self.clients.remove(client)
                print(self.clients)
            print("Client done")
