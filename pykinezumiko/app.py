"""主程序。

仅仅是导入这个模块就会启动服务器，所以务必在导入所有需要的插件后再导入这个模块。
"""

import os
import sys
import time
import errno
import traceback
from collections import defaultdict
import http.server
import werkzeug.serving
from flask import Flask, request

from . import ChatbotBehavior, conf, docstore


# 虽然只是加载而没有将模块留下，但是其中的类皆已成功定义。
# 靠深度优先搜索找出所有继承了ChatbotBehavior但没有子类的类，它们是要实例化的插件类。
def leaf_subclasses(cls: type) -> list[type]:
    """找出指定类的所有叶子类。使用类上的__subclasses__函数。"""
    return [s for c in cls.__subclasses__() for s in leaf_subclasses(c)] or [cls]


# 为定义了记录类的模块分配文档数据库。
os.makedirs("excel", exist_ok=True)
databases = defaultdict(list)
for t in leaf_subclasses(docstore.Record):
    databases[t.__module__].append(t)
databases = [
    docstore.Database(f"excel/{name}.xlsx", tuple(tables)) for name, tables in databases.items()
]

# 实例化找到的插件类。
plugins: list[ChatbotBehavior] = []
for p in leaf_subclasses(ChatbotBehavior):
    print("加载插件类", p.__name__)
    plugins.append(p())

# 上述过程中易碎的细节：
# • 插件模块相互独立，从而按导入顺序加载。
# • Python 3.4起，__subclasses__按字典键的顺序返回子类列表。
# • Python 3.6起，字典按加入顺序迭代键。
# • Python 3.9起，文档明确指出__subclasses__按子类定义先后顺序返回子类列表。
# • leaf_subclasses函数返回列表从而保持顺序。

# 创建Flask应用程序实例。
app = Flask(__name__)


def simulator_generator():
    yield """<!DOCTYPE html>
        <title>好梦在何方</title>
        <strong>114, 514!</strong>
    """
    for i in range(114514):
        yield f"<p>{i}</p>\n"
        time.sleep(1)


@app.route("/", methods=["GET", "POST"])
def gocqhttp_event():
    # GET请求来自浏览器。
    if request.method == "GET":
        return simulator_generator()

    # POST请求来自go-cqhttp。
    # 为了原路反馈异常信息，在局部变量中记录消息上下文。
    context = 0

    try:
        data = request.json
        # 因为request.json的类型是Optional[Any]，所以不得不先打回None的可能性。
        # 其实是data为None不可能的！在此之前就已经抛出异常挂掉了。
        # 为了类型检查通过不得已而检查一下罢了。
        assert data is not None
        context, _ = ChatbotBehavior.context_sender_from_gocqhttp_event(data)
        # 易碎的细节：all和any短路求值。
        any(p.gocqhttp_event(data) for p in plugins)
        # 在处理完任意事件后自动保存所有已修改的数据库。
        for database in databases:
            if database.dirty:
                print("写入数据库", database)
                database.save()
    except Exception as e:
        # 打印错误堆栈到控制台。
        # 通常的Flask应用中，只需再行抛出。但是，因为使用了自定义的服务器类，这么做会导致进程终止。
        traceback.print_exc()
        if context:
            ChatbotBehavior.send(context, f"\u267b\ufe0f {e!r}")
        else:
            ChatbotBehavior.send(conf.INTERIOR, f"\u267b\ufe0f 处理无来源事件时发生了下列异常：{e!r}")
    return ""


if len(sys.argv) > 1:
    print("启动参数", sys.argv[1])
    ChatbotBehavior.send(conf.INTERIOR, f"\U0001f4e6 {sys.argv[1] = }")


class PerseveringWSGIServer(http.server.ThreadingHTTPServer):
    """持续不断地尝试监听端口的多线程服务器。

    werkzeug.serving.make_server创建的服务器只是为了打印自定义错误信息
    “Either identify and stop that program, or start the server with a different …”
    就把OSError据为己有，所以不得不自己定义一个服务器类来使用。
    """

    multithread = True
    multiprocess = False

    def __init__(self, host: str, port: int, app) -> None:
        handler = werkzeug.serving.WSGIRequestHandler
        handler.protocol_version = "HTTP/1.1"

        self.host = host
        self.port = port
        self.app = app
        self.address_family = werkzeug.serving.select_address_family(host, port)
        self.ssl_context = None

        super().__init__(
            werkzeug.serving.get_sockaddr(host, port, self.address_family),  # type: ignore[arg-type]
            handler,
            bind_and_activate=False,
        )
        while True:
            try:
                self.server_bind()
                self.server_activate()
                break
            except OSError as e:
                if e.errno == errno.EADDRINUSE:
                    print("端口被占用，将重试")
                    time.sleep(1)
                else:
                    raise


PerseveringWSGIServer("127.0.0.1", 5701, app).serve_forever()
