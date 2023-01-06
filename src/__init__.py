import requests
from typing import Optional


class ChatbotBehavior:
    """所有插件的基类。

    继承此类且没有子类的类将自动被视为插件而实例化。
    通过覆盖以“on_”开头的方法，可以监听事件。
    因为这些方法都是空的，不必在覆盖的方法中调用super。
    可以在事件处理中调用messenger模块中的方法来作出行动。

    事件包含整数型的context和sender参数。
    正数表示好友，负数表示群。
    context表示消息来自哪个会话。要回复的话请发送到这里。
    sender表示消息的发送者。除了少数无来源的群通知事件，都会是正值。
    例如，私聊的场合，有context == sender > 0；群聊消息则满足context < 0 < sender。

    通常，当插件处理了事件（例如回复了消息），就要返回真值。
    为方便计，可以直接返回要回复的文字，与执行send函数无异。
    返回假值（即None、False、""）的场合，表示插件无法处理这个事件。该事件会轮替给下一个插件来处理。
    """

    @staticmethod
    def escape(text: str) -> str:
        """CQ码转义。"""
        return (
            text.replace("&", "&amp;")
            .replace("[", "&#91;")
            .replace("]", "&#93;")
            .replace(",", "&#44;")
        )

    @staticmethod
    def gocqhttp(endpoint: str, data: dict = {}, **kwargs) -> dict:
        """向go-cqhttp发送请求，并返回响应数据。

        关于具体参数，必须参考go-cqhttp的API文档。
        https://docs.go-cqhttp.org/api/

        使用例：
        - 发送私聊消息
            gocqhttp("send_private_msg", user_id=114514, message="你好")
        - 获取当前登录账号的昵称
            gocqhttp("get_login_info")["nickname"]
        """
        kwargs.update(data)
        data = requests.post(
            f"http://127.0.0.1:5700/{endpoint}",
            headers={"Content-Type": "application/json"},
            json=kwargs,
        ).json()
        if data["status"] == "failed":
            raise Exception(data["msg"], data["wording"])
        return data["data"] if "data" in data else {}

    @classmethod
    def send(cls, context: int, message: str) -> None:
        """发送消息。

        :param context: 发送目标，正数表示好友，负数表示群。
        :param message: 要发送的消息内容，富文本用CQ码表示。
        """
        cls.gocqhttp(
            "send_msg",
            {"user_id" if context >= 0 else "group_id": abs(context)},
            message=message,
        )

    def on_message(self, context: int, sender: int, text: str, message_id: int):
        """当收到消息时执行此函数。

        如果不知道参数和返回值的含义的话，请看ChatbotBehavior类的说明。
        """

    def on_message_deleted(self, context: int, sender: int, text: str, message_id: int):
        """消息被撤回。"""

    def on_file(self, context: int, sender: int, filename: str, size: int, url: str):
        """接收到离线文件或群有新文件。"""

    def on_admission(self, context: int, sender: int, text: str) -> Optional[bool]:
        """收到了添加好友的请求或加入群聊的请求。

        返回True接受，False拒绝，None无视并留给下一个插件处理。
        """
