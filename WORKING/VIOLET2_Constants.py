# AX.25 Layer 1
AX25_HEADER_LEN     = 16
AX25_CONTROL        = "00"
AX25_FCS            = "0000"
AX25_PID            = "F0"

SOURCE_CALLSIGN     = "VE9CNB"
SOURCE_SSID         = "E0"   # Bit 7 = 1, destination SSID
DEST_CALLSIGN       = "VE9VLT"
DEST_SSID           = "60"   # Bit 7 = 0, source SSID

# VIOLET2 Layer 2
VIOLET2_HEADER_LEN  = 8
VIOLET2_MIN_APP_DATA = 92
VIOLET2_MAX_APP_DATA = 248

PAD_BYTE_A          = 0xAA
PAD_BYTE_B          = 0x55

# Message Types
MSG_CMD_SINGLE      = 0x01
MSG_CMD_MULTI_START = 0x02
MSG_CMD_MULTI_CONT  = 0x03
MSG_CMD_MULTI_END   = 0x04
RESP_SINGLE         = 0x05
RESP_MULTI_START    = 0x06
RESP_MULTI_CONT     = 0x07
RESP_MULTI_END      = 0x08
MSG_ACK             = 0xA0
MSG_NACK            = 0xA1
MSG_PING            = 0xB0
MSG_PONG            = 0xB1
