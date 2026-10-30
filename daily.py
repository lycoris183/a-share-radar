# -*- coding: utf-8 -*-
"""每日板块行情分析 + 操作建议（腾讯行情数据源）

用法:  python daily.py
输出:  reports/YYYY-MM-DD.md  +  控制台中文摘要
状态:  data/history/YYYYMMDD.json（每日快照，用于连续主力流向、净值变化）

打分规则（透明可调）:
  动量: d5>0 +2 / d5<-3 -2 ; d20>-5 +1 / d20<-12 -1
  资金: main5>+20亿 +2 / main5<-20亿 -2 ; main1>+10亿 +1 / main1<-10亿 -1
  硬规则: d20<-15 且 main5<0 -> 至少减仓 ; 主力连续>=3日流出 -1
  总分 >=4 加仓 | >=1 持有 | 0/-1 观察 | <=-2 减仓 | <=-4 清仓
"""
import json, os, sys, time, urllib.request, datetime, csv, hashlib

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
HIST = os.path.join(DATA, "history")
REPO = os.path.join(HERE, "reports")
for d in (DATA, HIST, REPO):
    os.makedirs(d, exist_ok=True)

HDR = {"User-Agent": "Mozilla/5.0", "Referer": "https://gu.qq.com/"}
TZ = datetime.timezone(datetime.timedelta(hours=8))

WATCH = [
    ("pt02GN2238", "人形机器人", "核心", "020973"),
    ("pt02GN2165", "减速器",     "核心", ""),
    ("pt02GN2442", "物理AI",     "核心", ""),
    ("pt01801750", "计算机",     "核心", "001630"),
    ("pt02GN2116", "半导体产业", "核心", "007301"),
    ("pt02003800", "人工智能",   "核心", ""),
    ("pt01801960", "石油石化",   "核心", "023145"),
    ("pt01801890", "机械设备",   "观察", ""),
    ("pt01801790", "非银金融",   "观察", ""),
    ("pt01801730", "电力设备",   "对照", ""),
    ("pt01801780", "银行",       "对照", "010365"),
]
# 基金 -> (显示名, 对应A股板块code 或 None)
FUNDS = {
    "010365": ("鹏华中证香港银行指数C", "港股银行", None),
    "023145": ("汇添富中证油气资源ETF联接C", "油气资源", "pt01801960"),
    "020973": ("易方达机器人ETF联接C", "机器人", "pt02GN2238"),
    "001630": ("天弘中证计算机ETF联接C", "计算机", "pt01801750"),
    "007301": ("国联安中证半导体ETF联接C", "半导体", "pt02GN2116"),
}
INDEXES = [("sh000001", "上证"), ("sz399001", "深成"), ("sz399006", "创业板"),
           ("hkHSI", "恒指")]


class Tee:
    def __init__(self, path):
        self.f = open(path, "w", encoding="utf-8")
        self.out = sys.stdout

    def write(self, s):
        self.out.write(s)
        self.f.write(s)

    def flush(self):
        try:
            self.out.flush(); self.f.flush()
        except Exception:
            pass

    def close(self):
        self.f.close()


def http(url, timeout=25, tries=3):
    last = None
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers=HDR)
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.read()
        except Exception as e:  # 网络抖动/接口限流：退避重试
            last = e
            if i < tries - 1:
                time.sleep(1.5 * (i + 1))
    raise last


def jget(url, timeout=25):
    return json.loads(http(url, timeout).decode("utf-8", "replace"))


def fetch_board(bt, count=100, maxn=1200):
    rows, off = [], 0
    while off < maxn:
        u = ("http://proxy.finance.qq.com/cgi/cgi-bin/rank/pt/getRank?"
             f"board_type={bt}&sort_type=price&direct=down&offset={off}&count={count}")
        data = jget(u).get("data") or {}
        lst = data.get("rank_list") or []
        rows += lst
        if not lst or len(rows) >= (data.get("total") or 0):
            break
        off += count
        time.sleep(0.2)
    return rows


def f(x, d=0.0):
    try:
        return float(x)
    except Exception:
        return d


def snapshot_today():
    recs = {}
    for bt in ("hy", "gn"):
        for r in fetch_board(bt):
            code = r.get("code")
            if code and code not in recs:
                recs[code] = r
    return recs


