"""
Utilities to create TLS connections
"""

from __future__ import annotations

import socket
from typing import Dict, List, Tuple, Any

from ..utils.async_utils import blocking_to_async
from ..utils.data_saver import DataSaver

from .trusted_ca_keys import TrustedCAKeysExtension, TrustedCAKey

import os
import traceback

import ipaddress

import OpenSSL.crypto
import OpenSSL.SSL

from . import socket_wrapper

class TLS_Version:
    min: int | None
    max: int | None

    def __init__(self, min: int | None, max: int | None):
        self.min = min
        self.max = max

TLS_VERSIONS: Dict[str, TLS_Version] = {
    "V2": TLS_Version(OpenSSL.SSL.TLS1_2_VERSION, None),
    "VSUITE": TLS_Version(OpenSSL.SSL.TLS1_2_VERSION, OpenSSL.SSL.TLS1_2_VERSION),
    "V20": TLS_Version(OpenSSL.SSL.TLS1_3_VERSION, None),
    "PRE_V2": TLS_Version(None, OpenSSL.SSL.TLS1_1_VERSION),
    "PRE_V20": TLS_Version(None, OpenSSL.SSL.TLS1_2_VERSION),
}

TLS_CIPHER_GROUPS: Dict[str, List[str]] = {
    "V2": ["ECDHE-ECDSA-AES128-SHA256", "ECDH-ECDSA-AES128-SHA256"],
    "V20": ["TLS_AES_256_GCM_SHA384", "TLS_CHACHA20_POLY1305_SHA256"],
    "OTHER_TLS13": ["TLS_AES_128_GCM_SHA256", "TLS_AES_128_CCM_8_SHA256", "TLS_AES_128_CCM_SHA256"],
    #List of Iana recommended
    "OTHER_STRONG_TLS12": ["ECDHE-ECDSA-AES256-GCM-SHA384","ECDHE-RSA-AES256-GCM-SHA384","DHE-RSA-AES256-GCM-SHA384","ECDHE-ECDSA-CHACHA20-POLY1305","ECDHE-RSA-CHACHA20-POLY1305","DHE-RSA-CHACHA20-POLY1305","DHE-RSA-AES256-CCM","ECDHE-ECDSA-AES128-GCM-SHA256","ECDHE-RSA-AES128-GCM-SHA256","DHE-RSA-AES128-GCM-SHA256","DHE-RSA-AES128-CCM","DHE-PSK-AES256-GCM-SHA384","DHE-PSK-CHACHA20-POLY1305","ECDHE-PSK-CHACHA20-POLY1305","DHE-PSK-AES256-CCM","DHE-PSK-AES128-GCM-SHA256","DHE-PSK-AES128-CCM",],
    #List of not recommended, except for one used by -2
    "OTHER_INSECURE_TLS12": ["DHE-DSS-AES256-GCM-SHA384","ECDHE-ECDSA-AES256-CCM8","ECDHE-ECDSA-AES256-CCM","DHE-RSA-AES256-CCM8","ECDHE-ECDSA-ARIA256-GCM-SHA384","ECDHE-ARIA256-GCM-SHA384","DHE-DSS-ARIA256-GCM-SHA384","DHE-RSA-ARIA256-GCM-SHA384","ADH-AES256-GCM-SHA384","DHE-DSS-AES128-GCM-SHA256","ECDHE-ECDSA-AES128-CCM8","ECDHE-ECDSA-AES128-CCM","DHE-RSA-AES128-CCM8","ECDHE-ECDSA-ARIA128-GCM-SHA256","ECDHE-ARIA128-GCM-SHA256","DHE-DSS-ARIA128-GCM-SHA256","DHE-RSA-ARIA128-GCM-SHA256","ADH-AES128-GCM-SHA256","ECDHE-ECDSA-AES256-SHA384","ECDHE-RSA-AES256-SHA384","DHE-RSA-AES256-SHA256","DHE-DSS-AES256-SHA256","ECDHE-ECDSA-CAMELLIA256-SHA384","ECDHE-RSA-CAMELLIA256-SHA384","DHE-RSA-CAMELLIA256-SHA256","DHE-DSS-CAMELLIA256-SHA256","ADH-AES256-SHA256","ADH-CAMELLIA256-SHA256",
                             #"ECDHE-ECDSA-AES128-SHA256",
                             "ECDHE-RSA-AES128-SHA256","DHE-RSA-AES128-SHA256","DHE-DSS-AES128-SHA256","ECDHE-ECDSA-CAMELLIA128-SHA256","ECDHE-RSA-CAMELLIA128-SHA256","DHE-RSA-CAMELLIA128-SHA256","DHE-DSS-CAMELLIA128-SHA256","ADH-AES128-SHA256","ADH-CAMELLIA128-SHA256","ECDHE-ECDSA-AES256-SHA","ECDHE-RSA-AES256-SHA","DHE-RSA-AES256-SHA","DHE-DSS-AES256-SHA","DHE-RSA-CAMELLIA256-SHA","DHE-DSS-CAMELLIA256-SHA","AECDH-AES256-SHA","ADH-AES256-SHA","ADH-CAMELLIA256-SHA","ECDHE-ECDSA-AES128-SHA","ECDHE-RSA-AES128-SHA","DHE-RSA-AES128-SHA","DHE-DSS-AES128-SHA","DHE-RSA-SEED-SHA","DHE-DSS-SEED-SHA","DHE-RSA-CAMELLIA128-SHA","DHE-DSS-CAMELLIA128-SHA","AECDH-AES128-SHA","ADH-AES128-SHA","ADH-SEED-SHA","ADH-CAMELLIA128-SHA","RSA-PSK-AES256-GCM-SHA384","RSA-PSK-CHACHA20-POLY1305","DHE-PSK-AES256-CCM8","RSA-PSK-ARIA256-GCM-SHA384","DHE-PSK-ARIA256-GCM-SHA384","AES256-GCM-SHA384","AES256-CCM8","AES256-CCM","ARIA256-GCM-SHA384","PSK-AES256-GCM-SHA384","PSK-CHACHA20-POLY1305","PSK-AES256-CCM8","PSK-AES256-CCM","PSK-ARIA256-GCM-SHA384","RSA-PSK-AES128-GCM-SHA256","DHE-PSK-AES128-CCM8","RSA-PSK-ARIA128-GCM-SHA256","DHE-PSK-ARIA128-GCM-SHA256","AES128-GCM-SHA256","AES128-CCM8","AES128-CCM","ARIA128-GCM-SHA256","PSK-AES128-GCM-SHA256","PSK-AES128-CCM8","PSK-AES128-CCM","PSK-ARIA128-GCM-SHA256","AES256-SHA256","CAMELLIA256-SHA256","AES128-SHA256","CAMELLIA128-SHA256","ECDHE-PSK-AES256-CBC-SHA384","ECDHE-PSK-AES256-CBC-SHA","SRP-DSS-AES-256-CBC-SHA","SRP-RSA-AES-256-CBC-SHA","SRP-AES-256-CBC-SHA","RSA-PSK-AES256-CBC-SHA","DHE-PSK-AES256-CBC-SHA","ECDHE-PSK-CAMELLIA256-SHA384","RSA-PSK-CAMELLIA256-SHA384","DHE-PSK-CAMELLIA256-SHA384","AES256-SHA","CAMELLIA256-SHA","PSK-AES256-CBC-SHA384","PSK-AES256-CBC-SHA","PSK-CAMELLIA256-SHA384","ECDHE-PSK-AES128-CBC-SHA256","ECDHE-PSK-AES128-CBC-SHA","SRP-DSS-AES-128-CBC-SHA","SRP-RSA-AES-128-CBC-SHA","SRP-AES-128-CBC-SHA","RSA-PSK-AES128-CBC-SHA256","DHE-PSK-AES128-CBC-SHA256","RSA-PSK-AES128-CBC-SHA","DHE-PSK-AES128-CBC-SHA","ECDHE-PSK-CAMELLIA128-SHA256","RSA-PSK-CAMELLIA128-SHA256","DHE-PSK-CAMELLIA128-SHA256","AES128-SHA","SEED-SHA","CAMELLIA128-SHA","IDEA-CBC-SHA","PSK-AES128-CBC-SHA256","PSK-AES128-CBC-SHA","PSK-CAMELLIA128-SHA256"],
    "TLS11": ["DHE-RSA-CAMELLIA256-SHA256","DHE-DSS-CAMELLIA256-SHA256","ADH-CAMELLIA256-SHA256","DHE-RSA-CAMELLIA128-SHA256","DHE-DSS-CAMELLIA128-SHA256","ADH-CAMELLIA128-SHA256","ECDHE-ECDSA-AES256-SHA","ECDHE-RSA-AES256-SHA","DHE-RSA-AES256-SHA","DHE-DSS-AES256-SHA","DHE-RSA-CAMELLIA256-SHA","DHE-DSS-CAMELLIA256-SHA","AECDH-AES256-SHA","ADH-AES256-SHA","ADH-CAMELLIA256-SHA","ECDHE-ECDSA-AES128-SHA","ECDHE-RSA-AES128-SHA","DHE-RSA-AES128-SHA","DHE-DSS-AES128-SHA","DHE-RSA-SEED-SHA","DHE-DSS-SEED-SHA","DHE-RSA-CAMELLIA128-SHA","DHE-DSS-CAMELLIA128-SHA","AECDH-AES128-SHA","ADH-AES128-SHA","ADH-SEED-SHA","ADH-CAMELLIA128-SHA","CAMELLIA256-SHA256","CAMELLIA128-SHA256","ECDHE-PSK-AES256-CBC-SHA384","ECDHE-PSK-AES256-CBC-SHA","SRP-DSS-AES-256-CBC-SHA","SRP-RSA-AES-256-CBC-SHA","SRP-AES-256-CBC-SHA","RSA-PSK-AES256-CBC-SHA","DHE-PSK-AES256-CBC-SHA","ECDHE-PSK-CAMELLIA256-SHA384","RSA-PSK-CAMELLIA256-SHA384","DHE-PSK-CAMELLIA256-SHA384","AES256-SHA","CAMELLIA256-SHA","PSK-AES256-CBC-SHA384","PSK-AES256-CBC-SHA","PSK-CAMELLIA256-SHA384","ECDHE-PSK-AES128-CBC-SHA256","ECDHE-PSK-AES128-CBC-SHA","SRP-DSS-AES-128-CBC-SHA","SRP-RSA-AES-128-CBC-SHA","SRP-AES-128-CBC-SHA","RSA-PSK-AES128-CBC-SHA256","DHE-PSK-AES128-CBC-SHA256","RSA-PSK-AES128-CBC-SHA","DHE-PSK-AES128-CBC-SHA","ECDHE-PSK-CAMELLIA128-SHA256","RSA-PSK-CAMELLIA128-SHA256","DHE-PSK-CAMELLIA128-SHA256","AES128-SHA","SEED-SHA","CAMELLIA128-SHA","IDEA-CBC-SHA","PSK-AES128-CBC-SHA256","PSK-AES128-CBC-SHA","PSK-CAMELLIA128-SHA256",]
}

