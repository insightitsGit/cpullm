import sys
import pytest
from cpu_llm import ingest


@pytest.mark.parametrize('args,code',[(['--help'],0),(['--not-a-real-flag'],2),(['--test','--finance'],2)])
def test_help_and_invalid_flags_never_construct_an_appliance(monkeypatch,args,code):
    def forbidden(*args,**kwargs):raise AssertionError('CLI initialized a model/database before validating arguments')
    monkeypatch.setattr(ingest,'Appliance',forbidden)
    monkeypatch.setattr(sys,'argv',['cpu-llm-ingest',*args])
    with pytest.raises(SystemExit) as outcome:ingest.main()
    assert outcome.value.code==code
