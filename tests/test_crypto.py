import pytest
from cryptography.exceptions import InvalidTag

from cli_cache.crypto import _decrypt, _derive_key, _encrypt


def test_derive_key_deterministic():
    salt = b"a" * 16
    k1 = _derive_key("password", salt)
    k2 = _derive_key("password", salt)
    assert k1 == k2


def test_derive_key_different_passwords():
    salt = b"a" * 16
    assert _derive_key("pass1", salt) != _derive_key("pass2", salt)


def test_derive_key_different_salts():
    assert _derive_key("password", b"a" * 16) != _derive_key("password", b"b" * 16)


def test_derive_key_length():
    key = _derive_key("password", b"a" * 16)
    assert len(key) == 32  # AES-256


def test_encrypt_decrypt_roundtrip():
    key = _derive_key("password", b"s" * 16)
    plaintext = b"hello world"
    blob = _encrypt(plaintext, key)
    assert _decrypt(blob, key) == plaintext


def test_encrypt_nonce_is_random():
    key = _derive_key("password", b"s" * 16)
    blob1 = _encrypt(b"data", key)
    blob2 = _encrypt(b"data", key)
    assert blob1[:12] != blob2[:12]  # nonces differ


def test_decrypt_wrong_key_raises():
    key = _derive_key("password", b"s" * 16)
    wrong_key = _derive_key("wrong", b"s" * 16)
    blob = _encrypt(b"data", key)
    with pytest.raises(InvalidTag):
        _decrypt(blob, wrong_key)


def test_decrypt_tampered_data_raises():
    key = _derive_key("password", b"s" * 16)
    blob = bytearray(_encrypt(b"data", key))
    blob[-1] ^= 0xFF  # flip last byte
    with pytest.raises(InvalidTag):
        _decrypt(bytes(blob), key)
