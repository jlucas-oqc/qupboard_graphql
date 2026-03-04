"""
Utilities for converting Pydantic HardwareModel ↔ SQLAlchemy ORM instances.
"""

import json
import math

from qupboard_graphql.schemas.hardware_model import (
    AcquirePulseChannel,
    CalibratableAcquire,
    CalibratablePulse,
    CrossResonanceCancellationPulseChannel,
    CrossResonancePulseChannel,
    DrivePulseChannel,
    FreqShiftPulseChannel,
    HardwareModel,
    MeasurePulseChannel,
    PhysicalChannel,
    Qubit,
    QubitPulseChannels,
    Resonator,
    ResetPulseChannel,
    ResonatorPulseChannels,
    SecondStatePulseChannel,
    XPi2Comp,
    ZxPi4Comp,
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


def _pulse_orm(pulse: CalibratablePulse, owner_uuid, pulse_role: str) -> CalibratablePulseORM:
    return CalibratablePulseORM(
        owner_uuid=owner_uuid,
        pulse_role=pulse_role,
        waveform_type=pulse.waveform_type,
        width=pulse.width,
        amp=pulse.amp,
        phase=pulse.phase,
        drag=pulse.drag,
        rise=pulse.rise,
        amp_setup=pulse.amp_setup,
        std_dev=pulse.std_dev,
    )


def _physical_channel_orm(pc: PhysicalChannel) -> PhysicalChannelORM:
    return PhysicalChannelORM(
        uuid=pc.uuid,
        channel_kind="qubit",
        name_index=pc.name_index,
        block_size=pc.block_size,
        default_amplitude=pc.default_amplitude,
        switch_box=pc.switch_box,
        baseband_uuid=pc.baseband.uuid,
        baseband_frequency=pc.baseband.frequency,
        baseband_if_frequency=pc.baseband.if_frequency,
        iq_bias=pc.iq_voltage_bias.bias,
    )


def _resonator_physical_channel_orm(rpc: PhysicalChannel) -> PhysicalChannelORM:
    return PhysicalChannelORM(
        uuid=rpc.uuid,
        channel_kind="resonator",
        name_index=rpc.name_index,
        block_size=rpc.block_size,
        default_amplitude=rpc.default_amplitude,
        switch_box=rpc.switch_box,
        swap_readout_iq=rpc.swap_readout_iq,
        baseband_uuid=rpc.baseband.uuid,
        baseband_frequency=rpc.baseband.frequency,
        baseband_if_frequency=rpc.baseband.if_frequency,
        iq_bias=rpc.iq_voltage_bias.bias,
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


def _reset_pulse_channel_orm(rpc: ResetPulseChannel, reset_kind: str) -> ResetPulseChannelORM:
    real, imag = _scale_parts(rpc.scale)
    orm = ResetPulseChannelORM(
        uuid=rpc.uuid,
        reset_kind=reset_kind,
        frequency=_nan_to_none(rpc.frequency),
        imbalance=rpc.imbalance,
        phase_iq_offset=rpc.phase_iq_offset,
        scale_real=real,
        scale_imag=imag,
        delay=rpc.delay,
    )
    pulse_role = "reset_qubit" if reset_kind == "qubit" else "reset_resonator"
    orm.pulse = _pulse_orm(rpc.pulse, rpc.uuid, pulse_role)
    return orm


def _measure_pulse_channel_orm(mpc: MeasurePulseChannel) -> ResonatorPulseChannelORM:
    real, imag = _scale_parts(mpc.scale)
    orm = ResonatorPulseChannelORM(
        uuid=mpc.uuid,
        role="measure",
        frequency=mpc.frequency,
        imbalance=mpc.imbalance,
        phase_iq_offset=mpc.phase_iq_offset,
        scale_real=real,
        scale_imag=imag,
    )
    orm.pulse = _pulse_orm(mpc.pulse, mpc.uuid, "measure")
    return orm


def _acquire_pulse_channel_orm(apc: AcquirePulseChannel) -> ResonatorPulseChannelORM:
    real, imag = _scale_parts(apc.scale)
    return ResonatorPulseChannelORM(
        uuid=apc.uuid,
        role="acquire",
        frequency=apc.frequency,
        imbalance=apc.imbalance,
        phase_iq_offset=apc.phase_iq_offset,
        scale_real=real,
        scale_imag=imag,
        acq_delay=apc.acquire.delay,
        acq_width=apc.acquire.width,
        acq_sync=apc.acquire.sync,
        acq_use_weights=apc.acquire.use_weights,
    )


def _resonator_orm(resonator: Resonator) -> ResonatorORM:
    return ResonatorORM(
        uuid=resonator.uuid,
        physical_channel=_resonator_physical_channel_orm(resonator.physical_channel),
        measure_pulse_channel=_measure_pulse_channel_orm(resonator.pulse_channels.measure),
        acquire_pulse_channel=_acquire_pulse_channel_orm(resonator.pulse_channels.acquire),
        reset_pulse_channel=_reset_pulse_channel_orm(resonator.pulse_channels.reset, "resonator"),
    )


def _zx_pi4_comp_orm(auxiliary_qubit: int, comp: ZxPi4Comp) -> ZxPi4CompORM:
    orm = ZxPi4CompORM(
        auxiliary_qubit=auxiliary_qubit,
        phase_comp_target_zx_pi_4=comp.phase_comp_target_zx_pi_4,
        pulse_zx_pi_4_target_rotary_amp=comp.pulse_zx_pi_4_target_rotary_amp,
        precomp_active=comp.precomp_active,
        postcomp_active=comp.postcomp_active,
        use_second_state=comp.use_second_state,
        use_rotary=comp.use_rotary,
    )
    # UUID is generated by default=uuid4; we need it set before building pulses
    from uuid import uuid4 as _uuid4

    if orm.uuid is None:
        orm.uuid = _uuid4()
    if comp.pulse_precomp_target_zx_pi_4:
        orm.pulse_precomp = _pulse_orm(comp.pulse_precomp_target_zx_pi_4, orm.uuid, "zx_precomp")
    if comp.pulse_postcomp_target_zx_pi_4:
        orm.pulse_postcomp = _pulse_orm(comp.pulse_postcomp_target_zx_pi_4, orm.uuid, "zx_postcomp")
    return orm


def _qubit_pulse_channels_orm(
    qubit_pulse_channels,
    cross_resonance: dict[int, CrossResonancePulseChannel],
    cross_resonance_cancellation: dict[int, CrossResonanceCancellationPulseChannel],
) -> tuple[
    DrivePulseChannelORM,
    QubitPulseChannelORM,
    QubitPulseChannelORM,
    ResetPulseChannelORM,
    list[CrossResonanceChannelORM],
    list[CrossResonanceChannelORM],
]:
    drive = qubit_pulse_channels.drive
    drive_real, drive_imag = _scale_parts(drive.scale)
    drive_orm = DrivePulseChannelORM(
        uuid=drive.uuid,
        frequency=_nan_to_none(drive.frequency),
        imbalance=drive.imbalance,
        phase_iq_offset=drive.phase_iq_offset,
        scale_real=drive_real,
        scale_imag=drive_imag,
    )
    drive_orm.pulse = _pulse_orm(drive.pulse, drive.uuid, "drive")
    if drive.pulse_x_pi is not None:
        drive_orm.pulse_x_pi = _pulse_orm(drive.pulse_x_pi, drive.uuid, "drive_x_pi")

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
    if ss.pulse is not None:
        ss_orm.pulse = _pulse_orm(ss.pulse, ss.uuid, "second_state")

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

    reset_orm = _reset_pulse_channel_orm(qubit_pulse_channels.reset, "qubit")

    cr_orms: list[CrossResonanceChannelORM] = []
    for aux_idx, cr in cross_resonance.items():
        cr_real, cr_imag = _scale_parts(cr.scale)
        cr_row = CrossResonanceChannelORM(
            uuid=cr.uuid,
            role="cr",
            auxiliary_qubit=cr.auxiliary_qubit,
            frequency=cr.frequency,
            imbalance=cr.imbalance,
            phase_iq_offset=cr.phase_iq_offset,
            scale_real=cr_real,
            scale_imag=cr_imag,
        )
        if cr.zx_pi_4_pulse is not None:
            cr_row.zx_pi_4_pulse = _pulse_orm(cr.zx_pi_4_pulse, cr.uuid, "cr")
        cr_orms.append(cr_row)

    crc_orms: list[CrossResonanceChannelORM] = []
    for aux_idx, crc in cross_resonance_cancellation.items():
        crc_real, crc_imag = _scale_parts(crc.scale)
        crc_orms.append(
            CrossResonanceChannelORM(
                uuid=crc.uuid,
                role="crc",
                auxiliary_qubit=crc.auxiliary_qubit,
                frequency=crc.frequency,
                imbalance=crc.imbalance,
                phase_iq_offset=crc.phase_iq_offset,
                scale_real=crc_real,
                scale_imag=crc_imag,
            )
        )

    return drive_orm, ss_orm, fs_orm, reset_orm, cr_orms, crc_orms


def _qubit_orm(qubit_key: str, qubit: Qubit) -> QubitORM:
    discriminator_real, discriminator_imag = _scale_parts(qubit.discriminator)

    drive_orm, ss_orm, fs_orm, reset_orm, cr_orms, crc_orms = _qubit_pulse_channels_orm(
        qubit.pulse_channels,
        qubit.pulse_channels.cross_resonance_channels,
        qubit.pulse_channels.cross_resonance_cancellation_channels,
    )

    zx_pi_4_comp_orms = [_zx_pi4_comp_orm(aux_idx, comp) for aux_idx, comp in qubit.zx_pi_4_comp.items()]

    return QubitORM(
        uuid=qubit.uuid,
        qubit_key=qubit_key,
        mean_z_map_args=json.dumps([v.real if isinstance(v, complex) else v for v in qubit.mean_z_map_args]),
        discriminator_real=discriminator_real,
        discriminator_imag=discriminator_imag,
        direct_x_pi=qubit.direct_x_pi,
        phase_comp_x_pi_2=qubit.x_pi_2_comp.phase_comp_x_pi_2,
        physical_channel=_physical_channel_orm(qubit.physical_channel),
        drive_pulse_channel=drive_orm,
        second_state_pulse_channel=ss_orm,
        freq_shift_pulse_channel=fs_orm,
        reset_pulse_channel=reset_orm,
        resonator=_resonator_orm(qubit.resonator),
        cross_resonance_channels=cr_orms,
        cross_resonance_cancellation_channels=crc_orms,
        zx_pi_4_comps=zx_pi_4_comp_orms,
    )


def hardware_model_to_orm(model: HardwareModel) -> HardwareModelORM:
    """Convert a validated Pydantic HardwareModel into a fully-populated ORM tree."""
    qubit_orms = [_qubit_orm(key, qubit) for key, qubit in model.qubits.items()]
    return HardwareModelORM(
        version=model.version,
        calibration_id=model.calibration_id,
        logical_connectivity=model.logical_connectivity,
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


def _physical_channel_from_orm(orm: PhysicalChannelORM) -> PhysicalChannel:
    from qupboard_graphql.schemas.hardware_model import BaseBand, IQVoltageBias

    return PhysicalChannel(
        uuid=orm.uuid,
        name_index=orm.name_index,
        block_size=orm.block_size,
        default_amplitude=orm.default_amplitude,
        switch_box=orm.switch_box,
        swap_readout_iq=orm.swap_readout_iq,
        baseband=BaseBand(
            uuid=orm.baseband_uuid,
            frequency=orm.baseband_frequency,
            if_frequency=orm.baseband_if_frequency,
        ),
        iq_voltage_bias=IQVoltageBias(bias=orm.iq_bias),
    )


def _none_to_nan(value: float | None) -> float:
    return math.nan if value is None else value


def _reset_pulse_channel_from_orm(orm: ResetPulseChannelORM) -> ResetPulseChannel:
    return ResetPulseChannel(
        uuid=orm.uuid,
        frequency=_none_to_nan(orm.frequency),
        imbalance=orm.imbalance,
        phase_iq_offset=orm.phase_iq_offset,
        scale=complex(orm.scale_real, orm.scale_imag),
        delay=orm.delay,
        pulse=_pulse_from_orm(orm.pulse),
    )


def _resonator_from_orm(orm: ResonatorORM) -> Resonator:
    mpc = orm.measure_pulse_channel
    apc = orm.acquire_pulse_channel
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
                acquire=CalibratableAcquire(
                    delay=apc.acq_delay,
                    width=apc.acq_width,
                    sync=apc.acq_sync,
                    use_weights=apc.acq_use_weights,
                ),
            ),
            reset=_reset_pulse_channel_from_orm(orm.reset_pulse_channel),
        ),
    )


