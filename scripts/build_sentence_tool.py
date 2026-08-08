#!/usr/bin/env python3
"""Emit eval/sentences.html — sentence-level MT evaluation. For each sentence:
rate the model's Russian translation (faithful/minor/major) AND edit a reference
box (prefilled with the model output) into a fully-correct translation. The
reference feeds chrF++; the rating is human direct assessment. Separate
localStorage key so it never collides with the word-gloss tool."""
import json, pathlib
HERE=pathlib.Path(__file__).resolve().parent.parent
gold=json.loads((HERE/"out"/"gold_items.json").read_text())
pub=[{k:p[k] for k in ("id","handle","url","src","seg_text","explanation","start","end")}
     for p in gold["phrases"]]
DATA=json.dumps(pub,ensure_ascii=False)
HTML=r"""<!DOCTYPE html><html lang="ru"><head><meta charset="utf-8">
<title>armenian.cc — sentence translation eval</title><style>
:root{--bg:#0f1115;--card:#1a1d24;--fg:#e8eaed;--mut:#9aa0aa;--acc:#58a6ff;--line:#2b2f38;--ok:#3fb950;--warn:#d29922;--bad:#f85149}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--fg);font:16px/1.5 -apple-system,Segoe UI,sans-serif}
header{position:sticky;top:0;background:var(--bg);border-bottom:1px solid var(--line);padding:12px 20px;display:flex;gap:16px;align-items:center}
h1{font-size:15px;margin:0}.bar{flex:1;height:8px;background:var(--card);border-radius:6px;overflow:hidden}.bar>i{display:block;height:100%;background:var(--acc);width:0}
.wrap{max-width:780px;margin:0 auto;padding:20px}.card{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:20px}
.play{padding:10px 16px;border-radius:8px;border:1px solid var(--acc);background:#12233b;color:var(--acc);cursor:pointer;font-size:15px}
.am{font-size:21px;margin:10px 0}.mt{font-size:17px;color:var(--mut);padding:10px;background:#0d0f13;border-radius:8px;border:1px solid var(--line)}
textarea{width:100%;min-height:80px;margin-top:6px;padding:12px;border-radius:8px;border:1px solid var(--line);background:#0d0f13;color:var(--fg);font-size:18px;line-height:1.55}
.small{font-size:12px;color:var(--mut)}.btns{display:flex;gap:8px;margin-top:12px}
button.opt{flex:1;padding:12px;border-radius:9px;border:1px solid var(--line);background:#20242d;color:var(--fg);cursor:pointer;font-size:15px}
.opt.sel{outline:2px solid #fff}.ok{background:#12331c;border-color:var(--ok)}.acc{background:#3a3212;border-color:var(--warn)}.bad{background:#3a1615;border-color:var(--bad)}
.nav{display:flex;gap:10px;justify-content:space-between;margin-top:16px}.nav button{padding:12px 20px;border-radius:9px;border:1px solid var(--line);background:#20242d;color:var(--fg);cursor:pointer;font-size:15px}
.primary{background:var(--acc)!important;color:#000!important;font-weight:600}a{color:var(--acc)}</style></head><body>
<header><h1>Sentence translation eval — rate + give a correct reference</h1><div class="bar"><i id="prog"></i></div><span class="small" id="count"></span><button class="play" onclick="exportJSON()">⬇ Export</button></header>
<div class="wrap" id="app"></div><audio id="au"></audio><script>
const DATA=__DATA__;const KEY='armcc_sent_v1';let R=JSON.parse(localStorage.getItem(KEY)||'{}');
let i=DATA.findIndex(x=>!(R[x.id]&&R[x.id].rating));if(i<0)i=0;const au=document.getElementById('au');
function play(it){if(!it.src)return;au.src=it.src;const s=Math.max(0,(it.start||0)-0.15),e=(it.end||s+6)+0.4;au.currentTime=s;au.play();const st=()=>{if(au.currentTime>=e){au.pause();au.removeEventListener('timeupdate',st);}};au.addEventListener('timeupdate',st);}
function setR(id,k,v){R[id]={...(R[id]||{}),[k]:v};localStorage.setItem(KEY,JSON.stringify(R));draw();}
function draw(){const done=DATA.filter(x=>R[x.id]&&R[x.id].rating).length;document.getElementById('prog').style.width=(100*done/DATA.length)+'%';document.getElementById('count').textContent=done+'/'+DATA.length;
const it=DATA[i],r=R[it.id]||{};const ref=(r.reference!==undefined)?r.reference:it.explanation;
document.getElementById('app').innerHTML=`<div class="card"><div class="small">sentence ${i+1}/${DATA.length} · @${it.handle||''}</div>
<div style="margin:8px 0"><button class="play" id="pl">▶ play clip</button> <span class="small">(P)</span></div>
<div class="am">${it.seg_text}</div>
<div class="small">model translation:</div><div class="mt">${it.explanation}</div>
<div class="btns">
<button class="opt ok ${r.rating==='faithful'?'sel':''}" onclick="setR('${it.id}','rating','faithful')">✓ Faithful (1)</button>
<button class="opt acc ${r.rating==='minor'?'sel':''}" onclick="setR('${it.id}','rating','minor')">≈ Minor (2)</button>
<button class="opt bad ${r.rating==='major'?'sel':''}" onclick="setR('${it.id}','rating','major')">✗ Major (3)</button></div>
<div class="small" style="margin-top:12px">Correct Russian translation (edit to a faithful reference — used for chrF++):</div>
<textarea id="ta">${ref.replace(/</g,'&lt;')}</textarea>
<div class="small" style="margin-top:8px"><a href="${it.url}" target="_blank">↗ open TikTok</a></div>
<div class="nav"><button onclick="go(-1)">← Prev</button><button class="primary" id="next">Save & Next →</button></div></div>`;
const ta=document.getElementById('ta');
ta.oninput=()=>{R[it.id]={...(R[it.id]||{}),reference:ta.value};localStorage.setItem(KEY,JSON.stringify(R));};
document.getElementById('pl').onclick=()=>play(it);
document.getElementById('next').onclick=()=>{R[it.id]={...(R[it.id]||{}),reference:ta.value};if(!R[it.id].rating)R[it.id].rating='faithful';localStorage.setItem(KEY,JSON.stringify(R));go(1);};}
function go(d){au.pause();i=Math.max(0,Math.min(DATA.length-1,i+d));draw();scrollTo(0,0);}
document.addEventListener('keydown',e=>{if(e.target.tagName==='TEXTAREA'){if(e.key==='Escape')e.target.blur();return;}const it=DATA[i];if(e.key==='1')setR(it.id,'rating','faithful');if(e.key==='2')setR(it.id,'rating','minor');if(e.key==='3')setR(it.id,'rating','major');if(e.key==='p'||e.key==='P')play(it);if(e.key==='ArrowRight')go(1);if(e.key==='ArrowLeft')go(-1);});
function exportJSON(){const out={labeled_at:new Date().toISOString(),sentences:R};const b=new Blob([JSON.stringify(out,null,2)],{type:'application/json'});const a=document.createElement('a');a.href=URL.createObjectURL(b);a.download='sentence_refs.json';a.click();}
draw();</script></body></html>"""
(HERE/"eval"/"sentences.html").write_text(HTML.replace("__DATA__",DATA))
print(f"wrote eval/sentences.html ({len(pub)} sentences)")
