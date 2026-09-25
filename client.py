#!/usr/bin/env python3
"""
HTTP/1.1 Calculator Evaluation Client
Connects once via raw TCP socket and sends all test requests over the SAME socket,
verifying that the socket stays open and all responses match expected status and body.
"""

import socket
import sys
import time

def parse_http_response(raw_bytes):
    """Parses raw HTTP response bytes into (status_code, headers_dict, body_str, remaining_bytes)"""
    header_end = raw_bytes.find(b"\r\n\r\n")
    if header_end == -1:
        return None, {}, "", raw_bytes
    
    header_bytes = raw_bytes[:header_end]
    body_bytes = raw_bytes[header_end + 4:]
    
    header_str = header_bytes.decode("iso-8859-1")
    lines = header_str.split("\r\n")
    status_line = lines[0]
    parts = status_line.split(" ")
    status_code = int(parts[1]) if len(parts) > 1 else 0
    
    headers = {}
    for line in lines[1:]:
        if ":" in line:
            k, v = line.split(":", 1)
            headers[k.strip().lower()] = v.strip()
            
    content_len = int(headers.get("content-length", len(body_bytes)))
    actual_body = body_bytes[:content_len].decode("utf-8", errors="replace")
    
    remaining_bytes = body_bytes[content_len:]
    return status_code, headers, actual_body, remaining_bytes


def run_evaluation(host="localhost", port=8080):
    print("=" * 60)
    print("  EARLY HTTP/1.1 CALCULATOR EVALUATION SUITE")
    print("=" * 60)
    
    s = socket.create_connection((host, port))
    s.settimeout(2.0)
    
    test_cases = [
        ("GET /add?a=2&b=3 HTTP/1.1\r\nHost: localhost:8080\r\n\r\n", 200, "5"),
        ("GET /sub?a=10&b=4 HTTP/1.1\r\nHost: localhost:8080\r\n\r\n", 200, "6"),
        ("GET /mul?a=6&b=7 HTTP/1.1\r\nHost: localhost:8080\r\n\r\n", 200, "42"),
        ("GET /div?a=9&b=3 HTTP/1.1\r\nHost: localhost:8080\r\n\r\n", 200, "3"),
        ("GET /div?a=1&b=0 HTTP/1.1\r\nHost: localhost:8080\r\n\r\n", 400, None),
        ("GET /add?a=x&b=3 HTTP/1.1\r\nHost: localhost:8080\r\n\r\n", 400, None),
        ("GET /pow?a=2&b=8 HTTP/1.1\r\nHost: localhost:8080\r\n\r\n", 404, None),
        ("POST /add HTTP/1.1\r\nHost: localhost:8080\r\nContent-Length: 0\r\n\r\n", 405, None),
        ("GET /add?a=2&b=3 HTTP/1.1\r\n\r\n", 400, None), # No Host header
    ]
    
    passed_count = 0
    buffer = bytearray()
    
    for idx, (req_str, expected_status, expected_body) in enumerate(test_cases, 1):
        s.sendall(req_str.encode("utf-8"))
        
        # Read until full response headers + body
        while True:
            parsed_status, headers, body, leftover = parse_http_response(buffer)
            if parsed_status is not None:
                content_len = int(headers.get("content-length", 0))
                header_len = buffer.find(b"\r\n\r\n") + 4
                if len(buffer) >= header_len + content_len:
                    # Full response is in buffer
                    break
            
            chunk = s.recv(4096)
            if not chunk:
                break
            buffer.extend(chunk)
        
        status_code, headers, body, leftover = parse_http_response(buffer)
        buffer = bytearray(leftover)
        
        status_ok = (status_code == expected_status)
        body_ok = True
        if expected_body is not None:
            body_ok = (body.strip() == expected_body.strip())
            
        if status_ok and body_ok:
            passed_count += 1
            mark = "✅ PASS"
        else:
            mark = "❌ FAIL"
            
        summary_req = req_str.split('\r\n')[0]
        print(f"[{idx}/9] {summary_req:<42} -> {status_code} '{body.strip()}' {mark}")
    
    # Verify socket is STILL alive and open!
    socket_still_open = False
    try:
        # Send a final ping request
        s.sendall(b"GET /add?a=1&b=1 HTTP/1.1\r\nHost: localhost:8080\r\n\r\n")
        reply = s.recv(1024)
        if reply:
            socket_still_open = True
    except Exception:
        socket_still_open = False
    finally:
        s.close()
        
    print("-" * 60)
    print(f"socket still open: {socket_still_open}")
    print(f"1 TCP handshake, {passed_count}/{len(test_cases)} responses passed")
    print("=" * 60)
    return socket_still_open and (passed_count == len(test_cases))


if __name__ == "__main__":
    host = sys.argv[1] if len(sys.argv) > 1 else "localhost"
    port = int(sys.argv[2]) if len(sys.argv) > 2 else 8080
    success = run_evaluation(host, port)
    sys.exit(0 if success else 1)
