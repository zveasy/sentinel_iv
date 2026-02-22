#!/usr/bin/env python3
"""
Minimal WaveOS stub: logs incoming events; can emit ACTION_ACK for testing.
Run in container; optionally connect to MQTT to receive HB ACTION_REQUEST and reply ACTION_ACK.
"""
import os
import time

def main():
    print("WaveOS stub: running (no MQTT client in this minimal stub)")
    while True:
        time.sleep(60)

if __name__ == "__main__":
    main()
