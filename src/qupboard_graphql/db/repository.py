"""
Repository mixin providing generic primary-key query helpers.

Inherit alongside DeclarativeBase to give ORM models ``get_by_uuid`` and
``get_all_pks`` without cluttering the base class itself.
"""

from typing import Self
from uuid import UUID

from sqlalchemy import inspect
from sqlalchemy.orm import Session


class RepositoryMixin:
    @classmethod
    def get_by_uuid(cls, session: Session, uuid: UUID) -> Self | None:
        """Return the row whose primary-key column matches *uuid*, or ``None``."""
        pk_cols = inspect(cls).mapper.primary_key
        if not pk_cols:
            raise TypeError(f"{cls.__name__} has no primary key defined")
        pk_col = pk_cols[0]
        return session.query(cls).filter(pk_col == uuid).one_or_none()

    @classmethod
    def get_all_pks(cls, session: Session) -> list:
        """Return a list of all primary key values for this model's table."""
        pk_cols = inspect(cls).mapper.primary_key
        if not pk_cols:
            raise TypeError(f"{cls.__name__} has no primary key defined")
        pk_col = pk_cols[0]
        return [row[0] for row in session.query(pk_col).all()]
