import time
import random
from .. import ChatbotBehavior

class 今日人品(ChatbotBehavior):
    def on_message(self, context: int, sender: int, text: str, message_id: int):
        if text == ".jrrp":
            random.seed((int(time.time()) + 3600 * 8) // 86400 + sender)
            return random.randint(0, 100)
