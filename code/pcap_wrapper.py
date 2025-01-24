import subprocess
import signal

from contextlib import contextmanager

from .utils import settings

@contextmanager
def pcap_context(interface: str, output: str):
    if settings.SKIP_PCAP:
        try:
            yield None
        finally:
             pass

    else:
        print(output)
        # Code to acquire resource:
        pcap_process = subprocess.Popen([
            "tcpdump",
            "-i", interface,
            "-s", "65535",
            "-w", output
        ])
        try:
            yield pcap_process
        finally:
            # Code to release resource:
            if pcap_process is not None:
                print("Pcap exit")
                pcap_process.send_signal(signal.SIGINT)
                try:
                    pcap_process.wait(1)
                except subprocess.TimeoutExpired:
                    print("Pcap kill")
                    pcap_process.kill()