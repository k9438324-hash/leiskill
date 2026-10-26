# 官方更新

Windows，在已获准更新时运行：

```powershell
& ([scriptblock]::Create((Invoke-RestMethod 'https://raw.githubusercontent.com/k9438324-hash/leiskill/main/install.ps1')))
```

脚本安装本仓库四个技能；已安装的 dbs-script-flow 复用，仅缺失时从它的官方仓库补装。更新前备份本仓库同名技能，不删除其他技能或视频项目。
备份位于 `%LOCALAPPDATA%/leiskill/backups/`。旧版运行环境优先复用，不移动或删除。
只安装技能文件可使用 `npx -y skills add k9438324-hash/leiskill -g --all`，但此命令不会安装 Python 依赖，也不提供本仓库安装器的备份步骤。
