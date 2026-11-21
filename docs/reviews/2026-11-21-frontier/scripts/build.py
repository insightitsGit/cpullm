import json, re, sys, pathlib
meta = json.load(open(sys.argv[1]))
out = pathlib.Path(sys.argv[2]); out.mkdir(parents=True, exist_ok=True)
SUB = {
 'compute and chips': ['1704.04760','2009.06489','2202.05924','2207.02852','2304.01433','2010.15581','2104.04473','1910.02054','2311.15377'],
 'energy and power': ['1906.02243','1907.10597','2002.05651','2104.10350','2109.05472','2111.00364','2204.05149','2206.05229','2211.02001','2304.03271','2309.14393','2310.03003','2311.16863'],
 'memory bandwidth': ['2403.14123','2007.00072','2205.14135','2211.05102','2306.14048','2309.06180','2311.18677','2312.11514','2401.09670','2402.02750','2402.16363','2407.00079'],
 'training data supply': ['2211.04325','2305.16264','2305.17493','2107.06499','2306.01116','2306.11644','2406.17557','2407.14933','2206.14486'],
 'algorithmic efficiency': ['2001.08361','2203.15556','2005.04305','2212.05153','2403.05812','2009.06732','2101.03961','2112.06905','2208.07339','2210.17323'],
 'cost': ['2405.21015','2007.05558','2305.05176'],
 'talent and access': ['2103.06312','2205.03468'],
 'regulation and governance': ['2307.03718','2402.08797','2305.15324','2307.04699','2303.11341','2405.10799'],
}
HOLDOUT = {
 'H1': ('2403.14123', 'Memory bandwidth, not compute, has become the primary bottleneck for LLM serving and decoder inference.',
        ['However, the main performance bottleneck is increasingly shifting to memory bandwidth.',
         'This disparity has made memory, rather than compute, the primary bottleneck in AI applications, particularly in serving.',
         'Here, we analyze encoder and decoder Transformer models and show how memory bandwidth can become the dominant bottleneck for decoder models.',
         'Yet, with larger batch sizes and longer context lengths, the key-value (KV) cache, which stores attention keys and values to avoid re-computations, significantly increases memory demands and becomes the new bottleneck in speed and memory usage.',
         'This framework identifies the bottlenecks when deploying LLMs on hardware devices and provides a clear understanding of practical problems, such as why LLMs are memory-bound, how much memory and computation they need, and how to choose the right hardware.'],
        dict(full=[['memory'], ['serving', 'inference', 'decod', 'throughput', 'latency']], partial=[['memory'], ['bottleneck', 'performance', 'compute', 'model']])),
 'H2': ('2203.15556', 'At a fixed compute budget, model size and training tokens should scale equally; many large models are undertrained for lack of data.',
        ['We find that current large language models are significantly undertrained, a consequence of the recent focus on scaling language models whilst keeping the amount of training data constant.',
         'By training over 400 language models ranging from 70 million to over 16 billion parameters on 5 to 500 billion tokens, we find that for compute-optimal training, the model size and the number of training tokens should be scaled equally: for every doubling of model size the number of training tokens should also be doubled.'],
        dict(full=[['data', 'token'], ['model size', 'parameter', 'compute-optimal', 'model performance', 'loss']], partial=[['data', 'token'], ['model', 'scaling', 'training']])),
 'H3': ('2211.04325', 'The stock of public human-generated text will be exhausted by LLM training datasets around 2026-2032.',
        ['Our findings indicate that if current LLM development trends continue, models will be trained on datasets roughly equal in size to the available stock of public human text data between 2026 and 2032, or slightly earlier if models are overtrained.',
         'Extrapolating this trend suggests that training dataset size may soon be limited by the amount of text data available on the internet.'],
        dict(full=[['text data', 'human text', 'human-generated', 'data stock', 'web data', 'internet'], ['scaling', 'dataset size', 'training data', 'llm']], partial=[['data'], ['scaling', 'scale']])),
 'H4': ('2005.04305', 'Algorithmic efficiency gains (doubling every ~16 months) cut the compute needed for fixed capability faster than hardware gains.',
        ['We show that the number of floating-point operations required to train a classifier to AlexNet-level performance on ImageNet has decreased by a factor of 44x between 2012 and 2019.',
         'This corresponds to algorithmic efficiency doubling every 16 months over a period of 7 years.',
         "By contrast, Moore's Law would only have yielded an 11x cost improvement."],
        dict(full=[['algorithm'], ['compute', 'flop', 'cost']], partial=[['algorithm', 'efficien'], ['compute', 'progress', 'performance']])),
 'H5': ('2104.10350', 'The choice of model, datacenter and processor can reduce the carbon footprint of training by up to ~100-1000x.',
        ['Remarkably, the choice of DNN, datacenter, and processor can reduce the carbon footprint up to ~100-1000X.'],
        dict(full=[['datacenter', 'data center', 'processor', 'accelerator', 'hardware', 'location', 'sparse'], ['carbon', 'emission', 'co2']], partial=[['carbon', 'emission', 'energy'], ['training', 'model']])),
 'H6': ('2305.16264', 'Under data constraints, repeating data up to ~4 epochs is nearly as good as unique data, after which extra compute loses value.',
        ['We find that with constrained data for a fixed compute budget, training with up to 4 epochs of repeated data yields negligible changes to loss compared to having unique data.',
         'However, with more repetition, the value of adding compute eventually decays to zero.'],
        dict(full=[['repeat', 'repetition', 'epoch', 'data scarcity', 'constrained data'], ['compute', 'loss']], partial=[['data'], ['compute']])),
 'H7': ('2007.05558', 'Deep learning progress is strongly reliant on growing compute, which makes it economically and environmentally unsustainable along current lines.',
        ['This article catalogs the extent of this dependency, showing that progress across a wide variety of applications is strongly reliant on increases in computing power.',
         'Extrapolating forward this reliance reveals that progress along current lines is rapidly becoming economically, technically, and environmentally unsustainable.'],
        dict(full=[['comput'], ['progress', 'cost', 'unsustainab', 'environment']], partial=[['comput'], ['deep learning', 'performance', 'capabilit']])),
 'H8': ('2405.21015', 'AI accelerator chips (and staff) are the largest expenses in training frontier models. The growth rate of training cost is context, not part of this finding.',
        ['The analysis reveals that the amortized cost to train the most compute-intensive models has grown precipitously at a rate of 2.4x per year since 2016 (90% CI: 2.0x to 2.9x).',
         'For key frontier models, such as GPT-4 and Gemini, the most significant expenses are AI accelerator chips and staff costs, each costing tens of millions of dollars.'],
        dict(full=[['accelerator', 'chip', 'hardware', 'staff', 'compute'], ['cost', 'expense']], partial=[['cost'], ['training', 'model']])),
 'H9': ('2305.17493', 'Training on model-generated content causes irreversible model collapse.',
        ['We find that use of model-generated content in training causes irreversible defects in the resulting models, where tails of the original content distribution disappear.'],
        dict(full=[['generated', 'synthetic'], ['collapse', 'defect', 'degrad', 'quality', 'performance']], partial=[['generated', 'synthetic'], ['model', 'training', 'data']])),
}
subtopic = {pid: name for name, ids in SUB.items() for pid in ids}
assert set(subtopic) == set(meta), sorted(set(meta) ^ set(subtopic))
removed = {}
for key, (pid, finding, passages, _) in HOLDOUT.items():
    for p in passages:
        owners = [k for k, m in meta.items() if p in m['abstract']]
        assert owners, (key, p[:60])
        for owner in owners:
            removed.setdefault(owner, []).append(p)
