"""AES-256-CBC crypto for Enterprise WeChat encrypted callbacks.

Reference: https://developer.work.weixin.qq.com/document/path/90968

Wire format after decryption:
    bytes [0..16)         = random (16 bytes, ignored)
    bytes [16..20)        = msg_len (big-endian uint32)
    bytes [20..20+msg_len) = message
    bytes [20+msg_len..20+msg_len+receiveid_len) = receiveid (corp_id)

EncodingAESKey is a 43-char base64 string. The actual AES-256 key is base64
decoded (43 chars + "=" padding gives 32 bytes). IV = first 16 bytes of key.

This module supports both encrypted and plaintext modes. The handler picks
based on whether `WECHAT_CALLBACK_AES_KEY` is set.
"""

from __future__ import annotations

import base64
import hashlib
import os
import struct
from dataclasses import dataclass

from cryptography.hazmat.primitives import padding as sym_padding
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes


AES_BLOCK_SIZE = 16  # AES block size is always 16 bytes (128 bits)
RANDOM_LEN = 16
LEN_LEN = 4
PKCS7_BLOCK_BITS = AES_BLOCK_SIZE * 8  # PKCS7 constructor takes BITS, not bytes


def sha1_sign(*parts: str) -> str:
    """Compute WeChat signature: SHA1 of sorted concat."""
    return hashlib.sha1("".join(sorted(parts)).encode("utf-8")).hexdigest()


def verify_signature(token: str, timestamp: str, nonce: str, encrypted: str, signature: str) -> bool:
    """Verify msg_signature = SHA1(sort([token, timestamp, nonce, encrypted]))."""
    expected = sha1_sign(token, timestamp, nonce, encrypted)
    return expected == signature


def _decode_aes_key(encoding_aes_key: str) -> tuple[bytes, bytes]:
    """Return (key, iv). Key = base64-decoded EncodingAESKey+'=', IV = key[:16]."""
    if len(encoding_aes_key) != 43:
        raise ValueError(f"EncodingAESKey must be 43 chars, got {len(encoding_aes_key)}")
    key = base64.b64decode(encoding_aes_key + "=")
    if len(key) != 32:
        raise ValueError(f"Decoded AES key must be 32 bytes, got {len(key)}")
    return key, key[:16]


def _pkcs7_unpad(data: bytes) -> bytes:
    padder = sym_padding.PKCS7(PKCS7_BLOCK_BITS).unpadder()
    return padder.update(data) + padder.finalize()


def _pkcs7_pad(data: bytes) -> bytes:
    padder = sym_padding.PKCS7(PKCS7_BLOCK_BITS).padder()
    return padder.update(data) + padder.finalize()


def _aes_cbc_decrypt(ciphertext: bytes, key: bytes, iv: bytes) -> bytes:
    cipher = Cipher(algorithms.AES(key), modes.CBC(iv))
    decryptor = cipher.decryptor()
    return _pkcs7_unpad(decryptor.update(ciphertext) + decryptor.finalize())


def _aes_cbc_encrypt(plaintext: bytes, key: bytes, iv: bytes) -> bytes:
    cipher = Cipher(algorithms.AES(key), modes.CBC(iv))
    encryptor = cipher.encryptor()
    return encryptor.update(_pkcs7_pad(plaintext)) + encryptor.finalize()


# =============================================================================
# Decryption (used for URL verification echostr AND incoming message bodies)
# =============================================================================


@dataclass
class Decrypted:
    message: str  # the actual XML/JSON message content
    receive_id: str  # the corp_id (sanity check)


