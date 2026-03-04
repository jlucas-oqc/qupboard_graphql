from fastapi.testclient import TestClient

_GRAPHQL_URL = "/graphql"


def test_get_calibration(test_client: TestClient, hardware_model_uuid: str):
    """
    Test that we can retrieve a hardware model calibration by its UUID and that the returned data matches what we
    expect.
    :param test_client: fixture providing a TestClient instance for making requests to the API
    :param hardware_model_uuid: fixture that creates a hardware model and returns its UUID
    :return:
    """
    query = """
        query GetCalibration($id: UUID!) {
            getCalibration(id: $id) {
                id
                version
                calibrationId
                logicalConnectivity
                qubits {
                    edges {
                        node {
                            uuid
                            qubitKey
                            meanZMapArgs
                            discriminatorReal
                            discriminatorImag
                            directXPi
                            physicalChannel {
                                uuid
                                channelKind
                                nameIndex
                                blockSize
                                defaultAmplitude
                                switchBox
                                swapReadoutIq
                                basebandUuid
                                basebandFrequency
                                basebandIfFrequency
                                iqBias
                            }
                            drivePulseChannel {
                                uuid
                                frequency
                                imbalance
                                phaseIqOffset
                                scaleReal
                                scaleImag
                                pulse {
                                    id
                                    waveformType
                                    width
                                    amp
                                    phase
                                    drag
                                    rise
                                    ampSetup
                                    stdDev
                                }
                                pulseXPi {
                                    id
                                    waveformType
                                    width
                                    amp
                                    phase
                                    drag
                                    rise
                                    ampSetup
                                    stdDev
                                }
                            }
                            secondStatePulseChannel {
                                uuid
                                role
                                frequency
                                imbalance
                                phaseIqOffset
                                scaleReal
                                scaleImag
                                ssActive
                                ssDelay
                                fsActive
                                fsAmp
                                fsPhase
                                pulse {
                                    id
                                    waveformType
                                    width
                                    amp
                                    phase
                                    drag
                                    rise
                                    ampSetup
                                    stdDev
                                }
                            }
                            freqShiftPulseChannel {
                                uuid
                                role
                                frequency
                                imbalance
                                phaseIqOffset
                                scaleReal
                                scaleImag
                                ssActive
                                ssDelay
                                fsActive
                                fsAmp
                                fsPhase
                            }
                            resetPulseChannel {
                                uuid
                                resetKind
                                frequency
                                imbalance
                                phaseIqOffset
                                scaleReal
                                scaleImag
                                delay
                                pulse {
                                    id
                                    waveformType
                                    width
                                    amp
                                    phase
                                    drag
                                    rise
                                    ampSetup
                                    stdDev
                                }
                            }
                            crossResonanceChannels {
                                edges {
                                    node {
                                        uuid
                                        role
                                        auxiliaryQubit
                                        frequency
                                        imbalance
                                        phaseIqOffset
                                        scaleReal
                                        scaleImag
                                        zxPi4Pulse {
                                            id
                                            waveformType
                                            width
                                            amp
                                            phase
                                            drag
                                            rise
                                            ampSetup
                                            stdDev
                                        }
                                    }
                                }
                            }
                            crossResonanceCancellationChannels {
                                edges {
                                    node {
                                        uuid
                                        role
                                        auxiliaryQubit
                                        frequency
                                        imbalance
                                        phaseIqOffset
                                        scaleReal
                                        scaleImag
                                    }
                                }
                            }
                            resonator {
                                uuid
                                physicalChannel {
                                    uuid
                                    channelKind
                                    nameIndex
                                    blockSize
                                    defaultAmplitude
                                    switchBox
                                    swapReadoutIq
                                    basebandUuid
                                    basebandFrequency
                                    basebandIfFrequency
                                    iqBias
                                }
                                measurePulseChannel {
                                    uuid
                                    role
                                    frequency
                                    imbalance
                                    phaseIqOffset
                                    scaleReal
                                    scaleImag
                                    pulse {
                                        id
                                        waveformType
                                        width
                                        amp
                                        phase
                                        drag
                                        rise
                                        ampSetup
                                        stdDev
                                    }
                                }
                                acquirePulseChannel {
                                    uuid
                                    role
                                    frequency
                                    imbalance
                                    phaseIqOffset
                                    scaleReal
                                    scaleImag
                                    acquire {
                                        id
                                        delay
                                        width
                                        sync
                                        useWeights
                                    }
                                }
                                resetPulseChannel {
                                    uuid
                                    resetKind
                                    frequency
                                    imbalance
                                    phaseIqOffset
                                    scaleReal
                                    scaleImag
                                    delay
                                    pulse {
                                        id
                                        waveformType
                                        width
                                        amp
                                        phase
                                        drag
                                        rise
                                        ampSetup
                                        stdDev
                                    }
                                }
                            }
                            xPi2Comp {
                                uuid
                                phaseCompXPi2
                            }
                            zxPi4Comps {
                                edges {
                                    node {
                                        uuid
                                        auxiliaryQubit
                                        phaseCompTargetZxPi4
                                        pulseZxPi4TargetRotaryAmp
                                        precompActive
                                        postcompActive
                                        useSecondState
                                        useRotary
                                        pulsePrecomp {
                                            id
                                            waveformType
                                            width
                                            amp
                                            phase
                                            drag
                                            rise
                                            ampSetup
                                            stdDev
                                        }
                                        pulsePostcomp {
                                            id
                                            waveformType
                                            width
                                            amp
                                            phase
                                            drag
                                            rise
                                            ampSetup
                                            stdDev
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
    """
    payload = {
        "query": query,
        "variables": {"id": hardware_model_uuid},
    }

    response = test_client.post(_GRAPHQL_URL, json=payload)

    assert response.status_code == 200
    data = response.json()
    assert "errors" not in data, f"GraphQL errors: {data.get('errors')}"
    calibration = data["data"]["getCalibration"]
    assert calibration is not None
    assert calibration["id"] == hardware_model_uuid

    # Spot-check structure is populated
    qubit_nodes = calibration["qubits"]["edges"]
    assert len(qubit_nodes) > 0

    first_qubit = qubit_nodes[0]["node"]
    drive = first_qubit["drivePulseChannel"]
    assert drive["frequency"] is not None
    assert drive["pulse"] is not None

    second_state = first_qubit["secondStatePulseChannel"]
    assert second_state["pulse"] is not None

    qubit_reset = first_qubit["resetPulseChannel"]
    assert qubit_reset["resetKind"] == "qubit"
    assert qubit_reset["pulse"] is not None

    resonator_reset = first_qubit["resonator"]["resetPulseChannel"]
    assert resonator_reset["resetKind"] == "resonator"
    assert resonator_reset["pulse"] is not None

    assert first_qubit["xPi2Comp"] is not None
    assert len(first_qubit["zxPi4Comps"]["edges"]) > 0


def test_get_all_hardware_model_ids(test_client: TestClient, hardware_model_uuid: str):
    """
    Test that we can retrieve a list of all hardware model UUIDs and that it contains the UUID of the model we created.
    :param test_client: fixture providing a TestClient instance for making requests to the API
    :param hardware_model_uuid: fixture that creates a hardware model and returns its UUID
    :return:
    """
    query = """
        query {
            getAllHardwareModelIds
        }
    """
    response = test_client.post(_GRAPHQL_URL, json={"query": query})

    assert response.status_code == 200
    data = response.json()
    assert "errors" not in data, f"GraphQL errors: {data.get('errors')}"
    ids = data["data"]["getAllHardwareModelIds"]
    assert isinstance(ids, list)
    assert hardware_model_uuid in ids
