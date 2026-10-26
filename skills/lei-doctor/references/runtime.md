# 运行方式

从 LEISKILL_PYTHON 或 `%LOCALAPPDATA%/leiskill/venv/Scripts/python.exe` 读取本机解释器；如果仅有旧版 `%LOCALAPPDATA%/jj-skill/venv/Scripts/python.exe`，继续使用旧环境。均不存在时用已核验 Python 运行，缺依赖如实报告。

在当前技能目录运行：

```powershell
& "$env:LOCALAPPDATA\leiskill\venv\Scripts\python.exe" -X utf8 scripts/check.py
```

路径为示例，应使用实际找到的解释器，不要在本机安装路径未知时直接运行示例。
