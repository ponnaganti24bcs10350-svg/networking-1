#!/usr/bin/env python3
"""
Unit and Integration tests for HTTP/1.1 Calculator Server
"""

import unittest
import threading
import socket
import time
from http11_calculator.server import CalculatorServer
from http11_calculator.client_evaluator import run_evaluation, parse_http_response


class TestHTTP11Calculator(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.port = 8081
        cls.server = CalculatorServer(port=cls.port)
        cls.server.start(background=True)
        time.sleep(0.2)

    @classmethod
    def tearDownClass(cls):
        cls.server.stop()

    def test_professor_evaluator_suite(self):
        """Run professor's exact evaluation suite over a single TCP socket"""
        passed = run_evaluation("localhost", self.port)
        self.assertTrue(passed)

    def test_connection_close_header(self):
        """Server should close socket after response when Connection: close is sent"""
        s = socket.create_connection(("localhost", self.port))
        req = f"GET /add?a=5&b=5 HTTP/1.1\r\nHost: localhost:{self.port}\r\nConnection: close\r\n\r\n"
        s.sendall(req.encode("utf-8"))
        
        buffer = bytearray()
        while True:
            chunk = s.recv(4096)
            if not chunk:
                break
            buffer.extend(chunk)
            
        status, headers, body, _ = parse_http_response(buffer)
        s.close()
        self.assertEqual(status, 200)
        self.assertEqual(body.strip(), "10")
        self.assertEqual(headers.get("connection"), "close")

    def test_pipelined_requests(self):
        """Server should handle multiple requests sent in a single sendall buffer"""
        s = socket.create_connection(("localhost", self.port))
        s.settimeout(2.0)
        
        req1 = f"GET /add?a=10&b=20 HTTP/1.1\r\nHost: localhost:{self.port}\r\n\r\n"
        req2 = f"GET /mul?a=3&b=4 HTTP/1.1\r\nHost: localhost:{self.port}\r\n\r\n"
        
        # Send both requests concatenated together (Pipelining)
        s.sendall((req1 + req2).encode("utf-8"))
        
        buffer = bytearray()
        while True:
            status1, headers1, body1, leftover1 = parse_http_response(buffer)
            if status1 is not None:
                status2, headers2, body2, leftover2 = parse_http_response(leftover1)
                if status2 is not None:
                    c_len2 = int(headers2.get("content-length", 0))
                    h_len2 = leftover1.find(b"\r\n\r\n") + 4
                    if len(leftover1) >= h_len2 + c_len2:
                        break
            chunk = s.recv(4096)
            if not chunk:
                break
            buffer.extend(chunk)
                
        # Parse first response
        status1, headers1, body1, leftover1 = parse_http_response(buffer)
        self.assertEqual(status1, 200)
        self.assertEqual(body1.strip(), "30")
        
        # Parse second response
        status2, headers2, body2, leftover2 = parse_http_response(leftover1)
        self.assertEqual(status2, 200)
        self.assertEqual(body2.strip(), "12")
        s.close()


if __name__ == "__main__":
    unittest.main()
