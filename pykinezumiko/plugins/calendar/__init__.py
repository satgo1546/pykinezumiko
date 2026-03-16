import datetime
import importlib.resources
import threading
import time
import traceback
from bisect import bisect

from pykinezumiko import Event, Plugin, conf

chinese_calendar_data = importlib.resources.files().joinpath("chinese.txt").read_text().splitlines()


def gregorian_to_chinese(year: int, month: int, day: int) -> str:
    # "~"用于保证初一不会退到上一个月。
    index = bisect(chinese_calendar_data, f"{year:04}-{month:02}-{day:02}~")
    line = chinese_calendar_data[index - 1]
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


class Calendar(Plugin):
    """定时发日历。

    曾经会访问<https://api.vvhan.com/api/moyu?type=json>获取并发送摸鱼人日历图片，但该接口服务已于2025年7月停止工作。
    于是改成了发送无需联网也能获取的万年历数据。
    """

    def __init__(self) -> None:
        self.path = "data_calendar.txt"
        """记载最后一次定时发送日历的时间的文件路径。"""

        thread = threading.Thread(name=f"calendar scheduler {id(self):#x}", target=self.loop)
        thread.daemon = True
        thread.start()

    @staticmethod
    def calendar(t: datetime.datetime = datetime.datetime.now()) -> str:
        s = t.strftime("今天是 %Y 年 %-m 月 %-d 日星期")
        s += "日一二三四五六"[t.weekday()]
        s += "，"
        s += gregorian_to_chinese(t.year, t.month, t.day)
        s += "日月火水木金土"[t.weekday()] + "曜日。"
        # TODO：添加节气、星宿等
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
                if t.date() != last and t.hour > 7:
                    # 每天上午七点定时在管理群发摸鱼人日历
                    last = t.date()
                    with open(self.path, "w") as f:
                        print(last.isoformat(), file=f)
                    self.bot.send(conf.BACKSTAGE, self.calendar())
            except Exception:
                print("发送日历出错")
                traceback.print_exc()
            time.sleep(114)
