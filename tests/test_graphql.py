from fastapi.testclient import TestClient

_GRAPHQL_URL = "/graphql"


def test_get_calibration(test_client: TestClient, hardware_model_uuid: str):
    """
    Test that we can retrieve a hardware model calibration by its UUID and that the returned data matches what we
    expect.
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
                            phaseCompXPi2
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
                                pulseChannels {
                                    edges {
                                        node {
                                            uuid
                                            channelRole
                                            frequency
                                        }
                                    }
                                }
                            }
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
                            pulseChannels {
                                edges {
                                    node {
                                        uuid
                                        channelRole
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
                                        acqDelay
                                        acqWidth
                                        acqSync
                                        acqUseWeights
                                        resetDelay
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
                                        }
                                    }
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
                                        }
                                        pulsePostcomp {
                                            id
                                            waveformType
                                            width
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

    qubit_nodes = calibration["qubits"]["edges"]
    assert len(qubit_nodes) > 0

    first_qubit = qubit_nodes[0]["node"]

    channels_by_role = {n["node"]["channelRole"]: n["node"] for n in first_qubit["pulseChannels"]["edges"]}

    drive = channels_by_role["drive"]
    assert drive["frequency"] is not None
    assert drive["pulse"] is not None

    second_state = channels_by_role["second_state"]
    assert second_state["pulse"] is not None

    reset_qubit = channels_by_role["reset_qubit"]
    assert reset_qubit["pulse"] is not None

    assert first_qubit["phaseCompXPi2"] is not None
    assert first_qubit["resonator"] is not None
    assert first_qubit["resonator"]["uuid"] is not None
    assert first_qubit["resonator"]["physicalChannel"] is not None
    res_pc_kinds = {n["node"]["channelRole"] for n in first_qubit["resonator"]["pulseChannels"]["edges"]}
    assert res_pc_kinds == {"measure", "acquire", "reset_resonator"}
    assert len(first_qubit["zxPi4Comps"]["edges"]) > 0

    # Qubit physical channel
    assert first_qubit["physicalChannel"] is not None
    assert first_qubit["physicalChannel"]["channelKind"] == "qubit"


def test_cross_resonance_channels_are_filtered_by_role(test_client: TestClient, hardware_model_uuid: str):
    """
    Regression test: querying crossResonanceCancellationChannels should only return items
    with role='crc', and crossResonanceChannels should only return items with role='cr'.

    Previously, strawberry-sqlalchemy-mapper's DataLoader only applied the FK join
    condition (qubit_uuid) and ignored the primaryjoin role filter, causing both
    collections to return all cross-resonance channel rows regardless of role.
    """
    query = """
        query GetCalibration($id: UUID!) {
            getCalibration(id: $id) {
                qubits {
                    edges {
                        node {
                            qubitKey
                            crossResonanceChannels {
                                edges { node { uuid role auxiliaryQubit } }
                            }
                            crossResonanceCancellationChannels {
                                edges { node { uuid role auxiliaryQubit } }
                            }
                        }
                    }
                }
            }
        }
    """
    response = test_client.post(_GRAPHQL_URL, json={"query": query, "variables": {"id": hardware_model_uuid}})
    assert response.status_code == 200
    data = response.json()
    assert "errors" not in data, f"GraphQL errors: {data.get('errors')}"

    qubits = data["data"]["getCalibration"]["qubits"]["edges"]
    assert len(qubits) > 0

    for qubit_edge in qubits:
        node = qubit_edge["node"]
        qubit_key = node["qubitKey"]

        cr_roles = [e["node"]["role"] for e in node["crossResonanceChannels"]["edges"]]
        crc_roles = [e["node"]["role"] for e in node["crossResonanceCancellationChannels"]["edges"]]

        assert all(r == "cr" for r in cr_roles), (
            f"Qubit {qubit_key}: crossResonanceChannels contains non-cr items: {cr_roles}"
        )
        assert all(r == "crc" for r in crc_roles), (
            f"Qubit {qubit_key}: crossResonanceCancellationChannels contains non-crc items: {crc_roles}"
        )


def test_pulse_roles_are_correctly_filtered(test_client: TestClient, hardware_model_uuid: str):
    """
    Regression test: pulse sub-fields on pulseChannels, crossResonanceChannels, and zxPi4Comps
    must return the pulse with the correct pulse_role and never be swapped.

    Previously, strawberry-sqlalchemy-mapper's DataLoader only filtered by owner_uuid,
    ignoring the pulse_role discriminator in primaryjoin, so e.g. pulse and pulse_x_pi
    could return the same (wrong) CalibratablePulse row.
    """
    query = """
        query GetCalibration($id: UUID!) {
            getCalibration(id: $id) {
                qubits {
                    edges {
                        node {
                            qubitKey
                            pulseChannels {
                                edges {
                                    node {
                                        channelRole
                                        pulse { id pulseRole }
                                        pulseXPi { id pulseRole }
                                    }
                                }
                            }
                            crossResonanceChannels {
                                edges {
                                    node {
                                        role
                                        zxPi4Pulse { id pulseRole }
                                    }
                                }
                            }
                            zxPi4Comps {
                                edges {
                                    node {
                                        uuid
                                        pulsePrecomp { id pulseRole }
                                        pulsePostcomp { id pulseRole }
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
    """
    response = test_client.post(_GRAPHQL_URL, json={"query": query, "variables": {"id": hardware_model_uuid}})
    assert response.status_code == 200
    data = response.json()
    assert "errors" not in data, f"GraphQL errors: {data.get('errors')}"

    _PULSE_ROLES = {"drive", "second_state", "measure", "reset_qubit", "reset_resonator"}

    for qubit_edge in data["data"]["getCalibration"]["qubits"]["edges"]:
        node = qubit_edge["node"]
        key = node["qubitKey"]

        for pc_edge in node["pulseChannels"]["edges"]:
            pc = pc_edge["node"]
            role = pc["channelRole"]
            if pc["pulse"] is not None:
                assert pc["pulse"]["pulseRole"] in _PULSE_ROLES, (
                    f"Qubit {key}, channel {role}: pulse.pulseRole={pc['pulse']['pulseRole']!r} not in expected set"
                )
            if pc["pulseXPi"] is not None:
                assert pc["pulseXPi"]["pulseRole"] == "drive_x_pi", (
                    f"Qubit {key}, channel {role}: pulseXPi.pulseRole={pc['pulseXPi']['pulseRole']!r} != 'drive_x_pi'"
                )

        for cr_edge in node["crossResonanceChannels"]["edges"]:
            cr = cr_edge["node"]
            if cr["zxPi4Pulse"] is not None:
                assert cr["zxPi4Pulse"]["pulseRole"] == "cr", (
                    f"Qubit {key}, CR channel: zxPi4Pulse.pulseRole={cr['zxPi4Pulse']['pulseRole']!r} != 'cr'"
                )

        for zx_edge in node["zxPi4Comps"]["edges"]:
            zx = zx_edge["node"]
            if zx["pulsePrecomp"] is not None:
                assert zx["pulsePrecomp"]["pulseRole"] == "zx_precomp", (
                    f"Qubit {key}, ZxPi4Comp: pulsePrecomp.pulseRole={zx['pulsePrecomp']['pulseRole']!r} != 'zx_precomp'"
                )
            if zx["pulsePostcomp"] is not None:
                assert zx["pulsePostcomp"]["pulseRole"] == "zx_postcomp", (
                    f"Qubit {key}, ZxPi4Comp: pulsePostcomp.pulseRole={zx['pulsePostcomp']['pulseRole']!r} != 'zx_postcomp'"
                )


def test_get_all_calibrations(test_client: TestClient, hardware_model_uuid: str):
    """
    Test that get_all_calibrations returns a list of calibrations, each with an id and calibrationId,
    and that the seeded calibration is present.
    """
    query = """
        query {
            getAllCalibrations {
                id
                calibrationId
            }
        }
    """
    response = test_client.post(_GRAPHQL_URL, json={"query": query})

    assert response.status_code == 200
    data = response.json()
    assert "errors" not in data, f"GraphQL errors: {data.get('errors')}"
    calibrations = data["data"]["getAllCalibrations"]
    assert isinstance(calibrations, list)
    assert len(calibrations) > 0

    ids = [c["id"] for c in calibrations]
    assert hardware_model_uuid in ids

    for calibration in calibrations:
        assert "id" in calibration
        assert "calibrationId" in calibration
        assert calibration["id"] is not None
        assert calibration["calibrationId"] is not None


def test_get_all_hardware_model_ids(test_client: TestClient, hardware_model_uuid: str):
    """
    Test that we can retrieve a list of all hardware model UUIDs and that it contains the UUID of the model we created.
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
