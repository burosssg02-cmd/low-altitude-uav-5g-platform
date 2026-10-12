# UAV Communication Incident Knowledge Base

## 1. Communication degradation

A communication degradation event indicates that the UAV's
current radio link quality has fallen below the configured
operational thresholds.

The runtime detector evaluates multiple radio indicators,
including:

- RSRP
- SINR
- coverage score

A degradation event is generated only after the configured
number of consecutive degraded samples is reached.

This prevents temporary radio fluctuations from immediately
triggering route replanning.

---

## 2. RSRP

RSRP represents the received reference signal power.

A lower RSRP generally indicates weaker received signal
strength.

In the current platform:

- RSRP below -95 dBm contributes to communication degradation.
- RSRP above the recovery threshold contributes to link recovery.

RSRP alone is not sufficient to characterize communication
quality because interference may still result in poor SINR.

---

## 3. SINR

SINR represents the signal-to-interference-plus-noise ratio.

A low SINR indicates that the desired signal is weak relative
to interference and noise.

A UAV may therefore have acceptable RSRP while still
experiencing poor communication quality due to interference.

The platform evaluates RSRP and SINR together rather than
using only received power.

---

## 4. Coverage score

The platform uses a normalized coverage score to combine
radio-quality information.

The current synthetic radio-map implementation combines RSRP
and SINR information into a single coverage indicator.

The coverage score is used by:

- communication monitoring
- communication-aware path evaluation
- runtime incident policy

The current radio map is a simulation model and must not be
described as measured commercial 5G network data.

---

## 5. Runtime communication incident handling

When communication degradation is detected, the flight-critical
decision path does not wait for an LLM.

The runtime flow is:

1. Detect communication degradation.
2. Compare the current normal route and a communication-aware
   alternative.
3. Apply the deterministic Fast Incident Policy.
4. If replanning is recommended, obtain a fresh UAV position.
5. Generate a new communication-aware route.
6. Structurally validate the new route.
7. Replace the remaining runtime waypoints.
8. Continue the mission.
9. Monitor for communication recovery.

This architecture keeps the real-time flight-control path
independent from external LLM latency.

---

## 6. Fast Incident Policy

The Fast Incident Policy is deterministic.

It evaluates whether the communication-aware route provides
sufficient communication improvement while keeping the route
distance penalty within an allowed range.

Evidence includes:

- coverage-score improvement
- mean RSRP improvement
- mean SINR improvement
- handover reduction

The policy requires multiple communication-improvement signals
before recommending replanning.

The policy does not use an LLM.

---

## 7. LLM Incident Advisor

The Incident Advisor runs asynchronously after the deterministic
flight decision has already been made.

Its responsibilities include:

- explaining the communication incident
- interpreting radio-quality changes
- summarizing the Fast Policy decision
- suggesting follow-up engineering analysis

The Advisor has no authority to directly control PX4 or replace
the deterministic flight decision.

An Advisor timeout or failure must not interrupt the UAV mission.

---

## 8. Communication-aware replanning

Communication-aware A* modifies route cost using radio-map
information.

The planner attempts to avoid areas with poor predicted
communication quality while still considering geometric path
length.

The communication-aware route may therefore be longer than the
shortest geometric route if that provides significantly better
radio conditions.

---

## 9. Communication recovery

A communication recovery event is generated after the configured
number of consecutive samples exceeds the recovery thresholds.

Recovery thresholds are intentionally different from degradation
thresholds.

This hysteresis reduces repeated switching caused by radio
measurements fluctuating near a single threshold.

---

## 10. Multiple runtime replans

A mission may experience more than one communication degradation
episode.

Each episode is evaluated independently:

COMMUNICATION_DEGRADED
-> Fast Policy decision
-> optional runtime route replacement
-> COMMUNICATION_RECOVERED

The multi-replan evaluator aggregates all episodes and reports:

- number of replans
- number of recoveries
- decision latency
- route-application latency
- recovery time
- recovery path distance
- revised planned distance
- actual mission distance
- dynamic extra distance
- dynamic flight efficiency

---

## 11. Safety boundary

The current runtime route validator performs structural,
grid-level validation.

It checks properties such as:

- valid path structure
- valid grid cells
- correct start and goal
- adjacency of path nodes
- finite waypoint coordinates
- positive altitude

It is not yet a complete aviation safety validator.

It must not be described as providing full:

- regulatory compliance
- geofence compliance
- dynamic obstacle avoidance
- full 3D collision avoidance
