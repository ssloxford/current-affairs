from __future__ import annotations
import atexit
from typing import Any, List, Tuple

import requests
import subprocess
import xml.etree.ElementTree as ET
import os
from ..utils.async_utils import blocking_to_async

class ExiException(Exception):
    def __init__(self, msg):
        super().__init__(msg)

class ExiInterface():
    """Connection to an EXI Server, specific to each schema"""

    url: str
    schema_id: int
    def __init__(self, url: str, schema_id: int):
        self.url = url
        self.schema_id = schema_id

    async def encode(self, xml_obj: ET.Element) -> bytes:
        data = ET.tostring(xml_obj, encoding="unicode")
        #print(self.url, data)
        x = (await blocking_to_async(requests.post)(self.url, headers={"Format": "XML", "Connection": "close", "Grammar": str(self.schema_id)}, data=data, timeout=0.5)).text
        if(x == "null"):
            raise ExiException("Encode failed")
        return bytes.fromhex(x)

    async def decode(self, exi_bytes: bytes) -> Tuple[str, ET.Element]:
        data = exi_bytes.hex()
        #print(self.url, data)
        
        x = (await blocking_to_async(requests.post)(self.url, headers={"Format": "EXI", "Connection": "close", "Grammar": str(self.schema_id)}, data=data, timeout=0.5)).text
        
        if(x == "null"):
            raise ExiException("Decode failed")
        #print(x)
        return (x, ET.fromstring(x))

class ExiProcess:
    """Wrapper for running the EXI java process"""

    process: subprocess.Popen

    def __init__(self, jar_dir, schema_dir, schemas):
        schema_args: List[str] = [arg for schema in schemas for arg in ["-S", os.path.join(schema_dir, schema)]]
        print(schema_args)

        self.process = subprocess.Popen([
                "java",
                "-jar",
                os.path.join(jar_dir, "V2Gdecoder-jar-with-dependencies.jar"),
                *schema_args,
                "-w",
                "9000"
            ],
            #stdout=subprocess.DEVNULL,
            #stderr=subprocess.STDOUT
        )

        atexit.register(subprocess.Popen.kill, self.process)

EXI_BASE_DIR = os.path.join(os.path.dirname(__file__), "../../schemas/")
SCHEMA_BASE_DIR = os.path.join(os.path.dirname(__file__), "../../schemas/")

# Start process
EXI_PROCESS = ExiProcess(
    EXI_BASE_DIR,
    SCHEMA_BASE_DIR,
    [
        "AppProto/V2G_CI_AppProtocol.xsd",
        "DIN/V2G_CI_MsgDef.xsd",
        "2V10/V2G_CI_MsgDef.xsd",
        "2V13/V2G_CI_MsgDef.xsd",
        "20/V2G_CI_CommonMessages.xsd", #8002
        "20/V2G_CI_AC.xsd", #8003
        "20/V2G_CI_DC.xsd", #8004
        "20/V2G_CI_ACDP.xsd", #8005
        "20/V2G_CI_WPT.xsd", #8006
    ]
)

# List of interfaces for each protocol version
EXI_INSTANCE_APP = ExiInterface("http://localhost:9000", 0)
EXI_INSTANCE_DIN = ExiInterface("http://localhost:9000", 1)
EXI_INSTANCE_V2V10 = ExiInterface("http://localhost:9000", 2)
EXI_INSTANCE_V2V13 = ExiInterface("http://localhost:9000", 3)
EXI_INSTANCE_V20CM = ExiInterface("http://localhost:9000", 4)
EXI_INSTANCE_V20AC = ExiInterface("http://localhost:9000", 5)
EXI_INSTANCE_V20DC = ExiInterface("http://localhost:9000", 6)
EXI_INSTANCE_V20ACDP = ExiInterface("http://localhost:9000", 7)
EXI_INSTANCE_V20WPT = ExiInterface("http://localhost:9000", 8)