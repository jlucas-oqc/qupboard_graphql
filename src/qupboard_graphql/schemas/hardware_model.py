import math
from uuid import UUID

from pydantic import BaseModel, Field


class Component(BaseModel):
    uuid: UUID


class BaseBand(Component):
    frequency: float
    if_frequency: float


class IQVoltageBias(BaseModel):
    bias: str


class PhysicalChannel(Component):
    name_index: int
    baseband: BaseBand
    block_size: int
    iq_voltage_bias: IQVoltageBias
    default_amplitude: int
    switch_box: str
    swap_readout_iq: bool = False


class CalibratablePulse(BaseModel):
    waveform_type: str
    width: float
    amp: float = 0.25 / (100e-9 * 1.0 / 3.0 * math.pi**0.5)
    phase: float = 0.0
    drag: float = 0.0
    rise: float = 1.0 / 3.0
    amp_setup: float = 0.0
    std_dev: float = 0.0


class DrivePulseChannel(Component):
    pulse: CalibratablePulse
    pulse_x_pi: CalibratablePulse | None


class PulseChannel(Component):
    frequency: float = math.nan
    imbalance: float = 1.0
    phase_iq_offset: float = 0.0
    scale: complex | float = 1.0 + 0.0j


class QubitPulseChannel(PulseChannel): ...


class SecondStatePulseChannel(QubitPulseChannel):
    active: bool = False
    delay: float = 0.0


class FreqShiftPulseChannel(QubitPulseChannel):
    active: bool = False
    amp: float = 1.0
    phase: float = 0.0


class CrossResonancePulseChannel(QubitPulseChannel):
    auxiliary_qubit: int
    zx_pi_4_pulse: CalibratablePulse | None


class CrossResonanceCancellationPulseChannel(QubitPulseChannel):
    auxiliary_qubit: int


class QubitPulseChannels(BaseModel):
    drive: DrivePulseChannel
    second_state: SecondStatePulseChannel
    freq_shift: FreqShiftPulseChannel

    cross_resonance_channels: dict[int, CrossResonancePulseChannel]
    cross_resonance_cancellation_channels: dict[int, CrossResonanceCancellationPulseChannel]


class ResonatorPulseChannel(PulseChannel): ...


class MeasurePulseChannel(ResonatorPulseChannel):
    pulse: CalibratablePulse


class CalibratableAcquire(BaseModel):
    delay: float = Field(default=180e-08, ge=0)
    width: float = Field(default=1e-06, ge=0)
    sync: bool = True
    use_weights: bool = False


class AcquirePulseChannel(ResonatorPulseChannel):
    acquire: CalibratableAcquire = Field(default=CalibratableAcquire(), frozen=True)


class MeasureAcquirePulseChannel(MeasurePulseChannel, AcquirePulseChannel): ...


class ResonatorPulseChannels(BaseModel):
    measure: MeasurePulseChannel
    acquire: AcquirePulseChannel


class Resonator(Component):
    physical_channel: PhysicalChannel
    pulse_channels: ResonatorPulseChannels


class Qubit(BaseModel):
    uuid: UUID

    physical_channel: PhysicalChannel
    pulse_channels: QubitPulseChannels
    resonator: Resonator

    mean_z_map_args: list[complex | float] = Field(max_length=2, default=[1.0, 0.0])
    discriminator: complex | float = 0.0

    direct_x_pi: bool = False


class HardwareModel(BaseModel):
    version: str
    logical_connectivity: dict[str, list[int]]
    calibration_id: str
    qubits: dict[str, Qubit]
