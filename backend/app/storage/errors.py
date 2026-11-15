"""Errores de almacenamiento independientes del proveedor (sin detalles internos del SDK)."""


class StorageError(Exception):
    """Fallo genérico del almacenamiento."""


class StorageNotFound(StorageError):
    pass


class StorageAccessDenied(StorageError):
    pass


class StorageUnavailable(StorageError):
    """Timeout, conexión rechazada o servicio caído."""
