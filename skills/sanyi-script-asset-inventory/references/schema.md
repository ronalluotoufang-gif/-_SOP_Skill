# 制作前资产清单 JSON 结构 V1.3

V1.3 在 V1.2 基础上**新增字段**，没有删除字段。`meta.schema_version` 为 `"1.3"` 时，校验脚本按 V1.3 严格检查；缺省时按旧版宽松检查，新字段缺失只给警告，旧清单仍能校验和渲染。

根对象必须包含以下数组；没有内容时使用空数组，不删除字段。

```json
{
  "meta": {
    "schema_version": "1.3",
    "title": "项目名",
    "report_version": "1.0",
    "mode": "full",
    "provisional": false,
    "source_scope": "第1—10集定稿正文",
    "source_files": ["项目正文.docx"],
    "generated_date": "YYYY-MM-DD",
    "scene_index": ["E01-1", "E01-2", "E02-1"],
    "naming_registry": [
      {"canonical": "入殓师", "aliases": [], "banned": ["验尸员"]}
    ]
  },
  "characters": [],
  "scenes": [],
  "props": [],
  "selection_policy": [],
  "non_prebuilt": [],
  "episode_assets": [],
  "continuity_checks": [],
  "delta": {},
  "audio_plan": {}
}
```

- `mode`：`full`、`delta` 或 `preview`。
- `scene_index`：正文场次索引。提供后，校验脚本会检查所有 `source_refs` 是否真的存在。**建议始终提供。**
- `naming_registry`：规范名、可接受别名、禁用写法。校验脚本会扫描全部文本，发现禁用写法就警告。**`banned` 写“带上下文的错误短语”**（如“夹克办公室”），不要写“夹克”这类常用词，否则清单里正常出现该词也会误报。
- `delta`：`delta` 模式必填，其余模式用 `{}`。
- `audio_plan`：**默认必填**，见下文“声音建议”；确实不需要时在 `meta` 写 `"audio_skipped": true`，`audio_plan` 用 `{}`。

`selection_policy` 是几条简短的预制门槛说明。`non_prebuilt` 为候选项去向，每项使用：

```json
{"item": "名称", "tier": "场景级参考／镜头内生成／并入主场景／不成立的旧拆分／暂缓：范围内无出镜／暂缓：可见形态未写明", "reason": "为何不预制", "source_refs": ["E01-1"], "revisit_when": "（可选）若后续出现何事则重评"}
```

它们不计入主资产总数。“暂缓”类用于：范围内只有名字或声音、没有画面的对象，以及正文只提到但没写可见形态的效果；必须写 `revisit_when`，让下一轮（或 `delta` 模式）知道何时重评。

## 场次定位约定

- 一般写作 `E03-2`（第 3 集第 2 个场次标头）。
- 正文没有标头的转场画面，用字母后缀接在上一个场次后，如 `E04-2b`。
- 同一个标头里含多个地点（如“车内 / 广场”），用后缀拆开，如 `E08-1a`、`E08-1b`；`scene_index` 里按拆开后的写法列出。
- 正文重复集号时，用标题临时区分（如 `E33A`），并写入 `delta.ref_map` 或连续性检查，不替编剧重编集数。

## 所有主资产都有的字段

```json
{
  "id": "char-xxx",
  "name": "规范名",
  "source_refs": ["E01-1", "E04-3"],
  "gates": ["R", "E", "D"],
  "gate_reasons": {"R": "跨集复用，脸与服装不能漂", "E": "第7集要与第3集那张照片比对"},
  "deliverable_spec": {
    "forms": ["character_sheet", "form_sheet"],
    "must_include": ["正文已写的元素，1—5 条"],
    "weight": "full"
  },
  "generation_risk": {
    "types": ["T"],
    "failure_mode": "最可能出什么错，写具体"
  },
  "stability": "stable",
  "needs_confirmation": []
}
```

