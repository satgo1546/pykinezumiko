<img src=pykinezumiko/resources/favicon.webp align=right width=100 height=100>

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

## 用户手册

前往[**Read** *the* **Docs**](https://kinezumiko.readthedocs.io/)阅读木鼠子使用手册。

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

通过紫外线执行仓库内的主程序：`uv run -m pykinezumiko`。

pykinezumiko没有所谓的配置文件，所有配置都基于源代码级别的补丁或插件的互相副作用。显然不能指望世界上仅有一个实例的项目对多环境部署有什么恰当的应对措施。

与OneBot实现交互的部分不部署上线就无法测试。虽然[Matcha](https://github.com/A-kirami/matcha)能创建一个假的OneBot实现，但可惜Matcha不支持HTTP连接，这里没法直接使用。因此，目前最好的办法还是尽量抽出纯函数逻辑并编写测试，然后祈祷部署后不要立刻崩溃。

消息处理端一旦启动，除了Ctrl+C就没有其他退出的方法。直接原因是[uvicorn不支持编程退出](https://github.com/Kludex/uvicorn/discussions/1103)；但另一方面，`kill -SIGINT`也够用。GET /能返回该方法所需的PID。消息处理端就[像大多数OneBot实现一样](https://github.com/NapNeko/NapCatQQ/issues/508 "“事实上napcat的登录逻辑几乎是一次性的”")，无法处理崩溃，守护进程是持续运行的必要项。

> 木鼠子——在生产环境使用调试模式实现重要特性的先驱者

## 声明

本项目的代码按AGPL-3.0协议提供。

本项目**不含任何**通过生成式人工智能产生的内容，但这不代表所有内容都由人类创造。
