#!/usr/bin/env python3
import argparse
import os
import secrets


def main():
    parser = argparse.ArgumentParser(description="Generate a random key for HMAC/encryption.")
    parser.add_argument("--out", default="keys/signing.key")
    parser.add_argument("--bytes", type=int, default=32)
    args = parser.parse_args()

    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    key = secrets.token_bytes(args.bytes)
    with open(args.out, "wb") as f:
        f.write(key)
    print(f"wrote {args.out}")


if __name__ == "__main__":
    main()
