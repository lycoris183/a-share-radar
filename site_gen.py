"""生成静态网站：site/index.html（最新交易日）+ site/d/YYYYMMDD.html（历史每日）+ 30日对比表。
数据来源：data/history/*.json（daily.py 生成，含 report 字段）
用法：python site_gen.py
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

KEYS = [("pt02GN2238", "人形机器人"), ("pt02GN2442", "物理AI"),
        ("pt01801750", "计算机"), ("pt02GN2116", "半导体"),
        ("pt01801960", "石油石化"), ("pt01801780", "银行")]
FUNDS = [("010365", "港股银行"), ("023145", "油气资源"), ("020973", "机器人"),
         ("001630", "计算机"), ("007301", "半导体")]
AC_COLOR = {"加仓": "#c0392b", "持有": "#1e7e34", "观察": "#8a6d3b",
            "减仓": "#2c3e50", "清仓": "#111111"}

CSS = """
*{box-sizing:border-box;-webkit-text-size-adjust:100%}
body{margin:0;background:#f2f4f7;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',
'Microsoft YaHei',sans-serif;color:#1c1e21;font-size:15px;line-height:1.5}
.wrap{max-width:880px;margin:0 auto;padding:12px}
.card{background:#fff;border-radius:10px;padding:14px;margin:12px 0;
box-shadow:0 1px 3px rgba(0,0,0,.07)}
h1{font-size:19px;margin:0 0 4px}
h2{font-size:15px;margin:0 0 10px;color:#333}
.sub{font-size:12px;color:#8a8f98}
.chips{display:flex;flex-wrap:wrap;gap:6px;margin-top:10px}
.chip{background:#f4f6f8;border-radius:6px;padding:5px 9px;font-size:12.5px;white-space:nowrap}
.scroll{overflow-x:auto;-webkit-overflow-scrolling:touch;margin:0 -4px}
table{border-collapse:collapse;width:100%;min-width:520px}
th,td{padding:7px 8px;border-bottom:1px solid #eef1f3;font-size:13px;white-space:nowrap}
th{background:#f7f9fa;color:#5b6470;font-size:12px;font-weight:600;text-align:right;
position:sticky;top:0}
th:first-child,td:first-child{text-align:left;position:sticky;left:0;background:#fff;z-index:1}
th:first-child{background:#f7f9fa}
.up{color:#c0392b}.down{color:#1e7e34}.flat{color:#8a8f98}
.act{font-weight:700}
.note{background:#fff8e1;border-left:4px solid #f0ad4e;padding:8px 10px;border-radius:4px;
font-size:12.5px;color:#7a5c00;margin-bottom:10px}
.tip{font-size:11.5px;color:#9aa0a6;margin-top:6px}
.foot{font-size:11.5px;color:#9aa0a6;line-height:1.7}
.days{display:flex;flex-wrap:wrap;gap:6px}
.days a{font-size:12.5px;color:#2b6cb0;background:#eef4fb;border-radius:6px;
padding:4px 8px;text-decoration:none}
@media (max-width:600px){
  .wrap{padding:8px}
  .card{padding:10px;border-radius:8px;margin:9px 0}
  h1{font-size:17px}
  th,td{padding:6px 6px;font-size:12px}
  table{min-width:460px}
}
"""


def cls(v):
    return "up" if v > 0 else ("down" if v < 0 else "flat")


def pct(v, dec=2):
    return f"{v:+.{dec}f}%"


def load_days():
    out = []
    for p in glob.glob(os.path.join(HIST, "*.json")):
        try:
            with open(p, encoding="utf-8") as f:
                d = json.load(f)
            if d.get("date") and d.get("report"):
                out.append(d)
        except Exception:
            pass
    return sorted(out, key=lambda d: d["date"], reverse=True)


def page(title, body, generated):
    return f"""<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<meta name="format-detection" content="telephone=no">
<meta name="theme-color" content="#f2f4f7">
<title>{title}</title><style>{CSS}</style></head>
<body><div class="wrap">{body}
<div class="card"><div class="foot">由脚本自动生成 · {generated} ·
数据：腾讯行情 / 天天基金 · 仅供参考，不构成投资建议</div></div>
</div></body></html>"""


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
            f'<td class="act" style="color:{AC_COLOR.get(x["act"], "#333")}">{x["act"]}</td></tr>')
    ft = []
    for x in frows:
        ft.append(
            f'<tr><td>{x["tag"]}<br><span class="sub">{x["code"]}</span></td>'
            f'<td>{x["nav"]:.4f}</td>'
            f'<td class="{cls(x["d1"])}">{pct(x["d1"])}</td>'
            f'<td class="{cls(x["d5"])}">{pct(x["d5"])}</td>'
            f'<td class="{cls(x["d20"])}">{pct(x["d20"])}</td>'
            f'<td class="act" style="color:{AC_COLOR.get(x["act"], "#333")}">{x["act"]}</td>'
            f'<td style="white-space:normal;min-width:190px">{x["advice"]}</td></tr>')
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
<tr><th>基金</th><th>净值</th><th>日</th><th>5日</th><th>20日</th><th>信号</th><th>建议</th></tr>
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
    latest = days[0]

    # ---- 每日页面 ----
    links = []
    for d in days:
        rep = d["report"]
        chips = "".join(f'<span class="chip">{p}</span>' for p in rep.get("idx", []))
        nm = d["date"].replace("-", "")
        body = (f'<div class="card"><h1>A股板块 · {d["date"]}</h1>'
                f'<div class="chips">{chips}</div></div>'
                + report_block(rep, d["date"]))
        if rep.get("notice"):
            body = body.replace('<div class="chips">', f'<div class="note">{rep["notice"]}</div><div class="chips">', 1)
        with open(os.path.join(DAILY, f"{nm}.html"), "w", encoding="utf-8") as f:
            f.write(page(f"A股板块 {d['date']}", body + '<div class="card"><a href="../index.html">← 返回最新</a></div>', generated))
        links.append(f'<a href="d/{nm}.html">{d["date"]}</a>')

    # ---- 最新页 ----
    rep = latest["report"]
    chips = "".join(f'<span class="chip">{p}</span>' for p in rep.get("idx", []))
    head = (f'<div class="card"><h1>A股板块雷达</h1>'
            f'<div class="sub">最新交易日 {latest["date"]} · 每交易日 16:10 后自动更新</div>'
            f'<div class="chips">{chips}</div></div>')
    if rep.get("notice"):
        head = head.replace('<div class="chips">', f'<div class="note">{rep["notice"]}</div><div class="chips">', 1)

    # ---- 30 日对比 ----
    th = "".join(f"<th>{n}</th>" for _, n in KEYS)
    fh = "".join(f"<th>{n}</th>" for _, n in FUNDS)
    trs = []
    for d in days[:30]:
        s = d.get("sectors") or {}
        cells = []
        for code, _ in KEYS:
            v = (s.get(code) or {}).get("today")
            cells.append(f'<td class="{cls(v)}">{pct(v)}</td>' if v is not None else '<td class="flat">—</td>')
        fc = []
        for code, _ in FUNDS:
            nav = ((d.get("funds") or {}).get(code) or {}).get("nav")
            fc.append(f"<td>{nav:.4f}</td>" if nav else '<td class="flat">—</td>')
        trs.append(f'<tr><td>{d["date"]}</td>' + "".join(cells) + "".join(fc) + "</tr>")

    body = head + report_block(rep, latest["date"]) + f"""
<div class="card"><h2>近30个交易日：板块日涨幅 / 基金净值</h2>
<div class="scroll"><table>
<tr><th>日期</th>{th}{fh}</tr>
{''.join(trs)}</table></div>
<div class="tip">红色=涨，绿色=跌</div></div>
<div class="card"><h2>历史页面</h2><div class="days">{''.join(links)}</div></div>"""
    with open(os.path.join(OUT, "index.html"), "w", encoding="utf-8") as f:
        f.write(page("A股板块雷达", body, generated))
    with open(os.path.join(OUT, ".nojekyll"), "w", encoding="utf-8") as f:
        f.write("")
    print(f"[OK] site/ 已生成：index.html + {len(days)} 个日页面")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
