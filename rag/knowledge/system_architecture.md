# Low-Altitude UAV Agent Platform Architecture

## Mission layer

The user provides a high-level mission request.

The Mission Agent converts the request into structured mission
parameters and invokes backend tools.

The LLM operates at the mission and explanation layer rather
than the high-frequency flight-control layer.

---

## Planning layer

The platform currently supports:

- normal A* path planning
- communication-aware A* path planning

The communication-aware planner incorporates radio-map quality
into route cost.

---

## Execution layer

PX4 SITL and Gazebo provide the flight simulation environment.

MAVSDK is used by the Python runtime to:

- connect to PX4
- arm
- take off
- send position targets
- monitor telemetry
- land

---

## Communication layer

The current radio map is a synthetic communication model.

It estimates:

- RSRP
- SINR
- coverage score
- serving base station

The model can represent weak-coverage regions and multiple base
stations.

It is intended for algorithm and system validation rather than
claiming real measured 5G coverage.

---

## Runtime incident layer

The runtime communication monitor detects degraded and recovered
communication states.

The flight-critical incident path uses:

Communication Monitor
-> deterministic route comparison
-> Fast Incident Policy
-> fresh-position acquisition
-> runtime replanning
-> route validation
-> DynamicRouteController
-> PX4 execution

---

## Agent layer

The LLM is used for:

- mission understanding
- tool orchestration
- incident explanation
- engineering recommendations

The LLM is not used for real-time flight stabilization or
high-frequency control.

---

## Evaluation layer

The platform records:

- planned route
- actual trajectory
- communication samples
- communication events
- incident decisions
- runtime replans
- route-application events

Evaluation includes:

- trajectory distance
- flight efficiency
- path deviation
- radio-quality metrics
- handover count
- incident decision latency
- communication recovery
- single-replan metrics
- multi-replan metrics
