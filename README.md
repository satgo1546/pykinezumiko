# flask_guard_test

## 需求

- [x] 守护进程每隔一定时间就会执行git add—git commit—git push三连
    - [x] 当推送失败时则会自动拉取、合并再推送，但不会自动重启，数据文件可以如此更新
- [x] Flask服务器开启debug=True，这样当程序被git更新时可自动重启
- [x] 当Flask进程退出时，如果退出代码为零，守护进程会立即与仓库同步并重启Flask进程；如果退出代码不为零，则持续与仓库同步，在没有pull到新数据前不尝试重启
