# 低额度剪辑SOP

## 默认预算

- 高能力模型最多2次：文字锁定；画面/最终证据审核。
- 快速模型最多2次：候选粗分；动效或QA归类。
- 完整逐字稿、完整素材目录、完整草稿JSON进入模型均为0次。
- 单次候选不超过80段、中文不超过30000字、联系表不超过12张、单批图片不超过6张、manifest摘要不超过20KB。
- 素材搜索限定到用户指定目录，候选文件最多返回20条；扩大目录前先停止并报告当前定位证据。
- 命令日志只返回结论、错误附近30行和必要计数；源码按命中行读取，不整文件回传。
- 单阶段超出20KB文本、6张图片或既定模型次数时停止深化，先交付当前锁定结果和超限原因。

## 命令顺序

```powershell
py -3 scripts/workbench.py content-gate --srt "E:\字幕\项目名.srt"
py -3 scripts/workbench.py init --project "D:\剪辑工作台\项目名" --source "E:\素材目录" --name "项目名" --target-seconds 150 --min-seconds 135 --max-seconds 165
py -3 scripts/workbench.py ingest --project "D:\剪辑工作台\项目名"
py -3 scripts/workbench.py transcribe --project "D:\剪辑工作台\项目名" --min-duration 20
py -3 scripts/workbench.py search --project "D:\剪辑工作台\项目名" --keywords "返潮,铺板,抖音,材料,先干后付,报价"
py -3 scripts/workbench.py gate --project "D:\剪辑工作台\项目名" --payload "...\candidates.json" --stage script
py -3 scripts/workbench.py record-call --project "D:\剪辑工作台\项目名" --tier high
py -3 scripts/workbench.py lock --project "D:\剪辑工作台\项目名" --stage script --input "...\script-manifest.json"
py -3 scripts/workbench.py record-review --project "D:\剪辑工作台\项目名" --stage script --tier high --payload "...\candidates.json"
py -3 scripts/workbench.py lock --project "D:\剪辑工作台\项目名" --stage audio --input "...\audio-manifest.json"
py -3 scripts/workbench.py build-audio-preview --project "D:\剪辑工作台\项目名"
py -3 scripts/workbench.py prepare-visuals --project "D:\剪辑工作台\项目名" --scope selected --proxies --contact-sheets
py -3 scripts/workbench.py preflight --project "D:\剪辑工作台\项目名"
py -3 scripts/workbench.py overlay-handoff --project "D:\剪辑工作台\项目名"
py -3 scripts/workbench.py set-delivery-copy --project "D:\剪辑工作台\项目名" --video-title "视频标题" --poster-title "海报标题"
py -3 scripts/workbench.py build-jianying --project "D:\剪辑工作台\项目名" --draft-root "D:\剪映\JianyingPro Drafts" --name "项目名｜低额度版"
```

后续依次锁定 `audio`、`visual`、`overlay`。`status`只输出紧凑状态，不输出逐字稿内容。

先过 `content-gate`。有 SRT 时完成内置 SRT 审稿与本地提案检查并等待用户确认；已有确认 manifest 时直接执行；两者都没有时停止。用户说“约2.5分钟”时使用150/135/165；用户给出其他区间时按原话设置。脚本manifest必须先写 `duration_budget.sections`；合格素材不足时报告缺口，不复制句子、重复镜头或拉长停顿补时长。

`ingest` 默认只建立完整素材索引。不要在文字阶段传 `--proxies --contact-sheets`；这两个旧参数仅保留兼容。文字确认并锁定 `audio` 后，先运行 `build-audio-preview` 生成 `qa/audio-preview.m4a` 供 QA 留档；本地时长、源区间和构建检查通过后，不等待用户试听，直接使用 `prepare-visuals --scope selected` 处理入选素材。只有自动检查失败、切点无法可靠映射或发现明确音频异常时才暂停。需要从同项目全部素材挑B-roll时，才使用 `--scope all`。音频、代理与联系表均先写入临时文件，成功后原子替换；中断时不得留下可被识别为正式缓存的残片。

已有旧版剪辑manifest可用 `import-manifest --human-approved` 转换为四份manifest，再用 `lock-all` 锁定；这不会重新转写或扫描素材。

## 阶段行为

字幕默认关闭。用户明确要求字幕时，普通口播字幕不显示表达性标点；句首或句尾无信息语气词从字幕删除。原声音频只有在该词能无损独立切除时才删除。

字幕按成品模板逐句落轨：每条只放一个口语短句，默认不超过12个可见字符；上一条结束后下一条才出现。连续两条清洗后文本相同视为重复错误，长段落、同轨叠显或把两句话塞进一个字幕都不得锁定。普通字幕默认三极宋黑体超粗、字号11、缩放100%、`x=0`、`y=-0.56`（剪映界面Y=-925）、白色；黑色阴影使用90%不透明度、15%模糊、距离5、角度-45°。需要强调时改为浅黄 `#FFF589`，不要另复制一条相同字幕叠在上面。章节标题走独立 overlay 轨。

| 阶段 | 本地输出 | 模型可见内容 | 人工确认 |
|---|---|---|---|
| 入库 | 素材索引、指纹 | 统计摘要 | 素材范围与工地 |
| 候选定位 | 逐字稿JSON、关键词候选 | 命中片段及短语境 | 原片归属 |
| 文字锁定 | 干净稿、删减审计 | 原话、说话人、时间码 | 主线与边界 |
| 声音锁定 | 精确切点、声音预览 | 自动检查异常摘要 | 默认无需人工确认；异常时暂停 |
| 画面准备 | 入选素材代理、联系表 | 缓存计数 | 是否扩大到同项目B-roll |
| 画面锁定 | 主画面/B-roll/crop清单 | 每段最多3个候选 | 证据一致性 |
| 动效锁定 | 字幕及Overlay manifest | 已锁定文字和样例 | 安全区与可读性 |
| 构建验收 | 独立剪映草稿、QA | QA摘要及最多6帧 | 播放、导出和发布确认 |

构建返回成功前必须验证：实际时长位于契约区间；`draft_info.json`、`draft_content.json`、`draft_meta_info.json` 均存在且非空；加密内容可以回读；`DraftFolder.load_template` 能加载；素材引用与源路径无缺失；视频/音频同轨无重叠；草稿内注册元数据存在。`validate` 在已有 `qa/build.json` 时必须重复这些检查，不能只检查manifest锁。构建前必须保存视频标题与海报标题，草稿完成报告直接带出两者。

每个阶段完成后只报告产物路径、锁状态、验证结果和下一步。阶段已经锁定且输入指纹未变化时直接复用，不因用户再次说“继续”而重跑。

## 停止条件

出现任一情况停止自动深化：素材定位连续两轮失败；有效内容不足以达到最低时长；将要发生第3次高能力模型判断；文字锁定后主线改变；跨项目素材无法区分；草稿无法稳定解密/生成；缓存键缺少源指纹或工具版本；需要全盘扫描或把完整逐字稿、草稿JSON送入模型才能继续。

降级交付为：已锁定干净稿、声音切点、剪辑manifest和待人工项。不继续生成草稿、导出或动效。

## 缓存失效

- 源文件快速指纹变化：该素材的转写、代理、联系表及引用它的锁全部失效。
- 转写模型或参数变化：只重建转写、搜索和其后的锁。
- script变化：audio、visual、overlay失效。
- audio变化：visual、overlay失效。
- visual变化：只使overlay失效。
- overlay变化：不影响上游。
