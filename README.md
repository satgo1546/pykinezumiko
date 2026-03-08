# 木鼠子 ⅱ Python Ver. ~ 木卫二 ~

```
       .hddddddddddddddddddddddh.           pi@raspberrypi
      :dddddddddddddddddddddddddd:          --------------
     /dddddddddddddddddddddddddddd/         OS: Alpine Linux edge aarch64
    +dddddddddddddddddddddddddddddd+        Host: Raspberry Pi 4 Model B Rev 1.4
  `sdddddddddddddddddddddddddddddddds`      Kernel: Linux 6.12.69-0-rpi
 `ydddddddddddd++hdddddddddddddddddddy`     Uptime: 6 days, 23 hours, 11 mins
.hddddddddddd+`  `+ddddh:-sdddddddddddh.    Packages: 219 (apk)
hdddddddddd+`      `+y:    .sddddddddddh    Shell: fish 4.5.0
ddddddddh+`   `//`   `.`     -sddddddddd    Terminal: /dev/pts/7
ddddddh+`   `/hddh/`   `:s-    -sddddddd    CPU: BCM2711 (4) @ 1.50 GHz
ddddh+`   `/+/dddddh/`   `+s-    -sddddd    Memory: 1.83 GiB / 7.63 GiB (24%)
ddd+`   `/o` :dddddddh/`   `oy-    .yddd    Swap: Disabled
hdddyo+ohddyosdddddddddho+oydddy++ohdddh    Disk (/): 5.05 GiB / 28.80 GiB (18%) - ext4
.hddddddddddddddddddddddddddddddddddddh.    Local IP (wlan0): 192.168.1.48/24
 `yddddddddddddddddddddddddddddddddddy`     Locale: C.UTF-8
  `sdddddddddddddddddddddddddddddddds`
    +dddddddddddddddddddddddddddddd+
     /dddddddddddddddddddddddddddd/
      :dddddddddddddddddddddddddd:
       .hddddddddddddddddddddddh.
```

这里是今天也在树莓派4B上被修出新bug的骰娘<ruby>木鼠子<rp>（</rp><rt>きねずみこ</rt><rp>）</rp></ruby>。

木鼠子是基于pykinezumiko制作的骰娘，未公开。不过，要是找到了木鼠子的话，就跟木鼠子加个好友吧。

## 技术信息

pykinezumiko是[OneBot](https://onebot.dev/) SDK。它和[NoneBot](https://nonebot.dev/)等框架有着类似的作用，只是设计毫无保留地偏向开发的快乐。

要部署的话，首先要获取并运行[NapCat](https://napcat.napneko.icu/)（唯一经过测试的OneBot实现），配置下列连接方式（网络配置）：

```
┌────────────────────────┐POST ┌────────────────────────┐
│ OneBot                 ├────►│ pykinezumiko           │
│ http://localhost:5700/ │◄────┤ http://localhost:5701/ │
└────────────────────────┘ POST└────────────────────────┘
```

- 消息格式：数组
- 令牌：空

通过紫外线执行仓库内的主程序：`uv run main.py`。

pykinezumiko没有所谓的配置文件，所有配置都基于入口程序充满副作用的导入。某种意义上，pykinezumiko是个库；副作用却无情地将事实扭曲成别样。

```python
#!/usr/bin/env python3
"""消息处理端的入口。

请将本脚本保存为main.py。
"""

# conf模块中的配置项可在导入后修改。
import pykinezumiko.conf
# 少量紧急情况也需要使用的信息必须正确配置。
pykinezumiko.conf.BACKSTAGE = -979976910

# 导入即注册。通过导入顺序决定插件加载顺序。
# 下面加载了部分示例插件。
# 除了阅读Plugin类的文档，不要忘了可以跟随典例从实践中学习插件的制作方法。
import pykinezumiko.plugins.demo
import pykinezumiko.plugins.jrrp

# 在此加载自定义插件、当场创建插件，或者像下述这样，从指定文件夹下加载所有模块。
# 因为会按文件名顺序加载，所以可在文件名开头标注数字以指定插件加载顺序。
import os, importlib
for name in sorted(
    entry.name.removesuffix(".py")
    for entry in os.scandir("plugins")
    if entry.name.endswith(".py")
    and entry.name.count(".") == 1
    or entry.is_dir()
    and "." not in entry.name
):
    importlib.import_module("plugins." + name, ".")

# 导入app时就会启动服务循环。
import pykinezumiko.app
```

运行方法是在两个窗口分别启动go-cqhttp（`./go-cqhttp`）和消息处理端（`python main.py`）。

因为重启go-cqhttp需要重新发送登录信息，甚至重新扫码（`session.token`失效的场合），所以尽量少重启go-cqhttp。

消息处理端服务器启动时不断尝试监听目标端口，因此可以同时打开两个消息处理程序，甲成功监听的话，乙就会因端口被占用而被挡在门外。甲挂掉后，乙自然接管。这便是自我更新的原理：执行git pull之后，启动新的消息处理程序，再退出自己。

> 木鼠子——在生产环境使用调试模式实现重要特性的先驱者

## 以下功能在梦里有

因为在x86-64电脑上没法运行ARM64的程序，即使替换成x86-64版本的程序来尝试运行也势必会把树莓派上正在工作的踢下线，所以有个办法不需要真的登录QQ也能运行起一部分代码。使用类似[Matcha](https://github.com/A-kirami/matcha)的方法创建一个假的OneBot实现，就可以调试任何OneBot应用了。可惜Matcha不支持HTTP连接，这里没法直接使用。

### clock todos

- [ ] 取消机能
- [ ] 周天小时分钟秒
- [ ] 顺序变换
- [ ] 加减乘除

鼠：一直很想要但没做的功能

- [ ] 直接指定绝对时间，比如.clock 2023-01-09 刷红票
- [ ] .clock 明天 blabla
- [ ] .clock 明天8:00 刷红票
