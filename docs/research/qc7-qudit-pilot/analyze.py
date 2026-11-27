"""Apply the pre-registered reading to results.json and print a table and verdict."""
import json, math, sys
import numpy as np

data = json.load(open(sys.argv[1]))
rows = data['rows']
by = {(r['d'], r['n'], r['mitigated']): r['var'] for r in rows}
ds = sorted({r['d'] for r in rows})
common = sorted(set.intersection(*[{r['n'] for r in rows if r['d'] == d} for d in ds]))
print('Var[dC/dtheta] by qudit dimension d and size n (unmitigated -> mitigated, ratio)')
for d in ds:
    ns = sorted({r['n'] for r in rows if r['d'] == d})
    for n in ns:
        u, m = by[(d, n, False)], by[(d, n, True)]
        print(f'  d={d} n={n}: {u:.3e} -> {m:.3e}  ratio {m / u:5.2f}')
slopes = {}
for d in ds:
    ns = sorted({r['n'] for r in rows if r['d'] == d and r['n'] >= 3})
    for mit in (False, True):
        y = [math.log(by[(d, n, mit)]) for n in ns]
        slopes[(d, mit)] = float(np.polyfit(ns, y, 1)[0])
print('\nDecay rate of log Var per added qudit (n >= 3; more negative = worse barren plateau)')
for d in ds:
    print(f'  d={d}: unmitigated {slopes[(d, False)]:+.2f}, mitigated {slopes[(d, True)]:+.2f}, '
          f'change {slopes[(d, True)] - slopes[(d, False)]:+.2f}')
ratio_at = {d: float(np.mean([math.log(by[(d, n, True)] / by[(d, n, False)]) for n in common if n >= 3])) for d in ds}
print('\nMean log variance ratio (mitigated/unmitigated) at shared sizes n=' + ','.join(str(n) for n in common if n >= 3))
for d in ds:
    print(f'  d={d}: {ratio_at[d]:+.2f}  (x{math.exp(ratio_at[d]):.2f})')
helps = all(ratio_at[d] > 0 for d in ds)
grows = all(ratio_at[a] < ratio_at[b] for a, b in zip(ds, ds[1:]))
amplified = all(slopes[(a, False)] > slopes[(b, False)] for a, b in zip(ds, ds[1:]))
print('\nChecks: qudit dimension amplifies the decay (unmitigated):', amplified)
print('        mitigation raises the variance at every d:', helps)
print('        benefit grows with d:', grows)
print('Verdict (this toy model only):', 'SUPPORTED' if helps and grows else 'REFUTED' if not helps or not grows else 'INCONCLUSIVE')
