import re
import traceback

import httpx

import pykinezumiko


def decbv(bv: str) -> int:
    """转换BV号为avid。

    :param bv: 可以是"BV1GJ411x7h7"或单纯的"1GJ411x7h7"。
    """
    avid = 0
    bv_indices = ["fZodR9XQDSUm21yCkr6zBqiveYah8bt4xsWpHnJE7jL5VG3guMTKNPAwcF".index(ch) for ch in bv[-10:]]
    for i in range(6):
        avid += bv_indices[(1, 2, 4, 6, 8, 9)[i]] * 58 ** (2, 4, 5, 3, 1, 0)[i]
    return (avid - 8728348608) ^ 177451812


def encav(avid: int) -> str:
    """转换avid为BV号。

    :returns: 不带"BV"前缀的10位BV号，例如"1GJ411x7h7"。
    """
    bv = ["1", "?", "?", "4", "?", "1", "?", "7", "?", "?"]
    for i in range(6):
        bv[(1, 2, 4, 6, 8, 9)[i]] = "fZodR9XQDSUm21yCkr6zBqiveYah8bt4xsWpHnJE7jL5VG3guMTKNPAwcF"[
            ((avid ^ 177451812) + 8728348608) // 58 ** (2, 4, 5, 3, 1, 0)[i] % 58
        ]
    return "".join(bv)


class AV_BV(pykinezumiko.Plugin):
    def on_message(self, event: pykinezumiko.Event):
        if re.search(r"bilibili\.com\/video\/BV|BV1..4.1.7..|\bb23\.tv\b", event.text):
            return self.av_bv(event.text)

    def av_bv(self, text: str):
        bv = {bv: decbv(bv) for bv in re.findall(r"BV1\w\w4\w1\w7\w\w", text, re.ASCII)}
        try:
            b23 = {
                url: decbv(match.group())
                for url in (
                    httpx.head("https://" + url.group().replace("\\", "")).headers["Location"]
                    for url in re.finditer(r"\bb23\.tv\\{0,2}\/[A-Za-z0-9]{3,8}", text)
                )
                if (match := re.search(r"BV1..4.1.7..", url))
            }
        except httpx.RequestError:
            print("请求发生问题，忽略本次转换")
            traceback.print_exc()
            return
        if bv or b23:
            str1 = f" {len(bv)} 个 BV 号" if bv else ""
            str2 = f" {len(b23)} 个 bilibili 精巧地址" if b23 else ""
            str3 = "和" if bv and b23 else ""
            r = f"消息中的{str1}{str3}{str2}被转换为 aid。\n"
            # 目前小程序暂时还不是这样接收的。之后可能会修改。
            if text.startswith("\x1b<Rich message::Xiaochengxu>") and not bv and len(b23) == 1:
                r = "bilibili 小程序被转换为地址。\n"
            bv |= b23
            r += (
                "\n".join(f"‣ {k} = av{v}" for k, v in bv.items())
                if len(bv) > 1
                else f"‣ av{next(iter(bv.values()))}"
            )
            return r
