# 三义剧本制作前整理（SOP + Skill）V1.3

从**已确认的漫剧／短剧正文**里，筛出需要在出图、出视频之前先设计并归档的资产，生成制作前资产清单（JSON、Markdown、单文件 HTML），并默认附上人物音色和固定 BGM 建议。

## 它解决什么

- **哪些东西该预制**：用三道门判断，通过任一道就入库，并记录是哪一道。
  - **R 复用**：跨镜头、跨集反复出现，重新生成会让观众看出不一致。
  - **E 证据**：后续要比对同一物的文字、纹样、伤痕、位置、页序或持有人。
  - **D 难生成**：只出现一两次，但属于提示词难以稳定生成的类型（文字与界面、复杂空间／机关、非常规姿态、多步特效／变形、群像与精确数量、非常规形态），并且写得出具体失败表现。
- **预制成什么**：每个主资产写明预制形态（角色基型、状态对照、姿态参考、空间平面、版式页、证物特征表、特效关键帧等）、必须包含的内容、做到什么程度（轻量或完整）。
- **声音建议（默认提供）**：主角、配角、群声的音色声线；哪些场景可用固定 BGM，每首 BGM 的风格、节拍感、进入与退出点；场景与固定 BGM 对照表。
- **清单怎么读**：HTML 首页是制作总表（一行一个资产），详情折叠，只含制作需要的信息，不含剧情解释。

## 独立使用

本仓库只含制作前整理这一个 Skill，**不依赖其他 Skill、项目文件或外部服务**。脚本只用 Python 3 标准库（建议 3.9 及以上）。

## 使用许可

可免费安装和使用未经修改的原版 Skill（包括商业项目）；不得修改 Skill 本体或再分发文件。示例文件可在自己的项目中填写和调整。完整条款见 [LICENSE.md](LICENSE.md)。本仓库不是开源项目；GitHub 平台内的查看与 Fork 权利仍按 GitHub 服务条款执行。

## 目录

```text
skills/sanyi-script-asset-inventory/
  SKILL.md                 Skill 入口与执行步骤
  CHANGELOG.md             版本变更
  agents/openai.yaml       显示元信息
  references/
    SOP_V1.3.md            制作前整理 SOP
    gates-and-taxonomy.md  三道门的问法与难生成类型表
    delta-and-preview.md   增量与预研模式
    schema.md              JSON 结构
  scripts/
    validate_inventory.py  渲染前校验
    render_asset_inventory_html.py   JSON 渲染为单文件 HTML
  assets/example_inventory.json      结构示例（虚构）
  tests/run_tests.py       回归测试
examples/example_inventory.html      示例清单的渲染结果
```

## 安装

先从 [GitHub 仓库](https://github.com/ronalluotoufang-gif/-_SOP_Skill)获取文件，再把 Skill 目录复制到你的技能目录。以 Claude Code 为例：

```bash
git clone https://github.com/ronalluotoufang-gif/-_SOP_Skill.git sanyi-script-asset-inventory
cd sanyi-script-asset-inventory
mkdir -p ~/.claude/skills
cp -R skills/sanyi-script-asset-inventory ~/.claude/skills/
```

只想在某个项目里使用时，复制到该项目的 `.claude/skills/` 下。其他支持 `SKILL.md` 的工具，按各自文档放入技能目录。

### Kimi Work

在 Work 模式的新会话中输入 `/` 选择 `plugin-builder`，把 `https://github.com/ronalluotoufang-gif/-_SOP_Skill` 发给它，请它将这个纯 Skill 仓库导入为个人插件并检查依赖。提示登记完成后，打开「插件」→「个人」找到 `sanyi-script-asset-inventory` 并点击安装。

## 怎么用

在对话里提供定稿正文并指定范围，例如：

- “用制作前整理 Skill 整理第 1—10 集，附音色和 BGM 建议。”
- “这是上一版清单 JSON，正文改了，按增量模式更新。”
- “正文还在改，先出一份稳定项的预研清单。”
- “不需要音色和 BGM。”

Skill 会生成清单 JSON（唯一事实源）、Markdown 摘要和 HTML 预览。也可以单独运行脚本：

```bash
python3 skills/sanyi-script-asset-inventory/scripts/validate_inventory.py <inventory.json>
python3 skills/sanyi-script-asset-inventory/scripts/render_asset_inventory_html.py <inventory.json> --out <inventory.html>
python3 skills/sanyi-script-asset-inventory/tests/run_tests.py
```

脚本只负责校验和渲染，不会阅读剧本或判断哪些内容该入库；具体项目的结论须依据该项目正文重新生成。

## 示例

`examples/example_inventory.html` 是用虚构内容生成的示例清单，可直接用浏览器打开查看版面。对应的 JSON 在 `skills/sanyi-script-asset-inventory/assets/example_inventory.json`，可作为新项目的起点。

## 边界

- 这是“从剧本取事实”的整理工具，不改写正文、不补充设定、不设计外观，也不生成提示词、分镜或视频。
- 正文没写明的内容一律进入“待确认”。
- 音色与 BGM 是制作建议，需导演或声音指导确认；经文、歌曲、现成录音需另行确认授权。
- 不要把真实项目的剧本正文或生成的清单提交到公开仓库。

## 版本

当前版本 V1.3.0，变更见 `skills/sanyi-script-asset-inventory/CHANGELOG.md`。旧版 SOP 不随本包分发。
