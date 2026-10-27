"""Contraseñas, códigos de 2 pasos y tokens para Orión Equipo. Solo biblioteca estándar.

- Contraseñas (del equipo y la del panel de David): scrypt con sal propia; no se pueden leer.
- Tokens de sesión: se guarda solo su huella HMAC con ORION_EQUIPO_SECRETO.
- Código de 6 dígitos del panel (TOTP, RFC 6238): la clave se guarda tal cual en un archivo que
  solo lee el usuario equipo; es el segundo factor del dueño, igual que en el panel de Hallazgos.
"""
import base64
import hashlib
import hmac
import os
import secrets
import struct
import time

_N, _R, _P = 2 ** 14, 8, 5   # scrypt, parámetros de OWASP


def _secreto():
    return os.environ.get("ORION_EQUIPO_SECRETO", "orion-equipo-sin-secreto").encode()


def cifrar_clave(clave):
    sal = secrets.token_bytes(16)
    h = hashlib.scrypt(clave.encode(), salt=sal, n=_N, r=_R, p=_P, dklen=32)
    return f"scrypt${_N}${_R}${_P}${sal.hex()}${h.hex()}"


def clave_correcta(clave, guardado):
    try:
        _, n, r, p, sal, h = (guardado or "").split("$")
        calc = hashlib.scrypt(clave.encode(), salt=bytes.fromhex(sal), n=int(n), r=int(r), p=int(p),
                              dklen=32, maxmem=64 * 1024 * 1024)
        return hmac.compare_digest(calc.hex(), h)
    except Exception:
        return False


def token():
    return secrets.token_urlsafe(32)


def huella(texto):
    return hmac.new(_secreto(), str(texto).encode(), hashlib.sha256).hexdigest()


# ---------------------------------------------- TOTP (RFC 6238)
def totp_secreto():
    return base64.b32encode(secrets.token_bytes(20)).decode().rstrip("=")


def _totp(secreto, paso):
    llave = base64.b32decode(secreto + "=" * (-len(secreto) % 8))
    h = hmac.new(llave, struct.pack(">Q", paso), hashlib.sha1).digest()
    o = h[-1] & 0x0F
    return f"{(struct.unpack('>I', h[o:o + 4])[0] & 0x7FFFFFFF) % 10 ** 6:06d}"


def totp_correcto(secreto, codigo, ahora=None):
    codigo = "".join(str(codigo or "").split())
    if not secreto or len(codigo) != 6 or not codigo.isdigit():
        return False
    paso = int((ahora or time.time()) // 30)
    return any(hmac.compare_digest(_totp(secreto, paso + d), codigo) for d in (-1, 0, 1))


def otpauth(secreto, cuenta, emisor="Orion Equipo"):
    import urllib.parse
    return "otpauth://totp/" + urllib.parse.quote(f"{emisor}:{cuenta}") + "?" + urllib.parse.urlencode(
        {"secret": secreto, "issuer": emisor, "digits": 6, "period": 30})
