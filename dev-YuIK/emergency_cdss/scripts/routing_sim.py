"""Synthetic, safety-bounded hospital-routing simulation.

This module is an evaluation prototype, not a clinical decision system.  It
does not diagnose a patient or replace EMS/medical control.  In production,
``SEVERITY_TO_RESOURCES`` and all operational probabilities must be reviewed
by qualified emergency-medicine and EMS experts, and hospital status must come
from an authenticated, timestamped source.

Examples (run from ``dev-YuIK``)::

    python -m emergency_cdss.scripts.routing_sim --patients 3000
    python -m emergency_cdss.scripts.routing_sim --patients 3000 --bootstrap 5000 \
        --output-dir routing_results

The simulator deliberately shares every generated patient and availability
draw across policies.  Therefore its paired bootstrap intervals describe the
simulated *within-scenario* difference, rather than falsely treating policy
results as independent samples.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import random
from dataclasses import asdict, dataclass
from pathlib import Path
from statistics import fmean
from typing import Iterable, Sequence


# Provisional engineering assumptions.  They are NOT a KTAS-to-resource rule.
SEVERITY_TO_RESOURCES: dict[int, frozenset[str]] = {
    1: frozenset({"ER", "CT", "OR", "TRAUMA_SURG", "ICU"}),
    2: frozenset({"ER", "CT", "TRAUMA_SURG"}),
    3: frozenset({"ER", "CT"}),
    4: frozenset({"ER"}),
    5: frozenset({"ER"}),
}


@dataclass(frozen=True)
class SimulationConfig:
    """All tunable assumptions live here; do not hide them in route logic."""

    seed: int = 20261123
    patients: int = 3000
    ambulance_speed_kmh: float = 60.0
    # alpha: expected waiting-time weight, beta: rejection-risk penalty,
    # gamma: expected resource-unavailability penalty (all in minute-equivalents).
    alpha_wait: float = 1.0
    beta_rejection: float = 25.0
    gamma_resource: float = 60.0
    retry_delay_minutes: float = 5.0
    resource_failure_delay_minutes: float = 40.0
    critical_time_limit_minutes: float = 60.0
    bootstrap_replicates: int = 2000


@dataclass(frozen=True)
class Hospital:
    hospital_id: str
    x_km: float
    y_km: float
    bed_capacity: int
    capabilities: frozenset[str]
    # Long-run probabilities used only to generate synthetic availability draws.
    mean_bed_occupancy: float
    capability_failure_probability: float


@dataclass(frozen=True)
class PatientScenario:
    patient_id: int
    x_km: float
    y_km: float
    severity: int
    traffic_multiplier: float
    # Draws are keyed by hospital index so every policy sees the same state.
    beds_available: tuple[int, ...]
    capability_available: tuple[bool, ...]
    accepts: tuple[bool, ...]


@dataclass(frozen=True)
class Outcome:
    patient_id: int
    policy: str
    total_minutes: float
    rerouted: bool
    resource_mismatch: bool
    critical_delay: bool


DEFAULT_HOSPITALS: tuple[Hospital, ...] = (
    Hospital("H01", 7.0, 10.0, 25, frozenset({"ER", "CT", "OR", "TRAUMA_SURG", "ICU"}), 0.74, 0.03),
    Hospital("H02", 18.0, 4.0, 40, frozenset({"ER", "CT", "OR", "TRAUMA_SURG", "ICU"}), 0.58, 0.02),
    Hospital("H03", 4.0, 25.0, 18, frozenset({"ER", "CT", "TRAUMA_SURG"}), 0.70, 0.05),
    Hospital("H04", 28.0, 20.0, 55, frozenset({"ER", "CT", "OR", "TRAUMA_SURG", "ICU"}), 0.51, 0.02),
    Hospital("H05", 36.0, 8.0, 22, frozenset({"ER", "CT"}), 0.64, 0.06),
    Hospital("H06", 12.0, 38.0, 30, frozenset({"ER", "CT", "OR", "TRAUMA_SURG"}), 0.61, 0.04),
)


def eta_minutes(patient: PatientScenario, hospital: Hospital, speed_kmh: float) -> float:
    """Placeholder ETA: replace with timestamped OSMnx/ITS ETA in deployment."""
    distance_km = math.hypot(patient.x_km - hospital.x_km, patient.y_km - hospital.y_km)
    return 60.0 * distance_km / speed_kmh * patient.traffic_multiplier


def required_resources(severity: int) -> frozenset[str]:
    try:
        return SEVERITY_TO_RESOURCES[severity]
    except KeyError as exc:
        raise ValueError(f"severity must be 1..5, got {severity}") from exc


def generate_scenarios(config: SimulationConfig, hospitals: Sequence[Hospital]) -> list[PatientScenario]:
    """Generate shared synthetic states; no real patient data are used."""
    rng = random.Random(config.seed)
    scenarios: list[PatientScenario] = []
    severity_weights = (0.06, 0.14, 0.25, 0.30, 0.25)
    for patient_id in range(config.patients):
        severity = rng.choices((1, 2, 3, 4, 5), weights=severity_weights, k=1)[0]
        beds, capability, accepts = [], [], []
        for hospital in hospitals:
            # Beta-shaped occupancy proxy with bounded integer availability.
            occupancy = min(0.99, max(0.01, rng.gauss(hospital.mean_bed_occupancy, 0.13)))
            available = max(0, round(hospital.bed_capacity * (1.0 - occupancy)))
            cap_available = rng.random() >= hospital.capability_failure_probability
            # Acceptance remains stochastic even if capacity is nominally open.
            accept_probability = (0.15 + 0.80 * (available / hospital.bed_capacity)) if cap_available else 0.0
            beds.append(available)
            capability.append(cap_available)
            accepts.append(rng.random() < accept_probability)
        scenarios.append(
            PatientScenario(
                patient_id=patient_id,
                x_km=rng.uniform(0, 42),
                y_km=rng.uniform(0, 42),
                severity=severity,
                traffic_multiplier=max(0.65, rng.lognormvariate(0.0, 0.22)),
                beds_available=tuple(beds),
                capability_available=tuple(capability),
                accepts=tuple(accepts),
            )
        )
    return scenarios


def _resource_risk(patient: PatientScenario, index: int, hospital: Hospital) -> float:
    """Expected resource-failure indicator based on the *observed* state."""
    if not required_resources(patient.severity).issubset(hospital.capabilities):
        return 1.0
    return 0.0 if patient.capability_available[index] else 1.0


def _accept_probability(patient: PatientScenario, index: int, hospital: Hospital) -> float:
    if _resource_risk(patient, index, hospital) > 0:
        return 0.0
    return 0.15 + 0.80 * (patient.beds_available[index] / hospital.bed_capacity)


def _expected_wait(patient: PatientScenario, index: int, hospital: Hospital) -> float:
    occupancy = 1.0 - patient.beds_available[index] / hospital.bed_capacity
    return 4.0 + 32.0 * occupancy**2


def rank_hospitals(
    patient: PatientScenario, hospitals: Sequence[Hospital], config: SimulationConfig, policy: str
) -> list[int]:
    """Return a full ordering. Proposed policy explicitly exposes its trade-offs."""
    indices = list(range(len(hospitals)))
    if policy == "nearest":
        return sorted(indices, key=lambda i: eta_minutes(patient, hospitals[i], config.ambulance_speed_kmh))
    if policy == "max_beds":
        return sorted(indices, key=lambda i: (-patient.beds_available[i], eta_minutes(patient, hospitals[i], config.ambulance_speed_kmh)))
    if policy != "proposed":
        raise ValueError(f"unknown policy: {policy}")

    def cost(i: int) -> float:
        hospital = hospitals[i]
        return (
            eta_minutes(patient, hospital, config.ambulance_speed_kmh)
            + config.alpha_wait * _expected_wait(patient, i, hospital)
            + config.beta_rejection * (1.0 - _accept_probability(patient, i, hospital))
            + config.gamma_resource * _resource_risk(patient, i, hospital)
        )

    return sorted(indices, key=cost)


def simulate_policy(
    scenarios: Iterable[PatientScenario], hospitals: Sequence[Hospital], config: SimulationConfig, policy: str
) -> list[Outcome]:
    """Simulate top-3 rerouting with common random numbers for paired comparison."""
    outcomes: list[Outcome] = []
    for patient in scenarios:
        ranking = rank_hospitals(patient, hospitals, config, policy)[:3]
        elapsed, rerouted, mismatch = 0.0, False, False
        selected = ranking[-1]
        for position, index in enumerate(ranking):
            hospital = hospitals[index]
            static_mismatch = not required_resources(patient.severity).issubset(hospital.capabilities)
            unavailable = static_mismatch or not patient.capability_available[index]
            if unavailable:
                mismatch = True
            if not unavailable and patient.accepts[index]:
                selected = index
                break
            rerouted = True
            elapsed += config.retry_delay_minutes
        elapsed += eta_minutes(patient, hospitals[selected], config.ambulance_speed_kmh)
        # A failed required capability results in a modelled secondary transfer.
        if mismatch:
            elapsed += config.resource_failure_delay_minutes
        elapsed += _expected_wait(patient, selected, hospitals[selected])
        outcomes.append(Outcome(patient.patient_id, policy, elapsed, rerouted, mismatch, elapsed > config.critical_time_limit_minutes))
    return outcomes


def percentile(values: Sequence[float], q: float) -> float:
    ordered = sorted(values)
    if not ordered:
        raise ValueError("percentile requires at least one value")
    position = (len(ordered) - 1) * q
    lo, hi = math.floor(position), math.ceil(position)
    return ordered[lo] if lo == hi else ordered[lo] + (ordered[hi] - ordered[lo]) * (position - lo)


def summarize(outcomes: Sequence[Outcome]) -> dict[str, float]:
    times = [o.total_minutes for o in outcomes]
    return {
        "mean_transfer_minutes": fmean(times),
        "p90_transfer_minutes": percentile(times, 0.90),
        "reroute_rate": fmean(float(o.rerouted) for o in outcomes),
        "resource_mismatch_rate": fmean(float(o.resource_mismatch) for o in outcomes),
        "critical_delay_rate": fmean(float(o.critical_delay) for o in outcomes),
    }


def paired_bootstrap_ci(
    proposed: Sequence[Outcome], baseline: Sequence[Outcome], replicates: int, seed: int
) -> dict[str, dict[str, float]]:
    """Percentile 95% CIs of proposed minus baseline, resampling patient pairs."""
    if len(proposed) != len(baseline) or not proposed:
        raise ValueError("paired outcomes must have the same non-zero length")
    if [x.patient_id for x in proposed] != [x.patient_id for x in baseline]:
        raise ValueError("outcomes are not aligned by patient_id")
    metrics = {
        "mean_transfer_minutes": lambda o: o.total_minutes,
        "reroute_rate": lambda o: float(o.rerouted),
        "resource_mismatch_rate": lambda o: float(o.resource_mismatch),
        "critical_delay_rate": lambda o: float(o.critical_delay),
    }
    rng, n = random.Random(seed), len(proposed)
    point = {name: fmean(fn(p) - fn(b) for p, b in zip(proposed, baseline)) for name, fn in metrics.items()}
    samples = {name: [] for name in metrics}
    for _ in range(replicates):
        ids = [rng.randrange(n) for _ in range(n)]
        for name, fn in metrics.items():
            samples[name].append(fmean(fn(proposed[i]) - fn(baseline[i]) for i in ids))
    return {
        name: {"difference": point[name], "ci95_low": percentile(samples[name], 0.025), "ci95_high": percentile(samples[name], 0.975)}
        for name in metrics
    }


def grid_search(
    scenarios: Sequence[PatientScenario], hospitals: Sequence[Hospital], config: SimulationConfig,
    beta_values: Sequence[float], gamma_values: Sequence[float],
) -> list[dict[str, float]]:
    """Sensitivity analysis, not a validation-set hyperparameter selection claim."""
    rows: list[dict[str, float]] = []
    for beta in beta_values:
        for gamma in gamma_values:
            candidate = SimulationConfig(**{**asdict(config), "beta_rejection": beta, "gamma_resource": gamma})
            row = {"beta_rejection": beta, "gamma_resource": gamma}
            row.update(summarize(simulate_policy(scenarios, hospitals, candidate, "proposed")))
            rows.append(row)
    return rows


def write_csv(path: Path, rows: Sequence[dict[str, float]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--patients", type=int, default=3000)
    parser.add_argument("--seed", type=int, default=20261123)
    parser.add_argument("--bootstrap", type=int, default=2000)
    parser.add_argument("--beta-grid", type=float, nargs="+", default=[10.0, 25.0, 40.0, 60.0])
    parser.add_argument("--gamma-grid", type=float, nargs="+", default=[20.0, 40.0, 60.0, 80.0])
    parser.add_argument("--output-dir", type=Path, default=Path("routing_results"))
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.patients <= 0 or args.bootstrap <= 0 or any(x < 0 for x in args.beta_grid + args.gamma_grid):
        raise SystemExit("patients/bootstrap must be positive and beta/gamma values must be non-negative")
    config = SimulationConfig(seed=args.seed, patients=args.patients, bootstrap_replicates=args.bootstrap)
    scenarios = generate_scenarios(config, DEFAULT_HOSPITALS)
    policies = {name: simulate_policy(scenarios, DEFAULT_HOSPITALS, config, name) for name in ("nearest", "max_beds", "proposed")}
    summaries = [{"policy": name, **summarize(outcomes)} for name, outcomes in policies.items()]
    comparisons = {
        baseline: paired_bootstrap_ci(policies["proposed"], policies[baseline], config.bootstrap_replicates, config.seed + index)
        for index, baseline in enumerate(("nearest", "max_beds"), start=1)
    }
    grid = grid_search(scenarios, DEFAULT_HOSPITALS, config, args.beta_grid, args.gamma_grid)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    write_csv(args.output_dir / "policy_summary.csv", summaries)
    write_csv(args.output_dir / "beta_gamma_sensitivity.csv", grid)
    (args.output_dir / "paired_bootstrap_ci.json").write_text(
        json.dumps({"config": asdict(config), "comparisons": comparisons}, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps({"summary": summaries, "paired_bootstrap": comparisons, "outputs": str(args.output_dir)}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
