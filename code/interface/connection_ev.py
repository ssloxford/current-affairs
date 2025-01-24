"""
Utilities to create a connection as an EV
"""

from __future__ import annotations

import socket
import struct
from typing import List, Tuple
from ..utils.data_saver import DataSaver

from .trusted_ca_keys import TrustedCAKeysExtension, TrustedCAKey
from . import connection_tls

import os
import traceback

import OpenSSL.crypto
import OpenSSL.SSL

from . import socket_wrapper

async def create_ntls(
        logger: DataSaver,
        interface: str, hostname: str, port: int) -> socket_wrapper.WrappedSocketRaw:
    sock = await socket_wrapper.open_client_socket(interface, hostname, port)
    return socket_wrapper.WrappedSocketRaw(sock)

async def create_tls_dash2_suite(
        logger: DataSaver,
        interface: str, hostname: str, port: int,
        trusted_keys: List[TrustedCAKey],
        suites: List[str]
        ) -> socket_wrapper.WrappedSocketTLS:
    with logger.trace_enter("UTLS"):
        return await connection_tls.create_tls_client(
            logger, interface, hostname, port,
            connection_tls.TLS_VERSIONS["VSUITE"], suites,
            None, TrustedCAKeysExtension.to_bytes(trusted_keys)
        )

async def create_tls_dash2(
        logger: DataSaver,
        interface: str, hostname: str, port: int,
        trusted_keys: List[TrustedCAKey]
        ) -> socket_wrapper.WrappedSocketTLS:
    with logger.trace_enter("UTLS"):
        return await connection_tls.create_tls_client(
            logger, interface, hostname, port,
            connection_tls.TLS_VERSIONS["V2"], connection_tls.TLS_CIPHER_GROUPS["V2"],
            None, TrustedCAKeysExtension.to_bytes(trusted_keys)
        )


async def create_tls_old(
        logger: DataSaver,
        interface: str, hostname: str, port: int,
        trusted_keys: List[TrustedCAKey]
        ) -> socket_wrapper.WrappedSocketTLS:
    with logger.trace_enter("UTLS"):
        return await connection_tls.create_tls_client(
            logger, interface, hostname, port,
            connection_tls.TLS_VERSIONS["PRE_V2"], connection_tls.TLS_CIPHER_GROUPS["TLS11"],
            None, TrustedCAKeysExtension.to_bytes(trusted_keys)
        )

async def create_tls_dash2_bad_trusted(
        logger: DataSaver,
        interface: str, hostname: str, port: int,
        ) -> socket_wrapper.WrappedSocketTLS:
    with logger.trace_enter("UTLS"):
        return await connection_tls.create_tls_client(
            logger, interface, hostname, port,
            connection_tls.TLS_VERSIONS["V2"], connection_tls.TLS_CIPHER_GROUPS["V2"],
            None, b"\xff\xff"
        )



async def create_tls_dash20(
        logger: DataSaver,
        interface: str, hostname: str, port: int,
        client_auth: Tuple[List[OpenSSL.crypto.X509], OpenSSL.crypto.PKey]
        ) -> socket_wrapper.WrappedSocketTLS:
    with logger.trace_enter("MTLS"):
        if client_auth is None:
            print("No client certificate provided for -20 mode")
        return await connection_tls.create_tls_client(
            logger, interface, hostname, port,
            connection_tls.TLS_VERSIONS["V20"],
            [],
            #connection_tls.TLS_CIPHER_GROUPS["V20"],
            client_auth, None
        )