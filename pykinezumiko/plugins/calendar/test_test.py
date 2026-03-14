import datetime
import subprocess

import pytest

from . import Calendar, gregorian_to_chinese


def test_gregorian_to_chinese():
    # 此处采用的是ICU国际化组件提供的日历数据。
    assert gregorian_to_chinese(1900, 1, 31) == "庚子年正月初一"
    assert gregorian_to_chinese(2100, 12, 31) == "庚申年腊月初一"

    assert gregorian_to_chinese(1919, 8, 10) == "己未年七月十五"

    # https://zh.wikipedia.org/zh-cn/2033年问题
    assert gregorian_to_chinese(2033, 12, 22) == "癸丑年闰冬月初一"

    # https://www.weather.gov.hk/tc/gts/time/conversion.htm
    # 由於計算數十年後的月相及節氣時間可能會有數分鐘的誤差，若新月(即農曆初一)或節氣時間很接近午夜零時，「對照表」內相關農曆月份或節氣的日期可能會有一日之差別。這些情況會出現在2057年9月28日、2089年9月4日及2097年8月7日的新月、2021年的冬至、2051年的春分、2083年的立春和2084年的春分。
    assert gregorian_to_chinese(2057, 9, 28) == "丁丑年八月三十"


@pytest.mark.slow()
def test_gregorian_to_chinese_every_day():
    s = ""
    t = datetime.date(1900, 1, 31)
    while t.year <= 2100:
        s += t.isoformat() + gregorian_to_chinese(t.year, t.month, t.day) + "\n"
        t += datetime.timedelta(days=1)

    js = """
const format = new Intl.DateTimeFormat('zh-CN-u-ca-chinese', { dateStyle: 'full' })
for (let t = new Date(Date.UTC(1900, 0, 31)); t.getUTCFullYear() <= 2100; t.setUTCDate(t.getUTCDate() + 1)) {
    console.log(t.toISOString().slice(0, 10) + format.format(t).slice(4, -3))
}
"""
    js = subprocess.check_output(["node", "--eval", js], encoding="utf-8")
    js = js.replace("十一月", "冬月")
    assert s == js


def test_calendar():
    assert (
        Calendar.calendar(datetime.datetime(1919, 8, 10))
        == "今天是 1919 年 8 月 10 日星期六，己未年七月十五土曜日。"
    )
