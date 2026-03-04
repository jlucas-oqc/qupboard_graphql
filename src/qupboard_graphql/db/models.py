"""
SQLAlchemy ORM models mirroring the Pydantic HardwareModel schema.

Table hierarchy
---------------
hardware_models
  └─ qubits  (FK → hardware_models)
       ├─ physical_channels        (FK → qubits, channel_kind = 'qubit' | 'resonator')
       │    baseband and IQ-bias columns inlined here
       ├─ pulse_channels           (FK → qubits, channel_role discriminator)
       │    channel_role values:
       │      'drive'            – qubit drive channel
       │      'second_state'     – second-state pulse channel (ss_active, ss_delay)
       │      'freq_shift'       – freq-shift pulse channel   (fs_active, fs_amp, fs_phase)
       │      'measure'          – resonator measure channel
       │      'acquire'          – resonator acquire channel  (acq_delay/width/sync/use_weights)
       │      'reset_qubit'      – qubit reset channel        (reset_delay)
       │      'reset_resonator'  – resonator reset channel    (reset_delay)
       │    └─ calibratable_pulses (owner_uuid → pulse_channels.uuid, pulse_role discriminator)
       ├─ cross_resonance_channels (FK → qubits, role = 'cr' | 'crc')
       │    └─ calibratable_pulses (pulse_role = 'cr')
       ├─ zx_pi_4_comps            (FK → qubits, one per CR pair)
       │    └─ calibratable_pulses (pulse_role = 'zx_precomp' | 'zx_postcomp', nullable)
       │    phase_comp_x_pi_2 inlined on qubits
       └─ res_uuid inlined on qubits (resonator has no other data columns)
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
from qupboard_graphql.db.repository import RepositoryMixin


# ---------------------------------------------------------------------------
# HardwareModel (top-level)
# ---------------------------------------------------------------------------


class HardwareModelORM(RepositoryMixin, Base):
    __tablename__ = "hardware_models"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    version: Mapped[str] = mapped_column(String, nullable=False)
    calibration_id: Mapped[str] = mapped_column(String, nullable=False)
    # logical_connectivity stored as JSON text (dict[str, list[int]])
    logical_connectivity: Mapped[str] = mapped_column(Text, nullable=False)

    qubits: Mapped[list["QubitORM"]] = relationship(back_populates="hardware_model", cascade="all, delete-orphan")


# ---------------------------------------------------------------------------
# PhysicalChannel  (qubit + resonator unified, discriminated by channel_kind)
# ---------------------------------------------------------------------------


class PhysicalChannelORM(Base):
    """Covers both qubit PhysicalChannel and resonator PhysicalChannel.

    channel_kind: 'qubit' | 'resonator'
    swap_readout_iq is only meaningful when channel_kind == 'resonator'.
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
    qubit: Mapped["QubitORM | None"] = relationship(
        back_populates="physical_channels",
        foreign_keys=[qubit_uuid],
    )


# ---------------------------------------------------------------------------
# CalibratablePulse
#
# pulse_role discriminator values:
#   'drive'            – PulseChannelORM (channel_role='drive').pulse
#   'drive_x_pi'       – PulseChannelORM (channel_role='drive').pulse_x_pi
#   'second_state'     – PulseChannelORM (channel_role='second_state').pulse
#   'measure'          – PulseChannelORM (channel_role='measure').pulse
#   'reset_qubit'      – PulseChannelORM (channel_role='reset_qubit').pulse
#   'reset_resonator'  – PulseChannelORM (channel_role='reset_resonator').pulse
#   'cr'               – CrossResonanceChannelORM.zx_pi_4_pulse
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

    owner_uuid: Mapped[UUID] = mapped_column(nullable=False)
    pulse_role: Mapped[str] = mapped_column(String, nullable=False)


# ---------------------------------------------------------------------------
# PulseChannel – unified table replacing:
#   drive_pulse_channels, qubit_pulse_channels_base,
#   resonator_pulse_channels_base, reset_pulse_channels
# ---------------------------------------------------------------------------

_PULSE_OVERLAPS = "pulse,pulse_x_pi,zx_pi_4_pulse,pulse_precomp,pulse_postcomp"


