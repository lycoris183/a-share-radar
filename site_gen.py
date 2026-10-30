"""生成静态网站：site/index.html（最新交易日）+ site/d/YYYYMMDD.html（最近10个交易日）
数据来源：data/history/*.json（daily.py 生成，含 report 字段）
用法：python site_gen.py
特性：浅色/深色主题切换、页面内手动刷新、自动检测新数据、仅保留最近10个交易日
"""
import glob
import json
import os
import time

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
HIST = os.path.join(DATA, "history")
OUT = os.path.join(HERE, "site")
DAILY = os.path.join(OUT, "d")
KEEP = 10            # 只保留最近 10 个交易日

KEYS = [("pt02GN2238", "人形机器人"), ("pt02GN2442", "物理AI"),
        ("pt01801750", "计算机"), ("pt02GN2116", "半导体"),
        ("pt01801960", "石油石化"), ("pt01801780", "银行")]
FUNDS = [("010365", "港股银行"), ("023145", "油气资源"), ("020973", "机器人"),
         ("001630", "计算机"), ("007301", "半导体")]
ACT_CLS = {"加仓": "a-add", "持有": "a-hold", "观察": "a-watch",
           "减仓": "a-cut", "清仓": "a-out"}

CSS = """
*{box-sizing:border-box;-webkit-text-size-adjust:100%}
:root{
  --bg:#f2f4f7;--card:#fff;--fg:#1c1e21;--muted:#8a8f98;--line:#eef1f3;
  --thead:#f7f9fa;--chip:#f4f6f8;--btn:#fff;--btlborder:#e1e5ea;
  --up:#c0392b;--down:#1e7e34;--flat:#8a8f98;
  --a-add:#c0392b;--a-hold:#1e7e34;--a-watch:#8a6d3b;--a-cut:#2c3e50;--a-out:#111;
  --note:#fff8e1;--noteline:#f0ad4e;--notefg:#7a5c00;
}
html[data-theme=dark]{
  --bg:#0f1216;--card:#171b21;--fg:#e7eaee;--muted:#8b94a2;--line:#242a33;
  --thead:#1d232b;--chip:#212831;--btn:#1d232b;--btlborder:#2b333d;
  --up:#ff6b6b;--down:#4ade80;--flat:#8b94a2;
  --a-add:#ff6b6b;--a-hold:#4ade80;--a-watch:#e0b24d;--a-cut:#9aa6b8;--a-out:#cdd5e0;
  --note:#2a2416;--noteline:#a3792a;--notefg:#e3c274;
}
body{margin:0;background:var(--bg);color:var(--fg);font-size:15px;line-height:1.5;
font-family:-apple-system,BlinkMacSystemFont,'Segoe UI','Microsoft YaHei',sans-serif;
transition:background .18s ease,color .18s ease}
.wrap{max-width:880px;margin:0 auto;padding:0 12px 12px}
.bar{position:sticky;top:0;z-index:5;background:var(--bg);display:flex;align-items:center;
gap:8px;padding:10px 0 8px;transition:background .18s ease}
.bar h1{font-size:17px;margin:0;flex:1}
.btn{appearance:none;border:1px solid var(--btlborder);background:var(--btn);color:var(--fg);
border-radius:8px;padding:6px 10px;font-size:14px;line-height:1;cursor:pointer;
display:inline-flex;align-items:center;gap:4px}
.btn:active{transform:scale(.96)}
.btn.spin svg{animation:sp .8s linear infinite}
@keyframes sp{to{transform:rotate(360deg)}}
.card{background:var(--card);border-radius:10px;padding:14px;margin:12px 0;
box-shadow:0 1px 3px rgba(0,0,0,.07);transition:background .18s ease}
h2{font-size:15px;margin:0 0 10px;color:var(--fg)}
.sub{font-size:12px;color:var(--muted)}
.chips{display:flex;flex-wrap:wrap;gap:6px;margin-top:10px}
.chip{background:var(--chip);border-radius:6px;padding:5px 9px;font-size:12.5px;
white-space:nowrap}
.scroll{overflow-x:auto;-webkit-overflow-scrolling:touch;margin:0 -4px}
table{border-collapse:collapse;width:100%;min-width:520px}
th,td{padding:7px 8px;border-bottom:1px solid var(--line);font-size:13px;
white-space:nowrap;text-align:right}
th{background:var(--thead);color:var(--muted);font-size:12px;font-weight:600;
border-bottom:2px solid var(--line);position:sticky;top:0}
th:first-child,td:first-child{text-align:left;position:sticky;left:0;
background:var(--card);z-index:1}
th:first-child{background:var(--thead)}
td.adv,th.adv{text-align:left;white-space:normal;line-height:1.45}
.up{color:var(--up)}.down{color:var(--down)}.flat{color:var(--flat)}
.act{font-weight:700}
.a-add{color:var(--a-add)}.a-hold{color:var(--a-hold)}.a-watch{color:var(--a-watch)}
.a-cut{color:var(--a-cut)}.a-out{color:var(--a-out)}
.note{background:var(--note);border-left:4px solid var(--noteline);padding:8px 10px;
border-radius:4px;font-size:12.5px;color:var(--notefg);margin-bottom:10px}
.tip{font-size:11.5px;color:var(--muted);margin-top:6px}
.foot{font-size:11.5px;color:var(--muted);line-height:1.7}
.toast{position:fixed;left:50%;bottom:26px;transform:translate(-50%,20px);background:#000c;
color:#fff;padding:9px 14px;border-radius:20px;font-size:13px;opacity:0;
transition:.25s;pointer-events:none;z-index:9}
.toast.on{opacity:1;transform:translate(-50%,0)}
@media (max-width:600px){
  .wrap{padding:0 8px 8px}
  .card{padding:10px;border-radius:8px;margin:9px 0}
  .bar h1{font-size:16px}
  th,td{padding:6px 6px;font-size:12px}
  table{min-width:460px}
}
"""