def norm(r):
    return {
        "name": r.get("name"), "today": f(r.get("zdf")), "d5": f(r.get("zdf_d5")),
        "d20": f(r.get("zdf_d20")), "d60": f(r.get("zdf_d60")), "ytd": f(r.get("zdf_y")),
        "main1": f(r.get("zljlr")), "main5": f(r.get("zljlr_d5")),
        "mcap": f(r.get("zsz")), "lead": (r.get("lzg") or {}).get("name", ""),
        "zgb": r.get("zgb") or "",
    }


def qq_quotes(codes):
    """qt.gtimg.cn 批量报价；指数返回 price/prev，基金返回 nav/date"""
    out = {}
    for i in range(0, len(codes), 20):
        chunk = codes[i:i + 20]
        try:
            txt = http("http://qt.gtimg.cn/q=" + ",".join(chunk)).decode("gbk", "replace")
        except Exception as e:
            print("行情失败", chunk, repr(e))
            continue
        for line in txt.split(";"):
            line = line.strip()
            if not line.startswith("v_"):
                continue
            try:
                key = line[2:line.index("=")]
                body = line[line.index('"') + 1:line.rindex('"')]
                p = body.split("~")
                if key.startswith("jj"):
                    out[key[2:]] = {"name": p[1], "nav": f(p[5]),
                                    "date": p[8] if len(p) > 8 else ""}
                else:
                    out[key] = {"name": p[1], "price": f(p[3]), "prev": f(p[4])}
            except Exception:
                continue
    return out


def load_prev():
    files = sorted((x for x in os.listdir(HIST)
                    if x.endswith(".json") and not x.endswith("_am.json")), reverse=True)
    for last in files:
        try:
            with open(os.path.join(HIST, last), encoding="utf-8") as fp:
                d = json.load(fp)
            if d.get("date"):
                return d["date"], d
        except Exception:
            continue
    return None, None


def save_json(path, obj):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fp:
        json.dump(obj, fp, ensure_ascii=False, indent=1)
    os.replace(tmp, path)


def score(n, streak):
    s, why = 0, []
    if n["d5"] > 0:
        s += 2; why.append("5日转强")
    elif n["d5"] < -3:
        s -= 2; why.append("5日走弱")
    if n["d20"] > -5:
        s += 1
    elif n["d20"] < -12:
        s -= 1; why.append("20日深跌")
    m5, m1 = n["main5"] / 1e4, n["main1"] / 1e4
    if m5 > 20:
        s += 2; why.append(f"5日主力+{m5:.0f}亿")
    elif m5 < -20:
        s -= 2; why.append(f"5日主力{m5:.0f}亿")
    if m1 > 10:
        s += 1; why.append(f"今日主力+{m1:.0f}亿")
    elif m1 < -10:
        s -= 1; why.append(f"今日主力{m1:.0f}亿")
    if n["d20"] < -15 and m5 < 0:
        s = min(s, -2); why.append("趋势破坏")
    if streak >= 3:
        s -= 1; why.append(f"主力连续{streak}日流出")
    act = ("加仓" if s >= 4 else "持有" if s >= 1 else "观察" if s >= -1
           else "减仓" if s >= -4 else "清仓")
    return act, s, "；".join(why) or "-"


def nav_history(code, n=25):
    """东财净值历史 -> [(日期, 单位净值, 日涨跌%)] 按日期降序（接口每页上限20，翻页）"""
    out, page = [], 1
    while len(out) < n and page <= 5:
        u = (f"http://api.fund.eastmoney.com/f10/lsjz?fundCode={code}"
             f"&pageIndex={page}&pageSize=20")
        try:
            req = urllib.request.Request(u, headers={
                "User-Agent": "Mozilla/5.0", "Referer": "http://fundf10.eastmoney.com/"})
            with urllib.request.urlopen(req, timeout=20) as r:
                d = json.loads(r.read().decode("utf-8", "replace"))
        except Exception:
            break
        lst = (d.get("Data") or {}).get("LSJZList") or []
        if not lst:
            break
        for x in lst:
            try:
                out.append((x.get("FSRQ"), float(x.get("DWJZ")),
                            float(x.get("JZZZL") or 0)))
            except Exception:
                pass
        if len(lst) < 20:
            break
        page += 1
    return out


