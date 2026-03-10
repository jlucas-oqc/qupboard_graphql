"""
SQLAlchemy ORM models mirroring the Pydantic HardwareModel schema.

Table hierarchy
---------------
hardware_models
  └─ qubits  (FK → hardware_models)
       ├─ physical_channels        (FK → qubits OR resonators, channel_kind = 'qubit' | 'resonator')
       │    baseband and IQ-bias columns inlined here
       ├─ pulse_channels           (FK → qubits OR resonators, channel_role discriminator)
       │    channel_role values:
       │      'drive'            – qubit drive channel
       │      'second_state'     – second-state pulse channel (ss_active, ss_delay)
       │      'freq_shift'       – freq-shift pulse channel   (fs_active, fs_amp, fs_phase)
       │      'measure'          – resonator measure channel
       │      'acquire'          – resonator acquire channel  (acq_delay/width/sync/use_weights)
       │      'reset_qubit'      – qubit reset channel        (reset_delay)
       │      'reset_resonator'  – resonator reset channel    (reset_delay)
       │    └─ calibratable_pulses (owner_uuid → pulse_channels.id, pulse_role discriminator)
       ├─ cross_resonance_channels (FK → qubits, role = 'cr' | 'crc')
       │    └─ calibratable_pulses (pulse_role = 'cr')
       ├─ zx_pi_4_comps            (FK → qubits, one per CR pair)
       │    └─ calibratable_pulses (pulse_role = 'zx_precomp' | 'zx_postcomp', nullable)
       │    phase_comp_x_pi_2 inlined on qubits
       └─ resonators               (FK → qubits, one-to-one)
            ├─ physical_channels   (FK → resonators, channel_kind = 'resonator')
            └─ pulse_channels      (FK → resonators, channel_role = 'measure' | 'acquire' | 'reset_resonator')
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
    """Top-level hardware model record containing version and qubit calibration data.

    Attributes:
        id: Auto-generated UUID primary key.
        version: Schema or calibration version string.
        calibration_id: Identifier for the calibration run.
        logical_connectivity: JSON-encoded mapping of qubit label to list of
            neighbour indices.
        qubits: One-to-many collection of associated :class:`QubitORM` rows.
    """

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
    """Unified physical channel row covering both qubit and resonator channels.

    A single table (``physical_channels``) stores physical channels for both
    qubits and resonators, discriminated by *channel_kind*.  The inlined
    ``BaseBand`` and ``IQVoltageBias`` Pydantic fields are flattened into
    columns here rather than in separate tables.

    Attributes:
        uuid: UUID primary key (shared with the Pydantic schema's UUID).
        channel_kind: ``"qubit"`` or ``"resonator"`` — identifies the owner type.
        name_index: Hardware name index used to address the physical port.
        block_size: Waveform block size in samples.
        default_amplitude: Default output amplitude in hardware units.
        switch_box: Switch-box identifier string.
        swap_readout_iq: Whether to swap I and Q for readout (resonator only).
        baseband_uuid: UUID of the inlined baseband oscillator.
        baseband_frequency: Baseband carrier frequency in Hz.
        baseband_if_frequency: Intermediate frequency in Hz.
        iq_bias: Serialised IQ voltage bias correction string.
        qubit_uuid: FK to :class:`QubitORM` (set when ``channel_kind = "qubit"``).
        resonator_uuid: FK to :class:`ResonatorORM` (set when ``channel_kind = "resonator"``).
        qubit: Relationship to the owning :class:`QubitORM`.
        resonator: Relationship to the owning :class:`ResonatorORM`.
    """

    __tablename__ = "physical_channels"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
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

    qubit_uuid: Mapped[UUID | None] = mapped_column(ForeignKey("qubits.id"), nullable=True)
    resonator_uuid: Mapped[UUID | None] = mapped_column(ForeignKey("resonators.id"), nullable=True)

    qubit: Mapped["QubitORM | None"] = relationship(
        back_populates="physical_channel",
        foreign_keys=[qubit_uuid],
    )
    resonator: Mapped["ResonatorORM | None"] = relationship(
        back_populates="physical_channel",
        foreign_keys=[resonator_uuid],
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
    """A single calibratable waveform pulse stored in the ``calibratable_pulses`` table.

    Pulses are owned by a channel row identified by *owner_uuid* and are
    further distinguished by the *pulse_role* discriminator column.

    Attributes:
        id: Auto-increment integer primary key.
        waveform_type: Waveform shape identifier (e.g. ``"gaussian"``).
        width: Pulse duration in seconds.
        amp: Pulse amplitude.
        phase: Pulse phase in radians.
        drag: DRAG correction coefficient.
        rise: Rise-time parameter (fraction of width).
        amp_setup: Setup amplitude.
        std_dev: Gaussian standard deviation.
        owner_uuid: UUID of the owning channel row.
        pulse_role: Discriminator string identifying which relationship slot
            this pulse fills (e.g. ``"drive"``, ``"drive_x_pi"``, ``"cr"``).
    """

    __tablename__ = "calibratable_pulses"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
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
    """Unified pulse channel row covering all channel roles.

    A single table (``pulse_channels``) stores every role of pulse channel:
    drive, second_state, freq_shift, measure, acquire, reset_qubit, and
    reset_resonator.  Role-specific columns are ``NULL`` for rows of a
    different role.

    Attributes:
        uuid: UUID primary key.
        channel_role: Role discriminator (``"drive"``, ``"second_state"``,
            ``"freq_shift"``, ``"measure"``, ``"acquire"``,
            ``"reset_qubit"``, ``"reset_resonator"``).
        frequency: Carrier frequency in Hz (``None`` encodes NaN).
        imbalance: IQ imbalance correction factor.
        phase_iq_offset: IQ phase offset in radians.
        scale_real: Real part of the complex scale factor.
        scale_imag: Imaginary part of the complex scale factor.
        ss_active: (*second_state* only) Whether second-state driving is active.
        ss_delay: (*second_state* only) Second-state delay in seconds.
        fs_active: (*freq_shift* only) Whether frequency shifting is active.
        fs_amp: (*freq_shift* only) Frequency-shift amplitude.
        fs_phase: (*freq_shift* only) Frequency-shift phase.
        acq_delay: (*acquire* only) Acquisition delay in seconds.
        acq_width: (*acquire* only) Acquisition window width in seconds.
        acq_sync: (*acquire* only) Whether to sync the acquisition.
        acq_use_weights: (*acquire* only) Whether to use integration weights.
        reset_delay: (*reset_qubit/reset_resonator* only) Reset delay in seconds.
        qubit_uuid: FK to :class:`QubitORM` (set for qubit-owned channels).
        resonator_uuid: FK to :class:`ResonatorORM` (set for resonator channels).
        pulse: Primary pulse waveform (most roles).
        pulse_x_pi: X-π pulse waveform (drive role only).
    """

    __tablename__ = "pulse_channels"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
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

    qubit_uuid: Mapped[UUID | None] = mapped_column(ForeignKey("qubits.id"), nullable=True)
    resonator_uuid: Mapped[UUID | None] = mapped_column(ForeignKey("resonators.id"), nullable=True)

    pulse: Mapped["CalibratablePulseORM | None"] = relationship(
        primaryjoin="and_(CalibratablePulseORM.owner_uuid == PulseChannelORM.id,"
        " CalibratablePulseORM.pulse_role.in_("
        "['drive','second_state','measure','reset_qubit','reset_resonator']))",
        foreign_keys="CalibratablePulseORM.owner_uuid",
        cascade="all, delete-orphan",
        uselist=False,
        lazy="joined",
        overlaps=_PULSE_OVERLAPS,
    )
    pulse_x_pi: Mapped["CalibratablePulseORM | None"] = relationship(
        primaryjoin="and_(CalibratablePulseORM.owner_uuid == PulseChannelORM.id,"
        " CalibratablePulseORM.pulse_role == 'drive_x_pi')",
        foreign_keys="CalibratablePulseORM.owner_uuid",
        cascade="all, delete-orphan",
        uselist=False,
        lazy="joined",
        overlaps=_PULSE_OVERLAPS,
    )


# ---------------------------------------------------------------------------
# CrossResonanceChannel  (unified – CR and CRC, discriminated by role)
# ---------------------------------------------------------------------------


class CrossResonanceChannelORM(Base):
    """Unified cross-resonance channel row covering both CR and CRC channels.

    A single table (``cross_resonance_channels``) stores both
    CrossResonancePulseChannel (role ``"cr"``) and
    CrossResonanceCancellationPulseChannel (role ``"crc"``) rows.
    The ``zx_pi_4_pulse`` relationship is only populated for ``"cr"`` rows.

    Attributes:
        uuid: UUID primary key.
        role: ``"cr"`` for a cross-resonance channel or ``"crc"`` for a
            cross-resonance cancellation channel.
        auxiliary_qubit: Index of the auxiliary (target) qubit in the CR pair.
        frequency: Carrier frequency in Hz (``None`` encodes NaN).
        imbalance: IQ imbalance correction factor.
        phase_iq_offset: IQ phase offset in radians.
        scale_real: Real part of the complex scale factor.
        scale_imag: Imaginary part of the complex scale factor.
        qubit_uuid: FK to the owning :class:`QubitORM`.
        qubit: Relationship to the owning :class:`QubitORM`.
        zx_pi_4_pulse: ZX-π/4 calibration pulse (CR role only).
    """

    __tablename__ = "cross_resonance_channels"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    role: Mapped[str] = mapped_column(String, nullable=False)  # 'cr' | 'crc'
    auxiliary_qubit: Mapped[int] = mapped_column(Integer, nullable=False)
    frequency: Mapped[float | None] = mapped_column(Float, nullable=True, default=None)
    imbalance: Mapped[float] = mapped_column(Float, default=1.0)
    phase_iq_offset: Mapped[float] = mapped_column(Float, default=0.0)
    scale_real: Mapped[float] = mapped_column(Float, default=1.0)
    scale_imag: Mapped[float] = mapped_column(Float, default=0.0)

    qubit_uuid: Mapped[UUID | None] = mapped_column(ForeignKey("qubits.id"), nullable=True)
    qubit: Mapped["QubitORM | None"] = relationship(
        foreign_keys=[qubit_uuid],
        overlaps="cross_resonance_channels,cross_resonance_cancellation_channels",
    )

    zx_pi_4_pulse: Mapped["CalibratablePulseORM | None"] = relationship(
        primaryjoin="and_(CalibratablePulseORM.owner_uuid == CrossResonanceChannelORM.id,"
        " CalibratablePulseORM.pulse_role == 'cr')",
        foreign_keys="CalibratablePulseORM.owner_uuid",
        cascade="all, delete-orphan",
        uselist=False,
        lazy="joined",
        overlaps=_PULSE_OVERLAPS,
    )


# ---------------------------------------------------------------------------
# ZxPi4Comp  (one per CR pair, keyed by auxiliary_qubit)
# ---------------------------------------------------------------------------


class ZxPi4CompORM(Base):
    """ZX-π/4 compensation element associated with a specific auxiliary qubit.

    Each row represents the calibration data for one CR-pair compensation,
    keyed by *auxiliary_qubit* index.  Optional pre- and post-compensation
    pulses are stored as related :class:`CalibratablePulseORM` rows.

    Attributes:
        uuid: Auto-generated UUID primary key.
        auxiliary_qubit: Index of the auxiliary (control) qubit in the CR pair.
        phase_comp_target_zx_pi_4: Target ZX-π/4 phase compensation.
        pulse_zx_pi_4_target_rotary_amp: Optional rotary pulse amplitude.
        precomp_active: Whether pre-compensation is enabled.
        postcomp_active: Whether post-compensation is enabled.
        use_second_state: Whether to use the second excited state.
        use_rotary: Whether to use a rotary pulse.
        qubit_uuid: FK to the owning :class:`QubitORM`.
        qubit: Relationship to the owning :class:`QubitORM`.
        pulse_precomp: Optional pre-compensation :class:`CalibratablePulseORM`.
        pulse_postcomp: Optional post-compensation :class:`CalibratablePulseORM`.
    """

    __tablename__ = "zx_pi_4_comps"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    auxiliary_qubit: Mapped[int] = mapped_column(Integer, nullable=False)
    phase_comp_target_zx_pi_4: Mapped[float] = mapped_column(Float, default=0.0)
    pulse_zx_pi_4_target_rotary_amp: Mapped[float | None] = mapped_column(Float, nullable=True, default=None)
    precomp_active: Mapped[bool] = mapped_column(Boolean, default=False)
    postcomp_active: Mapped[bool] = mapped_column(Boolean, default=False)
    use_second_state: Mapped[bool] = mapped_column(Boolean, default=False)
    use_rotary: Mapped[bool] = mapped_column(Boolean, default=False)

    qubit_uuid: Mapped[UUID | None] = mapped_column(ForeignKey("qubits.id"), nullable=True)
    qubit: Mapped["QubitORM | None"] = relationship(back_populates="zx_pi_4_comps")

    pulse_precomp: Mapped["CalibratablePulseORM | None"] = relationship(
        primaryjoin="and_(CalibratablePulseORM.owner_uuid == ZxPi4CompORM.id,"
        " CalibratablePulseORM.pulse_role == 'zx_precomp')",
        foreign_keys="CalibratablePulseORM.owner_uuid",
        cascade="all, delete-orphan",
        uselist=False,
        lazy="joined",
        overlaps=_PULSE_OVERLAPS,
    )
    pulse_postcomp: Mapped["CalibratablePulseORM | None"] = relationship(
        primaryjoin="and_(CalibratablePulseORM.owner_uuid == ZxPi4CompORM.id,"
        " CalibratablePulseORM.pulse_role == 'zx_postcomp')",
        foreign_keys="CalibratablePulseORM.owner_uuid",
        cascade="all, delete-orphan",
        uselist=False,
        lazy="joined",
        overlaps=_PULSE_OVERLAPS,
    )


# ---------------------------------------------------------------------------
# Resonator  (one-to-one with Qubit)
# ---------------------------------------------------------------------------


class ResonatorORM(Base):
    """Readout resonator coupled one-to-one with a :class:`QubitORM`.

    Holds the resonator's physical channel and its three pulse channels
    (measure, acquire, reset_resonator).

    Attributes:
        uuid: UUID primary key (shared with the Pydantic schema's UUID).
        qubit_uuid: FK to the parent :class:`QubitORM`.
        qubit: Relationship to the parent :class:`QubitORM`.
        physical_channel: Single :class:`PhysicalChannelORM` with
            ``channel_kind = "resonator"``.
        pulse_channels: All resonator pulse channels (measure, acquire,
            reset_resonator).
    """

    __tablename__ = "resonators"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)

    qubit_uuid: Mapped[UUID] = mapped_column(ForeignKey("qubits.id"), nullable=False, unique=True)
    qubit: Mapped["QubitORM"] = relationship(back_populates="resonator")

    # One resonator physical channel
    physical_channel: Mapped["PhysicalChannelORM | None"] = relationship(
        back_populates="resonator",
        foreign_keys="PhysicalChannelORM.resonator_uuid",
        cascade="all, delete-orphan",
        uselist=False,
        lazy="selectin",
    )

    # Resonator pulse channels (measure, acquire, reset_resonator)
    pulse_channels: Mapped[list["PulseChannelORM"]] = relationship(
        foreign_keys="PulseChannelORM.resonator_uuid",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    @property
    def measure_channel(self) -> "PulseChannelORM | None":
        """Return the measure pulse channel, or ``None`` if absent."""
        return next((c for c in self.pulse_channels if c.channel_role == "measure"), None)

    @property
    def acquire_channel(self) -> "PulseChannelORM | None":
        """Return the acquire pulse channel, or ``None`` if absent."""
        return next((c for c in self.pulse_channels if c.channel_role == "acquire"), None)

    @property
    def reset_resonator_channel(self) -> "PulseChannelORM | None":
        """Return the resonator reset pulse channel, or ``None`` if absent."""
        return next((c for c in self.pulse_channels if c.channel_role == "reset_resonator"), None)


# ---------------------------------------------------------------------------
# Qubit
# ---------------------------------------------------------------------------


class QubitORM(Base):
    """ORM representation of a single qubit and its full calibration payload.

    Owns a physical channel, multiple pulse channels (drive, second_state,
    freq_shift, reset_qubit), cross-resonance channels, ZX-π/4 compensation
    entries, and a one-to-one resonator.

    Attributes:
        uuid: UUID primary key.
        qubit_key: String key used to identify the qubit within the model
            (e.g. ``"q0"``).
        mean_z_map_args: JSON-encoded two-element list ``[real, imag]``
            representing the mean-Z mapping arguments.
        discriminator_real: Real part of the state-discrimination threshold.
        discriminator_imag: Imaginary part of the state-discrimination threshold.
        direct_x_pi: Whether to use a direct X-π pulse.
        phase_comp_x_pi_2: X-π/2 phase compensation value.
        hardware_model_id: FK to the parent :class:`HardwareModelORM`.
        hardware_model: Relationship to the parent :class:`HardwareModelORM`.
        physical_channel: Single :class:`PhysicalChannelORM` with
            ``channel_kind = "qubit"``.
        pulse_channels: All qubit-owned pulse channels.
        resonator: One-to-one :class:`ResonatorORM`.
        cross_resonance_channels: CR pulse channels (role ``"cr"``).
        cross_resonance_cancellation_channels: CRC pulse channels (role ``"crc"``).
        zx_pi_4_comps: ZX-π/4 compensation rows.
    """

    __tablename__ = "qubits"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    qubit_key: Mapped[str] = mapped_column(String, nullable=False)
    mean_z_map_args: Mapped[str] = mapped_column(Text, nullable=False)  # JSON [real, imag]
    discriminator_real: Mapped[float] = mapped_column(Float, default=0.0)
    discriminator_imag: Mapped[float] = mapped_column(Float, default=0.0)
    direct_x_pi: Mapped[bool] = mapped_column(Boolean, default=False)
    # Inlined XPi2Comp
    phase_comp_x_pi_2: Mapped[float] = mapped_column(Float, default=0.0)

    hardware_model_id: Mapped[UUID | None] = mapped_column(ForeignKey("hardware_models.id"), nullable=True)
    hardware_model: Mapped["HardwareModelORM | None"] = relationship(back_populates="qubits")

    # Qubit physical channel (channel_kind = 'qubit')
    physical_channel: Mapped["PhysicalChannelORM | None"] = relationship(
        back_populates="qubit",
        foreign_keys="PhysicalChannelORM.qubit_uuid",
        cascade="all, delete-orphan",
        uselist=False,
        lazy="selectin",
    )

    # All qubit-owned pulse channels (drive, second_state, freq_shift, reset_qubit)
    pulse_channels: Mapped[list["PulseChannelORM"]] = relationship(
        foreign_keys="PulseChannelORM.qubit_uuid",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    # One-to-one resonator
    resonator: Mapped["ResonatorORM | None"] = relationship(
        back_populates="qubit",
        cascade="all, delete-orphan",
        uselist=False,
        lazy="selectin",
    )

    @property
    def drive_channel(self) -> "PulseChannelORM | None":
        """Return the drive pulse channel, or ``None`` if absent."""
        return next((c for c in self.pulse_channels if c.channel_role == "drive"), None)

    @property
    def second_state_channel(self) -> "PulseChannelORM | None":
        """Return the second-state pulse channel, or ``None`` if absent."""
        return next((c for c in self.pulse_channels if c.channel_role == "second_state"), None)

    @property
    def freq_shift_channel(self) -> "PulseChannelORM | None":
        """Return the frequency-shift pulse channel, or ``None`` if absent."""
        return next((c for c in self.pulse_channels if c.channel_role == "freq_shift"), None)

    @property
    def reset_qubit_channel(self) -> "PulseChannelORM | None":
        """Return the qubit reset pulse channel, or ``None`` if absent."""
        return next((c for c in self.pulse_channels if c.channel_role == "reset_qubit"), None)

    cross_resonance_channels: Mapped[list["CrossResonanceChannelORM"]] = relationship(
        cascade="all, delete-orphan",
        primaryjoin="and_(CrossResonanceChannelORM.qubit_uuid == QubitORM.id, CrossResonanceChannelORM.role == 'cr')",
        foreign_keys="CrossResonanceChannelORM.qubit_uuid",
        lazy="selectin",
        overlaps="cross_resonance_cancellation_channels,qubit",
    )
    cross_resonance_cancellation_channels: Mapped[list["CrossResonanceChannelORM"]] = relationship(
        cascade="all, delete-orphan",
        primaryjoin="and_(CrossResonanceChannelORM.qubit_uuid == QubitORM.id, CrossResonanceChannelORM.role == 'crc')",
        foreign_keys="CrossResonanceChannelORM.qubit_uuid",
        lazy="selectin",
        overlaps="cross_resonance_channels,qubit",
    )
    zx_pi_4_comps: Mapped[list["ZxPi4CompORM"]] = relationship(
        back_populates="qubit", cascade="all, delete-orphan", lazy="selectin"
    )