JS = """
(function(){
  var root=document.documentElement;
  var saved=null;
  try{saved=localStorage.getItem('radar-theme');}catch(e){}
  var mq=window.matchMedia('(prefers-color-scheme: dark)');
  root.setAttribute('data-theme', saved || (mq.matches?'dark':'light'));
  var tbtn=document.getElementById('tbtn'), rbtn=document.getElementById('rbtn');
  var ico=document.getElementById('tico');
  function paint(){
    var dark=root.getAttribute('data-theme')==='dark';
    ico.textContent=dark?'☀️':'🌙';
    tbtn.title=dark?'切换为浅色（太阳）':'切换为深色（月亮）';
    var mt=document.querySelector('meta[name=theme-color]');
    if(mt) mt.setAttribute('content', dark?'#0f1216':'#f2f4f7');
  }
  paint();
  tbtn.onclick=function(){
    var t=root.getAttribute('data-theme')==='dark'?'light':'dark';
    root.setAttribute('data-theme',t);
    try{localStorage.setItem('radar-theme',t);}catch(e){}
    paint();
  };
  if(!saved && mq.addEventListener) mq.addEventListener('change',function(e){
    root.setAttribute('data-theme', e.matches?'dark':'light'); paint();
  });
  var toast=document.getElementById('toast');
  function say(msg){ toast.textContent=msg; toast.classList.add('on');
    setTimeout(function(){toast.classList.remove('on');},2200); }
  function curDate(){
    var m=document.body.innerHTML.match(/最新交易日\\s*(\\d{4}-\\d{2}-\\d{2})/);
    return m?m[1]:'';
  }
  var busy=false;
  function check(manual){
    if(busy) return; busy=true; rbtn.classList.add('spin');
    fetch(location.pathname+'?t='+Date.now(),{cache:'no-store'})
      .then(function(r){return r.text();})
      .then(function(html){
        var m=html.match(/最新交易日\\s*(\\d{4}-\\d{2}-\\d{2})/);
        var nd=m?m[1]:'';
        if(nd && nd!==curDate()){ say('发现新数据 '+nd+'，正在刷新…');
          setTimeout(function(){location.reload();},600); return; }
        if(manual) say('已是最新数据（'+ (nd||'—') +'）');
      })
      .catch(function(){ if(manual) say('刷新失败，请检查网络'); })
      .then(function(){ rbtn.classList.remove('spin'); busy=false; });
  }
  rbtn.onclick=function(){ check(true); };
  setInterval(function(){ check(false); }, 5*60*1000);
})();
"""