TLS_CIPHER_GROUPS["ALL_TLS12"] = TLS_CIPHER_GROUPS["V2"] + TLS_CIPHER_GROUPS["OTHER_STRONG_TLS12"] + TLS_CIPHER_GROUPS["OTHER_INSECURE_TLS12"]

#Version

async def tls_set_version(logger: DataSaver, ctx: OpenSSL.SSL.Context, version: TLS_Version):
    if version.min is not None:
        ctx.set_min_proto_version(version.min)
    if version.max is not None:
        ctx.set_max_proto_version(version.max)

#Verify

async def tls_set_verify(logger: DataSaver, ctx: OpenSSL.SSL.Context, need_cert: bool):
    ctx.set_verify(
        OpenSSL.SSL.VERIFY_PEER | (OpenSSL.SSL.VERIFY_FAIL_IF_NO_PEER_CERT if need_cert else 0),
        lambda conn, cert, errno, depth, preverify: True
    )

#Cert

async def tls_set_certificate(logger: DataSaver, ctx: OpenSSL.SSL.Context, cert: Tuple[List[OpenSSL.crypto.X509], OpenSSL.crypto.PKey]):
    print("#### SETTING CERT")
    ctx.use_privatekey(cert[1])
    ctx.use_certificate(cert[0][0])
    for c in cert[0][1:]:
        ctx.add_extra_chain_cert(c)

