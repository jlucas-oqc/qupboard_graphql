"""
SQLAlchemy ORM models mirroring the Pydantic HardwareModel schema.

Table hierarchy
---------------
hardware_models
  └─ qubits  (FK → hardware_models)
       ├─ physical_channels          (FK → qubits OR resonators, discriminated by channel_kind)
       │    baseband and IQ-bias columns are inlined here
       ├─ drive_pulse_channels       (FK → qubits)
       │    └─ calibratable_pulses   (owner_uuid + pulse_role = 'drive' | 'drive_x_pi')
       ├─ qubit_pulse_channels_base  (FK → qubits, role = 'second_state' | 'freq_shift')
       │    └─ calibratable_pulses   (pulse_role = 'second_state')
       ├─ reset_pulse_channels       (FK → qubits OR resonators, discriminated by reset_kind)
       │    └─ calibratable_pulses   (pulse_role = 'reset_qubit' | 'reset_resonator')
       ├─ cross_resonance_channels   (FK → qubits, role = 'cr' | 'crc')
       │    └─ calibratable_pulses   (pulse_role = 'cr')
       ├─ zx_pi_4_comps              (FK → qubits, one per CR pair)
       │    └─ calibratable_pulses   (pulse_role = 'zx_precomp' | 'zx_postcomp', nullable)
       │    phase_comp_x_pi_2 inlined on qubits
       └─ resonators                (FK → qubits)
            ├─ physical_channels    (channel_kind='resonator', FK → resonators)
            └─ resonator_pulse_channels_base  (FK → resonators, role = 'measure' | 'acquire')
                 ├─ calibratable_pulses       (pulse_role = 'measure')
                 └─ acquire columns inlined   (delay, width, sync, use_weights on role='acquire' rows)
"""

import math
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from qupboard_graphql.db.database import Base


# ---------------------------------------------------------------------------
# HardwareModel (top-level)
# ---------------------------------------------------------------------------


class HardwareModelORM(Base):
    __tablename__ = "hardware_models"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    version: Mapped[str] = mapped_column(String, nullable=False)
    calibration_id: Mapped[str] = mapped_column(String, nullable=False)
    # logical_connectivity stored as JSON text (dict[str, list[int]])
    logical_connectivity: Mapped[str] = mapped_column(Text, nullable=False)

    qubits: Mapped[list["QubitORM"]] = relationship(back_populates="hardware_model", cascade="all, delete-orphan")


# ---------------------------------------------------------------------------
# PhysicalChannel  (unified – qubit and resonator, discriminated by channel_kind)
# Baseband and IQVoltageBias fields are inlined here (both are always 1-to-1).
# ---------------------------------------------------------------------------


class PhysicalChannelORM(Base):
    """Covers both qubit PhysicalChannel and resonator PhysicalChannel.

    channel_kind: 'qubit' | 'resonator'
    swap_readout_iq is only meaningful when channel_kind == 'resonator'.
    Exactly one of qubit_uuid / resonator_uuid will be non-NULL per row.

    BaseBand fields (baseband_uuid, baseband_frequency, baseband_if_frequency) and
    IQVoltageBias field (iq_bias) are stored as inline columns rather than
    separate tables, since both are always present and always 1-to-1.
    """

    __tablename__ = "physical_channels"

    uuid: Mapped[UUID] = mapped_column(primary_key=True)
    channel_kind: Mapped[str] = mapped_column(String, nullable=False)  # 'qubit' | 'resonator'
    name_index: Mapped[int] = mapped_column(Integer, nullable=False)
    block_size: Mapped[int] = mapped_column(Integer, nullable=False)
    default_amplitude: Mapped[int] = mapped_column(Integer, nullable=False)
    switch_box: Mapped[str] = mapped_column(String, nullable=False)
    swap_readout_iq: Mapped[bool] = mapped_column(Boolean, default=False)

    # Inlined BaseBand
    baseband_uuid: Mapped[UUID] = mapped_column(nullable=False)
    baseband_frequency: Mapped[float | None] = mapped_column(Float, nullable=True, default=None)
    baseband_if_frequency: Mapped[float | None] = mapped_column(Float, nullable=True, default=None)

    # Inlined IQVoltageBias
    iq_bias: Mapped[str] = mapped_column(String, nullable=False)

    qubit_uuid: Mapped[UUID | None] = mapped_column(ForeignKey("qubits.uuid"), nullable=True)
    qubit: Mapped["QubitORM | None"] = relationship(back_populates="physical_channel")

    resonator_uuid: Mapped[UUID | None] = mapped_column(ForeignKey("resonators.uuid"), nullable=True)
    resonator: Mapped["ResonatorORM | None"] = relationship(back_populates="physical_channel")


