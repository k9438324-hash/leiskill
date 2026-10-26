# 安装与环境检查

## 一键安装（Windows）

在 PowerShell 执行：

```powershell
& ([scriptblock]::Create((Invoke-RestMethod 'https://raw.githubusercontent.com/k9438324-hash/leiskill/main/install.ps1')))
```

此入口安装基础工具、leiskill 四个技能、缺失的审稿依赖和独立 Python 环境，并运行环境检查。剪映需已安装并打开过一次。完成后重启 Codex。
一键安装后的实际 Python 记录在 LEISKILL_PYTHON 及 `%LOCALAPPDATA%/leiskill/runtime.json`。默认位于 `%LOCALAPPDATA%/leiskill/venv/Scripts/python.exe`；已有旧 jj-skill 环境时复用。后文所有 `py -3` 命令均应改用该解释器：

```powershell
& $env:LEISKILL_PYTHON -X utf8 "$env:USERPROFILE\.agents\skills\jj\scripts\doctor.py"
```

以下为手动安装方法；使用一键入口后无需重复安装。

支持 Windows + 剪映专业版。建议 Python 3.12；需要 Node.js LTS 和 Git 才能运行 npx 安装命令。

## 安装技能

```powershell
npx -y skills add k9438324-hash/leiskill --skill jj -g -y
npx -y skills add dontbesilent2025/dbskill --skill dbs-script-flow -g -y
```

第二条安装官方字幕审稿依赖，本仓库不复制第三方技能。退出并重新打开 Codex 后开始新聊天。

## 安装运行依赖

```powershell
py -3 -m pip install imageio-ffmpeg
py -3 -m pip install "git+https://github.com/aoguai/pyJianYingDraft.git"
```

完整 FFmpeg（同时包含 ffmpeg 和 ffprobe）加入 PATH 为推荐配置。imageio-ffmpeg 是脚本支持的备选。
转写仅在需要时安装 `py -3 -m pip install faster-whisper`，已有确认 SRT 的流程无需主动下载转写模型。
pyJianYingDraft 必须提供 JianyingDraftCryptoCodec 和 DraftCryptoConfig，不能用不支持加密草稿的同名版本替代。

在已安装 jj 技能目录运行：

```powershell
py -3 scripts/doctor.py
py -3 scripts/workbench.py --help
```

doctor 只检查环境，不修改剪映工程。环境检查通过后仍需用用户指定素材构建独立草稿并检查剪映打开、播放和导出。

## 自定义路径

默认从当前用户的 LOCALAPPDATA 查找剪映，从当前用户目录查找扩展，不依赖原作者用户名。
自定义安装位置时，在运行 Python 的同一 PowerShell 中设置：

```powershell
$env:JY_INSTALL_DIR = "D:\Apps\JianyingPro\10.8.0.0"
$env:JY_USER_DATA = "D:\JianyingUserData"
$env:JJ_FONT_PATH = "D:\Fonts\subtitle.ttf"
```

这些是示例，需替换成本机真实目录。JY_INSTALL_DIR 应包含 JianyingPro.exe；字体需用户自行提供，本仓库不分发字体。默认无字幕时无需配置字体。
若使用源码形式的 pyJianYingDraft，可设置 PYJY_ROOT 为包含 pyJianYingDraft 子目录的项目根目录。