#OCSP

async def tls_set_ocsp_client(logger: DataSaver, ctx: OpenSSL.SSL.Context):
    def ocsp_callback(ctx, ocsp, args):
        logger.log_entry("OCSP", ocsp.hex())
        return True #We really dont actually care
    ctx.set_ocsp_client_callback(ocsp_callback)

async def tls_set_ocsp_server(logger: DataSaver, ctx: OpenSSL.SSL.Context, ocsp_data: bytes):
    def ocsp_callback(conn, data):
        return ocsp_data
    ctx.set_ocsp_server_callback(ocsp_callback, None)

#Keylog

async def tls_set_keylog_callback(logger: DataSaver, ctx: OpenSSL.SSL.Context):
    def keylog_callback(ctx, b: bytes):
        logger.log_entry("KEYS", b.decode("ascii"))
        try:
            with open(os.path.join(logger.result_subfolder, "../key.log"), "ab") as f:
                f.write(b + b'\n')
        except:
            traceback.print_exc()
            pass
        pass
    ctx.set_keylog_callback(keylog_callback)

#Trusted

async def tls_set_trusted_keys_client(logger: DataSaver, ctx: OpenSSL.SSL.Context, content: bytes):
    #Create TrustedCAKeysExtension
    ca_extension = TrustedCAKeysExtension(ctx, content)
    ca_extension.inject()

