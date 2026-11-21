"""The agent-facing documents must match the code and the PyPI description must match the README."""
import json
from pathlib import Path

from cpu_llm.serve import _ASK_FIELDS

ROOT = Path(__file__).resolve().parents[1]


def test_tool_schema_matches_the_server_fields():
    schema = json.loads((ROOT / 'docs/agent-tool-schema.json').read_text())
    [ask] = [tool for tool in schema['tools'] if tool['name'] == 'cpu_llm_ask']
    assert set(ask['parameters']['properties']) - {'message'} <= set(_ASK_FIELDS)
    import tomllib
    assert schema['version'] == tomllib.loads((ROOT / 'pyproject.toml').read_text())['project']['version']


def test_pypi_readme_is_generated_from_the_readme():
    import importlib.util
    spec = importlib.util.spec_from_file_location('build_pypi_readme', ROOT / 'tools/build_pypi_readme.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    expected = module.pypi_readme((ROOT / 'README.md').read_text(encoding='utf-8'))
    assert (ROOT / 'PYPI_README.md').read_text(encoding='utf-8') == expected, 'run python tools/build_pypi_readme.py'
    assert '](docs/' not in expected and '](CHANGELOG.md)' not in expected


def test_documented_statuses_and_files_exist():
    readme = (ROOT / 'README.md').read_text()
    agents = (ROOT / 'AGENTS.md').read_text()
    for status in ('answered', 'evidence_quote', 'derived_inference', 'hypotheses', 'shortage', 'deepened',
                   'insufficient_evidence', 'unsupported', 'needs_clarification', 'partial', 'blocked'):
        assert f'`{status}`' in readme and f'`{status}`' in agents, status
    import re
    for link in re.findall(r'\]\(((?:docs/|examples/|inference-guide|CHANGELOG|AGENTS|LICENSE|THIRD)[^)#\s]*)', readme):
        assert (ROOT / link).exists(), link
