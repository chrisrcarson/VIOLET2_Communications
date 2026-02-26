import socket
import time

UDP_IP   = "127.0.0.1"   # Must match GNU Radio socket_pdu source
UDP_PORT = 27001

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

print("Sending test payloads to GNU Radio...")

counter = 0
while True:
    # 100 bytes of constant pattern
    payload = bytes([counter & 0xFF]) * 100

    sock.sendto(payload, (UDP_IP, UDP_PORT))
    print(f"Sent payload #{counter}")

    counter += 1
    time.sleep(3)