async def tls_set_trusted_keys_server(logger: DataSaver, ctx: OpenSSL.SSL.Context):
    def my_trusted_ca_callback(raw: bytes, parsed: List[TrustedCAKey], done: bool):
        logger.log_entry("TRUSTED", {
            "raw": raw.hex(),
            "parse_ok": done,
            "parsed": [key.to_json() for key in parsed]
        })
    ctx.my_trusted_ca_callback = my_trusted_ca_callback#type: ignore

    ca_extension = TrustedCAKeysExtension(ctx, None)
    ca_extension.inject()

# Main helper

async def create_tls_context(
        logger: DataSaver, server: bool,
        version: TLS_Version, ciphers: List[str],
        cert: Tuple[List[OpenSSL.crypto.X509], OpenSSL.crypto.PKey] | None = None,
        need_peer_cert: bool = False,
        ocsp_data: bytes | None = None,
        trusted_keys: bytes | None = None
        ):
    
    context = OpenSSL.SSL.Context(OpenSSL.SSL.TLS_SERVER_METHOD if server else OpenSSL.SSL.TLS_CLIENT_METHOD)

    context.set_tmp_ecdh(OpenSSL.crypto.get_elliptic_curve("prime256v1"))

    context.set_options(0x4)
    #pyopenssl_ext.set_timeout(context, 5)

    if len(ciphers) > 0:
        context.set_cipher_list((":".join(ciphers + ["TLS_EMPTY_RENEGOTIATION_INFO_SCSV"])).encode("ascii"))

    await tls_set_version(logger, context, version)
    await tls_set_verify(logger, context, need_peer_cert)

    if cert is not None:
        await tls_set_certificate(logger, context, cert)
    
    if server:
        if ocsp_data is not None:
            await tls_set_ocsp_server(logger, context, ocsp_data)
    else:
        await tls_set_ocsp_client(logger, context)

    await tls_set_keylog_callback(logger, context)

    if server:
            await tls_set_trusted_keys_server(logger, context)
    else:
        if trusted_keys is not None:
            await tls_set_trusted_keys_client(logger, context, trusted_keys)

    return context

async def create_tls_client(
    logger: DataSaver,
    interface: str, hostname: str, port: int,
    version: TLS_Version, ciphers: List[str],
    cert: Tuple[List[OpenSSL.crypto.X509], OpenSSL.crypto.PKey] | None,
    trusted_keys: bytes | None = None
):
    context = await create_tls_context(
        logger, False, version, ciphers,
        cert = cert, need_peer_cert=False,
        ocsp_data= None, trusted_keys = trusted_keys
    )

    conn = OpenSSL.SSL.Connection(context, await socket_wrapper.open_client_socket(interface, hostname, port))
    conn.request_ocsp()

    #Connect socket
    await blocking_to_async(conn.set_connect_state)()
    while True:
        try:
            await blocking_to_async(conn.do_handshake)()
            break
        except OpenSSL.SSL.WantReadError:
            pass

    logger.log_entry("CERT", socket_wrapper.dump_cert_chain(conn.get_peer_cert_chain()))

    return socket_wrapper.WrappedSocketTLS(conn)