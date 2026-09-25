#!/usr/bin/env python3
"""
Binary HTTP Protocol (bHTTP v1.0)
Binary Framing, Header Encoding, Frame Packing/Unpacking, Unknown Frame Handling,
and Visual Annotated Hex Dump Generator.
"""

import struct

# Frame Types
FRAME_HEADERS = 0x01
FRAME_DATA = 0x02
FRAME_SETTINGS = 0x03
FRAME_RST_STREAM = 0x04
FRAME_GOAWAY = 0x05
FRAME_UNKNOWN_TEST = 0x99  # Used for testing forward-compatibility

# Flags
FLAG_NONE = 0x00
FLAG_END_STREAM = 0x01
FLAG_END_HEADERS = 0x02

# Static Header Name Index (10 standard names for HPACK-like compression)
STATIC_HEADER_TABLE = {
    0x01: ":method",
    0x02: ":path",
    0x03: ":status",
    0x04: ":scheme",
    0x05: "content-type",
    0x06: "content-length",
    0x07: "server",
    0x08: "user-agent",
    0x09: "accept",
    0x0A: "host",
}
REV_STATIC_HEADER_TABLE = {v: k for k, v in STATIC_HEADER_TABLE.items()}

# Header Format:
# Byte 0: 0x80 | static_index (if static index match) OR 0x00 (if literal name string follows)
# If 0x00: 2 bytes name_len + name_bytes
# Followed by: 2 bytes value_len + value_bytes

HEADER_NAME_INDEXED_MASK = 0x80

HEADER_FRAME_HEADER_SIZE = 8  # 3 bytes Length, 1 byte Type, 1 byte Flags, 3 bytes Stream ID


class BinaryProtocolError(Exception):
    pass


class MalformedFrameError(BinaryProtocolError):
    pass


def pack_24bit_int(val):
    if not (0 <= val <= 0xFFFFFF):
        raise ValueError(f"Value {val} out of 24-bit range")
    return struct.pack(">I", val)[1:]


def unpack_24bit_int(data):
    if len(data) != 3:
        raise ValueError("Requires 3 bytes for 24-bit int")
    return struct.unpack(">I", b"\x00" + data)[0]


def pack_frame(frame_type, flags, stream_id, payload=b""):
    """
    Packs a frame with an 8-byte fixed header:
    - 3 bytes: Payload Length (24 bits)
    - 1 byte:  Frame Type (8 bits)
    - 1 byte:  Flags (8 bits)
    - 3 bytes: Stream ID (24 bits)
    Followed by payload bytes.
    """
    payload_len = len(payload)
    if payload_len > 0xFFFFFF:
        raise ValueError("Payload size exceeds 16MB limit")
        
    hdr = pack_24bit_int(payload_len) + bytes([frame_type, flags]) + pack_24bit_int(stream_id)
    return hdr + payload


def unpack_frame_header(header_bytes):
    """Parses 8-byte frame header into (payload_len, frame_type, flags, stream_id)"""
    if len(header_bytes) < HEADER_FRAME_HEADER_SIZE:
        raise MalformedFrameError("Header incomplete (less than 8 bytes)")
    
    payload_len = unpack_24bit_int(header_bytes[0:3])
    frame_type = header_bytes[3]
    flags = header_bytes[4]
    stream_id = unpack_24bit_int(header_bytes[5:8])
    return payload_len, frame_type, flags, stream_id


def encode_headers(headers_dict):
    """
    Encodes key-value dictionary into binary header block.
    Uses static index byte when header name matches static table.
    """
    buf = bytearray()
    for name, value in headers_dict.items():
        lower_name = name.lower()
        val_bytes = str(value).encode("utf-8")
        
        if lower_name in REV_STATIC_HEADER_TABLE:
            static_idx = REV_STATIC_HEADER_TABLE[lower_name]
            buf.append(HEADER_NAME_INDEXED_MASK | static_idx)
        else:
            buf.append(0x00)
            name_bytes = lower_name.encode("utf-8")
            buf.extend(struct.pack(">H", len(name_bytes)))
            buf.extend(name_bytes)
            
        buf.extend(struct.pack(">H", len(val_bytes)))
        buf.extend(val_bytes)
        
    return bytes(buf)


def decode_headers(header_block):
    """Decodes binary header block back into a dictionary"""
    headers = {}
    idx = 0
    total = len(header_block)
    
    while idx < total:
        b0 = header_block[idx]
        idx += 1
        
        if b0 & HEADER_NAME_INDEXED_MASK:
            static_idx = b0 & ~HEADER_NAME_INDEXED_MASK
            name = STATIC_HEADER_TABLE.get(static_idx, f"unknown-{static_idx}")
        else:
            if idx + 2 > total:
                raise MalformedFrameError("Truncated header name length")
            name_len = struct.unpack(">H", header_block[idx:idx+2])[0]
            idx += 2
            if idx + name_len > total:
                raise MalformedFrameError("Truncated header name value")
            name = header_block[idx:idx+name_len].decode("utf-8", errors="replace")
            idx += name_len
            
        if idx + 2 > total:
            raise MalformedFrameError("Truncated header value length")
        val_len = struct.unpack(">H", header_block[idx:idx+2])[0]
        idx += 2
        if idx + val_len > total:
            raise MalformedFrameError("Truncated header value payload")
        val = header_block[idx:idx+val_len].decode("utf-8", errors="replace")
        idx += val_len
        
        headers[name] = val
        
    return headers


