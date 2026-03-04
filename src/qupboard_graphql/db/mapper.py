"""
Utilities for converting Pydantic HardwareModel ↔ SQLAlchemy ORM instances.
"""

import json
import math

from qupboard_graphql.schemas.hardware_model import (
    AcquirePulseChannel,
    BaseBand,
    CalibratableAcquire,
    CalibratablePulse,
    CrossResonanceCancellationPulseChannel,
    CrossResonancePulseChannel,
    DrivePulseChannel,
    FreqShiftPulseChannel,
    HardwareModel,
    IQVoltageBias,
    MeasurePulseChannel,
    PhysicalChannel,
    Qubit,
    QubitPulseChannels,
    Resonator,
    ResonatorPulseChannels,
    SecondStatePulseChannel,
)
from qupboard_graphql.db.models import (
    AcquirePulseChannelORM,
    BaseBandORM,
    CalibratableAcquireORM,
    CalibratablePulseORM,
    CrossResonanceCancellationChannelORM,
    CrossResonanceChannelORM,
    DrivePulseChannelORM,
    HardwareModelORM,
    IQVoltageBiasORM,
    MeasurePulseChannelORM,
    PhysicalChannelORM,
    QubitORM,
    QubitPulseChannelORM,
    QubitPulseChannelsORM,
    ResonatorORM,
    ResonatorPulseChannelsORM,
)


def _pulse_orm(pulse: CalibratablePulse) -> CalibratablePulseORM:
    return CalibratablePulseORM(
        waveform_type=pulse.waveform_type,
        width=pulse.width,
        amp=pulse.amp,
        phase=pulse.phase,
        drag=pulse.drag,
        rise=pulse.rise,
        amp_setup=pulse.amp_setup,
        std_dev=pulse.std_dev,
    )


def _iq_bias_orm(bias: IQVoltageBias) -> IQVoltageBiasORM:
    return IQVoltageBiasORM(bias=bias.bias)


def _physical_channel_orm(pc: PhysicalChannel) -> PhysicalChannelORM:
    return PhysicalChannelORM(
        uuid=pc.uuid,
        channel_kind="qubit",
        name_index=pc.name_index,
        block_size=pc.block_size,
        default_amplitude=pc.default_amplitude,
        switch_box=pc.switch_box,
        baseband=BaseBandORM(
            uuid=pc.baseband.uuid,
            frequency=pc.baseband.frequency,
            if_frequency=pc.baseband.if_frequency,
        ),
        iq_voltage_bias=_iq_bias_orm(pc.iq_voltage_bias),
    )


def _resonator_physical_channel_orm(
    rpc: PhysicalChannel,
) -> PhysicalChannelORM:
    return PhysicalChannelORM(
        uuid=rpc.uuid,
        channel_kind="resonator",
        name_index=rpc.name_index,
        block_size=rpc.block_size,
        default_amplitude=rpc.default_amplitude,
        switch_box=rpc.switch_box,
        swap_readout_iq=rpc.swap_readout_iq,
        baseband=BaseBandORM(
            uuid=rpc.baseband.uuid,
            frequency=rpc.baseband.frequency,
            if_frequency=rpc.baseband.if_frequency,
        ),
        iq_voltage_bias=_iq_bias_orm(rpc.iq_voltage_bias),
    )


def _acquire_orm(acq: CalibratableAcquire) -> CalibratableAcquireORM:
    return CalibratableAcquireORM(
        delay=acq.delay,
        width=acq.width,
        sync=acq.sync,
        use_weights=acq.use_weights,
    )


def _scale_parts(scale) -> tuple[float, float]:
    """Return (real, imag) from a complex or float scale value."""
    if isinstance(scale, complex):
        return scale.real, scale.imag
    return float(scale), 0.0


def _nan_to_none(value: float) -> float | None:
    """Convert NaN to None so it is stored as SQL NULL rather than triggering NOT NULL errors."""
    if value is None:
        return None
    try:
        return None if math.isnan(value) else value
    except (TypeError, ValueError):
        return value


