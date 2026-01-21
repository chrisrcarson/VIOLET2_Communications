import socket
import os
import time
import subprocess


# Set the UDP recieve address and port
receive_host = "127.0.0.1"
receive_port = 27003

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

	print(f"EARTH PC TRANSMISSION: {AX25Packet.hex()}\n")

	# push over udp
	sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
	sock.sendto(AX25Packet, (UDP_HOST, UDP_PORT))
	sock.close()
	return AX25Packet

# receive and print response as byte string over UDP
receive_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
receive_socket.bind((receive_host, receive_port))
receive_socket.settimeout(10) # timeout set to 10 seconds

isExiting = False
while not isExiting:
    
    userInput = input("VIOLET2> ")
    
    if userInput.lower() == "quit":
        isExiting = True
        break
    
    # force flushing buffer
    receive_socket.setblocking(False)
    flush_count = 0
    try:
        while True:
            receive_socket.recvfrom(4096)
            flush_count += 1
    except (BlockingIOError, socket.error):
        if flush_count > 0:
            print(f"Flushed stale packets...")
    
    # send the command and reset timeout
    receive_socket.settimeout(10) 
    info = userInput.encode('ascii')
    AX_25Send(info)
    
    # waiting for response
    try:
        data, addr = receive_socket.recvfrom(2048)#1024)
        print(f"[Received Data]: {data.hex()}")
        command_output = data[16:] 
        print(f"Response: {command_output.decode('ascii', errors='replace')}")
        
    except socket.timeout:
        print("Connection Timeout: No data received after 10 seconds")
        
    except KeyboardInterrupt:
        isExiting = True
        break

receive_socket.close()
