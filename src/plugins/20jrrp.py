import time
import random
from .. import ChatbotBehavior

class 今日人品(ChatbotBehavior):
    def on_message(self, context: int, sender: int, text: str, message_id: int):
        if text == ".jrrp":
            t = random.Random((int(time.time()) + 3600 * 8) // 86400 + sender)
            return "今日のあんたん運勢は"+str(t.randint(0, 100))+"点や"
