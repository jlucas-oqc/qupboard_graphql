"""
Utilities for converting Pydantic HardwareModel ↔ SQLAlchemy ORM instances.
"""

import json
import math
from uuid import uuid4

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
    HardwareModelORM,
    PhysicalChannelORM,
    PulseChannelORM,
    QubitORM,
    ResonatorORM,
    ZxPi4CompORM,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


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


def _scale_parts(scale) -> tuple[float, float]:
    """Return (real, imag) from a complex or float scale value."""
    if isinstance(scale, complex):
        return scale.real, scale.imag
    return float(scale), 0.0


def _nan_to_none(value: float) -> float | None:
    """Convert NaN to None for SQL NULL storage."""
    if value is None:
        return None
    try:
        return None if math.isnan(value) else value
    except (TypeError, ValueError):
        return value


def _none_to_nan(value: float | None) -> float:
    return math.nan if value is None else value


def _pulse_channel_orm(
    uuid,
    channel_role: str,
    frequency,
    imbalance,
    phase_iq_offset,
    scale,
    qubit_uuid=None,
    resonator_uuid=None,
    **extras,
) -> PulseChannelORM:
    """Build a PulseChannelORM row from common fields + role-specific extras."""
    real, imag = _scale_parts(scale)
    return PulseChannelORM(
        uuid=uuid,
        channel_role=channel_role,
        frequency=_nan_to_none(frequency),
        imbalance=imbalance,
        phase_iq_offset=phase_iq_offset,
        scale_real=real,
        scale_imag=imag,
        qubit_uuid=qubit_uuid,
        resonator_uuid=resonator_uuid,
        **extras,
    )


# ---------------------------------------------------------------------------
# Pydantic → ORM
# ---------------------------------------------------------------------------