def _measure_pulse_channel_orm(mpc: MeasurePulseChannel) -> MeasurePulseChannelORM:
    real, imag = _scale_parts(mpc.scale)
    return MeasurePulseChannelORM(
        uuid=mpc.uuid,
        frequency=mpc.frequency,
        imbalance=mpc.imbalance,
        phase_iq_offset=mpc.phase_iq_offset,
        scale_real=real,
        scale_imag=imag,
        pulse=_pulse_orm(mpc.pulse),
    )


def _resonator_orm(resonator: Resonator) -> ResonatorORM:
    acquire_pc = resonator.pulse_channels.acquire
    acquire_real, acquire_imag = _scale_parts(acquire_pc.scale)
    return ResonatorORM(
        uuid=resonator.uuid,
        physical_channel=_resonator_physical_channel_orm(resonator.physical_channel),
        pulse_channels=ResonatorPulseChannelsORM(
            uuid=resonator.pulse_channels.acquire.uuid,  # reuse one UUID for container
            measure=_measure_pulse_channel_orm(resonator.pulse_channels.measure),
            acquire=AcquirePulseChannelORM(
                uuid=acquire_pc.uuid,
                frequency=acquire_pc.frequency,
                imbalance=acquire_pc.imbalance,
                phase_iq_offset=acquire_pc.phase_iq_offset,
                scale_real=acquire_real,
                scale_imag=acquire_imag,
                acquire=_acquire_orm(acquire_pc.acquire),
            ),
        ),
    )


def _qubit_pulse_channels_orm(
    qubit_pulse_channels,
    cross_resonance: dict[int, CrossResonancePulseChannel],
    cross_resonance_cancellation: dict[int, CrossResonanceCancellationPulseChannel],
) -> tuple[
    QubitPulseChannelsORM,
    list[CrossResonanceChannelORM],
    list[CrossResonanceCancellationChannelORM],
]:
    drive = qubit_pulse_channels.drive
    drive_orm = DrivePulseChannelORM(
        uuid=drive.uuid,
        pulse=_pulse_orm(drive.pulse),
        pulse_x_pi=_pulse_orm(drive.pulse_x_pi) if drive.pulse_x_pi is not None else None,
    )

    ss: SecondStatePulseChannel = qubit_pulse_channels.second_state
    ss_real, ss_imag = _scale_parts(ss.scale)
    ss_orm = QubitPulseChannelORM(
        uuid=ss.uuid,
        role="second_state",
        frequency=_nan_to_none(ss.frequency),
        imbalance=ss.imbalance,
        phase_iq_offset=ss.phase_iq_offset,
        scale_real=ss_real,
        scale_imag=ss_imag,
        ss_active=ss.active,
        ss_delay=ss.delay,
    )

    fs: FreqShiftPulseChannel = qubit_pulse_channels.freq_shift
    fs_real, fs_imag = _scale_parts(fs.scale)
    fs_orm = QubitPulseChannelORM(
        uuid=fs.uuid,
        role="freq_shift",
        frequency=_nan_to_none(fs.frequency),
        imbalance=fs.imbalance,
        phase_iq_offset=fs.phase_iq_offset,
        scale_real=fs_real,
        scale_imag=fs_imag,
        fs_active=fs.active,
        fs_amp=fs.amp,
        fs_phase=fs.phase,
    )

    container = QubitPulseChannelsORM(
        drive=drive_orm,
        second_state=ss_orm,
        freq_shift=fs_orm,
    )

    cr_orms: list[CrossResonanceChannelORM] = []
    for aux_idx, cr in cross_resonance.items():
        cr_real, cr_imag = _scale_parts(cr.scale)
        cr_orms.append(
            CrossResonanceChannelORM(
                uuid=cr.uuid,
                auxiliary_qubit=cr.auxiliary_qubit,
                frequency=cr.frequency,
                imbalance=cr.imbalance,
                phase_iq_offset=cr.phase_iq_offset,
                scale_real=cr_real,
                scale_imag=cr_imag,
                zx_pi_4_pulse=_pulse_orm(cr.zx_pi_4_pulse) if cr.zx_pi_4_pulse is not None else None,
            )
        )

    crc_orms: list[CrossResonanceCancellationChannelORM] = []
    for aux_idx, crc in cross_resonance_cancellation.items():
        crc_real, crc_imag = _scale_parts(crc.scale)
        crc_orms.append(
            CrossResonanceCancellationChannelORM(
                uuid=crc.uuid,
                auxiliary_qubit=crc.auxiliary_qubit,
                frequency=crc.frequency,
                imbalance=crc.imbalance,
                phase_iq_offset=crc.phase_iq_offset,
                scale_real=crc_real,
                scale_imag=crc_imag,
            )
        )

    return container, cr_orms, crc_orms


