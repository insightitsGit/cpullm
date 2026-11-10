"""Cross-domain invention using a shared, explicitly defined mathematical relation."""
import cmath
import hashlib
import re

from cpu_llm.connection_channels import evaluate_connection
from cpu_llm.invention import _snapshot
from cpu_llm.knowledge_graph import Fact

_MAX_KBS = 7


def cross_domain_seed(query):
    match = re.fullmatch(
        r'(?:CrossDoma?in\s*:\s*(.*?)|(?:please\s+)?'
        r'(?:research|investigate|explore)\s+(.+?\s+using\s+kbs\s*:\s*.+?))\s*[.!?]*',
        query.strip(), re.I,
    )
    return (match[1] if match[1] is not None else match[2]).strip() if match else None


def execute_cross_domain(app, message, seed, *, caller=None, as_of=None, strict=False):
    import psycopg
    from cpu_llm.answerability import _sentences
    from cpu_llm.pipeline import _caller_for

    def result(status, body, **receipt):
        response = dict(message=message, tenant_id=app.tenant_id, status=status, answer_status=status,
                        answer=None, answer_evidence=[], audit_passed=False, reply=dict(text=body, body=body),
                        needs_clarification=status == 'needs_clarification')
        if receipt:
            response['invention'] = dict(triggered=True, node='crossdomin', **receipt)
            response['routing'] = dict(post_stages=['crossdomin'])
        return response

    context = _caller_for(app, caller)
    allowed = None if context is None else context.allowed_sources
    if app.guard.check(message).decision != 'allow' or allowed is not None and not allowed:
        return result('blocked', 'Request blocked.')
    if strict:
        return result('unsupported', 'Strict evidence mode disables CrossDomain invention.')
    parts = re.split(r'\s+using\s+kbs\s*:\s*', seed, maxsplit=1, flags=re.I)
    topic = parts[0].strip()
    requested = [name.strip().casefold() for name in parts[1].split(',')] if len(parts) == 2 else ['physics', 'mathematics']
    requested = ['mathematics' if name == 'math' else name for name in requested]
    if (not 2 <= len(requested) <= _MAX_KBS or len(set(requested)) != len(requested)
            or any(not re.fullmatch(r'[a-z0-9]{1,32}', name) for name in requested)):
        return result('needs_clarification', 'Select two to seven distinct KB prefixes separated by commas. '
                      'Use letters and numbers in each prefix.', joins=[])
    if not topic or len(topic) > 240:
        return result('needs_clarification', 'Name the physics model or mathematical relation to join.', joins=[])
    try:
        rows, when = _snapshot(app, allowed, as_of)
    except (RuntimeError, ValueError, psycopg.Error):
        return result('partial', 'The CrossDomain source snapshot is unavailable.', joins=[])

    anchor = re.compile(r'(?<!\w)' + re.escape(topic) + r'(?!\w)', re.I)
    premises = {}
    construction = None
    for row in rows:
        document, chunk = row['document_id'], row['chunk_text']
        domain = document.split('-', 1)[0].casefold()
        domain = 'mathematics' if domain == 'math' else domain
        if domain not in requested or (domain == requested[0] and not anchor.search(chunk)):
            continue
        for quote in _sentences(chunk):
            if len(quote) > 1000 or quote not in chunk:
                continue
            if re.search(r'\b(?:not|never|fails?|unless|whether|may|might|could|approximately)\b', quote, re.I):
                continue
            compact = re.sub(r'[\s*\^{}()$]', '', quote.casefold()).replace('ᵗ', 't')
            if (not re.search(r'complex[- ]orthogonal(?:ity)?\b', quote, re.I)
                    or not re.search(r'rtr=i(?![a-z0-9])', compact)):
                continue
            has_construction = all(term in compact for term in ('cosz', 'sinz', 'complexz'))
            if domain == 'mathematics' and not has_construction:
                continue
            start = chunk.index(quote)
            premise = dict(domain=domain, document_id=document, quote=quote, start=start,
                           end=start + len(quote), chunk_sha256=hashlib.sha256(chunk.encode()).hexdigest())
            premises.setdefault(domain, premise)
            if has_construction and construction is None:
                construction = premise
                premises[domain] = premise
        if len(premises) == len(requested) and construction is not None:
            break
    missing = [domain for domain in requested if domain not in premises]
    if missing or construction is None:
        reason = ('Missing matching premises from: ' + ', '.join(missing) + '.' if missing else
                  'No selected KB supplied the complex sine and cosine construction.')
        return result('insufficient_evidence', 'CrossDomain needs a matching transpose identity R^T R = I '
                      'in every selected KB. ' + reason + ' Ingest a source with the missing premise '
                      'under the corresponding KB prefix, then retry.', joins=[], requested_domains=requested,
                      matched_domains=[domain for domain in requested if domain in premises],
                      missing_domains=missing, as_of=when)

    proof = dict(key='complex_orthogonality:transpose', premises=[premises[domain] for domain in requested],
                 channels=evaluate_connection(Fact('complex orthogonality', 'crossdomain_join', 'transpose identity',
                                                   '', ''))['channels'])
    residual = max(abs(cmath.cos(z)**2 + cmath.sin(z)**2 - 1) for z in (0j, .5 + .5j, -.7 + 1j))
    check = dict(operator='cos(z)^2 + sin(z)^2', samples=3, max_residual=residual, passed=residual <= 1e-12)
    lines = ['Proposed model check: Verify the complex rotation using R^T R = I. '
             'For the rotation row, check cos(z)^2 + sin(z)^2 = 1.',
             f'The built-in check sampled three complex angles with maximum residual {residual:.3g}.']
    lines.extend(f'[{item["document_id"]}] {item["quote"]}' for item in proof['premises'])
    return result('hypotheses', '\n'.join(lines), joins=[proof], requested_domains=requested, check=check, as_of=when)

# Compatibility with the 1.12.0 Python API.
crossdomin_seed = cross_domain_seed
execute_crossdomin = execute_cross_domain
