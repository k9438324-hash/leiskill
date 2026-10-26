# 数据契约

## `project-state.json`

包含项目名、源目录、工具版本、预算、各阶段锁和失效状态。`duration` 必须记录 `target_seconds`、`min_seconds`、`max_seconds`、`source`（user/reference）及可选参考文件。用户明确值始终覆盖reference。聊天续接只需要此文件的紧凑摘要。

## 阶段manifest共同字段

```json
{
  "schema_version": 1,
  "project_id": "string",
  "stage": "script|audio|visual|overlay",
  "upstream_hash": "sha256",
  "items": [],
  "human_approved": false
}
```

`script` 还必须包含 `duration_budget.sections`、`subtitles_enabled` 和带时间码的确认内容。`script.items`每项至少包含 `id`、`text`、`target_start`、`target_end`。当 `subtitles_enabled=true` 时，它们同时作为逐句字幕，默认每条不超过12个可见字符；关闭字幕时只用于内容追溯和时长校验，不生成文字轨。`audio.items`保存用户确认的原素材切点与接话提示。`visual.items`增加画面来源、证据对象、景别、裁切及遮挡目的。

兼容导入旧manifest时，`script.items`允许先保存已对齐字幕；原话证据继续由旧manifest的 `imported_from` 追溯。后续人工修改应补齐说话人和保留理由。

## 候选片段

候选文件只保留命中片段及限定语境：素材ID、入出点、文本、关键词、前后语境、命中类型。不得复制整条逐字稿。

## QA最低字段

记录缺素材、源区间越界、时间重叠、空隙、字幕安全区、跨项目路径、响度和锁哈希一致性。错误摘要可以交给模型，完整草稿JSON不可以。

字幕 QA 还必须记录：单条字符数、相邻同文重复、同轨重叠。普通字幕默认模板为 `dalian-zhangge-sanjisonghei-10.7`：`三极宋黑体 超粗.ttf`、字号 `11`、缩放 `1.0`、`x=0`、`y=-0.56`（剪映界面Y=-925）、白色 `#FFFFFF`、强调色 `#FFF589`；黑色阴影参数为 `alpha=0.9`、`diffuse=15`、`distance=5`、`angle=-45`。章节标题使用独立 overlay 轨，不与普通字幕混写。

构建后QA还必须记录：标准草稿文件是否齐全、加密回读是否成功、`draft_info`与`draft_content` ID是否一致、库加载是否成功、草稿注册元数据、缺失素材引用、缺失源路径和同轨重叠。只有这些字段无错误时，`build-jianying` 才能返回 `ok: true`。

`source-index.json` 是同一项目完整素材索引。`index-manifest-sources` 只增加或更新manifest引用，并用 `manifest_sources` 标记本次引用；不得用少量主剪素材覆盖完整索引。

## 标题交付

`qa/delivery-copy.json` 必须同时包含 `video_title` 与 `poster_title`。海报标题控制在20个中文字符以内。它们是草稿交付物，不替代视频内已锁定的字幕或Overlay。
