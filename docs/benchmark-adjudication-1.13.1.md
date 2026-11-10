# CPU-LLM 1.13.1 benchmark adjudication

Review of all 67 missed rows across 40 distinct cases. Classifications are provisional where request policy or conversational state needs further review. Historical scores remain frozen.

## Misses

- **direct-har-05** (2). Explicit request missed or incomplete against gold evidence. dense-dev insufficient, resonance-dev insufficient. Prompt “How much does the Kestrel weigh?”.
  Gold evidence — har-public-p0015 — The Kestrel weighs 18 pounds.
- **direct-har-07** (2). Correct fact in reply, full benchmark contract failed. dense-dev answer, resonance-dev answer. Prompt “Is the Kestrel violet?”.
  Gold evidence — har-public-p0012 — The Kestrel is not violet.
- **direct-arc-05** (2). Explicit request missed or incomplete against gold evidence. dense-dev insufficient, resonance-dev insufficient. Prompt “How much does the Sable weigh?”.
  Gold evidence — arc-public-p0015 — The Sable weighs 9 pounds.
- **direct-arc-06** (2). Explicit request missed or incomplete against gold evidence. dense-dev insufficient, resonance-dev insufficient. Prompt “What color is the Index?”.
  Gold evidence — arc-public-p0025 — The Index is pearl.
- **direct-arc-07** (2). Explicit request missed or incomplete against gold evidence. dense-dev answer, resonance-dev answer. Prompt “Is the Sable lilac?”.
  Gold evidence — arc-public-p0012 — The Sable is not lilac.
- **join-har-02** (2). Explicit request missed or incomplete against gold evidence. dense-dev insufficient, resonance-dev insufficient. Prompt “Does the Kestrel have a bell?”.
  Gold evidence — har-public-p0001 — The Kestrel is a survey skiff.; har-public-p0005 — Every survey skiff has a bell.
- **join-har-06** (2). Explicit request missed or incomplete against gold evidence. dense-dev insufficient, resonance-dev insufficient. Prompt “What equipment does the Kestrel have?”.
  Gold evidence — har-public-p0004 — The Kestrel has a lamp.; har-public-p0001 — The Kestrel is a survey skiff.; har-public-p0005 — Every survey skiff has a bell.
- **join-arc-06** (2). Explicit request missed or incomplete against gold evidence. dense-dev insufficient, resonance-dev insufficient. Prompt “What equipment does the Sable have?”.
  Gold evidence — arc-public-p0004 — The Sable has a prism.; arc-public-p0001 — The Sable is a survey pane.; arc-public-p0005 — Every survey pane has a shade.
- **depth-har-05** (2). Open-ended gold requires an unrequested fact. dense-dev answer, resonance-dev answer. Prompt “Tell me about the Kestrel.”.
  Gold evidence — har-public-p0001 — The Kestrel is a survey skiff.
- **depth-arc-06** (2). Open-ended gold requires an unrequested fact. dense-dev answer, resonance-dev answer. Prompt “Summarize the Sable in bullets.”.
  Gold evidence — arc-public-p0001 — The Sable is a survey pane.
- **depth-gal-07** (2). Input robustness or budget contract. dense-dev insufficient, resonance-dev insufficient. Prompt “What color is the Wicker? Background: The shed note is not evidence. The shed note is not evidence. The shed note is not evidence. The shed note is not evidence. The shed” (truncated).
  Gold evidence — gal-public-p0002 — The Wicker is olive.
- **separation-har-10** (2). Input robustness or budget contract. dense-dev insufficient, resonance-dev insufficient. Prompt “What color is the Kestrel? ccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc” (truncated).
  Gold evidence — har-public-p0002 — The Kestrel is copper.
- **separation-har-12** (2). Input robustness or budget contract. dense-dev insufficient, resonance-dev insufficient. Prompt “What color is the Kestrel? Context: dddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddd” (truncated).
  Gold evidence — har-public-p0002 — The Kestrel is copper.
- **separation-arc-14** (2). Input robustness or budget contract. dense-dev insufficient, resonance-dev insufficient. Prompt “What color is the Kestrel? a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a” (truncated).
  Gold evidence — har-public-p0002 — The Kestrel is copper.
