from typing import Optional

class ChatbotBehavior:
    """所有插件的基类。

    继承此类且没有子类的类将自动被视为插件而实例化。
    通过覆盖方法，可以监听事件。
    因为这些方法都是空的，不必在覆盖的方法中调用super。
    可以在事件处理中调用messenger模块中的方法来作出行动。

    事件包含整数型的context和sender参数。
    正数表示用户，负数表示群。
    context表示消息来自哪个会话。要回复的话请发送到这里。
    sender表示消息的发送者。除了少数无来源的群通知事件，都会是正值。
    例如，私聊的场合，有context == sender > 0；群聊消息则满足context < 0 < sender。
    """

    def onmessage(self, context: int, sender: int, text: str):
        """当收到消息时执行此函数。

        如果不知道参数含义的话，请看ChatbotBehavior类的说明。
        """

    def onfriendrequest(self, context: int, sender: int, text: str) -> Optional[bool]:
        """收到了添加好友请求。

        返回True接受，False拒绝，None无视。"""
