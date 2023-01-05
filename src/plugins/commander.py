from .. import ChatbotBehavior, messenger
import tarfile
import tempfile

class Commander(ChatbotBehavior):
    def onmessage(self, context: int, sender: int, text: str):
        ...
