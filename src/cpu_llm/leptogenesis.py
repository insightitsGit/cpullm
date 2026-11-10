"""Illustrative hierarchical, unflavored N1 leptogenesis scan adapter."""
import cmath
import math

from cpu_llm.constraint_evaluator import evaluate_invention_constraints

PARAMETER_UNITS = {
    'm_lightest': 'eV', 'M1': 'GeV', 're_z': 'rad', 'im_z': 'rad',
    'alpha21': 'rad', 'alpha31': 'rad',
}
OBSERVABLE_UNITS = {'eta_B': '1', 'm_beta_beta': 'eV', 'sum_m_nu': 'eV'}


def predict(parameters):
    """Predict observables for normal ordering on the R=(0, cos z, sin z) slice."""
    m1 = parameters['m_lightest']
    heavy_mass = parameters['M1']
    if m1 < 0 or heavy_mass <= 0:
        raise ValueError('Light mass must be nonnegative and heavy mass must be positive.')
    m2 = math.sqrt(m1 * m1 + 7.42e-5)
    m3 = math.sqrt(m1 * m1 + 2.51e-3)
    alpha21 = parameters.get('alpha21', 0.0)
    alpha31 = parameters.get('alpha31', 0.0)
    delta_cp = 1.97 * math.pi
    s12_sq, s13_sq = 0.304, 0.0222
    effective_mass = abs(
        m1 * (1 - s12_sq) * (1 - s13_sq)
        + m2 * s12_sq * (1 - s13_sq) * cmath.exp(1j * alpha21)
        + m3 * s13_sq * cmath.exp(1j * (alpha31 - 2 * delta_cp))
    )
    z = complex(parameters['re_z'], parameters['im_z'])
    r2, r3 = cmath.cos(z), cmath.sin(z)
    washout_mass = m2 * abs(r2)**2 + m3 * abs(r3)**2
    k = washout_mass / 1.08e-3
    # This slice is always in strong washout since washout_mass >= m2.
    efficiency = 0.3 / (k * math.log(k)**0.6)
    weighted_mass = (m2**2 * (r2**2).imag + m3**2 * (r3**2).imag) / washout_mass
    weighted_mass_gev = weighted_mass * 1e-9
    epsilon = -3 / (16 * math.pi) * heavy_mass / 174.0**2 * weighted_mass_gev
    eta = 7.04 * (28 / 79) * epsilon * efficiency / 106.75
    return dict(eta_B=eta, m_beta_beta=effective_mass, sum_m_nu=m1 + m2 + m3)


def scan_leptogenesis(hypothesis, *, axes, limits):
    """Run the illustrative adapter with explicitly supplied empirical limits."""
    axes = tuple(axes)
    names = {axis.name for axis in axes}
    required = {'m_lightest', 'M1', 're_z', 'im_z'}
    if not required <= names or any(PARAMETER_UNITS.get(axis.name) != axis.unit for axis in axes):
        raise ValueError('Supply the required leptogenesis axes with their declared units.')
    limits = tuple(limits)
    if not {'eta_B', 'm_beta_beta'} <= {limit.observable for limit in limits}:
        raise ValueError('Supply both a baryon-asymmetry target and an effective-mass limit.')
    scan = evaluate_invention_constraints(
        hypothesis, model='illustrative_hierarchical_unflavored_n1', predict=predict,
        axes=axes, observable_units=OBSERVABLE_UNITS, limits=limits,
    )
    scan['model_scope'] = dict(
        qualification='illustrative_approximation', mass_ordering='normal',
        orthogonal_slice='(0, cos(z), sin(z))', flavor_effects=False,
        fixed_phases={name: 0.0 for name in ('alpha21', 'alpha31') if name not in names},
        delta_cp_rad=1.97 * math.pi,
    )
    return scan


def run_reference_profile(hypothesis):
    """Run a fixed, versioned diagnostic profile suitable for chat."""
    from collections import Counter
    from cpu_llm.constraint_evaluator import ObservableLimit, ParameterAxis

    scan = scan_leptogenesis(
        hypothesis,
        axes=[
            ParameterAxis('M1', 'GeV', [10**(9 + 3*i/19) for i in range(20)]),
            ParameterAxis('m_lightest', 'eV', [.001 + .049*i/19 for i in range(20)]),
            ParameterAxis('im_z', 'rad', [.1 + 2.4*i/9 for i in range(10)]),
            ParameterAxis('re_z', 'rad', [-math.pi/4]),
        ],
        limits=[
            ObservableLimit('eta_B', 'eta_B', '1', 'Project diagnostic acceptance window',
                            lower=5.62e-10, upper=6.62e-10),
            ObservableLimit('kamland_zen', 'm_beta_beta', 'eV',
                            'https://arxiv.org/abs/2406.11438 (28 meV nuclear-matrix-element scenario)',
                            upper=.028),
            ObservableLimit('planck_bao', 'sum_m_nu', 'eV',
                            'https://arxiv.org/abs/1807.06209 (Planck 2018 + BAO scenario)', upper=.12),
        ],
    )
    passing = [point for point in scan['points'] if not point['failed_limits']]
    lowest = min(passing, key=lambda point: point['parameters']['M1'], default=None)
    refined = []
    for bracket in scan['transition_brackets']:
        lower, upper = bracket['lower_point'], bracket['upper_point']
        if (bracket['axis'] != 'M1' or upper['failed_limits']
                or upper['parameters']['M1'] != lowest['parameters']['M1']
                or lower['failed_limits'] != ['eta_B'] or lower['predictions']['eta_B'] >= 5.62e-10):
            continue
        left, right = lower['parameters']['M1'], upper['parameters']['M1']
        for _ in range(32):
            midpoint = (left + right) / 2
            if predict(dict(upper['parameters'], M1=midpoint))['eta_B'] < 5.62e-10:
                left = midpoint
            else:
                right = midpoint
        parameters = dict(upper['parameters'], M1=right)
        refined.append(dict(parameters=parameters, predictions=predict(parameters),
                            binding_limit='eta_B', mass_bracket_gev=[left, right]))
    crossings = Counter(
        ', '.join(pair['lower_point']['failed_limits'] or pair['upper_point']['failed_limits'])
        for pair in scan['transition_brackets']
    )
    return dict(profile='leptogenesis_reference_v1', status=scan['status'], axes=scan['axes'],
                scope=scan['model_scope'], limits=scan['limits'], sampled=len(scan['points']),
                accepted=len(passing), brackets=len(scan['transition_brackets']),
                rejected_endpoint_limits=dict(crossings),
                lowest_passing=lowest,
                refined_crossing=min(refined, key=lambda point: point['parameters']['M1'], default=None))


def format_reference_result(scan):
    text = (f'Automatic scan ({scan["profile"]}, illustrative normal ordering without flavor effects): '
            f'{scan["accepted"]} of {scan["sampled"]} sampled points passed; '
            f'{scan["brackets"]} adjacent pass/fail brackets.')
    point = scan['lowest_passing']
    if point:
        text += f' Lowest passing sampled M1: {point["parameters"]["M1"]:.3g} GeV.'
    return text
