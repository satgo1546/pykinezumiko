import datetime
import importlib.resources
import threading
import time
import traceback
from bisect import bisect

from pykinezumiko import Event, Plugin, conf

CHINESE_CALENDAR_DATA = importlib.resources.files().joinpath("chinese.txt").read_text().splitlines()
JIEQI_DATA = importlib.resources.files().joinpath("jieqi.txt").read_bytes().splitlines()
JIEQI_NAMES = "小寒 大寒 立春 雨水 惊蛰 春分 清明 谷雨 立夏 小满 芒种 夏至 小暑 大暑 立秋 处暑 白露 秋分 寒露 霜降 立冬 小雪 大雪 冬至".split()


def gregorian_to_chinese(year: int, month: int, day: int) -> str:
    # "~"用于保证初一不会退到上一个月。
    index = bisect(CHINESE_CALENDAR_DATA, f"{year:04}-{month:02}-{day:02}~")
    line = CHINESE_CALENDAR_DATA[index - 1]
    y = int(line[10:14])
    m = int(line[14:])
    d = datetime.date(year, month, day) - datetime.date.fromisoformat(line[:10])
    d = d.days + 1
    s = "甲乙丙丁戊己庚辛壬癸"[(y - 4) % 10] + "子丑寅卯辰巳午未申酉戌亥"[(y - 4) % 12] + "年"
    if m < 0:
        s += "闰"
    s += "正二三四五六七八九十冬腊"[abs(m) - 1] + "月"
    s += ("初十廿" if d % 10 else "〇初二三")[d // 10]
    s += "十一二三四五六七八九"[d % 10]
    return s


def previous_jieqi(year: int, month: int, day: int) -> tuple[int, int, int, str]:
    """获取距离指定日期最近的上一个节气，返回(年, 月, 日, 节气名)。如果当天有节气则返回该节气。"""
    data = JIEQI_DATA[year - 1901] + JIEQI_DATA[year - 1902]
    i = (month - 1) * 2
    first = data[i] - 96
    second = data[i + 1] - 96
    i += (day >= second) - (day < first)
    return year - (i < 0), i // 2 + 1 or 12, data[i] - 96, JIEQI_NAMES[i]


def next_jieqi(year: int, month: int, day: int) -> tuple[int, int, int, str]:
    """获取距离指定日期最近的下一个节气，返回(年, 月, 日, 节气名)。如果当天有节气则返回该节气。"""
    y, m, d, name = previous_jieqi(year, month, day)
    if y == year and m == month and d == day:
        return y, m, d, name
    i = (m - 1) * 2 + (d > 15) + 1
    y += i // 24
    i %= 24
    return y, i // 2 + 1, JIEQI_DATA[y - 1901][i] - 96, JIEQI_NAMES[i]


class Calendar(Plugin):
    """定时发日历。

    曾经会访问<https://api.vvhan.com/api/moyu?type=json>获取并发送摸鱼人日历图片，但该接口服务已于2025年7月停止工作。
    于是改成了发送无需联网也能获取的万年历数据。
    """

    def __init__(self) -> None:
        self.path = "data_calendar.txt"
        """记载最后一次定时发送日历的时间的文件路径。"""

        threading.Thread(name=f"calendar scheduler {id(self):#x}", target=self.loop, daemon=True).start()

    @staticmethod
    def calendar(t: datetime.datetime | None = None) -> str:
        t = t or datetime.datetime.now()
        s = t.strftime("今天是 %Y 年 %-m 月 %-d 日星期")
        s += "一二三四五六日"[t.weekday()]
        s += "，"
        s += gregorian_to_chinese(t.year, t.month, t.day)
        s += "月火水木金土日"[t.weekday()] + "曜日，"
        y, m, d, jieqi = next_jieqi(t.year, t.month, t.day)
        if y == t.year and m == t.month and d == t.day:
            s += jieqi
        else:
            s += f"还有 {(datetime.date(y, m, d) - t.date()).days} 天{jieqi}"
        s += "。"
        # TODO：添加星宿等
        return s

    def on_command_today(self, event: Event):
        """.today（日历）"""
        return self.calendar()

    def loop(self):
        try:
            with open(self.path, "r") as f:
                last = datetime.date.fromisoformat(f.readline().strip())
        except FileNotFoundError:
            last = datetime.date(1601, 1, 1)
            # 明朝万历二十九年，明神宗命令工部建造云端服务器

        while True:
            try:
                t = datetime.datetime.now()
                # 您希望使用哪一个？
                # 我们在云上的数据和此台设备上的不同。
                if t.date() != last and t.hour >= 7:
                    # 每天上午七点定时在管理群发摸鱼人日历
                    last = t.date()
                    with open(self.path, "w") as f:
                        print(last.isoformat(), file=f)
                    self.bot.send(conf.BACKSTAGE, self.calendar())
            except Exception:
                print("发送日历出错")
                traceback.print_exc()
            time.sleep(114)