def decrypt(encrypted_b64: str, encoding_aes_key: str) -> Decrypted:
    """Decrypt an encrypted message body. Returns message + receive_id."""
    key, iv = _decode_aes_key(encoding_aes_key)
    ciphertext = base64.b64decode(encrypted_b64)
    plain = _aes_cbc_decrypt(ciphertext, key, iv)

    # Parse structure
    if len(plain) < RANDOM_LEN + LEN_LEN:
        raise ValueError("Decrypted payload too short")
    msg_len = struct.unpack(">I", plain[RANDOM_LEN : RANDOM_LEN + LEN_LEN])[0]
    start = RANDOM_LEN + LEN_LEN
    end = start + msg_len
    if end > len(plain):
        raise ValueError(f"msg_len {msg_len} exceeds payload size {len(plain)}")
    message = plain[start:end].decode("utf-8")
    receive_id = plain[end:].decode("utf-8")
    return Decrypted(message=message, receive_id=receive_id)


# =============================================================================
# Encryption (used for outbound passive replies)
# =============================================================================


def encrypt(plaintext: str, encoding_aes_key: str, receive_id: str) -> str:
    """Encrypt a reply message. Returns base64 ciphertext."""
    key, iv = _decode_aes_key(encoding_aes_key)
    rand_bytes = os.urandom(RANDOM_LEN)
    msg_bytes = plaintext.encode("utf-8")
    msg_len = struct.pack(">I", len(msg_bytes))
    receive_id_bytes = receive_id.encode("utf-8")
    plain = rand_bytes + msg_len + msg_bytes + receive_id_bytes
    ciphertext = _aes_cbc_encrypt(plain, key, iv)
    return base64.b64encode(ciphertext).decode("utf-8")


# =============================================================================
# Convenience helpers used by handlers
# =============================================================================


def verify_and_decrypt_echo(
    msg_signature: str,
    timestamp: str,
    nonce: str,
    echostr: str,
    token: str,
    encoding_aes_key: str,
    corp_id: str,
) -> str:
    """URL verification: decrypt the encrypted echostr and return plaintext.

    Raises ValueError on signature mismatch or decryption failure.
    """
    if not verify_signature(token, timestamp, nonce, echostr, msg_signature):
        raise ValueError("msg_signature mismatch")
    decrypted = decrypt(echostr, encoding_aes_key)
    if decrypted.receive_id != corp_id:
        raise ValueError(
            f"receive_id mismatch: expected {corp_id!r}, got {decrypted.receive_id!r}"
        )
    return decrypted.message


def verify_and_decrypt_message(
    msg_signature: str,
    timestamp: str,
    nonce: str,
    encrypted: str,
    token: str,
    encoding_aes_key: str,
    corp_id: str,
) -> str:
    """Decrypt an incoming message body. Returns the inner XML string."""
    if not verify_signature(token, timestamp, nonce, encrypted, msg_signature):
        raise ValueError("msg_signature mismatch")
    decrypted = decrypt(encrypted, encoding_aes_key)
    if decrypted.receive_id != corp_id:
        raise ValueError(
            f"receive_id mismatch: expected {corp_id!r}, got {decrypted.receive_id!r}"
        )
    return decrypted.message


def build_encrypted_reply_envelope(
    plaintext_xml: str,
    timestamp: str,
    nonce: str,
    token: str,
    encoding_aes_key: str,
    corp_id: str,
) -> str:
    """Build the encrypted reply XML envelope.

    Output:
    <xml>
      <Encrypt>...</Encrypt>
      <MsgSignature>...</MsgSignature>
      <TimeStamp>...</TimeStamp>
      <Nonce>...</Nonce>
    </xml>
    """
    encrypted = encrypt(plaintext_xml, encoding_aes_key, corp_id)
    signature = sha1_sign(token, timestamp, nonce, encrypted)
    return (
        f"<xml>"
        f"<Encrypt><![CDATA[{encrypted}]]></Encrypt>"
        f"<MsgSignature><![CDATA[{signature}]]></MsgSignature>"
        f"<TimeStamp>{timestamp}</TimeStamp>"
        f"<Nonce><![CDATA[{nonce}]]></Nonce>"
        f"</xml>"
    )