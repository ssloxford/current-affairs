import argparse
from typing import Dict

from .interface.connection_tls import TLS_CIPHER_GROUPS
from .interface.trusted_ca_keys import TrustedCAKey, TrustedCAKeyType
from .certs import generate_self_signed_certificate, load_cert_chain
from .controller_ev import ControllerEV
from .experiment.experiment_ev import Task_EV_Conn_Base, Task_EV_SLAC, Task_EV_SDP, Task_EV_Conn_NTLS, Task_EV_Conn_V2, Task_EV_Conn_TLS_Old, Task_EV_Conn_V2_BadTrusted, Task_EV_Conn_V2_Suite, Task_EV_Conn_V20, Task_EV_Supported, Task_EV_V2G
from .v2g.supported_app_protocol import PROTO_TESTS_EV
import faulthandler
import asyncio
import signal
import os

async def add_proto_test_all(cont: ControllerEV, conn_task: Task_EV_Conn_Base):
    cont.add_task(conn_task, False)

    proto_keys = ["ALL", "V20DC", "V2V13", "V2V10", "DIN"]

    for key in proto_keys:
        supp_task = Task_EV_Supported(cont.ui, conn_task, PROTO_TESTS_EV[key])
        cont.add_task(supp_task, False)
        v2g_task = Task_EV_V2G(cont.ui, supp_task)
        cont.add_task(v2g_task, True)

async def add_proto_test_default(cont: ControllerEV, conn_task: Task_EV_Conn_Base):
    cont.add_task(conn_task, False)
    supp_task = Task_EV_Supported(cont.ui, conn_task, PROTO_TESTS_EV["ALL"])
    cont.add_task(supp_task, False)
    v2g_task = Task_EV_V2G(cont.ui, supp_task)
    cont.add_task(v2g_task, True)


async def main(args):
    faulthandler.enable()

    cont = ControllerEV("eth0", args)

    hubject_hash = bytes.fromhex("d8367e861f5807f8141fea572d676dbf58bb5f7c")

    task_slac = Task_EV_SLAC(cont.ui)
    cont.add_task(task_slac, False)

    task_sdp_ntls = Task_EV_SDP(cont.ui, task_slac, False)
    cont.add_task(task_sdp_ntls, False)

    task_sdp_ytls = Task_EV_SDP(cont.ui, task_slac, True)
    cont.add_task(task_sdp_ytls, False)

    task_con_v20 = Task_EV_Conn_V20(cont.ui, task_sdp_ytls)
    task_con_v20.cert = generate_self_signed_certificate()#load_cert_chain()
        
    
    await add_proto_test_all(cont, task_con_v20)

    task_con_V2 = Task_EV_Conn_V2(cont.ui, task_sdp_ytls)
    #task_con_V2.trusted.append(TrustedCAKey(TrustedCAKeyType.cert_sha1_hash,cert_sha1_hash= hubject_hash))
    await add_proto_test_all(cont, task_con_V2)

    task_con_old = Task_EV_Conn_TLS_Old(cont.ui, task_sdp_ytls)
    #task_con_old.trusted.append(TrustedCAKey(TrustedCAKeyType.cert_sha1_hash,cert_sha1_hash= hubject_hash))
    await add_proto_test_default(cont, task_con_old)

    task_con_badtrust = Task_EV_Conn_V2_BadTrusted(cont.ui, task_sdp_ytls)
    await add_proto_test_default(cont, task_con_badtrust)

    task_con_strong = Task_EV_Conn_V2_Suite(cont.ui, "STRONG", task_sdp_ytls)
    task_con_strong.suites = TLS_CIPHER_GROUPS["OTHER_STRONG_TLS12"]
    #task_con_strong.trusted.append(TrustedCAKey(TrustedCAKeyType.cert_sha1_hash,cert_sha1_hash= hubject_hash))
    await add_proto_test_default(cont, task_con_strong)

    task_con_weak = Task_EV_Conn_V2_Suite(cont.ui, "WEAK", task_sdp_ytls)
    task_con_weak.suites = TLS_CIPHER_GROUPS["OTHER_INSECURE_TLS12"]
    #task_con_weak.trusted.append(TrustedCAKey(TrustedCAKeyType.cert_sha1_hash,cert_sha1_hash= hubject_hash))
    await add_proto_test_all(cont, task_con_weak)

    task_con_ntls = Task_EV_Conn_NTLS(cont.ui, task_sdp_ntls)
    await add_proto_test_all(cont, task_con_ntls)


    await cont.run_forever()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        prog='EV Simulator'
    )

    parser.add_argument('outpath')
    parser.add_argument('--name')      # option that takes a value
    parser.add_argument('--box')
    parser.add_argument('--plug')
    parser.add_argument('--lat')
    parser.add_argument('--long')
    
    args = parser.parse_args()

    try:
        asyncio.run(main(args))
    except KeyboardInterrupt:
        pass
    finally:
        print("Shutting down")