def cls(v):
    return "up" if v > 0 else ("down" if v < 0 else "flat")


def pct(v, dec=2):
    return f"{v:+.{dec}f}%"


def load_days():
    import datetime
    out = []
    for p in glob.glob(os.path.join(HIST, "*.json")):
        if p.endswith("_am.json"):
            continue
        try:
            with open(p, encoding="utf-8") as f:
                d = json.load(f)
            if not (d.get("date") and d.get("report")):
                continue
            try:
                wd = datetime.date.fromisoformat(d["date"]).isoweekday()
            except Exception:
                wd = 1
            if wd >= 6:          # 周末文件一律不算交易日（历史误产物兜底）
                continue
            out.append(d)
        except Exception:
            pass
    out.sort(key=lambda d: d["date"])
    seen, res = set(), []
    for d in out:
        fp = d.get("_fp") or d["date"]
        if fp in seen:
            continue
        seen.add(fp)
        res.append(d)
    return res[::-1]


def prune(days):
    """只保留最近 KEEP 个交易日：删掉更早的 json 快照与对应日页面"""
    keep_dates = {d["date"] for d in days[:KEEP]}
    removed = 0
    for p in glob.glob(os.path.join(HIST, "*.json")):
        try:
            with open(p, encoding="utf-8") as f:
                dt = json.load(f).get("date")
        except Exception:
            dt = None
        if dt and dt not in keep_dates:
            os.remove(p)
            removed += 1
    if os.path.isdir(DAILY):
        keep_file = {d["date"].replace("-", "") + ".html" for d in days[:KEEP]}
        for p in glob.glob(os.path.join(DAILY, "*.html")):
            if os.path.basename(p) not in keep_file:
                os.remove(p)
    return removed


def page(title, body, generated, refresh=True):
    btn = ""
    if refresh:
        btn = ('<button class="btn" id="rbtn" title="立即检查是否有新数据">'
               '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" '
               'stroke="currentColor" stroke-width="2.4" stroke-linecap="round">'
               '<path d="M21 12a9 9 0 1 1-2.6-6.4"/><path d="M21 3v6h-6"/></svg>'
               '<span>刷新</span></button>')
    return f"""<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<meta name="format-detection" content="telephone=no">
<meta name="theme-color" content="#f2f4f7">
<title>{title}</title><style>{CSS}{FUND_CSS}</style></head>
<body><div class="wrap">
<div class="bar"><h1>{title}</h1>{btn}
<button class="btn" id="tbtn" title="切换背景"><span id="tico">🌙</span></button></div>
{body}
<div class="card"><div class="foot">由脚本自动生成 · {generated} ·
数据：腾讯行情 / 天天基金 · 仅供参考，不构成投资建议</div></div>
</div><div class="toast" id="toast"></div><script>{JS}</script><script>{FUND_JS}</script></body></html>"""


