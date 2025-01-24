from __future__ import annotations

from abc import abstractmethod, ABC
import socket
import struct
from typing import Any, List, NamedTuple, Tuple
from ..utils.data_saver import DataSaver
import asyncio

from ..v2g.exi_interface import ExiException

from ..utils.async_utils import blocking_to_async

import OpenSSL.crypto
import OpenSSL.SSL

class V2GPacket(NamedTuple):
    version: int
    type: int
    data: bytes

class WrappedSocket(ABC):
    @abstractmethod
    def close(self):
        raise Exception()

    async def send_v2g_packet(self, packet: V2GPacket):
        header = struct.pack(">BBHI", packet.version, 255-packet.version, packet.type, len(packet.data))
        #Not a standard given number, just a reasonable limit
        await self.send(header + packet.data)

    async def read_v2g_packet(self) -> V2GPacket:
        header = await self.read(8)
        if(len(header) == 0):
            raise ExiException("Connection closed")
        if(len(header) < 8):
            raise ExiException("Incomplete packet header")
        version, inverse_version, type, data_length = struct.unpack(">BBHI", header)
        if(version + inverse_version != 255):
            raise ExiException("Invalid packet header")
        if(version != 1):
            raise ExiException("Unknown packet version")
        #Not a standard given number, just a reasonable limit
        if(data_length > 65535):
            raise ExiException("Exi packet too long")
        res = await self.read(data_length)
        if(len(res) < data_length):
            raise ExiException("Incomplete packet data")
        return V2GPacket(version, type, res)

    async def read(self, n) -> bytes:
        buf = b''
        while (len(buf) < n):
            tmp = await self._read(n)
            buf = buf + tmp
        return buf

    async def send(self, b: bytes):
        await self._sendall(b)

    @abstractmethod
    async def _read(self, n) -> bytes:
        raise Exception()

    @abstractmethod
    async def _sendall(self, b: bytes):
        raise Exception()

class WrappedSocketRaw(WrappedSocket):
    s: socket.socket

    def __init__(self, s: socket.socket):
        self.s = s

    def close(self):
        self.s.close()

    async def _read(self, n: int) -> bytes:
        return await blocking_to_async(self.s.recv)(n)

    async def _sendall(self, b: bytes):
        await blocking_to_async(self.s.sendall)(b)

class WrappedSocketTLS(WrappedSocket):
    conn: OpenSSL.SSL.Connection

    def __init__(self, conn: OpenSSL.SSL.Connection):
        self.conn = conn

    def close(self):
        self.conn.close()

    async def _read(self, n: int) -> bytes:
        try:
            return await blocking_to_async(self.conn.recv)(n)
        except OpenSSL.SSL.WantReadError:
            await asyncio.sleep(0.01)
            return b""

    async def _sendall(self, b: bytes):
        await blocking_to_async(self.conn.sendall)(b)


def dump_cert_chain(chain: List[OpenSSL.crypto.X509] | None):
    if chain is None:
        return None
    return '\n\n'.join([OpenSSL.crypto.dump_certificate(OpenSSL.crypto.FILETYPE_PEM, c).decode("ascii") for c in chain])
    


# Socket utils


async def open_client_socket(interface: str, hostname: str, port: int) -> socket.socket:
    # Create the UDP socket
    sock = socket.socket(socket.AF_INET6, socket.SOCK_STREAM, 0)

    #Bind to interface
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_BINDTODEVICE, interface.encode())#type: ignore

    # Set socket receive timeout to 5 seconds
    sock.settimeout(5)
    #sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVTIMEO, struct.pack('QQ', 5, 0))

    #Set IPv6 mode
    sock.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_V6ONLY, 1)

    sock.connect((hostname, port))
    print("Timeout", sock.gettimeout())

    return sock

