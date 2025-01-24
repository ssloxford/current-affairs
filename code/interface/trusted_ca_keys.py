from __future__ import annotations
from typing import List, Tuple
import OpenSSL.crypto
import OpenSSL.SSL

from OpenSSL._util import lib as _openssl_lib # type: ignore
from OpenSSL._util import ffi as _openssl_ffi # type: ignore

from enum import Enum
import struct

# Despite being a 2011 RFC, no major library seems to implement RFC 6066 trusted_ca_keys.
# OpenSSL allows custom extensions, but PyOpenSSL does not expose this api.
# So we force our way into it

class TrustedCAKeyType(Enum):
    pre_agreed = 0
    key_sha1_hash = 1
    x509_name = 2
    cert_sha1_hash = 3

class TrustedCAKey:
    type: TrustedCAKeyType
    key_sha1_hash: bytes | None
    x509_name: bytes | None
    cert_sha1_hash: bytes | None

    def __init__(
        self,
        type: TrustedCAKeyType,
        key_sha1_hash: bytes | None = None,
        x509_name: bytes | None = None,
        cert_sha1_hash: bytes | None = None
    ):
        self.type = type
        if self.type == TrustedCAKeyType.pre_agreed:
            pass
        elif self.type == TrustedCAKeyType.key_sha1_hash:
            if key_sha1_hash is not None and (len(key_sha1_hash) != 20):
                raise Exception("Invalid SHA1 key")
            self.key_sha1_hash = key_sha1_hash
        elif self.type == TrustedCAKeyType.x509_name:
            if x509_name is not None and (len(x509_name) > 0):
                raise Exception("Invalid X509 name")
            self.x509_name = x509_name
        elif self.type == TrustedCAKeyType.cert_sha1_hash:
            if cert_sha1_hash is not None and (len(cert_sha1_hash) != 20):
                raise Exception("Invalid SHA1 hash")
            self.cert_sha1_hash = cert_sha1_hash
        else:
            raise Exception("Unknown type")
    
    def to_json(self):
        res = {
            "type": self.type.name
        }
        if self.key_sha1_hash is not None:
            res["key_sha1_hash"] = self.key_sha1_hash.hex()
        if self.x509_name is not None:
            res["x509_name"] = self.x509_name.hex()
        if self.cert_sha1_hash is not None:
            res["cert_sha1_hash"] = self.cert_sha1_hash.hex()
        return res


    @staticmethod
    def new_pre_agreed():
        return TrustedCAKey(TrustedCAKeyType.pre_agreed)

    @staticmethod
    def new_key_sha1_hash(key_sha1_hash: bytes):
        return TrustedCAKey(TrustedCAKeyType.key_sha1_hash, key_sha1_hash = key_sha1_hash)

    @staticmethod
    def new_x509_name(x509_name: bytes):
        return TrustedCAKey(TrustedCAKeyType.x509_name, x509_name = x509_name)

    @staticmethod
    def new_cert_sha1_hash(cert_sha1_hash: bytes):
        return TrustedCAKey(TrustedCAKeyType.cert_sha1_hash, cert_sha1_hash = cert_sha1_hash)

    @staticmethod
    def new_x509(cert_sha1_hash: bytes):
        return TrustedCAKey(TrustedCAKeyType.cert_sha1_hash, cert_sha1_hash = cert_sha1_hash)

    def to_bytes(self) -> bytes:
        if self.type == TrustedCAKeyType.pre_agreed:
            return struct.pack(">B", self.type.value)
        if self.type == TrustedCAKeyType.key_sha1_hash and self.key_sha1_hash is not None:
            return struct.pack(">B20s", self.type.value, self.key_sha1_hash)
        if self.type == TrustedCAKeyType.x509_name and self.x509_name is not None:
            return struct.pack(f">BH{len(self.x509_name)}s", self.type.value, len(self.x509_name), self.x509_name)
        if self.type == TrustedCAKeyType.cert_sha1_hash and self.cert_sha1_hash is not None:
            return struct.pack(">B20s", self.type.value, self.cert_sha1_hash)
        raise Exception("Unknown type")
    
