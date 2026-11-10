"""Public API boundaries: explicit style follows canonical dispatch."""
from contextlib import nullcontext
from types import SimpleNamespace
import pytest
from cpu_llm.pipeline import Appliance

@pytest.mark.parametrize('style', [None, 'friendly'])
def test_style_runs_after_dispatch_before_render(monkeypatch, style):
    import cpu_llm.request_planner as planner
    import cpu_llm.output_rendering as rendering
    import cpu_llm.stylistic as stylistic
    events=[]
    def dispatch(*args):
        events.append('canonical_dispatch');return {'reply': {'text': 'accepted'}}
    def apply(result, profile):
        assert result['reply']['text']=='accepted'
        events.append('style');return result
    def render(result):
        events.append('render');return result
    monkeypatch.setattr(planner,'dispatch_request',dispatch)
    monkeypatch.setattr(stylistic,'apply_style',apply)
    monkeypatch.setattr(rendering,'render_response',render)
    app=SimpleNamespace(_session_turn=nullcontext,small_talk=False,strict_evidence=False)
    Appliance.ask(app,'Please be friendly and give a detailed answer.',style=style)
    assert events==(['canonical_dispatch','render'] if style is None else ['canonical_dispatch','style','render'])

def test_strict_evidence_bypasses_style(monkeypatch):
    import cpu_llm.strict_evidence as strict
    import cpu_llm.stylistic as stylistic
    expected={'answer_status':'evidence_quote'}
    monkeypatch.setattr(strict,'answer',lambda *a,**k:expected)
    monkeypatch.setattr(stylistic,'apply_style',lambda *a:pytest.fail('strict must not style'))
    app=SimpleNamespace(_session_turn=nullcontext,small_talk=False,strict_evidence=True)
    assert Appliance.ask(app,'What color is the Aster?',style='friendly') is expected
