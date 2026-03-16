import threading
import time

from pykinezumiko import Event, Plugin, conf


class MOTD(Plugin):
    def __init__(self) -> None:
        # 由于init里拿不到self.bot，需要这个hack
        def thread():
            time.sleep(0.114514)
            self.bot.send(conf.BACKSTAGE, self.get_motd())

        threading.Thread(target=thread).start()

    def get_motd(self) -> str:
        with open("motd.txt") as f:
            return f.read().rstrip()

    def on_command_motd(self, event: Event):
        return self.get_motd()
