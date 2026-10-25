"""把 data/last_push.txt 通过 QQ 邮箱 SMTP 发到指定邮箱。
用法：
  python send_mail.py            # 发送当日收盘推送
  python send_mail.py --test     # 发送一封"你好"测试邮件
  python send_mail.py --dry      # 只打印将要发送的内容，不连网
配置文件：mail_config.json（与脚本同目录）
  {"user": "xxx@qq.com", "auth_code": "SMTP授权码", "to": "收件邮箱",
   "smtp_host": "smtp.qq.com", "smtp_port": 465}
"""
import datetime
import json
import os
import smtplib
import ssl
import sys
import time
from email.header import Header
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formataddr, formatdate

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
CFG_PATH = os.path.join(HERE, "mail_config.json")
PUSH_PATH = os.path.join(DATA, "last_push.txt")
HTML_PATH = os.path.join(DATA, "last_mail.html")
META_PATH = os.path.join(DATA, "last_meta.json")
SENT_PATH = os.path.join(DATA, "sent_days.txt")

SEND_AFTER = "16:10"  # 早于此时段不发（当日收盘数据尚未最终稳定）


def gate(force=False):
    """返回 (是否允许发送, 原因)。规则：
    1) 只发当天数据（meta.date == 今天），跨日不补发；
    2) 只发交易日且数据非重复（stale=False）；
    3) 当前时间不早于 16:10；
    4) 同一天最多一封（sent_days.txt 记录）。
    """
    if force:
        return True, "force"
    bj = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8)))
    today = bj.strftime("%Y-%m-%d")
    if bj.isoweekday() > 5:
        return False, "周末休市，不发送"
    if not os.path.exists(META_PATH):
        return False, "缺少 last_meta.json（先运行 daily.py）"
    with open(META_PATH, encoding="utf-8") as f:
        meta = json.load(f)
    if meta.get("date") != today:
        return False, f"数据日期 {meta.get('date')} 不是今天 {today}，按规则不补发"
    if meta.get("stale") or not meta.get("trading_day"):
        return False, "今日为休市/数据与上一交易日相同，不发送"
    if bj.strftime("%H:%M") < SEND_AFTER:
        return False, f"未到发送时间 {SEND_AFTER}"
    if os.path.exists(SENT_PATH):
        with open(SENT_PATH, encoding="utf-8") as f:
            if today in {ln.strip() for ln in f}:
                return False, f"今天（{today}）已发送过，每天只发一封"
    return True, "ok"


def load_cfg():
    # 优先环境变量（GitHub Actions Secrets 用），其次 mail_config.json
    env = os.environ
    if env.get("MAIL_USER") and env.get("MAIL_AUTH_CODE") and env.get("MAIL_TO"):
        return {"user": env["MAIL_USER"], "auth_code": env["MAIL_AUTH_CODE"],
                "to": env["MAIL_TO"], "smtp_host": env.get("MAIL_HOST", "smtp.qq.com"),
                "smtp_port": int(env.get("MAIL_PORT", "465"))}
    if not os.path.exists(CFG_PATH):
        return None
    try:
        with open(CFG_PATH, encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"[配置读取失败] {e}")
        return None


def build_msg(cfg, subject, body, html=None):
    if html:
        msg = MIMEMultipart("alternative")
        msg.attach(MIMEText(body, "plain", "utf-8"))
        msg.attach(MIMEText(html, "html", "utf-8"))
    else:
        msg = MIMEText(body, "plain", "utf-8")
    msg["Subject"] = Header(subject, "utf-8")
    msg["From"] = formataddr((str(Header("A股收盘", "utf-8")), cfg["user"]))
    msg["To"] = cfg["to"]
    msg["Date"] = formatdate(localtime=True)
    return msg


def send(cfg, subject, body, html=None):
    host = cfg.get("smtp_host", "smtp.qq.com")
    port = int(cfg.get("smtp_port", 465))
    ctx = ssl.create_default_context()
    if port == 465:
        srv = smtplib.SMTP_SSL(host, port, timeout=30, context=ctx)
    else:
        srv = smtplib.SMTP(host, port, timeout=30)
        srv.starttls(context=ctx)
    try:
        srv.login(cfg["user"], cfg["auth_code"])
        srv.sendmail(cfg["user"], [cfg["to"]],
                     build_msg(cfg, subject, body, html).as_string())
    finally:
        try:
            srv.quit()
        except Exception:
            pass


def main():
    args = set(sys.argv[1:])
    html = None
    if "--test" in args:
        body = ("你好。\n\n"
                "这是 A股板块每日收盘分析 的邮件通道测试。\n"
                "收到这封邮件，说明 SMTP 配置可用；之后每个交易日 15:40 左右会收到当日推送。\n"
                "（休市日与非交易日不发送。）\n\n"
                f"发送时间：{time.strftime('%Y-%m-%d %H:%M:%S')}")
        subject = "【测试】A股收盘推送通道 · 你好"
    else:
        if not os.path.exists(PUSH_PATH):
            print("[无内容] data/last_push.txt 不存在，请先运行 daily.py")
            return 1
        with open(PUSH_PATH, encoding="utf-8") as f:
            body = f.read().strip()
        if not body:
            print("[无内容] last_push.txt 为空")
            return 1
        if os.path.exists(HTML_PATH):
            with open(HTML_PATH, encoding="utf-8") as f:
                html = f.read().strip() or None
        subject = "A股收盘 " + time.strftime("%m-%d") + "｜板块信号与基金操作"

    cfg = load_cfg()
    if not cfg:
        print("[缺配置] 请先在 E:\\DSH-workingplace\\mail_config.json 填写 user / auth_code / to")
        return 2
    for k in ("user", "auth_code", "to"):
        if not cfg.get(k) or "填" in str(cfg.get(k)):
            print(f"[缺配置] mail_config.json 的 {k} 未填写")
            return 2

    if "--dry" in args:
        print("----- 收件人:", cfg["to"])
        print("----- 主题:", subject)
        print("----- 正文(纯文本) -----")
        print(body)
        if html:
            print("----- HTML 已附带", len(html), "字节 -----")
        return 0

    ok, why = gate(force="--force" in args or "--test" in args)
    if not ok:
        print(f"[跳过] {why}")
        return 0
    try:
        send(cfg, subject, body, html)
        if "--test" not in args:
            with open(SENT_PATH, "a", encoding="utf-8") as f:
                f.write(time.strftime("%Y-%m-%d") + "\n")
        print(f"[OK] 已发送 -> {cfg['to']}  ({time.strftime('%H:%M:%S')})"
              + ("  [HTML]" if html else ""))
        return 0
    except Exception as e:
        print(f"[失败] {type(e).__name__}: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
