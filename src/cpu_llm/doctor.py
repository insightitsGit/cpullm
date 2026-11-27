"""``cpu-llm-doctor``: check the database, pgvector, encoder cache, state directory and optional parser.

Prints one line per check (OK, WARN or FAIL) with the fix for each problem, and exits 1 when anything failed.
Nothing is written except a probe file in the state directory, which is removed again.
"""
from __future__ import annotations

import importlib.util
import os
import sys
from pathlib import Path

ENCODER = 'sentence-transformers/all-mpnet-base-v2'
MIN_PGVECTOR = (0, 7)


def _version(text):
    parts = []
    for piece in (text or '').split('.')[:3]:
        digits = ''.join(ch for ch in piece if ch.isdigit())
        parts.append(int(digits) if digits else 0)
    return tuple(parts)


def check_python():
    ok = sys.version_info >= (3, 11)
    return ('OK' if ok else 'FAIL', 'python', sys.version.split()[0], None if ok else 'Use Python 3.11 or later.')


def check_database(dsn=None, connect=None):
    """Connect, then report the pgvector version and the namespaces present."""
    from cpu_llm.retrieval import LOCAL_PG_DSN
    dsn = dsn or os.environ.get('VECTORPRISM_PG_DSN')
    source = 'VECTORPRISM_PG_DSN' if dsn else 'built-in local default'
    dsn = dsn or LOCAL_PG_DSN
    results = []
    try:
        if connect is None:
            import psycopg
            connect = psycopg.connect
        with connect(dsn, connect_timeout=5) as conn:
            results.append(('OK', 'database', f'connected ({source})', None))
            row = conn.execute("select extversion from pg_extension where extname = 'vector'").fetchone()
            if row is None:
                available = conn.execute(
                    "select default_version from pg_available_extensions where name = 'vector'").fetchone()
                results.append(('FAIL', 'pgvector', 'not installed in this database',
                                'Run CREATE EXTENSION vector;' if available else
                                'Install pgvector 0.7 or later on the server, then CREATE EXTENSION vector;'))
            elif _version(row[0]) < MIN_PGVECTOR:
                results.append(('FAIL', 'pgvector', f'version {row[0]}', 'Upgrade pgvector to 0.7 or later '
                                '(0.6 lacks subvector), then ALTER EXTENSION vector UPDATE;'))
            else:
                results.append(('OK', 'pgvector', f'version {row[0]}', None))
            names = [r[0][3:] for r in conn.execute(
                "select schema_name from information_schema.schemata where schema_name like 'ns\\_%' "
                "and schema_name not like 'ns\\_pipeline\\_test\\_%' order by 1").fetchall()]
            names = [n for n in names if not n.startswith('pipeline_test_')]
            results.append(('OK', 'namespaces', ', '.join(names) if names else 'none yet', None))
    except Exception as exc:          # any connection problem is reported, never raised
        results.append(('FAIL', 'database', f'cannot connect ({source}): {type(exc).__name__}',
                        'Start PostgreSQL and set VECTORPRISM_PG_DSN, for example '
                        'postgresql://user:password@127.0.0.1:5432/dbname'))
    return results


def check_encoder(environ=None):
    environ = os.environ if environ is None else environ
    roots = [Path(environ['HF_HOME']) / 'hub'] if environ.get('HF_HOME') else []
    roots += [Path(environ.get('XDG_CACHE_HOME', Path.home() / '.cache')) / 'huggingface' / 'hub']
    if environ.get('SENTENCE_TRANSFORMERS_HOME'):
        roots.append(Path(environ['SENTENCE_TRANSFORMERS_HOME']))
    folder = 'models--' + ENCODER.replace('/', '--')
    for root in roots:
        if (root / folder).exists():
            offline = environ.get('HF_HUB_OFFLINE') == '1'
            return ('OK', 'encoder', f'{ENCODER} cached in {root}' + ('' if offline else
                    ' (set HF_HUB_OFFLINE=1 to skip network checks)'), None)
    return ('WARN', 'encoder', f'{ENCODER} not found in the Hugging Face cache',
            'It downloads on first use (needs access to huggingface.co); or set HF_HOME to an existing cache.')


def check_state_dir(state_dir=None):
    from cpu_llm.pipeline import resolve_state_dir
    explicit = state_dir or os.environ.get('CPU_LLM_STATE_DIR')
    path = resolve_state_dir(state_dir)
    try:
        path.mkdir(parents=True, exist_ok=True)
        probe = path / '.cpu-llm-doctor-probe'
        probe.write_text('ok')
        probe.unlink()
    except OSError as exc:
        return ('FAIL', 'state directory', f'{path} is not writable ({type(exc).__name__})',
                'Pass state_dir= or set CPU_LLM_STATE_DIR to a writable folder.')
    if explicit:
        return ('OK', 'state directory', str(path), None)
    return ('WARN', 'state directory', f'{path} (depends on the working directory)',
            'Set CPU_LLM_STATE_DIR (or pass state_dir=) so every run uses the same local state.')


def check_parser():
    for model in ('en_core_web_lg', 'en_core_web_sm'):
        if importlib.util.find_spec(model) is not None:
            return ('OK', 'parser', f'spaCy {model} (Frontier and Deepen use dependency parsing)', None)
    return ('WARN', 'parser', 'no spaCy English model; Frontier and Deepen use the regex reader',
            'pip install "cpu-llm[prompt_nlp]" && python -m spacy download en_core_web_lg')


def run(state_dir=None, out=print):
    checks = [check_python(), *check_database(), check_encoder(), check_state_dir(state_dir), check_parser()]
    for level, name, detail, fix in checks:
        out(f'{level:4}  {name}: {detail}')
        if fix:
            out(f'      fix: {fix}')
    failed = sum(level == 'FAIL' for level, *_ in checks)
    out('All required checks passed.' if not failed else f'{failed} required check(s) failed.')
    return 1 if failed else 0


def main(argv=None):
    import argparse
    parser = argparse.ArgumentParser(prog='cpu-llm-doctor', description=__doc__.splitlines()[0])
    parser.add_argument('--state-dir', help='state directory to check (default: CPU_LLM_STATE_DIR or ./.chorusgraph)')
    args = parser.parse_args(argv)
    return run(args.state_dir)


if __name__ == '__main__':
    sys.exit(main())
