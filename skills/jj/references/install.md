# 安装与环境检查

Windows 官方安装入口：

```powershell
& ([scriptblock]::Create((Invoke-RestMethod 'https://raw.githubusercontent.com/k9438324-hash/leiskill/main/install.ps1')))
```

安装本仓库四个技能及独立 Python 环境，不安装外部审稿技能。剪映需已安装并打开一次；安装完成后重新加载客户端技能。新旧独立 Python 环境的选择方式见 [主流程](../SKILL.md)。

只安装技能文件：

```powershell
npx -y skills add k9438324-hash/leiskill --skill jj -g -y
```

手动准备运行依赖时，在所选解释器中安装 imageio-ffmpeg 与支持所需草稿格式的 pyJianYingDraft。已有 SRT 不需要下载转写模型；转写只在明确请求时按需准备 faster-whisper。

审稿脚本 `scripts/review_srt.py` 只使用 Python 标准库。`prepare` 和 `check` 均不访问网络或扫描媒体；使用方法见 [SRT 审稿流程](srt-review.md)。运行 `scripts/doctor.py` 可检查脚本入口及媒体环境。

安装器将实际解释器写入 LEISKILL_PYTHON 和 `%LOCALAPPDATA%/leiskill/runtime.json`。手动安装需使用已核验依赖的同一个解释器；避免在系统 Python 与独立环境之间混用。

JY_INSTALL_DIR 可指定含 JianyingPro.exe 的版本目录，JY_USER_DATA 指定用户数据目录；JJ_FONT_PATH 指定用户提供的字幕字体，默认无字幕时无需字体。运行工具的开源许可与剪映组件的使用授权分别确认；更换审稿流程不等于草稿加解密路径已获商用授权。
