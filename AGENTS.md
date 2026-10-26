# leiskill 维护规则

## 定位

仓库名 leiskill，展示名“lei 的视频剪辑 Skills”；/jj 是正式且兼容保留的剪辑入口。用户材料、工程与运行日志不得进入公开仓库。

## 真源与修改

catalog.json 是正式技能目录，VERSION 是版本真源；修改时同步 skills/lei/references/catalog.json、SKILL.md、agents/openai.yaml 和文档。正文优先于交接摘要。CLAUDE.md 仅引用本文件。
四个技能各自负责入口、剪辑、只读诊断和明确请求的更新，不凭框架扩展用户权限。新增技能必须有独立输入、输出和真实验证依据，不创建占位能力。

## 验证

提交前运行 `python tools/validate.py` 与 `python -m unittest discover -s tests -v`。改安装器时另外执行 PowerShell 语法与 -CheckOnly 检查。发布后在隔离目录运行 npx 安装并比对技能资源。明确区分静态检查、脚本行为、安装、真实剪映播放与导出。

## 交付边界

切点须由用户确认；默认60fps、无字幕、独立草稿。复用状态与缓存，不改用户原工程。第三方审稿技能从官方单独安装，不重分发其正文或私密材料。
安装更新先备份本仓库同名技能，不删除其他技能、用户素材或项目状态。禁止 git add . 与 git add -A；只暂存明确文件。