FUND_CSS = """
.fh{display:flex;align-items:center;gap:10px;flex-wrap:wrap;margin-bottom:10px}
.fh h2{margin:0}
.fsearch{position:relative;flex:0 1 300px;margin-left:auto;min-width:180px}
.fsearch input{width:100%;padding:7px 10px;font-size:13px;border-radius:8px;
border:1px solid var(--btlborder);background:var(--btn);color:var(--fg);outline:none}
.fsearch input:focus{border-color:#3b82f6}
.fres{position:absolute;z-index:40;top:calc(100% + 4px);left:0;right:0;background:var(--card);
border:1px solid var(--btlborder);border-radius:10px;box-shadow:0 10px 28px rgba(0,0,0,.2);
max-height:320px;overflow:auto;display:none}
.fres.on{display:block}
.fitem{display:flex;align-items:center;gap:6px;padding:8px 10px;
border-bottom:1px solid var(--line);font-size:13px}
.fitem:last-child{border-bottom:0}
.fitem .fname{flex:1;min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.fitem .fcode{color:var(--muted);font-size:12px;flex:none}
.fb{border:1px solid var(--btlborder);background:transparent;color:var(--fg);
border-radius:6px;padding:3px 8px;font-size:12px;line-height:1.3;cursor:pointer;flex:none}
.fb.pri{background:#3b82f6;border-color:#3b82f6;color:#fff}
.fempty{padding:12px;font-size:12px;color:var(--muted);text-align:center}
#fmenu{position:fixed;z-index:60;background:var(--card);border:1px solid var(--btlborder);
border-radius:9px;box-shadow:0 8px 24px rgba(0,0,0,.28);display:none;min-width:104px;overflow:hidden}
#fmenu.on{display:block}
#fmenu button{display:block;width:100%;text-align:left;padding:9px 16px;background:none;
border:0;color:#e5484d;font-size:14px;cursor:pointer}
.mask{position:fixed;inset:0;z-index:70;background:rgba(0,0,0,.45);display:none;
align-items:center;justify-content:center;padding:20px}
.mask.on{display:flex}
.dlg{background:var(--card);border-radius:14px;padding:20px;max-width:380px;width:100%;
box-shadow:0 20px 60px rgba(0,0,0,.35)}
.dlg h3{margin:0 0 10px;font-size:16px}
.dlg p{margin:0 0 18px;font-size:14px;line-height:1.6;color:var(--muted)}
.dlg .row{display:flex;gap:10px;justify-content:flex-end}
.dlg .row button{min-width:86px;padding:9px 14px;border-radius:9px;border:1px solid var(--btlborder);
background:transparent;color:var(--fg);font-size:14px;cursor:pointer}
.dlg .row button.danger{background:#e5484d;border-color:#e5484d;color:#fff}
.kv{display:grid;grid-template-columns:auto 1fr;gap:7px 16px;font-size:13.5px;margin:0 0 18px}
.kv span:nth-child(odd){color:var(--muted)}
.frow{cursor:default}
"""

