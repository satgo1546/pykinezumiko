# 木鼠子 ⅱ Python Ver. ~ 木卫二 ~

```
         _,met$$$$$gg.           pi@raspberrypi
      ,g$$$$$$$$$$$$$$$P.        OS: Debian 11 bullseye
    ,g$$P""       """Y$$.".      Kernel: aarch64 Linux 5.15.61-v8+
   ,$$P'              `$$$.      Uptime: 6d 12h 2m
  ',$$P       ,ggs.     `$$b:    Packages: 597
  `d$$'     ,$P"'   .    $$$     Shell: bash 5.1.4
   $$P      d$'     ,    $$P     Resolution: No X Server
   $$:      $$.   -    ,d$$'     WM: Not Found
   $$\;      Y$b._   _,d$P'      Disk: 1.9G / 30G (7%)
   Y$$.    `.`"Y$$$$P"'          CPU: BCM2835 @ 4x 1.8GHz
   `$$b      "-.__               RAM: 251MiB / 7812MiB
    `Y$$
     `Y$$.
       `$$b.
         `Y$$b.
            `"Y$b._
                `""""
```

架构仍是经典的双端分离：go-cqhttp负责假装自己是QQ，Flask + requests这边负责消息的实际处理。这回因为是CQHTTP，所以两边用HTTP和JSON通信。具体来说，就是像下面这样。

```
┌────────────────────────┐POST ┌────────────────────────┐
│ go-cqhttp              ├────►│ Flask                  │
│ http://localhost:5700/ │◄────┤ http://localhost:5701/ │
└────────────────────────┘ POST└────────────────────────┘
```

端口号是go-cqhttp自动生成的配置文件中的默认值，现在写死了，改的话要改好几个地方。go-cqhttp收到消息时，会发送请求给Flask端。Flask端想要发出消息时，会调用requests库向go-cqhttp发出请求。这是标准的go-cqhttp通信流程。

仓库中已经包含了能让它在树莓派上运行的全部资源，包括go-cqhttp的ARM64二进制、上线的配置`config.yml`、常用设备信息`device.json`、会话令牌`session.token`。额外需要安装的包列表如下：

- git
- python3-requests
- python3-flask

运行方法是在两个窗口分别启动go-cqhttp（`./go-cqhttp`）和消息处理端的守护程序（`./daemon.py`）。使用Raspbian自带的Python即可，无需创建虚拟环境等。因为重启go-cqhttp需要重新发送登录信息，甚至重新扫码（`session.token`失效的场合），所以尽量少重启go-cqhttp。

## 以下功能在梦里有

守护进程每隔一定时间就会执行git add—git commit—git push三连，当推送失败时则会自动拉取、合并再推送，**但不会自动重启**，数据文件可以如此更新，程序更新需要手动指令使Flask进程结束。
当Flask进程退出时，无论退出代码为何，守护进程都会立即与仓库同步并尝试重启，如果退出代码不为零，则回退到。
所以就是检测到更新就git pull然后重启flask罢
不过有一些细节问题，比如代码有问题，重启一下挂了

因为在x86-64电脑上没法运行ARM64的程序，即使替换成x86-64版本的程序来尝试运行也势必会把树莓派上正在工作的踢下线，所以有个办法不需要真的登录QQ也能运行起一部分代码。单纯运行`python -m src`的话，只会启动Flask端。用浏览器访问`http://localhost:5701/`，因为检测到是来自浏览器的GET而非来自go-cqhttp的POST，就会提供一个假的聊天窗口。因为是假的聊天窗口，所以很多功能都用不了，只适合用来测试聊天AI，与QQ绑定的逻辑还是要传到树莓派上实机测试。
