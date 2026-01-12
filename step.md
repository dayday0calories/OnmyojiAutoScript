是谁用 Mac 玩游戏啊！！！
是我了
感谢原作者大大精心构建的脚本让 mac 端也能轻松运行
下面详细介绍下操作流程

python3.10 -m venv .venv
source .venv/bin/activate
安装 dependcies
python -m pip install -r requirements-nonwin.txt

接下来启动 server
python server.py

记住 INFO 的 port
eg:
2026-01-11 00:35:45.021 │ <<< LAUNCHER CONFIG >>>  
INFO 2026-01-11 00:35:45.023 │ [Host] 0.0.0.0  
INFO 2026-01-11 00:35:45.025 │ [Port] 22267  
INFO 2026-01-11 00:35:45.026 │ [Reload] False

然后就是启动 OASX
这里推荐网页版简单粗暴
https://runhey.github.io/OASX/#/main
在地址这一栏填写 127.0.0.1:port 登陆即可
注意注意很重要，如果这里出现连接失败，显示空白的等等问题，请在浏览器 control+command+R 强制 reload 就好

模拟器本人用的 mumu 模拟器的 macos 版本
在脚本的模拟器设置方面，截屏方案和操作方式请都选择 ADB

目前我发现会有个别 task 在 mac 端运行会报错，如 DailyTrifiles， 大部分其他的没问题

最后最后感谢作者大大
