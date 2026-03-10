"""
REST API routes for managing hardware-model calibration records.

Exposes CRUD-style endpoints under the prefix defined by
:data:`~qupboard_graphql.config.Settings.REST_PATH` (default ``/rest``).
"""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, UploadFile
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from qupboard_graphql.db.mapper_from_orm import hardware_model_from_orm
from qupboard_graphql.db.mapper_to_orm import hardware_model_to_orm
from qupboard_graphql.db.models import HardwareModelORM, QubitORM, ResonatorORM
from qupboard_graphql.db.session import get_db
from qupboard_graphql.schemas.hardware_model import HardwareModel


rest_router = APIRouter(tags=["Hardware Models"])


@rest_router.get(
    "/logical-hardware",
    summary="List all hardware model IDs",
    response_description="A list of UUIDs for every stored hardware model",
)
async def get_all_logical_hardware_ids(
    db: AsyncSession = Depends(get_db),
) -> list[UUID]:
    """Return the UUIDs of all hardware models currently stored in the database.

    Args:
        db: An active SQLAlchemy async session injected by :func:`~qupboard_graphql.db.session.get_db`.

    Returns:
        A list of UUIDs, one per stored hardware model.
    """
    return await HardwareModelORM.get_all_pks(db)


@rest_router.get(
    "/logical-hardware/{uuid}",
    summary="Get a hardware model by ID",
    response_description="The hardware model matching the given UUID",
    responses={404: {"description": "Hardware model not found"}},
)
async def get_logical_hardware(
    uuid: UUID,
    db: AsyncSession = Depends(get_db),
) -> HardwareModel:
    """Retrieve a single hardware model by its UUID.

    Args:
        uuid: UUID of the hardware model to retrieve.
        db: An active SQLAlchemy async session injected by :func:`~qupboard_graphql.db.session.get_db`.

    Returns:
        The :class:`~qupboard_graphql.schemas.hardware_model.HardwareModel` matching *uuid*.

    Raises:
        HTTPException: 404 if no hardware model with the given UUID exists.
    """
    orm_obj = await HardwareModelORM.get_by_uuid(
        db,
        uuid,
        load_options=[
            selectinload(HardwareModelORM.qubits).selectinload(QubitORM.physical_channel),
            selectinload(HardwareModelORM.qubits).selectinload(QubitORM.pulse_channels),
            selectinload(HardwareModelORM.qubits)
            .selectinload(QubitORM.resonator)
            .selectinload(ResonatorORM.physical_channel),
            selectinload(HardwareModelORM.qubits)
            .selectinload(QubitORM.resonator)
            .selectinload(ResonatorORM.pulse_channels),
            selectinload(HardwareModelORM.qubits).selectinload(QubitORM.cross_resonance_channels),
            selectinload(HardwareModelORM.qubits).selectinload(QubitORM.cross_resonance_cancellation_channels),
            selectinload(HardwareModelORM.qubits).selectinload(QubitORM.zx_pi_4_comps),
        ],
    )
    if orm_obj is None:
        raise HTTPException(status_code=404, detail=f"HardwareModel {uuid} not found")
    return hardware_model_from_orm(orm_obj)


@rest_router.post(
    "/logical-hardware",
    status_code=201,
    summary="Create a hardware model",
    response_description="The UUID assigned to the newly created hardware model",
    responses={
        409: {"description": "A hardware model with the same unique identifier already exists"},
        415: {"description": "Unsupported file type — only application/json is accepted"},
        422: {"description": "File content could not be parsed as a valid hardware model"},
    },
)
async def create_logical_hardware(
    model: HardwareModel,
    db: AsyncSession = Depends(get_db),
) -> UUID:
    """Persist a new hardware model supplied as a JSON body.

    Args:
        model: A validated :class:`~qupboard_graphql.schemas.hardware_model.HardwareModel`
            instance parsed from the request body.
        db: An active SQLAlchemy async session injected by :func:`~qupboard_graphql.db.session.get_db`.

    Returns:
        The UUID assigned to the newly created hardware model record.

    Raises:
        HTTPException: 409 if a hardware model with the same unique identifier
            already exists.
    """
    orm_obj = hardware_model_to_orm(model)
    db.add(orm_obj)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=409,
            detail="A hardware model with the same unique identifier already exists.",
        )
    return orm_obj.id


@rest_router.post(
    "/logical-hardware/upload",
    status_code=201,
    summary="Upload a hardware model from a file",
    response_description="The UUID assigned to the newly created hardware model",
    responses={
        409: {"description": "A hardware model with the same unique identifier already exists"},
        415: {"description": "Unsupported file type — only application/json is accepted"},
        422: {"description": "File content could not be parsed as a valid hardware model"},
    },
)
async def upload_logical_hardware(
    file: UploadFile,
    db: AsyncSession = Depends(get_db),
) -> UUID:
    """Upload a JSON file containing a hardware model and persist it.

    Args:
        file: A JSON file whose content conforms to the
            :class:`~qupboard_graphql.schemas.hardware_model.HardwareModel` schema.
        db: An active SQLAlchemy async session injected by :func:`~qupboard_graphql.db.session.get_db`.

    Returns:
        The UUID assigned to the newly created hardware model record.

    Raises:
        HTTPException: 415 if the file's content type is not ``application/json``
            or ``text/plain``.
        HTTPException: 422 if the file content cannot be parsed as a valid
            ``HardwareModel``.
        HTTPException: 409 if a hardware model with the same unique identifier
            already exists.
    """
    if file.content_type not in ("application/json", "text/plain"):
        raise HTTPException(
            status_code=415,
            detail=f"Unsupported file type '{file.content_type}'. Expected application/json.",
        )
    raw = await file.read()
    try:
        model = HardwareModel.model_validate_json(raw)
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"Invalid hardware model file: {exc}") from exc
    orm_obj = hardware_model_to_orm(model)
    db.add(orm_obj)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=409,
            detail="A hardware model with the same unique identifier already exists.",
        )
    return orm_obj.id
