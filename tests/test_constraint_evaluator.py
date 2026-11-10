import pytest
import numpy as np

from cpu_llm.constraint_evaluator import ObservableLimit, ParameterAxis, scan_constraints
from cpu_llm.pipeline import Appliance
from cpu_llm.leptogenesis import predict


def test_leptogenesis_prediction_changes_sign_under_angle_reflection():
    point = dict(m_lightest=0.001, M1=1e11, re_z=np.pi / 4, im_z=0.5)
    original = predict(point)
    reflected = predict(dict(point, re_z=-point['re_z']))
    assert original['eta_B'] < 0
    assert reflected['eta_B'] == pytest.approx(-original['eta_B'])
    assert reflected['m_beta_beta'] == original['m_beta_beta']
    assert predict(dict(point, im_z=0))['eta_B'] == 0


def test_leptogenesis_diagnostic_grid_matches_reference_calculation():
    hypothesis = dict(qualification='hypothesis', premises=[{'document_id': 'fixture'}],
                      proposal='Find an overlap in the illustrative parameter slice.')
    result = Appliance.scan_leptogenesis(
        hypothesis,
        axes=[ParameterAxis('M1', 'GeV', np.logspace(9, 12, 20)),
              ParameterAxis('m_lightest', 'eV', np.linspace(.001, .05, 20)),
              ParameterAxis('im_z', 'rad', np.linspace(.1, 2.5, 10)),
              ParameterAxis('re_z', 'rad', [-np.pi / 4])],
        limits=[ObservableLimit('target', 'eta_B', '1', 'diagnostic window', lower=5.62e-10, upper=6.62e-10),
                ObservableLimit('mass', 'm_beta_beta', 'eV', 'historical scenario', upper=.036),
                ObservableLimit('sum', 'sum_m_nu', 'eV', 'Planck 2018 + BAO scenario', upper=.12)],
    )
    assert len(result['points']) == 4000
    assert result['accepted_count'] == 33
    assert len(result['transition_brackets']) == 152
    assert result['model_scope']['qualification'] == 'illustrative_approximation'


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