def _qubit_pulse_channels_from_orm(
    qubit_orm: QubitORM,
    cr_orms,
    crc_orms,
) -> QubitPulseChannels:
    drive_orm = qubit_orm.drive_pulse_channel
    ss_orm = qubit_orm.second_state_pulse_channel
    fs_orm = qubit_orm.freq_shift_pulse_channel

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
            frequency=_none_to_nan(drive_orm.frequency),
            imbalance=drive_orm.imbalance,
            phase_iq_offset=drive_orm.phase_iq_offset,
            scale=complex(drive_orm.scale_real, drive_orm.scale_imag),
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
            pulse=_pulse_from_orm(ss_orm.pulse) if ss_orm.pulse else None,
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
        reset=_reset_pulse_channel_from_orm(qubit_orm.reset_pulse_channel),
        cross_resonance_channels=cross_resonance,
        cross_resonance_cancellation_channels=cross_resonance_cancellation,
    )


def _qubit_from_orm(orm: QubitORM) -> tuple[str, Qubit]:
    mean_z = json.loads(orm.mean_z_map_args)
    discriminator = complex(orm.discriminator_real, orm.discriminator_imag)
    pulse_channels = _qubit_pulse_channels_from_orm(
        orm,
        orm.cross_resonance_channels,
        orm.cross_resonance_cancellation_channels,
    )

    zx_pi_4_comp = {
        comp.auxiliary_qubit: ZxPi4Comp(
            pulse_precomp_target_zx_pi_4=_pulse_from_orm(comp.pulse_precomp) if comp.pulse_precomp else None,
            pulse_postcomp_target_zx_pi_4=_pulse_from_orm(comp.pulse_postcomp) if comp.pulse_postcomp else None,
            phase_comp_target_zx_pi_4=comp.phase_comp_target_zx_pi_4,
            pulse_zx_pi_4_target_rotary_amp=comp.pulse_zx_pi_4_target_rotary_amp,
            precomp_active=comp.precomp_active,
            postcomp_active=comp.postcomp_active,
            use_second_state=comp.use_second_state,
            use_rotary=comp.use_rotary,
        )
        for comp in orm.zx_pi_4_comps
    }

    x_pi_2_comp = XPi2Comp(phase_comp_x_pi_2=orm.phase_comp_x_pi_2)

    return orm.qubit_key, Qubit(
        uuid=orm.uuid,
        physical_channel=_physical_channel_from_orm(orm.physical_channel),
        pulse_channels=pulse_channels,
        resonator=_resonator_from_orm(orm.resonator),
        mean_z_map_args=mean_z,
        discriminator=discriminator,
        direct_x_pi=orm.direct_x_pi,
        x_pi_2_comp=x_pi_2_comp,
        zx_pi_4_comp=zx_pi_4_comp,
    )


def hardware_model_from_orm(orm: HardwareModelORM) -> HardwareModel:
    """Convert a fully-loaded ORM HardwareModelORM back into a Pydantic HardwareModel."""
    qubits = dict(_qubit_from_orm(q) for q in orm.qubits)
    return HardwareModel(
        version=orm.version,
        calibration_id=orm.calibration_id,
        logical_connectivity=orm.logical_connectivity,
        qubits=qubits,
    )