# ---------------------------------------------------------------------------
# CalibratablePulse
#
# pulse_role discriminator values:
#   'drive'            – DrivePulseChannelORM.pulse
#   'drive_x_pi'       – DrivePulseChannelORM.pulse_x_pi
#   'second_state'     – QubitPulseChannelORM.pulse  (role='second_state')
#   'cr'               – CrossResonanceChannelORM.zx_pi_4_pulse
#   'measure'          – ResonatorPulseChannelORM.pulse
#   'reset_qubit'      – ResetPulseChannelORM.pulse  (reset_kind='qubit')
#   'reset_resonator'  – ResetPulseChannelORM.pulse  (reset_kind='resonator')
#   'zx_precomp'       – ZxPi4CompORM.pulse_precomp
#   'zx_postcomp'      – ZxPi4CompORM.pulse_postcomp
# ---------------------------------------------------------------------------


class CalibratablePulseORM(Base):
    __tablename__ = "calibratable_pulses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    waveform_type: Mapped[str] = mapped_column(String, nullable=False)
    width: Mapped[float] = mapped_column(Float, nullable=False)
    amp: Mapped[float] = mapped_column(Float, default=0.25 / (100e-9 * 1.0 / 3.0 * math.pi**0.5))
    phase: Mapped[float] = mapped_column(Float, default=0.0)
    drag: Mapped[float] = mapped_column(Float, default=0.0)
    rise: Mapped[float] = mapped_column(Float, default=1.0 / 3.0)
    amp_setup: Mapped[float] = mapped_column(Float, default=0.0)
    std_dev: Mapped[float] = mapped_column(Float, default=0.0)

    # Single generic FK + role discriminator replaces the previous 8 nullable FKs.
    # owner_uuid points at the PK of whichever parent table owns this pulse.
    # No DB-level FK constraint is declared here; referential integrity is
    # enforced by the application layer.
    owner_uuid: Mapped[UUID] = mapped_column(nullable=False)
    pulse_role: Mapped[str] = mapped_column(String, nullable=False)


# ---------------------------------------------------------------------------
# DrivePulseChannel  (FK directly to qubits)
# ---------------------------------------------------------------------------


_PULSE_OVERLAPS = "pulse,pulse_x_pi,zx_pi_4_pulse,pulse_precomp,pulse_postcomp"


class DrivePulseChannelORM(Base):
    __tablename__ = "drive_pulse_channels"

    uuid: Mapped[UUID] = mapped_column(primary_key=True)
    frequency: Mapped[float | None] = mapped_column(Float, nullable=True, default=None)
    imbalance: Mapped[float] = mapped_column(Float, default=1.0)
    phase_iq_offset: Mapped[float] = mapped_column(Float, default=0.0)
    scale_real: Mapped[float] = mapped_column(Float, default=1.0)
    scale_imag: Mapped[float] = mapped_column(Float, default=0.0)

    qubit_uuid: Mapped[UUID | None] = mapped_column(ForeignKey("qubits.uuid"), nullable=True)
    qubit: Mapped["QubitORM | None"] = relationship(back_populates="drive_pulse_channel")

    pulse: Mapped["CalibratablePulseORM | None"] = relationship(
        primaryjoin="and_(CalibratablePulseORM.owner_uuid == DrivePulseChannelORM.uuid,"
        " CalibratablePulseORM.pulse_role == 'drive')",
        foreign_keys="CalibratablePulseORM.owner_uuid",
        cascade="all, delete-orphan",
        uselist=False,
        overlaps=_PULSE_OVERLAPS,
    )
    pulse_x_pi: Mapped["CalibratablePulseORM | None"] = relationship(
        primaryjoin="and_(CalibratablePulseORM.owner_uuid == DrivePulseChannelORM.uuid,"
        " CalibratablePulseORM.pulse_role == 'drive_x_pi')",
        foreign_keys="CalibratablePulseORM.owner_uuid",
        cascade="all, delete-orphan",
        uselist=False,
        overlaps=_PULSE_OVERLAPS,
    )


