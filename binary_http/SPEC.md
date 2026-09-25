# Protocol Specification: Binary HTTP (bHTTP/1.0)

**Version:** 1.0  
**Authors:** Course Assignment Submissions (Networking HW 1)  
**Status:** Protocol Specification  

---

## 1. Overview & Objectives

**bHTTP/1.0** is a binary application-layer protocol designed to replace HTTP/1.1 ASCII header strings with compact, fixed-size binary frames over persistent TCP connections.

### Key Features:
- **Fixed 8-Byte Frame Header**: Eliminates string scanning (`\r\n\r\n`) and ambiguity in message boundaries.
- **Single Persistent TCP Socket**: Multiple requests and responses flow sequentially or via stream identifiers over a single TCP connection (`socket still open: True`).
- **Static Header Table (Indexed Names)**: 10 common header names are assigned 1-byte static index tokens, reducing header overhead.
- **Forward Compatibility Rule**: Any receiver encountering an unknown Frame Type **MUST** read `Payload Length` bytes and cleanly skip the payload without raising a protocol error or closing the connection. This guarantees room for version 2 upgrades.

---

## 2. Frame Structure (Wire Format)

Every bHTTP frame consists of a mandatory **8-byte Fixed Header** followed by a variable-length **Payload** (0 to 16,777,215 bytes).

```
 0                   1                   2                   3
 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1
+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
|                       Payload Length (24)                     |
+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
|   Type (8)    |   Flags (8)   |        Stream ID (24)         |
+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
|                     Payload Bytes (...)                       |
+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
```

### Field Definitions:

1. **Payload Length (24 bits / 3 bytes)**:
   Unsigned integer (Big-Endian) indicating byte length of payload. Maximum payload size = $2^{24} - 1 = 16,777,215$ bytes (16MB).
2. **Frame Type (8 bits / 1 byte)**:
   - `0x01` (`HEADERS`): Contains encoded key-value header block.
   - `0x02` (`DATA`): Contains raw message body bytes (file payload or response body).
   - `0x03` (`SETTINGS`): Stream configuration.
   - `0x04` (`RST_STREAM`): Aborts a stream.
   - `0x05` (`GOAWAY`): Initiates connection shutdown.
   - `0x99+` (`UNKNOWN_V2`): Reserved for future versions.
3. **Flags (8 bits / 1 byte)**:
   - `0x01` (`END_STREAM`): Indicates this frame is the final frame sent for the current stream.
   - `0x02` (`END_HEADERS`): Indicates header block completion.
4. **Stream ID (24 bits / 3 bytes)**:
   Unsigned integer (Big-Endian) identifying the request/response stream. Client requests use odd IDs (1, 3, 5, ...); server-initiated frames use even IDs.

---

## 3. Header Block Encoding (Static Table)

Header blocks consist of packed key-value entries:

```
[Header Byte 0]
  - Bit 7 = 1: Static Indexed Header Name (Bits 0-6 = Static Index 1..10)
  - Bit 7 = 0: Literal Header Name (Followed by 2-byte Length + Name UTF-8 Bytes)
[2-Byte Value Length] + [Value UTF-8 Bytes]
```

### Static Header Index Table:

| Index (`0x80 | ID`) | Header Name |
|---|---|
| `0x81` | `:method` |
| `0x82` | `:path` |
| `0x83` | `:status` |
| `0x84` | `:scheme` |
| `0x85` | `content-type` |
| `0x86` | `content-length` |
| `0x87` | `server` |
| `0x88` | `user-agent` |
| `0x89` | `accept` |
| `0x8A` | `host` |

---

## 4. Annotated Hex Dump Example

The following annotated hex dump demonstrates a complete request frame produced by `bcurl -v localhost:9000/index.html`:

```
┌────────────────────────────────────────────────────────────────────────┐
│ FRAME HEADER (8 bytes): Stream ID = 1      Payload Length = 44     Bytes │
│ Type: HEADERS (0x01)         Flags: END_STREAM|END_HEADERS             │
├────────────────────────────────────────────────────────────────────────┤
│ OFFSET | HEX BYTES                | FIELD BREAKDOWN / ANNOTATION       │
├───────┼──────────────────────────┼────────────────────────────────────┤
│ 0000  │ 00 00 2C                 │ Payload Length: 44 bytes           │
│ 0003  │ 01                       │ Frame Type: HEADERS (0x01)         │
│ 0004  │ 03                       │ Flags: END_STREAM|END_HEADERS      │
│ 0005  │ 00 00 01                 │ Stream ID: 1                       │
├───────┼──────────────────────────┼────────────────────────────────────┤
│ PAYLOAD (44 bytes):                                                    │
│       │ Header: :method = GET                                          │
│       │ Header: :path = /index.html                                    │
│       │ Header: :scheme = http                                         │
│       │ Header: :host = localhost:9000                                 │
│       │ Header: user-agent = bcurl/1.0                                 │
└────────────────────────────────────────────────────────────────────────┘
```

---

## 5. Forward Compatibility Rule

> **Rule:** If a receiver encounters a Frame Type byte that is not recognized by its specification version, it **MUST NOT** terminate the connection. It MUST parse `Payload Length` from bytes 0–2, read and discard `Payload Length` bytes from the stream, and resume parsing subsequent frames on the same socket.

---

## 6. Program Usage Reference

### Server (`bserve`)
```bash
python3 binary_http/bserve.py <root_directory> <port>
# Example:
python3 binary_http/bserve.py ./www 9000
```

### Client (`bcurl`)
```bash
python3 binary_http/bcurl.py [-v] <host:port/path>
# Example:
python3 binary_http/bcurl.py -v localhost:9000/index.html
```
