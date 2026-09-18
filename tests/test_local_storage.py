"""Tests del almacenamiento local de archivos."""

import pytest

from app.storage.local import LocalFileStorage


def test_roundtrip(tmp_path) -> None:
    storage = LocalFileStorage(tmp_path)
    key = storage.save(b"contenido-secreto", "jpg")
    assert storage.exists(key) is True
    assert storage.load(key) == b"contenido-secreto"


def test_delete(tmp_path) -> None:
    storage = LocalFileStorage(tmp_path)
    key = storage.save(b"x", "png")
    storage.delete(key)
    assert storage.exists(key) is False


def test_unique_keys(tmp_path) -> None:
    storage = LocalFileStorage(tmp_path)
    k1 = storage.save(b"a", "jpg")
    k2 = storage.save(b"b", "jpg")
    assert k1 != k2


def test_path_traversal_rejected(tmp_path) -> None:
    storage = LocalFileStorage(tmp_path)
    with pytest.raises(ValueError):
        storage.load("../etc/passwd")
    with pytest.raises(ValueError):
        storage.delete("../../secret")


def test_invalid_extension_sanitized(tmp_path) -> None:
    storage = LocalFileStorage(tmp_path)
    key = storage.save(b"x", ".JPG")
    assert key.endswith(".jpg")
