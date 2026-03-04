"""
SQLAlchemy ORM models mirroring the Pydantic HardwareModel schema.

Table hierarchy
---------------
hardware_models
  └─ qubits  (FK → hardware_models)
       ├─ physical_channels          (FK → qubits OR resonators, discriminated by channel_kind)
       │    └─ basebands             (FK → physical_channels)
       │    └─ iq_voltage_biases     (FK → physical_channels)
       ├─ qubit_pulse_channels       (drive / second_state / freq_shift)
       │    └─ calibratable_pulses   (FK → qubit_pulse_channels)
       ├─ cross_resonance_channels   (FK → qubits)
       │    └─ calibratable_pulses
       ├─ cross_resonance_cancellation_channels (FK → qubits)
       └─ resonators                (FK → qubits)
            ├─ physical_channels    (channel_kind='resonator', FK → resonators)
            └─ resonator_pulse_channels
                 ├─ measure_pulse_channels  + calibratable_pulse
                 └─ acquire_pulse_channels  + calibratable_acquire
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
# BaseBand
# ---------------------------------------------------------------------------


class BaseBandORM(Base):
    __tablename__ = "basebands"

    uuid: Mapped[UUID] = mapped_column(primary_key=True)
    frequency: Mapped[float | None] = mapped_column(Float, nullable=True, default=None)
    if_frequency: Mapped[float | None] = mapped_column(Float, nullable=True, default=None)

    physical_channel_uuid: Mapped[UUID | None] = mapped_column(ForeignKey("physical_channels.uuid"), nullable=True)

    physical_channel: Mapped["PhysicalChannelORM | None"] = relationship(back_populates="baseband")


# ---------------------------------------------------------------------------
# IQVoltageBias
# ---------------------------------------------------------------------------


class IQVoltageBiasORM(Base):
    __tablename__ = "iq_voltage_biases"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    bias: Mapped[str] = mapped_column(String, nullable=False)

    physical_channel_uuid: Mapped[UUID | None] = mapped_column(ForeignKey("physical_channels.uuid"), nullable=True)

    physical_channel: Mapped["PhysicalChannelORM | None"] = relationship(back_populates="iq_voltage_bias")


# ---------------------------------------------------------------------------
# PhysicalChannel  (unified – qubit and resonator, discriminated by channel_kind)
# ---------------------------------------------------------------------------


class PhysicalChannelORM(Base):
    """Covers both qubit PhysicalChannel and resonator PhysicalChannel.

    channel_kind: 'qubit' | 'resonator'
    swap_readout_iq is only meaningful when channel_kind == 'resonator'.
    Exactly one of qubit_uuid / resonator_uuid will be non-NULL per row.
    """

    __tablename__ = "physical_channels"

    uuid: Mapped[UUID] = mapped_column(primary_key=True)
    channel_kind: Mapped[str] = mapped_column(String, nullable=False)  # 'qubit' | 'resonator'
    name_index: Mapped[int] = mapped_column(Integer, nullable=False)
    block_size: Mapped[int] = mapped_column(Integer, nullable=False)
    default_amplitude: Mapped[int] = mapped_column(Integer, nullable=False)
    switch_box: Mapped[str] = mapped_column(String, nullable=False)
    swap_readout_iq: Mapped[bool] = mapped_column(Boolean, default=False)

    qubit_uuid: Mapped[UUID | None] = mapped_column(ForeignKey("qubits.uuid"), nullable=True)
    qubit: Mapped["QubitORM | None"] = relationship(back_populates="physical_channel")

    resonator_uuid: Mapped[UUID | None] = mapped_column(ForeignKey("resonators.uuid"), nullable=True)
    resonator: Mapped["ResonatorORM | None"] = relationship(back_populates="physical_channel")

    baseband: Mapped["BaseBandORM | None"] = relationship(
        back_populates="physical_channel",
        cascade="all, delete-orphan",
        uselist=False,
    )
    iq_voltage_bias: Mapped["IQVoltageBiasORM | None"] = relationship(
        back_populates="physical_channel",
        cascade="all, delete-orphan",
        uselist=False,
    )


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
    cr_channel_uuid: Mapped[UUID | None] = mapped_column(
        ForeignKey("cross_resonance_channels.uuid"),
        nullable=True,
    )
    measure_pulse_channel_uuid: Mapped[UUID | None] = mapped_column(
        ForeignKey("measure_pulse_channels.uuid"),
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
    cr_channel: Mapped["CrossResonanceChannelORM | None"] = relationship(
        back_populates="zx_pi_4_pulse",
        foreign_keys=[cr_channel_uuid],
    )
    measure_pulse_channel: Mapped["MeasurePulseChannelORM | None"] = relationship(
        back_populates="pulse",
        foreign_keys=[measure_pulse_channel_uuid],
    )


# ---------------------------------------------------------------------------
# DrivePulseChannel
# ---------------------------------------------------------------------------


class DrivePulseChannelORM(Base):
    __tablename__ = "drive_pulse_channels"

    uuid: Mapped[UUID] = mapped_column(primary_key=True)

    qubit_pulse_channels_uuid: Mapped[UUID | None] = mapped_column(
        ForeignKey("qubit_pulse_channels.uuid"), nullable=True
    )
    qubit_pulse_channels: Mapped["QubitPulseChannelsORM | None"] = relationship(back_populates="drive")

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
# PulseChannel  (base columns reused by several concrete tables)
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

    qubit_pulse_channels_uuid: Mapped[UUID | None] = mapped_column(
        ForeignKey("qubit_pulse_channels.uuid"), nullable=True
    )


# ---------------------------------------------------------------------------
# QubitPulseChannels  (container – one per Qubit)
# ---------------------------------------------------------------------------


class QubitPulseChannelsORM(Base):
    __tablename__ = "qubit_pulse_channels"

    uuid: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)

    qubit_uuid: Mapped[UUID | None] = mapped_column(ForeignKey("qubits.uuid"), nullable=True)
    qubit: Mapped["QubitORM | None"] = relationship(back_populates="pulse_channels")

    drive: Mapped["DrivePulseChannelORM | None"] = relationship(
        back_populates="qubit_pulse_channels",
        cascade="all, delete-orphan",
        uselist=False,
    )
    second_state: Mapped["QubitPulseChannelORM | None"] = relationship(
        primaryjoin=(
            "and_(QubitPulseChannelORM.qubit_pulse_channels_uuid == QubitPulseChannelsORM.uuid,"
            " QubitPulseChannelORM.role == 'second_state')"
        ),
        cascade="all, delete-orphan",
        uselist=False,
        viewonly=False,
        foreign_keys=[QubitPulseChannelORM.qubit_pulse_channels_uuid],
        overlaps="freq_shift",
    )
    freq_shift: Mapped["QubitPulseChannelORM | None"] = relationship(
        primaryjoin=(
            "and_(QubitPulseChannelORM.qubit_pulse_channels_uuid == QubitPulseChannelsORM.uuid,"
            " QubitPulseChannelORM.role == 'freq_shift')"
        ),
        cascade="all, delete-orphan",
        uselist=False,
        viewonly=False,
        foreign_keys=[QubitPulseChannelORM.qubit_pulse_channels_uuid],
        overlaps="second_state",
    )


# ---------------------------------------------------------------------------
# CrossResonanceChannel
# ---------------------------------------------------------------------------


class CrossResonanceChannelORM(Base):
    __tablename__ = "cross_resonance_channels"

    uuid: Mapped[UUID] = mapped_column(primary_key=True)
    auxiliary_qubit: Mapped[int] = mapped_column(Integer, nullable=False)
    frequency: Mapped[float | None] = mapped_column(Float, nullable=True, default=None)
    imbalance: Mapped[float] = mapped_column(Float, default=1.0)
    phase_iq_offset: Mapped[float] = mapped_column(Float, default=0.0)
    scale_real: Mapped[float] = mapped_column(Float, default=1.0)
    scale_imag: Mapped[float] = mapped_column(Float, default=0.0)

    qubit_uuid: Mapped[UUID | None] = mapped_column(ForeignKey("qubits.uuid"), nullable=True)
    qubit: Mapped["QubitORM | None"] = relationship(back_populates="cross_resonance_channels")

    zx_pi_4_pulse: Mapped["CalibratablePulseORM | None"] = relationship(
        back_populates="cr_channel",
        foreign_keys=[CalibratablePulseORM.cr_channel_uuid],
        cascade="all, delete-orphan",
        uselist=False,
    )


# ---------------------------------------------------------------------------
# CrossResonanceCancellationChannel
# ---------------------------------------------------------------------------


class CrossResonanceCancellationChannelORM(Base):
    __tablename__ = "cross_resonance_cancellation_channels"

    uuid: Mapped[UUID] = mapped_column(primary_key=True)
    auxiliary_qubit: Mapped[int] = mapped_column(Integer, nullable=False)
    frequency: Mapped[float | None] = mapped_column(Float, nullable=True, default=None)
    imbalance: Mapped[float] = mapped_column(Float, default=1.0)
    phase_iq_offset: Mapped[float] = mapped_column(Float, default=0.0)
    scale_real: Mapped[float] = mapped_column(Float, default=1.0)
    scale_imag: Mapped[float] = mapped_column(Float, default=0.0)

    qubit_uuid: Mapped[UUID | None] = mapped_column(ForeignKey("qubits.uuid"), nullable=True)
    qubit: Mapped["QubitORM | None"] = relationship(back_populates="cross_resonance_cancellation_channels")


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
        ForeignKey("acquire_pulse_channels.uuid"),
        nullable=True,
    )
    acquire_pulse_channel: Mapped["AcquirePulseChannelORM | None"] = relationship(back_populates="acquire")


# ---------------------------------------------------------------------------
# MeasurePulseChannel
# ---------------------------------------------------------------------------


class MeasurePulseChannelORM(Base):
    __tablename__ = "measure_pulse_channels"

    uuid: Mapped[UUID] = mapped_column(primary_key=True)
    frequency: Mapped[float | None] = mapped_column(Float, nullable=True, default=None)
    imbalance: Mapped[float] = mapped_column(Float, default=1.0)
    phase_iq_offset: Mapped[float] = mapped_column(Float, default=0.0)
    scale_real: Mapped[float] = mapped_column(Float, default=1.0)
    scale_imag: Mapped[float] = mapped_column(Float, default=0.0)

    resonator_pulse_channels_uuid: Mapped[UUID | None] = mapped_column(
        ForeignKey("resonator_pulse_channels.uuid"),
        nullable=True,
    )
    resonator_pulse_channels: Mapped["ResonatorPulseChannelsORM | None"] = relationship(back_populates="measure")

    pulse: Mapped["CalibratablePulseORM | None"] = relationship(
        back_populates="measure_pulse_channel",
        foreign_keys=[CalibratablePulseORM.measure_pulse_channel_uuid],
        cascade="all, delete-orphan",
        uselist=False,
    )


# ---------------------------------------------------------------------------
# AcquirePulseChannel
# ---------------------------------------------------------------------------


class AcquirePulseChannelORM(Base):
    __tablename__ = "acquire_pulse_channels"

    uuid: Mapped[UUID] = mapped_column(primary_key=True)
    frequency: Mapped[float | None] = mapped_column(Float, nullable=True, default=None)
    imbalance: Mapped[float] = mapped_column(Float, default=1.0)
    phase_iq_offset: Mapped[float] = mapped_column(Float, default=0.0)
    scale_real: Mapped[float] = mapped_column(Float, default=1.0)
    scale_imag: Mapped[float] = mapped_column(Float, default=0.0)

    resonator_pulse_channels_uuid: Mapped[UUID | None] = mapped_column(
        ForeignKey("resonator_pulse_channels.uuid"),
        nullable=True,
    )
    resonator_pulse_channels: Mapped["ResonatorPulseChannelsORM | None"] = relationship(back_populates="acquire")

    acquire: Mapped["CalibratableAcquireORM | None"] = relationship(
        back_populates="acquire_pulse_channel",
        cascade="all, delete-orphan",
        uselist=False,
    )


# ---------------------------------------------------------------------------
# ResonatorPulseChannels  (container)
# ---------------------------------------------------------------------------


class ResonatorPulseChannelsORM(Base):
    __tablename__ = "resonator_pulse_channels"

    uuid: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)

    resonator_uuid: Mapped[UUID | None] = mapped_column(ForeignKey("resonators.uuid"), nullable=True)
    resonator: Mapped["ResonatorORM | None"] = relationship(back_populates="pulse_channels")

    measure: Mapped["MeasurePulseChannelORM | None"] = relationship(
        back_populates="resonator_pulse_channels",
        cascade="all, delete-orphan",
        uselist=False,
    )
    acquire: Mapped["AcquirePulseChannelORM | None"] = relationship(
        back_populates="resonator_pulse_channels",
        cascade="all, delete-orphan",
        uselist=False,
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
    pulse_channels: Mapped["ResonatorPulseChannelsORM | None"] = relationship(
        back_populates="resonator", cascade="all, delete-orphan", uselist=False
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
    pulse_channels: Mapped["QubitPulseChannelsORM | None"] = relationship(
        back_populates="qubit", cascade="all, delete-orphan", uselist=False
    )
    resonator: Mapped["ResonatorORM | None"] = relationship(
        back_populates="qubit", cascade="all, delete-orphan", uselist=False
    )
    cross_resonance_channels: Mapped[list["CrossResonanceChannelORM"]] = relationship(
        back_populates="qubit", cascade="all, delete-orphan"
    )
    cross_resonance_cancellation_channels: Mapped[list["CrossResonanceCancellationChannelORM"]] = relationship(
        back_populates="qubit", cascade="all, delete-orphan"
    )
