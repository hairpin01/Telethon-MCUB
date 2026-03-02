"""
Tests for telethon password module
"""
import pytest

from telethon import password


def test_check_prime_invalid_bit_length():
    """Test that invalid bit lengths raise ValueError"""
    with pytest.raises(ValueError):
        password.check_prime_and_good_check(12345, 2)


def test_pbkdf2sha512():
    """Test PBKDF2 implementation"""
    result = password.pbkdf2sha512(b"test", b"salt", 100000)
    assert len(result) == 64  # SHA-512 produces 64 bytes


def test_password_module_imports():
    """Test that password module can be imported"""
    from telethon import password
    assert hasattr(password, 'check_prime_and_good_check')
    assert hasattr(password, 'pbkdf2sha512')
    assert hasattr(password, 'compute_check')
