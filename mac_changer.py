#!/usr/bin/env python3
"""
mac_changer.py — safer, minimal MAC address changer
Use only in authorized/test environments.
"""

import argparse
import re
import subprocess
import sys
import os

MAC_REGEX = r"^(?:[0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}$"

def is_root():
    try:
        return os.geteuid() == 0
    except AttributeError:
        # non-POSIX: cannot reliably check, warn user
        return False

def parse_args():
    p = argparse.ArgumentParser(description="Change MAC address (use in authorized environments only)")
    p.add_argument("-i", "--interface", required=True, help="Network interface (e.g. eth0)")
    p.add_argument("-m", "--mac", required=True, help="New MAC address (format: xx:xx:xx:xx:xx:xx)")
    return p.parse_args()

def validate_mac(mac):
    return re.match(MAC_REGEX, mac) is not None

def run_cmd(cmd):
    try:
        subprocess.run(cmd, check=True)
    except subprocess.CalledProcessError as e:
        print(f"[!] Command failed: {' '.join(cmd)} (exit {e.returncode})")
        sys.exit(1)

def get_current_mac(interface):
    # try ip first
    try:
        out = subprocess.check_output(["ip", "link", "show", interface], stderr=subprocess.DEVNULL).decode()
        m = re.search(r"link/\w+\s+([0-9a-f:]{17})", out, re.IGNORECASE)
        if m:
            return m.group(1)
    except Exception:
        pass
    # fallback to ifconfig
    try:
        out = subprocess.check_output(["ifconfig", interface], stderr=subprocess.DEVNULL).decode()
        m = re.search(r"([0-9A-Fa-f]{2}(?::[0-9A-Fa-f]{2}){5})", out)
        if m:
            return m.group(1)
    except Exception:
        pass
    return None

def change_mac_ip(interface, new_mac):
    # prefer iproute2
    print(f"[+] Using ip link to set MAC on {interface}")
    run_cmd(["ip", "link", "set", "dev", interface, "down"])
    run_cmd(["ip", "link", "set", "dev", interface, "address", new_mac])
    run_cmd(["ip", "link", "set", "dev", interface, "up"])

def change_mac_ifconfig(interface, new_mac):
    print(f"[+] Falling back to ifconfig for {interface}")
    run_cmd(["ifconfig", interface, "down"])
    run_cmd(["ifconfig", interface, "hw", "ether", new_mac])
    run_cmd(["ifconfig", interface, "up"])

def main():
    args = parse_args()

    if not is_root():
        print("[!] This script must be run as root (sudo). Exiting.")
        sys.exit(1)

    if not validate_mac(args.mac):
        print("[!] Invalid MAC format. Expected: xx:xx:xx:xx:xx:xx (hex pairs).")
        sys.exit(1)

    current = get_current_mac(args.interface)
    print(f"[+] Current MAC for {args.interface}: {current or 'unknown'}")
    try:
        # try ip
        change_mac_ip(args.interface, args.mac)
    except SystemExit:
        # run_cmd already exits on failure
        sys.exit(1)
    except Exception:
        # fallback to ifconfig
        try:
            change_mac_ifconfig(args.interface, args.mac)
        except Exception as e:
            print(f"[!] Failed to change MAC: {e}")
            sys.exit(1)

    new = get_current_mac(args.interface)
    if new and new.lower() == args.mac.lower():
        print(f"[+] MAC successfully changed to {new}")
    else:
        print("[!] MAC change did not take effect or could not be verified.")
        print(f"[+] Current observed MAC: {new or 'unknown'}")

if __name__ == "__main__":
    main()

