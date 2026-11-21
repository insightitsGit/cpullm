# Holdout findings

These findings are stated in the source abstracts. The listed passages were removed from the ingested files, so no ingested chunk states them directly. A Frontier hypothesis rediscovers a finding **fully** when its text and anchors contain a term from each `full` group, and **partially** when they contain a term from each `partial` group. Matching is case-insensitive substring matching on the hypothesis text.

Removal was applied twice. First, the passages below were cut wherever they occur. Second, every sentence in the corpus that contains a term from each `full` group of any finding was dropped, so no ingested sentence states a finding in the terms used to score it. Sentences dropped by the second rule: H1 106, H2 134, H3 23, H4 130, H5 65, H6 11, H7 150, H8 134, H9 14. Sentences dropped by the first rule outside the abstracts: 1.

## H1. Memory bandwidth, not compute, has become the primary bottleneck for LLM serving and decoder inference.

Source: https://arxiv.org/abs/2403.14123

Removed passages:

> However, the main performance bottleneck is increasingly shifting to memory bandwidth.
> This disparity has made memory, rather than compute, the primary bottleneck in AI applications, particularly in serving.
> Here, we analyze encoder and decoder Transformer models and show how memory bandwidth can become the dominant bottleneck for decoder models.
> Yet, with larger batch sizes and longer context lengths, the key-value (KV) cache, which stores attention keys and values to avoid re-computations, significantly increases memory demands and becomes the new bottleneck in speed and memory usage.
> This framework identifies the bottlenecks when deploying LLMs on hardware devices and provides a clear understanding of practical problems, such as why LLMs are memory-bound, how much memory and computation they need, and how to choose the right hardware.

Full match groups: [['memory'], ['serving', 'inference', 'decod', 'throughput', 'latency']]

Partial match groups: [['memory'], ['bottleneck', 'performance', 'compute', 'model']]

## H2. At a fixed compute budget, model size and training tokens should scale equally; many large models are undertrained for lack of data.

Source: https://arxiv.org/abs/2203.15556

Removed passages:

> We find that current large language models are significantly undertrained, a consequence of the recent focus on scaling language models whilst keeping the amount of training data constant.
> By training over 400 language models ranging from 70 million to over 16 billion parameters on 5 to 500 billion tokens, we find that for compute-optimal training, the model size and the number of training tokens should be scaled equally: for every doubling of model size the number of training tokens should also be doubled.

Full match groups: [['data', 'token'], ['model size', 'parameter', 'compute-optimal', 'model performance', 'loss']]

Partial match groups: [['data', 'token'], ['model', 'scaling', 'training']]

## H3. The stock of public human-generated text will be exhausted by LLM training datasets around 2026-2032.

Source: https://arxiv.org/abs/2211.04325

Removed passages:

> Our findings indicate that if current LLM development trends continue, models will be trained on datasets roughly equal in size to the available stock of public human text data between 2026 and 2032, or slightly earlier if models are overtrained.
> Extrapolating this trend suggests that training dataset size may soon be limited by the amount of text data available on the internet.

Full match groups: [['text data', 'human text', 'human-generated', 'data stock', 'web data', 'internet'], ['scaling', 'dataset size', 'training data', 'llm']]

Partial match groups: [['data'], ['scaling', 'scale']]

## H4. Algorithmic efficiency gains (doubling every ~16 months) cut the compute needed for fixed capability faster than hardware gains.

Source: https://arxiv.org/abs/2005.04305

Removed passages:

> We show that the number of floating-point operations required to train a classifier to AlexNet-level performance on ImageNet has decreased by a factor of 44x between 2012 and 2019.
> This corresponds to algorithmic efficiency doubling every 16 months over a period of 7 years.
> By contrast, Moore's Law would only have yielded an 11x cost improvement.

Full match groups: [['algorithm'], ['compute', 'flop', 'cost']]

Partial match groups: [['algorithm', 'efficien'], ['compute', 'progress', 'performance']]

## H5. The choice of model, datacenter and processor can reduce the carbon footprint of training by up to ~100-1000x.

Source: https://arxiv.org/abs/2104.10350

Removed passages:

> Remarkably, the choice of DNN, datacenter, and processor can reduce the carbon footprint up to ~100-1000X.

Full match groups: [['datacenter', 'data center', 'processor', 'accelerator', 'hardware', 'location', 'sparse'], ['carbon', 'emission', 'co2']]

Partial match groups: [['carbon', 'emission', 'energy'], ['training', 'model']]

## H6. Under data constraints, repeating data up to ~4 epochs is nearly as good as unique data, after which extra compute loses value.

Source: https://arxiv.org/abs/2305.16264

Removed passages:

> We find that with constrained data for a fixed compute budget, training with up to 4 epochs of repeated data yields negligible changes to loss compared to having unique data.
> However, with more repetition, the value of adding compute eventually decays to zero.

Full match groups: [['repeat', 'repetition', 'epoch', 'data scarcity', 'constrained data'], ['compute', 'loss']]

Partial match groups: [['data'], ['compute']]

## H7. Deep learning progress is strongly reliant on growing compute, which makes it economically and environmentally unsustainable along current lines.

Source: https://arxiv.org/abs/2007.05558

Removed passages:

> This article catalogs the extent of this dependency, showing that progress across a wide variety of applications is strongly reliant on increases in computing power.
> Extrapolating forward this reliance reveals that progress along current lines is rapidly becoming economically, technically, and environmentally unsustainable.

Full match groups: [['comput'], ['progress', 'cost', 'unsustainab', 'environment']]

Partial match groups: [['comput'], ['deep learning', 'performance', 'capabilit']]

## H8. AI accelerator chips (and staff) are the largest expenses in training frontier models. The growth rate of training cost is context, not part of this finding.

Source: https://arxiv.org/abs/2405.21015

Removed passages:

> The analysis reveals that the amortized cost to train the most compute-intensive models has grown precipitously at a rate of 2.4x per year since 2016 (90% CI: 2.0x to 2.9x).
> For key frontier models, such as GPT-4 and Gemini, the most significant expenses are AI accelerator chips and staff costs, each costing tens of millions of dollars.

Full match groups: [['accelerator', 'chip', 'hardware', 'staff', 'compute'], ['cost', 'expense']]

Partial match groups: [['cost'], ['training', 'model']]

## H9. Training on model-generated content causes irreversible model collapse.

Source: https://arxiv.org/abs/2305.17493

Removed passages:

> We find that use of model-generated content in training causes irreversible defects in the resulting models, where tails of the original content distribution disappear.

Full match groups: [['generated', 'synthetic'], ['collapse', 'defect', 'degrad', 'quality', 'performance']]

Partial match groups: [['generated', 'synthetic'], ['model', 'training', 'data']]
