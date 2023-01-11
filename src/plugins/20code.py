import re
from .. import ChatbotBehavior


class Code(ChatbotBehavior):
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
    MORSE_NORMALIZE = str.maketrans(
        MORSE_DOTS + MORSE_DASHES, "." * len(MORSE_DOTS) + "-" * len(MORSE_DASHES)
    )

    @ChatbotBehavior.documented()
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
