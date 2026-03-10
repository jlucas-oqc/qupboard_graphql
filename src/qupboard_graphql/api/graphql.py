"""
GraphQL query resolvers, schema, and FastAPI router.

Strawberry type declarations live in graphql_types.py.
"""

from contextlib import asynccontextmanager
from typing import Optional
from uuid import UUID

import strawberry
from fastapi import Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from strawberry.fastapi import GraphQLRouter
from strawberry_sqlalchemy_mapper import StrawberrySQLAlchemyLoader

from qupboard_graphql.api.graphql_types import HardwareModel, mapper  # noqa: F401 – mapper.finalize() called there
from qupboard_graphql.db.models import HardwareModelORM
from qupboard_graphql.db.session import get_db

# Reuse the relay ListConnection type the mapper generates for relationship fields,
# ensuring getAllCalibrations uses an identical connection shape to e.g. qubits.
HardwareModelConnection = mapper._connection_type_for("HardwareModel")


async def get_db_context(db: AsyncSession = Depends(get_db)) -> dict:
    """FastAPI dependency that builds the Strawberry request context.

    Provides a SQLAlchemy async session and a :class:`StrawberrySQLAlchemyLoader`
    to all GraphQL resolvers via ``info.context``.

    Args:
        db: An active SQLAlchemy async session injected by :func:`get_db`.

    Returns:
        A dictionary with ``"db"`` and ``"sqlalchemy_loader"`` keys.
    """

    @asynccontextmanager
    async def _same_session():
        # Reuse the request-scoped session so the loader queries the same
        # connection/transaction as the root resolvers (critical for in-memory
        # test databases and for transactional consistency in production).
        yield db

    return {"db": db, "sqlalchemy_loader": StrawberrySQLAlchemyLoader(async_bind_factory=_same_session)}


@strawberry.type
class Query:
    """Root GraphQL query type exposing hardware-model calibration data."""

    @strawberry.field
    async def get_calibration(self, info: strawberry.types.Info, id: UUID) -> HardwareModel | None:
        """Retrieve a single hardware model by its UUID.

        Args:
            info: Strawberry resolver context carrying the database session.
            id: UUID of the hardware model to retrieve.

        Returns:
            The matching :class:`HardwareModel` GraphQL object, or ``None``
            if no record with the given UUID exists.
        """
        db = info.context["db"]
        return await HardwareModelORM.get_by_uuid(db, id)

    @strawberry.field
    async def get_all_hardware_model_ids(self, info: strawberry.types.Info) -> list[UUID]:
        """Return the UUIDs of all hardware models stored in the database.

        Args:
            info: Strawberry resolver context carrying the database session.

        Returns:
            A list of UUIDs, one per stored hardware model.
        """
        db = info.context["db"]
        return await HardwareModelORM.get_all_pks(db)

    @strawberry.field
    async def get_all_calibrations(
        self,
        info: strawberry.types.Info,
        first: Optional[int] = None,
        after: Optional[str] = None,
        last: Optional[int] = None,
        before: Optional[str] = None,
    ) -> HardwareModelConnection:
        """Return a paginated connection of all hardware models in the database.

        Supports relay-style cursor pagination via ``first``/``after`` (forward)
        and ``last``/``before`` (backward), with ``pageInfo`` and per-edge cursors,
        matching the connection shape used by relationship fields such as ``qubits``.

        Args:
            info: Strawberry resolver context carrying the database session.
            first: Return the first *n* records after ``after``.
            after: Cursor from a previous ``endCursor`` — start after this position.
            last: Return the last *n* records before ``before``.
            before: Cursor from a previous ``startCursor`` — end before this position.

        Returns:
            A :class:`HardwareModelConnection` containing ``edges``, per-edge
            ``cursor`` values, and a ``pageInfo`` block.
        """
        db = info.context["db"]
        # Pass the Query object — resolve_connection slices it as nodes[start:overfetch],
        # which SQLAlchemy translates to LIMIT/OFFSET SQL rather than fetching all rows.
        result = await db.execute(select(HardwareModelORM))
        nodes = result.scalars().all()
        return HardwareModelConnection.resolve_connection(
            nodes,
            info=info,
            first=first,
            after=after,
            last=last,
            before=before,
        )


schema = strawberry.Schema(Query)

graphql_router = GraphQLRouter(schema, context_getter=get_db_context)