def build_push(day, idx_parts, rows, frows, notice=""):
    L = [f"{day[5:].replace('-', '/')} 收盘｜" + " ".join(idx_parts)]
    if notice:
        L.append(notice)
    for a in ("加仓", "持有", "观察", "减仓", "清仓"):
        grp = [x for x in rows if x["act"] == a and x["role"] != "对照"]
        for x in grp[:2]:
            L.append(f"{a}｜{x['name']} {x['today']:+.2f}%"
                     f"（5日{x['d5']:+.2f}%，主力5日{x['main5']/1e4:+.0f}亿）")
    L.append("基金：")
    for x in frows:
        L.append(f"· {x['code']} {x['tag']} {x['nav']:.4f} 日{x['d1']:+.2f}% "
                 f"5日{x['d5']:+.2f}% 20日{x['d20']:+.2f}% → {x['act']}")
    return "\n".join(L)


AC_COLOR = {"加仓": "#c0392b", "持有": "#1e7e34", "观察": "#8a6d3b",
            "减仓": "#2c3e50", "清仓": "#111111"}


def cnum(v, pct=True, dec=2):
    c = "#c0392b" if v > 0 else ("#1e7e34" if v < 0 else "#666")
    s = f"{v:+.{dec}f}%" if pct else f"{v:+.0f}"
    return f'<span style="color:{c}">{s}</span>'


def advice(x):
    """把信号翻译成一句可执行建议：位置 + 资金 + 动作 + 风控，保持短句"""
    act, d1, d5, d20 = x["act"], x["d1"], x["d5"], x["d20"]
    m5 = x.get("main5") or 0            # 单位：万元
    fund = f"主力5日{m5/1e4:+.0f}亿" if m5 else ""
    pos = f"20日{d20:+.1f}%"
    tail = ("｜" + fund) if fund else ""

    if act == "加仓":
        if d1 >= 5:
            return (f"动能强但日涨{d1:.1f}%偏急{tail} → 分2笔买，首笔半仓，"
                    f"回踩5日线不破再补")
        return (f"{pos}{tail} → 位置不高、资金配合，本期定投加1份即买，"
                f"跌破20日线止损")
    if act == "持有":
        return f"5日{d5:+.1f}%{tail} → 趋势未破，定投照常，不额外加码"
    if act == "观察":
        return f"{pos}{tail} → 资金未共振，本期定投跳过，待5日转正+资金回补"
    if act == "减仓":
        return f"{tail or pos} 持续流出 → 减1/3锁定利润，留底仓，反弹至5日线再评估"
    return f"{pos}{tail}，趋势结构已破 → 清仓离场，等右侧信号再进"


