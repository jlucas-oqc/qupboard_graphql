# Qubboard GraphQL/Rest API PoC

## Example query

```graphql
{
  getCalibration(id: "92f4847b-4df2-4c04-9fbc-18c9228b78ab") {
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
            nameIndex
            blockSize
            defaultAmplitude
            switchBox
            baseband {
              uuid
              frequency
              ifFrequency
            }
            iqVoltageBias {
              id
              bias
            }
          }
          pulseChannels {
            uuid
            drive {
              uuid
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
            secondState {
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
            freqShift {
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
          }
          crossResonanceChannels {
            edges {
              node {
                uuid
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
              nameIndex
              blockSize
              defaultAmplitude
              switchBox
              swapReadoutIq
              baseband {
                uuid
                frequency
                ifFrequency
              }
              iqVoltageBias {
                id
                bias
              }
            }
            pulseChannels {
              uuid
              measure {
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
              }
              acquire {
                uuid
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
            }
          }
        }
      }
    }
  }
}```
