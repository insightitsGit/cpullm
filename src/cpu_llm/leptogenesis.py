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
