# /jj 装修短视频剪辑技能

把带时间码的 SRT 或已确认切点，交给 AI 编程助手生成独立、可编辑的剪映草稿。默认 60 fps、无字幕，保留原工程；切点必须先由用户确认。用项目状态、素材缓存和阶段锁定控制重复工作与模型读取量，实际额度消耗取决于所用模型和素材。

## 下载与安装

[点击下载 ZIP](https://github.com/k9438324-hash/jj-skill/archive/refs/heads/main.zip)

安装本技能（先安装 Node.js LTS 和 Git）：

```powershell
npx -y skills add k9438324-hash/jj-skill --skill jj -g -y
```

安装官方字幕审稿依赖：

```powershell
npx -y skills add dontbesilent2025/dbskill --skill dbs-script-flow -g -y
```

命令安装的是技能文件。运行视频处理还需要 Windows、Python、剪映专业版、FFmpeg 和支持加密草稿的 pyJianYingDraft；详见 [环境配置](skills/jj/references/install.md)。本仓库不包含剪映、字体、模型或用户视频。

## 使用

重新打开 Codex，新建聊天，发送：

> 使用 /jj。字幕：本机 SRT 路径；素材：本机素材目录；目标约 2 分半。先给我带原始时间码的删留建议，等我确认再生成独立草稿。

没有带时间码字幕或已确认切点时，技能先索取 SRT。确认之后按 script → audio → visual → overlay 推进，复用缓存，不重新猜测内容。

结构检查会核对草稿文件、加密回读、库加载、素材引用、路径、轨道重叠与时长；剪映界面播放和导出需要另外验证。

## 依赖与来源

- [skills 安装工具](https://github.com/vercel-labs/skills)
- [dbskill / dbs-script-flow](https://github.com/dontbesilent2025/dbskill)，单独安装，不在此重分发。
- [aoguai/pyJianYingDraft](https://github.com/aoguai/pyJianYingDraft)，支持草稿加密读写的运行依赖，单独安装。

本仓库提供 jj 技能文件下载；第三方依赖各自遵循其许可证。当前版本 0.7.5，首次公开打包。
