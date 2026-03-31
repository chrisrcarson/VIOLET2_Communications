#!/usr/bin/bash


/usr/bin/gpioset -t 0 -c 2 62=1 # Power on LimeSDR Mini
/usr/bin/gpioset -t 0 -c 3 5=1 # Power on RF DC Module
/usr/bin/gpioset -t 0 -c 2 61=0 # Set RF Switch to Rx Mode
/usr/bin/gpioset -t 0 -c 3 4=1 # Power on RF Switch
/usr/bin/gpioset -t 0 -c 2 60=1 # Enable RF DC Module
/usr/bin/gpioset -t 0 -c 2 45=0 # Enable CAN Transceiver
/usr/bin/ip link set can0 type can bitrate 500000
/usr/sbin/ifconfig can0 up
