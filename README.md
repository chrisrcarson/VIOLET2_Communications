# VIOLET2 Communications

PocketBeagle 2 Setup and Dependencies:
- Radio Conda
- Space PC hier blocks
- BeagleBoard-DeviceTrees https://github.com/beagleboard/BeagleBoard-DeviceTrees
- CAN-Utils https://github.com/linux-can/can-utils
- Implement ArduPilot Overlays for CAN interface https://github.com/juvinski/ardupilot_wiki/blob/pocket2/common/source/docs/common-pocketbeagle-2.rst
- Enabled service to setup CAN that runs:

``
sudo ip link set can0 type can bitrate 500000
sudo ifconfig can0 up
``

- CAN Receive:

``
candump -cae can0,0:0,#FFFFFFFF
``

- CAN Send:

``
cansend can0 123#DEADBEEF
``

- LimeSDR Mini Tx sweep test:

``
LimeUtil --cal --start 145915000 --stop 145915000
``
