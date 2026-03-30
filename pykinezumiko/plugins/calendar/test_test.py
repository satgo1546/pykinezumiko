import datetime
import re
import subprocess

import pytest
from hypothesis import given
from hypothesis import strategies as st

from . import Calendar, gregorian_to_chinese, next_jieqi, previous_jieqi


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


def test_previous_jieqi():
    # 此处采用的是香港天文台提供的日历数据。
    assert previous_jieqi(1901, 1, 6) == (1901, 1, 6, "小寒")
    assert previous_jieqi(2100, 12, 22) == (2100, 12, 22, "冬至")

    assert previous_jieqi(1919, 8, 10) == (1919, 8, 8, "立秋")
    assert previous_jieqi(2001, 1, 4) == (2000, 12, 21, "冬至")

    assert previous_jieqi(2021, 12, 22) == (2021, 12, 21, "冬至")
    assert previous_jieqi(2051, 3, 21) == (2051, 3, 20, "春分")


def test_next_jieqi():
    assert next_jieqi(1901, 1, 6) == (1901, 1, 6, "小寒")
    assert next_jieqi(2100, 12, 22) == (2100, 12, 22, "冬至")

    assert next_jieqi(1919, 8, 10) == (1919, 8, 24, "处暑")
    assert next_jieqi(2000, 12, 22) == (2001, 1, 5, "小寒")

    assert next_jieqi(1979, 1, 20) == (1979, 1, 21, "大寒")
    assert next_jieqi(2083, 2, 1) == (2083, 2, 3, "立春")
    assert next_jieqi(2084, 3, 15) == (2084, 3, 19, "春分")


@given(st.dates(min_value=datetime.date(1901, 1, 6), max_value=datetime.date(2100, 12, 22)))
def test_jieqi_properties(t: datetime.date):
    y, m, d, name = previous_jieqi(t.year, t.month, t.day)
    assert 0 <= (t - datetime.date(y, m, d)).days <= 16
    assert re.fullmatch(r"[一-鿿]{2}", name)
    assert previous_jieqi(y, m, d) == (y, m, d, name) == next_jieqi(y, m, d)
    y, m, d, name = next_jieqi(t.year, t.month, t.day)
    assert 0 <= (datetime.date(y, m, d) - t).days <= 16
    assert re.fullmatch(r"[一-鿿]{2}", name)
    assert previous_jieqi(y, m, d) == (y, m, d, name) == next_jieqi(y, m, d)


@pytest.mark.parametrize(
    "t",
    [
        datetime.datetime(1919, 8, 10),
        # https://github.com/infinet/lunar-calendar
        # 1979-01-20 大寒
        # 不一致的原因在于上面两处节气及新月正好跨越午夜时分，差距数秒就能影响该节气或新月的发生日期。由于使用不同的行星位置计算方法和Delta T估算方法，出现这种差异在所难免。
        datetime.datetime(1979, 1, 20),
        datetime.datetime(2021, 12, 21),
    ],
)
def test_calendar(t, snapshot):
    assert Calendar.calendar(t) == snapshot
