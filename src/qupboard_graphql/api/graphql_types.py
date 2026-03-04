"""
Strawberry GraphQL type declarations, generated from the SQLAlchemy ORM models
via strawberry-sqlalchemy-mapper.

All @mapper.type classes live here so that graphql.py can stay focused on
query resolvers, schema construction, and router wiring.
"""

import json
from uuid import UUID

import strawberry
from sqlalchemy import Uuid as SaUuid
from strawberry_sqlalchemy_mapper import StrawberrySQLAlchemyMapper

from qupboard_graphql.db.models import (
    CalibratablePulseORM,
    CrossResonanceChannelORM,
    HardwareModelORM,
    PhysicalChannelORM,
    PulseChannelORM,
    QubitORM,
    ResonatorORM,
    ZxPi4CompORM,
)

mapper = StrawberrySQLAlchemyMapper(
    extra_sqlalchemy_type_to_strawberry_type_map={SaUuid: UUID},
)


@mapper.type(PhysicalChannelORM)
class PhysicalChannel:
    __exclude__ = ["qubit", "resonator"]


@mapper.type(CalibratablePulseORM)
class CalibratablePulse:
    __exclude__ = []


@mapper.type(PulseChannelORM)
class PulseChannel:
    __exclude__ = []


@mapper.type(CrossResonanceChannelORM)
class CrossResonanceChannel:
    __exclude__ = ["qubit"]


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
