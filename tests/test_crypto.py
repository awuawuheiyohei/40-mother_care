"""Tests for WeChat AES-256-CBC crypto."""

from __future__ import annotations

import base64
import struct

import pytest

from app.wechat.crypto import (
    Decrypted,
    build_encrypted_reply_envelope,
    decrypt,
    encrypt,
    sha1_sign,
    verify_and_decrypt_echo,
    verify_and_decrypt_message,
    verify_signature,
)


# 43-char EncodingAESKey (sample from WeChat docs, NOT a real key)
TEST_AES_KEY = "jWmYm7qr5nMoAUwZRjGtBxmz3KA1tkAj3ykkR6q2B2C"
TEST_TOKEN = "QDG6eK"
TEST_CORP_ID = "wx5823bf96d3bd56c7"


def test_sha1_sign_matches_wechat_spec():
    """sha1_sign sorts inputs lexicographically before joining — matches WeChat."""
    token, ts, nonce, encrypted = "tok", "1409659813", "1372623149", "encrypted"
    sig = sha1_sign(token, ts, nonce, encrypted)
    # Re-compute with explicit sort
    import hashlib as _h
    expected = _h.sha1("".join(sorted([token, ts, nonce, encrypted])).encode()).hexdigest()
    assert sig == expected


def test_encrypt_decrypt_roundtrip():
    """Encrypted message can be decrypted back to the same plaintext + receive_id."""
    plaintext = "<xml><Content>hello</Content></xml>"
    corp = TEST_CORP_ID

    enc = encrypt(plaintext, TEST_AES_KEY, corp)
    assert isinstance(enc, str)
    # Must be valid base64
    base64.b64decode(enc)

    dec = decrypt(enc, TEST_AES_KEY)
    assert isinstance(dec, Decrypted)
    assert dec.message == plaintext
    assert dec.receive_id == corp


def test_decrypt_handles_long_messages():
    """Long messages (over 16-byte boundary) decrypt cleanly."""
    long_msg = "<xml>" + ("x" * 1000) + "</xml>"
    enc = encrypt(long_msg, TEST_AES_KEY, TEST_CORP_ID)
    dec = decrypt(enc, TEST_AES_KEY)
    assert dec.message == long_msg
    assert dec.receive_id == TEST_CORP_ID


def test_decrypt_handles_chinese():
    """Chinese UTF-8 message survives encrypt/decrypt."""
    msg = "<xml><Content>新生儿发烧多少度算危险？</Content></xml>"
    enc = encrypt(msg, TEST_AES_KEY, TEST_CORP_ID)
    dec = decrypt(enc, TEST_AES_KEY)
    assert dec.message == msg


def test_signature_verify_accepts_correct():
    """Correct signature passes verification."""
    encrypted = "abc123"
    ts, nonce = "1", "2"
    sig = sha1_sign(TEST_TOKEN, ts, nonce, encrypted)
    assert verify_signature(TEST_TOKEN, ts, nonce, encrypted, sig) is True


def test_signature_verify_rejects_tampered():
    """Tampered signature fails verification."""
    assert verify_signature(TEST_TOKEN, "1", "2", "abc", "wrong-sig") is False


def test_wrong_aes_key_fails():
    """Decrypting with the wrong key produces a payload that fails PKCS7 unpad."""
    enc = encrypt("hello", TEST_AES_KEY, TEST_CORP_ID)
    wrong_key = "X" * 43
    # Should either raise or produce garbage — we don't care exactly which,
    # as long as it doesn't return "hello" cleanly.
    with pytest.raises(Exception):
        decrypt(enc, wrong_key)


def test_wrong_key_length_raises():
    """EncodingAESKey must be exactly 43 chars."""
    with pytest.raises(ValueError):
        encrypt("hello", "short", TEST_CORP_ID)


def test_verify_and_decrypt_echo():
    """End-to-end URL verification with echo decryption."""
    # WeChat sends encrypted echostr; we decrypt and return plaintext
    echostr = "test_echo_string_12345"
    enc = encrypt(echostr, TEST_AES_KEY, TEST_CORP_ID)

    ts, nonce = "1", "2"
    sig = sha1_sign(TEST_TOKEN, ts, nonce, enc)
    result = verify_and_decrypt_echo(
        msg_signature=sig,
        timestamp=ts,
        nonce=nonce,
        echostr=enc,
        token=TEST_TOKEN,
        encoding_aes_key=TEST_AES_KEY,
        corp_id=TEST_CORP_ID,
    )
    assert result == echostr


def test_verify_and_decrypt_message():
    """End-to-end message decryption with signature check."""
    msg = "<xml><Content>宝宝发烧怎么办</Content></xml>"
    enc = encrypt(msg, TEST_AES_KEY, TEST_CORP_ID)

    ts, nonce = "1", "2"
    sig = sha1_sign(TEST_TOKEN, ts, nonce, enc)
    result = verify_and_decrypt_message(
        msg_signature=sig,
        timestamp=ts,
        nonce=nonce,
        encrypted=enc,
        token=TEST_TOKEN,
        encoding_aes_key=TEST_AES_KEY,
        corp_id=TEST_CORP_ID,
    )
    assert result == msg


def test_build_encrypted_reply_envelope():
    """Reply envelope is well-formed XML with signature + encrypt."""
    reply_xml = "<xml><Content>reply</Content></xml>"
    ts, nonce = "1", "2"
    envelope = build_encrypted_reply_envelope(
        plaintext_xml=reply_xml,
        timestamp=ts,
        nonce=nonce,
        token=TEST_TOKEN,
        encoding_aes_key=TEST_AES_KEY,
        corp_id=TEST_CORP_ID,
    )
    assert "<Encrypt>" in envelope
    assert "<MsgSignature>" in envelope
    assert f"<TimeStamp>{ts}</TimeStamp>" in envelope
    assert f"<Nonce><![CDATA[{nonce}]]></Nonce>" in envelope

    # Roundtrip: parse envelope, decrypt Encrypt, verify signature
    import re as _re

    sig_m = _re.search(r"<MsgSignature><!\[CDATA\[([^\]]+)\]\]></MsgSignature>", envelope)
    enc_m = _re.search(r"<Encrypt><!\[CDATA\[([^\]]+)\]\]></Encrypt>", envelope)
    assert sig_m and enc_m

    decrypted = decrypt(enc_m.group(1), TEST_AES_KEY)
    assert decrypted.message == reply_xml
    assert verify_signature(TEST_TOKEN, ts, nonce, enc_m.group(1), sig_m.group(1))