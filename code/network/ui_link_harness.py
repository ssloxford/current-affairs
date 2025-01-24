from __future__ import annotations

import websockets.client as wsc
import websockets.server as wss
import websockets.exceptions as wse
import traceback
import asyncio
import logging
from typing import List
from . import states
from ..utils import settings
import json

from . import ui_link

class UI_Harness(ui_link.UI_Link):
    state_info: states.StateInfo
    state_process: states.StateSubprocess
    
    def __init__(self, results_folder):
        super().__init__()

        self.state_info = states.StateInfo(self)
        self.state_process = states.StateSubprocess(self, self.state_info, results_folder)

    @staticmethod
    async def run_forward(client: wss.WebSocketServerProtocol, forward: wsc.WebSocketClientProtocol):
        try:
            async for message in forward:
                await client.send(json.dumps({"type":"forward", "data":json.loads(message)}))

        except wse.ConnectionClosed:
            pass
        finally:
            try:
                await client.send(json.dumps({"type": "forward_fail"}))
            except wse.ConnectionClosed:
                pass
    
    async def on_websocket_client_inner(self, client: wss.WebSocketServerProtocol):
        await self.state_info.send_state_init(client)
        await self.send_client(client, {
            "type": "init_done"
        })

        forward_socket: None | wsc.WebSocketClientProtocol = None    

        async for message_s in client:
            try:
                message = json.loads(message_s)
                
                if message["type"] == "info":
                    await self.state_info.on_message(message["data"])
                elif message["type"] == "process":
                    await self.state_process.on_message(message["data"])

                elif message["type"] == "forward_open":
                    if forward_socket is not None:
                        await forward_socket.close()

                    try:
                        forward_socket = await wsc.connect(f"ws://localhost:{settings.WS_PORT_NSSL}")
                        await client.send(json.dumps({"type": "forward_success"}))
                        asyncio.ensure_future(UI_Harness.run_forward(client, forward_socket))
                        
                    except (OSError, wse.InvalidHandshake):
                        await client.send(json.dumps({"type": "forward_fail"}))
                        pass


                elif message["type"] == "forward":
                    if forward_socket is not None:
                        try:
                            await forward_socket.send(json.dumps(message["data"]))
                        except wse.ConnectionClosed:
                            forward_socket = None

                    if forward_socket is None:
                        await client.send(json.dumps({"type": "forward_fail"}))
                
                #elif message["type"] == "shutdown":
                #    os.system("shutdown -h now")

            except KeyboardInterrupt:
                raise
            except asyncio.CancelledError:
                raise
            except:
                logging.error(traceback.format_exc())
                pass
