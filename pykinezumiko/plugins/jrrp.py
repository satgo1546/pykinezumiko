import time
import random
from .. import ChatbotBehavior

class 今日人品(ChatbotBehavior):
    def on_command_jrrp(self, sender: int):
        r = random.Random((int(time.time()) + 3600 * 8) // 86400 + sender)
        return f"今日のあんたん運勢は{r.randrange(101)}点や。"
