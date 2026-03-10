import re

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


class Code(pykinezumiko.Plugin):
    def on_message(self, event: pykinezumiko.Event):
        if re.search(r"bilibili\.com\/video\/BV|BV1..4.1.7..|\bb23\.tv\b", event.text):
            return self.av_bv(event.text)

    def av_bv(self, text: str):
        bv = {bv: decbv(bv) for bv in re.findall(r"BV1\w\w4\w1\w7\w\w", text, re.ASCII)}
        b23 = {
            url: decbv(match.group())
            for url in (
                httpx.head("https://" + url.group().replace("\\", "")).headers["Location"]
                for url in re.finditer(r"\bb23\.tv\\{0,2}\/[A-Za-z0-9]{3,8}", text)
            )
            if (match := re.search(r"BV1..4.1.7..", url))
        }
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

    @pykinezumiko.documented()
    # 由于on_command_u+不是合法的标识符名称，只能先定义一个别名，然后在类定义完全后setattr。
    def on_command_unicode(self, s: str):
        """.u+ ⟨210F|ℏ⟩（Unicode 码位）"""
        r = []
        for w in s.split():
            if re.fullmatch(r"[0-9A-Fa-f]{1,6}", w):
                r.append(f"{int(w, 16):c} U+{w.upper():>04s}")
            else:
                for c in w:
                    r.append(f"{c!r} U+{ord(c):04X}")
        return "\n".join(r)

    MORSE_TABLE = {
        "A": ".-",
        "B": "-...",
        "C": "-.-.",
        "D": "-..",
        "E": ".",
        "F": "..-.",
        "G": "--.",
        "H": "....",
        "I": "..",
        "J": ".---",
        "K": "-.-",
        "L": ".-..",
        "M": "--",
        "N": "-.",
        "O": "---",
        "P": ".--.",
        "Q": "--.-",
        "R": ".-.",
        "S": "...",
        "T": "-",
        "U": "..-",
        "V": "...-",
        "W": ".--",
        "X": "-..-",
        "Y": "-.--",
        "Z": "--..",
        "0": "-----",
        "1": ".----",
        "2": "..---",
        "3": "...--",
        "4": "....-",
        "5": ".....",
        "6": "-....",
        "7": "--...",
        "8": "---..",
        "9": "----.",
    }
    for c in list(MORSE_TABLE.keys()):
        MORSE_TABLE[MORSE_TABLE[c]] = c
    MORSE_DOTS = ".·⋅∙•⸳⸱・･ꞏ․‧˙⦁"
    MORSE_DASHES = "-‐‒–—⁃−𐆑―一ー𝄖－"
    MORSE_NORMALIZE = str.maketrans(MORSE_DOTS + MORSE_DASHES, "." * len(MORSE_DOTS) + "-" * len(MORSE_DASHES))

    @pykinezumiko.documented()
    def on_command_morse(self, s: str):
        """.morse ⟨·–|A⟩（摩尔斯电码）"""

        def replacer(match: re.Match[str]) -> str:
            s = match.group().translate(self.MORSE_NORMALIZE)
            return self.MORSE_TABLE.get(s.upper(), s)

        s = re.sub(r"(?<=\w) +(?=\w)", " / ", s)
        s = re.sub(r"(?<=\w)(?=\w)", " ", s)
        s = re.sub(
            rf"\w|[{re.escape(self.MORSE_DOTS)}{re.escape(self.MORSE_DASHES)}]+",
            replacer,
            s,
        )
        return s


setattr(Code, "on_command_u+", Code.on_command_unicode)