- `inclusion_reason`（旧版字段）：V1.3 的入库理由由 `gate_reasons` 承担，可省略，避免重复。
- **不写剧情功能。** `narrative_function`、`dramatic_function`、`usage` 属剧情描述，与制作无关，V1.3 不再使用，HTML 不显示，校验会提示删除。
- `tier`（角色）：`主角` 或 `配角`，用于音色建议分层。
- `gates`：取值 `R`、`E`、`D` 的非空子集。**每个门都要在 `gate_reasons` 里有一句话。**
- `deliverable_spec.forms`：`character_sheet`、`form_sheet`、`pose_pack`、`space_plan`、`layout_pages`、`evidence_sheet`、`fx_keyframes`、`photo_ref`。
- `deliverable_spec.weight`：`light`（一张参考页或一组关键帧）或 `full`（完整资产包）。仅 D 门默认 `light`，有 R 或 E 门则 `full`。
- `generation_risk`：**只要 `gates` 含 `D` 就必填**。`types` 取 `T`、`S`、`P`、`F`、`M`、`X`（见 `gates-and-taxonomy.md`），`failure_mode` 不能空。
- `weight_note`：`weight` 为 `light` 但含 R 或 E 门时必须写理由（如背景群演、没有正面画面），否则校验脚本会警告。
- `related_assets`：关联资产 id 数组，用于跨资产引用（如角色的灵魂态由某形态素材承担）；校验脚本会检查 id 是否存在。
- `stability`：`stable` 或 `volatile`，`preview` 模式必填，其他模式可选。
- `needs_confirmation`：待确认事项数组，没有则空数组。

`visible_anchors` 的每一项可以是字符串，也可以是对象，用于条件可见锚点：

```json
{"text": "颈侧旧伤疤", "visibility": "conditional", "visible_when": "仅低头特写可见；其他镜头被衣领遮挡"}
```

`visibility` 取 `always`（默认）、`conditional`、`one_shot`。

## 角色

```json
{
  "id": "char-zhou-ming",
  "name": "周明",
  "tier": "主角",
  "first_seen": "E01-1",
  "source_refs": ["E01-1", "E01-2"],
  "visible_anchors": ["正文明确写出的可见特征"],
  "state_variants": [{"name": "常态", "details": "正文事实", "source_refs": ["E01-1"]}],
  "production_states": [
    {
      "id": "char-xxx-office",
      "name": "状态名",
      "source_refs": ["E01-1"],
      "wardrobe": ["正文明确的服装／鞋履／手持；未写则标为待确认"],
      "hair_makeup_or_cover": ["发妆、口罩、帽子、面具等可见遮挡"],
      "damage_or_soiling": ["伤妆、血污、潮湿、病容等可见状态"],
      "effects_or_visibility": ["灵异特效、镜头不可见规则、必须保留的局部锚点"],
      "change_trigger": "何时从此状态切换，或为什么需要独立制作",
      "needs_confirmation": []
    }
  ],
  "continuity_notes": ["仅资产相关的复用备注"],
  "needs_confirmation": []
}
```

`production_states` 是制作状态卡，不是角色心理或场景标签。只有画面状态需要跨镜头／跨集固定才拆卡；普通吐血、虚弱、淤青不拆。正文未说明是否换装时，不得凭场景名称新建状态。

## 场景

```json
{
  "id": "scene-teahouse-night",
  "name": "老街茶馆·夜间",
  "first_seen": "E01-2",
  "source_refs": ["E01-2", "E02-1"],
  "visible_anchors": ["可画、可核对的空间物件或结构"],
  "state_variants": [{"name": "凌晨营业", "details": "仅正文写明的灯光、门、陈设变化", "source_refs": ["E01-2"]}],
  "continuity_notes": [],
  "needs_confirmation": []
}
```

多子空间的场景包，在 `deliverable_spec.forms` 里写 `space_plan`，并在 `must_include` 写相互方位。

## 叙事道具／规则视觉／版式包／形态素材

```json
{
  "id": "prop-old-key",
  "name": "旧钥匙",
  "asset_type": "证物道具",
  "first_seen": "E01-2",
  "source_refs": ["E01-2", "E03-3"],
  "holders": ["阿青"],
  "visible_anchors": ["正文明确的材质、破损或标记"],
  "state_variants": [{"name": "使用后", "details": "正文明确状态", "source_refs": ["E03-3"]}],
  "continuity_notes": [],
  "needs_confirmation": []
}
```

`asset_type` **必填**，取值：

| 取值 | 含义 |
|---|---|
| `证物道具` | 剧情中被追踪的物件，通常走 E 门 |
| `规则视觉` | 反复调用的能力效果或界面（能力特效、数值界面、转场） |
| `版式包` | 文书、短信、屏幕界面、表格、标签等文字载体，通常走 T 类 D 门 |
| `形态素材` | 反复出现的特殊生物或半透明形态，通常走 X 类 D 门 |

