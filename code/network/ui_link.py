from abc import abstractmethod
import websockets.server as ws
import websockets.exceptions as wse
import traceback
import asyncio
from typing import Any, List
from ..utils import settings
import json
import ssl
import os

class UI_Link:
    clients: List[ws.WebSocketServerProtocol]
    client_lock: asyncio.Lock

    
    def __init__(self):
        self.clients = []
        self.client_lock = asyncio.Lock()

    async def send_broadcast(self, message):
        message_s = json.dumps(message)
        async with self.client_lock:
            try:
                await asyncio.gather(*[client.send(message_s) for client in self.clients])
            except (wse.ConnectionClosed, wse.ConnectionClosedError):
                pass

    async def send_client(self, client, message):
        message_s = json.dumps(message)
        try:
            await client.send(message_s)
        except (wse.ConnectionClosed, wse.ConnectionClosedError):
            pass

    @abstractmethod
    async def on_websocket_client_inner(self, client):
        pass

    async def on_websocket_client(self, client):
        print("Client connected")
        async with self.client_lock:
            self.clients.append(client)
        
        try:
            await self.on_websocket_client_inner(client)
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

    async def start_websocket_server(self, use_ssl = False):
        ssl_context = None
        if use_ssl:
            ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)

            # Generate with Lets Encrypt, copied to this location, chown to current user and 400 permissions
            ssl_cert = os.path.join(os.path.dirname(os.path.realpath(__file__)),"../../www/certs/certificate.pem")
            ssl_key = os.path.join(os.path.dirname(os.path.realpath(__file__)),"../../www/certs/key.pem")

            ssl_context.load_cert_chain(ssl_cert, keyfile=ssl_key)

        print("Starting websocket")
        server = await ws.serve(
            ws_handler = self.on_websocket_client,
            port = settings.WS_PORT_SSL if use_ssl else settings.WS_PORT_NSSL,
            start_serving = False, ssl = ssl_context)
        try:
            await server.serve_forever()
        except asyncio.CancelledError:
            print("Server cancelled")
            pass
        except KeyboardInterrupt:
            print("Keyboard Interrupt")
            pass
        except:
            traceback.print_exc()
            pass
        finally:
            server.close()