import importlib.util
import json
from pathlib import Path
import pytest

spec=importlib.util.spec_from_file_location('candidates',Path(__file__).resolve().parents[1]/'tools/prepare_conversation_candidates.py')
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)


def test_only_reviewed_user_phrases_are_exported_without_external_identity(tmp_path):
    path=tmp_path/'export.jsonl'
    rows=[dict(role='prompter',text='Who are you?',lang='en',review_result=True,deleted=False,message_id='1'),
          dict(role='assistant',text='I am ChatGPT.',lang='en',review_result=True,deleted=False),
          dict(role='prompter',text='Which antibiotic should I take?',lang='en',review_result=True,deleted=False),
          dict(role='prompter',text='Hello',lang='en',review_result=False,deleted=False)]
    path.write_text('\n'.join(json.dumps(r) for r in rows),encoding='utf-8')
    result=module.prepare(path,'OpenAssistant/oasst1','a'*40)
    assert len(result['candidates'])==1
    assert result['candidates'][0]['intent']=='identity'
    assert not result['assistant_answers_imported'] and not result['runtime_imported']
    assert 'ChatGPT' not in json.dumps(result)


def test_ultrachat_uses_first_user_turn_only_and_deduplicates(tmp_path):
    path=tmp_path/'export.json'
    path.write_text(json.dumps([dict(messages=[dict(role='user',content='Hello!'),dict(role='assistant',content='Medical advice')])]*2),encoding='utf-8')
    result=module.prepare(path,'HuggingFaceH4/ultrachat_200k','b'*40,max_records=1)
    assert len(result['candidates'])==1 and result['scan_truncated']
    assert 'Medical advice' not in json.dumps(result)


def test_daily_requires_explicit_noncommercial_acknowledgment(tmp_path):
    path=tmp_path/'daily.json';path.write_text('[{"dialog":["hello","goodbye"]}]',encoding='utf-8')
    with pytest.raises(ValueError,match='noncommercial'):module.prepare(path,'li2017dailydialog/daily_dialog','c'*40)
    result=module.prepare(path,'li2017dailydialog/daily_dialog','c'*40,allow_noncommercial=True)
    assert len(result['candidates'])==2 and result['declared_license']=='cc-by-nc-sa-4.0'
