# leiskill

**lei 的视频剪辑 Skills**

[![Version](https://img.shields.io/badge/version-0.8.0-2563EB)](VERSION)

面向本地短视频素材的中文剪辑技能包。把带时间码的 SRT、素材目录和目标时长交给助手，先检查原话与删留切点，确认后生成独立、可编辑的剪映草稿。默认 60 fps、无字幕；保留原工程，复用项目缓存。

## 快速开始

**第 1 步：安装**

Windows 打开 PowerShell，粘贴这一整行：

```powershell
& ([scriptblock]::Create((Invoke-RestMethod 'https://raw.githubusercontent.com/k9438324-hash/leiskill/main/install.ps1')))
```

它会安装四个技能与缺失的审稿依赖，补齐 Python 3.12、Git、Node.js，创建或复用独立 Python 环境，安装 FFmpeg 和剪映草稿依赖，最后检查环境。基础工具通过 winget 安装，可能出现 Windows 权限窗口；没有 winget 时给出修复提示。剪映专业版需提前安装并打开一次，Codex 需自行登录。

已有环境、只要技能文件时：

```bash
npx -y skills add k9438324-hash/leiskill -g --all
```

这条命令不安装视频运行依赖。[下载 ZIP](https://github.com/k9438324-hash/leiskill/archive/refs/heads/main.zip) · [详细安装与故障排查](docs/安装与排障.md)

**第 2 步：把材料交给 `/lei`**

安装后重启 Codex，新建聊天：

```text
/lei 我有带时间码的 SRT 和本地素材，想剪成约 2 分半。先给删留建议，确认后生成可编辑剪映草稿。
字幕：本机 SRT 路径
素材：本机素材目录
```

已有明确任务时可以继续直接用 `/jj`。没有 SRT 或已确认切点时，助手先索取字幕，不提前扫描或转写全部素材。

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

重点验证环境为 Windows + Codex。技能文件可被其他支持 Skills 的助手安装，但视频运行与各助手的完整交互尚未逐一验收。

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
