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
<title>{title}</title><style>{CSS}</style></head>
<body><div class="wrap">
<div class="bar"><h1>{title}</h1>{btn}
<button class="btn" id="tbtn" title="切换背景"><span id="tico">🌙</span></button></div>
{body}
<div class="card"><div class="foot">由脚本自动生成 · {generated} ·
数据：腾讯行情 / 天天基金 · 仅供参考，不构成投资建议</div></div>
</div><div class="toast" id="toast"></div><script>{JS}</script></body></html>"""


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
            f'<tr><td>{x["tag"]}<br><span class="sub">{x["code"]}</span></td>'
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
<h2>持仓基金与操作</h2>
<div class="scroll"><table>
<tr><th>基金</th><th>净值</th><th>日</th><th>5日</th><th>20日</th><th>信号</th><th class="adv">建议</th></tr>
{''.join(ft)}</table></div>
<div class="tip">左右滑动可看完整表格</div>
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
            f'<div class="sub">最新交易日 {latest["date"]} · 每交易日 16:10 后自动更新</div>'
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

    body = head + report_block(rep, latest["date"]) + f"""
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
