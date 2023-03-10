"""插件的文件夹。

因为会按文件名顺序加载，所以标注了数字。用数字作为模块名开头还有防止插件间互相导入的意想不到的副作用。不支持子文件夹。

要学习插件制作方法的话，下面是推荐的阅读顺序。

- 20jrrp：梦开始的地方。
- 70demo：从最基础的收到消息就回复，到基于Python生成器语言功能的对话流程，汇聚了各种功能演示的插件。
- 20clock：演示定时任务和数据持久化的做法。
- 10gate：遭遇来自go-cqhttp的事件时，会依次询问插件是否能处理该事件，遇到第一个有处理能力的插件后就结束询问。因此，10gate能在机器人被某个群禁用时拦截事件，阻止后续插件对事件的处理。
"""
