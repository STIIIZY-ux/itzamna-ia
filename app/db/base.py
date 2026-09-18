"""Base declarativa y convenciones de nombres para SQLAlchemy."""

from enum import Enum
from typing import TypeVar

from sqlalchemy import MetaData
from sqlalchemy.orm import DeclarativeBase

NAMING_CONVENTION: dict[str, str] = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(column_0_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}

_EnumT = TypeVar("_EnumT", bound=Enum)


def enum_values(enum_cls: type[_EnumT]) -> list[str]:
    """Devuelve los ``.value`` de un enum para usar en ``values_callable``.

    Así SQLAlchemy persiste el valor (minúsculas) y no el nombre del miembro.
    """
    return [member.value for member in enum_cls]


class Base(DeclarativeBase):
    """Base declarativa común a todos los modelos."""

    metadata = MetaData(naming_convention=NAMING_CONVENTION)

