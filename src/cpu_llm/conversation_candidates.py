"""Filter local dialogue exports into a review queue; never import answers/facts.

No network, remote dataset code, training, or automatic runtime-pack updates.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import re
import sys

from cpu_llm.conversation import recognize,normalize

SOURCES={
    'OpenAssistant/oasst1':dict(license='apache-2.0',format='oasst',url='https://huggingface.co/datasets/OpenAssistant/oasst1'),
    'HuggingFaceH4/ultrachat_200k':dict(license='mit',format='ultrachat',url='https://huggingface.co/datasets/HuggingFaceH4/ultrachat_200k'),
    'li2017dailydialog/daily_dialog':dict(license='cc-by-nc-sa-4.0',format='daily',url='https://huggingface.co/datasets/li2017dailydialog/daily_dialog')}


def prompts(row,kind):
    if kind=='oasst':
        if row.get('role')!='prompter' or row.get('lang')!='en' or row.get('deleted') is not False or row.get('review_result') is not True:
            return []
        labels=row.get('labels') or {}
        if not isinstance(labels,dict):return []
        pii=labels.get('pii') or {}
        if isinstance(pii,dict) and float(pii.get('value') or 0)>0:return []
        if 'name' in labels and 'pii' in labels['name']:
            if float(labels['value'][labels['name'].index('pii')])>0:return []
        return [(row.get('message_id'),row.get('text'))]
    if kind=='ultrachat':
        messages=row.get('messages') or []
        if not messages or messages[0].get('role')!='user':return []
        return [(row.get('prompt_id'),messages[0].get('content'))]
    dialog=row.get('dialog') or []
    if isinstance(dialog,str):dialog=json.loads(dialog)
    if not isinstance(dialog,list):return []
    return [(None,text) for text in dialog]


def prepare(path,source,revision,*,allow_noncommercial=False,max_records=10000):
    if source not in SOURCES:raise ValueError('Unknown dataset source')
    if not re.fullmatch(r'[a-fA-F0-9]{40}',revision):raise ValueError('Pin a 40-character upstream revision SHA')
    if SOURCES[source]['format']=='daily' and not allow_noncommercial:
        raise ValueError('DailyDialog is noncommercial/share-alike; explicitly acknowledge with --allow-noncommercial')
    if not 1<=max_records<=100000:raise ValueError('max_records must be 1..100000')
    if path.stat().st_size>128*1024*1024:raise ValueError('Use a local export shard of at most 128 MiB')
    raw=path.read_bytes()
    if path.suffix.casefold()=='.jsonl':
        rows=(json.loads(line) for line in raw.decode('utf-8').splitlines() if line.strip())
    else:
        rows=json.loads(raw)
        if not isinstance(rows,list):raise ValueError('JSON export must be a record array')
    candidates=[];seen=set();scanned=0;malformed=0;truncated=False
    for index,row in enumerate(rows):
        if index>=max_records:truncated=True;break
        scanned+=1
        try:
            if not isinstance(row,dict):raise ValueError('Record must be an object')
            values=prompts(row,SOURCES[source]['format'])
            for id,text in values:
                if not isinstance(text,str):continue
                intent=recognize(text)
                if intent is None or normalize(text) in seen:continue
                seen.add(normalize(text))
                candidates.append(dict(source_record_id=id,input_phrase=text,intent=intent,reviewed=False))
        except (ValueError,TypeError,KeyError,IndexError,AttributeError):malformed+=1
    return dict(schema='conversation-candidate-review-v1',source=source,upstream_revision=revision,
        source_card=SOURCES[source]['url'],declared_license=SOURCES[source]['license'],
        source_identity_verified=False,input_sha256=hashlib.sha256(raw).hexdigest(),
        records_scanned=scanned,scan_truncated=truncated,malformed_records=malformed,
        runtime_imported=False,assistant_answers_imported=False,clinical_validation=False,candidates=candidates)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input',type=Path,required=True)
    parser.add_argument('--source',choices=tuple(SOURCES),required=True)
    parser.add_argument('--revision',required=True)
    parser.add_argument('--out',type=Path,required=True)
    parser.add_argument('--allow-noncommercial',action='store_true')
    parser.add_argument('--max-records',type=int,default=10000)
    args=parser.parse_args()
    result=prepare(args.input,args.source,args.revision,allow_noncommercial=args.allow_noncommercial,max_records=args.max_records)
    with args.out.open('x',encoding='utf-8') as sink:json.dump(result,sink,indent=2);sink.write('\n')
    print(f"Prepared {len(result['candidates'])} deduplicated phrases for review. No answers or runtime changes imported.")


if __name__=='__main__':main()
