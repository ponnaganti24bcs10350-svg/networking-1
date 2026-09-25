#!/usr/bin/env python3
"""
bserve - Binary HTTP Protocol Server (Track 1)
Usage: python3 bserve.py <root_dir> <port>
Listens on TCP socket, accepts binary frames, maps paths to files under root_dir,
serves HEADERS and DATA frames over persistent TCP connections.
"""

import sys
import os
import socket
import threading
from binary_http.protocol import (
    read_next_frame,
    pack_frame,
    encode_headers,
    decode_headers,
    FRAME_HEADERS,
    FRAME_DATA,
    FLAG_END_STREAM,
    FLAG_END_HEADERS,
    MalformedFrameError,
)

DEFAULT_PORT = 9000
DEFAULT_ROOT = "./www"


def resolve_file_path(root_dir, request_path):
    # Sanitize path to prevent directory traversal
    clean_path = os.path.normpath(request_path.lstrip("/"))
    if clean_path in ("", "."):
        clean_path = "index.html"
        
    full_path = os.path.join(root_dir, clean_path)
    # Check if inside root directory
    abs_root = os.path.abspath(root_dir)
    abs_full = os.path.abspath(full_path)
    
    if not abs_full.startswith(abs_root):
        return None  # Security traversal block
        
    if os.path.isfile(abs_full):
        return abs_full
    return None


def handle_client_connection(client_sock, client_addr, root_dir):
    try:
        while True:
            frame = read_next_frame(client_sock)
            if frame is None:
                # Client closed socket
                break
                
            frame_type, flags, stream_id, payload = frame
            
            if frame_type != FRAME_HEADERS:
                # First frame on a stream should be HEADERS
                err_hdr = encode_headers({":status": "400", "server": "bserve/1.0"})
                resp_frame = pack_frame(FRAME_HEADERS, FLAG_END_HEADERS | FLAG_END_STREAM, stream_id, err_hdr)
                client_sock.sendall(resp_frame)
                continue
                
            try:
                headers = decode_headers(payload)
            except Exception:
                err_hdr = encode_headers({":status": "400", "server": "bserve/1.0"})
                resp_frame = pack_frame(FRAME_HEADERS, FLAG_END_HEADERS | FLAG_END_STREAM, stream_id, err_hdr)
                client_sock.sendall(resp_frame)
                continue
                
            path = headers.get(":path", "/")
            method = headers.get(":method", "GET")
            
            file_path = resolve_file_path(root_dir, path)
            if file_path is None:
                # 404 Not Found
                body_bytes = b"404 File Not Found\n"
                res_headers = {
                    ":status": "404",
                    "content-type": "text/plain",
                    "content-length": str(len(body_bytes)),
                    "server": "bserve/1.0",
                }
                hdr_bytes = encode_headers(res_headers)
                hdr_frame = pack_frame(FRAME_HEADERS, FLAG_END_HEADERS, stream_id, hdr_bytes)
                data_frame = pack_frame(FRAME_DATA, FLAG_END_STREAM, stream_id, body_bytes)
                client_sock.sendall(hdr_frame + data_frame)
            else:
                try:
                    with open(file_path, "rb") as f:
                        body_bytes = f.read()
                        
                    res_headers = {
                        ":status": "200",
                        "content-type": "text/html" if file_path.endswith(".html") else "application/octet-stream",
                        "content-length": str(len(body_bytes)),
                        "server": "bserve/1.0",
                    }
                    hdr_bytes = encode_headers(res_headers)
                    hdr_frame = pack_frame(FRAME_HEADERS, FLAG_END_HEADERS, stream_id, hdr_bytes)
                    data_frame = pack_frame(FRAME_DATA, FLAG_END_STREAM, stream_id, body_bytes)
                    client_sock.sendall(hdr_frame + data_frame)
                except IOError:
                    body_bytes = b"500 Internal Server Error\n"
                    res_headers = {
                        ":status": "500",
                        "content-length": str(len(body_bytes)),
                        "server": "bserve/1.0",
                    }
                    hdr_bytes = encode_headers(res_headers)
                    hdr_frame = pack_frame(FRAME_HEADERS, FLAG_END_HEADERS, stream_id, hdr_bytes)
                    data_frame = pack_frame(FRAME_DATA, FLAG_END_STREAM, stream_id, body_bytes)
                    client_sock.sendall(hdr_frame + data_frame)

    except (ConnectionResetError, BrokenPipeError):
        pass
    finally:
        client_sock.close()


class BinaryServer:
    def __init__(self, root_dir=DEFAULT_ROOT, port=DEFAULT_PORT, host="127.0.0.1"):
        self.root_dir = root_dir
        self.port = port
        self.host = host
        self.server_socket = None
        self.is_running = False
        self._thread = None

    def start(self, background=False):
        os.makedirs(self.root_dir, exist_ok=True)
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
        print(f"[*] bserve Binary Server listening on {self.host}:{self.port} serving root '{self.root_dir}'")
        while self.is_running:
            try:
                client_sock, addr = self.server_socket.accept()
                t = threading.Thread(
                    target=handle_client_connection,
                    args=(client_sock, addr, self.root_dir),
                    daemon=True,
                )
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
    root = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_ROOT
    port = int(sys.argv[2]) if len(sys.argv) > 2 else DEFAULT_PORT
    server = BinaryServer(root_dir=root, port=port)
    try:
        server.start(background=False)
    except KeyboardInterrupt:
        print("\n[*] Shutting down bserve.")
        server.stop()
