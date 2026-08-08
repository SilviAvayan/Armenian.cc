#!/usr/bin/env python3
"""Rebuild dataset/transcripts/google_chirp_3.basic from ~/Downloads/chirp_results.json.
Applies the three quality gates (loop / impossible-rate / wrong-script) and two
embedded overrides where an earlier run's clean text beats the stored one.
Run from the repo root:  python3 rebuild_chirp.py"""
import json, re, collections
from pathlib import Path

OVERRIDES = {
  "multi_speakers__simpo.....samo_7629307328130501904": "Կներեք, դուք ասեցիք, որ մի քիչ ուշ մեր պատվերը կգա, բայց արդեն երկու ժամ ա լռանում, ի՞նչ եղավ մեր պատվերը։ Ո՞ր հասցեն ա ձեր հասցեն։ Երևան, Թաղամաս։ Սոված մերը դուք մտածում եք։ Մինչև տաս-տասնհինգ րոպե կհասնի, հա։ Շատ վատ եք աշխատում, ինչի՞ եք էսքան ուշ բերում։ Բարև, ներողություն, պատվերները շատ-շատ ա, դրա համար ուշացում եղավ։ Տասնհինգ րոպեից մեր պատվերը սեղանին լինի։ Այո, տասնհինգ րոպեից ձեր մոտ կլինի պատվերը։ Դե սոված ենք, կարաս ջան, մեզ քյաբաբ և մեզ ուտելիք բերեք, էլի մենք սպասելով։ Եղավ, պուճուր ջան, հիմա արագ կմոտեցնենք։ Մերսի։ Պակա։",
  "multi_speakers__zhanna_jaan_7668233361306995988": "Ի՞նչ ա մոտը, ի՞նչ ա մոտը։ Գիշերվա մեկն ա, ի՞նչ կուրս, կորչո՞ւյս։ Չէ, ո՞վ։ Կորչողները վելել են։ Գիշերվա մեկն ա։ Ի՞նչ ա մոտը, ի՞նչ ա մոտը, շոկի մեջ եմ։ Կողքդ նստողը կուրսի՞ ա, կուրսի՞։ Նար, հարսանիքի ենք գնացել։ Հասի, տոռեկոները... Իշի քաշորիքները։ Չէ։ Դու երեսուն երեք, տե, ի՞նչ ա մոտը, ի՞նչ ա մոտը։ Նարա, ի՞նչ ես ասում, դու չես էկել։ Ասա, որ սիրուն ենք էս էլի։ Ես երկու կուրս սիրուն ենք հարսանիքին։ Նար, քեզ ի՞նչ թանգ ա։ Դու սպասի... Ես ամենավերջում սաղի դիմակները պատռելու եմ։ Դու սպասի վարդիկ տատ, դու սպասի... Մաման տեսել ա, ասում ա շատ սիրուն ենք։ Հա, բայց էս ժամի՞ն։ Ի՞նչն ա նորմալ չի։ Էս ժամին, էս շորերով, կարմիր, յարկի գույնով, սաղ աշխարհի դեմը... Ի՞նչն ա մոտ։ Դու սպասի էս վարդիկը, ժամն ա եկել։ Ի՞նչ անենք։ Մեկ իրիկուն ա ժամը։ Հետո՞։ Ի՞նչ ա հետո, յարկի կարմիր գույն... ի՞նչ ա մոտը։ Նստավ։ Նինա, բա սենց կա՞րճը հագնում ես։ Էս կարճ... Էկել ես... Մոռաց նայի մի հատ։ Վայ, Նարեն հարսանիքից եկել... Այդ պատճառով դու հարսանիք չեք եկել իմ հետ։ Դու երկար էիր հագնելու։",
}

def degenerate(t, dur):
    letters = re.findall(r"[A-Za-z\u0400-\u04FF\u0530-\u058F\u0600-\u06FF\u0900-\u097F]", t)
    if len(letters) >= 5:
        arm = sum(1 for c in letters if "\u0530" <= c <= "\u058F")
        if arm / len(letters) < 0.5:
            return "wrong script"
    w = t.split()
    if dur > 3 and len(w) / dur > 6.0:
        return "impossible rate"
    if len(w) >= 20:
        g = collections.Counter(tuple(w[i:i+5]) for i in range(len(w)-4))
        c = g.most_common(1)[0][1]
        if c >= 15 and c*5/len(w) > 0.6:
            return "loop"
    return None

src = Path.home()/"Downloads"/"chirp_results.json"
d = json.loads(src.read_text(encoding="utf-8"))
ROOT = Path("dataset/transcripts/google_chirp_3.basic")
n = 0
for k, v in d.items():
    cat, clip, dur = v["category"], v["clip"], v["duration"]
    if k in OVERRIDES:
        text = OVERRIDES[k]
        chunks = [{"index":1,"offset":0.0,"text":text,
                   "usage":{"audio_seconds":None,"cost":None},
                   "latency_seconds":None,"variant":"reassembled (v3 run)",
                   "provider_model":"google/chirp-3"}]
    else:
        chunks = []
        parts = []
        for s in v["segments"]:
            t = (s.get("text") or "").strip()
            if t and degenerate(t, s.get("seg_duration",0)):
                t = ""
            if t: parts.append(t)
            chunks.append({"index":s["index"],"offset":s["offset"],"text":t,
                "usage":{"audio_seconds":s.get("audio_seconds"),"cost":s.get("cost")},
                "latency_seconds":s.get("latency"),"variant":s.get("variant"),
                "provider_model":"google/chirp-3"})
        text = " ".join(parts).strip()
    p = ROOT/cat; p.mkdir(parents=True, exist_ok=True)
    (p/(clip+".txt")).write_text(text+"\n", encoding="utf-8")
    payload = {"source":clip+".mp4","model":"google/chirp-3","requested_language":"hy",
        "endpoint":"openrouter /v1/audio/transcriptions",
        "method":"silence-aligned chunking <=51s + fallback ladder (wav-first) + quality gates (loop/rate/script)",
        "duration_seconds":dur,"ok":bool(text),"text":text,"chunks":chunks}
    if not text:
        payload["note"] = "model returned empty/degenerate output on every attempt (music-heavy or refused clip)"
    (p/(clip+".json")).write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n",
                                  encoding="utf-8")
    n += 1
print(f"rebuilt {n} clips under {ROOT}")