def _physical_channel_orm(pc: PhysicalChannel, owner_uuid, owner_kind: str) -> PhysicalChannelORM:
    """owner_kind: 'qubit' | 'resonator'"""
    return PhysicalChannelORM(
        uuid=pc.uuid,
        channel_kind=owner_kind,
        name_index=pc.name_index,
        block_size=pc.block_size,
        default_amplitude=pc.default_amplitude,
        switch_box=pc.switch_box,
        swap_readout_iq=pc.swap_readout_iq,
        baseband_uuid=pc.baseband.uuid,
        baseband_frequency=pc.baseband.frequency,
        baseband_if_frequency=pc.baseband.if_frequency,
        iq_bias=pc.iq_voltage_bias.bias,
        qubit_uuid=owner_uuid if owner_kind == "qubit" else None,
        resonator_uuid=owner_uuid if owner_kind == "resonator" else None,
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
    if orm.uuid is None:
        orm.uuid = uuid4()
    if comp.pulse_precomp_target_zx_pi_4:
        orm.pulse_precomp = _pulse_orm(comp.pulse_precomp_target_zx_pi_4, orm.uuid, "zx_precomp")
    if comp.pulse_postcomp_target_zx_pi_4:
        orm.pulse_postcomp = _pulse_orm(comp.pulse_postcomp_target_zx_pi_4, orm.uuid, "zx_postcomp")
    return orm


def _qubit_orm(qubit_key: str, qubit: Qubit) -> QubitORM:
    discriminator_real, discriminator_imag = _scale_parts(qubit.discriminator)
    qid = qubit.uuid
    pc = qubit.pulse_channels
    res = qubit.resonator

    # Drive channel
    drive = pc.drive
    drive_orm = _pulse_channel_orm(
        drive.uuid, "drive", drive.frequency, drive.imbalance, drive.phase_iq_offset, drive.scale, qubit_uuid=qid
    )
    drive_orm.pulse = _pulse_orm(drive.pulse, drive.uuid, "drive")
    if drive.pulse_x_pi is not None:
        drive_orm.pulse_x_pi = _pulse_orm(drive.pulse_x_pi, drive.uuid, "drive_x_pi")

    # Second-state channel
    ss = pc.second_state
    ss_orm = _pulse_channel_orm(
        ss.uuid,
        "second_state",
        ss.frequency,
        ss.imbalance,
        ss.phase_iq_offset,
        ss.scale,
        qubit_uuid=qid,
        ss_active=ss.active,
        ss_delay=ss.delay,
    )
    if ss.pulse is not None:
        ss_orm.pulse = _pulse_orm(ss.pulse, ss.uuid, "second_state")

    # Freq-shift channel
    fs = pc.freq_shift
    fs_orm = _pulse_channel_orm(
        fs.uuid,
        "freq_shift",
        fs.frequency,
        fs.imbalance,
        fs.phase_iq_offset,
        fs.scale,
        qubit_uuid=qid,
        fs_active=fs.active,
        fs_amp=fs.amp,
        fs_phase=fs.phase,
    )

    # Qubit reset channel
    qreset = pc.reset
    qreset_orm = _pulse_channel_orm(
        qreset.uuid,
        "reset_qubit",
        qreset.frequency,
        qreset.imbalance,
        qreset.phase_iq_offset,
        qreset.scale,
        qubit_uuid=qid,
        reset_delay=qreset.delay,
    )
    qreset_orm.pulse = _pulse_orm(qreset.pulse, qreset.uuid, "reset_qubit")

    # Resonator
    res_id = res.uuid

    # Measure channel
    mpc = res.pulse_channels.measure
    mpc_orm = _pulse_channel_orm(
        mpc.uuid, "measure", mpc.frequency, mpc.imbalance, mpc.phase_iq_offset, mpc.scale, resonator_uuid=res_id
    )
    mpc_orm.pulse = _pulse_orm(mpc.pulse, mpc.uuid, "measure")

    # Acquire channel
    apc = res.pulse_channels.acquire
    apc_orm = _pulse_channel_orm(
        apc.uuid,
        "acquire",
        apc.frequency,
        apc.imbalance,
        apc.phase_iq_offset,
        apc.scale,
        resonator_uuid=res_id,
        acq_delay=apc.acquire.delay,
        acq_width=apc.acquire.width,
        acq_sync=apc.acquire.sync,
        acq_use_weights=apc.acquire.use_weights,
    )

    # Resonator reset channel
    rreset = res.pulse_channels.reset
    rreset_orm = _pulse_channel_orm(
        rreset.uuid,
        "reset_resonator",
        rreset.frequency,
        rreset.imbalance,
        rreset.phase_iq_offset,
        rreset.scale,
        resonator_uuid=res_id,
        reset_delay=rreset.delay,
    )
    rreset_orm.pulse = _pulse_orm(rreset.pulse, rreset.uuid, "reset_resonator")

    resonator_orm = ResonatorORM(
        uuid=res_id,
        qubit_uuid=qid,
        physical_channel=_physical_channel_orm(res.physical_channel, res_id, "resonator"),
        pulse_channels=[mpc_orm, apc_orm, rreset_orm],
    )

    # CR / CRC channels
    cr_orms = []
    for _, cr in pc.cross_resonance_channels.items():
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

    crc_orms = []
    for _, crc in pc.cross_resonance_cancellation_channels.items():
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

    zx_pi_4_comp_orms = [_zx_pi4_comp_orm(aux, comp) for aux, comp in qubit.zx_pi_4_comp.items()]

    return QubitORM(
        uuid=qid,
        qubit_key=qubit_key,
        mean_z_map_args=json.dumps([v.real if isinstance(v, complex) else v for v in qubit.mean_z_map_args]),
        discriminator_real=discriminator_real,
        discriminator_imag=discriminator_imag,
        direct_x_pi=qubit.direct_x_pi,
        phase_comp_x_pi_2=qubit.x_pi_2_comp.phase_comp_x_pi_2,
        physical_channel=_physical_channel_orm(qubit.physical_channel, qid, "qubit"),
        pulse_channels=[drive_orm, ss_orm, fs_orm, qreset_orm],
        resonator=resonator_orm,
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


def _reset_pulse_channel_from_orm(orm: PulseChannelORM) -> ResetPulseChannel:
    return ResetPulseChannel(
        uuid=orm.uuid,
        frequency=_none_to_nan(orm.frequency),
        imbalance=orm.imbalance,
        phase_iq_offset=orm.phase_iq_offset,
        scale=complex(orm.scale_real, orm.scale_imag),
        delay=orm.reset_delay,
        pulse=_pulse_from_orm(orm.pulse),
    )


def _qubit_from_orm(orm: QubitORM) -> tuple[str, Qubit]:
    mean_z = json.loads(orm.mean_z_map_args)
    discriminator = complex(orm.discriminator_real, orm.discriminator_imag)

    qubit_pc = _physical_channel_from_orm(orm.physical_channel)
    res_pc = _physical_channel_from_orm(orm.resonator.physical_channel)

    drive = orm.drive_channel
    ss = orm.second_state_channel
    fs = orm.freq_shift_channel
    mpc = orm.resonator.measure_channel
    apc = orm.resonator.acquire_channel

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
        for cr in orm.cross_resonance_channels
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
        for crc in orm.cross_resonance_cancellation_channels
    }

    pulse_channels = QubitPulseChannels(
        drive=DrivePulseChannel(
            uuid=drive.uuid,
            frequency=_none_to_nan(drive.frequency),
            imbalance=drive.imbalance,
            phase_iq_offset=drive.phase_iq_offset,
            scale=complex(drive.scale_real, drive.scale_imag),
            pulse=_pulse_from_orm(drive.pulse),
            pulse_x_pi=_pulse_from_orm(drive.pulse_x_pi) if drive.pulse_x_pi else None,
        ),
        second_state=SecondStatePulseChannel(
            uuid=ss.uuid,
            frequency=_none_to_nan(ss.frequency),
            imbalance=ss.imbalance,
            phase_iq_offset=ss.phase_iq_offset,
            scale=complex(ss.scale_real, ss.scale_imag),
            active=ss.ss_active,
            delay=ss.ss_delay,
            pulse=_pulse_from_orm(ss.pulse) if ss.pulse else None,
        ),
        freq_shift=FreqShiftPulseChannel(
            uuid=fs.uuid,
            frequency=_none_to_nan(fs.frequency),
            imbalance=fs.imbalance,
            phase_iq_offset=fs.phase_iq_offset,
            scale=complex(fs.scale_real, fs.scale_imag),
            active=fs.fs_active,
            amp=fs.fs_amp,
            phase=fs.fs_phase,
        ),
        reset=_reset_pulse_channel_from_orm(orm.reset_qubit_channel),
        cross_resonance_channels=cross_resonance,
        cross_resonance_cancellation_channels=cross_resonance_cancellation,
    )

    resonator = Resonator(
        uuid=orm.resonator.uuid,
        physical_channel=res_pc,
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
            reset=_reset_pulse_channel_from_orm(orm.resonator.reset_resonator_channel),
        ),
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

    return orm.qubit_key, Qubit(
        uuid=orm.uuid,
        physical_channel=qubit_pc,
        pulse_channels=pulse_channels,
        resonator=resonator,
        mean_z_map_args=mean_z,
        discriminator=discriminator,
        direct_x_pi=orm.direct_x_pi,
        x_pi_2_comp=XPi2Comp(phase_comp_x_pi_2=orm.phase_comp_x_pi_2),
        zx_pi_4_comp=zx_pi_4_comp,
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