# ---------------------------------------------------------------------------
# QubitPulseChannel  (second_state / freq_shift – FK directly to qubits)
# ---------------------------------------------------------------------------


class QubitPulseChannelORM(Base):
    """Covers QubitPulseChannel / SecondStatePulseChannel / FreqShiftPulseChannel."""

    __tablename__ = "qubit_pulse_channels_base"

    uuid: Mapped[UUID] = mapped_column(primary_key=True)
    role: Mapped[str] = mapped_column(String, nullable=False)  # 'second_state' | 'freq_shift'
    frequency: Mapped[float | None] = mapped_column(Float, nullable=True, default=None)
    imbalance: Mapped[float] = mapped_column(Float, default=1.0)
    phase_iq_offset: Mapped[float] = mapped_column(Float, default=0.0)
    scale_real: Mapped[float] = mapped_column(Float, default=1.0)
    scale_imag: Mapped[float] = mapped_column(Float, default=0.0)
    # SecondStatePulseChannel extras
    ss_active: Mapped[bool] = mapped_column(Boolean, default=False)
    ss_delay: Mapped[float] = mapped_column(Float, default=0.0)
    # FreqShiftPulseChannel extras
    fs_active: Mapped[bool] = mapped_column(Boolean, default=False)
    fs_amp: Mapped[float] = mapped_column(Float, default=1.0)
    fs_phase: Mapped[float] = mapped_column(Float, default=0.0)

    qubit_uuid: Mapped[UUID | None] = mapped_column(ForeignKey("qubits.uuid"), nullable=True)

    pulse: Mapped["CalibratablePulseORM | None"] = relationship(
        primaryjoin="and_(CalibratablePulseORM.owner_uuid == QubitPulseChannelORM.uuid,"
        " CalibratablePulseORM.pulse_role == 'second_state')",
        foreign_keys="CalibratablePulseORM.owner_uuid",
        cascade="all, delete-orphan",
        uselist=False,
        overlaps=_PULSE_OVERLAPS,
    )


# ---------------------------------------------------------------------------
# CrossResonanceChannel  (unified – CR and CRC, discriminated by role)
# ---------------------------------------------------------------------------


class CrossResonanceChannelORM(Base):
    """Covers both CrossResonancePulseChannel and CrossResonanceCancellationPulseChannel.

    role: 'cr' | 'crc'
    zx_pi_4_pulse is only populated when role == 'cr'.
    """

    __tablename__ = "cross_resonance_channels"

    uuid: Mapped[UUID] = mapped_column(primary_key=True)
    role: Mapped[str] = mapped_column(String, nullable=False)  # 'cr' | 'crc'
    auxiliary_qubit: Mapped[int] = mapped_column(Integer, nullable=False)
    frequency: Mapped[float | None] = mapped_column(Float, nullable=True, default=None)
    imbalance: Mapped[float] = mapped_column(Float, default=1.0)
    phase_iq_offset: Mapped[float] = mapped_column(Float, default=0.0)
    scale_real: Mapped[float] = mapped_column(Float, default=1.0)
    scale_imag: Mapped[float] = mapped_column(Float, default=0.0)

    qubit_uuid: Mapped[UUID | None] = mapped_column(ForeignKey("qubits.uuid"), nullable=True)
    qubit: Mapped["QubitORM | None"] = relationship(
        foreign_keys=[qubit_uuid],
        overlaps="cross_resonance_channels,cross_resonance_cancellation_channels",
    )

    zx_pi_4_pulse: Mapped["CalibratablePulseORM | None"] = relationship(
        primaryjoin="and_(CalibratablePulseORM.owner_uuid == CrossResonanceChannelORM.uuid,"
        " CalibratablePulseORM.pulse_role == 'cr')",
        foreign_keys="CalibratablePulseORM.owner_uuid",
        cascade="all, delete-orphan",
        uselist=False,
        overlaps=_PULSE_OVERLAPS,
    )