FUND_JS = r"""
(function(){
  var OVK='radar-funds-ov';
  function ovLoad(){
    try{var o=JSON.parse(localStorage.getItem(OVK)||'{}');
      return {del:o.del||[],add:o.add||[]};}catch(e){return {del:[],add:[]};}
  }
  function ovSave(){try{localStorage.setItem(OVK,JSON.stringify(OV));}catch(e){}}
  var OV=ovLoad();
  var tbody=document.getElementById('ftbody');
  if(!tbody) return;
  var mask=null,menu=null;

  function mk(tag,cls,txt){var e=document.createElement(tag);if(cls)e.className=cls;
    if(txt!=null)e.textContent=txt;return e;}

  function fmtPct(v){ if(v==null||isNaN(v)) return '—';
    return (v>0?'+':'')+v.toFixed(2)+'%'; }
  function clsOf(v){ if(v==null||isNaN(v)||v===0) return 'flat';
    return v>0?'up':'down'; }

  function setCell(tr,i,txt,cls){
    var c=tr.children[i]; if(!c) return;
    c.textContent=txt; if(cls) c.className=cls;
  }

  function metrics(){
    var t=window.Data_netWorthTrend||[];
    if(!t.length) return null;
    var last=t[t.length-1].y, px=t.length>1?t[t.length-2].y:last;
    function back(n){ return t.length>n+1?t[t.length-1-n].y:null; }
    var p5=back(5), p20=back(20);
    return {nav:last, name:window.fS_name||'',
      d1:(last/px-1)*100,
      d5:p5?(last/p5-1)*100:null,
      d20:p20?(last/p20-1)*100:null};
  }

  var navQueue=[], navBusy=false;
  function loadNav(code,done){
    navQueue.push([code,done]); if(!navBusy) nextNav();
  }
  function nextNav(){
    if(!navQueue.length){navBusy=false;return;}
    navBusy=true;
    var job=navQueue.shift();
    var s=document.createElement('script');
    s.src='https://fund.eastmoney.com/pingzhongdata/'+job[0]+'.js?v='+Date.now();
    s.onload=function(){
      try{ job[1](metrics()); }catch(e){}
      s.remove(); nextNav();
    };
    s.onerror=function(){ try{job[1](null);}catch(e){} s.remove(); nextNav(); };
    document.head.appendChild(s);
  }

  function adviceFor(m){
    if(!m) return '暂无净值数据';
    if(m.d20!=null&&m.d20<=-10) return '20日跌幅较大，趋势偏弱 → 暂不加，观察能否企稳';
    if(m.d5!=null&&m.d20!=null&&m.d5>0&&m.d20>0) return '5日/20日同向上 → 可继续持有，回踩再加';
    if(m.d5!=null&&m.d5<=-3) return '5日走弱 → 本期定投可跳过';
    return '趋势未明 → 观察，等右侧信号';
  }

  function fillRow(tr,code){
    loadNav(code,function(m){
      if(!m){ setCell(tr,1,'—'); return; }
      setCell(tr,1,m.nav.toFixed(4));
      setCell(tr,2,fmtPct(m.d1),clsOf(m.d1));
      setCell(tr,3,fmtPct(m.d5),clsOf(m.d5));
      setCell(tr,4,fmtPct(m.d20),clsOf(m.d20));
      setCell(tr,5,'观察','act a-watch');
      setCell(tr,6,adviceFor(m),'adv');
      if(m.name){ var sub=tr.querySelector('.sub'); if(sub) sub.textContent=code; }
    });
  }

  function makeRow(code,name){
    var tr=mk('tr','frow');
    tr.setAttribute('data-code',code); tr.setAttribute('data-name',name||code);
    tr.appendChild(mk('td',null,name||code)).appendChild(mk('span','sub',code));
    for(var i=0;i<4;i++) tr.appendChild(mk('td',null,'—'));
    tr.appendChild(mk('td','act a-watch','观察'));
    tr.appendChild(mk('td','adv','加载中…'));
    return tr;
  }

  function applyDeletes(){
    var keep=OV.del;
    Array.prototype.forEach.call(tbody.querySelectorAll('tr[data-code]'),function(tr){
      if(keep.indexOf(tr.getAttribute('data-code'))>=0) tr.remove();
    });
  }

  function applyAdds(){
    OV.add.forEach(function(f){
      if(tbody.querySelector('tr[data-code="'+f.code+'"]')) return;
      var tr=makeRow(f.code,f.name);
      tbody.appendChild(tr);
      fillRow(tr,f.code);
    });
  }

  function closeMenu(){ if(menu) menu.classList.remove('on'); }
  function showMenu(x,y,code,name){
    if(!menu){
      menu=mk('div'); menu.id='fmenu';
      var b=mk('button',null,'删除');
      b.onclick=function(){ closeMenu(); askDelete(code,name); };
      menu.appendChild(b); document.body.appendChild(menu);
    }
    menu.style.left=Math.min(x,window.innerWidth-120)+'px';
    menu.style.top=Math.min(y,window.innerHeight-70)+'px';
    menu.classList.add('on');
  }

  function dialog(title,body,okText,okCls,onOk){
    if(mask) mask.remove();
    mask=mk('div','mask');
    var d=mk('div','dlg');
    d.appendChild(mk('h3',null,title));
    d.appendChild(body);
    var row=mk('div','row');
    var cancel=mk('button',null,'取消');
    var ok=mk('button',okCls,okText);
    cancel.onclick=function(){ mask.classList.remove('on'); };
    ok.onclick=function(){ mask.classList.remove('on'); onOk(); };
    row.appendChild(cancel); row.appendChild(ok); d.appendChild(row);
    mask.appendChild(d); document.body.appendChild(mask);
    requestAnimationFrame(function(){ mask.classList.add('on'); });
    mask.onclick=function(e){ if(e.target===mask) mask.classList.remove('on'); };
  }

  function askDelete(code,name){
    var p=mk('p',null,'你确定要删除该基金信息？');
    p.style.color='var(--fg)';
    dialog('删除基金',p,'确定','danger',function(){
      var tr=tbody.querySelector('tr[data-code="'+code+'"]'); if(tr) tr.remove();
      var i=OV.add.findIndex(function(f){return f.code===code;});
      if(i>=0){ OV.add.splice(i,1); }
      if(OV.del.indexOf(code)<0) OV.del.push(code);
      ovSave();
      toast('已删除 '+name);
    });
  }

  // 右键 / 长按 触发删除菜单
  var pressTimer=null, startX=0, startY=0;
  tbody.addEventListener('contextmenu',function(e){
    var tr=e.target.closest('tr[data-code]'); if(!tr) return;
    e.preventDefault();
    showMenu(e.clientX,e.clientY,tr.getAttribute('data-code'),tr.getAttribute('data-name'));
  });
  tbody.addEventListener('touchstart',function(e){
    var tr=e.target.closest('tr[data-code]'); if(!tr) return;
    var t=e.touches[0]; startX=t.clientX; startY=t.clientY;
    pressTimer=setTimeout(function(){
      showMenu(startX,startY,tr.getAttribute('data-code'),tr.getAttribute('data-name'));
      if(navigator.vibrate) navigator.vibrate(15);
    },600);
  },{passive:true});
  function cancelPress(){ if(pressTimer){clearTimeout(pressTimer);pressTimer=null;} }
  tbody.addEventListener('touchend',cancelPress);
  tbody.addEventListener('touchmove',function(e){
    var t=e.touches[0];
    if(Math.abs(t.clientX-startX)>10||Math.abs(t.clientY-startY)>10) cancelPress();
  },{passive:true});
  tbody.addEventListener('touchcancel',cancelPress);
  document.addEventListener('click',function(e){
    if(menu&&!menu.contains(e.target)) closeMenu();
  });

  var toastEl=document.getElementById('toast');
  function toast(msg){
    if(!toastEl) return;
    toastEl.textContent=msg; toastEl.classList.add('on');
    setTimeout(function(){toastEl.classList.remove('on');},2200);
  }

  // ---------- 搜索添加 ----------
  var inp=document.getElementById('fq'), box=document.getElementById('fres');
  var seq=0, timer=null;

  function jsonp(key,token){
    var cb='__fsearch'+(++seq);
    window[cb]=function(d){
      try{ render(d); }finally{ delete window[cb]; }
    };
    var s=document.createElement('script');
    s.src='https://fundsuggest.eastmoney.com/FundSearch/api/FundSearchAPI.ashx?m=1&key='
      +encodeURIComponent(key)+'&callback='+cb+'&_='+token;
    s.onerror=function(){ delete window[cb]; };
    document.head.appendChild(s);
  }

  function render(d){
    box.innerHTML='';
    var list=(d&&d.Datas)||[];
    if(!list.length){ box.appendChild(mk('div','fempty','没有找到匹配的基金')); box.classList.add('on'); return; }
    list.slice(0,12).forEach(function(it){
      var info=it.FundBaseInfo||{};
      var row=mk('div','fitem');
      var nm=mk('div','fname',it.NAME||it.SHORTNAME||'');
      var cd=mk('div','fcode',it.CODE);
      var ba=mk('button','fb pri','添加');
      var vb=mk('button','fb','查看');
      ba.onclick=function(){ doAdd(it.CODE,it.NAME||info.SHORTNAME||'',info); };
      vb.onclick=function(){ doView(it.CODE,it.NAME||info.SHORTNAME||'',info); };
      row.appendChild(nm); row.appendChild(cd); row.appendChild(ba); row.appendChild(vb);
      box.appendChild(row);
    });
    box.classList.add('on');
  }

  function doAdd(code,name,info){
    box.classList.remove('on'); inp.value='';
    if(tbody.querySelector('tr[data-code="'+code+'"]')){ toast('该基金已在列表中'); return; }
    var i=OV.del.indexOf(code); if(i>=0) OV.del.splice(i,1);
    OV.add.push({code:code,name:name});
    ovSave();
    var tr=makeRow(code,name);
    tbody.appendChild(tr);
    fillRow(tr,code);
    toast('已添加 '+name);
  }

  function doView(code,name,info){
    box.classList.remove('on');
    var body=mk('div');
    var kv=mk('div','kv');
    function line(k,v){ kv.appendChild(mk('span',null,k)); kv.appendChild(mk('span',null,v)); }
    line('代码',code); line('名称',name);
    if(info.FTYPE) line('类型',info.FTYPE);
    if(info.JJGS) line('公司',info.JJGS);
    if(info.JJJL) line('经理',info.JJJL);
    if(info.DWJZ) line('最新净值',Number(info.DWJZ).toFixed(4)+(info.FSRQ?'（'+info.FSRQ+'）':''));
    body.appendChild(kv);
    var extra=mk('p',null,'正在读取净值走势…');
    extra.style.margin='0';
    body.appendChild(extra);
    dialog('基金信息',body,'关闭','',function(){});
    loadNav(code,function(m){
      if(!m){ extra.textContent='净值数据读取失败'; return; }
      extra.textContent='日 '+fmtPct(m.d1)+'　5日 '+fmtPct(m.d5)+'　20日 '+fmtPct(m.d20);
    });
  }

  inp.addEventListener('input',function(){
    clearTimeout(timer);
    var k=inp.value.trim();
    if(k.length<2){ box.classList.remove('on'); return; }
    timer=setTimeout(function(){
      box.innerHTML=''; box.appendChild(mk('div','fempty','搜索中…')); box.classList.add('on');
      jsonp(k,Date.now());
    },320);
  });
  document.addEventListener('click',function(e){
    if(box&&!box.contains(e.target)&&e.target!==inp) box.classList.remove('on');
  });

  applyDeletes();
  applyAdds();
})();
"""


