#!/usr/bin/env python3
"""
bcurl - Binary HTTP Protocol Client (Track 2)
Usage: python3 bcurl.py [-v] <host:port/path>
Builds binary request frame, sends over single TCP connection, receives response binary frames.
-v flag outputs detailed annotated hex dumps for all frames.
Exits non-zero on 4xx/5xx responses.
"""

import sys
import socket
import urllib.parse
from binary_http.protocol import (
    pack_frame,
    read_next_frame,
    encode_headers,
    decode_headers,
    annotate_hex_dump,
    FRAME_HEADERS,
    FRAME_DATA,
    FLAG_END_STREAM,
    FLAG_END_HEADERS,
    MalformedFrameError,
)


def parse_target_url(target_str):
    if not target_str.startswith("http://") and not target_str.startswith("https://"):
        target_str = "http://" + target_str
    parsed = urllib.parse.urlparse(target_str)
    
    host = parsed.hostname or "localhost"
    port = parsed.port or 9000
    path = parsed.path or "/index.html"
    if parsed.query:
        path += "?" + parsed.query
        
    return host, port, path


def run_bcurl(target_url, verbose=False, conn_socket=None, stream_id=1):
    host, port, path = parse_target_url(target_url)
    
    should_close_sock = False
    if conn_socket is None:
        conn_socket = socket.create_connection((host, port))
        conn_socket.settimeout(5.0)
        should_close_sock = True

    try:
        # Build HEADERS frame
        headers_dict = {
            ":method": "GET",
            ":path": path,
            ":scheme": "http",
            ":host": f"{host}:{port}",
            "user-agent": "bcurl/1.0",
        }
        hdr_payload = encode_headers(headers_dict)
        req_frame = pack_frame(FRAME_HEADERS, FLAG_END_HEADERS | FLAG_END_STREAM, stream_id, hdr_payload)
        
        if verbose:
            print(">>> SENDING REQUEST FRAME >>>")
            print(annotate_hex_dump(req_frame))
            print()
            
        conn_socket.sendall(req_frame)
        
        # Read response frames
        status_code = None
        response_headers = {}
        body_chunks = []
        
        while True:
            frame = read_next_frame(conn_socket)
            if frame is None:
                break
                
            frame_type, flags, rec_stream_id, payload = frame
            
            # Reconstruction of full frame for hex dumper visualization
            rec_full_frame = pack_frame(frame_type, flags, rec_stream_id, payload)
            
            if verbose:
                print("<<< RECEIVED RESPONSE FRAME <<<")
                print(annotate_hex_dump(rec_full_frame))
                print()
                
            if frame_type == FRAME_HEADERS:
                response_headers = decode_headers(payload)
                status_str = response_headers.get(":status", "200")
                status_code = int(status_str)
            elif frame_type == FRAME_DATA:
                body_chunks.append(payload)
                
            if flags & FLAG_END_STREAM:
                break

        full_body = b"".join(body_chunks)
        
        # Output body to stdout
        sys.stdout.buffer.write(full_body)
        sys.stdout.buffer.flush()
        
        if status_code is not None and status_code >= 400:
            return status_code
        return 0

    finally:
        if should_close_sock:
            conn_socket.close()


if __name__ == "__main__":
    args = sys.argv[1:]
    verbose = False
    if "-v" in args:
        verbose = True
        args.remove("-v")
        
    if not args:
        print("Usage: python3 bcurl.py [-v] <host:port/path>")
        sys.exit(1)
        
    target = args[0]
    exit_code = run_bcurl(target, verbose=verbose)
    sys.exit(exit_code)
