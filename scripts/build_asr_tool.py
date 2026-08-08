#!/usr/bin/env python3
"""Emit eval/asr.html — play each clip, fix the ElevenLabs transcript to exactly
what is said (or mark it already correct). The corrected text is the WER reference.
Category is hidden so checking stays unbiased."""
import json, pathlib
HERE=pathlib.Path(__file__).resolve().parent.parent
items=json.loads((HERE/"out"/"asr_items.json").read_text())
pub=[{k:s[k] for k in ("id","handle","url","src","text","start","end")} for s in items]
DATA=json.dumps(pub,ensure_ascii=False)
HTML=r"""<!DOCTYPE html><html lang="hy"><head><meta charset="utf-8">
<title>armenian.cc — transcription ground truth</title><style>
:root{--bg:#0f1115;--card:#1a1d24;--fg:#e8eaed;--mut:#9aa0aa;--acc:#58a6ff;--line:#2b2f38;--ok:#3fb950}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--fg);font:16px/1.5 -apple-system,Segoe UI,sans-serif}
header{position:sticky;top:0;background:var(--bg);border-bottom:1px solid var(--line);padding:12px 20px;display:flex;gap:16px;align-items:center}
h1{font-size:15px;margin:0}.bar{flex:1;height:8px;background:var(--card);border-radius:6px;overflow:hidden}.bar>i{display:block;height:100%;background:var(--acc);width:0}
.wrap{max-width:780px;margin:0 auto;padding:20px}.card{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:20px}
.play{padding:10px 16px;border-radius:8px;border:1px solid var(--acc);background:#12233b;color:var(--acc);cursor:pointer;font-size:15px}
.ro{font-size:19px;color:var(--mut);padding:10px;background:#0d0f13;border-radius:8px;border:1px solid var(--line);margin-top:4px}
textarea{width:100%;min-height:96px;margin-top:8px;padding:12px;border-radius:8px;border:1px solid var(--line);background:#0d0f13;color:var(--fg);font-size:22px;line-height:1.6}
.small{font-size:12px;color:var(--mut)}.nav{display:flex;gap:10px;justify-content:space-between;margin-top:16px}
.nav button,.perfect{padding:12px 18px;border-radius:9px;border:1px solid var(--line);background:#20242d;color:var(--fg);cursor:pointer;font-size:15px}
.primary{background:var(--acc)!important;color:#000!important;font-weight:600}.perfect{border-color:var(--ok);color:var(--ok);background:#12331c}
a{color:var(--acc)}</style></head><body>
<header><h1>Transcription check — fix the text to match the audio</h1><div class="bar"><i id="prog"></i></div><span class="small" id="count"></span><button class="play" onclick="exportJSON()">⬇ Export</button></header>
<div class="wrap" id="app"></div><audio id="au"></audio><script>
const DATA=__DATA__;const KEY='armcc_asr_v1';let R=JSON.parse(localStorage.getItem(KEY)||'{}');
let i=DATA.findIndex(x=>!(R[x.id]&&R[x.id].done));if(i<0)i=0;const au=document.getElementById('au');
function play(it){if(!it.src){alert('no audio url');return;}au.src=it.src;const s=Math.max(0,(it.start||0)-0.15),e=(it.end||s+5)+0.4;au.currentTime=s;au.play();const st=()=>{if(au.currentTime>=e){au.pause();au.removeEventListener('timeupdate',st);}};au.addEventListener('timeupdate',st);}
function draw(){const done=DATA.filter(x=>R[x.id]&&R[x.id].done).length;document.getElementById('prog').style.width=(100*done/DATA.length)+'%';document.getElementById('count').textContent=done+'/'+DATA.length;
const it=DATA[i],r=R[it.id]||{};const ref=(r.reference!==undefined)?r.reference:it.text;
document.getElementById('app').innerHTML=`<div class="card"><div class="small">clip ${i+1}/${DATA.length} · @${it.handle||''}</div>
<div style="margin:10px 0"><button class="play" id="pl">▶ play clip</button> <span class="small">(press P)</span></div>
<div class="small">ElevenLabs heard:</div><div class="ro">${it.text}</div>
<div class="small" style="margin-top:12px">Correct transcript (edit to EXACTLY what is said — punctuation optional):</div>
<textarea id="ta">${ref.replace(/</g,'&lt;')}</textarea>
<div style="display:flex;gap:10px;margin-top:10px">
<button class="perfect" id="same">= already perfect (no changes)</button></div>
<div class="small" style="margin-top:8px"><a href="${it.url}" target="_blank">↗ open TikTok</a></div>
<div class="nav"><button onclick="go(-1)">← Prev</button><button class="primary" id="next">Save & Next →</button></div></div>`;
const ta=document.getElementById('ta');
ta.oninput=()=>{R[it.id]={...(R[it.id]||{}),reference:ta.value};localStorage.setItem(KEY,JSON.stringify(R));};
document.getElementById('pl').onclick=()=>play(it);
document.getElementById('same').onclick=()=>{R[it.id]={reference:it.text,done:true,unchanged:true};localStorage.setItem(KEY,JSON.stringify(R));go(1);};
document.getElementById('next').onclick=()=>{R[it.id]={reference:ta.value,done:true,unchanged:ta.value.trim()===it.text.trim()};localStorage.setItem(KEY,JSON.stringify(R));go(1);};}
function go(d){au.pause();i=Math.max(0,Math.min(DATA.length-1,i+d));draw();scrollTo(0,0);}
document.addEventListener('keydown',e=>{if(e.target.tagName==='TEXTAREA'){if(e.key==='Escape')e.target.blur();return;}if(e.key==='p'||e.key==='P')play(DATA[i]);if(e.key==='ArrowRight')go(1);if(e.key==='ArrowLeft')go(-1);});
function exportJSON(){const out={labeled_at:new Date().toISOString(),refs:R};const b=new Blob([JSON.stringify(out,null,2)],{type:'application/json'});const a=document.createElement('a');a.href=URL.createObjectURL(b);a.download='asr_refs.json';a.click();}
draw();</script></body></html>"""
(HERE/"eval"/"asr.html").write_text(HTML.replace("__DATA__",DATA))
print(f"wrote eval/asr.html ({len(pub)} clips)")
