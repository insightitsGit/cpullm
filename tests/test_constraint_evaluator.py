import pytest

from cpu_llm.constraint_evaluator import ObservableLimit, ParameterAxis, scan_constraints
from cpu_llm.pipeline import Appliance


def test_invention_scan_brackets_known_joint_intersection():
    hypothesis = dict(qualification='hypothesis', premises=[{'document_id': 'fixture'}],
                      proposal='A region satisfies both synthetic bounds.')
    result = Appliance.evaluate_invention_constraints(
        hypothesis, model='synthetic', predict=lambda p: {'target': p['x'] + p['y'], 'lab': p['x']},
        axes=[ParameterAxis('x', '1', [0, 1, 2]), ParameterAxis('y', '1', [0, 1])],
        observable_units={'target': '1', 'lab': '1'},
        limits=[ObservableLimit('target-band', 'target', '1', 'fixture target', lower=2, upper=2),
                ObservableLimit('lab-ceiling', 'lab', '1', 'fixture lab', upper=1)],
    )
    assert result['accepted_count'] == 1
    assert [p['parameters'] for p in result['points'] if not p['failed_limits']] == [{'x': 1, 'y': 1}]
    assert len(result['transition_brackets']) == 3
    assert all(bracket['lower_point']['failed_limits'] or bracket['upper_point']['failed_limits']
               for bracket in result['transition_brackets'])


def test_scan_reports_no_accepted_samples_and_rejects_bad_model_predictions():
    axes = [ParameterAxis('x', '1', [0, 1])]
    limits = [ObservableLimit('limit', 'target', 'eV', 'fixture', lower=2)]
    result = scan_constraints('synthetic', lambda p: {'target': p['x']}, axes, {'target': 'eV'}, limits)
    assert result['status'] == 'no_accepted_samples'
    assert result['transition_brackets'] == []
    with pytest.raises(ValueError, match='Invalid bounds, units, or source'):
        scan_constraints('synthetic', lambda p: {}, axes, {'target': 'meV'}, limits)
    with pytest.raises(ValueError, match='Model evaluation failed'):
        scan_constraints('synthetic', lambda p: {'target': float('nan')}, axes, {'target': 'eV'}, limits)