def _qubit_orm(qubit_key: str, qubit: Qubit) -> QubitORM:
    discriminator_real, discriminator_imag = _scale_parts(qubit.discriminator)

    pulse_channels_container, cr_orms, crc_orms = _qubit_pulse_channels_orm(
        qubit.pulse_channels,
        qubit.pulse_channels.cross_resonance_channels,
        qubit.pulse_channels.cross_resonance_cancellation_channels,
    )

    return QubitORM(
        uuid=qubit.uuid,
        qubit_key=qubit_key,
        mean_z_map_args=json.dumps([v.real if isinstance(v, complex) else v for v in qubit.mean_z_map_args]),
        discriminator_real=discriminator_real,
        discriminator_imag=discriminator_imag,
        direct_x_pi=qubit.direct_x_pi,
        physical_channel=_physical_channel_orm(qubit.physical_channel),
        pulse_channels=pulse_channels_container,
        resonator=_resonator_orm(qubit.resonator),
        cross_resonance_channels=cr_orms,
        cross_resonance_cancellation_channels=crc_orms,
    )


def hardware_model_to_orm(model: HardwareModel) -> HardwareModelORM:
    """Convert a validated Pydantic HardwareModel into a fully-populated ORM tree."""
    qubit_orms = [_qubit_orm(key, qubit) for key, qubit in model.qubits.items()]
    return HardwareModelORM(
        version=model.version,
        calibration_id=model.calibration_id,
        logical_connectivity=json.dumps(model.logical_connectivity),
        qubits=qubit_orms,
    )


# ---------------------------------------------------------------------------
# ORM → Pydantic
# ---------------------------------------------------------------------------


def _pulse_from_orm(orm) -> CalibratablePulse:
    return CalibratablePulse(
        waveform_type=orm.waveform_type,
        width=orm.width,
        amp=orm.amp,
        phase=orm.phase,
        drag=orm.drag,
        rise=orm.rise,
        amp_setup=orm.amp_setup,
        std_dev=orm.std_dev,
    )


def _baseband_from_orm(orm) -> BaseBand:
    return BaseBand(
        uuid=orm.uuid,
        frequency=orm.frequency,
        if_frequency=orm.if_frequency,
    )


def _iq_bias_from_orm(orm) -> IQVoltageBias:
    return IQVoltageBias(bias=orm.bias)


def _physical_channel_from_orm(orm: PhysicalChannelORM) -> PhysicalChannel:
    return PhysicalChannel(
        uuid=orm.uuid,
        name_index=orm.name_index,
        block_size=orm.block_size,
        default_amplitude=orm.default_amplitude,
        switch_box=orm.switch_box,
        swap_readout_iq=orm.swap_readout_iq,
        baseband=_baseband_from_orm(orm.baseband),
        iq_voltage_bias=_iq_bias_from_orm(orm.iq_voltage_bias),
    )


def _acquire_from_orm(orm) -> CalibratableAcquire:
    return CalibratableAcquire(
        delay=orm.delay,
        width=orm.width,
        sync=orm.sync,
        use_weights=orm.use_weights,
    )


def _none_to_nan(value: float | None) -> float:
    return math.nan if value is None else value


def _resonator_from_orm(orm) -> Resonator:
    mpc = orm.pulse_channels.measure
    apc = orm.pulse_channels.acquire
    return Resonator(
        uuid=orm.uuid,
        physical_channel=_physical_channel_from_orm(orm.physical_channel),
        pulse_channels=ResonatorPulseChannels(
            measure=MeasurePulseChannel(
                uuid=mpc.uuid,
                frequency=_none_to_nan(mpc.frequency),
                imbalance=mpc.imbalance,
                phase_iq_offset=mpc.phase_iq_offset,
                scale=complex(mpc.scale_real, mpc.scale_imag),
                pulse=_pulse_from_orm(mpc.pulse),
            ),
            acquire=AcquirePulseChannel(
                uuid=apc.uuid,
                frequency=_none_to_nan(apc.frequency),
                imbalance=apc.imbalance,
                phase_iq_offset=apc.phase_iq_offset,
                scale=complex(apc.scale_real, apc.scale_imag),
                acquire=_acquire_from_orm(apc.acquire),
            ),
        ),
    )


