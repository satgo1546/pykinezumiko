import time
import pickle
import requests

from .. import ChatbotBehavior, conf


def stamp2day(stamp: float, time_zone: int) -> int:
    return int(stamp // 3600 + time_zone) // 24


def stamp2hour(stamp: float, time_zone: int) -> int:
    return int(stamp // 3600 + time_zone) % 24


class TouchFish(ChatbotBehavior):
    """定时发摸鱼人日历"""

    def __init__(self) -> None:
        super().__init__()
        # 存储路径
        self.path = "logs/20touchfish.pickle"

    def touch_fish(self, sender: int) -> None:
        r = requests.get("https://api.vvhan.com/api/moyu?type=json", timeout=3)
        print()
        # 请求摸鱼人日历API
        self.send(
            sender,
            f"{r.json()['url']}",
        )

    def on_message(self, context: int, sender: int, text: str, message_id: int):
        if text.startswith(".touchfish"):
            self.touch_fish(sender)

    def on_interval(self):
        stp = time.time()
        with open(self.path, "rb") as f:
            last = pickle.load(f)

        # 每天上午七点定时在管理群发摸鱼人日历
        if stamp2day(stp, 8) != last and stamp2hour(stp, 8) > 7:
            self.touch_fish(conf.INTERIOR)
            # 标记当前日期
            with open(self.path, "wb") as f:
                pickle.dump(stamp2day(stp, 8), f)
        pass
