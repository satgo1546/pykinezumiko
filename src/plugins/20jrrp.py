from .. import ChatbotBehavior


class 今日人品(ChatbotBehavior):
    def on_message(self, context: int, sender: int, text: str, message_id: int):
        if text == ".jrrp":
            return "诶，功能还没做呢！"
