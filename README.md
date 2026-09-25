# EARLY HTTP/1.1: Build a Calculator That Stays on the Line

A pure Python TCP socket server implementing HTTP/1.1 persistent connections from scratch without any web framework or `http.server` library.

---

## 📌 Assignment Overview

### The Task
Build an HTTP/1.1 calculator server using raw TCP sockets:
```text
GET /add?a=2&b=3   -> 200 5
GET /sub?a=10&b=4  -> 200 6
GET /mul?a=6&b=7   -> 200 42
GET /div?a=9&b=3   -> 200 3

GET /div?a=1&b=0   -> 400
GET /add?a=x&b=3   -> 400
GET /pow?a=2&b=8   -> 404
POST /add          -> 405
GET /add (no Host) -> 400
```

### The Hard Part: Keeping the Connection Open
In HTTP/1.0, connections were closed at EOF for every request. In HTTP/1.1, the connection stays open by default:
- Correctly delimits request boundaries by reading headers up to `\r\n\r\n`.
- Honors `Content-Length` so byte $n+1$ belongs to the next request.
- Handles back-to-back requests in the same TCP buffer (**HTTP Pipelining**).
- Honors `Connection: close` when requested by the client.
- Defends against idle socket resource leaks via configurable timeout.

---

## 📁 Repository Structure

```
.
├── server.py        # HTTP/1.1 persistent socket calculator server
├── client.py        # Professor's evaluation test runner
├── test_server.py   # Automated unit test suite
├── .gitignore       # Git ignore rules
└── README.md        # Assignment documentation
```

---

## 🚀 How to Run

### 1. Start the Server
```bash
python3 server.py 8080
```

### 2. Run the Evaluation Script (Professor's Marking Suite)
Tests all 9 required cases over **1 single persistent TCP socket**:
```bash
python3 client.py localhost 8080
```

### 3. Run Automated Unit Tests
```bash
python3 -m unittest -v test_server.py
```

---

## 🧪 Evaluation Output

```text
============================================================
  EARLY HTTP/1.1 CALCULATOR EVALUATION SUITE
============================================================
[1/9] GET /add?a=2&b=3 HTTP/1.1                  -> 200 '5' ✅ PASS
[2/9] GET /sub?a=10&b=4 HTTP/1.1                 -> 200 '6' ✅ PASS
[3/9] GET /mul?a=6&b=7 HTTP/1.1                  -> 200 '42' ✅ PASS
[4/9] GET /div?a=9&b=3 HTTP/1.1                  -> 200 '3' ✅ PASS
[5/9] GET /div?a=1&b=0 HTTP/1.1                  -> 400 'Division by zero' ✅ PASS
[6/9] GET /add?a=x&b=3 HTTP/1.1                  -> 400 'Invalid numeric value for parameter 'a' or 'b'' ✅ PASS
[7/9] GET /pow?a=2&b=8 HTTP/1.1                  -> 404 'Unknown endpoint: /pow' ✅ PASS
[8/9] POST /add HTTP/1.1                         -> 405 'Only GET method is supported' ✅ PASS
[9/9] GET /add?a=2&b=3 HTTP/1.1                  -> 400 'Missing Host header' ✅ PASS
------------------------------------------------------------
socket still open: True
1 TCP handshake, 9/9 responses passed
============================================================
```
