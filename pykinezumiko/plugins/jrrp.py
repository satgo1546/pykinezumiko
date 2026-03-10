import random
import time

from pykinezumiko import Event, Plugin


class 今日人品(Plugin):
    def on_command_jrrp(self, event: Event):
        name = self.bot.name(event.context, event.sender)
        r = random.Random(time.strftime("%j%Y") + name)
        return f"[{name}] 的今日人品为 {r.randrange(101)}。"
