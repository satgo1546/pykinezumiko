import math
import os
import re
import time
import zlib
from io import BytesIO

import requests
from PIL import Image

from .. import ChatbotBehavior, conf, docstore
from ..ponyfill import bisect_right

github_token = "ghp_1145141919810HengHengAaaaaaaaaaaargh"


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
        self.vlink_refresh()
        self.send(conf.INTERIOR,
                  f"[{self.name(sender)}] 增加了 {days} 日和相当于 {dollars} 元 {user} 的订阅时长。")

    @staticmethod
    def scatter(x: int | str) -> int:
        return zlib.crc32(str(x).encode())

    def on_command_debug_vlink_who(self, y: int):
        x = {x for x in self.get_expiry_dict().keys() if self.scatter(x) == y}
        return f"{x!r} ↦ {y} ↦ {self.scatter(y)}"

    def vlink_subscribe(
        self, user: int, identifier: str, cents: int, days: float, bug: bool
    ) -> str:
        expiry = time.time()  # 当前订阅过期日期
        for subscription in Subscription.values():
            if subscription.user == user:
                if subscription.identifier == identifier:
                    self.send(
                        conf.INTERIOR,
                        f"{user} 试图多次发送具有相同账单时间 {identifier} 的图像。",
                    )
                    return "该记录已确认过。"
                expiry = max(expiry, subscription.expiry)
        expiry += (days + cents_to_days(cents)) * 86400
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
        ) + f"订阅 {days} 日至 {expiry}。"

    def get_expiry_dict(self) -> dict[int, float]:
        """获取各用户的过期时间。"""
        # 易碎的细节：字典解析式（dict comprehension）对重复键保留末次迭代的值。
        return {subscription.user: subscription.expiry for subscription in Subscription.values()}

    def vlink_refresh(self) -> requests.Response:
        command = "# run by tenshitaux.rb^W^W^W30vlink.py\n"
        for user, expiry in self.get_expiry_dict().items():
            filename = f"docs/{self.scatter(user)}.yml"
            command += f"ln -vfs {'hello' if time.time() < expiry else 'mfgexp'}.yml {filename}\n"
        return requests.post(
            "https://api.github.com/repos/Salenzo/Spoon-Knife/actions/workflows/ruby.yml/dispatches",
            headers={
                "Accept": "application/vnd.github+json",
                "Authorization": f"Bearer {github_token}",
            },
            json={"ref": "main", "inputs": {"name": command}},
        )

    def on_command_debug_vlink_refresh(self):
        response = self.vlink_refresh()
        return f"更新订阅列表响应：{response.reason}，响应体 {response.content}。"

    def get_vlink_url_message(self, user_id: int) -> str:
        url = str(self.scatter(user_id))
        if len(url) > 5:
            url = url[:len(url)//2] + "\x9dface\0id=60\x9c" + url[len(url)//2:]
        url = f"https:\x9dface\0id=60\x9c//metsubojinrai\x9dface\0id=60\x9c.top\x9dface\0id=60\x9c/Spoon-Knife/{url}.yml"
        m = self.get_expiry_dict()
        if user_id in m:
            expiry = time.strftime("%Y 年 %-m 月 %-d 日",time.gmtime(m[user_id]+8*3600))
            if time.time() < m[user_id]:
                return f"[{self.name(user_id)}] 的订阅链接如下，使用期限至 {expiry}。首次使用时，可能需要数分钟才能生效。因为可能存在的河蟹，请删除表情后食用。\n‣ {url}"
            else:
                return f"[{self.name(user_id)}] 的订阅已于 {expiry}过期。"
        else:
            return f"[{self.name(user_id)}] 当前没有可用的订阅。"

    def on_command_vlink(self, context: int):
        if context > 0:  # 私聊
            return self.get_vlink_url_message(context)

    def on_message(self, context: int, sender: int, text: str, message_id: int):
        if context < 0:  # 群聊
            return
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
                        f"{text}"
                    )
                    self.send(
                        conf.INTERIOR,
                        f".debug link {sender} $"
                    )
                    # 存储在账单目录下
                    os.makedirs("logs/zd", exist_ok=True)
                    with open(os.path.join("logs/zd", ".png"), "wb") as f:
                        f.write(response.content)
                    return "判断为《账单》，转发等待审核中"
