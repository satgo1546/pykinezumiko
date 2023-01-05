import requests

def escape(text: str) -> str:
    return text.replace("&", "&amp;").replace("[", "&#91;").replace("]", "&#93;").replace(",", "&#44;")


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


def send(context: int, message: str) -> None:
    """发送消息。

    :param context: 发送目标，正数表示好友，负数表示群。
    :param message: 要发送的消息内容，富文本用CQ码表示。
    """
    data = {"message": message}
    data["user_id" if context >= 0 else "group_id"] = abs(context)
    gocqhttp("send_msg", data)
