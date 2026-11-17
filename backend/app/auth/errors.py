"""Errores de la API con forma {statusCode, code, message}. `detail` repite el mensaje (lo lee el frontend)."""
from __future__ import annotations


class ApiError(Exception):
    def __init__(self, status: int, code: str, message: str, headers: dict[str, str] | None = None):
        super().__init__(message)
        self.status, self.code, self.message, self.headers = status, code, message, headers or {}


def unauthenticated() -> ApiError:
    return ApiError(401, "UNAUTHENTICATED", "Inicia sesión para continuar.")


def forbidden(message: str = "No tienes permiso para esta acción.") -> ApiError:
    return ApiError(403, "FORBIDDEN", message)


def payload(status: int, code: str, message: str) -> dict:
    return {"statusCode": status, "code": code, "message": message, "detail": message}
