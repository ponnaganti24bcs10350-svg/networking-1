#!/usr/bin/env python3
"""
Unit and Integration tests for Binary HTTP Protocol (bserve, bcurl, protocol)
"""

import unittest
import socket
import time
import io
import sys
from binary_http.protocol import (
    pack_frame,
    unpack_frame_header,
    encode_headers,
    decode_headers,
    annotate_hex_dump,
    read_next_frame,
    FRAME_HEADERS,
    FRAME_DATA,
    FRAME_UNKNOWN_TEST,
    FLAG_NONE,
    FLAG_END_STREAM,
    FLAG_END_HEADERS,
)
from binary_http.bserve import BinaryServer
from binary_http.bcurl import run_bcurl


class TestBinaryHTTP(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.port = 9001
        cls.root_dir = "./www"
        cls.server = BinaryServer(root_dir=cls.root_dir, port=cls.port)
        cls.server.start(background=True)
        time.sleep(0.2)

    @classmethod
    def tearDownClass(cls):
        cls.server.stop()

    def test_frame_header_pack_unpack(self):
        """Test packing and unpacking 8-byte frame headers"""
        payload = b"Hello, Binary World!"
        frame = pack_frame(FRAME_DATA, FLAG_END_STREAM, stream_id=42, payload=payload)
        
        # Header is 8 bytes
        self.assertEqual(len(frame), 8 + len(payload))
        
        p_len, f_type, flags, stream_id = unpack_frame_header(frame[:8])
        self.assertEqual(p_len, len(payload))
        self.assertEqual(f_type, FRAME_DATA)
        self.assertEqual(flags, FLAG_END_STREAM)
        self.assertEqual(stream_id, 42)

    def test_header_encoding_static_table(self):
        """Test static table header indexing and literal fallbacks"""
        headers = {
            ":method": "GET",
            ":path": "/index.html",
            "custom-header": "custom-value",
        }
        encoded = encode_headers(headers)
        decoded = decode_headers(encoded)
        
        self.assertEqual(decoded[":method"], "GET")
        self.assertEqual(decoded[":path"], "/index.html")
        self.assertEqual(decoded["custom-header"], "custom-value")

    def test_bcurl_get_index(self):
        """Test bcurl fetching index.html from bserve"""
        exit_code = run_bcurl(f"localhost:{self.port}/index.html", verbose=False)
        self.assertEqual(exit_code, 0)

    def test_bcurl_404_non_zero_exit(self):
        """Test bcurl exiting with non-zero code on 404 Not Found"""
        exit_code = run_bcurl(f"localhost:{self.port}/non_existent_file.html", verbose=False)
        self.assertEqual(exit_code, 404)

    def test_unknown_frame_skipping(self):
        """Test server and reader cleanly skipping unknown frame types (forward compatibility)"""
        s = socket.create_connection(("localhost", self.port))
        
        # Send unknown frame type 0x99 with payload
        unkn_frame = pack_frame(FRAME_UNKNOWN_TEST, FLAG_NONE, stream_id=0, payload=b"FUTURE_V2_PAYLOAD")
        s.sendall(unkn_frame)
        
        # Right after, send valid HEADERS request frame over SAME socket
        req_hdr = encode_headers({":method": "GET", ":path": "/index.html"})
        valid_frame = pack_frame(FRAME_HEADERS, FLAG_END_HEADERS | FLAG_END_STREAM, stream_id=1, payload=req_hdr)
        s.sendall(valid_frame)
        
        # Read response
        resp_frame = read_next_frame(s)
        s.close()
        
        self.assertIsNotNone(resp_frame)
        f_type, flags, s_id, payload = resp_frame
        self.assertEqual(f_type, FRAME_HEADERS)
        headers = decode_headers(payload)
        self.assertEqual(headers.get(":status"), "200")

    def test_annotated_hex_dump_output(self):
        """Test annotated hex dump formatting string output"""
        payload = encode_headers({":status": "200", ":path": "/"})
        frame = pack_frame(FRAME_HEADERS, FLAG_END_HEADERS | FLAG_END_STREAM, stream_id=7, payload=payload)
        dump = annotate_hex_dump(frame)
        
        self.assertIn("FRAME HEADER", dump)
        self.assertIn("HEADERS (0x01)", dump)
        self.assertIn("Stream ID: 7", dump)


if __name__ == "__main__":
    unittest.main()
