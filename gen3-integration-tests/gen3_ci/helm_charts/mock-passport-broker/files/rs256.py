"""
Minimal, dependency-free RS256 JWT signing for the mock passport broker.

Reads an RSA private key PEM (PKCS#1 or PKCS#8), signs JWTs with
RSASSA-PKCS1-v1_5 using SHA-256 (RFC 7518 section 3.3), and exports the public
half of the key as a PEM and as an RFC 7517 JWK.

Runs on the Python standard library only, so the broker needs no image build
and no network access at startup. This is a test fixture: the signing is not
constant-time, so never use it with a key that protects anything real.
"""

import base64
import hashlib
import json

# SEQUENCE { OID 1.2.840.113549.1.1.1 (rsaEncryption), NULL }
RSA_ALGORITHM_IDENTIFIER = bytes.fromhex("300d06092a864886f70d0101010500")
RSA_OID = bytes.fromhex("06092a864886f70d010101")

# DER encoding of DigestInfo { sha256, NULL } minus the digest (RFC 8017 9.2)
SHA256_DIGEST_INFO_PREFIX = bytes.fromhex("3031300d060960864801650304020105000420")


def b64url_encode(data):
    return base64.urlsafe_b64encode(data).decode().rstrip("=")


def _uint_bytes(value):
    return value.to_bytes((value.bit_length() + 7) // 8 or 1, "big")


# --- tiny DER reader ---------------------------------------------------------


def _read_tlv(buf, offset):
    """Read one DER tag-length-value at offset. Returns (tag, value, next_offset)."""
    tag = buf[offset]
    length = buf[offset + 1]
    offset += 2
    if length & 0x80:
        num_bytes = length & 0x7F
        length = int.from_bytes(buf[offset : offset + num_bytes], "big")
        offset += num_bytes
    return tag, buf[offset : offset + length], offset + length


def _pem_to_der(text):
    body = "".join(
        line.strip()
        for line in text.strip().splitlines()
        if line.strip() and not line.strip().startswith("-----")
    )
    return base64.b64decode(body)


def _pkcs1_numbers(der):
    """(n, e, d) from a PKCS#1 RSAPrivateKey: SEQUENCE { version, n, e, d, ... }."""
    tag, seq, _ = _read_tlv(der, 0)
    if tag != 0x30:
        raise ValueError("expected a DER SEQUENCE in the RSA private key")
    _, _, offset = _read_tlv(seq, 0)  # version
    numbers = []
    for _ in range(3):  # modulus, publicExponent, privateExponent
        tag, value, offset = _read_tlv(seq, offset)
        if tag != 0x02:
            raise ValueError("expected a DER INTEGER in the RSA private key")
        numbers.append(int.from_bytes(value, "big"))
    return tuple(numbers)


def _private_numbers(pem_text):
    """(n, e, d) from a PKCS#1 or PKCS#8 RSA private key PEM."""
    der = _pem_to_der(pem_text)
    tag, seq, _ = _read_tlv(der, 0)
    if tag != 0x30:
        raise ValueError("private key does not start with a DER SEQUENCE")
    _, _, offset = _read_tlv(seq, 0)  # version
    tag, value, next_offset = _read_tlv(seq, offset)
    if tag == 0x30:
        # PKCS#8: version, AlgorithmIdentifier, privateKey OCTET STRING
        if RSA_OID not in value:
            raise ValueError("only RSA keys are supported; this PKCS#8 key is not RSA")
        tag, inner, _ = _read_tlv(seq, next_offset)
        if tag != 0x04:
            raise ValueError("unexpected PKCS#8 structure: no privateKey OCTET STRING")
        return _pkcs1_numbers(inner)
    if tag == 0x02:
        # PKCS#1: the integer after the version is the modulus
        return _pkcs1_numbers(der)
    raise ValueError("unrecognized private key format")


# --- tiny DER writer, for the SubjectPublicKeyInfo PEM ----------------------


def _der_len(length):
    if length < 0x80:
        return bytes([length])
    encoded = length.to_bytes((length.bit_length() + 7) // 8, "big")
    return bytes([0x80 | len(encoded)]) + encoded


def _der_tlv(tag, payload):
    return bytes([tag]) + _der_len(len(payload)) + payload


def _der_uint(value):
    encoded = _uint_bytes(value)
    if encoded[0] & 0x80:
        encoded = b"\x00" + encoded
    return _der_tlv(0x02, encoded)


# --- the key ----------------------------------------------------------------


class RSAPrivateKey:
    def __init__(self, n, e, d):
        self.n = n
        self.e = e
        self.d = d

    @classmethod
    def from_pem(cls, pem):
        if isinstance(pem, bytes):
            pem = pem.decode()
        return cls(*_private_numbers(pem))

    @property
    def size_in_bytes(self):
        return (self.n.bit_length() + 7) // 8

    def sign(self, message):
        """RSASSA-PKCS1-v1_5 signature of `message` using SHA-256 (RFC 8017 8.2)."""
        digest_info = SHA256_DIGEST_INFO_PREFIX + hashlib.sha256(message).digest()
        padding_length = self.size_in_bytes - len(digest_info) - 3
        if padding_length < 8:
            raise ValueError("RSA key is too small to sign a SHA-256 digest")
        encoded = b"\x00\x01" + b"\xff" * padding_length + b"\x00" + digest_info
        signature = pow(int.from_bytes(encoded, "big"), self.d, self.n)
        return signature.to_bytes(self.size_in_bytes, "big")

    def public_key_pem(self):
        rsa_public_key = _der_tlv(0x30, _der_uint(self.n) + _der_uint(self.e))
        spki = _der_tlv(
            0x30, RSA_ALGORITHM_IDENTIFIER + _der_tlv(0x03, b"\x00" + rsa_public_key)
        )
        encoded = base64.b64encode(spki).decode()
        wrapped = "\n".join(encoded[i : i + 64] for i in range(0, len(encoded), 64))
        return "-----BEGIN PUBLIC KEY-----\n" + wrapped + "\n-----END PUBLIC KEY-----\n"

    def public_jwk(self, kid, alg="RS256"):
        return {
            "kty": "RSA",
            "alg": alg,
            "use": "sig",
            "kid": kid,
            "n": b64url_encode(_uint_bytes(self.n)),
            "e": b64url_encode(_uint_bytes(self.e)),
        }

    def thumbprint(self):
        """RFC 7638 JWK thumbprint: a key ID that changes whenever the key does."""
        members = {
            "e": b64url_encode(_uint_bytes(self.e)),
            "kty": "RSA",
            "n": b64url_encode(_uint_bytes(self.n)),
        }
        canonical = json.dumps(members, separators=(",", ":"), sort_keys=True)
        return b64url_encode(hashlib.sha256(canonical.encode()).digest())


def encode_jwt(claims, private_key, kid=None):
    """
    Sign `claims` as an RS256 JWT, including "kid" in the header when provided.
    Fence only refreshes an issuer's public keys when the token carries a "kid",
    so without one validation fails with "Public key for issuer <iss> not found."
    """
    header = {"alg": "RS256", "typ": "JWT"}
    if kid:
        header["kid"] = kid
    signing_input = ".".join(
        b64url_encode(json.dumps(part, separators=(",", ":")).encode())
        for part in (header, claims)
    )
    signature = private_key.sign(signing_input.encode())
    return signing_input + "." + b64url_encode(signature)
