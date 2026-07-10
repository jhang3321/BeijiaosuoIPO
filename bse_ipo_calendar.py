#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
北交所打新日历生成脚本

抓取北京证券交易所（北交所）最新 10 只新股的申购日与上市日，
生成标准 .ics 日历文件，供 iPhone / Google 日历订阅，实现打新日程自动提醒。

数据源：https://www.bseinfo.net/newShareController/infoResult.do （JSONP 接口）
依赖：requests、icalendar
"""

import re
import sys
import json
import hashlib
from datetime import datetime, date, time, timedelta
from zoneinfo import ZoneInfo

import requests
from icalendar import Calendar, Event, Alarm

# ---------------------------------------------------------------------------
# 可调参数
# ---------------------------------------------------------------------------
API_URL = "https://www.bseinfo.net/newShareController/infoResult.do"
PAGE_SIZE = 20            # 每页条数（接口默认 20）
LATEST_COUNT = 10         # 只保留最新的 N 只新股
TIMEOUT = 15              # 网络请求超时（秒）
OUTPUT_FILE = "bse_ipo_calendar.ics"
CALENDAR_NAME = "北交所打新日历"
TIMEZONE = "Asia/Shanghai"
TZ = ZoneInfo(TIMEZONE)

# 事件显示时段（北京时间）：申购 8:30-9:00，上市 9:30-10:00
PURCHASE_START = time(8, 30)
PURCHASE_END = time(9, 0)
LISTING_START = time(9, 30)
LISTING_END = time(10, 0)

# 顶格资金估算系数：单账户申购上限约为初始发行量的 5%
CAP_RATIO = 0.05

# 必需请求头（缺失会被 CDN 拦截）
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36"
    ),
    "Referer": "https://www.bseinfo.net/newshare/listofissues.html",
}


# ---------------------------------------------------------------------------
# 抓取
# ---------------------------------------------------------------------------
def fetch_page(session: requests.Session, page: int) -> dict:
    """
    请求指定页码，返回剥壳并解析后的 listInfo 字典。

    接口返回是 JSONP（cb([{...}])），且首次请求会被 CDN 以 302 + Set-Cookie
    做一次"cookie 挑战"；使用 requests.Session 可自动携带 cookie 并跟随重定向。
    """
    resp = session.get(
        API_URL,
        params={"callback": "cb", "page": page, "pageSize": PAGE_SIZE},
        timeout=TIMEOUT,
    )
    resp.raise_for_status()
    return parse_jsonp(resp.text)


def parse_jsonp(text: str) -> dict:
    """
    剥离 JSONP 外壳并解析，返回 listInfo 字典。

    剥离正则：^[^(]*\\((.*)\\)\\s*$，配合 re.S（单行模式）匹配跨行内容。
    剥离后的结构为 [ { "listInfo": {...} } ]。
    """
    match = re.match(r"^[^(]*\((.*)\)\s*$", text, re.S)
    if not match:
        raise ValueError("JSONP 剥壳失败：返回内容不符合 cb(...) 格式")

    payload = json.loads(match.group(1))
    if not payload or "listInfo" not in payload[0]:
        raise ValueError("解析失败：返回数据中缺少 listInfo 字段")

    return payload[0]["listInfo"]


def fetch_latest_stocks(session: requests.Session) -> list:
    """
    抓取最新的 LATEST_COUNT 只新股。

    数据按时间升序排列：page=0 为最早的历史新股，最新数据在最后一页
    （totalPages - 1）。因此先读 page=0 拿到 totalPages，再请求最后一页，
    取其 content 的最后 LATEST_COUNT 条。
    """
    first = fetch_page(session, 0)
    total_pages = first.get("totalPages", 1)

    last_page = max(total_pages - 1, 0)
    last = first if last_page == 0 else fetch_page(session, last_page)

    content = last.get("content", []) or []
    return content[-LATEST_COUNT:]


# ---------------------------------------------------------------------------
# 日期转换
# ---------------------------------------------------------------------------
def to_date(field) -> date | None:
    """
    将接口的日期对象转换为 date。

    日期字段是对象（形如 {"time": 1751817600000, ...}），取 time（毫秒时间戳）
    转换。字段可能为 null（如上市日未定），返回 None 由调用方跳过。
    """
    if not field or not isinstance(field, dict):
        return None
    ts = field.get("time")
    if ts is None:
        return None
    try:
        return datetime.fromtimestamp(ts / 1000).date()
    except (ValueError, OSError, TypeError):
        return None


# ---------------------------------------------------------------------------
# 事件生成
# ---------------------------------------------------------------------------
def make_uid(title: str, day: date) -> str:
    """基于"标题 + 日期"生成稳定 UID，保证重复运行不产生重复事件。"""
    digest = hashlib.md5(f"{title}|{day.isoformat()}".encode("utf-8")).hexdigest()
    return f"{digest}@bse-ipo-calendar"


def _fmt_num(value) -> str:
    """安全格式化数字字段，缺失时返回占位符。"""
    return "—" if value is None else str(value)


def build_purchase_event(stock: dict, day: date) -> Event:
    """构建申购日全天事件（提醒：前一天晚上，提前约 13 小时）。"""
    name = stock.get("stockName", "未知")
    code = stock.get("stockCode", "")
    price = stock.get("issuePrice")
    pe = stock.get("peRatio")
    amount = stock.get("initialIssueAmount")

    # 估算顶格资金 = 初始发行量 × 5% × 发行价，换算为万元
    cap_text = "—"
    if amount is not None and price is not None:
        try:
            cap_wan = float(amount) * CAP_RATIO * float(price) / 10000
            cap_text = f"约 {cap_wan:.2f} 万元"
        except (TypeError, ValueError):
            pass

    title = f"🔔申购 {name}({code})"
    desc = (
        f"代码：{code}\n"
        f"发行价：{_fmt_num(price)} 元\n"
        f"发行市盈率：{_fmt_num(pe)}\n"
        f"估算顶格资金：{cap_text}\n"
        f"申购时段 8:35-15:00，资金需提前全额到位冻结"
    )

    start = datetime.combine(day, PURCHASE_START, tzinfo=TZ)
    end = datetime.combine(day, PURCHASE_END, tzinfo=TZ)
    event = _new_timed_event(title, start, end, desc)
    # 提醒：前一天晚上（申购当日 8:30 往前 13 小时 = 前一天 19:30）
    _add_alarm(event, timedelta(hours=-13), f"明日申购 {name}")
    return event


def build_listing_event(stock: dict, day: date) -> Event:
    """构建上市日全天事件（提醒：当天早上，提前约 1.5 小时）。"""
    name = stock.get("stockName", "未知")
    code = stock.get("stockCode", "")

    title = f"📈上市 {name}({code})"
    desc = f"代码：{code}\n策略提示：首日分批卖出、尾盘清仓"

    start = datetime.combine(day, LISTING_START, tzinfo=TZ)
    end = datetime.combine(day, LISTING_END, tzinfo=TZ)
    event = _new_timed_event(title, start, end, desc)
    # 提醒：当天早上（上市当日 9:30 往前 1.5 小时 = 当天 8:00）
    _add_alarm(event, timedelta(hours=-1, minutes=-30), f"今日上市 {name}")
    return event


def _new_timed_event(title: str, start: datetime, end: datetime, desc: str) -> Event:
    """创建一个定时事件（DTSTART/DTEND 为带时区的 datetime）。"""
    event = Event()
    event.add("uid", make_uid(title, start.date()))
    event.add("summary", title)
    event.add("description", desc)
    event.add("dtstart", start)             # 带 tzinfo 的 datetime => 定时事件
    event.add("dtend", end)
    event.add("transp", "OPAQUE")
    return event


def _add_alarm(event: Event, trigger: timedelta, text: str) -> None:
    """为事件添加相对提醒。"""
    alarm = Alarm()
    alarm.add("action", "DISPLAY")
    alarm.add("description", text)
    alarm.add("trigger", trigger)
    event.add_component(alarm)


# ---------------------------------------------------------------------------
# 主流程
# ---------------------------------------------------------------------------
def build_calendar(stocks: list) -> Calendar:
    """根据新股列表生成日历对象。"""
    cal = Calendar()
    cal.add("prodid", "-//BeijiaosuoIPO//bse_ipo_calendar//CN")
    cal.add("version", "2.0")
    cal.add("x-wr-calname", CALENDAR_NAME)
    cal.add("x-wr-timezone", TIMEZONE)
    cal.add("calscale", "GREGORIAN")

    for stock in stocks:
        purchase_day = to_date(stock.get("purchaseDate"))
        listing_day = to_date(stock.get("enterPremiumDate"))

        # 日期为 null 的事件自动跳过，不报错
        if purchase_day:
            cal.add_component(build_purchase_event(stock, purchase_day))
        if listing_day:
            cal.add_component(build_listing_event(stock, listing_day))

    # 补齐 VTIMEZONE 组件，保证各日历客户端正确解析时区
    cal.add_missing_timezones()
    return cal


def print_summary(stocks: list) -> None:
    """在控制台打印抓到的新股清单供核对。"""
    print(f"共抓取 {len(stocks)} 只最新新股：")
    print(f"{'名称':<10}{'代码':<10}{'申购日':<14}{'上市日':<14}")
    for stock in stocks:
        name = stock.get("stockName", "未知")
        code = stock.get("stockCode", "")
        pd = to_date(stock.get("purchaseDate"))
        ld = to_date(stock.get("enterPremiumDate"))
        pd_s = pd.isoformat() if pd else "—"
        ld_s = ld.isoformat() if ld else "—"
        print(f"{name:<10}{code:<10}{pd_s:<14}{ld_s:<14}")


def main() -> int:
    session = requests.Session()
    session.headers.update(HEADERS)

    try:
        stocks = fetch_latest_stocks(session)
    except requests.RequestException as exc:
        print(f"[错误] 网络请求失败：{exc}", file=sys.stderr)
        return 1
    except (ValueError, json.JSONDecodeError) as exc:
        print(f"[错误] 数据解析失败：{exc}", file=sys.stderr)
        return 1

    if not stocks:
        print("[错误] 未抓取到任何新股数据", file=sys.stderr)
        return 1

    print_summary(stocks)

    cal = build_calendar(stocks)
    with open(OUTPUT_FILE, "wb") as fp:
        fp.write(cal.to_ical())

    event_count = len(cal.walk("VEVENT"))
    print(f"\n已生成 {OUTPUT_FILE}，共 {event_count} 个事件。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