def build_html(day, idx_parts, rows, frows, notice):
    d = day[5:].replace("-", "/")
    idx = " &nbsp;|&nbsp; ".join(idx_parts)
    vis = [x for x in rows if x["role"] != "对照"]
    up = sum(1 for x in vis if x["act"] == "加仓")
    dn = sum(1 for x in vis if x["act"] in ("减仓", "清仓"))
    head = f"加仓{up}个、减仓{dn}个" if (up or dn) else "无明确加减仓信号"

    td = 'padding:6px 8px;border-bottom:1px solid #eee;font-size:13px;'
    th = ('padding:6px 8px;background:#f4f6f8;border-bottom:2px solid #dfe4e8;'
          'font-size:12px;color:#555;text-align:left;')
    rows_html = []
    for x in rows:
        if x["role"] == "对照":
            continue
        rows_html.append(
            f'<tr><td style="{td}">{x["name"]}</td>'
            f'<td style="{td};text-align:right">{cnum(x["today"])}</td>'
            f'<td style="{td};text-align:right">{cnum(x["d5"])}</td>'
            f'<td style="{td};text-align:right">{cnum(x["d20"])}</td>'
            f'<td style="{td};text-align:right">{cnum(x["main5"]/1e4, pct=False)}亿</td>'
            f'<td style="{td};text-align:right;font-weight:600;color:{AC_COLOR[x["act"]]}">'
            f'{x["act"]}</td></tr>')
    f_html = []
    for x in frows:
        f_html.append(
            f'<tr><td style="{td}">{x["tag"]}<br><span style="color:#888;font-size:11px">'
            f'{x["code"]}</span></td>'
            f'<td style="{td};text-align:right">{x["nav"]:.4f}</td>'
            f'<td style="{td};text-align:right">{cnum(x["d1"])}</td>'
            f'<td style="{td};text-align:right">{cnum(x["d5"])}</td>'
            f'<td style="{td};text-align:right">{cnum(x["d20"])}</td>'
            f'<td style="{td};font-weight:600;color:{AC_COLOR[x["act"]]}">{x["act"]}</td>'
            f'<td style="{td};color:#333">{advice(x)}</td></tr>')

    warn = (f'<div style="background:#fff8e1;border-left:4px solid #f0ad4e;padding:8px 10px;'
            f'margin:0 0 14px;font-size:12px;color:#7a5c00">{notice}</div>' if notice else "")
    return f"""<div style="font-family:-apple-system,'Segoe UI','Microsoft YaHei',sans-serif;
max-width:720px;margin:0 auto;padding:18px;color:#222">
<div style="font-size:19px;font-weight:700;margin-bottom:4px">A股板块收盘 · {d}</div>
<div style="font-size:13px;color:#666;margin-bottom:12px">{idx}</div>
{warn}
<div style="font-size:13px;margin-bottom:14px;padding:8px 10px;background:#f4f6f8;border-radius:4px">
今日信号：<b>{head}</b>。板块方向看下表，基金按"建议"列操作即可，不需要盯盘。</div>

<div style="font-size:15px;font-weight:700;margin:16px 0 6px">一、板块信号</div>
<table style="border-collapse:collapse;width:100%">
<tr><th style="{th}">板块</th><th style="{th};text-align:right">今日</th>
<th style="{th};text-align:right">5日</th><th style="{th};text-align:right">20日</th>
<th style="{th};text-align:right">主力5日</th><th style="{th};text-align:right">信号</th></tr>
{''.join(rows_html)}
</table>

<div style="font-size:15px;font-weight:700;margin:20px 0 6px">二、持仓基金与操作</div>
<table style="border-collapse:collapse;width:100%">
<tr><th style="{th}">基金</th><th style="{th};text-align:right">净值</th>
<th style="{th};text-align:right">日</th><th style="{th};text-align:right">5日</th>
<th style="{th};text-align:right">20日</th><th style="{th}">信号</th>
<th style="{th}">建议</th></tr>
{''.join(f_html)}
</table>

<div style="font-size:11px;color:#999;margin-top:16px;line-height:1.7">
数据：腾讯行情（板块/指数）、天天基金（净值），{day} 收盘。信号由5日/20日涨幅与主力资金流打分得出，
仅供参考，不构成投资建议。<br>
参考：<a href="https://fund.eastmoney.com/" style="color:#2b6cb0">天天基金</a> ·
<a href="https://quote.eastmoney.com/center/boardlist.html#industry_board" style="color:#2b6cb0">东财板块行情</a> ·
<a href="https://gu.qq.com/" style="color:#2b6cb0">腾讯行情</a>
</div></div>"""


