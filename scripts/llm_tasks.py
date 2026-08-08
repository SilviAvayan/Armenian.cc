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
