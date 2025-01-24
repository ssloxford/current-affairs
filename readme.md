# EV charger measurement system

This code is used in the paper "Current Affairs: A Security Measurement Study of CCS EV Charging Deployments".


## Setup instructions

The following section provides setup instructions on a Raspberry 4 running Raspbian.

#### Hardware

To interface with real EV chargers, multiple hardware components are needed:

- A physical CCS inlet can be purchased, or 3D printed. The device only requires connection to the CP, PP and PE pins of a CCS plug.
- A HomePlug GP modem configured to EV mode should be connected to the ethernet interface of the Pi.
- Special electronics are needed to read and generate the voltages necessary for CCS basic signalling. We used a custom PCB, the design files are located in `pcb/`. This was designed in Easyeda and ordered from JLCPCB. The code to interface with the board is located in `code/hal_v2.py`. Different hardware can be used by re-implementing this file. If using our PCB, the differential signal of the PLC modem should be connected to PLC+ and PLC-, and the GND, EV CP and EV PP sockets on the PCB should be connected to the PE, CP and PP pins of the CCS socket respectively.
- We recommend using a power bank to make the setup portable, and using a small external screen + wireless keyboard to assist debugging.

#### Packages

Most of the code is written in Python 3. Some portions are written as a C Python module. Install the necessary packages:
```sh
apt install python3 python3-dev python3-pip build-essential tcpdump git maven
pip3 install -r requirements.txt
```

#### V2G decoding

The code depends on a modified version of [V2Gdecoder](https://github.com/FlUxIuS/V2Gdecoder). For licensing reasons we can not provide the edited repo, but we provide `libs/V2Gdecoder.patch` to be applied to `6c26c817` containing the changes. The compiled `V2Gdecoder-jar-with-dependencies.jar` file should be placed in the `schemas` folder.

We require the DIN and ISO 15118 schemas, which can be obtained in the Appendices of relevant standards documents, and may be available elsewhere. For licensing reasons we can not provide these files. They should be placed in the `schemas` folder in the following structure:

```
schemas/
├── AppProto/
│   └── V2G_CI_AppProtocol.xsd
├── DIN/
│   ├── V2G_CI_MsgBody.xsd
│   ├── V2G_CI_MsgDataTypes.xsd
│   ├── V2G_CI_MsgDef.xsd
│   ├── V2G_CI_MsgHeader.xsd
│   └── xmldsig-core-schema.xsd
├── 2V10/
│   ├── V2G_CI_MsgBody.xsd
│   ├── V2G_CI_MsgDataTypes.xsd
│   ├── V2G_CI_MsgDef.xsd
│   ├── V2G_CI_MsgHeader.xsd
│   └── xmldsig-core-schema.xsd
├── 2V13/
│   ├── V2G_CI_MsgBody.xsd
│   ├── V2G_CI_MsgDataTypes.xsd
│   ├── V2G_CI_MsgDef.xsd
│   ├── V2G_CI_MsgHeader.xsd
│   └── xmldsig-core-schema.xsd
└── 20/
    ├── V2G_CI_AC.xsd
    ├── V2G_CI_ACDP.xsd
    ├── V2G_CI_CommonMessages.xsd
    ├── V2G_CI_CommonTypes.xsd
    ├── V2G_CI_DC.xsd
    ├── V2G_CI_WPT.xsd
    └── xmldsig-core-schema.xsd
```

#### Python module

Build the C module, and copy the built files:
```sh
cd open-plc-utils
make
cd ..
cp open-plc-utils/slac_python_module/slac_wrapper.so code/interface/slac_wrapper.so
```

#### System config
Edit `/boot/config.txt`:
- Enable hardware PWM controller for CP generation. Add:
`dtoverlay=pwm-2chan,pin=12,func=4,pin2=13,func2=4`

- Enable hardware SPI. Add:
`dtparam=spi=on`

- Lock CPU frequency (SPI clock is tied to CPU, needed for reliable ADC timing)
`arm_boost=0`
`core_freq=500`
`core_freq_min=500`


Set adapter connected to HPGP modem to have only Link-local IPv6 address.
(Change `Wired\ connection\ 1` if necessary)
```
nmcli connection edit Wired\ connection\ 1 
nmcli> set ipv4.method disabled 
nmcli> set ipv6.method link-local 
nmcli> set ipv6.addr-gen-mode eui64
nmcli> save
nmcli> quit
```

Give raw interface permissions to `python` (replace the command with the installed version, it can not be a symlink) and `tcpdump`, so app can be run unpriviledged.
``` sh
sudo setcap cap_net_raw,cap_net_admin=eip /usr/bin/python3.11
sudo setcap cap_net_raw,cap_net_admin=eip /usr/bin/tcpdump
```

#### Autorun

Our code can run as a `systemd` process. The template for this is located in `data_collector_service.template`. Edit this to configure the path of the project, and make systemd run the system at startup. A simple shell script is provided to de-escale from root to a user process. The steps above guarantee the necessary hardware permissions.


## Usage

Connect to the Pi over WiFi (either set the Pi to host a network, or connect to a mobile hotspot).

#### Main interface

The code launches an https server on port 8000. Navigate to this page on a device with GPS (such as a phone). The webserver uses a self-signed certificate, which must be manually accepted in most major browsers. If the page shows "click here to activate WS certificate" follow this link to accept a separate certificate for the websocket connection.

Text boxes can be used to enter some location information about the tested charger, which will be saved in the data file. The "Set position" button sends the GPS reading from the browser to the server. In our experience, some browsers only provide inaccurate and delayed position, Chrome on Android is known to work reliably.

The file upload button on the top bar opens the smartphone camera, and uploads the taken pictures with a UTC timestamp.

Raspberry Pi-s usually handle power loss without corruption, however the "Shutdown" can be used to perform a proper Linux shutdown before power is disconnected.

#### Measurements

The "Start" button launches the data collector. Enter information into the text boxes and set the GPS before clicking start.

The interface now shows live readings of the CP voltage (low voltage, high voltage, duty cycle), and the PP voltage.

The "Start All" button performs all tests automatically, and then enters manual mode. "Start Manual" skips the automatic tests.
Next to each experiment, a "Start" button can be used in manual mode, to perform the specific experiment. This is useful is there was an anomaly with one of the automatic tests, and the operator would like to repeat it. 

Experiments are shown in a tree structure to represent dependencies. It is enough to click "Start" on only the inner most layer, it will perform a clean re-plug of the device, and run all dependencies.

The custom PCB we designed supports re-plugging the device without needing to physically touch the connector. When the device is disconnected ready to be connected, the "Plug" button is enabled, and once pressed, it will simulate a plug in event. On some chargers, this may have to occur only after a payment card is presented.
The "Auto Plug" checkbox can be used to press this button after a few seconds automatically. This is suitable for most devices we tested.

If an experiment becomes stuck (such as a broken charger ignoring SLAC), the "SIGINT" button can be used to interrupt it. When experiments are complete, the "Done" button exits the data collector. The device can now be moved to the next charger for testing.


#### Data download

To download data, connect via SSH/FTP or similair. The files are located in `results/`.

