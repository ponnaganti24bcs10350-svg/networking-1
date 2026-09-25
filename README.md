# Networking Homework 1: Early HTTP/1.1 Calculator & Binary HTTP Framing Protocol

This repository contains the complete implementation for two networking assignments built from scratch using raw Python sockets (`socket`, `struct`, `threading`), with zero external framework dependencies:

1. **Early HTTP/1.1 Persistent Calculator Server** ("Build a calculator that stays on the line")
2. **Binary HTTP Framing Protocol** (`bserve`, `bcurl`, formal 2-page specification, and annotated hex dumps)

---

## 📁 Repository Structure

```
.
├── http11_calculator/
│   ├── server.py             # Pure TCP socket HTTP/1.1 persistent calculator server
│   └── client_evaluator.py   # Automated evaluator testing all endpoints on 1 TCP socket
├── binary_http/
│   ├── protocol.py           # Fixed 8-byte framing, header encoding, unknown frame skipping
│   ├── bserve.py             # Binary HTTP server (Track 1)
│   ├── bcurl.py              # Binary HTTP client with -v annotated hex dumps (Track 2)
│   └── SPEC.md               # Formal 2-page Binary Protocol Specification document
├── www/
│   └── index.html            # Static HTML file served by bserve
├── tests/
│   ├── test_calculator.py    # Unittest suite for HTTP/1.1 persistent calculator
│   └── test_binary_http.py   # Unittest suite for Binary HTTP protocol
├── run_all.py                # Master verification runner
└── README.md
```

---

## 🚀 Quick Start

### 1. Run the Master Verification Suite
Runs all 9 unit tests, launches both servers, executes the 1-socket calculator evaluation suite, and displays live annotated hex dumps:

```bash
python3 run_all.py
```

### 2. Run the Automated Unit Tests
```bash
python3 -m unittest discover -s tests -p "test_*.py"
```

---

## 🧮 Part 1: Early HTTP/1.1 Calculator Server

### Start Server
```bash
python3 http11_calculator/server.py 8080
```

### Run Evaluator (Professor's Marking Suite)
Tests all endpoints over **1 single persistent TCP socket**:
```bash
python3 http11_calculator/client_evaluator.py localhost 8080
```

### Supported Routes & Expected Responses
| Request | Status | Response / Note |
|---|---|---|
| `GET /add?a=2&b=3` | `200 OK` | `5` |
| `GET /sub?a=10&b=4` | `200 OK` | `6` |
| `GET /mul?a=6&b=7` | `200 OK` | `42` |
| `GET /div?a=9&b=3` | `200 OK` | `3` |
| `GET /div?a=1&b=0` | `400 Bad Request` | Division by zero |
| `GET /add?a=x&b=3` | `400 Bad Request` | Invalid number format |
| `GET /pow?a=2&b=8` | `404 Not Found` | Unknown endpoint |
| `POST /add` | `405 Method Not Allowed` | Only GET allowed |
| `GET /add?a=2&b=3` (no Host) | `400 Bad Request` | HTTP/1.1 requires Host header |

**Features**:
- True TCP connection persistence (`socket still open: True`).
- HTTP pipelining support (parses consecutive back-to-back requests in a single buffer).
- Handles `Connection: close` and idle timeouts cleanly.

---

## ⚡ Part 2: Binary HTTP Framing Protocol (`bserve` & `bcurl`)

### Specification Summary
See [`binary_http/SPEC.md`](binary_http/SPEC.md) for the complete 2-page formal protocol specification.
- **Fixed 8-byte Frame Header**:
  - `Payload Length` (24 bits / 3 bytes)
  - `Frame Type` (8 bits / 1 byte): `0x01` HEADERS, `0x02` DATA, `0x03` SETTINGS, etc.
  - `Flags` (8 bits / 1 byte): `0x01` END_STREAM, `0x02` END_HEADERS
  - `Stream ID` (24 bits / 3 bytes)
- **Static Header Name Table**: 10 standard HTTP headers encoded as 1-byte tokens (`:method`, `:path`, `:status`, `:scheme`, `content-type`, `content-length`, `server`, `user-agent`, `accept`, `host`).
- **Forward Compatibility Rule**: Any receiver encountering an unknown frame type skips `Payload Length` bytes cleanly without closing the connection.

### Run Server (`bserve`)
```bash
python3 binary_http/bserve.py ./www 9000
```

### Run Client (`bcurl`) with Annotated Hex Dump
```bash
python3 binary_http/bcurl.py -v localhost:9000/index.html
```

---

## 🧪 Verification Results

```text
Ran 9 tests in 0.421s

OK
socket still open: True
1 TCP handshake, 9/9 responses passed
```
All requirements verified with 0 errors.