# ---------------------------------------------------------------------------
# ResonatorPulseChannel  (measure / acquire – FK directly to resonators)
# Acquire fields (acq_delay, acq_width, acq_sync, acq_use_weights) are inlined
# here rather than in a separate table, since they are always 1-to-1.
# ---------------------------------------------------------------------------


class ResonatorPulseChannelORM(Base):
    """Covers both MeasurePulseChannel and AcquirePulseChannel.

    role: 'measure' | 'acquire'
    pulse is only populated when role == 'measure'.
    acq_* columns are only meaningful when role == 'acquire'.
    """

    __tablename__ = "resonator_pulse_channels_base"

    uuid: Mapped[UUID] = mapped_column(primary_key=True)
    role: Mapped[str] = mapped_column(String, nullable=False)  # 'measure' | 'acquire'
    frequency: Mapped[float | None] = mapped_column(Float, nullable=True, default=None)
    imbalance: Mapped[float] = mapped_column(Float, default=1.0)
    phase_iq_offset: Mapped[float] = mapped_column(Float, default=0.0)
    scale_real: Mapped[float] = mapped_column(Float, default=1.0)
    scale_imag: Mapped[float] = mapped_column(Float, default=0.0)

    # Inlined CalibratableAcquire (only meaningful when role == 'acquire')
    acq_delay: Mapped[float | None] = mapped_column(Float, nullable=True, default=None)
    acq_width: Mapped[float | None] = mapped_column(Float, nullable=True, default=None)
    acq_sync: Mapped[bool | None] = mapped_column(Boolean, nullable=True, default=None)
    acq_use_weights: Mapped[bool | None] = mapped_column(Boolean, nullable=True, default=None)

    resonator_uuid: Mapped[UUID | None] = mapped_column(ForeignKey("resonators.uuid"), nullable=True)

    pulse: Mapped["CalibratablePulseORM | None"] = relationship(
        primaryjoin="and_(CalibratablePulseORM.owner_uuid == ResonatorPulseChannelORM.uuid,"
        " CalibratablePulseORM.pulse_role == 'measure')",
        foreign_keys="CalibratablePulseORM.owner_uuid",
        cascade="all, delete-orphan",
        uselist=False,
        overlaps=_PULSE_OVERLAPS,
    )


# ---------------------------------------------------------------------------
# ResetPulseChannel  (qubit reset and resonator reset, discriminated by reset_kind)
# ---------------------------------------------------------------------------


class ResetPulseChannelORM(Base):
    """Covers qubit-side and resonator-side reset pulse channels.

    reset_kind: 'qubit' | 'resonator'
    Exactly one of qubit_uuid / resonator_uuid will be non-NULL per row.
    """

    __tablename__ = "reset_pulse_channels"

    uuid: Mapped[UUID] = mapped_column(primary_key=True)
    reset_kind: Mapped[str] = mapped_column(String, nullable=False)  # 'qubit' | 'resonator'
    frequency: Mapped[float | None] = mapped_column(Float, nullable=True, default=None)
    imbalance: Mapped[float] = mapped_column(Float, default=1.0)
    phase_iq_offset: Mapped[float] = mapped_column(Float, default=0.0)
    scale_real: Mapped[float] = mapped_column(Float, default=1.0)
    scale_imag: Mapped[float] = mapped_column(Float, default=0.0)
    delay: Mapped[float] = mapped_column(Float, default=0.0)

    qubit_uuid: Mapped[UUID | None] = mapped_column(ForeignKey("qubits.uuid"), nullable=True)
    qubit: Mapped["QubitORM | None"] = relationship(back_populates="reset_pulse_channel")

    resonator_uuid: Mapped[UUID | None] = mapped_column(ForeignKey("resonators.uuid"), nullable=True)
    resonator: Mapped["ResonatorORM | None"] = relationship(back_populates="reset_pulse_channel")

    pulse: Mapped["CalibratablePulseORM | None"] = relationship(
        primaryjoin="and_(CalibratablePulseORM.owner_uuid == ResetPulseChannelORM.uuid,"
        " CalibratablePulseORM.pulse_role.in_(['reset_qubit', 'reset_resonator']))",
        foreign_keys="CalibratablePulseORM.owner_uuid",
        cascade="all, delete-orphan",
        uselist=False,
        overlaps=_PULSE_OVERLAPS,
    )