class TrustedCAKeysExtension(OpenSSL.SSL._CallbackExceptionHelper):# type: ignore
    content: bytes | None

    def __init__(self, parent: OpenSSL.SSL.Context, content: bytes | None):
        super().__init__()
        self.content = content
        self.parent = parent

        def add_cb(
            s, #SSL *s,
            ext_type, #unsigned int ext_type,
            out, #const unsigned char **out,
            outlen, #size_t *outlen,
            al, #int *al,
            add_arg, #void *add_arg
        ):
            #Dont include
            if self.content is None:
                return 0

            try:
                outbytes = self.content

                #Memory is owned by these objects. They will be freed by Cffi
                parent._my_trusted_ca_keys_message = [# type: ignore
                    _openssl_ffi.new("unsigned char *", len(outbytes)),
                    _openssl_ffi.new("unsigned char[]", outbytes),
                ]

                outlen[0] = parent._my_trusted_ca_keys_message[0][0]
                out[0] = parent._my_trusted_ca_keys_message[1]

                print("Added trusted_ca_keys: ", outbytes)

                return 1
            except Exception as e:
                self._problems.append(e)
                print(e)
                return -1

        self.add_cb = _openssl_ffi.callback("int (*)(SSL *, unsigned int, const unsigned char **, size_t *, int *, void *)", add_cb)

        def dont_add_cb(
            s, #SSL *s,
            ext_type, #unsigned int ext_type,
            out, #const unsigned char **out,
            outlen, #size_t *outlen,
            al, #int *al,
            add_arg, #void *add_arg
        ):
            return 0
    
        self.dont_add_cb = _openssl_ffi.callback("int (*)(SSL *, unsigned int, const unsigned char **, size_t *, int *, void *)", dont_add_cb)

    def inject(self):
        self.parent._my_trusted_ca_keys_obj = self# type: ignore
        #print(vars(_openssl_lib))
        #We need to make our own extension for trusted_ca_keys
        _openssl_lib.SSL_CTX_add_client_custom_ext(
            self.parent._context, #SSL_CTX *ctx
            3, #unsigned int ext_type = trusted_ca_keys
            #_openssl_lib.SSL_EXT_TLS_ONLY | _openssl_lib.SSL_EXT_CLIENT_HELLO, #unsigned int context
            self.add_cb, #SSL_custom_ext_add_cb_ex add_cb
            _openssl_ffi.NULL, #SSL_custom_ext_free_cb_ex free_cb
            _openssl_ffi.NULL, #void *add_arg
            _openssl_ffi.NULL, #SSL_custom_ext_parse_cb_ex parse_cb
            _openssl_ffi.NULL #void *parse_arg
        )

        _openssl_lib.SSL_CTX_add_server_custom_ext(
            self.parent._context, #SSL_CTX *ctx
            3, #unsigned int ext_type = trusted_ca_keys
            #_openssl_lib.SSL_EXT_TLS_ONLY | _openssl_lib.SSL_EXT_CLIENT_HELLO, #unsigned int context
            self.dont_add_cb, #SSL_custom_ext_add_cb_ex add_cb
            _openssl_ffi.NULL, #SSL_custom_ext_free_cb_ex free_cb
            _openssl_ffi.NULL, #void *add_arg
            _openssl_ffi.NULL, #SSL_custom_ext_parse_cb_ex parse_cb
            _openssl_ffi.NULL #void *parse_arg
        )

    @staticmethod
    def to_bytes(trusted: List[TrustedCAKey]):
        joins = []
        total_len = 0
        for t in trusted:
            entry = t.to_bytes()
            total_len += len(entry)
            joins.append(entry)

        return struct.pack(">H", total_len) + b''.join(joins)