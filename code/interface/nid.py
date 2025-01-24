"""
Compute NID from NMK
"""

import hashlib

def to_bits(bytes, len):
    return (("0"*len) + bin(int.from_bytes(bytes, byteorder="little"))[2:])[-len:]

def to_nid(nmk: bytes) -> bytes:

    val = nmk
    for _ in range(5):
        val = hashlib.sha256(val).digest()

    nid = val
    nid_truncated = to_bits(nid, 256)[-56:]
    nid_bits = "0000" + nid_truncated[0:4] + nid_truncated[8:]
    return int(nid_bits, base=2).to_bytes(7, byteorder="little")

if __name__ == "__main__":
    print(to_nid(bytes.fromhex("50D3E4933F855B7040784DF815AA8DB7")).hex().upper())
    print(to_nid(bytes.fromhex("0088119922AA33BB44CC55DD66EE77FF")).hex().upper())