# ---------------------------------------------------------------------------
# ZxPi4Comp  (one per CR pair, keyed by auxiliary_qubit)
# ---------------------------------------------------------------------------


class ZxPi4CompORM(Base):
    __tablename__ = "zx_pi_4_comps"

    uuid: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    auxiliary_qubit: Mapped[int] = mapped_column(Integer, nullable=False)
    phase_comp_target_zx_pi_4: Mapped[float] = mapped_column(Float, default=0.0)
    pulse_zx_pi_4_target_rotary_amp: Mapped[float | None] = mapped_column(Float, nullable=True, default=None)
    precomp_active: Mapped[bool] = mapped_column(Boolean, default=False)
    postcomp_active: Mapped[bool] = mapped_column(Boolean, default=False)
    use_second_state: Mapped[bool] = mapped_column(Boolean, default=False)
    use_rotary: Mapped[bool] = mapped_column(Boolean, default=False)

    qubit_uuid: Mapped[UUID | None] = mapped_column(ForeignKey("qubits.uuid"), nullable=True)
    qubit: Mapped["QubitORM | None"] = relationship(back_populates="zx_pi_4_comps")

    pulse_precomp: Mapped["CalibratablePulseORM | None"] = relationship(
        primaryjoin="and_(CalibratablePulseORM.owner_uuid == ZxPi4CompORM.uuid,"
        " CalibratablePulseORM.pulse_role == 'zx_precomp')",
        foreign_keys="CalibratablePulseORM.owner_uuid",
        cascade="all, delete-orphan",
        uselist=False,
        overlaps=_PULSE_OVERLAPS,
    )
    pulse_postcomp: Mapped["CalibratablePulseORM | None"] = relationship(
        primaryjoin="and_(CalibratablePulseORM.owner_uuid == ZxPi4CompORM.uuid,"
        " CalibratablePulseORM.pulse_role == 'zx_postcomp')",
        foreign_keys="CalibratablePulseORM.owner_uuid",
        cascade="all, delete-orphan",
        uselist=False,
        overlaps=_PULSE_OVERLAPS,
    )


# ---------------------------------------------------------------------------
# Resonator
# ---------------------------------------------------------------------------


class ResonatorORM(Base):
    __tablename__ = "resonators"

    uuid: Mapped[UUID] = mapped_column(primary_key=True)

    qubit_uuid: Mapped[UUID | None] = mapped_column(ForeignKey("qubits.uuid"), nullable=True)
    qubit: Mapped["QubitORM | None"] = relationship(back_populates="resonator")

    physical_channel: Mapped["PhysicalChannelORM | None"] = relationship(
        back_populates="resonator", cascade="all, delete-orphan", uselist=False
    )
    measure_pulse_channel: Mapped["ResonatorPulseChannelORM | None"] = relationship(
        primaryjoin=(
            "and_(ResonatorPulseChannelORM.resonator_uuid == ResonatorORM.uuid,"
            " ResonatorPulseChannelORM.role == 'measure')"
        ),
        foreign_keys="ResonatorPulseChannelORM.resonator_uuid",
        cascade="all, delete-orphan",
        uselist=False,
        viewonly=False,
        overlaps="acquire_pulse_channel,resonator",
    )
    acquire_pulse_channel: Mapped["ResonatorPulseChannelORM | None"] = relationship(
        primaryjoin=(
            "and_(ResonatorPulseChannelORM.resonator_uuid == ResonatorORM.uuid,"
            " ResonatorPulseChannelORM.role == 'acquire')"
        ),
        foreign_keys="ResonatorPulseChannelORM.resonator_uuid",
        cascade="all, delete-orphan",
        uselist=False,
        viewonly=False,
        overlaps="measure_pulse_channel,resonator",
    )
    reset_pulse_channel: Mapped["ResetPulseChannelORM | None"] = relationship(
        back_populates="resonator",
        cascade="all, delete-orphan",
        uselist=False,
    )