def report_block(rep, day):
    rows = [x for x in rep.get("rows", []) if x.get("role") != "对照"]
    frows = rep.get("frows", [])
    up = sum(1 for x in rows if x["act"] == "加仓")
    dn = sum(1 for x in rows if x["act"] in ("减仓", "清仓"))
    head = f"加仓 {up} 个、减仓 {dn} 个" if (up or dn) else "无明确加减仓信号"
    rt = []
    for x in rows:
        rt.append(
            f'<tr><td>{x["name"]}</td>'
            f'<td class="{cls(x["today"])}">{pct(x["today"])}</td>'
            f'<td class="{cls(x["d5"])}">{pct(x["d5"])}</td>'
            f'<td class="{cls(x["d20"])}">{pct(x["d20"])}</td>'
            f'<td class="{cls(x["main5"])}">{x["main5"]/1e4:+.0f}亿</td>'
            f'<td class="act {ACT_CLS.get(x["act"], "")}">{x["act"]}</td></tr>')
    ft = []
    for x in frows:
        ft.append(
            f'<tr class="frow" data-code="{x["code"]}" data-name="{x["tag"]}">'
            f'<td>{x["tag"]}<br><span class="sub">{x["code"]}</span></td>'
            f'<td>{x["nav"]:.4f}</td>'
            f'<td class="{cls(x["d1"])}">{pct(x["d1"])}</td>'
            f'<td class="{cls(x["d5"])}">{pct(x["d5"])}</td>'
            f'<td class="{cls(x["d20"])}">{pct(x["d20"])}</td>'
            f'<td class="act {ACT_CLS.get(x["act"], "")}">{x["act"]}</td>'
            f'<td class="adv" style="min-width:210px">{x["advice"]}</td></tr>')
    return f"""
<div class="card">
<h2>板块信号</h2>
<div class="sub" style="margin-bottom:8px">今日信号：{head}</div>
<div class="scroll"><table>
<tr><th>板块</th><th>今日</th><th>5日</th><th>20日</th><th>主力5日</th><th>信号</th></tr>
{''.join(rt)}</table></div>
</div>
<div class="card">
<div class="fh"><h2>持仓基金与操作</h2>
<div class="fsearch"><input id="fq" placeholder="搜索基金代码或名称" autocomplete="off">
<div class="fres" id="fres"></div></div></div>
<div class="scroll"><table>
<thead><tr><th>基金</th><th>净值</th><th>日</th><th>5日</th><th>20日</th><th>信号</th><th class="adv">建议</th></tr></thead>
<tbody id="ftbody">
{''.join(ft)}</tbody></table></div>
<div class="tip">左右滑动可看完整表格 · 长按/右键任意基金行可删除 · 上方搜索框可添加</div>
</div>"""


