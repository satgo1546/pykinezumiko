import importlib
import os
import time

from flask import Flask, request

from . import ChatbotBehavior, conf, docstore

# 从plugins文件夹下加载所有Python模块。
modules = [
    importlib.import_module("pykinezumiko.plugins." + name, ".")
    for name in sorted(
        filename.removesuffix(".py")
        for filename in os.listdir("pykinezumiko/plugins")
        if filename.endswith(".py") and filename.count(".") == 1
    )
]

# 为定义了记录类的模块分配文档数据库。
os.makedirs("excel", exist_ok=True)
databases = [
    docstore.Database(f"excel/{name}.xlsx", tables)
    for name, tables in (
        (
            module.__name__.rpartition(".")[2],
            tuple(
                v
                for v in module.__dict__.values()
                if isinstance(v, docstore.Table) and v.__module__ == module.__name__
            ),
        )
        for module in modules
    )
    if tables
]

# 虽然只是加载而没有将模块留下，但是其中的类皆已成功定义。
# 靠深度优先搜索找出所有继承了ChatbotBehavior但没有子类的类，它们是要实例化的插件类。
def leaf_subclasses(cls: type) -> list[type]:
    """找出指定类的所有叶子类。使用类上的__subclasses__函数。"""
    return [s for c in cls.__subclasses__() for s in leaf_subclasses(c)] or [cls]


# 实例化找到的插件类。
plugins: list[ChatbotBehavior] = []
for p in leaf_subclasses(ChatbotBehavior):
    print("加载插件类", p.__name__)
    plugins.append(p())

# 上述过程中易碎的细节：
# • 加载模块按文件名顺序。
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
        e.__traceback__
        if context:
            ChatbotBehavior.send(context, f"\u267b\ufe0f {e!r}")
        else:
            ChatbotBehavior.send(conf.INTERIOR, f"\u267b\ufe0f 处理无来源事件时发生了下列异常：{e!r}")
        # 异常将由Flask捕获并打印到控制台，因此再行抛出。
        raise
    return ""
