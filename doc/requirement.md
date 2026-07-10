BeijiaosuoIPO — 需求文档（requirement.md）
1. 项目概述
构建一个自动化程序，每天抓取北京证券交易所（北交所）最新的新股发行数据，提取申购日与上市日，生成标准 .ics 日历文件。通过 GitHub Actions 定时运行、GitHub Pages 托管，供 iPhone 日历和 Google 日历订阅，实现打新日程的自动提醒。

目标仓库：https://github.com/jhang3321/BeijiaosuoIPO.git
运行方式：GitHub Actions 定时任务（无需本地服务器常开）
托管方式：GitHub Pages（提供稳定订阅 URL）

2. 数据源（已实测验证）
2.1 接口地址
https://www.bseinfo.net/newShareController/infoResult.do
2.2 请求方式
GET 请求，参数：
参数值说明callbackcbJSONP 回调名，可任意page从 0 开始的页码见 2.5 分页方向pageSize20每页条数
2.3 必需请求头
User-Agent: Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36
Referer: https://www.bseinfo.net/newshare/listofissues.html
2.4 返回格式（JSONP）
返回内容是 JSONP，即 JSON 外包一层回调函数：cb([{...}])。必须先用正则剥离外壳再解析。

剥离正则：^[^(]*\((.*)\)\s*$，配合 re.S（单行模式）
剥离后用 json.loads 解析

剥离后的结构：
[
  {
    "listInfo": {
      "content": [ {单条新股记录}, ... ],
      "totalPages": 17,
      "totalElements": 334,
      "number": 当前页码,
      ...
    }
  }
]
2.5 分页方向（关键）
数据按时间升序排列：page=0 是最早的历史新股，最新的新股在最后一页（totalPages - 1）。
因此抓取最新数据的流程为：先请求 page=0 读取 totalPages，再请求最后一页，取其 content 中最后 10 条（时间上最新的 10 只新股）。
3. 字段映射（已实测，直接使用这些字段名）
单条新股记录中需要用到的字段：
字段名含义示例备注stockName股票名称乔路铭stockCode代码874075新三板原始代码，上市后交易代码变为 920 开头；仅作备注purchaseDate申购日日期对象核心字段enterPremiumDate上市日日期对象核心字段，北交所对上市日的命名，已确认正确issuePrice发行价14.36数字peRatio发行市盈率14.99数字initialIssueAmount初始发行量（股）22460000整数
3.1 日期字段格式
日期字段不是字符串，而是对象，形如：
json{ "time": 1751817600000, "year": 126, "month": 6, "date": 7, ... }

取 time（毫秒时间戳）转换：datetime.fromtimestamp(time / 1000).date()
字段可能为 null（如上市日未定），必须判空处理

4. 功能需求
4.1 抓取范围
只抓取最新的 10 条新股记录。读取 totalPages 后请求最后一页（pageSize=20），取返回 content 的最后 10 条。不抓取全部历史数据。
4.2 生成 .ics 日历
使用 icalendar 库，为每只新股生成两个全天事件：
申购日事件

标题：🔔申购 {stockName}({stockCode})
日期：purchaseDate
备注内容包含：

代码
发行价
发行市盈率
估算顶格资金 = initialIssueAmount × 0.05 × issuePrice（单账户申购上限约为初始发行量的 5%），以万元为单位显示
提示文案："申购时段 8:35-15:00，资金需提前全额到位冻结"


提醒：前一天晚上（提前约 13 小时）

上市日事件

标题：📈上市 {stockName}({stockCode})
日期：enterPremiumDate
备注内容包含：代码、策略提示"首日分批卖出、尾盘清仓"
提醒：当天早上（提前约 1.5 小时）

通用规则

日期字段为 null 的事件自动跳过，不报错
每个事件使用稳定 UID（基于"标题 + 日期"做哈希），保证重复运行不产生重复事件

4.3 日历元数据

日历名称：北交所打新日历
时区：Asia/Shanghai

4.4 输出

生成 bse_ipo_calendar.ics 到仓库根目录
运行时在控制台打印抓到的 10 只新股清单（名称、代码、申购日、上市日）供核对

4.5 健壮性

网络请求设置超时（建议 15 秒）与异常捕获
JSONP 剥离失败、字段缺失、日期为空等情况均需优雅处理，不能导致程序崩溃
接口异常时输出清晰的错误信息

5. 技术栈与约束

Python 3.12
依赖仅使用 requests 与 icalendar（保持轻量）
代码结构清晰，函数分离：抓取 / JSONP 解析 / 日期转换 / 事件生成 / 主流程
添加中文注释
禁止使用浏览器自动化（如 Selenium）；纯 HTTP 请求即可

6. GitHub Actions 需求
创建 .github/workflows/update.yml：

触发条件：

定时：cron: '30 23 * * *'（UTC 23:30 = 北京时间次日 07:30）
手动：支持 workflow_dispatch


权限：contents: write
步骤：

checkout 仓库
安装 Python 3.12
pip install requests icalendar
运行 bse_ipo_calendar.py
若 bse_ipo_calendar.ics 有变化则 commit & push；无变化则跳过（避免空提交）



7. 文档需求（README.md）
需包含：

项目用途与数据源说明
推送到 https://github.com/jhang3321/BeijiaosuoIPO.git 的操作步骤
在仓库 Settings 开启 GitHub Pages（main 分支 / root）的步骤
生成的订阅地址：https://jhang3321.github.io/BeijiaosuoIPO/bse_ipo_calendar.ics
iPhone 订阅步骤：设置 → 日历 → 账户 → 添加账户 → 其他 → 添加已订阅的日历 → 粘贴地址
Google 日历订阅步骤：其他日历 → 从网址 → 粘贴地址（注明 Google 刷新较慢，iPhone 体验更好）
脚本可调参数说明

8. 交付物清单
bse_ipo_calendar.py            主脚本
.github/workflows/update.yml   定时任务配置
README.md                      部署与订阅说明
requirement.md                 本需求文档
.gitignore                     忽略 __pycache__ 等
9. 验收标准

本地运行 python bse_ipo_calendar.py 能成功抓取到最新 10 只新股并生成 bse_ipo_calendar.ics
生成的 .ics 可被 icalendar 反向解析，事件数量正确（≤ 20 个，每只新股最多 2 个事件）
控制台正确打印 10 只新股的名称、代码、申购日、上市日
上市日为空的新股，其上市事件被跳过、程序不报错
推送到 GitHub 后，手动触发 Actions 能成功运行并提交更新后的 .ics
开启 Pages 后，订阅地址可正常访问并被 iPhone 日历成功订阅

10. 实现提示（避坑要点）
以下细节均已实测确认，实现时直接采用，无需重新摸索：

接口返回是 JSONP，必须剥壳后再解析
分页是升序，最新数据在最后一页，不是第一页
上市日字段名是 enterPremiumDate（不直觉但正确），不是 listingDate 等
日期是时间戳对象（取 time 字段），不是日期字符串
stockCode 是新三板原始代码，与上市后 920 交易代码不同，仅作备注用途
部分记录的日期字段可能为 null，务必判空