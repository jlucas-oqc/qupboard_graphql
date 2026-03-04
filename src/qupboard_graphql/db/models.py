"""
SQLAlchemy ORM models mirroring the Pydantic HardwareModel schema.

Table hierarchy
---------------
hardware_models
  └─ qubits  (FK → hardware_models)
       ├─ physical_channels          (FK → qubits OR resonators, discriminated by channel_kind)
       │    baseband and IQ-bias columns are inlined here
       ├─ drive_pulse_channels       (FK → qubits)
       │    └─ calibratable_pulses   (pulse / pulse_x_pi)
       ├─ qubit_pulse_channels_base  (FK → qubits, role = 'second_state' | 'freq_shift')
       │    └─ calibratable_pulses   (second_state pulse only)
       ├─ reset_pulse_channels       (FK → qubits OR resonators, discriminated by reset_kind)
       │    └─ calibratable_pulses
       ├─ cross_resonance_channels   (FK → qubits, role = 'cr' | 'crc')
       │    └─ calibratable_pulses   (role='cr' rows only)
       ├─ x_pi_2_comps               (FK → qubits, one per qubit)
       ├─ zx_pi_4_comps              (FK → qubits, one per CR pair)
       │    └─ calibratable_pulses   (precomp / postcomp, nullable)
       └─ resonators                (FK → qubits)
            ├─ physical_channels    (channel_kind='resonator', FK → resonators)
            └─ resonator_pulse_channels_base  (FK → resonators, role = 'measure' | 'acquire')
                 ├─ calibratable_pulses       (role='measure' rows only)
                 └─ calibratable_acquires     (role='acquire' rows only)
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
# CalibratablePulse  (generic – used by DrivePulseChannel & CR channels)
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

    # FK back to owning row – only one will be non-NULL per row
    drive_pulse_channel_uuid: Mapped[UUID | None] = mapped_column(
        ForeignKey("drive_pulse_channels.uuid"), nullable=True
    )
    drive_pulse_channel_pulse_x_pi_uuid: Mapped[UUID | None] = mapped_column(
        ForeignKey("drive_pulse_channels.uuid"),
        nullable=True,
    )
    second_state_pulse_channel_uuid: Mapped[UUID | None] = mapped_column(
        ForeignKey("qubit_pulse_channels_base.uuid"),
        nullable=True,
    )
    cr_channel_uuid: Mapped[UUID | None] = mapped_column(
        ForeignKey("cross_resonance_channels.uuid"),
        nullable=True,
    )
    measure_pulse_channel_uuid: Mapped[UUID | None] = mapped_column(
        ForeignKey("resonator_pulse_channels_base.uuid"),
        nullable=True,
    )
    reset_pulse_channel_uuid: Mapped[UUID | None] = mapped_column(
        ForeignKey("reset_pulse_channels.uuid"),
        nullable=True,
    )
    zx_pi_4_comp_precomp_uuid: Mapped[UUID | None] = mapped_column(
        ForeignKey("zx_pi_4_comps.uuid"),
        nullable=True,
    )
    zx_pi_4_comp_postcomp_uuid: Mapped[UUID | None] = mapped_column(
        ForeignKey("zx_pi_4_comps.uuid"),
        nullable=True,
    )

    drive_pulse_channel: Mapped["DrivePulseChannelORM | None"] = relationship(
        back_populates="pulse",
        foreign_keys=[drive_pulse_channel_uuid],
    )
    drive_pulse_channel_x_pi: Mapped["DrivePulseChannelORM | None"] = relationship(
        back_populates="pulse_x_pi",
        foreign_keys=[drive_pulse_channel_pulse_x_pi_uuid],
    )
    second_state_pulse_channel: Mapped["QubitPulseChannelORM | None"] = relationship(
        back_populates="pulse",
        foreign_keys=[second_state_pulse_channel_uuid],
    )
    cr_channel: Mapped["CrossResonanceChannelORM | None"] = relationship(
        back_populates="zx_pi_4_pulse",
        foreign_keys=[cr_channel_uuid],
    )
    measure_pulse_channel: Mapped["ResonatorPulseChannelORM | None"] = relationship(
        back_populates="pulse",
        foreign_keys=[measure_pulse_channel_uuid],
    )
    reset_pulse_channel: Mapped["ResetPulseChannelORM | None"] = relationship(
        back_populates="pulse",
        foreign_keys=[reset_pulse_channel_uuid],
    )
    zx_pi_4_comp_precomp: Mapped["ZxPi4CompORM | None"] = relationship(
        back_populates="pulse_precomp",
        foreign_keys=[zx_pi_4_comp_precomp_uuid],
        overlaps="zx_pi_4_comp_postcomp",
    )
    zx_pi_4_comp_postcomp: Mapped["ZxPi4CompORM | None"] = relationship(
        back_populates="pulse_postcomp",
        foreign_keys=[zx_pi_4_comp_postcomp_uuid],
        overlaps="zx_pi_4_comp_precomp",
    )


# ---------------------------------------------------------------------------
# DrivePulseChannel  (FK directly to qubits)
# ---------------------------------------------------------------------------


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
        back_populates="drive_pulse_channel",
        foreign_keys=[CalibratablePulseORM.drive_pulse_channel_uuid],
        cascade="all, delete-orphan",
        uselist=False,
    )
    pulse_x_pi: Mapped["CalibratablePulseORM | None"] = relationship(
        back_populates="drive_pulse_channel_x_pi",
        foreign_keys=[CalibratablePulseORM.drive_pulse_channel_pulse_x_pi_uuid],
        cascade="all, delete-orphan",
        uselist=False,
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
        back_populates="second_state_pulse_channel",
        foreign_keys="CalibratablePulseORM.second_state_pulse_channel_uuid",
        cascade="all, delete-orphan",
        uselist=False,
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
        back_populates="cr_channel",
        foreign_keys=[CalibratablePulseORM.cr_channel_uuid],
        cascade="all, delete-orphan",
        uselist=False,
    )


# ---------------------------------------------------------------------------
# CalibratableAcquire
# ---------------------------------------------------------------------------


class CalibratableAcquireORM(Base):
    __tablename__ = "calibratable_acquires"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    delay: Mapped[float] = mapped_column(Float, default=180e-8)
    width: Mapped[float] = mapped_column(Float, default=1e-6)
    sync: Mapped[bool] = mapped_column(Boolean, default=True)
    use_weights: Mapped[bool] = mapped_column(Boolean, default=False)

    acquire_pulse_channel_uuid: Mapped[UUID | None] = mapped_column(
        ForeignKey("resonator_pulse_channels_base.uuid"),
        nullable=True,
    )
    acquire_pulse_channel: Mapped["ResonatorPulseChannelORM | None"] = relationship(back_populates="acquire")


# ---------------------------------------------------------------------------
# ResonatorPulseChannel  (measure / acquire – FK directly to resonators)
# ---------------------------------------------------------------------------


class ResonatorPulseChannelORM(Base):
    """Covers both MeasurePulseChannel and AcquirePulseChannel.

    role: 'measure' | 'acquire'
    pulse is only populated when role == 'measure'.
    acquire is only populated when role == 'acquire'.
    """

    __tablename__ = "resonator_pulse_channels_base"

    uuid: Mapped[UUID] = mapped_column(primary_key=True)
    role: Mapped[str] = mapped_column(String, nullable=False)  # 'measure' | 'acquire'
    frequency: Mapped[float | None] = mapped_column(Float, nullable=True, default=None)
    imbalance: Mapped[float] = mapped_column(Float, default=1.0)
    phase_iq_offset: Mapped[float] = mapped_column(Float, default=0.0)
    scale_real: Mapped[float] = mapped_column(Float, default=1.0)
    scale_imag: Mapped[float] = mapped_column(Float, default=0.0)

    resonator_uuid: Mapped[UUID | None] = mapped_column(ForeignKey("resonators.uuid"), nullable=True)

    pulse: Mapped["CalibratablePulseORM | None"] = relationship(
        back_populates="measure_pulse_channel",
        foreign_keys=[CalibratablePulseORM.measure_pulse_channel_uuid],
        cascade="all, delete-orphan",
        uselist=False,
    )
    acquire: Mapped["CalibratableAcquireORM | None"] = relationship(
        back_populates="acquire_pulse_channel",
        cascade="all, delete-orphan",
        uselist=False,
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
        back_populates="reset_pulse_channel",
        foreign_keys="CalibratablePulseORM.reset_pulse_channel_uuid",
        cascade="all, delete-orphan",
        uselist=False,
    )


# ---------------------------------------------------------------------------
# XPi2Comp
# ---------------------------------------------------------------------------


class XPi2CompORM(Base):
    __tablename__ = "x_pi_2_comps"

    uuid: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    phase_comp_x_pi_2: Mapped[float] = mapped_column(Float, default=0.0)

    qubit_uuid: Mapped[UUID | None] = mapped_column(ForeignKey("qubits.uuid"), nullable=True)
    qubit: Mapped["QubitORM | None"] = relationship(back_populates="x_pi_2_comp")


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
        back_populates="zx_pi_4_comp_precomp",
        foreign_keys="CalibratablePulseORM.zx_pi_4_comp_precomp_uuid",
        cascade="all, delete-orphan",
        uselist=False,
        overlaps="zx_pi_4_comp_postcomp",
    )
    pulse_postcomp: Mapped["CalibratablePulseORM | None"] = relationship(
        back_populates="zx_pi_4_comp_postcomp",
        foreign_keys="CalibratablePulseORM.zx_pi_4_comp_postcomp_uuid",
        cascade="all, delete-orphan",
        uselist=False,
        overlaps="zx_pi_4_comp_precomp",
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
    x_pi_2_comp: Mapped["XPi2CompORM | None"] = relationship(
        back_populates="qubit", cascade="all, delete-orphan", uselist=False
    )
    zx_pi_4_comps: Mapped[list["ZxPi4CompORM"]] = relationship(back_populates="qubit", cascade="all, delete-orphan")
