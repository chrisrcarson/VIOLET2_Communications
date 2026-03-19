#!/usr/bin/bash

/usr/sbin/ifconfig can0 down
/usr/bin/ip link set can0 down
/usr/bin/gpioset -t 0 -c 2 45=1
