"""Frozen, standard-library descriptive statistics for the MHS pilot.

There are deliberately no null-hypothesis tests or p-values here.  Bootstrap
resampling is item-level, uses 10,000 iterations, and is fixed at seed 20260718.
"""

import math
import random
import statistics


CONFIDENCE_Z = 1.959963984540054
BOOTSTRAP_ITERATIONS = 10000
BOOTSTRAP_SEED = 20260718


def _finite(values):
    normalized = [float(value) for value in values]
    if not normalized or any(not math.isfinite(value) for value in normalized):
        raise ValueError("values must be a non-empty sequence of finite numbers")
    return normalized


def _percentile(values, probability):
    ordered = sorted(_finite(values))
    if not 0.0 <= probability <= 1.0:
        raise ValueError("probability must lie in [0, 1]")
    if len(ordered) == 1:
        return ordered[0]
    position = (len(ordered) - 1) * probability
    lower = int(math.floor(position))
    upper = int(math.ceil(position))
    if lower == upper:
        return ordered[lower]
    weight = position - lower
    return ordered[lower] * (1.0 - weight) + ordered[upper] * weight


def median_iqr(values):
    """Return median, Q1, Q3, and IQR using linear interpolated quartiles."""
    normalized = _finite(values)
    q1 = _percentile(normalized, 0.25)
    q3 = _percentile(normalized, 0.75)
    return {
        "median": statistics.median(normalized),
        "q1": q1,
        "q3": q3,
        "iqr": q3 - q1,
    }


def wilson_interval(successes, total, z=CONFIDENCE_Z):
    """Wilson score interval for a binomial proportion (95% by default)."""
    if type(successes) is not int or type(total) is not int:
        raise ValueError("successes and total must be integers")
    if total <= 0 or successes < 0 or successes > total:
        raise ValueError("require 0 <= successes <= total and total > 0")
    proportion = successes / total
    z2 = z * z
    denominator = 1.0 + z2 / total
    centre = (proportion + z2 / (2.0 * total)) / denominator
    radius = (
        z
        * math.sqrt(
            proportion * (1.0 - proportion) / total
            + z2 / (4.0 * total * total)
        )
        / denominator
    )
    return {"lower": max(0.0, centre - radius), "upper": min(1.0, centre + radius)}


def bootstrap_statistic(
    observations,
    statistic,
    iterations=BOOTSTRAP_ITERATIONS,
    seed=BOOTSTRAP_SEED,
):
    """Item-level percentile-bootstrap interval for an arbitrary statistic."""
    observations = list(observations)
    if not observations:
        raise ValueError("observations must not be empty")
    if type(iterations) is not int or iterations <= 0:
        raise ValueError("iterations must be a positive integer")
    rng = random.Random(seed)
    size = len(observations)
    estimates = []
    for _ in range(iterations):
        sample = [observations[rng.randrange(size)] for _ in range(size)]
        estimate = float(statistic(sample))
        if not math.isfinite(estimate):
            raise ValueError("bootstrap statistic must be finite")
        estimates.append(estimate)
    return {
        "lower": _percentile(estimates, 0.025),
        "upper": _percentile(estimates, 0.975),
        "iterations": iterations,
        "seed": seed,
    }


def bootstrap_median(
    values, iterations=BOOTSTRAP_ITERATIONS, seed=BOOTSTRAP_SEED
):
    return bootstrap_statistic(
        _finite(values),
        statistics.median,
        iterations=iterations,
        seed=seed,
    )
