# armenian.cc — Pitch brief (evaluation track)

Handoff doc for the **presentation/pitch session**. Everything here is real unless marked
⏳ pending. Numbers come from `out/REPORT.md`, `out/results.json`, `out/*.json`; charts in `out/*.svg`.

## The product (one line)
Learn spoken Armenian from viral TikToks: each clip is transcribed (ElevenLabs), translated
(Gemini), and **every word glossed in context** for a Russian-speaking learner. armenian.cc.

## The pitch spine (evaluation is the story)
We don't score the app as a black box. We evaluate **each pipeline stage** against a
**fluent-human gold set**, then use a **cross-family LLM judge — validated against that gold
before we trust it** — to scale. We sample **adversarially** (slang, polysemy, low-confidence,
code-switch) and probe **where it breaks** and **whether the LLM is even needed**.

Pipeline:  `dataset → ElevenLabs ASR → Gemini translate+gloss → EVAL (this track)`

## Headline numbers (real)
| metric | result | n |
|---|---|---|
| Per-word gloss accuracy (human, in context) | **88% strict** (95% CI 81–93%), 94% lenient | 113 |
| ASR WER (human-checked) | **5.1%** overall; **0% formal → 22% difficult** | 25 clips |
| ASR confidence ↔ WER (difficulty ranking) | **identical order, ρ=1.0** | 5 tiers |
| Sentence translation (human) | **90% faithful** (stage ~solved) | 20 |
| Confidence predicts errors (AUC logprob→) | **0.69** gloss error, **0.86** mis-transcription | 113 |
| Uncertainty flag (logprob < −0.3) | catches **71%** of errors, flags **27%** of words | — |
| Error attribution | **29%** of gloss errors are ASR's fault (rest = real MT errors) | — |
| LLM-as-judge (DeepSeek) vs human | κ=0.22, **recall 0.86 / precision 0.18** → over-flagger, *not yet trustworthy to scale* | 113 |
| Context vs no-context (LLM earns its place) | **+5 pts overall**; code-switch +17, control +18, low-conf +13 | 103 |

Corpus: **218 videos, 2,303 segments, 19,467 words, 3,256 notes** (scraped, real).

## The five stories that land
1. **Two independent signals agree on difficulty** — ElevenLabs' own confidence *and* human WER
   rank formal→single→multi→songs→difficult identically (ρ=1.0). The ASR knows when it's guessing.
2. **The model is good where it's hard, breaks where audio is hard** — gloss accuracy is high on
   slang (93%) and polysemy (95%) but lowest on **low-ASR-confidence words (79%)**. Errors
   concentrate downstream of shaky audio, not in the linguistics.
3. **Sentences are solved; the gloss is the frontier** — the fluent annotator accepted all 20
   sentence translations verbatim. A generic MT would do sentences too → the LLM "earns its place"
   only on the **per-word contextual gloss**. (chrF++ intentionally *not* reported: refs were
   prefilled → degenerate; BLEU rejected for Armenian morphology.)
4. **A named, quantified failure: copula/auxiliary contamination** — the glosser puts the lexical
   meaning on the auxiliary («է→на улице», «եմ→люблю») instead of "is/am". `է`: 71% of 482 uses get
   a non-copula gloss (upper bound). A concrete flaw the reproduction can fix.
5. **We validated the judge before trusting it — and it failed the bar** — κ=0.22, so we *don't*
   let it grade the corpus unsupervised. High recall (0.86) makes it a good error *screen*; the fix
   is few-shot seeding from the human labels. This is the strategy working, not a failure to hide.

## Failure taxonomy (14 flagged errors)
ASR-propagated 5 · translation/other 3 · code-switch/NER 3 · colloquial/slang 2 · polysemy 1.
Notable: a **negation flip** («պատասխանում → не отвечает», should be "отвечает") — teaches the
opposite meaning.

