"""Author fictional facts and expected contracts without importing cpu_llm."""
from __future__ import annotations
import hashlib
import json
import random
from collections import Counter
from pathlib import Path

FAMILIES = ['conversational_normalization','field_lists_and_task_coverage','meaning_and_reference',
 'joins_and_retrieval_repair','attribute_slots','response_depth_and_size','layout_and_media',
 'proof_and_display_fidelity','access_and_history','instructions_versus_data',
 'existing_specialists_and_templates','missing_conflicting_unsupported']
ROUTING = ['optional_priority_and_composition','guard_and_hold_precedence','presentation_budget_consistency',
 'false_activation','draft_and_api_boundaries','channel_signals_vs_execution',
 'trace_and_early_return_fidelity','batch_and_render_stages']
COLORS = ['blue','white','amber','green','red','purple','teal','gray']
SHAPES = ['round','square','oval','flat']
MATERIALS = ['brass','wood','steel','glass']

def dump(path):
    path=Path(path);path.mkdir(parents=True,exist_ok=False)
    corpus=[];domains=[];facts=[];rng=random.Random(291033)
    def name(r):
        return ''.join(r.choice(['va','ne','ru','zi','po','ke','du','fi','lo','ma','te','sha']) for _ in range(4)).capitalize()
    used=set()
    def unique(r):
        while (n:=name(r)) in used: pass
        used.add(n);return n
    def add(d,source,text,relation=None,subject=None,obj=None,quantifier='direct',**extra):
        prefix=f'v3d{d}-{source}-p';number=1+sum(c['id'].startswith(prefix) for c in corpus)
        item=dict(id=prefix+f'{number:04d}',text=text,domain=d,source=source,**extra);corpus.append(item)
        if relation: facts.append(dict(subject=subject,relation=relation,object=obj,quantifier=quantifier,
                                       document_id=item['id'],span=text))
        return item['id']
    for d in range(3):
        dev=random.Random(291031+d*100);hold=random.Random(291032+d*100)
        names=[unique(dev) for _ in range(4)]+[unique(hold) for _ in range(4)]
        kind=['survey lantern','survey gauge','survey vessel'][d]
        other=['display lantern','display gauge','display vessel'][d]
        place=unique(dev)+' Reach';place2=unique(hold)+' Reach'
        year=str(21+d*7);lens=['a prism','a sensor','a bell'][d]
        subjects=[]
        for i,n in enumerate(names):
            r=dev if i<4 else hold; k=kind if i%2==0 else other
            color=r.choice(COLORS);shape=r.choice(SHAPES);material=r.choice(MATERIALS);weight=str(10+d*4+i)+' pounds'
            e=dict(name=n,kind=k,color=color,shape=shape,material=material,weight=weight,
                   place=place if i<4 else place2,years=year,universal_part=lens)
            e['type_id']=add(d,'public',f'The {n} is a {k}.','is_a',n,k)
            e['color_id']=add(d,'public',f'The {n} is {color}.','has_color',n,color)
            e['place_id']=add(d,'public',f'The {n} is found in {e["place"]}.','lives_in',n,e['place'])
            e['part_id']=add(d,'public',f'The {n} has a handle.','has',n,'a handle')
            e['shape_id']=add(d,'public',f'The shape of the {n} is {shape}.','attribute:shape',n,shape)
            if i!=6:
                e['material_id']=add(d,'public',f'The material of the {n} is {material}.','attribute:material',n,material)
            else: e['material_id']=add(d,'public',f'The {n} is copper.','has_color',n,'copper')
            e['weight_id']=add(d,'public',f'The {n} weighs {weight}.','weight',n,weight)
            e['weight_attribute_id']=add(d,'public',f'The weight of the {n} is {weight}.','attribute:weight',n,weight)
            e['cause_id']=add(d,'public',f'The {n} stopped because its battery failed.','causes',f'{n} stopped','its battery failed')
            subjects.append(e)
        age=add(d,'public',f'Every {kind} lives for {year} years.','has_lifespan',kind,f'{year} years','every')
        part=add(d,'public',f'Every {kind} has {lens}.','has',kind,lens,'every')
        add(d,'public',f'Some {other}s have a filter.','has',other,'a filter','some')
        add(d,'public',f'The average {other} lives for 4 years.','has_lifespan',other,'4 years','average')
        add(d,'public',f'A {kind} is a logged instrument.','is_a',kind,'logged instrument')
        extras=[]
        for split,r,i in [('development',dev,0),('holdout',hold,4)]:
            n=names[i];person=unique(r);amb=unique(r);glyph=unique(r);alias=unique(r)+' moth';unknown=unique(r)
            a=add(d,'public',f'The {amb} is a survey marker.','is_a',amb,'survey marker')
            b=add(d,'public',f'The {amb} is a display marker.','is_a',amb,'display marker')
            action=add(d,'public',f'{person} baked a cake.','activity',person,'baked a cake')
            alias_id=add(d,'public',f'The {n}, known as the {alias}, is a {kind}.','alias',alias,n)
            ranking=add(d,'public',f'The {n} is the best {kind} for portability.','best',n,'portability')
            literal='code-0007 | <tag> {{ 7 * 7 }}'
            glyph_id=add(d,'public',f'The color of the {glyph} is {literal}.','has_color',glyph,literal)
            extras.append(dict(split=split,person=person,amb=amb,amb_ids=[a,b],action_id=action,
                               alias=alias,alias_id=alias_id,ranking_id=ranking,glyph=glyph,glyph_id=glyph_id,
                               literal=literal,unknown=unknown))
        private=[]
        for j in range(10):
            n=names[0 if j<5 else 4];canary=f'v3-secret-{d}-{j}-'+unique(rng).lower()
            private.append(add(d,'private',f'The {n} seal is {canary}.','seal',n,canary))
        secret_color=add(d,'private',f'The {names[0]} is orange.','has_color',names[0],'orange')
        history=[]
        for j in range(10):
            entity=names[0 if j<5 else 4]+' '+['panel','bracket','case','mount','cap'][j%5]
            prior=f'The material of the {entity} is oak.';new=f'The material of the {entity} is iron.'
            key=add(d,'history',prior,'attribute:material',entity,'oak',correction=new,valid_at=1700000000,corrected_at=1700000100)
            history.append(dict(entity=entity,id=key,old='oak',new='iron'))
        for j in range(100):
            near=names[j%8]+rng.choice(['a','e','on','er'])
            add(d,'distractor',f'The {near} ledger records {1000+j} components in sector {d+1}.')
        domains.append(dict(index=d,subjects=subjects,kind=kind,other=other,age_id=age,part_id=part,
                            extras=extras,history=history,private_ids=private,secret_color=secret_color))
    cases=[]
    def base(f,i,d,e):
        split='development' if i<12 else 'holdout'
        return dict(id=f'core-{f:02}-{i:02}',family=FAMILIES[f],split=split,domain=d['index'],
                    caller=dict(id='reader',sources=[f'v3d{d["index"]}-public-p']),
                    allowed_outcomes=['answered','evidence_quote'],proof_sets=[],claims=[],bindings=[],forbidden=[],
                    capability='supported_shared',execution_mode='public_live')
    def expect(c,e,relation,obj,ids):
        c.update(claims=[obj],bindings=[dict(subject=e['name'],relation=relation,object=obj,
                direction='subject',polarity='affirmative',quantifier='direct')],proof_sets=[ids])
    def child(e,relation,obj,ids):
        return dict(subject=e['name'],relation=relation,object=obj,proof_sets=[ids],claims=[obj])
    for f in range(12):
        for i in range(20):
            d=domains[i%3];idx=0 if i<12 else 4;e=d['subjects'][idx];other=d['subjects'][idx+1]
            x=d['extras'][0 if i<12 else 1];n=e['name'];v=i%5;c=base(f,i,d,e)
            if f==0:
                prompts=[f'Could you tell me what color the {n} is?',f"I'd like to know where the {n} lives.",
                         f'I was wondering how long the {n} lives.',f'Can you explain what the {n} is?',
                         f'Please give me information about the color of the {n}.']
                c['prompt']=prompts[v]
                choices=[('has_color',e['color'],[e['color_id']]),('lives_in',e['place'],[e['place_id']]),
                         ('has_lifespan',e['years']+' years',[e['type_id'],d['age_id']]),('is_a',e['kind'],[e['type_id']]),
                         ('has_color',e['color'],[e['color_id']])]
                expect(c,e,*choices[v])
                if v==4:c['capability']='spacy_only';c['rules_allowed_outcomes']=['insufficient_evidence','unsupported','needs_clarification']
            elif f==1:
                if v in (0,1):
                    c['prompt']=f'Tell me the color, habitat, and lifespan of the {n}.' if v==0 else f'What color is the {n}, where does it live, and how long does it live?'
                    c['children']=[child(e,'has_color',e['color'],[e['color_id']]),child(e,'lives_in',e['place'],[e['place_id']]),child(e,'has_lifespan',e['years']+' years',[e['type_id'],d['age_id']])]
                elif v==2:c.update(prompt=f'Tell me the color and friendliness of the {n}.',allowed_outcomes=['needs_clarification'],capability='safe_rejection')
                elif v==3:c.update(prompt=f'Tell me the color and habitat of the {n} and {other["name"]}.',allowed_outcomes=['needs_clarification'],capability='safe_rejection')
                else:c.update(prompt=' '.join([f'What color is the {n}?' for _ in range(9)]),allowed_outcomes=['needs_clarification'],capability='safe_rejection')
            elif f==2:
                if v==0:c.update(prompt=f'What is the {x["amb"]}?',allowed_outcomes=['needs_clarification'],capability='expected_clarification')
                elif v==1:c.update(prompt=f'Who is {x["person"]}?',allowed_outcomes=['needs_clarification','insufficient_evidence'],capability='safe_rejection',forbidden=[f'{x["person"]} is a baker'])
                elif v==2:c.update(prompt=f'What color is the {n}? Where does it live?',children=[child(e,'has_color',e['color'],[e['color_id']]),child(e,'lives_in',e['place'],[e['place_id']])])
                elif v==3:c.update(prompt=f'What color is the {n}? What color is the {other["name"]}? Where does it live?',allowed_outcomes=['needs_clarification'],capability='expected_clarification')
                else:c['prompt']=f'What kind of thing is the {n}?';expect(c,e,'is_a',e['kind'],[e['type_id']])
            elif f==3:
                if v in (0,1):c['prompt']=f'How long does the {n} live?';expect(c,e,'has_lifespan',e['years']+' years',[e['type_id'],d['age_id']])
                elif v==2:c['prompt']=f'What does the {n} contain?';expect(c,e,'has',e['universal_part'],[e['type_id'],d['part_id']]);c['claims'].append('a handle');c['proof_sets'][0].append(e['part_id'])
                elif v==3:c.update(prompt=f'How long does the {other["name"]} live?',allowed_outcomes=['insufficient_evidence','needs_clarification'],capability='safe_rejection',forbidden=['4 years'])
                else:c.update(prompt=f'What does the filter possess?',allowed_outcomes=['insufficient_evidence','needs_clarification'],capability='safe_rejection')
            elif f==4:
                rel,obj,key,prompt=[('has_color',e['color'],'color_id',f'What color is the {n}?'),
                    ('attribute:shape',e['shape'],'shape_id',f'What shape is the {n}?'),
                    ('attribute:material',e['material'],'material_id',f'What material is the {n}?'),
                    ('weight',e['weight'],'weight_id',f'How much does the {n} weigh?'),
                    ('attribute:weight',e['weight'],'weight_attribute_id',f'What is the weight of the {n}?')][v]
                c['prompt']=prompt;expect(c,e,rel,obj,[e[key]])
            elif f==5:
                c['prompt']=[f'Briefly explain the {n}.',f'Give me a long response about the {n}.',f'Explain the {n} in 20 sentences.',f'Explain the {n} in three bullet points.',f'Explain the {n} in 300 words.'][v]
                c.update(min_visible_facts=1 if v==0 else 2,min_citations=1,
                         flags={'long_response':v in (1,2,4)},optional_limit=1 if v==0 else 20 if v==2 else 3 if v==3 else 12 if v==4 else 8)
                if v==3:c['format']='bullets'
            elif f==6:
                form,media=[('table','text/markdown'),('table','text/html'),('report','text/html'),('bullets','text/markdown'),('numbered','text/markdown')][v]
                suffix={('table','text/markdown'):'a Markdown table',('table','text/html'):'an HTML table',('report','text/html'):'an HTML report',('bullets','text/markdown'):'bullet points',('numbered','text/markdown'):'a numbered list'}[(form,media)]
                c.update(prompt=f'Show the color and habitat of the {n} as {suffix}.',format=form,media=media,
                         children=[child(e,'has_color',e['color'],[e['color_id']]),child(e,'lives_in',e['place'],[e['place_id']])])
            elif f==7:
                if v in (0,1,2):
                    suffix=['a Markdown table','an HTML table','an HTML report'][v]
                    c.update(prompt=f'What color is the {x["glyph"]} as {suffix}?',format='report' if v==2 else 'table',media='text/markdown' if v==0 else 'text/html',claims=[x['literal']],proof_sets=[[x['glyph_id']]],literal=x['literal'])
                elif v==3:c['prompt']=f'In one sentence: How long does the {n} live?';expect(c,e,'has_lifespan',e['years']+' years',[e['type_id'],d['age_id']])
                else:c['prompt']=f'What is the {x["alias"]}?';expect(c,dict(name=x['alias']),'is_a',d['kind'],[x['alias_id']])
            elif f==8:
                h=d['history'][0 if i<12 else 5]
                if v in (0,1):
                    c.update(prompt=f'What material is the {h["entity"]}?',caller=dict(id='historian',sources=[f'v3d{d["index"]}-history-p']),claims=[h['old'] if v==0 else h['new']],proof_sets=[[h['id'] if v==0 else '@corrected:'+h['id']]])
                    if v==0:c['as_of']=1700000000
                elif v==2:c.update(prompt=f'What color is the {n}?',caller=dict(id='nobody',sources=[]),allowed_outcomes=['blocked'],capability='safe_rejection')
                elif v==3:c['prompt']=f'What color is the {n}?';expect(c,e,'has_color',e['color'],[e['color_id']]);c['forbidden']=['orange'] if idx==0 else []
                else:c.update(prompt=f'How long does the {n} live?',caller=dict(id='limited',sources=[e['type_id']]),allowed_outcomes=['insufficient_evidence','needs_clarification'],capability='safe_rejection',forbidden=[e['years']+' years'])
            elif f==9:
                prompts=[f'What is the "summary" archive of {n}?',f'What is deep search?',
                         f'What is the title "2 + 3"?',f'Can the {n} live without water?',
                         f'Could you tell me where the {n} lives if it is damaged?']
                c.update(prompt=prompts[v],allowed_outcomes=['insufficient_evidence','unsupported','needs_clarification'],capability='safe_rejection',forbidden_nodes=['math'] if v==2 else ['deep'] if v==1 else [])
            elif f==10:
                if v==0:c.update(prompt='Calculate 7 + 8.',claims=['15'],required_nodes=['math'],min_citations=0)
                elif v==1:c.update(prompt=f'Draft a letter about the {n}.',min_visible_facts=1,min_citations=1)
                elif v==2:c.update(prompt=f'Create a checklist about the {n}.',min_visible_facts=1,min_citations=1)
                elif v==3:c.update(prompt=f'Explain the {n} as a Markdown report.',format='report',media='text/markdown',min_visible_facts=1,min_citations=1)
                else:c.update(prompt='Calculate 12 divided by 3.',claims=['4'],required_nodes=['math'],min_citations=0)
            else:
                if v==0:c.update(prompt=f'How long does the {x["unknown"]} live?',allowed_outcomes=['insufficient_evidence','needs_clarification'],capability='safe_rejection')
                elif v==1:c.update(prompt=f'Which {d["kind"].split()[-1]} is best?',allowed_outcomes=['needs_clarification'],capability='expected_clarification')
                elif v==2:c.update(prompt=f'Where does it live?',allowed_outcomes=['needs_clarification'],capability='expected_clarification')
                elif v==3:c.update(prompt=f'What is the {x["amb"]}?',allowed_outcomes=['needs_clarification'],capability='expected_clarification')
                else:c.update(prompt=f'What will the {n} do next year?',allowed_outcomes=['insufficient_evidence','unsupported','needs_clarification'],capability='safe_rejection')
            cases.append(c)
    # Routing cases have their own denominator and independently specified nodes.
    routing=[]
    for f,family in enumerate(ROUTING):
        for j in range(4):
            split='development' if j<2 else 'holdout';d=domains[j%3];e=d['subjects'][0 if j<2 else 4];n=e['name']
            c=dict(id=f'route-{f:02}-{j:02}',family=family,split=split,domain=d['index'],execution_mode='public_live',
                   caller=dict(id='router',sources=[f'v3d{d["index"]}-public-p']),allowed_outcomes=['answered','evidence_quote'],
                   capability='supported_shared',claims=[],bindings=[],proof_sets=[],flags={},required_nodes=[],forbidden_nodes=[])
            if f==0:
                c.update(prompt=f'Deep search compare {n} and {d["subjects"][1 if j<2 else 5]["name"]}.',required_nodes=['deep','compare'],order=[['deep','compare']])
            elif f==1:
                c.update(prompt=f'What color is the {n}?',caller=dict(id='empty',sources=[]),allowed_outcomes=['blocked'],capability='safe_rejection',no_search=True)
            elif f==2:
                c.update(prompt=f'Explain the {n} in detail.',flags={'long_response':True,'expand_retrieval':True},required_nodes=['brief'],forbidden_nodes=['deep','gather','imagine'],min_visible_facts=2,min_citations=1)
            elif f==3:
                c.update(prompt=f'What is the "list" archive?',allowed_outcomes=['insufficient_evidence','unsupported','needs_clarification'],capability='safe_rejection',forbidden_nodes=['brief','math','deep'])
            elif f==4:
                c.update(prompt=f'What color is the {n}?',api={'discover':bool(j%2)},required_nodes=['discover'] if j%2 else [],forbidden_nodes=[] if j%2 else ['discover'],claims=[e['color']],proof_sets=[[e['color_id']]])
            elif f==5:
                c.update(prompt=f'What color is the {n}?',claims=[e['color']],proof_sets=[[e['color_id']]],required_nodes=['dense','relational','disentangled','hyperbolic','identity','causal'])
            elif f==6:
                c.update(prompt=f'What color is the {n}?',claims=[e['color']],proof_sets=[[e['color_id']]],required_nodes=['retrieve','think','reply'],post_stages=['finalize_turn'])
            else:
                c.update(prompt=f'Show the color and habitat of the {n} as an HTML report.',format='report',media='text/html',children=[child(e,'has_color',e['color'],[e['color_id']]),child(e,'lives_in',e['place'],[e['place_id']])],post_stages=['render_response'])
            routing.append(c)
    scripts=[]
    groups=['reference','criterion','meaning','batch','boundary','scope_lifecycle']
    for g,group in enumerate(groups):
        for j in range(4):
            split='development' if j<2 else 'holdout';d=domains[j%3];e=d['subjects'][0 if j<2 else 4];x=d['extras'][0 if j<2 else 1];n=e['name']
            common=dict(caller=dict(id='script-reader',sources=[f'v3d{d["index"]}-public-p']),domain=d['index'],split=split,capability='supported_shared')
            def turn(prompt,outcomes,**kw):return dict(prompt=prompt,allowed_outcomes=outcomes,**common,**kw)
            yes=['answered','evidence_quote']
            if group=='reference':
                turns=[turn('Where does it live?',['needs_clarification']),turn(n,yes,claims=[e['place']],proof_sets=[[e['place_id']]])]
            elif group=='criterion':
                turns=[turn(f'Which {d["kind"].split()[-1]} is best?',['needs_clarification']),turn('portability',yes,claims=['best','portability'],proof_sets=[[x['ranking_id']]])]
            elif group=='meaning':
                label='survey marker' if j%2==0 else 'display marker';key=x['amb_ids'][j%2]
                turns=[turn(f'What is the {x["amb"]}?',['needs_clarification']),turn(label,yes,claims=[label],proof_sets=[[key]])]
            elif group=='batch':
                turns=[turn(f'Where does it live? What color is the {n}?',['needs_clarification']),turn(n,['answered','partial','evidence_quote'],claims=[e['place'],e['color']],proof_sets=[[e['place_id'],e['color_id']]])]
            elif group=='boundary':
                turns=[turn('Where does it live?',['needs_clarification']),turn('cancel',['cancelled']),turn(f'What color is the {n}?',yes,claims=[e['color']],proof_sets=[[e['color_id']]])]
            else:
                # TTL/reset are distinct; real-process restart is separately tested.
                turns=[turn('Where does it live?',['needs_clarification']),turn(f'Where does it live?',['needs_clarification'],action='advance_clock' if j%2==0 else 'reset_sessions',clock_delta=1801)]
            scripts.append(dict(id=f'script-{group}-{j}',group=group,split=split,domain=d['index'],turns=turns,extension=False))
    for g,group in enumerate(['multi_agent_precedence','hold_reset_boundaries','global_layout_pending_resume','caller_api_config_isolation']):
        for j in range(2):
            split='development' if j==0 else 'holdout';d=domains[g%3];e=d['subjects'][0 if j==0 else 4];n=e['name'];caller=dict(id='routing-script',sources=[f'v3d{d["index"]}-public-p'])
            common=dict(domain=d['index'],split=split,caller=caller,capability='supported_shared')
            if g==0:turns=[dict(common,prompt=f'Explain the {n} in detail.',allowed_outcomes=['answered','evidence_quote'],required_nodes=['brief'],forbidden_nodes=['deep']),dict(common,prompt='Calculate 3 + 6.',allowed_outcomes=['answered','evidence_quote'],claims=['9'],required_nodes=['math'])]
            elif g==1:turns=[dict(common,prompt='Where does it live?',allowed_outcomes=['needs_clarification']),dict(common,prompt='start over',allowed_outcomes=['cancelled'])]
            elif g==2:turns=[dict(common,prompt=f'Where does it live? What color is the {n}? Please use a table.',allowed_outcomes=['needs_clarification']),dict(common,prompt=n,allowed_outcomes=['answered','partial','evidence_quote'],claims=[e['place'],e['color']],proof_sets=[[e['place_id'],e['color_id']]],format='table')]
            else:turns=[dict(common,prompt=f'What color is the {n}?',allowed_outcomes=['answered','evidence_quote'],claims=[e['color']],proof_sets=[[e['color_id']]]),dict(common,prompt=f'What color is the {n}?',caller=dict(id='other',sources=[]),allowed_outcomes=['blocked'],no_search=True)]
            scripts.append(dict(id=f'route-script-{g}-{j}',group=group,split=split,domain=d['index'],turns=turns,extension=True))
    assert Counter(c['family'] for c in cases)==Counter({f:20 for f in FAMILIES})
    assert len(cases)==240 and len(routing)==32 and len(scripts)==32
    data=dict(corpus=corpus,facts=facts,domains=domains,cases=cases,routing_cases=routing,scripts=scripts)
    hashes={}
    for key,rows in data.items():
        content=''.join(json.dumps(row,sort_keys=True)+'\n' for row in rows)
        (path/(key+'.jsonl')).write_text(content,encoding='utf-8');hashes[key]=hashlib.sha256(content.encode()).hexdigest()
    manifest=dict(schema='v3-gold-1',hashes=hashes,cases=240,routing_cases=32,controlled_fixtures=16,scripts=32,
                  script_turns=sum(len(s['turns']) for s in scripts),initial_paragraphs=len(corpus),
                  factual_paragraphs=sum(c['source']!='distractor' for c in corpus),distractors=300,
                  splits=dict(Counter(c['split'] for c in cases)),script_splits=dict(Counter(s['split'] for s in scripts)))
    (path/'manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    return manifest
