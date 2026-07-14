# BeijiaosuoIPO — 北交所打新日历

自动抓取**北京证券交易所（北交所）**最新新股发行数据，提取申购日与上市日，生成标准 `.ics` 日历文件。通过 GitHub Actions 每天定时运行、GitHub Pages 托管，供 iPhone 日历和 Google 日历订阅，实现打新日程的自动提醒。

## 项目用途

- 📅 自动生成"北交所打新日历"，包含每只新股的**申购**与**上市**两个定时事件（北京时间）
- 🔔 申购事件：**8:30-9:00**，前一晚提醒，备注含发行价、市盈率、估算顶格资金、申购时段说明
- 📈 上市事件：**9:30-10:00**，当天早上提醒，备注含卖出策略提示
- 🤖 GitHub Actions 每天定时更新，无需本地服务器常开

## 数据源

- 接口：`https://www.bseinfo.net/newShareController/infoResult.do`（JSONP）
- 抓取范围：最新 **10** 只新股（数据按时间升序排列，最新数据在最后一页）
- 字段说明：申购日 `purchaseDate`、上市日 `enterPremiumDate`（北交所对上市日的命名）、发行价 `issuePrice`、市盈率 `peRatio`、初始发行量 `initialIssueAmount`

> 日期字段是北京时间 0 点的毫秒时间戳，脚本按 `Asia/Shanghai` 解析——若按运行机器的本地时区（GitHub Actions 为 UTC）解析，会整体偏成前一天。

> `stockCode` 为新三板原始代码（如 `874075`），上市后交易代码变为 `920` 开头，脚本仅将其作为备注展示。

## 本地运行

```bash
pip install requests icalendar
python bse_ipo_calendar.py
```

运行后会在仓库根目录生成 `bse_ipo_calendar.ics`，并在控制台打印抓到的 10 只新股清单（名称、代码、申购日、上市日）供核对。

## 部署到 GitHub

1. 创建远程仓库并推送：

   ```bash
   git init
   git add .
   git commit -m "init: 北交所打新日历"
   git branch -M main
   git remote add origin https://github.com/jhang3321/BeijiaosuoIPO.git
   git push -u origin main
   ```

2. GitHub Actions 会按计划自动运行：
   - 定时：`cron: '30 23 * * *'`（UTC 23:30 = 北京时间次日 07:30）
   - 手动：在仓库 **Actions → 更新北交所打新日历 → Run workflow** 手动触发
   - 仅当 `bse_ipo_calendar.ics` 有变化时才 commit & push，避免空提交

## 开启 GitHub Pages

1. 进入仓库 **Settings → Pages**
2. **Source** 选择 **Deploy from a branch**
3. **Branch** 选择 `main`，目录选择 `/ (root)`，点击 **Save**
4. 稍等片刻，订阅地址即可访问：

   ```
   https://jhang3321.github.io/BeijiaosuoIPO/bse_ipo_calendar.ics
   ```

## 订阅日历

### iPhone

**设置 → 日历 → 账户 → 添加账户 → 其他 → 添加已订阅的日历**，粘贴订阅地址：

```
https://jhang3321.github.io/BeijiaosuoIPO/bse_ipo_calendar.ics
```

### Google 日历

**其他日历 → 从网址（From URL）→** 粘贴上述地址。

> ⚠️ Google 日历对订阅链接的刷新较慢（可能数小时到一天），iPhone 日历刷新更及时、体验更好。

## 可调参数

脚本顶部 `bse_ipo_calendar.py` 中可调整：

| 参数 | 默认值 | 说明 |
| --- | --- | --- |
| `LATEST_COUNT` | `10` | 抓取最新新股数量 |
| `PAGE_SIZE` | `20` | 接口每页条数 |
| `TIMEOUT` | `15` | 网络请求超时（秒） |
| `OUTPUT_FILE` | `bse_ipo_calendar.ics` | 输出文件名 |
| `CALENDAR_NAME` | `北交所打新日历` | 日历显示名称 |
| `TIMEZONE` | `Asia/Shanghai` | 日历时区 |
| `PURCHASE_START` / `PURCHASE_END` | `8:30` / `9:00` | 申购事件显示时段 |
| `LISTING_START` / `LISTING_END` | `9:30` / `10:00` | 上市事件显示时段 |
| `CAP_RATIO` | `0.05` | 顶格资金估算系数（初始发行量的 5%） |

## 交付物

| 文件 | 说明 |
| --- | --- |
| `bse_ipo_calendar.py` | 主脚本 |
| `.github/workflows/update.yml` | 定时任务配置 |
| `README.md` | 部署与订阅说明 |
| `doc/requirement.md` | 需求文档 |
| `.gitignore` | 忽略 `__pycache__` 等 |
