#!/usr/bin/env python3
"""LLM task prompts + robust JSON parsing, with a MOCK mode (env MOCK=1) so the
whole pipeline can be validated with no network / no key."""
import json, os, re
import orclient

MOCK = os.environ.get("MOCK") == "1"

def _parse_json(txt):
    m = re.search(r"\{.*\}", txt, re.S)
    if not m: raise ValueError(f"no json in: {txt[:120]}")
    return json.loads(m.group(0))

# ---------- 1. LLM-as-judge: is the RU gloss right for this word in context? ----------
JUDGE_SYS = ("You are a bilingual Armenian–Russian linguist grading a language-learning "
    "app. You are strict, fair, and terse.")
JUDGE_TMPL = (
 "Armenian phrase (spoken, may be colloquial/dialectal):\n«{seg}»\n\n"
 "Target word: «{word}»\n"
 "App's Russian gloss for that word IN THIS CONTEXT: «{gloss}»\n\n"
 "Is the gloss a correct translation of the target word AS USED HERE?\n"
 'Reply ONLY JSON: {{"verdict":"correct|acceptable|wrong",'
 '"correct_gloss":"<best RU gloss in this context>","reason":"<=12 words"}}')

def judge_gloss(model, seg, word, gloss):
    if MOCK:
        v = "wrong" if len(word) % 7 == 0 else ("acceptable" if len(word)%5==0 else "correct")
        return {"verdict":v,"correct_gloss":gloss,"reason":"mock"}
    out = orclient.chat(model,
        [{"role":"system","content":JUDGE_SYS},
         {"role":"user","content":JUDGE_TMPL.format(seg=seg,word=word,gloss=gloss)}],
        temperature=0.0, max_tokens=160, json_mode=True)
    return _parse_json(out)

# ---------- 2. controlled baseline: gloss WITH vs WITHOUT context (same model) ----------
CTX_TMPL = ('Armenian phrase: «{seg}»\nTranslate ONLY the word «{word}» into Russian, '
    'choosing the meaning it has IN THIS PHRASE.\nReply ONLY JSON: {{"gloss":"<russian>"}}')
NOCTX_TMPL = ('Translate the Armenian word «{word}» into Russian (its most common '
    'dictionary meaning, no context).\nReply ONLY JSON: {{"gloss":"<russian>"}}')

def gloss_in_context(model, seg, word):
    if MOCK: return {"gloss": f"ctx:{word}"}
    return _parse_json(orclient.chat(model,
        [{"role":"user","content":CTX_TMPL.format(seg=seg,word=word)}],
        temperature=0.0, max_tokens=60, json_mode=True))

def gloss_no_context(model, word):
    if MOCK: return {"gloss": f"noctx:{word}"}
    return _parse_json(orclient.chat(model,
        [{"role":"user","content":NOCTX_TMPL.format(word=word)}],
        temperature=0.0, max_tokens=60, json_mode=True))

# ---------- 3. semantic match judge: do two RU glosses mean the same here? ----------
MATCH_TMPL = ('Armenian phrase: «{seg}»\nWord: «{word}»\n'
    'Gold Russian meaning (correct in this context): «{gold}»\n'
    'Candidate Russian gloss: «{cand}»\n'
    'Does the candidate convey the SAME meaning as the gold for this word here '
    '(synonyms/inflection ok)?\nReply ONLY JSON: {{"match":true|false}}')

def glosses_match(model, seg, word, gold, cand):
    if MOCK: return {"match": gold.strip().lower()==cand.strip().lower()}
    return _parse_json(orclient.chat(model,
        [{"role":"user","content":MATCH_TMPL.format(seg=seg,word=word,gold=gold,cand=cand)}],
        temperature=0.0, max_tokens=20, json_mode=True))

# ---------- 5. grammar/note judge: is the model's linguistic claim true? ----------
NOTE_SYS=("You are a strict bilingual Armenian–Russian linguist. You verify whether a "
 "grammatical/etymological/register claim about an Armenian word is TRUE. Be terse.")
NOTE_TMPL=(
 "Armenian sentence: «{seg}»\n"
 "Word: «{word}»   (Russian gloss: «{gloss}»)\n"
 "Claim to verify: «{note}»\n\n"
 "Is the claim linguistically correct for this word in this context?\n"
 'Reply ONLY JSON: {{"verdict":"correct|partial|wrong",'
 '"reason":"<=15 words","fix":"<correct claim if not correct, else empty>"}}')

def judge_note(model, seg, word, gloss, note):
    if MOCK:
        v="wrong" if len(note)%9==0 else ("partial" if len(note)%5==0 else "correct")
        return {"verdict":v,"reason":"mock","fix":""}
    return _parse_json(orclient.chat(model,
        [{"role":"system","content":NOTE_SYS},
         {"role":"user","content":NOTE_TMPL.format(seg=seg,word=word,gloss=gloss or "",note=note)}],
        temperature=0.0, max_tokens=120, json_mode=True))

# ---------- 4. THE PRODUCTION COMPONENT: translate a segment ----------
# Takes an ASR segment (sentence + ordered tokens) and returns the full-sentence
# translation, a gloss per token IN ORDER, and notes for tricky/colloquial words.
TRANSLATE_SYS = ("You translate spoken, often colloquial/dialectal Armenian for "
 "{lang}-speaking learners. Glosses must fit the word's meaning IN THIS SENTENCE, "
 "not its dictionary default. Output STRICT JSON only.")
TRANSLATE_TMPL = (
 "Armenian sentence (spoken): «{sent}»\n\n"
 "Tokens (translate EACH in this context, keep exact order and count = {n}):\n{toklist}\n\n"
 'Return JSON: {{"sentence":"<full {lang} translation>",'
 '"glosses":["<{lang} for token 0>", ... exactly {n} items in order],'
 '"notes":[{{"word":"<armenian>","gloss":"<{lang}>","note":"<short: slang/contraction/grammar>"}}]}}')

def translate_segment(model, sentence, tokens, target="Russian", max_tokens=3000, reasoning=None):
    n = len(tokens)
    if MOCK:
        return {"sentence": f"[{target}] {sentence}",
                "glosses": [f"g:{t}" for t in tokens],
                "notes": [{"word": tokens[0], "gloss": "mock", "note": "mock"}] if tokens else []}
    toklist = "\n".join(f"{i}: {t}" for i, t in enumerate(tokens))
    out = orclient.chat(model,
        [{"role":"system","content":TRANSLATE_SYS.format(lang=target)},
         {"role":"user","content":TRANSLATE_TMPL.format(sent=sentence,n=n,toklist=toklist,lang=target)}],
        temperature=0.0, max_tokens=max_tokens, json_mode=True, reasoning=reasoning)
    return _parse_json(out)
