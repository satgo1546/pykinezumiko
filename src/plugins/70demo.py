import time
import random
from typing import Union
from collections.abc import Generator
from .. import ChatbotBehavior


class Demonstration(ChatbotBehavior):
    """演示各种功能的插件。"""

    def on_message(
        self, context: int, sender: int, text: str, message_id: int
    ) -> Generator[str, str, Union[None, bool, str]]:
        if text == ".debug p":
            return "你好，世界！"
        elif text == ".cat":
            return random.choice(("喵呜～", "喵！", "喵？", "喵～"))
        # 可以使用任意字符串判据。（废话。）
        elif not text.startswith("^") and text.endswith("^") or text == "More?":
            return "More?"
        elif text == ".debug m":
            # 不必只回复一条消息。有需要的话，可以向任意会话任意发送消息。
            self.send(context, "这是第一条消息。")
            self.send(context, "这是第二条消息。")
            return True
        elif text == ".debug t":
            self.send(context, "8 秒后，将被回调。")
            # 在这8秒内，其他命令能否响应？
            time.sleep(8)
            return "被回调。"
        elif text == ".猜数字":
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
        elif text.startswith(".debug next"):
            text = text.removeprefix(".debug next")
            n = max(1, int(text)) if text.isnumeric() else 1
            if n > 9:
                return "注意，即使 .debug cls 也无法清除待回显的状态。请再考虑一下。"
            for i in range(n):
                text = yield text if i else f"将回显接下来的 {n} 条消息。"