class PulseChannelORM(Base):
    __tablename__ = "pulse_channels"

    uuid: Mapped[UUID] = mapped_column(primary_key=True)
    channel_role: Mapped[str] = mapped_column(String, nullable=False)

    # Common to all roles
    frequency: Mapped[float | None] = mapped_column(Float, nullable=True, default=None)
    imbalance: Mapped[float] = mapped_column(Float, default=1.0)
    phase_iq_offset: Mapped[float] = mapped_column(Float, default=0.0)
    scale_real: Mapped[float] = mapped_column(Float, default=1.0)
    scale_imag: Mapped[float] = mapped_column(Float, default=0.0)

    # second_state extras
    ss_active: Mapped[bool | None] = mapped_column(Boolean, nullable=True, default=None)
    ss_delay: Mapped[float | None] = mapped_column(Float, nullable=True, default=None)

    # freq_shift extras
    fs_active: Mapped[bool | None] = mapped_column(Boolean, nullable=True, default=None)
    fs_amp: Mapped[float | None] = mapped_column(Float, nullable=True, default=None)
    fs_phase: Mapped[float | None] = mapped_column(Float, nullable=True, default=None)

    # acquire extras
    acq_delay: Mapped[float | None] = mapped_column(Float, nullable=True, default=None)
    acq_width: Mapped[float | None] = mapped_column(Float, nullable=True, default=None)
    acq_sync: Mapped[bool | None] = mapped_column(Boolean, nullable=True, default=None)
    acq_use_weights: Mapped[bool | None] = mapped_column(Boolean, nullable=True, default=None)

    # reset extras (shared by reset_qubit and reset_resonator)
    reset_delay: Mapped[float | None] = mapped_column(Float, nullable=True, default=None)

    qubit_uuid: Mapped[UUID | None] = mapped_column(ForeignKey("qubits.uuid"), nullable=True)

    pulse: Mapped["CalibratablePulseORM | None"] = relationship(
        primaryjoin="and_(CalibratablePulseORM.owner_uuid == PulseChannelORM.uuid,"
        " CalibratablePulseORM.pulse_role.in_("
        "['drive','second_state','measure','reset_qubit','reset_resonator']))",
        foreign_keys="CalibratablePulseORM.owner_uuid",
        cascade="all, delete-orphan",
        uselist=False,
        overlaps=_PULSE_OVERLAPS,
    )
    pulse_x_pi: Mapped["CalibratablePulseORM | None"] = relationship(
        primaryjoin="and_(CalibratablePulseORM.owner_uuid == PulseChannelORM.uuid,"
        " CalibratablePulseORM.pulse_role == 'drive_x_pi')",
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
# Qubit
# ---------------------------------------------------------------------------


class QubitORM(Base):
    __tablename__ = "qubits"

    uuid: Mapped[UUID] = mapped_column(primary_key=True)
    qubit_key: Mapped[str] = mapped_column(String, nullable=False)
    mean_z_map_args: Mapped[str] = mapped_column(Text, nullable=False)  # JSON [real, imag]
    discriminator_real: Mapped[float] = mapped_column(Float, default=0.0)
    discriminator_imag: Mapped[float] = mapped_column(Float, default=0.0)
    direct_x_pi: Mapped[bool] = mapped_column(Boolean, default=False)
    # Inlined XPi2Comp
    phase_comp_x_pi_2: Mapped[float] = mapped_column(Float, default=0.0)
    # Inlined Resonator UUID (resonator has no other data columns)
    res_uuid: Mapped[UUID] = mapped_column(nullable=False)

    hardware_model_id: Mapped[UUID | None] = mapped_column(ForeignKey("hardware_models.id"), nullable=True)
    hardware_model: Mapped["HardwareModelORM | None"] = relationship(back_populates="qubits")

    # Both qubit and resonator physical channels FK here (channel_kind discriminates)
    physical_channels: Mapped[list["PhysicalChannelORM"]] = relationship(
        back_populates="qubit",
        foreign_keys="PhysicalChannelORM.qubit_uuid",
        cascade="all, delete-orphan",
    )

    # All pulse channels for this qubit (all roles)
    pulse_channels: Mapped[list["PulseChannelORM"]] = relationship(
        foreign_keys="PulseChannelORM.qubit_uuid",
        cascade="all, delete-orphan",
    )

    @property
    def drive_channel(self) -> "PulseChannelORM | None":
        return next((c for c in self.pulse_channels if c.channel_role == "drive"), None)

    @property
    def second_state_channel(self) -> "PulseChannelORM | None":
        return next((c for c in self.pulse_channels if c.channel_role == "second_state"), None)

    @property
    def freq_shift_channel(self) -> "PulseChannelORM | None":
        return next((c for c in self.pulse_channels if c.channel_role == "freq_shift"), None)

    @property
    def measure_channel(self) -> "PulseChannelORM | None":
        return next((c for c in self.pulse_channels if c.channel_role == "measure"), None)

    @property
    def acquire_channel(self) -> "PulseChannelORM | None":
        return next((c for c in self.pulse_channels if c.channel_role == "acquire"), None)

    @property
    def reset_qubit_channel(self) -> "PulseChannelORM | None":
        return next((c for c in self.pulse_channels if c.channel_role == "reset_qubit"), None)

    @property
    def reset_resonator_channel(self) -> "PulseChannelORM | None":
        return next((c for c in self.pulse_channels if c.channel_role == "reset_resonator"), None)

    cross_resonance_channels: Mapped[list["CrossResonanceChannelORM"]] = relationship(
        cascade="all, delete-orphan",
        primaryjoin="and_(CrossResonanceChannelORM.qubit_uuid == QubitORM.uuid, CrossResonanceChannelORM.role == 'cr')",
        foreign_keys="CrossResonanceChannelORM.qubit_uuid",
        viewonly=False,
        overlaps="cross_resonance_cancellation_channels,qubit",
    )
    cross_resonance_cancellation_channels: Mapped[list["CrossResonanceChannelORM"]] = relationship(
        cascade="all, delete-orphan",
        primaryjoin="and_(CrossResonanceChannelORM.qubit_uuid == QubitORM.uuid,"
        " CrossResonanceChannelORM.role == 'crc')",
        foreign_keys="CrossResonanceChannelORM.qubit_uuid",
        viewonly=False,
        overlaps="cross_resonance_channels,qubit",
    )
    zx_pi_4_comps: Mapped[list["ZxPi4CompORM"]] = relationship(back_populates="qubit", cascade="all, delete-orphan")
