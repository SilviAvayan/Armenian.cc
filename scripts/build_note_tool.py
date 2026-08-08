#!/usr/bin/env python3
"""Emit eval/notes.html — judge whether each model NOTE (its grammatical/
etymological claim) is TRUE. Claim type is hidden to avoid biasing."""
import json, pathlib
HERE=pathlib.Path(__file__).resolve().parent.parent
items=json.loads((HERE/"out"/"note_items.json").read_text())
pub=[{k:s[k] for k in ("id","handle","url","src","seg_text","seg_translation",
      "word","gloss","note","start","end") if k in s} for s in items]
DATA=json.dumps(pub,ensure_ascii=False)
HTML=r"""<!DOCTYPE html><html lang="ru"><head><meta charset="utf-8">
<title>armenian.cc — note (grammar) annotation</title><style>
:root{--bg:#0f1115;--card:#1a1d24;--fg:#e8eaed;--mut:#9aa0aa;--acc:#58a6ff;--line:#2b2f38;--ok:#3fb950;--warn:#d29922;--bad:#f85149}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--fg);font:16px/1.5 -apple-system,Segoe UI,sans-serif}
header{position:sticky;top:0;background:var(--bg);border-bottom:1px solid var(--line);padding:12px 20px;display:flex;gap:16px;align-items:center}
h1{font-size:15px;margin:0}.bar{flex:1;height:8px;background:var(--card);border-radius:6px;overflow:hidden}.bar>i{display:block;height:100%;background:var(--acc);width:0}
.wrap{max-width:780px;margin:0 auto;padding:20px}.card{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:20px}
.play{padding:9px 15px;border-radius:8px;border:1px solid var(--acc);background:#12233b;color:var(--acc);cursor:pointer}
.am{font-size:26px;font-weight:600;margin:6px 0}.gloss{font-size:18px;color:var(--acc)}
.ctx{color:var(--mut);font-size:15px;padding:10px;background:#0d0f13;border-radius:8px;border:1px solid var(--line);margin:8px 0}
.ctx b{color:var(--fg);background:#33415e;padding:1px 5px;border-radius:4px}
.note{font-size:17px;color:var(--warn);padding:12px;background:#1e1a10;border:1px solid var(--warn);border-radius:8px;margin:10px 0}
.q{font-size:13px;color:var(--mut);margin-top:4px}
.btns{display:flex;gap:8px;margin-top:10px;flex-wrap:wrap}
button.opt{flex:1;min-width:120px;padding:12px;border-radius:9px;border:1px solid var(--line);background:#20242d;color:var(--fg);cursor:pointer;font-size:15px}
.opt.sel{outline:2px solid #fff}.ok{background:#12331c;border-color:var(--ok)}.part{background:#3a3212;border-color:var(--warn)}.bad{background:#3a1615;border-color:var(--bad)}.sk{background:#20242d}
textarea{width:100%;min-height:56px;margin-top:10px;padding:10px;border-radius:8px;border:1px solid var(--line);background:#0d0f13;color:var(--fg);font-size:15px}
.nav{display:flex;gap:10px;justify-content:space-between;margin-top:16px}.nav button{padding:12px 20px;border-radius:9px;border:1px solid var(--line);background:#20242d;color:var(--fg);cursor:pointer}
.primary{background:var(--acc)!important;color:#000!important;font-weight:600}.small{font-size:12px;color:var(--mut)}a{color:var(--acc)}</style></head><body>
<header><h1>Note annotation — is the grammatical claim TRUE?</h1><div class="bar"><i id="prog"></i></div><span class="small" id="count"></span><button class="play" onclick="exportJSON()">⬇ Export</button></header>
<div class="wrap" id="app"></div><audio id="au"></audio><script>
const DATA=__DATA__;const KEY='armcc_notes_v1';let R=JSON.parse(localStorage.getItem(KEY)||'{}');
let i=DATA.findIndex(x=>!(R[x.id]&&R[x.id].verdict));if(i<0)i=0;const au=document.getElementById('au');
function play(it){if(!it.src)return;au.src=it.src;const s=Math.max(0,(it.start||0)-0.15),e=(it.end||s+6)+0.4;au.currentTime=s;au.play();const st=()=>{if(au.currentTime>=e){au.pause();au.removeEventListener('timeupdate',st);}};au.addEventListener('timeupdate',st);}
function hl(seg,w){if(!w)return seg;const b=w.replace(/[։՝՜՞,.]+$/,'');return seg.replace(b,m=>'<b>'+m+'</b>');}
function setV(id,v){R[id]={...(R[id]||{}),verdict:v};localStorage.setItem(KEY,JSON.stringify(R));draw();}
function draw(){const done=DATA.filter(x=>R[x.id]&&R[x.id].verdict).length;document.getElementById('prog').style.width=(100*done/DATA.length)+'%';document.getElementById('count').textContent=done+'/'+DATA.length;
const it=DATA[i],r=R[it.id]||{};
document.getElementById('app').innerHTML=`<div class="card"><div class="small">note ${i+1}/${DATA.length} · @${it.handle||''} · <button class="play" id="pl">▶ audio</button></div>
<div class="am">${it.word}</div><div class="gloss">gloss: “${it.gloss||''}”</div>
<div class="ctx">${hl(it.seg_text,it.word)}<br><span class="small">${it.seg_translation||''}</span></div>
<div class="note">📝 model note: ${it.note}</div>
<div class="q">Is this note (the grammatical / etymological / register claim) correct?</div>
<div class="btns">
<button class="opt ok ${r.verdict==='correct'?'sel':''}" onclick="setV('${it.id}','correct')">✓ Correct (1)</button>
<button class="opt part ${r.verdict==='partial'?'sel':''}" onclick="setV('${it.id}','partial')">◐ Partly (2)</button>
<button class="opt bad ${r.verdict==='wrong'?'sel':''}" onclick="setV('${it.id}','wrong')">✗ Wrong (3)</button>
<button class="opt sk ${r.verdict==='unsure'?'sel':''}" onclick="setV('${it.id}','unsure')">? Unsure (4)</button></div>
<textarea id="fix" placeholder="what's wrong / correct claim (if partly/wrong)">${(r.correction||'').replace(/</g,'&lt;')}</textarea>
<div class="small" style="margin-top:6px"><a href="${it.url}" target="_blank">↗ open TikTok</a></div>
<div class="nav"><button onclick="go(-1)">← Prev</button><button class="primary" onclick="go(1)">Next →</button></div></div>`;
document.getElementById('pl').onclick=()=>play(it);
document.getElementById('fix').oninput=e=>{R[it.id]={...(R[it.id]||{}),correction:e.target.value};localStorage.setItem(KEY,JSON.stringify(R));};}
function go(d){au.pause();i=Math.max(0,Math.min(DATA.length-1,i+d));draw();scrollTo(0,0);}
document.addEventListener('keydown',e=>{if(e.target.tagName==='TEXTAREA')return;const it=DATA[i];if(e.key==='1')setV(it.id,'correct');if(e.key==='2')setV(it.id,'partial');if(e.key==='3')setV(it.id,'wrong');if(e.key==='4')setV(it.id,'unsure');if(e.key==='p'||e.key==='P')play(it);if(e.key==='ArrowRight')go(1);if(e.key==='ArrowLeft')go(-1);});
function exportJSON(){const out={labeled_at:new Date().toISOString(),labels:R};const b=new Blob([JSON.stringify(out,null,2)],{type:'application/json'});const a=document.createElement('a');a.href=URL.createObjectURL(b);a.download='note_labels.json';a.click();}
draw();</script></body></html>"""
(HERE/"eval"/"notes.html").write_text(HTML.replace("__DATA__",DATA))
print(f"wrote eval/notes.html ({len(pub)} notes)")