import unicodedata
def clean(text):
    text = unicodedata.normalize('NFKC', text)
    text = ''.join(ch for ch in text if ch in '\n\t' or unicodedata.category(ch)[0] != 'C')
    text = re.sub(r'\$\\times\$', 'x', text)
    text = re.sub(r'\$([^$]*)\$', lambda m: re.sub(r'[\\{}_^]', '', m[1]), text)
    return ' '.join(text.split())
SENT = re.compile(r'(?<=[.!?])\s+(?=[A-Z0-9(])')
FULL_OK = ('/by/', '/by-sa/', 'publicdomain')
textdir = pathlib.Path(sys.argv[3])
def states(sentence, groups):
    low = sentence.casefold()
    return all(any(term in low for term in group) for group in groups)
VOCAB = set()
for pid in meta:
    VOCAB.update(w.casefold() for w in re.findall(r'[A-Za-z]+', meta[pid]['abstract'] + ' ' + (meta[pid]['title'] or '')))
    if (textdir / f'{pid}.txt').exists():
        VOCAB.update(w.casefold() for w in re.findall(r'[A-Za-z]+', (textdir / f'{pid}.txt').read_text()))
LIGATURE_FIXES = 0
def repair(text):
    # PDF extraction drops fi/ff/fl/ffi/ffl ligatures as a space ("signi cant"). Rejoin a split only
    # when the joined word appears intact elsewhere in the corpus.
    global LIGATURE_FIXES
    def join(match):
        global LIGATURE_FIXES
        left, right = match[1], match[2]
        for lig in ('fi', 'ff', 'fl', 'ffi', 'ffl'):
            word = left + lig + right
            if word.casefold() in VOCAB and (left + right).casefold() not in VOCAB:
                LIGATURE_FIXES += 1
                return word
        return match[0]
    return re.sub(r'\b([A-Za-z]{1,12}) ([a-z]{1,12})\b', join, text)
