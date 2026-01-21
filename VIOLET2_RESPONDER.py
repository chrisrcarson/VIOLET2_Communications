import socket
from time import sleep
import subprocess


# Set the UDP recieve address and port
receive_host = "127.0.0.1"
receive_port = 27000

# Set the UDP server addresses and ports
UDP_HOST = "127.0.0.1" 
UDP_PORT = 27002


# 7 bytes allocated for each callsign, byte 7 for SSID in Hex
SourceCallsign = "VE9VLT"
SourceSSID = "E0" # Bit 7 set to 1 indicating destination SSID **

DestinationCallsign = "VE9CNB"
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

	sleep(2)

	# push over udp
	sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
	sock.sendto(AX25Packet, (UDP_HOST, UDP_PORT))
	sock.close()

	print("Pushed over UDP, returning to main function")
	return AX25Packet

while 1:
	# Receive and print response as byte string over UDP
	receive_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
	receive_socket.bind((receive_host, receive_port))
	data, addr = receive_socket.recvfrom(1024)
	command = data[16:]

	print("Command:")
	print(command)
	print()

	result = subprocess.run(command, shell=True, capture_output=True, text=True)
	result.wait()

	print("Command output:")
	print(result.stdout)
	print()
	info = result.stdout.encode('ascii')

	AX_25Send(info)

	info = ""