- **separation-gal-15** (2). Input robustness or budget contract. dense-dev partial, resonance-dev partial. Prompt “What color is the Spool? What is the Wicker? eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee” (truncated).
  Gold evidence — gal-public-p0031 — The Spool is ivory.; gal-public-p0001 — The Wicker is a survey loom.
- **separation-gal-17** (2). Explicit request missed or incomplete against gold evidence. dense-dev partial, resonance-dev partial. Prompt “What color is the Heddle? What color is the Bobbin?”.
  Gold evidence — gal-public-p0025 — The Heddle is umber.; gal-public-p0028 — The Bobbin is maize.
- **separation-gal-18** (2). Input robustness or budget contract. dense-dev budget_refusal, resonance-dev budget_refusal. Prompt “What color is the Heddle? What color is the Bobbin? Context: The gallery log is background only. The gallery log is background only. The gallery log is background only. T” (truncated).
  Gold evidence — gal-public-p0025 — The Heddle is umber.; gal-public-p0028 — The Bobbin is maize.
- **separation-gal-21** (2). Explicit request missed or incomplete against gold evidence. dense-dev partial, resonance-dev partial. Prompt “Why did the Wicker sag? What color is the Reel?”.
  Gold evidence — gal-public-p0007 — The Wicker sagged because its beam cracked.; gal-public-p0034 — The Reel is plum.
- **script-quote-hold-t1** (2). Explicit request missed or incomplete against gold evidence. dense-hold-scripts clarification, resonance-hold-scripts clarification. Prompt “Quote the sentence that says where the Kestrel lives.”.
  Gold evidence — har-public-p0003 — The Kestrel is found in Marrow.
- **direct-gal-05** (2). Explicit request missed or incomplete against gold evidence. dense-hold insufficient, resonance-hold insufficient. Prompt “How much does the Wicker weigh?”.
  Gold evidence — gal-public-p0015 — The Wicker weighs 6 pounds.
- **direct-gal-06** (2). Explicit request missed or incomplete against gold evidence. dense-hold insufficient, resonance-hold insufficient. Prompt “What color is the Heddle?”.
  Gold evidence — gal-public-p0025 — The Heddle is umber.
- **direct-gal-07** (2). Correct fact in reply, full benchmark contract failed. dense-hold answer, resonance-hold answer. Prompt “Is the Wicker rose?”.
  Gold evidence — gal-public-p0012 — The Wicker is not rose.
- **join-gal-06** (2). Explicit request missed or incomplete against gold evidence. dense-hold insufficient, resonance-hold insufficient. Prompt “What equipment does the Wicker have?”.
  Gold evidence — gal-public-p0004 — The Wicker has a shuttle.; gal-public-p0001 — The Wicker is a survey loom.; gal-public-p0005 — Every survey loom has a warp.
- **ambiguity-har-12** (2). Explicit request missed or incomplete against gold evidence. dense-hold insufficient, resonance-hold insufficient. Prompt “What color is the Kestrel and the Ibis?”.
  Gold evidence — har-public-p0002 — The Kestrel is copper.; har-public-p0020 — The Ibis is cream.
- **depth-har-14** (2). Explicit request missed or incomplete against gold evidence. dense-hold insufficient, resonance-hold insufficient. Prompt “What color is the Ibis? Use at most two sentences.”.
  Gold evidence — har-public-p0020 — The Ibis is cream.
- **separation-arc-27** (2). Explicit request missed or incomplete against gold evidence. dense-hold clarification, resonance-hold clarification. Prompt “What color is the Sable? Context: The Sable is crimson in this note.”.
  Gold evidence — arc-public-p0002 — The Sable is slate.
- **unsupported-arc-05** (2). Open-ended gold requires an unrequested fact. dense-hold partial, resonance-hold partial. Prompt “Draft a letter about the Sable.”.
  Gold evidence — arc-public-p0002 — The Sable is slate.
- **direct-har-03** (1). Explicit request missed or incomplete against gold evidence. resonance-dev clarification. Prompt “What is the Kestrel?”.
  Gold evidence — har-public-p0001 — The Kestrel is a survey skiff.
- **direct-arc-03** (1). Explicit request missed or incomplete against gold evidence. resonance-dev clarification. Prompt “What is the Sable?”.
  Gold evidence — arc-public-p0001 — The Sable is a survey pane.