def load_am(day):
    p = os.path.join(HIST, day.replace("-", "") + "_am.json")
    if not os.path.exists(p):
        return None
    try:
        with open(p, encoding="utf-8") as f:
            d = json.load(f)
        return d if d.get("report") else None
    except Exception:
        return None


def am_block(rep, day, ts=""):
    rows = [x for x in rep.get("rows", []) if x.get("role") != "对照"]
    rt = []
    for x in rows:
        rt.append(
            f'<tr><td>{x["name"]}</td>'
            f'<td class="{cls(x["today"])}">{pct(x["today"])}</td>'
            f'<td class="{cls(x["d5"])}">{pct(x["d5"])}</td>'
            f'<td class="{cls(x["d20"])}">{pct(x["d20"])}</td>'
            f'<td class="{cls(x["main5"])}">{x["main5"]/1e4:+.0f}亿</td>'
            f'<td class="act {ACT_CLS.get(x["act"], "")}">{x["act"]}</td></tr>')
    t = f' · 采集于 {ts.replace("T", " ")[:16]}' if ts else ""
    return f"""
<div class="card">
<h2>上午收盘（11:30）· {day}</h2>
<div class="sub" style="margin:-4px 0 8px">半日数据，仅供盘中参考；全天信号见下方“板块信号”{t}</div>
<div class="scroll"><table>
<tr><th>板块</th><th>今日</th><th>5日</th><th>20日</th><th>主力5日</th><th>信号</th></tr>
{''.join(rt)}</table></div>
</div>"""