## 按集新增资产

```json
{
  "episode": "E03",
  "new_characters": ["char-xxx"],
  "new_scenes": ["scene-xxx"],
  "new_props": ["prop-xxx"],
  "source_refs": ["E03-1", "E03-2"]
}
```

`preview` 模式不写本表。

## 增量变化（delta 模式）

```json
{
  "delta": {
    "base_report": "V1.1",
    "ref_map": [{"old": "E33A", "new": "E33"}],
    "changes": [
      {"item": "资产名或ID", "change": "kept", "from": "A", "to": "A", "reason": "为何", "source_refs": ["E33-1"]}
    ]
  }
}
```

`change` 取值：`kept`、`added`、`upgraded`、`downgraded`、`removed`、`relocated`。

## 连续性检查

```json
{
  "severity": "待确认",
  "category": "道具状态",
  "item": "旧钥匙",
  "issue": "E03 使用后去向未写明，但 E05 又需要出现。",
  "source_refs": ["E03-3", "E05-1"],
  "minimum_action": "确认是否由阿青保留，或在正文补一处交接。"
}
```

`severity` 常用 `高`、`中`、`待确认`；`category` 例如：道具状态、命名、空间、文字版式、集号。命名漂移（同一对象两种叫法）归 `命名`。

## 声音建议（默认提供）

声音建议是建议层：不替代角色资产事实，不使用具体成品歌曲名作为默认方案，不指向在世演员或配音员，不以未确认的外貌推导声线。声音库不计入视觉资产数量。

```json
{
  "audio_plan": {
    "voice_direction": [
      {
        "character_id": "char-xxx",
        "name": "角色名",
        "role_tier": "主角",
        "source_refs": ["E01-1"],
        "voice_profile": ["音域倾向、质地、语速"],
        "state_switches": ["不同状态下的声音变化，附来源场次"],
        "avoid": ["不应采用的表演或处理"],
        "needs_confirmation": []
      }
    ],
    "bgm_library": [
      {
        "id": "bgm-xxx",
        "name": "主题名",
        "recurrence": "固定主题",
        "scene_ids": ["scene-xxx"],
        "applies_to": ["没有对应资产的段落，如“E05-2 推理段”"],
        "source_refs": ["E01-1"],
        "purpose": "一句话用途",
        "music_profile": ["风格与配器", "BPM 或节拍感"],
        "entry_exit": ["入点", "出点或留白规则"],
        "avoid": ["避免事项"],
        "needs_confirmation": []
      }
    ],
    "cue_sheet": [
      {
        "episodes": "E01—E02",
        "scene": "具体场景",
        "bgm_id": "bgm-xxx",
        "source_refs": ["E01-1"],
        "cue": "何时进入、何时退出",
        "sound_design": "优先的环境声／Foley／静默",
        "purpose": "该声音设计支付的功能"
      }
    ],
    "audio_checks": [
      {
        "item": "需确认项",
        "issue": "版权、语言、分级或音色问题",
        "source_refs": ["E01-1"],
        "minimum_action": "最小确认动作"
      }
    ]
  }
}
```

字段要点：

- `voice_direction`：每个**有台词的角色**一条。`role_tier` 取 `主角`、`配角`、`群声`；已在角色清单里的角色可只写 `character_id`，层级从 `tier` 取。没有对应角色资产的发声者（如两个亡灵的合声、电视播音员、群众呼喊）写 `name` 并标 `群声`。
- `bgm_library.purpose`：这首 BGM 在片中承担的听感作用（旧版字段名 `narrative_function` 仍可读取）。
- `bgm_library.recurrence`：`固定主题`（该场景或效果反复出现，建议整季固定同一首）、`段落氛围`（只服务某一段，后续回访再升级）、`不固定`（只留环境声）。
- `bgm_library.scene_ids`：适用的场景资产或规则视觉资产 id，校验会检查 id 是否存在；**必须能回答“这首 BGM 用在哪些场景”**。没有对应资产的段落写 `applies_to`。
- 场景与固定 BGM 对照由 `scene_ids` 自动生成，没有指定固定 BGM 的场景会明确标出。
- `cue_sheet.bgm_id` 留空表示该段不配 BGM，用 `sound_design` 写拟音替代。
