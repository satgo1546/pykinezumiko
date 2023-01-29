from .app import app

# 以调试模式运行应用程序，监视源代码的变更并自动重新加载。
app.run(port=5701, debug=True, use_reloader=True, use_debugger=False)
