import bisect
import pickle
import re
import threading
import time
from typing import NoReturn

from pykinezumiko import Event, Plugin
from pykinezumiko.humanity import CommandSyntaxError, format_timespan


class Clock(Plugin):
    q: list[tuple[float, int, str]]
    """提醒队列。

    按时间从早到晚排序。
    条目格式：(浮点触发时间戳, 上下文, 回复内容)。
    """

    def __init__(self) -> None:
        self.path = "data_clock.pickle"
        """提醒队列文件路径。"""

        try:
            with open(self.path, "rb") as f:
                self.q = pickle.load(f)
        except FileNotFoundError:
            self.q = []

        for t, c, s in self.q:
            assert isinstance(t, float) and isinstance(c, int) and isinstance(s, str), "提醒队列文件数据类型错误"
        self.q.sort()

        thread = threading.Thread(name=f"clock scheduler {id(self):#x}", target=self.loop)
        thread.daemon = True
        thread.start()

    def on_command_clock(self, event: Event):
        """.clock ⟨秒后⟩ [注释]（定时器·计划任务）
        定时器和计划任务。不保证精确，服务器的变故还可能使任务消失。
        """
        # 【前世的记忆】
        # 支持掷骰表达式。
        # 使用下列额外表达式计算时长：
        # ‣ ◊day
        # ‣ ◊hour
        # ‣ ◊minute
        # ‣ ◊second
        if not event.text:
            raise CommandSyntaxError()
        # 匹配开头和结尾作为时间输入
        match = re.search(r"^\d+|\d+$", event.text)
        if not match:
            return "无法识别到有效时间。"
        t = int(match.group())
        if not t:
            return "？"
        if t >= 1000000000:
            return "木鼠子的一生可能也没有这样长吧。"
        if t >= 100000000:
            return "#{format_timespan(t)}对于木鼠子来说太长了。"
        title = event.text[: match.start()] + event.text[match.end() :].strip()
        if t > 600:
            bisect.insort(self.q, (time.time() + t, event.context, title))
            with open(self.path, "wb") as f:
                pickle.dump(self.q, f)
            return f"计划任务 [{title}] 于 {format_timespan(t).removesuffix(' 0 秒')}后。"
        else:
            self.bot.send(event.context, f"定时器将在 {format_timespan(t)}后响铃。")
            time.sleep(t)
            return "定时器时间到" + ("：\n‣ " + title if title else "。")

    def loop(self) -> NoReturn:
        while True:
            # 如果提醒队列非空且第一个提醒到时间了就提醒用户
            while self.q and self.q[0][0] < time.time():
                _, target, title = self.q.pop(0)
                with open(self.path, "wb") as f:
                    pickle.dump(self.q, f)
                self.bot.send(target, f"现在有下列计划任务。\n‣ {title}")
                time.sleep(1)
            time.sleep(60)
