"""
GraphQL query resolvers, schema, and FastAPI router.

Strawberry type declarations live in graphql_types.py.
"""

from uuid import UUID

import strawberry
from fastapi import Depends
from sqlalchemy.orm import Session
from strawberry.fastapi import GraphQLRouter
from strawberry_sqlalchemy_mapper import StrawberrySQLAlchemyLoader

from qupboard_graphql.api.graphql_types import HardwareModel, mapper  # noqa: F401 – mapper.finalize() called there
from qupboard_graphql.db.models import HardwareModelORM
from qupboard_graphql.db.session import get_db


async def get_db_context(db: Session = Depends(get_db)):
    return {"db": db, "sqlalchemy_loader": StrawberrySQLAlchemyLoader(bind=db)}


@strawberry.type
class Query:
    @strawberry.field
    def get_calibration(self, info: strawberry.types.Info, id: UUID) -> HardwareModel | None:
        db = info.context["db"]
        return HardwareModelORM.get_by_uuid(db, id)

    @strawberry.field
    def get_all_hardware_model_ids(self, info: strawberry.types.Info) -> list[UUID]:
        db = info.context["db"]
        return HardwareModelORM.get_all_pks(db)

    @strawberry.field
    def get_all_calibrations(self, info: strawberry.types.Info) -> list[HardwareModel]:
        db = info.context["db"]
        return db.query(HardwareModelORM).all()


schema = strawberry.Schema(Query)

graphql_router = GraphQLRouter(schema, context_getter=get_db_context)
