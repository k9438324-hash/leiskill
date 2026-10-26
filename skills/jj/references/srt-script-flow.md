# SRT 删稿与切点交接

## 入口

先运行：

```powershell
py -3 scripts/workbench.py content-gate --srt "带时间码字幕.srt"
```

- `action=run_dbs_script_flow`：调用 `/dbs-script-flow`，只处理该 SRT。
- `action=request_timed_srt`：停止媒体处理，只向用户索取带时间码 SRT。
- `action=execute_confirmed_manifest`：直接复用用户确认的 manifest，不重复删稿。

若同时提供 SRT 和已确认 manifest，以 manifest 为准。闸门通过前不得运行 `ingest`、`transcribe`、`prepare-visuals` 或读取联系表。

## `/dbs-script-flow` 输出契约

按自然话题段检查逻辑衔接、重复内容、信息密度、口播流畅度和观众流失点。候选切点逐项包含：

- `id`；
- SRT 原始起止时间码；
- 保留原文；
- 保留或删除理由；
- 逻辑或流失风险；
- 建议顺序。

结尾汇总预计总时长。用户只说“约2.5分钟”时，目标为150秒、验收135—165秒；用户明确的时长覆盖默认值。内容不足时报告缺口，不拼接重复内容补时长。

先在当前对话交付候选切点并等待确认。只有用户确认后，才能转换成 `human_approved=true` 的剪辑 manifest。

## 确认后的执行边界

`/jj` 只把确认区间映射到源素材，校准切点、生成声音预览、准备已选画面、构建独立剪映草稿并验证。声音预览作为 QA 产物留档，默认不要求用户试听或确认；自动检查通过后直接继续。只有自动检查失败、切点无法可靠映射或发现明确音频异常时才暂停。保持切点内容和顺序；吞字或接缝问题只允许在相邻静音边界内微调，并在结果中记录。

字幕默认关闭。用户明确要求字幕时设置：

```json
{"subtitle": {"enabled": true}}
```

未明确要求时使用 `"enabled": false`，草稿不创建字幕轨道。
