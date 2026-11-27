"""QC-7 pilot: do mid-circuit measure-and-reset operations offset the qudit-dimension amplification of barren plateaus?

Model (fixed before running; a toy operationalization, not the cited papers' exact methods):
- n qudits of dimension d, density-matrix simulation, initial state |0...0>.
- L = 2n layers. Each layer: on every qudit a parameterized rotation exp(-i theta G), G a random Hermitian generator
  (Haar-random eigenbasis, eigenvalues spread on [-1, 1]); then a generalized controlled-phase
  |j,k> -> exp(2 pi i jk / d) |j,k> on neighbouring pairs (brick pattern).
- Cost: C = Tr(rho P), P = |0><0| on qudit 0 (a local cost).
- Gradient: central difference (eps = 1e-4) with respect to the first-layer rotation angle on the middle qudit.
- Barren-plateau signature: Var[dC/dtheta] over random angles and generators, as n grows.
- Mitigation ("mid-circuit measurements"): after every second layer, measure the qudit farthest from qudit 0 in the
  computational basis and reset it to |0> (the reset channel). Unmitigated circuits are otherwise identical.

Hypothesis (QC-7, mid-circuit-measurement variant): the mitigation offsets the amplification by qudit dimension.
Pre-registered reading:
- supported in this model if the mitigation raises the gradient variance and the benefit (ratio of variances, or the
  change in decay rate with n) grows with d;
- refuted in this model if the benefit does not grow with d, or the mitigation does not raise the variance.
usage: simulate.py out.json [samples]
"""
import json, sys, time
import numpy as np

EPS = 1e-4


def random_generator(d, rng):
    z = (rng.normal(size=(d, d)) + 1j * rng.normal(size=(d, d))) / np.sqrt(2)
    q, r = np.linalg.qr(z)
    q = q * (np.diag(r) / np.abs(np.diag(r)))
    return q, np.linspace(-1.0, 1.0, d)


def rotation(gen, theta):
    q, eig = gen
    return (q * np.exp(-1j * theta * eig)) @ q.conj().T


def apply_one(rho, u, site, n, d):
    shape = (d,) * n
    t = rho.reshape(shape + shape)
    t = np.tensordot(u, t, axes=([1], [site]))
    t = np.moveaxis(t, 0, site)
    t = np.tensordot(t, u.conj(), axes=([n + site], [1]))
    t = np.moveaxis(t, -1, n + site)
    return t.reshape(d ** n, d ** n)


def cphase_diag(n, d, pairs):
    idx = np.indices((d,) * n).reshape(n, -1)
    phase = np.zeros(d ** n)
    for a, b in pairs:
        phase += idx[a] * idx[b]
    return np.exp(2j * np.pi * phase / d)


def reset(rho, site, n, d):
    shape = (d,) * n
    t = rho.reshape(shape + shape)
    # Tr over the site, then tensor |0><0| back in: sum_k |0><k| rho |k><0|
    reduced = np.trace(t, axis1=site, axis2=n + site)
    out = np.zeros_like(t)
    index = [slice(None)] * (2 * n)
    index[site] = 0
    index[n + site] = 0
    out[tuple(index)] = reduced
    return out.reshape(d ** n, d ** n)


def cost(thetas, gens, n, d, layers, mitigated, diags):
    rho = np.zeros((d ** n, d ** n), dtype=complex)
    rho[0, 0] = 1.0
    for layer in range(layers):
        for site in range(n):
            rho = apply_one(rho, rotation(gens[layer][site], thetas[layer, site]), site, n, d)
        diag = diags[layer % 2]
        rho = (diag[:, None] * rho) * diag.conj()[None, :]
        if mitigated and layer % 2 == 1 and layer < layers - 1:
            rho = reset(rho, n - 1, n, d)
    marg = rho.reshape((d,) * (2 * n))
    # probability that qudit 0 is |0>
    return float(np.real(np.einsum('i...i->', marg.reshape(d ** n, d ** n)[:d ** (n - 1), :d ** (n - 1)])))


def gradient_variance(n, d, samples, mitigated, seed):
    rng = np.random.default_rng(seed)
    layers = 2 * n
    pairs_even = [(i, i + 1) for i in range(0, n - 1, 2)]
    pairs_odd = [(i, i + 1) for i in range(1, n - 1, 2)]
    diags = (cphase_diag(n, d, pairs_even), cphase_diag(n, d, pairs_odd or pairs_even))
    target = (0, n // 2)
    grads = []
    for _ in range(samples):
        gens = [[random_generator(d, rng) for _ in range(n)] for _ in range(layers)]
        thetas = rng.uniform(0, 2 * np.pi, size=(layers, n))
        plus, minus = thetas.copy(), thetas.copy()
        plus[target] += EPS
        minus[target] -= EPS
        grads.append((cost(plus, gens, n, d, layers, mitigated, diags) -
                      cost(minus, gens, n, d, layers, mitigated, diags)) / (2 * EPS))
    grads = np.array(grads)
    return float(np.var(grads)), float(np.mean(np.abs(grads)))


def main():
    out = sys.argv[1]
    samples = int(sys.argv[2]) if len(sys.argv) > 2 else 200
    sizes = {2: [2, 3, 4, 5, 6], 3: [2, 3, 4, 5], 4: [2, 3, 4]}
    rows = []
    for d, ns in sizes.items():
        for n in ns:
            for mitigated in (False, True):
                t0 = time.perf_counter()
                var, mean_abs = gradient_variance(n, d, samples, mitigated, seed=1000 * d + n)
                rows.append(dict(d=d, n=n, mitigated=mitigated, var=var, mean_abs=mean_abs,
                                 seconds=round(time.perf_counter() - t0, 1)))
                print(rows[-1], flush=True)
    json.dump(dict(samples=samples, eps=EPS, rows=rows), open(out, 'w'), indent=1)


if __name__ == '__main__':
    main()
