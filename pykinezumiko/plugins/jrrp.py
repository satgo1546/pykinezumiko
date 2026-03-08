import random
import time

from pykinezumiko import Event, on_command


@on_command("123")
def _(event: Event):
    r = random.Random(time.strftime("%j%Y") + str(event.sender))
    return f"[{event.sender}] 的今日人品为 {r.randrange(101)}。"
