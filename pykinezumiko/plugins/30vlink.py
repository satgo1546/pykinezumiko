import math
import time
from bisect import bisect_right
import re
import requests
from PIL import Image
from io import BytesIO
import os

from .. import ChatbotBehavior, conf, docstore


def days_to_cents(days: float) -> int:
    """「曲线」系统计算公式。"""
    return math.floor(days * 40 / 3 * (math.exp(-days * days / 36000) + 2))


def cents_to_days(cents: int) -> float:
    """days_to_cents的反函数。因为无解析解，返回二分得到的近似解。"""
    return (
        bisect_right(
            range(cents * 1000000), cents, key=lambda x: days_to_cents(x * 1e-6)
        )
        * 1e-6
    )


class Subscription(docstore.Record):
    # 索引值是记录的添加时间
    user: int
    identifier: str  # 表明该记录来源（账单识别（日期）、.debug link命令等）
    cents: int
    expiry: float


class VLink(ChatbotBehavior):
    def on_command_debug_link(self, sender: int, user: int, amount: str):
        """.debug link ⟨用户⟩ [⟨天⟩][$◊]"""
        days, _, dollars = amount.partition("$")
        days = float("0" + days)
        dollars = float(dollars or "0")
        self.send(
            user,
            self.vlink_subscribe(
                user, f".debug link {time.asctime()}", round(
                    dollars * 100), days, True
            ),
        )
        self.send(conf.INTERIOR,
                  f"[{self.name(sender)}] 增加了 #{days} 日 #{user} 的订阅时长。")

    def vlink_subscribe(
        self, user: int, identifier: str, cents: int, days: float, bug: bool
    ) -> str:
        expiry = time.time()  # 当前订阅过期日期
        for _, subscription in Subscription.items():
            if subscription.user == user and subscription.identifier == identifier:
                self.send(conf.INTERIOR,
                          f"{user} 试图多次发送具有相同账单时间 {identifier} 的图像。")
                return "该记录已确认过。"
            expiry = max(expiry, subscription.expiry)
        expiry += days * 86400
        Subscription[time.time()] = Subscription(
            user=user,
            identifier=identifier,
            cents=cents,
            expiry=expiry,
        )
        expiry = time.strftime("%-Y 年 %-m 月 %-d 日",
                               time.gmtime(expiry + 3600 * 8))

        self.send(
            conf.INTERIOR,
            f"user = {user}, cents = {cents}, days = {days}, bill time = {identifier}, expire = {expiry}",
        )
        return (
            f"因为系统问题，管理员在确认后为你调整了订阅时长。现在" if bug else f"确认 {cents / 100.0} 元。"
        ) + f"订阅 {days} 日至 #{expiry}。"

    def on_message(self, context: int, sender: int, text: str, message_id: int):
        # 如果消息以图片开头（含仅包含一张图片的情况）……
        if match := re.match(r'\x9dimage\0url=(.*?)\0', text):
            response = requests.get(match.group(1))
            with Image.open(BytesIO(response.content)).convert('RGB') as img:
                size = img.size
                total_pixels = size[0] * size[1]
                white_pixels = 0
                for x in range(size[0]):
                    for y in range(size[1]):
                        r, g, b = img.getpixel((x, y))
                        if r == g == b == 255:
                            white_pixels += 1
                ratio = white_pixels / total_pixels
                if ratio > 0.6:
                    # 直接转发
                    self.send(
                        conf.INTERIOR,
                        f"user = {sender}, img = {text}"
                    )
                    # 存储在账单目录下
                    os.makedirs("logs/zd", exist_ok=True)
                    with open(os.path.join("logs/zd", ".png"), "wb") as f:
                        f.write(response.content)
                    return "判断为《账单》，转发等待审核中"
