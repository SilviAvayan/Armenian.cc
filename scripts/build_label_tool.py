#!/usr/bin/env python3
"""Emit a single self-contained eval/label.html with the gold items inlined.
Blind: labeler never sees logprob or stratum. Audio plays the real clip at the
word's timestamp so transcription can be verified by ear."""
import json, pathlib
HERE = pathlib.Path(__file__).resolve().parent.parent
gold = json.loads((HERE/"out"/"gold_items.json").read_text())

# strip fields that could bias the labeler
def clean_word(w):
    return {k: w[k] for k in ("id","video_id","handle","url","src","seg_text",
            "seg_explanation","word","gloss","note","start","end") if k in w}
def clean_phrase(p):
    return {k: p[k] for k in ("id","video_id","handle","url","src","seg_text",
            "explanation","start","end") if k in p}
payload = {"words":[clean_word(w) for w in gold["words"]],
           "phrases":[clean_phrase(p) for p in gold["phrases"]]}
DATA = json.dumps(payload, ensure_ascii=False)

HTML = r"""<!DOCTYPE html>
<html lang="ru"><head><meta charset="utf-8">
<title>armenian.cc — gold labeling</title>
<style>
 :root{--bg:#0f1115;--card:#1a1d24;--fg:#e8eaed;--mut:#9aa0aa;--ok:#3fb950;
   --warn:#d29922;--bad:#f85149;--acc:#58a6ff;--line:#2b2f38}
 *{box-sizing:border-box} body{margin:0;background:var(--bg);color:var(--fg);
   font:16px/1.5 -apple-system,Segoe UI,Roboto,sans-serif}
 header{position:sticky;top:0;background:var(--bg);border-bottom:1px solid var(--line);
   padding:12px 20px;display:flex;gap:16px;align-items:center;z-index:5}
 header h1{font-size:15px;margin:0;font-weight:600}
 .bar{flex:1;height:8px;background:var(--card);border-radius:6px;overflow:hidden}
 .bar>i{display:block;height:100%;background:var(--acc);width:0}
 .wrap{max-width:760px;margin:0 auto;padding:20px}
 .card{background:var(--card);border:1px solid var(--line);border-radius:12px;
   padding:20px;margin:14px 0}
 .tag{font-size:11px;color:var(--mut);text-transform:uppercase;letter-spacing:.08em}
 .am{font-size:30px;font-weight:600;margin:6px 0}
 .ctx{color:var(--mut);font-size:15px;margin:8px 0;padding:10px;background:#0d0f13;
   border-radius:8px;border:1px solid var(--line)}
 .ctx b{color:var(--fg);background:#33415e;padding:1px 5px;border-radius:4px}
 .gloss{font-size:22px;color:var(--acc);margin:10px 0}
 .note{font-size:13px;color:var(--warn);margin:6px 0}
 .btns{display:flex;gap:8px;flex-wrap:wrap;margin-top:12px}
 button.opt{flex:1;min-width:110px;padding:12px;border-radius:9px;border:1px solid var(--line);
   background:#20242d;color:var(--fg);cursor:pointer;font-size:15px}
 button.opt:hover{border-color:var(--acc)}
 button.opt.sel{outline:2px solid #fff}
 .ok{background:#12331c;border-color:var(--ok)} .acc{background:#3a3212;border-color:var(--warn)}
 .bad{background:#3a1615;border-color:var(--bad)} .skip{background:#20242d}
 .row{display:flex;gap:10px;align-items:center;margin-top:10px;flex-wrap:wrap}
 input[type=text]{flex:1;min-width:200px;padding:10px;border-radius:8px;border:1px solid var(--line);
   background:#0d0f13;color:var(--fg);font-size:15px}
 label.chk{font-size:14px;color:var(--mut);display:flex;gap:6px;align-items:center}
 .audio{display:flex;gap:8px;align-items:center;margin:8px 0}
 .play{padding:8px 14px;border-radius:8px;border:1px solid var(--acc);background:#12233b;
   color:var(--acc);cursor:pointer}
 .nav{display:flex;gap:10px;justify-content:space-between;margin-top:16px}
 .nav button{padding:12px 20px;border-radius:9px;border:1px solid var(--line);
   background:#20242d;color:var(--fg);cursor:pointer;font-size:15px}
 .primary{background:var(--acc)!important;color:#000!important;font-weight:600}
 a{color:var(--acc)} .small{font-size:12px;color:var(--mut)}
 .done{text-align:center;padding:40px}
 .scale{display:flex;gap:6px} .scale button{flex:1}
</style></head><body>
<header>
 <h1>armenian.cc gold labeling</h1>
 <div class="bar"><i id="prog"></i></div>
 <span class="small" id="count"></span>
 <button class="play" onclick="exportJSON()">⬇ Export</button>
</header>
<div class="wrap" id="app"></div>
<audio id="au"></audio>
<script>
const DATA = __DATA__;
const ITEMS = [...DATA.words.map(w=>({...w,kind:'word'})),
               ...DATA.phrases.map(p=>({...p,kind:'phrase'}))];
const KEY='armcc_gold_v1';
let R = JSON.parse(localStorage.getItem(KEY)||'{}');
let i = ITEMS.findIndex(it=>!R[it.id]); if(i<0)i=0;
const au=document.getElementById('au');

function save(){localStorage.setItem(KEY,JSON.stringify(R));draw();}
function highlight(seg,word){
  if(!word) return seg;
  const w=word.replace(/[։՝՜՞,.]+$/,'');
  return seg.replace(word,'<b>'+word+'</b>').replace(w,m=>m.includes('<b>')?m:'<b>'+m+'</b>');
}
function playClip(it){
  if(!it.src){alert('no audio');return;}
  au.src=it.src;
  const s=Math.max(0,(it.start||0)-(it.kind==='word'?1.8:0.2));
  const e=(it.end||s+3)+0.4;
  au.currentTime=s; au.play();
  const stop=()=>{if(au.currentTime>=e){au.pause();au.removeEventListener('timeupdate',stop);}};
  au.addEventListener('timeupdate',stop);
}
function setW(id,v){R[id]={...(R[id]||{}),verdict:v};save();}
function setField(id,k,v){R[id]={...(R[id]||{}),[k]:v};localStorage.setItem(KEY,JSON.stringify(R));}

function draw(){
  const done=ITEMS.filter(it=>R[it.id]&&R[it.id].verdict).length;
  document.getElementById('prog').style.width=(100*done/ITEMS.length)+'%';
  document.getElementById('count').textContent=done+'/'+ITEMS.length;
  const it=ITEMS[i]; const r=R[it.id]||{}; const app=document.getElementById('app');
  if(it.kind==='word'){
    app.innerHTML=`
    <div class="card">
      <div class="tag">word ${i+1} / ${ITEMS.length} &nbsp;·&nbsp; @${it.handle||''}</div>
      <div class="am">${it.word}</div>
      <div class="audio"><button class="play" id="pl">▶ play clip</button>
        <span class="small">listen: does the audio really say this word?</span></div>
      <div class="ctx">${highlight(it.seg_text,it.word)}</div>
      <div class="small">full-phrase translation: ${it.seg_explanation||'—'}</div>
      <div class="gloss">model gloss → “${it.gloss}”</div>
      ${it.note?`<div class="note">ℹ model note: ${it.note}</div>`:''}
      <div class="btns">
        <button class="opt ok  ${r.verdict==='correct'?'sel':''}" onclick="setW('${it.id}','correct')">✓ Correct</button>
        <button class="opt acc ${r.verdict==='acceptable'?'sel':''}" onclick="setW('${it.id}','acceptable')">≈ Acceptable</button>
        <button class="opt bad ${r.verdict==='wrong'?'sel':''}" onclick="setW('${it.id}','wrong')">✗ Wrong</button>
        <button class="opt skip ${r.verdict==='unsure'?'sel':''}" onclick="setW('${it.id}','unsure')">? Unsure</button>
      </div>
      <div class="row">
        <label class="chk"><input type="checkbox" id="mt" ${r.mistranscribed?'checked':''}
          onchange="setField('${it.id}','mistranscribed',this.checked)"> ⚠ Armenian word is mis-transcribed (audio says something else)</label>
      </div>
      <div class="row">
        <input type="text" id="corr" placeholder="correct gloss (if wrong/acceptable)"
          value="${(r.correction||'').replace(/"/g,'&quot;')}"
          oninput="setField('${it.id}','correction',this.value)">
      </div>
      <div class="row"><a href="${it.url}" target="_blank" class="small">↗ open TikTok</a></div>
    </div>`;
    document.getElementById('pl').onclick=()=>playClip(it);
  } else {
    app.innerHTML=`
    <div class="card">
      <div class="tag">phrase ${i+1} / ${ITEMS.length} &nbsp;·&nbsp; @${it.handle||''}</div>
      <div class="audio"><button class="play" id="pl">▶ play clip</button>
        <span class="small">rate the RU translation of the whole phrase</span></div>
      <div class="am" style="font-size:22px">${it.seg_text}</div>
      <div class="gloss">translation → “${it.explanation}”</div>
      <div class="btns">
        <button class="opt ok  ${r.verdict==='faithful'?'sel':''}" onclick="setW('${it.id}','faithful')">✓ Faithful</button>
        <button class="opt acc ${r.verdict==='minor'?'sel':''}" onclick="setW('${it.id}','minor')">≈ Minor issue</button>
        <button class="opt bad ${r.verdict==='major'?'sel':''}" onclick="setW('${it.id}','major')">✗ Major error</button>
        <button class="opt skip ${r.verdict==='unsure'?'sel':''}" onclick="setW('${it.id}','unsure')">? Unsure</button>
      </div>
      <div class="row">
        <input type="text" placeholder="what's wrong / better translation (optional)"
          value="${(r.correction||'').replace(/"/g,'&quot;')}"
          oninput="setField('${it.id}','correction',this.value)"></div>
      <div class="row"><a href="${it.url}" target="_blank" class="small">↗ open TikTok</a></div>
    </div>`;
    document.getElementById('pl').onclick=()=>playClip(it);
  }
  app.innerHTML+=`<div class="nav">
     <button onclick="go(-1)">← Prev</button>
     <button class="primary" onclick="go(1)">Next →</button></div>
     <p class="small">Progress auto-saves in this browser. Click Export when done and send me the file.</p>`;
}
function go(d){au.pause();i=Math.max(0,Math.min(ITEMS.length-1,i+d));draw();window.scrollTo(0,0);}
document.addEventListener('keydown',e=>{
  if(e.target.tagName==='INPUT')return;
  const it=ITEMS[i];
  if(e.key==='1')setW(it.id, it.kind==='word'?'correct':'faithful');
  if(e.key==='2')setW(it.id, it.kind==='word'?'acceptable':'minor');
  if(e.key==='3')setW(it.id, it.kind==='word'?'wrong':'major');
  if(e.key==='4')setW(it.id,'unsure');
  if(e.key==='p'||e.key==='P')playClip(it);
  if(e.key==='ArrowRight')go(1); if(e.key==='ArrowLeft')go(-1);
});
function exportJSON(){
  const out={labeled_at:new Date().toISOString(),labels:R};
  const blob=new Blob([JSON.stringify(out,null,2)],{type:'application/json'});
  const a=document.createElement('a');a.href=URL.createObjectURL(blob);
  a.download='gold_labels.json';a.click();
}
draw();
</script></body></html>"""
html = HTML.replace("__DATA__", DATA)
(HERE/"eval"/"label.html").write_text(html)
print(f"wrote eval/label.html  ({len(html)} bytes, {len(payload['words'])} words + {len(payload['phrases'])} phrases)")
