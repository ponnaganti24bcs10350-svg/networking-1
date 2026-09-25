#!/usr/bin/env python3
"""
HTTP/1.1 Persistent Calculator Server
Pure socket implementation without any third-party framework or http.server library.
Supports persistent TCP connections, HTTP/1.1 header validation, query parameter parsing,
error handling (400, 404, 405), pipelining, and Connection: close.
"""

import sys
import socket
import urllib.parse
import threading
import time
from datetime import datetime, timezone

HOST = "127.0.0.1"
DEFAULT_PORT = 8080
IDLE_TIMEOUT = 10.0  # seconds before closing idle socket


def format_http_date():
    return datetime.now(timezone.utc).strftime("%a, %d %b %Y %H:%M:%S GMT")


def parse_query_params(url_path):
    parsed = urllib.parse.urlparse(url_path)
    path = parsed.path
    params = urllib.parse.parse_qs(parsed.query)
    return path, params


def format_number(val):
    """Format float or int cleanly (e.g. 3.0 -> '3', 3.14 -> '3.14')"""
    if val.is_integer():
        return str(int(val))
    return str(val)


def build_response(status_code, status_text, body="", headers=None, keep_alive=True):
    if headers is None:
        headers = {}
    
    body_bytes = body.encode("utf-8") if isinstance(body, str) else body
    
    default_headers = {
        "Content-Type": "text/plain; charset=utf-8",
        "Content-Length": str(len(body_bytes)),
        "Connection": "keep-alive" if keep_alive else "close",
        "Date": format_http_date(),
        "Server": "Early-HTTP1.1-CalcServer/1.0",
    }
    
    for k, v in headers.items():
        default_headers[k] = v
        
    lines = [f"HTTP/1.1 {status_code} {status_text}"]
    for k, v in default_headers.items():
        lines.append(f"{k}: {v}")
    
    header_raw = "\r\n".join(lines) + "\r\n\r\n"
    return header_raw.encode("iso-8859-1") + body_bytes


def handle_request(raw_request_line, headers):
    parts = raw_request_line.split(" ")
    if len(parts) < 3:
        return 400, "Bad Request", "Malformed request line\n"
    
    method, full_path, http_version = parts[0], parts[1], parts[2]
    
    # HTTP/1.1 requires Host header
    if "host" not in headers:
        return 400, "Bad Request", "Missing Host header\n"
    
    # Method check
    if method != "GET":
        return 405, "Method Not Allowed", "Only GET method is supported\n", {"Allow": "GET"}
    
    path, params = parse_query_params(full_path)
    
    # Allowed calculator routes
    valid_routes = {"/add", "/sub", "/mul", "/div"}
    if path not in valid_routes:
        return 404, "Not Found", f"Unknown endpoint: {path}\n"
    
    # Validate 'a' and 'b' parameters
    if "a" not in params or "b" not in params:
        return 400, "Bad Request", "Missing required query parameters 'a' and 'b'\n"
    
    try:
        a_val = float(params["a"][0])
        b_val = float(params["b"][0])
    except (ValueError, IndexError):
        return 400, "Bad Request", "Invalid numeric value for parameter 'a' or 'b'\n"
    
    # Calculate operation
    if path == "/add":
        result = a_val + b_val
    elif path == "/sub":
        result = a_val - b_val
    elif path == "/mul":
        result = a_val * b_val
    elif path == "/div":
        if b_val == 0:
            return 400, "Bad Request", "Division by zero\n"
        result = a_val / b_val
    else:
        return 404, "Not Found", "Endpoint not found\n"
        
    return 200, "OK", format_number(result)


def handle_client(client_socket, client_address):
    client_socket.settimeout(IDLE_TIMEOUT)
    recv_buffer = bytearray()
    
    try:
        while True:
            # Check if buffer already contains complete header (\r\n\r\n)
            while b"\r\n\r\n" not in recv_buffer:
                try:
                    chunk = client_socket.recv(4096)
                    if not chunk:
                        # Client closed connection
                        return
                    recv_buffer.extend(chunk)
                except socket.timeout:
                    # Idle timeout defense
                    return
                except ConnectionResetError:
                    return

            # Extract header part from buffer
            header_end_idx = recv_buffer.find(b"\r\n\r\n")
            header_bytes = recv_buffer[:header_end_idx]
            # Advance buffer past header
            del recv_buffer[:header_end_idx + 4]
            
            # Parse HTTP header text
            header_text = header_bytes.decode("iso-8859-1", errors="replace")
            lines = header_text.split("\r\n")
            if not lines or not lines[0].strip():
                continue
            
            request_line = lines[0].strip()
            headers = {}
            for line in lines[1:]:
                if ":" in line:
                    key, value = line.split(":", 1)
                    headers[key.strip().lower()] = value.strip()
            
            # Check Content-Length if present (for requests with body)
            content_length = 0
            if "content-length" in headers:
                try:
                    content_length = int(headers["content-length"])
                except ValueError:
                    content_length = 0
            
            # Read exact Content-Length bytes if present
            while len(recv_buffer) < content_length:
                try:
                    chunk = client_socket.recv(4096)
                    if not chunk:
                        return
                    recv_buffer.extend(chunk)
                except (socket.timeout, ConnectionResetError):
                    return
            
            # Body payload (if any)
            request_body = bytes(recv_buffer[:content_length])
            del recv_buffer[:content_length]
            
            # Check client Connection header
            client_connection = headers.get("connection", "keep-alive").lower()
            keep_alive = (client_connection != "close")
            
            # Dispatch & generate response
            status_code, status_text, body, *extra = handle_request(request_line, headers)
            extra_headers = extra[0] if extra else {}
            
            response_bytes = build_response(
                status_code, status_text, body, extra_headers, keep_alive=keep_alive
            )
            client_socket.sendall(response_bytes)
            
            if not keep_alive:
                break
                
    except Exception as e:
        pass
    finally:
        try:
            client_socket.close()
        except OSError:
            pass


class CalculatorServer:
    def __init__(self, host=HOST, port=DEFAULT_PORT):
        self.host = host
        self.port = port
        self.server_socket = None
        self.is_running = False
        self._thread = None

    def start(self, background=False):
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server_socket.bind((self.host, self.port))
        self.server_socket.listen(128)
        self.is_running = True
        
        if background:
            self._thread = threading.Thread(target=self._listen_loop, daemon=True)
            self._thread.start()
        else:
            self._listen_loop()

    def _listen_loop(self):
        print(f"[*] Calculator Server listening on {self.host}:{self.port}")
        while self.is_running:
            try:
                client_sock, addr = self.server_socket.accept()
                t = threading.Thread(target=handle_client, args=(client_sock, addr), daemon=True)
                t.start()
            except OSError:
                break

    def stop(self):
        self.is_running = False
        if self.server_socket:
            try:
                self.server_socket.close()
            except OSError:
                pass


if __name__ == "__main__":
    port = DEFAULT_PORT
    if len(sys.argv) > 1:
        port = int(sys.argv[1])
    server = CalculatorServer(port=port)
    try:
        server.start(background=False)
    except KeyboardInterrupt:
        print("\n[*] Shutting down Calculator Server.")
        server.stop()