def read_next_frame(sock):
    """
    Reads next valid or unknown frame from socket stream.
    Automatically SKIPS unknown frame types cleanly as required by spec!
    Returns (frame_type, flags, stream_id, payload_bytes).
    """
    while True:
        hdr_bytes = bytearray()
        while len(hdr_bytes) < HEADER_FRAME_HEADER_SIZE:
            chunk = sock.recv(HEADER_FRAME_HEADER_SIZE - len(hdr_bytes))
            if not chunk:
                return None  # Connection closed cleanly
            hdr_bytes.extend(chunk)
            
        payload_len, frame_type, flags, stream_id = unpack_frame_header(hdr_bytes)
        
        payload_bytes = bytearray()
        while len(payload_bytes) < payload_len:
            chunk = sock.recv(payload_len - len(payload_bytes))
            if not chunk:
                raise MalformedFrameError("Unexpected EOF while reading frame payload")
            payload_bytes.extend(chunk)
            
        payload = bytes(payload_bytes)
        
        # Check if known frame type
        known_types = {FRAME_HEADERS, FRAME_DATA, FRAME_SETTINGS, FRAME_RST_STREAM, FRAME_GOAWAY}
        if frame_type not in known_types:
            # Cleanly skip unknown frame type for forward compatibility (Version 2 room)
            continue
            
        return frame_type, flags, stream_id, payload


def annotate_hex_dump(frame_bytes):
    """
    Generates a human-readable annotated hex dump breakdown of a binary frame.
    """
    if len(frame_bytes) < HEADER_FRAME_HEADER_SIZE:
        return "[HexDump] Invalid frame size < 8 bytes"
        
    payload_len, frame_type, flags, stream_id = unpack_frame_header(frame_bytes[:8])
    
    type_names = {
        FRAME_HEADERS: "HEADERS (0x01)",
        FRAME_DATA: "DATA (0x02)",
        FRAME_SETTINGS: "SETTINGS (0x03)",
        FRAME_RST_STREAM: "RST_STREAM (0x04)",
        FRAME_GOAWAY: "GOAWAY (0x05)",
        FRAME_UNKNOWN_TEST: "UNKNOWN_V2 (0x99)",
    }
    type_str = type_names.get(frame_type, f"UNKNOWN (0x{frame_type:02X})")
    
    flag_parts = []
    if flags & FLAG_END_STREAM:
        flag_parts.append("END_STREAM")
    if flags & FLAG_END_HEADERS:
        flag_parts.append("END_HEADERS")
    flag_str = "|".join(flag_parts) if flag_parts else "NONE (0x00)"
    
    lines = []
    lines.append("┌" + "─" * 72 + "┐")
    lines.append(f"│ FRAME HEADER (8 bytes): Stream ID = {stream_id:<6} Payload Length = {payload_len:<6} Bytes │")
    lines.append(f"│ Type: {type_str:<22} Flags: {flag_str:<28} │")
    lines.append("├" + "─" * 72 + "┤")
    lines.append("│ OFFSET | HEX BYTES                | FIELD BREAKDOWN / ANNOTATION       │")
    lines.append("├───────┼──────────────────────────┼────────────────────────────────────┤")
    
    # Header byte annotations
    l_bytes = " ".join(f"{b:02X}" for b in frame_bytes[0:3])
    lines.append(f"│ 0000  │ {l_bytes:<24} │ Payload Length: {payload_len} bytes         │")
    lines.append(f"│ 0003  │ {frame_bytes[3]:02X}                       │ Frame Type: {type_str:<20} │")
    lines.append(f"│ 0004  │ {frame_bytes[4]:02X}                       │ Flags: {flag_str:<25} │")
    s_bytes = " ".join(f"{b:02X}" for b in frame_bytes[5:8])
    lines.append(f"│ 0005  │ {s_bytes:<24} │ Stream ID: {stream_id}                        │")
    
    payload = frame_bytes[8:]
    if payload:
        lines.append("├───────┼──────────────────────────┼────────────────────────────────────┤")
        lines.append(f"│ PAYLOAD ({len(payload)} bytes):                                                       │")
        
        if frame_type == FRAME_HEADERS:
            try:
                headers = decode_headers(payload)
                for k, v in headers.items():
                    lines.append(f"│       │ Header: {k} = {v:<43} │")
            except Exception as e:
                lines.append(f"│       │ Raw Header Payload Bytes ({len(payload)}B)                           │")
        elif frame_type == FRAME_DATA:
            sample = payload[:32].decode("utf-8", errors="replace").replace("\n", "\\n")
            lines.append(f"│       │ Data Content: \"{sample}\"")
        else:
            lines.append(f"│       │ Payload Bytes: {payload[:24].hex()}...")
            
    lines.append("└" + "─" * 72 + "┘")
    return "\n".join(lines)
