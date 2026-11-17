"""Contraseñas con Argon2id. Nunca se guardan ni se registran en claro."""
from __future__ import annotations

import secrets

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError

_ph = PasswordHasher()  # Argon2id con los parámetros recomendados por argon2-cffi
# hash de una contraseña aleatoria: se verifica contra él cuando el correo no existe para igualar tiempos
_DUMMY_HASH = _ph.hash(secrets.token_urlsafe(24))

MIN_LENGTH = 12
MAX_LENGTH = 256  # evita hashear entradas enormes
_TEMP_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnpqrstuvwxyz23456789"


def hash_password(password: str) -> str:
    return _ph.hash(password)


def verify_password(stored_hash: str | None, password: str) -> bool:
    """Verifica en tiempo similar exista o no la cuenta (`stored_hash=None` usa el hash ficticio)."""
    if len(password) > MAX_LENGTH:
        password = password[:MAX_LENGTH]
    try:
        ok = _ph.verify(stored_hash or _DUMMY_HASH, password)
    except (VerificationError, InvalidHashError):
        return False
    return bool(ok) and stored_hash is not None


def needs_rehash(stored_hash: str) -> bool:
    try:
        return _ph.check_needs_rehash(stored_hash)
    except InvalidHashError:
        return False


def policy_error(password: str, email: str = "") -> str | None:
    """Mensaje si la contraseña nueva no cumple la política; None si es válida."""
    if len(password) < MIN_LENGTH:
        return f"La contraseña debe tener al menos {MIN_LENGTH} caracteres."
    if len(password) > MAX_LENGTH:
        return f"La contraseña no puede superar {MAX_LENGTH} caracteres."
    if len(set(password)) < 5:
        return "La contraseña es demasiado repetitiva."
    local = email.split("@")[0].lower()
    if email and (password.lower() == email.lower() or (len(local) >= 4 and local in password.lower())):
        return "La contraseña no puede contener tu correo."
    return None


def temporary_password() -> str:
    """20 caracteres sin ambiguos (0/O, 1/l/I), agrupados para copiarlos con facilidad."""
    raw = "".join(secrets.choice(_TEMP_ALPHABET) for _ in range(20))
    return "-".join(raw[i:i + 5] for i in range(0, 20, 5))