def main():
    os.makedirs(OUT, exist_ok=True)
    os.makedirs(DAILY, exist_ok=True)
    days = load_days()
    if not days:
        print("没有快照（data/history/*.json 缺 report 字段），先运行 daily.py")
        return 1
    generated = time.strftime("%Y-%m-%d %H:%M")
    removed = prune(days)
    days = days[:KEEP]
    latest = days[0]

    # ---- 每日页面（仅最近 10 天）----
    for d in days:
        rep = d["report"]
        chips = "".join(f'<span class="chip">{p}</span>' for p in rep.get("idx", []))
        nm = d["date"].replace("-", "")
        body = (f'<div class="card"><h1>A股板块 · {d["date"]}</h1>'
                f'<div class="chips">{chips}</div></div>'
                + report_block(rep, d["date"]))
        if rep.get("notice"):
            body = body.replace('<div class="chips">',
                                f'<div class="note">{rep["notice"]}</div><div class="chips">', 1)
        with open(os.path.join(DAILY, f"{nm}.html"), "w", encoding="utf-8") as f:
            f.write(page(f"A股板块 {d['date']}",
                         body + '<div class="card"><a href="../index.html">← 返回最新</a></div>',
                         generated))

    # ---- 最新页 ----
    rep = latest["report"]
    chips = "".join(f'<span class="chip">{p}</span>' for p in rep.get("idx", []))
    head = (f'<div class="card"><h1>A股板块雷达</h1>'
            f'<div class="sub">最新交易日 {latest["date"]} · 上午收盘 12:30 / 全天收盘 16:10 后自动更新</div>'
            f'<div class="chips">{chips}</div></div>')
    if rep.get("notice"):
        head = head.replace('<div class="chips">',
                            f'<div class="note">{rep["notice"]}</div><div class="chips">', 1)

    # ---- 近 10 个交易日对比 ----
    th = "".join(f"<th>{n}</th>" for _, n in KEYS)
    fh = "".join(f"<th>{n}</th>" for _, n in FUNDS)
    trs = []
    for d in days:
        s = d.get("sectors") or {}
        cells = []
        for code, _ in KEYS:
            v = (s.get(code) or {}).get("today")
            cells.append(f'<td class="{cls(v)}">{pct(v)}</td>' if v is not None
                         else '<td class="flat">—</td>')
        fc = []
        for code, _ in FUNDS:
            nav = ((d.get("funds") or {}).get(code) or {}).get("nav")
            fc.append(f"<td>{nav:.4f}</td>" if nav else '<td class="flat">—</td>')
        trs.append(f'<tr><td>{d["date"]}</td>' + "".join(cells) + "".join(fc) + "</tr>")

    am = load_am(latest["date"])
    amh = am_block(am["report"], latest["date"], am.get("ts", "")) if am else ""
    body = head + amh + report_block(rep, latest["date"]) + f"""
<div class="card"><h2>近10个交易日：板块日涨幅 / 基金净值</h2>
<div class="scroll"><table>
<tr><th>日期</th>{th}{fh}</tr>
{''.join(trs)}</table></div>
<div class="tip">红色=涨，绿色=跌 · 只保留最近 10 个交易日</div></div>"""
    with open(os.path.join(OUT, "index.html"), "w", encoding="utf-8") as f:
        f.write(page("A股板块雷达", body, generated))
    with open(os.path.join(OUT, ".nojekyll"), "w", encoding="utf-8") as f:
        f.write("")
    print(f"[OK] site/ 已生成：index.html + {len(days)} 个日页面（清理旧快照 {removed} 个）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