# ---------------------------------------------------------------------------
# Qubit
# ---------------------------------------------------------------------------


class QubitORM(Base):
    __tablename__ = "qubits"

    uuid: Mapped[UUID] = mapped_column(primary_key=True)
    # qubit index key within the hardware model (e.g. "0", "1")
    qubit_key: Mapped[str] = mapped_column(String, nullable=False)
    mean_z_map_args: Mapped[str] = mapped_column(Text, nullable=False)  # JSON [real, imag]
    discriminator_real: Mapped[float] = mapped_column(Float, default=0.0)
    discriminator_imag: Mapped[float] = mapped_column(Float, default=0.0)
    direct_x_pi: Mapped[bool] = mapped_column(Boolean, default=False)
    # Inlined XPi2Comp (always 1-to-1, single data column)
    phase_comp_x_pi_2: Mapped[float] = mapped_column(Float, default=0.0)

    hardware_model_id: Mapped[UUID | None] = mapped_column(ForeignKey("hardware_models.id"), nullable=True)
    hardware_model: Mapped["HardwareModelORM | None"] = relationship(back_populates="qubits")

    physical_channel: Mapped["PhysicalChannelORM | None"] = relationship(
        back_populates="qubit", cascade="all, delete-orphan", uselist=False
    )
    drive_pulse_channel: Mapped["DrivePulseChannelORM | None"] = relationship(
        back_populates="qubit", cascade="all, delete-orphan", uselist=False
    )
    second_state_pulse_channel: Mapped["QubitPulseChannelORM | None"] = relationship(
        primaryjoin=(
            "and_(QubitPulseChannelORM.qubit_uuid == QubitORM.uuid, QubitPulseChannelORM.role == 'second_state')"
        ),
        foreign_keys="QubitPulseChannelORM.qubit_uuid",
        cascade="all, delete-orphan",
        uselist=False,
        viewonly=False,
        overlaps="freq_shift_pulse_channel",
    )
    freq_shift_pulse_channel: Mapped["QubitPulseChannelORM | None"] = relationship(
        primaryjoin=(
            "and_(QubitPulseChannelORM.qubit_uuid == QubitORM.uuid, QubitPulseChannelORM.role == 'freq_shift')"
        ),
        foreign_keys="QubitPulseChannelORM.qubit_uuid",
        cascade="all, delete-orphan",
        uselist=False,
        viewonly=False,
        overlaps="second_state_pulse_channel",
    )
    reset_pulse_channel: Mapped["ResetPulseChannelORM | None"] = relationship(
        back_populates="qubit",
        cascade="all, delete-orphan",
        uselist=False,
    )
    resonator: Mapped["ResonatorORM | None"] = relationship(
        back_populates="qubit", cascade="all, delete-orphan", uselist=False
    )
    cross_resonance_channels: Mapped[list["CrossResonanceChannelORM"]] = relationship(
        cascade="all, delete-orphan",
        primaryjoin=(
            "and_(CrossResonanceChannelORM.qubit_uuid == QubitORM.uuid, CrossResonanceChannelORM.role == 'cr')"
        ),
        foreign_keys="CrossResonanceChannelORM.qubit_uuid",
        viewonly=False,
        overlaps="cross_resonance_cancellation_channels,qubit",
    )
    cross_resonance_cancellation_channels: Mapped[list["CrossResonanceChannelORM"]] = relationship(
        cascade="all, delete-orphan",
        primaryjoin=(
            "and_(CrossResonanceChannelORM.qubit_uuid == QubitORM.uuid, CrossResonanceChannelORM.role == 'crc')"
        ),
        foreign_keys="CrossResonanceChannelORM.qubit_uuid",
        viewonly=False,
        overlaps="cross_resonance_channels,qubit",
    )
    zx_pi_4_comps: Mapped[list["ZxPi4CompORM"]] = relationship(back_populates="qubit", cascade="all, delete-orphan")
