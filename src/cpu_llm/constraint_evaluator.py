"""Deterministic evaluation of sourced bounds over a finite parameter grid."""
from dataclasses import dataclass
from itertools import product
from math import isfinite, prod
from typing import Callable, Mapping, Sequence


@dataclass(frozen=True)
class ParameterAxis:
    name: str
    unit: str
    values: Sequence[float]


@dataclass(frozen=True)
class ObservableLimit:
    id: str
    observable: str
    unit: str
    source: str
    lower: float | None = None
    upper: float | None = None


def scan_constraints(
    model: str,
    predict: Callable[[Mapping[str, float]], Mapping[str, float]],
    axes: Sequence[ParameterAxis],
    observable_units: Mapping[str, str],
    limits: Sequence[ObservableLimit],
) -> dict:
    """Return sampled points and adjacent transition brackets."""
    axes = tuple(axes)
    limits = tuple(limits)
    if not model.strip() or not axes or not limits:
        raise ValueError('Provide a model name, parameter axes, and sourced limits.')
    if len(axes) > 32 or len(limits) > 128 or prod(len(axis.values) for axis in axes) not in range(1, 10001):
        raise ValueError('Scan exceeds the axis, limit, or 10,000-point budget, or has an empty axis.')
    names = [axis.name for axis in axes]
    if len(set(names)) != len(names) or len({limit.id for limit in limits}) != len(limits):
        raise ValueError('Axis names and limit identifiers must be unique.')
    values = [tuple(axis.values) for axis in axes]
    for axis, samples in zip(axes, values):
        if (not axis.name.strip() or not axis.unit.strip() or not all(map(isfinite, samples))
                or any(a >= b for a, b in zip(samples, samples[1:]))):
            raise ValueError('Each axis needs a name, unit, and strictly increasing finite samples.')
    for limit in limits:
        bounds = [value for value in (limit.lower, limit.upper) if value is not None]
        if (not limit.id.strip() or not limit.source.strip() or not limit.unit.strip()
                or observable_units.get(limit.observable) != limit.unit
                or not bounds or not all(map(isfinite, bounds)) or bounds != sorted(bounds)):
            raise ValueError(f'Invalid bounds, units, or source for {limit.id!r}.')

    observables = tuple(dict.fromkeys(limit.observable for limit in limits))
    points = {}
    transitions = []
    accepted = 0
    for index in product(*(range(len(samples)) for samples in values)):
        parameters = {name: samples[i] for name, samples, i in zip(names, values, index)}
        try:
            result = predict(parameters.copy())
            predictions = {name: result[name] for name in observables}
            if not all(map(isfinite, predictions.values())):
                raise ValueError('Non-finite prediction.')
        except Exception as exc:
            raise ValueError(f'Model evaluation failed at {parameters!r}.') from exc
        failed = []
        for limit in limits:
            value = predictions[limit.observable]
            if ((limit.lower is not None and value < limit.lower)
                    or (limit.upper is not None and value > limit.upper)):
                failed.append(limit.id)
        accepted += not failed
        point = dict(parameters=parameters, predictions=predictions, failed_limits=failed)
        points[index] = point
        for axis, i in enumerate(index):
            if i == 0:
                continue
            neighbor = points[index[:axis] + (i - 1,) + index[axis + 1:]]
            if bool(failed) != bool(neighbor['failed_limits']):
                transitions.append(dict(axis=names[axis], lower_point=neighbor, upper_point=point))
    return dict(model=model, status='accepted_samples' if accepted else 'no_accepted_samples',
                axes=[dict(name=axis.name, unit=axis.unit, values=samples) for axis, samples in zip(axes, values)],
                observable_units={name: observable_units[name] for name in observables},
                limits=[vars(limit).copy() for limit in limits], points=list(points.values()),
                accepted_count=accepted, transition_brackets=transitions)


def evaluate_invention_constraints(hypothesis, *, model, predict, axes, observable_units, limits):
    """Run an explicit scan for a selected invention hypothesis."""
    if hypothesis.get('qualification') != 'hypothesis' or not hypothesis.get('premises'):
        raise ValueError('Select a cited invention hypothesis before scanning.')
    scan = scan_constraints(model, predict, axes, observable_units, limits)
    scan['hypothesis'] = hypothesis['proposal']
    return scan
