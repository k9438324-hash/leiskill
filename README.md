# leiskill

**lei 的视频剪辑 Skills**

[![Version](https://img.shields.io/badge/version-0.8.1-2563EB)](VERSION)

面向本地短视频素材的中文剪辑技能包。把带时间码的 SRT、素材目录和目标时长交给助手，先检查原话与删留切点，确认后生成独立、可编辑的剪映草稿。默认 60 fps、无字幕；保留原工程，复用项目缓存。

## 快速开始

**第 1 步：把安装指令发给 AI**

复制下面整段，发给你正在使用的 Codex、Claude、豆包、WorkBuddy 等 AI：

```text
请帮我安装 leiskill（lei 的视频剪辑 Skills）：
https://github.com/k9438324-hash/leiskill

先读取仓库 README 和安装说明，检查你当前是否具备联网、执行本机命令和安装 Skills 的能力。
具备能力时，请按当前操作系统和你所在的 AI 客户端实际执行安装，不要只复述步骤。
Windows 使用仓库官方 install.ps1，安装四个技能、审稿依赖和剪辑运行环境；检查并配置当前客户端的技能入口。
保留已有素材、剪映工程、项目状态和其他技能；更新同名技能前先备份。
安装后核对技能文件，执行环境检查，并说明怎样在当前客户端调用“视频剪辑助手”或“短视频剪辑”。
只有检查通过才能说安装成功；缺少剪映、权限、网络或工具时，明确报告卡在哪一步。
如果你没有本机工具，或当前客户端不支持 Skills，请说明具体限制，再给我最少的手动操作或技能导入方法，不要声称已经安装。
非 Windows 系统可先安装技能文件，但不要把它说成已经具备本仓库的 Windows 剪映运行环境。
```

支持本机工具和 Skills 的客户端可以执行安装；仅聊天的网页或手机版需要按 AI 给出的步骤操作。Claude 的本机执行版为 Claude Code；豆包等客户端是否能直接安装，以当前版本的工具与导入能力为准。

Windows 官方安装器会准备四个技能、缺失的审稿依赖及独立 Python 环境，检查 FFmpeg 和剪映。它使用公共技能目录，并为已安装的 Claude Code、WorkBuddy 配置对应入口。剪映专业版需提前安装并打开一次，AI 客户端需自行登录。[手动安装与故障排查](docs/安装与排障.md)

已有环境、只要技能文件时：

```bash
npx -y skills add k9438324-hash/leiskill -g --all
```

这条命令不安装视频运行依赖。[下载 ZIP](https://github.com/k9438324-hash/leiskill/archive/refs/heads/main.zip) · [详细安装与故障排查](docs/安装与排障.md)

**第 2 步：把材料交给 `/lei`**

安装后重新加载当前 AI 客户端的技能或重启客户端，新建聊天：

```text
/lei 我有带时间码的 SRT 和本地素材，想剪成约 2 分半。先给删留建议，确认后生成可编辑剪映草稿。
字幕：本机 SRT 路径
素材：本机素材目录
```

已有明确任务时可以继续直接用 `/jj`。没有 SRT 或已确认切点时，助手先索取字幕，不提前扫描或转写全部素材。
不支持斜杠命令但能读取技能的客户端，可直接说“使用 leiskill 的视频剪辑助手处理这些材料”。

**第 3 步：确认切点，继续同一聊天**

检查带原始时间码的删留建议、理由、风险和预计时长，回复确认后再构建。后续说“继续”即可；每条视频使用独立项目状态，已锁定阶段复用。

## 技能目录

| 入口 | 用途 | 交出 |
| --- | --- | --- |
| [/lei](skills/lei/SKILL.md) | 不确定从哪里开始、了解用法或继续项目 | 按当前材料选择下一步 |
| [/jj](skills/jj/SKILL.md) | SRT 审阅、确认切点、执行剪辑 | 独立剪映草稿与结构检查 |
| [/lei-doctor](skills/lei-doctor/SKILL.md) | 首次安装、换电脑、依赖报错 | 只读环境检查与缺失项 |
| [/lei-update](skills/lei-update/SKILL.md) | 明确要求更新或重装 | 备份、更新结果与环境核对 |

`dbs-script-flow` 是外部审稿依赖，从官方仓库单独安装，不计入本仓库四个技能。框架参考 dbskill，技能正文与脚本由本项目维护。[框架对照](docs/框架对照.md)

## 能力与验收

- 按 `script → audio → visual → overlay` 锁定，确认切点后不重新猜测内容。
- 检查草稿文件、加密回读、库加载、引用、路径、轨道重叠与时长。
- 区分技能安装、环境通过、草稿结构通过、剪映播放、导出与发布；每一级只报告实际证据。
- 不分发剪映、字体、转写模型或用户素材；不自动上传或发布视频。

重点验证环境为 Windows + Codex。安装器提供公共技能目录、Claude Code 与 WorkBuddy 的入口适配；其他客户端由 AI 根据真实支持情况安装或导入。各客户端的完整交互与视频运行尚未逐一验收。

## 文档与维护

- [新手入门](docs/新手入门.md)：输入示例、常见任务和四个入口。
- [安装与排障](docs/安装与排障.md)：环境、路径、备份和更新。
- [架构与交接](docs/架构与交接.md)：目录真源、职责边界与维护规则。
- [旧版迁移](docs/旧版迁移.md)：jj-skill 改名后的命令与运行环境。
- [更新记录](CHANGELOG.md) · [贡献指南](CONTRIBUTING.md) · [提交问题](https://github.com/k9438324-hash/leiskill/issues)

## 来源

- [dontbesilent2025/dbskill](https://github.com/dontbesilent2025/dbskill)：参考统一入口、交接说明、目录与校验的组织方式；不复制它的技能正文或知识库。
- [vercel-labs/skills](https://github.com/vercel-labs/skills)：技能安装工具。
- [aoguai/pyJianYingDraft](https://github.com/aoguai/pyJianYingDraft)：独立安装的剪映草稿依赖。

第三方依赖遵循各自许可证。本仓库未另行指定授权许可；公开可下载不代表已授予任意再分发或商业使用权。
