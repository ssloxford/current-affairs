"""
Implementation of SDP process
"""

from __future__ import annotations

import socket
import struct
from typing import Any, Callable, NamedTuple, Tuple
from ..utils.data_saver import DataSaver
from ..utils.async_utils import blocking_to_async
import ipaddress

from ..network.states import StateBaseClass
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from ..network import ui_link_inner as ui_link

class SDPError(Exception):
    def __init__(self, message):            
        # Call the base class constructor with the parameters it needs
        super().__init__(message)


class Packet(NamedTuple):
    data: bytes
    addr: Tuple[str, int, int, int]

    def to_json(self):
        return {
            "data": self.data.hex(),
            "addr": {
                "ip": ipaddress.ip_address(self.addr[0]).exploded,
                "port": self.addr[1],
                "flow": self.addr[2],
                "scope": self.addr[3],
            }
        }

async def send_multicast(interface: str, request: bytes):
    print("Sending multicast on " + interface)
    # Create the UDP socket
    with socket.socket(socket.AF_INET6, socket.SOCK_DGRAM, 0) as sock:
        #Bind to interface
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BINDTODEVICE, interface.encode())#type: ignore

        #Set IPv6 mode
        sock.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_V6ONLY, 1)

        #Create addresses
        multicast_addr_obj = socket.getaddrinfo('ff02::1', 15118, socket.AF_INET6)[0][4]

        # Set socket receive timeout to 0.25 seconds
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVTIMEO, struct.pack('LL', 0, 250000))

        # Set the TTL (time-to-live) for the multicast packet
        sock.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_MULTICAST_HOPS, 1)

        try:
            sock.sendto(request, multicast_addr_obj)
        except:
            print("Failed to send")

        response, reply_addr = await blocking_to_async(sock.recvfrom)(1024)
        print(response, reply_addr)

        return Packet(data = response, addr = reply_addr)



class SDPRequestData(NamedTuple):
    #Request
    tls: bool
    tcp: bool

    def to_json(self):
        return {
            "tls": self.tls,
            "tcp": self.tcp
        }
    
    def encode(self):
        return (
            b"\x01\xFE\x90\x00\x00\x00\x00\x02" +
            (b"\x00" if self.tls else b"\x10") +
            (b"\x00" if self.tcp else b"\x10")
        )

class SDPResponseData(NamedTuple):
    ip: str
    port: int
    tls: bool
    tcp: bool

    def to_json(self):
        return {
            "ip": ipaddress.ip_address(self.ip).exploded,
            "port": self.port,
            "tls": self.tls,
            "tcp": self.tcp
        }

    @staticmethod
    def read_packet(raw_packet: bytes) -> "SDPResponseData":
        if len(raw_packet) != (8 + 16 + 2 + 2):
            raise SDPError("Invalid length")
        
        if raw_packet[0:8] != b"\x01\xFE\x90\x01\x00\x00\x00\x14":
            raise SDPError("Invalid header")

        return SDPResponseData(
            ip = socket.inet_ntop(socket.AF_INET6, raw_packet[8:24]),
            port = (raw_packet[24] << 8) | raw_packet[25],
            tls = (raw_packet[26] == 0),
            tcp = (raw_packet[27] == 0),
        )

class SDPRequest():
    """
    SDP client for EV
    """
    #Request
    req: SDPRequestData

    #Response
    raw: Packet | None

    #Parsed response
    res: SDPResponseData | None

    success: bool

    def __init__(self, req: SDPRequestData):
        self.req = req

        self.raw = None

        self.res = None
        self.success = False

    def on_response(self, packet: Packet):
        self.raw = packet

        self.res = SDPResponseData.read_packet(self.raw.data)
        self.success = True

    def to_json(self):
        return {
            "req": self.req.to_json(),
            "raw": self.raw.to_json() if self.raw is not None else None,
            "res": self.res.to_json() if self.res is not None else None,
        }


async def sdp_client_single(logger: DataSaver, interface: str, req_tls: bool, req_tcp: bool = True) -> SDPRequest:
    sdp: SDPRequest = SDPRequest(SDPRequestData(req_tls, req_tcp))

    packet = await send_multicast(interface, sdp.req.encode())
    
    try:
        sdp.on_response(packet)
        return sdp
    finally:
        logger.log_entry("RES", sdp.to_json())

async def sdp_client(logger: DataSaver, interface: str, tls: bool, retries: int = 50) -> SDPRequest:
    with logger.trace_enter("SDP"):
        sdp_res = None
        for _ in range(retries):
            try:
                sdp_res = await sdp_client_single(logger, interface, tls)
                break
            except BlockingIOError:
                pass
        if sdp_res is None:
            raise SDPError(f"SDP Failed after {retries} retries")
        return sdp_res

class StateSDPClient(StateBaseClass):
    result: SDPRequest | None

    def __init__(self, ws: "ui_link.UI_Inner"):
        super().__init__(ws)

        self.result = None

    async def send_state_update(self):
        if self.result is None:
            return
        await self.ws.send_broadcast({
            "type": "SDP_Client",
            "result": self.result.to_json()
        })

    async def send_state_init(self, client):
        if self.result is not None:
            await self.ws.send_client(client, {
            "type": "SDP_Client",
            "result": self.result.to_json()
        })

    async def set_response(self, result):
        self.result = result
        await self.send_state_update()
