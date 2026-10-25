# A股板块雷达 · 部署指南（GitHub Pages，全免费）

目标：得到一个网址 `https://你的用户名.github.io/仓库名/`，每个交易日 16:10 后自动更新，
手机、电脑随时打开；你的电脑关机也不影响。

---

## 第 0 步：注册 GitHub（已注册就跳到第 1 步）

1. 打开 https://github.com/signup
2. 填邮箱（QQ 邮箱可以）→ 设密码 → 起用户名（英文，例如 `zhangsan2026`，它会出现在网址里）
3. 收邮件，输入 8 位验证码
4. 完成后会进入 GitHub 首页

> 用户名一旦确定会出现在网址中，想好再填；后续也能改。

## 第 1 步：新建仓库

1. 右上角 `+` → **New repository**
2. **Repository name** 填：`a-share-radar`（名字随意，建议英文）
3. 选 **Public**（一定要 Public，免费版 Pages 只支持公开仓库）
4. 下面的 `Add a README file` **不要勾**
5. 点 **Create repository**

## 第 2 步：上传文件

### 方式 A（推荐，一次拖进去）

1. 把 `a-share-site.zip` 解压到桌面，得到 `daily.py`、`site_gen.py`、`site`、`data`、`reports`、
   `.github` 等文件/文件夹
2. 在仓库首页点 **Add file → Upload files**
3. 打开解压后的文件夹，**全选里面的所有内容**（Ctrl+A），拖到网页的上传区域
4. 等进度条走完（约 20 个文件，1 分钟内）
5. 页面下方 Commit changes 直接点 **Commit changes**

> 若 `.github` 文件夹没被上传（有些浏览器会忽略隐藏文件夹），用方式 B 单独补这个文件。

### 方式 B（补 `.github/workflows/daily.yml`）

1. 仓库首页 **Add file → Create new file**
2. 文件名框输入：`.github/workflows/daily.yml`（斜杠会自动建目录）
3. 把压缩包里的 `.github/workflows/daily.yml` 内容整段粘贴进去
4. 点 **Commit changes**

## 第 3 步：启用 Actions（自动更新的引擎）

1. 仓库顶部点 **Actions** 标签
2. 若出现提示，点 **I understand my workflows, go ahead and enable them**
3. 左侧点 **daily-market** → 右侧 **Enable workflow**（若有）
4. 点 **Run workflow** → 绿色按钮 **Run workflow** 手动跑一次
5. 等 1–2 分钟刷新，看到绿色 ✅ 就说明抓数、生成网页、提交全部成功

> 失败（红色 ❌）：点进去看日志，把报错那几行发我，我换方案（备用：Cloudflare，同样免费）。

## 第 4 步：开启网页（Pages）

1. 仓库顶部 **Settings**
2. 左侧栏找到 **Pages**
3. **Source** 选 **Deploy from a branch**
4. **Branch** 选 `main`，右边文件夹选 **/site**，点 **Save**
5. 等 1–2 分钟，页面上方出现：
   `Your site is live at https://你的用户名.github.io/a-share-radar/`
6. 点 **Visit site** 打开

## 第 5 步：手机使用

1. 手机上用浏览器打开那个网址
2. 微信里也能直接点开（可以发给自己）
3. iPhone Safari：底部分享 → **添加到主屏幕**；安卓 Chrome：右上菜单 → **添加到主屏幕**
   之后像 App 一样点开即可

---

## 之后会发生什么

- 每个交易日北京时间 16:10 和 16:45 各自动跑一次（脚本自身去重，同一天数据不会重复提交）
- 页面顶部显示"最新交易日"；周末/节假日不更新，页面上仍保留上一交易日的数据
- 若当天抓数失败：页面保持旧数据，不会出现空白或错误数字

## 常见问题

**Q：会不会产生费用？**
不会。公开仓库的 Actions 不限时长、Pages 托管与 HTTPS 全部免费。

**Q：会不会泄露隐私？**
不会。仓库里只有公开行情数据、脚本和生成的网页，没有任何账号信息。
（本机 `mail_config.json` 含邮箱授权码，已在 `.gitignore` 中，不会上传。）

**Q：抓数失败怎么办？**
先看 Actions 日志里的报错。若长期连不上腾讯接口（GitHub 服务器在境外），
可换成 Cloudflare 方案（同样免费），或改由东财接口取数。

**Q：想改板块/基金怎么办？**
编辑 `daily.py` 里的 `WATCH`（板块）和 `FUNDS`（基金）两个列表即可，改完提交，
下一次运行自动生效。
