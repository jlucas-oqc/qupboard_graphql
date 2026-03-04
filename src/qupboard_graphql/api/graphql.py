import json
from uuid import UUID

import strawberry
from fastapi import Depends
from sqlalchemy import Uuid as SaUuid
from sqlalchemy.orm import Session
from strawberry.fastapi import GraphQLRouter
from strawberry_sqlalchemy_mapper import (
    StrawberrySQLAlchemyLoader,
    StrawberrySQLAlchemyMapper,
)

from qupboard_graphql.db.models import (
    CalibratablePulseORM,
    CrossResonanceChannelORM,
    DrivePulseChannelORM,
    HardwareModelORM,
    PhysicalChannelORM,
    QubitORM,
    QubitPulseChannelORM,
    ResonatorORM,
    ResonatorPulseChannelORM,
    ResetPulseChannelORM,
    ZxPi4CompORM,
)
from qupboard_graphql.db.session import get_db


mapper = StrawberrySQLAlchemyMapper(
    extra_sqlalchemy_type_to_strawberry_type_map={SaUuid: UUID},
)


@mapper.type(PhysicalChannelORM)
class PhysicalChannel:
    __exclude__ = ["qubit", "resonator"]


@mapper.type(CalibratablePulseORM)
class CalibratablePulse:
    __exclude__ = []


@mapper.type(DrivePulseChannelORM)
class DrivePulseChannel:
    __exclude__ = ["qubit"]


@mapper.type(QubitPulseChannelORM)
class QubitPulseChannel:
    __exclude__ = ["qubit"]


@mapper.type(CrossResonanceChannelORM)
class CrossResonanceChannel:
    __exclude__ = ["qubit"]


@mapper.type(ResonatorPulseChannelORM)
class ResonatorPulseChannel:
    __exclude__ = ["resonator"]


@mapper.type(ResetPulseChannelORM)
class ResetPulseChannel:
    __exclude__ = ["qubit", "resonator"]


@mapper.type(ZxPi4CompORM)
class ZxPi4Comp:
    __exclude__ = ["qubit"]


@mapper.type(ResonatorORM)
class Resonator:
    __exclude__ = ["qubit"]


@mapper.type(QubitORM)
class Qubit:
    __exclude__ = ["hardware_model"]

    @strawberry.field
    def mean_z_map_args(self) -> list[float]:
        return json.loads(self.mean_z_map_args)  # type: ignore[attr-defined]


@mapper.type(HardwareModelORM)
class HardwareModel:
    pass


mapper.finalize()


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


schema = strawberry.Schema(Query)

graphql_router = GraphQLRouter(schema, context_getter=get_db_context)
