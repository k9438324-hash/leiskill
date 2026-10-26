# 官方更新

Windows，在已获准更新时运行：

```powershell
& ([scriptblock]::Create((Invoke-RestMethod 'https://raw.githubusercontent.com/k9438324-hash/leiskill/main/install.ps1')))
```

脚本只安装本仓库四个技能；内置审稿流程随 jj 更新，不安装、更新或删除其他 Skill。已有独立 Python 环境继续复用；更新前备份同名 leiskill 技能。
备份位于 `%LOCALAPPDATA%/leiskill/backups/`。旧版安装过的外部审稿技能保持原样，本仓库不再调用它；移除旧技能需用户另行明确要求。
只安装技能文件可使用 `npx -y skills add k9438324-hash/leiskill -g --all`，但此命令不会安装 Python 依赖，也不提供本仓库安装器的备份步骤。