def _qubit_pulse_channels_from_orm(
    container,
    cr_orms,
    crc_orms,
) -> QubitPulseChannels:
    drive_orm = container.drive
    ss_orm = container.second_state
    fs_orm = container.freq_shift

    cross_resonance = {
        cr.auxiliary_qubit: CrossResonancePulseChannel(
            uuid=cr.uuid,
            auxiliary_qubit=cr.auxiliary_qubit,
            frequency=_none_to_nan(cr.frequency),
            imbalance=cr.imbalance,
            phase_iq_offset=cr.phase_iq_offset,
            scale=complex(cr.scale_real, cr.scale_imag),
            zx_pi_4_pulse=_pulse_from_orm(cr.zx_pi_4_pulse) if cr.zx_pi_4_pulse else None,
        )
        for cr in cr_orms
    }

    cross_resonance_cancellation = {
        crc.auxiliary_qubit: CrossResonanceCancellationPulseChannel(
            uuid=crc.uuid,
            auxiliary_qubit=crc.auxiliary_qubit,
            frequency=_none_to_nan(crc.frequency),
            imbalance=crc.imbalance,
            phase_iq_offset=crc.phase_iq_offset,
            scale=complex(crc.scale_real, crc.scale_imag),
        )
        for crc in crc_orms
    }

    return QubitPulseChannels(
        drive=DrivePulseChannel(
            uuid=drive_orm.uuid,
            pulse=_pulse_from_orm(drive_orm.pulse),
            pulse_x_pi=_pulse_from_orm(drive_orm.pulse_x_pi) if drive_orm.pulse_x_pi else None,
        ),
        second_state=SecondStatePulseChannel(
            uuid=ss_orm.uuid,
            frequency=_none_to_nan(ss_orm.frequency),
            imbalance=ss_orm.imbalance,
            phase_iq_offset=ss_orm.phase_iq_offset,
            scale=complex(ss_orm.scale_real, ss_orm.scale_imag),
            active=ss_orm.ss_active,
            delay=ss_orm.ss_delay,
        ),
        freq_shift=FreqShiftPulseChannel(
            uuid=fs_orm.uuid,
            frequency=_none_to_nan(fs_orm.frequency),
            imbalance=fs_orm.imbalance,
            phase_iq_offset=fs_orm.phase_iq_offset,
            scale=complex(fs_orm.scale_real, fs_orm.scale_imag),
            active=fs_orm.fs_active,
            amp=fs_orm.fs_amp,
            phase=fs_orm.fs_phase,
        ),
        cross_resonance_channels=cross_resonance,
        cross_resonance_cancellation_channels=cross_resonance_cancellation,
    )


def _qubit_from_orm(orm) -> tuple[str, Qubit]:
    mean_z = json.loads(orm.mean_z_map_args)
    discriminator = complex(orm.discriminator_real, orm.discriminator_imag)
    pulse_channels = _qubit_pulse_channels_from_orm(
        orm.pulse_channels,
        orm.cross_resonance_channels,
        orm.cross_resonance_cancellation_channels,
    )
    return orm.qubit_key, Qubit(
        uuid=orm.uuid,
        physical_channel=_physical_channel_from_orm(orm.physical_channel),
        pulse_channels=pulse_channels,
        resonator=_resonator_from_orm(orm.resonator),
        mean_z_map_args=mean_z,
        discriminator=discriminator,
        direct_x_pi=orm.direct_x_pi,
    )


def hardware_model_from_orm(orm: HardwareModelORM) -> HardwareModel:
    """Convert a fully-loaded ORM HardwareModelORM back into a Pydantic HardwareModel."""
    qubits = dict(_qubit_from_orm(q) for q in orm.qubits)
    return HardwareModel(
        version=orm.version,
        calibration_id=orm.calibration_id,
        logical_connectivity=json.loads(orm.logical_connectivity),
        qubits=qubits,
    )
