import time

import httpx

import pykinezumiko


def stamp2day(stamp: float, time_zone: int) -> int:
    return int(stamp // 3600 + time_zone) // 24


def stamp2hour(stamp: float, time_zone: int) -> int:
    return int(stamp // 3600 + time_zone) % 24


class TouchFish(pykinezumiko.Plugin):
    """定时发摸鱼人日历"""

    def __init__(self) -> None:
        # 存储路径
        self.path = "logs/20touchfish.txt"

    def on_command_touch_fish(self, sender: int) -> None:
        r = httpx.get("https://api.vvhan.com/api/moyu?type=json", timeout=3)
        # 请求摸鱼人日历API
        self.bot.send(sender, f"\a<Image {r.json()['url']}>")

    def on_interval(self):
        stp = time.time()
        try:
            with open(self.path, "r") as f:
                last = int(f.readline())
        except FileNotFoundError:
            last = 0

        # 每天上午七点定时在管理群发摸鱼人日历
        if stamp2day(stp, 8) != last and stamp2hour(stp, 8) > 7:
            # 标记当前日期
            with open(self.path, "w") as f:
                print(stamp2day(stp, 8), file=f)
            self.on_command_touch_fish(pykinezumiko.conf.BACKSTAGE)
