import pathlib
import random
import re
import time
from collections.abc import Generator
from typing import override

from pykinezumiko import Event, Plugin, documented, humanity


class Demonstration(Plugin):
    """演示各种功能的插件。"""

    @override
    def on_message(self, event: Event):
        # 可以使用任意字符串判据。（废话。）
        if not event.text.startswith("^") and event.text.endswith("^") or event.text == "More?":
            return "More?"

    def on_command_debug_p(self, event: Event):
        return "你好，世界！"

    def on_command_debug_cat(self, event: Event):
        return random.choice(("喵呜～", "喵！", "喵？", "喵～"))

    def on_command_debug_m(self, event: Event):
        # 不必只回复一条消息。有需要的话，可以向任意会话任意发送消息。
        self.bot.send(event.context, "这是第一条消息。")
        self.bot.send(event.context, "这是第二条消息。")
        return True

    def on_command_debug_t(self, event: Event):
        self.bot.send(event.context, "8 秒后，将被回调。")
        # 在这8秒内，其他命令能否响应？
        time.sleep(8)
        return "被回调。"

    @documented()
    def on_command_猜数字(self, event: Event) -> Generator[str, str, None | bool | str]:
        # 注意观察下列代码与控制台程序有多么相像。
        def number_guessing_in_console() -> None:
            x = random.randint(1, 100)
            guess = input("I've chosen a random integer between 1 and 100.")
            while guess.isnumeric():
                guess = int(guess)
                if guess < x:
                    guess = input("Too small.")
                elif guess > x:
                    guess = input("Too big.")
                else:
                    return print("Right!")
            print(f"Game over. The answer should be {x}.")

        # 转换为对话流程只需要进行以下替换：
        # • input(…) → yield …
        # • print(…) → self.send(context, …)
        # • 以及依惯例，self.send(context, …); return True → return …
        # 这和应用程序与用户界面框架的主从关系近几十年来的反转有关。
        # 实际上，在现代操作系统中，input函数内部的系统调用以类似yield的方式实现。
        x = random.randint(1, 100)
        guess = yield "我从 1～100 中随机选了一个整数。猜对了也没有奖励，猜错了也没有惩罚。"
        while guess.isnumeric():
            guess = int(guess)
            if guess < x:
                guess = yield "太小了。"
            elif guess > x:
                guess = yield "太大了。"
            else:
                return "猜对了！"
        return f"游戏结束。正确答案是 {x}。"

    def on_command_debug_next(self, event: Event):
        n = max(1, int(event.text or "1"))
        if n > 9:
            return "注意，即使 .debug cls 也无法清除待回显的状态。请再考虑一下。"
        text = yield f"将回显接下来的 {n} 条消息。"
        for _ in range(n - 1):
            text = yield text
        return text

    def on_command_debug_repr(self, event: Event):
        return repr((yield "将以 repr 回显接下来的一条消息。"))

    def on_command_debug_face(self, event: Event):
        if match := re.search(r"\a<Emoticon (\d+)>", event.text):
            id = int(match.group(1))
        else:
            id = int(event.text)
        return f"\a<Emoticon {id}> = {id}"

    def on_command_debug_img(self, event: Event):
        raise NotImplementedError()
        uri = pathlib.Path("pykinezumiko/resources/sample.png").resolve().as_uri()
        return f"查看下列图片：\a<Image {uri}>"


class DebugJSON(Plugin):
    """实现.debug json命令的插件。

    由于对话流程只传入木鼠子码格式的消息内容，只能不依靠对话流程实现JSON回显功能。"""

    def __init__(self) -> None:
        self.pending = set[tuple[int, int]]()
        """接下来需要回显的(context, sender)对。"""

    def on_message(self, event: Event) -> object:
        if (event.context, event.sender) in self.pending:
            self.pending.remove((event.context, event.sender))
            return humanity.format_object(event._json)

    def on_command_debug_json(self, event: Event):
        self.pending.add((event.context, event.sender))
        return "将以 JSON 回显接下来未被处理的一条消息。"
