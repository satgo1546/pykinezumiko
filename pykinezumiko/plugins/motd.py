import os

from pykinezumiko import Event, Plugin, conf


class MOTD(Plugin):
    def __init__(self) -> None:
        if motd := self.get_motd():
            self.bot.send(conf.BACKSTAGE, motd)
            os.remove("motd.txt")

    def get_motd(self) -> str:
        try:
            with open("motd.txt") as f:
                return f.read().rstrip()
        except FileNotFoundError:
            return ""

    def on_command_motd(self, event: Event):
        if motd := self.get_motd():
            return motd
        return "没有设置今日消息。"
