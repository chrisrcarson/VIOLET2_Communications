#!/usr/bin/bash

/usr/bin/gpioset -t 0 -c 2 45=0
/usr/bin/ip link set can0 type can bitrate 500000
/usr/sbin/ifconfig can0 up