def main():
    now = datetime.datetime.now(TZ)
    day = now.strftime("%Y-%m-%d")
    force = "--force" in sys.argv          # 忽略周末/休市保护（补跑用）
    for a in sys.argv:                      # --date 2026-10-30 指定快照日期
        if a.startswith("--date="):
            day = a.split("=", 1)[1].strip()
    # 15:00 前视为"上午收盘快照"（11:30 收盘），否则为全天收盘
    midday = now.hour < 15
    if "--midday" in sys.argv:
        midday = True
    elif "--close" in sys.argv:
        midday = False
    suffix = "_am" if midday else ""
    md_path = os.path.join(REPO, f"{day}{'_am' if midday else ''}.md")
    tee = Tee(md_path)
    sys.stdout = tee
    try:
        print(f"# {day} 板块{'上午收盘' if midday else '收盘'}分析\n")
        if now.isoweekday() >= 6 and not force:
            print("> 今日为周末休市：不采集数据、不生成新快照，网页保留上一个交易日。")
            save_json(os.path.join(DATA, "last_meta.json"),
                      {"date": day, "ts": now.isoformat(timespec="seconds"),
                       "stale": False, "weekday": now.isoweekday(),
                       "trading_day": False, "send_after": "16:10"})
            return 0
        recs = snapshot_today()
        if not recs:
            print("!! 板块数据获取失败（检查网络/接口），本次不产出建议")
            return 1

        prev_day, prev = load_prev()
        fp_sum = hashlib.md5("".join(
            f"{c}:{round(f(recs[c].get('zdf')), 2)}" for c in sorted(recs)
        ).encode()).hexdigest()
        same_fp = bool(prev and prev.get("_fp") == fp_sum)
        stale = bool(prev and prev.get("date") == day and same_fp)
        # 与上一份快照数据完全一致（节假日/停市）：不写新快照，避免把休市日当成交易日
        non_trading = bool(prev and prev.get("date") != day and same_fp)

        idx = qq_quotes([c for c, _ in INDEXES])
        parts = []
        for c, nm in INDEXES:
            q = idx.get(c)
            if q and q["prev"]:
                parts.append(f"{nm} {q['price']:.2f} {(q['price'] / q['prev'] - 1) * 100:+.2f}%")
        print("大盘：" + ("｜".join(parts) if parts else "获取失败"))
        if stale and prev_day == day:
            print("> 今日已运行过且行情未更新（重复运行），以下为同一份收盘数据。")
        elif stale:
            print(f"> 行情与{prev_day}完全一致：今日休市/非交易日，无新数据，不产生新操作。")
        print()

        rows = []
        prev_hist = (prev or {}).get("_hist", {})
        for code, nm, role, fund in WATCH:
            r = recs.get(code)
            if not r:
                print(f"!! 缺失板块 {nm}({code})")
                continue
            n = norm(r)
            hist = (prev_hist.get(code, []) + [n["main1"]])[-10:]
            streak = 0
            for v in reversed(hist):
                if v < 0:
                    streak += 1
                else:
                    break
            act, s, why = score(n, streak)
            rows.append({"code": code, "name": nm, "role": role, "fund": fund,
                         "act": act, "score": s, "why": why, "streak": streak,
                         "_hist": hist, **n})

        print("| 板块 | 角色 | 今日 | 5日 | 20日 | 年内 | 主力5日(亿) | 连续流出 | 信号 | 依据 |")
        print("|---|---|---|---|---|---|---|---|---|---|")
        for x in rows:
            print(f"| {x['name']} | {x['role']} | {x['today']:+.2f}% | {x['d5']:+.2f}% | "
                  f"{x['d20']:+.2f}% | {x['ytd']:+.1f}% | {x['main5']/1e4:+.0f} | "
                  f"{x['streak']}日 | **{x['act']}**({x['score']:+d}) | {x['why']} |")

        alln = [(norm(r)["today"], r.get("name")) for r in recs.values()]
        alln = [(v, n) for v, n in alln if n]
        print("\n领涨：" + "、".join(f"{n} {v:+.2f}%" for v, n in sorted(alln, reverse=True)[:5]))
        print("领跌：" + "、".join(f"{n} {v:+.2f}%" for v, n in sorted(alln)[:3]))

        # ---- 基金（5只标准持仓）----
        funds = qq_quotes(["jj" + c for c in FUNDS])
        frows = []
        print("\n| 基金 | 代码 | 净值 | 日 | 5日 | 20日 | 信号 | 依据 |")
        print("|---|---|---|---|---|---|---|---|")
        for code, (fname, tag, sect_code) in FUNDS.items():
            info = funds.get(code) or {}
            nav = info.get("nav") or 0.0
            hist = nav_history(code, 25)

            def ret(n, hist=hist):
                if len(hist) > n and hist[n][1]:
                    return (hist[0][1] / hist[n][1] - 1) * 100
                return 0.0

            d1 = hist[0][2] if hist else 0.0
            d5, d20 = ret(5), ret(20)
            sect = next((x for x in rows if x["code"] == sect_code), None) if sect_code else None
            if sect:
                act, basis = sect["act"], f"{sect['name']}信号"
            else:
                if d5 > 1 and d20 > 0:
                    act = "加仓"
                elif d5 < -1 and d20 < -3:
                    act = "减仓"
                elif d5 < 0:
                    act = "观察"
                else:
                    act = "持有"
                basis = "净值趋势"
            print(f"| {fname} | {code} | {nav:.4f} | {d1:+.2f}% | {d5:+.2f}% | {d20:+.2f}% | "
                  f"**{act}** | {basis} |")
            frows.append({"code": code, "name": fname, "tag": tag, "nav": nav,
                          "d1": d1, "d5": d5, "d20": d20, "act": act, "basis": basis,
                          "advice": advice({"act": act, "d1": d1, "d5": d5, "d20": d20,
                                            "main5": (sect or {}).get("main5", 0)})})

        print("\n## 今日操作")
        for x in frows:
            tip = {"加仓": "可加仓，定投继续并考虑追加1期",
                   "持有": "持有不动，定投继续",
                   "观察": "暂不新增，定投本期可跳过",
                   "减仓": "减仓1/3，定投暂停",
                   "清仓": "清仓离场，定投终止"}[x["act"]]
            print(f"- **{x['name']}**（{x['code']}）：{tip}（{x['basis']}）")
        if prev_day:
            print(f"\n_对比基准：{prev_day}_")

        if stale and prev_day == day:
            notice = "（重复运行，行情与上次一致）"
        elif non_trading:
            notice = f"（今日休市，数据同 {prev_day}，不生成新快照）"
        else:
            notice = ""
        push = build_push(day, parts, rows, frows, notice)
        with open(os.path.join(DATA, "last_push.txt"), "w", encoding="utf-8") as pf:
            pf.write(push)
        with open(os.path.join(DATA, "last_mail.html"), "w", encoding="utf-8") as hf:
            hf.write(build_html(day, parts, rows, frows, notice))

        log_path = os.path.join(DATA, "daily_log.csv")
        header = ["date", "code", "name", "today", "d5", "d20", "d60", "ytd",
                  "main1_wan", "main5_wan", "streak", "signal", "score"]
        if not non_trading:
            old_rows = []
            if os.path.exists(log_path):
                with open(log_path, encoding="utf-8-sig", newline="") as logf:
                    old_rows = [r for r in csv.reader(logf) if r and r[0] != day and r != header]
            with open(log_path, "w", encoding="utf-8-sig", newline="") as logf:
                w = csv.writer(logf)
                w.writerow(header)
                w.writerows(old_rows)
                for x in rows:
                    w.writerow([day, x["code"], x["name"], f"{x['today']:.2f}", f"{x['d5']:.2f}",
                                f"{x['d20']:.2f}", f"{x['d60']:.2f}", f"{x['ytd']:.1f}",
                                int(x["main1"]), int(x["main5"]), x["streak"], x["act"], x["score"]])

        # 发送门控元数据：只有"交易日 + 数据是新的一天 + 当前不早于16:10"才允许发信
        meta = {"date": day, "ts": now.isoformat(timespec="seconds"),
                "stale": bool(stale), "weekday": now.isoweekday(),
                "trading_day": now.isoweekday() <= 5 and not stale and not non_trading,
                "send_after": "16:10"}
        save_json(os.path.join(DATA, "last_meta.json"), meta)

        if not non_trading:
            save_json(os.path.join(HIST, day.replace("-", "") + suffix + ".json"),
                      {"date": day, "session": "am" if midday else "close",
                       "ts": now.isoformat(timespec="seconds"),
                       "_fp": fp_sum,
                       "_hist": {x["code"]: x["_hist"] for x in rows},
                       "report": {"idx": parts, "notice": notice,
                                  "rows": [{k: x[k] for k in ("code", "name", "role",
                                                              "today", "d5", "d20", "main5",
                                                              "act", "score", "why")}
                                           for x in rows],
                                  "frows": frows},
                       "sectors": {x["code"]: {k: v for k, v in x.items() if k != "_hist"} for x in rows},
                       "funds": {c: {k: v for k, v in (funds.get(c) or {}).items() if k != "name"}
                                 for c in FUNDS}})
        return 0
    finally:
        sys.stdout = tee.out
        tee.close()
        print(f"报告已写入 {md_path}")


if __name__ == "__main__":
    sys.exit(main())
