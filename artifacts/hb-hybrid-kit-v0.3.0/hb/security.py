import base64
import hashlib
import hmac
import os


def load_key(path):
    with open(path, "rb") as f:
        return f.read().strip()


def sign_file(path, key_bytes):
    payload = open(path, "rb").read()
    digest = hmac.new(key_bytes, payload, hashlib.sha256).hexdigest()
    return digest


def verify_signature(path, key_bytes, expected_hex):
    actual = sign_file(path, key_bytes)
    return hmac.compare_digest(actual, expected_hex)


def encrypt_file(path, key_bytes):
    try:
        from cryptography.fernet import Fernet
    except ImportError:
        return None, "cryptography not installed"

    if len(key_bytes) == 32:
        key_bytes = base64.urlsafe_b64encode(key_bytes)
    fernet = Fernet(key_bytes)
    plaintext = open(path, "rb").read()
    ciphertext = fernet.encrypt(plaintext)
    out_path = path + ".enc"
    with open(out_path, "wb") as f:
        f.write(ciphertext)
    return out_path, None


def decrypt_file(path, key_bytes):
    try:
        from cryptography.fernet import Fernet
    except ImportError:
        return None, "cryptography not installed"

    if len(key_bytes) == 32:
        key_bytes = base64.urlsafe_b64encode(key_bytes)
    fernet = Fernet(key_bytes)
    ciphertext = open(path, "rb").read()
    plaintext = fernet.decrypt(ciphertext)
    out_path = path + ".dec"
    with open(out_path, "wb") as f:
        f.write(plaintext)
    return out_path, None