rows, removal_log = [], {k: 0 for k in HOLDOUT}
NORMALIZED = [re.sub(r'[^a-z]', '', p.casefold()) for v in HOLDOUT.values() for p in v[2]]
for pid in sorted(meta):
    m = meta[pid]
    full = textdir / f'{pid}.txt'
    use_full = bool(m['licence']) and any(t in m['licence'] for t in FULL_OK) and full.exists() and full.stat().st_size > 1000
    paragraphs = [repair(p) for p in full.read_text().split('\n\n')] if use_full else [m['abstract']]
    kept = []
    for para in paragraphs:
        para = clean(para)
        for passage in removed.get(pid, []):
            if clean(passage) in para:
                para = para.replace(clean(passage), '')
        sentences = []
        for sentence in SENT.split(para):
            norm = re.sub(r'[^a-z]', '', sentence.casefold())
            if len(norm) > 30 and any(norm in passage or passage in norm for passage in NORMALIZED):
                removal_log['explicit'] = removal_log.get('explicit', 0) + 1
                continue
            hit = [k for k, v in HOLDOUT.items() if states(sentence, v[3]['full'])]
            if hit:
                for k in hit:
                    removal_log[k] += 1
                continue
            sentences.append(sentence)
        para = ' '.join(' '.join(sentences).split())
        if len(para) >= 40:
            kept.append(para)
    name = 'arxiv-' + pid.replace('.', '-')
    (out / f'{name}.md').write_text(f'# {clean(m["title"])}\n\n' + '\n\n'.join(kept) + '\n')
    rows.append((subtopic[pid], name, clean(m['title']), pid, m['date'], m['licence'],
                 'full text (first ~40k characters, before references)' if use_full else 'abstract only'))
src = ['# AI-bottlenecks corpus sources', '',
       'Each file holds one arXiv paper, fetched from arXiv on 2026-11-21. Papers released under CC BY 4.0 or '
       'CC BY-SA 4.0 contribute their body text (PDF text extraction with pypdf, before the references, capped at '
       'about 40,000 characters); the text is modified only by whitespace clean-up and the holdout removals described '
       'in `holdout.md`. All other papers (arXiv non-exclusive licence, CC BY-NC-SA, CC BY-NC-ND) contribute only '
       'their abstract, which arXiv releases as CC0 1.0 metadata (https://info.arxiv.org/help/license/index.html). '
       'Copyright in each paper remains with its authors; see the URL for attribution.', '',
       '| Subtopic | File | Title | URL | Date | Licence | Content used |', '|---|---|---|---|---|---|---|']
for sub, name, title, pid, date, lic, used in sorted(rows):
    src.append(f'| {sub} | `{name}.md` | {title.replace("|", "/")} | https://arxiv.org/abs/{pid} | {date} | {lic} | {used} |')
src += ['', f'{len(rows)} documents. Subtopic counts: ' + ', '.join(f'{k} {len(v)}' for k, v in SUB.items()) + '.']
(out / 'SOURCES.md').write_text('\n'.join(src) + '\n')
hold = ['# Holdout findings', '',
        'These findings are stated in the source abstracts. The listed passages were removed from the ingested files, so no '
        'ingested chunk states them directly. A Frontier hypothesis rediscovers a finding **fully** when its text and anchors '
        'contain a term from each `full` group, and **partially** when they contain a term from each `partial` group. '
        'Matching is case-insensitive substring matching on the hypothesis text.', '',
        'Removal was applied twice. First, the passages below were cut wherever they occur. Second, every sentence in '
        'the corpus that contains a term from each `full` group of any finding was dropped, so no ingested sentence '
        'states a finding in the terms used to score it. Sentences dropped by the second rule: '
        + ', '.join(f'{k} {v}' for k, v in removal_log.items() if k != 'explicit')
        + f'. Sentences dropped by the first rule outside the abstracts: {removal_log.get("explicit", 0)}.', '']
for key, (pid, finding, passages, criteria) in HOLDOUT.items():
    hold += [f'## {key}. {finding}', '', f'Source: https://arxiv.org/abs/{pid}', '', 'Removed passages:', '']
    hold += [f'> {clean(p)}' for p in passages]
    hold += ['', f'Full match groups: {criteria["full"]}', '', f'Partial match groups: {criteria["partial"]}', '']
(out / 'holdout.md').write_text('\n'.join(hold))
json.dump({k: dict(source=v[0], finding=v[1], criteria=v[3]) for k, v in HOLDOUT.items()},
          open(out / 'holdout.json', 'w'), indent=1)
print(len(rows), 'documents', LIGATURE_FIXES, 'ligature repairs')