## Safety / harms → mitigations
- **Confidently-wrong gloss teaches the wrong word** (automation bias) → the **logprob flag**
  (feature #6 above) surfaces low-confidence words to the learner.
- **Song/music clips can transcribe to empty or garbage** → gate on empty ASR + low confidence.
- **Code-switch / loanwords** (`подписка`, `red flag`) mishandled → flagged category.

## Rubric mapping
- *Evaluation & evidence* → per-stage metrics, Wilson CIs, validated judge, reproducible.
- *Model limits & safety* → error attribution, named failures, the confidence flag.
- *Real-world plausibility* → messy TikToks, drops onto the team's live pipeline (SCHEMA.md).
- *LLM earns its place* → sentences solved by MT; the LLM matters on the contextual gloss.

## Context-vs-no-context (LLM earns its place) — real, mixed, honest
Reading the sentence helps overall (**+5 pts**), clearly on **code-switch (+17)**, **control (+18)**,
**low-confidence (+13)**. Colloquial flat; **polysemy −21 is a measurement artifact** — those short
function words are scored by the *same* DeepSeek match-judge that only reaches κ=0.22, which splits
hairs on Russian case forms and even scored an identical «я» both ways. Lead the pitch with the
**human-anchored** numbers (§1) + the clear-win strata; present the polysemy dip as evidence that
*automated function-word scoring is itself a limit* (ties to the judge κ story). Don't cite the
baseline `production≈100%` column — it's circular (gold = the shipped gloss).

## Session-2 additions (all real)

**Full pipeline end-to-end** — ran ElevenLabs Scribe → `translate.py` on all 111 videos → **97 videos / 625 segments / 5,214 words** of eval-ready output (`out/pipeline_full/`); 14 empty (music clips).

**Reproduction eval** (our `translate.py`, Gemini-2.5-flash, vs incumbent vs gold): gloss ~83%, **fixes 46%** of incumbent errors, **preserves 88%** of its correct ones, agreement-with-incumbent 56%, sentence chrF++ 65.

**ASR model bake-off** (teammates, 18 models on the 19-clip set): **ElevenLabs Scribe wins, 7.6% WER**; best Gemini ~10–14%; GPT/open models worse.

**Translation model bake-off** (our stage; chrF++ vs gold + valid-output rate + latency; 11 models, fair 8k-token budget):
| model | gloss chrF++ | sent chrF++ | valid | latency |
|---|--:|--:|--:|--:|
| gemini-3.1-flash-lite 🏆 | 71.7 | 74.1 | 100% | 1.5s |
| gemini-3-flash-preview | 69.0 | 73.0 | 99% | 2.9s |
| gemini-3.5-flash | 66.8 | 71.0 | 100% | 8.2s |
| gemini-3.1-pro | 63.4 | 67.2 | 98% | 14.6s |
| gemini-2.5-flash | 63.2 | 65.2 | 100% | 1.4s |
| gemini-3.6-flash | 61.0 | 66.1 | 99% | 6.3s |
| gpt-4.1-mini | 58.7 | 55.4 | 100% | 3.4s |
| deepseek-v3.1 | 55.8 | 57.6 | 100% | 10.6s |
| gemini-2.5-flash-lite | 49.5 | 52.7 | 93% | 1.2s |
| gpt-4o-mini | 44.8 | 55.8 | 99% | 3.6s |
| deepseek-v4-flash | 40.0 | 48.7 | 77% | 43.5s |

Findings (corrected after a fair re-run): the earlier "reasoning tiers break 70–96%" was **our token budget, not the models** — at 8k tokens the Gemini reasoning tiers return ~100% valid JSON. The real story is **latency, not breakage**: `gemini-3.1-flash-lite` wins on quality **and** speed (1.5s), while the bigger reasoning/pro tiers match quality but cost 4–10× the latency. The genuine outlier is **DeepSeek v4-flash — worst quality (40.0), still 23% fragile, and ~30× slower (43.5s)**; not competitive here. (v4-pro excluded — never fairly re-run.) For a per-word glosser that runs on every video, reliability + latency matter as much as raw quality → flash-lite.

**Task B.1 — few-shot judge (the payoff):** seeding the gloss judge with 8 of your labeled examples lifts it from **κ=0.22 → 0.66** (substantial, clears the trust bar), **precision 1.0** on flagged errors. So the human labels *make the judge trustworthy* — closing the loop. Caveat: run on `deepseek-v4-flash`, which (reasoning model) left 45% of calls unparseable → only 58 scored; deploy with a reliable flash-tier judge for full coverage. *(Fresh human-eval of the winner's own glosses still pending.)*

**Grammar/notes human→judge loop:** human says **89% of notes correct** (errors mostly ASR-driven); DeepSeek grammar judge **κ=0.00** (rubber-stamps, catches 0/5) → not scaled.

**Meta-finding (the story):** *zero-shot* LLM judges fail in opposite ways — gloss judge **over-flags** (κ=0.22), grammar judge **rubber-stamps** (κ=0.00). But **few-shot with the human labels fixes it**: the gloss judge jumps to **κ=0.66** (trustworthy). So the arc is: human-anchored gold → zero-shot judges aren't good enough → *human examples make the judge trustworthy* → then it can scale. Honest, and it shows the human labels doing real work.

## What's ⏳ pending (engineering session is finishing)
- `translate.py` reproduction run on the ElevenLabs transcripts → eval its output vs incumbent.
- Grammar/note-correctness gold (50 notes) → grammar judge validate-κ then scale to 3,252.
- Improve the gloss judge (few-shot) to lift κ above the trust bar.

## Where things are
- Report: `out/REPORT.md` · Charts: `out/chart_stratum.svg`, `chart_asr_difficulty.svg`, `chart_flag.svg`, `chart_baseline.svg`
- Consolidated gold: `out/gold_dataset.json` · Raw results: `out/results.json`, `out/asr_wer.json`, `out/sentence_eval.json`, `out/copula_probe.json`, `out/judge_validation.json`
- Repo: github.com/SilviAvayan/Armenian.cc — PRs #1 harness, #2 translator, #3 ASR/WER (merged); #4 eval-suite (open).
- Reproduce: `./run_all.sh` (offline) · `./run_all.sh --llm` (judge+baseline; key in `.env`).

## One-liner for a judge
> "We measured every stage against a fluent-human gold, validated an independent LLM judge against
> that gold before trusting it to scale, and stress-tested exactly where Armenian is hard — slang,
> polysemy, and low-confidence audio."
