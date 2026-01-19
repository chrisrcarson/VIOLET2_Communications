import socket
import os
import time
import subprocess


# Set the UDP recieve address and port
receive_host = "127.0.0.1"
receive_port = 27001

# Set the UDP server addresses and ports
UDP_HOST = "127.0.0.1" 
UDP_PORT = 27000


# 7 bytes allocated for each callsign, byte 7 for SSID in Hex
SourceCallsign = "VE9CNB"
SourceSSID = "E0" # Bit 7 set to 1 indicating destination SSID **

DestinationCallsign = "VE9VLT"
DestinationSSID = "60" # Bit 7 set to 0 indicating source SSID **

# Control byte
Control = "00"

# FCS
FCS = "0000"

# PID Byte
PID = "F0"


def AX_25Send(Info):
    # Combine into a single byte string
	AX25Packet = (
	DestinationCallsign.encode('ascii') +
	bytes.fromhex(DestinationSSID) +
	SourceCallsign.encode('ascii') +
	bytes.fromhex(SourceSSID) +
	bytes.fromhex(Control) +
	bytes.fromhex(PID) +
	Info 
	)

	print("AX.25 Packet Transmitted From SPC:")
	print(AX25Packet.hex())
	print()

	# push over udp
	sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
	sock.sendto(AX25Packet, (UDP_HOST, UDP_PORT))
	sock.close()
	return AX25Packet

command = "echo hello"
info = command.encode('ascii')
AX_25Send(info)

while 1:
	# Receive and print response as byte string over UDP
	receive_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
	receive_socket.bind((receive_host, receive_port))
	data, addr = receive_socket.recvfrom(1024)
	command_output = data[16:]
	
	print(command_output)