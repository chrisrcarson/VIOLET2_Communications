#
# Troy T. Lavigne
# Updated May 13, 2024
# VF907
# Prepend commands with 100x "A5" to provide Satellite time to lock onto signal
#
import os
from datetime import datetime,timezone
import socket
import subprocess
import json
import requests
import time
from time import sleep

#Lime setup duration
LimeSetupTime = 30

#Delay between Tx. packets sent to violet
#TransmitDelay = 8

# Callsigns (ASCII)
# 7 bytes allocated for each callsign, byte 7 for SSID in hex

#DestinationCallsign = "VE9VLT"
#DCS = format(ord(DestinationCallsign), "x")
#DCS = format(ord('VE9VLT'), "x")
#DCS = binascii.hexlify(DestinationCallsign.encode()).decode()
#print("DCS=",DCS)

PrependBytes = ""

# Create string of prepend bytes
for i in range (100):
     PrependBytes += str("A5") # Prepending bytes to provide the TRXVU time to lock on

#print("prepend =",PrependBytes)

DestinationCallsign = "AC8A72AC98A8"
DestinationSSID = "E2" # Bit 7 set to 1 indicating destination SSID = 1

#SourceCallsign = "VE9CNB"
SourceCallsign = "AC8A72869C84"
SourceSSID = "63" # Bit 7 set to 0 indicating source SSID = 1

# Flag Byte for start and end of packet (ASCII)
Flag = "~"

# Control byte
Control = "03"

# FCS Bytes
FCS = "0000"

# PID Byte
PID = "F0"

# GNU Radio UDP settings
UDP_HOST = "127.0.0.1"
UDP_PORT = 27001

receive_host = "127.0.0.1"
receive_port = 27000

def AX_25Gen(arg):

        data = "FFF0000FFFFFFF0000FFFF0000FFFF00FFFFFF0000FFFFFF0000FFFFF0000FFFFF000000FFFFFF0000FFFFF0000FFFFFFF0000FF0000FFFFFF0000FFFFF0000FFFFFFF0000FFFF0000FFFF00FFFFFF0000FFFFFF0000FFFFF0000FFFFF000000FFFFFF0000FFFFF0000FFFFFFF0000FFFF0000FFFFFFFF0000FFFFFFF0000FFFFFFF0000FFFFFFFF0000FFFFFFFF0000FFFFFFFF0000FFFFFFFF0000FFFFFFFF0000FFFFFFFF0000FFFFFFFF0000FFFFFFFF0000FFFFFFFF0000FFFFFFFF0000FFFFFFFF0000FFFF" # ascii command "TX."

#
# May 3, 2024 - added timeout to prevent script from failing if the violet_packet_database is offline
#
 
        Info = data
        print(Info)

    # Check if AX.25 dataframe [ID,IV,Ciphertext,Auth tag]  is not equal to 144 bytes 
    # Disabled

        print("Payload=",len(Info)/2,"bytes")
        # Combine into a single byte string
 
        AX25Packet = (
                bytes.fromhex(DestinationCallsign) +
                bytes.fromhex(DestinationSSID) +
                bytes.fromhex(SourceCallsign) +
                bytes.fromhex(SourceSSID) +
                bytes.fromhex(Control) +
                bytes.fromhex(PID) +
                bytes.fromhex(Info)
        )

        print("AX.25 Packet Transmitted From GPC:")
        print(AX25Packet.hex())


        def current_milli_time():
            return round(time.time() * 1000)
        
        # Save the transmitted command to a file
        DateAndTime = datetime.now()
        FormattedDateAndTime = DateAndTime.strftime("%Y-%m-%d_%H-%M-%S-%f")
         # Define the directory where you want to save the file
        directory = "Packets/"
        # Combine the directory and filename to create the full file path       
        filename = f"Transmitted_Packet_{FormattedDateAndTime}.txt"
        full_path = os.path.join(directory, filename)
        # Save the AX.25 Packet to the file
        #with open(full_path, 'wb') as file:
        with open(full_path, 'w') as file:
            file.write(AX25Packet.hex())

        return AX25Packet
#

# Code starts running here
#
# Arg to AX-25Gen:
#	1 = Add A5 byte prepend
#	0 = Do not add A5 byte prepend

Packet1 = AX_25Gen(0)

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
#print("Packet#",i)

#sock.sendto(Packet1, (UDP_HOST, UDP_PORT))

#sleep(0.01)

for i in range (24):
	print("Packet#",i)
	sock.sendto(Packet1, (UDP_HOST, UDP_PORT))
	sleep (1.5)
count = 0	


#while (count<7):
#	receive_socket = socket.socket(socket.AF_INET,socket.SOCK_DGRAM)
#	receive_socket.bind((receive_host,receive_port))
#	data, addr = receive_socket.recvfrom(1024)
#	print("Received message from SPC:", count, data.hex())
#	print("\n")
#	count+=1
		
sock.close()



