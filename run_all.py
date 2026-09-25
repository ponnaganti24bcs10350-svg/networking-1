#!/usr/bin/env python3
"""
Master Verification Runner for Networking Homework 1
Runs all unit tests, HTTP/1.1 Calculator evaluation, and Binary HTTP framing demos.
"""

import sys
import unittest
import time
import os

# Import modules to verify everything is working cleanly
from http11_calculator.server import CalculatorServer
from http11_calculator.client_evaluator import run_evaluation
from binary_http.bserve import BinaryServer
from binary_http.bcurl import run_bcurl


def run_master_suite():
    print("\n" + "=" * 70)
    print(" 🌟 NETWORKING HOMEWORK 1: COMPREHENSIVE VERIFICATION SUITE")
    print("=" * 70 + "\n")
    
    # 1. Run Unit Tests via unittest loader
    print(">>> STEP 1: Running Automated Unit Tests (tests/)...")
    loader = unittest.TestLoader()
    suite = loader.discover(start_dir="tests", pattern="test_*.py")
    runner = unittest.TextTestRunner(verbosity=2)
    test_result = runner.run(suite)
    
    if not test_result.wasSuccessful():
        print("\n❌ Unit tests failed!")
        return False
        
    print("\n✅ All unit tests passed cleanly!\n")
    
    # 2. HTTP/1.1 Calculator Server Live Verification
    print(">>> STEP 2: Running HTTP/1.1 Persistent Calculator Live Test...")
    calc_server = CalculatorServer(port=8080)
    calc_server.start(background=True)
    time.sleep(0.3)
    
    try:
        calc_ok = run_evaluation("localhost", 8080)
    finally:
        calc_server.stop()
        
    if not calc_ok:
        print("\n❌ HTTP/1.1 Calculator evaluation failed!")
        return False
        
    print("\n✅ HTTP/1.1 Persistent Calculator Server verified successfully!\n")
    
    # 3. Binary HTTP Protocol (bserve & bcurl) Live Demo
    print(">>> STEP 3: Running Binary HTTP (bserve & bcurl) Frame Demo with -v...")
    bin_server = BinaryServer(root_dir="./www", port=9000)
    bin_server.start(background=True)
    time.sleep(0.3)
    
    try:
        # Run bcurl with -v to show annotated hex dump
        bcurl_exit = run_bcurl("localhost:9000/index.html", verbose=True)
    finally:
        bin_server.stop()
        
    if bcurl_exit != 0:
        print(f"\n❌ bcurl exited with error code {bcurl_exit}")
        return False
        
    print("\n✅ Binary HTTP Protocol (bserve & bcurl) verified successfully!\n")
    
    print("=" * 70)
    print(" 🎉 ALL HOMEWORK REQUIREMENTS FULLY VERIFIED WITH 0 ERRORS!")
    print("=" * 70 + "\n")
    return True


if __name__ == "__main__":
    success = run_master_suite()
    sys.exit(0 if success else 1)