- **ambiguity-har-02** (1). Bare entity permits intent clarification. resonance-dev clarification. Prompt “Kestrel”.
  Gold evidence — har-public-p0001 — The Kestrel is a survey skiff.
- **ambiguity-gal-07** (1). Bare entity permits intent clarification. resonance-dev clarification. Prompt “Wicker”.
  Gold evidence — gal-public-p0001 — The Wicker is a survey loom.
- **separation-arc-19** (1). Explicit request missed or incomplete against gold evidence. resonance-dev clarification. Prompt “What is the Sable? Where does the Sable live?”.
  Gold evidence — arc-public-p0001 — The Sable is a survey pane.; arc-public-p0003 — The Sable is found in Cinder.
- **script-expire-hold-t3** (1). Bare entity permits intent clarification. resonance-hold-scripts clarification. Prompt “Wicker”.
  Gold evidence — gal-public-p0001 — The Wicker is a survey loom.
- **script-reopen-hold-t3** (1). Bare entity permits intent clarification. resonance-hold-scripts clarification. Prompt “Kestrel”.
  Gold evidence — har-public-p0001 — The Kestrel is a survey skiff.
- **script-cancel-hold-t1** (1). Explicit request missed or incomplete against gold evidence. resonance-hold-scripts clarification. Prompt “What is the Sable? Where does it live?”.
  Gold evidence — arc-public-p0001 — The Sable is a survey pane.; arc-public-p0003 — The Sable is found in Cinder.
- **direct-gal-03** (1). Explicit request missed or incomplete against gold evidence. resonance-hold clarification. Prompt “What is the Wicker?”.
  Gold evidence — gal-public-p0001 — The Wicker is a survey loom.
- **depth-har-11** (1). Explicit request missed or incomplete against gold evidence. resonance-hold clarification. Prompt “In one sentence, what is the Kestrel?”.
  Gold evidence — har-public-p0001 — The Kestrel is a survey skiff.
- **separation-arc-30** (1). Explicit request missed or incomplete against gold evidence. resonance-hold clarification. Prompt “What is the Sable? What color is the Sable? Where does the Sable live?”.
  Gold evidence — arc-public-p0001 — The Sable is a survey pane.; arc-public-p0002 — The Sable is slate.; arc-public-p0003 — The Sable is found in Cinder.
- **separation-arc-35** (1). Explicit request missed or incomplete against gold evidence. resonance-hold clarification. Prompt “What color is the Sable? What color is the Reed? What is the Sable?”.
  Gold evidence — arc-public-p0002 — The Sable is slate.; arc-public-p0020 — The Reed is linen.; arc-public-p0001 — The Sable is a survey pane.
- **separation-gal-36** (1). Explicit request missed or incomplete against gold evidence. resonance-hold clarification. Prompt “What color is the Wicker? What is the Wicker? Where does the Wicker live? Why did the Wicker sag?”.
  Gold evidence — gal-public-p0002 — The Wicker is olive.; gal-public-p0001 — The Wicker is a survey loom.; gal-public-p0003 — The Wicker is found in Nook.; gal-public-p0007 — The Wicker sagged because its beam cracked.

## Passed-case spot checks

- **direct-har-01**. What color is the Kestrel? Gold — The Kestrel is copper.. Saved reply — From har-public-p0002: The Kestrel is copper. From har-public-p0002: The Kestrel is copper.
- **direct-arc-01**. What color is the Sable? Gold — The Sable is slate.. Saved reply — From arc-public-p0002: The Sable is slate. From arc-public-p0002: The Sable is slate.
- **join-har-01**. How long does the Kestrel live? Gold — The Kestrel is a survey skiff.; Every survey skiff lives for 19 years.. Saved reply — From har-public-p0011: The Kestrel, known as the dusk skiff, is a survey skiff. From har-public-p0001: The Kestrel is a survey skiff. From har-public-p0006: Every survey skiff lives for 19 years. From har-public-p0011: The Kestrel, known as the dusk skiff, is a survey skiff. From har-public-p0001: T
- **direct-gal-01**. What color is the Wicker? Gold — The Wicker is olive.. Saved reply — From gal-public-p0002: The Wicker is olive. From gal-public-p0002: The Wicker is olive.

All four sampled passes contained the expected evidence, and all four repeated their output. The join returned the supporting premises. Use distinct checks for claim support, proof, and presentation.

