"""
Repository mixin providing generic primary-key query helpers.

Inherit alongside DeclarativeBase to give ORM models ``get_by_uuid`` and
``get_all_pks`` without cluttering the base class itself.
"""

from typing import Self
from uuid import UUID

from sqlalchemy import inspect, select
from sqlalchemy.orm import Load
from sqlalchemy.ext.asyncio import AsyncSession


class RepositoryMixin:
    """Mixin that adds common primary-key query helpers to SQLAlchemy ORM models.

    Classes that inherit from both :class:`RepositoryMixin` and SQLAlchemy's
    :class:`~sqlalchemy.orm.DeclarativeBase` gain :meth:`get_by_uuid` and
    :meth:`get_all_pks` as class-level helpers without needing a separate
    repository object.
    """

    @classmethod
    async def get_by_uuid(
        cls,
        session: AsyncSession,
        uuid: UUID,
        load_options: list[Load] | None = None,
    ) -> Self | None:
        """Return the row whose primary-key column matches *uuid*.

        Args:
            session: An active SQLAlchemy async session.
            uuid: The primary-key value to look up.
            load_options: Optional list of SQLAlchemy loader options (e.g.
                ``selectinload``) to apply to the query for eager loading.

        Returns:
            The matching ORM instance, or ``None`` if no row is found.

        Raises:
            TypeError: If the model class has no primary key defined.
        """
        pk_cols = inspect(cls).mapper.primary_key
        if not pk_cols:
            raise TypeError(f"{cls.__name__} has no primary key defined")
        pk_col = pk_cols[0]
        stmt = select(cls).where(pk_col == uuid)
        if load_options:
            stmt = stmt.options(*load_options)
        result = await session.execute(stmt)
        return result.scalars().one_or_none()

    @classmethod
    async def get_all_pks(cls, session: AsyncSession) -> list:
        """Return a list of all primary key values for this model's table.

        Args:
            session: An active SQLAlchemy async session.

        Returns:
            A list containing every primary key value in the table, in
            database-defined order.

        Raises:
            TypeError: If the model class has no primary key defined.
        """
        pk_cols = inspect(cls).mapper.primary_key
        if not pk_cols:
            raise TypeError(f"{cls.__name__} has no primary key defined")
        pk_col = pk_cols[0]
        result = await session.execute(select(pk_col))
        return list(result.scalars().all())
