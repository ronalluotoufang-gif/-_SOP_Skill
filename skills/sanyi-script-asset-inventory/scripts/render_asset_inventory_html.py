#!/usr/bin/env python3
"""Render a Sanyi pre-production inventory JSON into one self-contained HTML file.

V1.3 layout: a one-table overview of every prebuilt asset first, collapsible detail cards that only
carry production-relevant facts (what to make, what must appear, visible anchors, states, risks,
open questions), then non-prebuilt items, audio (voices, fixed BGM, scene-to-BGM map) and open issues.
Plot-function fields are not rendered. V1.1/V1.2 inventories still render; missing fields are omitted.
"""

from __future__ import annotations

import argparse
import html
import json
import re
from pathlib import Path
from typing import Any

REQUIRED = ("meta", "characters", "scenes", "props", "episode_assets", "continuity_checks")
GATE_LABELS = {"R": "复用", "E": "证据", "D": "难生成"}
FORM_LABELS = {
    "character_sheet": "角色基型参考", "form_sheet": "状态／形态对照", "pose_pack": "姿态／动作参考组",
    "space_plan": "空间平面与机位约束", "layout_pages": "文字／界面版式页", "evidence_sheet": "证物固定特征表",
    "fx_keyframes": "特效／变形关键帧", "photo_ref": "照片类参考",
}
RISK_LABELS = {
    "T": "文字与版式", "S": "复杂空间／机关", "P": "非常规姿态／动作",
    "F": "多步特效／变形", "M": "群像与精确数量", "X": "非常规形态",
}
CHANGE_LABELS = {
    "kept": "保留", "added": "新增", "upgraded": "升级", "downgraded": "降级",
    "removed": "移除", "relocated": "来源移位",
}
WEIGHT_LABELS = {"light": "轻量参考", "full": "完整资产包"}
TIER_ORDER = ("主角", "配角", "群声")
GROUPS = (("characters", "角色"), ("scenes", "场景"), ("props", "道具"))


def esc(value: Any) -> str:
    return html.escape(str(value if value is not None else "—"))


def lines(values: list[Any] | None) -> str:
    return "<br>".join(esc(value) for value in (values or [])) or "<span class='muted'>—</span>"


def bullets(values: list[Any] | None) -> str:
    if not values:
        return "<span class='muted'>—</span>"
    return "<ul class='tight'>" + "".join(f"<li>{esc(value)}</li>" for value in values) + "</ul>"


def span(refs: list[str] | None) -> str:
    """Compress source refs into episode spans such as E01–E06 or E01、E03、E08."""
    parsed = set()
    for ref in refs or []:
        match = re.match(r"^([A-Za-z]+)(\d+)([A-Za-z]?)", str(ref))
        if match:
            parsed.add((match.group(1), int(match.group(2)), match.group(3)))
    if not parsed:
        return "—"
    ordered = sorted(parsed)
    parts: list[str] = []
    index = 0
    while index < len(ordered):
        prefix, number, suffix = ordered[index]
        end = index
        if not suffix:
            while (end + 1 < len(ordered) and ordered[end + 1][0] == prefix
                   and not ordered[end + 1][2] and ordered[end + 1][1] == ordered[end][1] + 1):
                end += 1
        if end - index >= 2:
            parts.append(f"{prefix}{number:02d}–{prefix}{ordered[end][1]:02d}")
            index = end + 1
        else:
            parts.append(f"{prefix}{number:02d}{suffix}")
            index += 1
    return "、".join(parts)


def pending_count(asset: dict[str, Any]) -> int:
    total = len(asset.get("needs_confirmation") or [])
    for state in asset.get("production_states") or []:
        total += len(state.get("needs_confirmation") or [])
    return total


def kind_label(asset: dict[str, Any], default: str) -> str:
    return asset.get("asset_type") or default


def gate_chips(asset: dict[str, Any]) -> str:
    gates = asset.get("gates") or []
    return "".join(f"<span class='chip gate-{esc(g)}'>{esc(g)} {GATE_LABELS.get(g, '')}</span>" for g in gates) or "<span class='muted'>—</span>"


def form_names(asset: dict[str, Any]) -> str:
    spec = asset.get("deliverable_spec")
    if not isinstance(spec, dict):
        return "<span class='muted'>—</span>"
    return "、".join(esc(FORM_LABELS.get(item, item)) for item in spec.get("forms", [])) or "—"


def weight_chip(asset: dict[str, Any]) -> str:
    spec = asset.get("deliverable_spec")
    weight = spec.get("weight") if isinstance(spec, dict) else None
    if not weight:
        return "<span class='muted'>—</span>"
    return f"<span class='chip w-{esc(weight)}'>{esc(WEIGHT_LABELS.get(weight, weight))}</span>"


def anchor_list(values: list[Any] | None) -> str:
    """Anchors are plain strings or {text, visibility, visible_when} objects."""
    if not values:
        return "<span class='muted'>—</span>"
    rows = []
    for item in values:
        if isinstance(item, dict):
            line = esc(item.get("text", "—"))
            visibility = item.get("visibility", "always")
            if visibility != "always":
                tag = "条件可见" if visibility == "conditional" else "单次可见"
                line += " <span class='chip cond'>{}：{}</span>".format(tag, esc(item.get("visible_when", "未写明")))
            rows.append(f"<li>{line}</li>")
        else:
            rows.append(f"<li>{esc(item)}</li>")
    return "<ul class='tight'>" + "".join(rows) + "</ul>"


def state_variants(values: list[dict[str, Any]] | None) -> str:
    if not values:
        return ""
    rows = "".join("<li><b>{}</b>：{}</li>".format(esc(item.get("name", "状态")), esc(item.get("details", "—"))) for item in values)
    return f"<dt>状态变化</dt><dd><ul class='tight'>{rows}</ul></dd>"


def production_states(values: list[dict[str, Any]] | None) -> str:
    if not values:
        return ""
    labels = (
        ("wardrobe", "服装／手持"), ("hair_makeup_or_cover", "发妆／遮挡"),
        ("damage_or_soiling", "伤妆／污损"), ("effects_or_visibility", "特效／可见限制"),
    )
    cards = []
    for item in values:
        rows = "".join("<div><b>{}</b>：{}</div>".format(label, "；".join(esc(x) for x in item.get(key)))
                       for key, label in labels if item.get(key))
        if item.get("change_trigger"):
            rows += "<div><b>切换</b>：{}</div>".format(esc(item["change_trigger"]))
        if item.get("needs_confirmation"):
            rows += "<div class='mini-confirm'><b>待确认</b>：{}</div>".format("；".join(esc(x) for x in item["needs_confirmation"]))
        cards.append("<div class='state'><b>{}</b> <span class='muted'>{}</span>{}</div>".format(
            esc(item.get("name", "状态")), esc(span(item.get("source_refs"))), rows))
    return "<dt>制作状态卡</dt><dd>" + "".join(cards) + "</dd>"


def spec_block(asset: dict[str, Any]) -> str:
    spec = asset.get("deliverable_spec")
    if not isinstance(spec, dict):
        return ""
    head = "{}　{}".format(form_names(asset), weight_chip(asset))
    must = f"<div><b>必须包含</b>{bullets(spec.get('must_include'))}</div>" if spec.get("must_include") else ""
    note = f"<div class='muted'>轻量理由：{esc(asset['weight_note'])}</div>" if asset.get("weight_note") else ""
    return f"<dt>预制形态</dt><dd><div>{head}</div>{must}{note}</dd>"


def gate_block(asset: dict[str, Any]) -> str:
    gates = asset.get("gates") or []
    if not gates:
        return ""
    reasons = asset.get("gate_reasons") or {}
    rows = "".join("<div><span class='chip gate-{g}'>{g} {label}</span> {why}</div>".format(
        g=esc(g), label=GATE_LABELS.get(g, ""), why=esc(reasons.get(g, "—"))) for g in gates)
    return f"<dt>入库理由</dt><dd>{rows}</dd>"


def risk_block(asset: dict[str, Any]) -> str:
    risk = asset.get("generation_risk")
    if not isinstance(risk, dict):
        return ""
    kinds = "、".join(RISK_LABELS.get(item, item) for item in risk.get("types", []))
    return "<dt>最可能出的错</dt><dd><div><b>{}</b>：{}</div></dd>".format(esc(kinds or "—"), esc(risk.get("failure_mode", "—")))


def asset_card(asset: dict[str, Any], default_kind: str, names: dict[str, str]) -> str:
    pending = asset.get("needs_confirmation") or []
    body = [gate_block(asset), spec_block(asset), risk_block(asset)]
    if not asset.get("gates") and asset.get("inclusion_reason"):
        body.insert(0, f"<dt>入库理由</dt><dd>{esc(asset['inclusion_reason'])}</dd>")
    body.append(f"<dt>可见锚点</dt><dd>{anchor_list(asset.get('visible_anchors'))}</dd>")
    body.append(state_variants(asset.get("state_variants")))
    body.append(production_states(asset.get("production_states")))
    if asset.get("holders") and asset.get("asset_type") == "证物道具":
        body.append(f"<dt>持有人</dt><dd>{lines(asset['holders'])}</dd>")
    if asset.get("continuity_notes"):
        body.append(f"<dt>制作约束</dt><dd>{bullets(asset['continuity_notes'])}</dd>")
    if asset.get("related_assets"):
        body.append("<dt>关联资产</dt><dd>{}</dd>".format("、".join(esc(names.get(item, item)) for item in asset["related_assets"])))
    if pending:
        body.append(f"<dt class='warn'>待确认</dt><dd class='confirm'>{bullets(pending)}</dd>")
    volatile = " <span class='chip volatile'>不稳定</span>" if asset.get("stability") == "volatile" else ""
    tier = f" <span class='chip tier'>{esc(asset['tier'])}</span>" if asset.get("tier") in TIER_ORDER else ""
    return ("<details class='asset' id='{id}'><summary><b>{name}</b> <span class='kind'>{kind}</span>{tier}{volatile}"
            "<span class='sum-right'>{gates} {span}</span></summary><dl>{body}</dl></details>").format(
        id=esc(asset.get("id", "")), name=esc(asset.get("name", "未命名")), kind=esc(kind_label(asset, default_kind)),
        tier=tier, volatile=volatile, gates=gate_chips(asset), span=esc(span(asset.get("source_refs"))), body="".join(body))


def overview_table(data: dict[str, Any]) -> str:
    rows = []
    for group, default_kind in GROUPS:
        for asset in data[group]:
            pending = pending_count(asset)
            rows.append(
                "<tr><td>{kind}</td><td><a href='#{id}'><b>{name}</b></a><div class='small muted'>{id}</div></td>"
                "<td>{gates}</td><td>{forms}</td><td>{weight}</td><td>{span}</td><td>{pending}</td></tr>".format(
                    kind=esc(kind_label(asset, default_kind)), id=esc(asset.get("id", "")), name=esc(asset.get("name", "未命名")),
                    gates=gate_chips(asset), forms=form_names(asset), weight=weight_chip(asset),
                    span=esc(span(asset.get("source_refs"))), pending=f"<span class='pend'>{pending}</span>" if pending else "<span class='muted'>0</span>"))
    head = "<tr><th>类别</th><th>资产</th><th>入库门</th><th>预制形态</th><th>做到什么程度</th><th>出现</th><th>待确认</th></tr>"
    return f"<div class='table-wrap'><table class='overview'><thead>{head}</thead><tbody>{''.join(rows)}</tbody></table></div>"


def non_prebuilt_rows(rows: list[dict[str, Any]]) -> str:
    return "".join("<tr><td><b>{}</b></td><td><span class='chip'>{}</span></td><td>{}</td><td>{}</td></tr>".format(
        esc(row.get("item", "—")), esc(row.get("tier", "—")), esc(row.get("reason", "—")), esc(row.get("revisit_when", "—"))
    ) for row in rows) or "<tr><td colspan='4' class='muted'>无。</td></tr>"


def episode_rows(rows: list[dict[str, Any]], names: dict[str, str]) -> str:
    def block(label: str, ids: list[str] | None) -> str:
        if not ids:
            return ""
        return f"<div><span class='muted'>{label}</span> " + "、".join(esc(names.get(item, item)) for item in ids) + "</div>"
    return "".join("<tr><td><b>{}</b></td><td>{}{}{}</td></tr>".format(
        esc(row.get("episode", "—")), block("角色", row.get("new_characters")), block("场景", row.get("new_scenes")),
        block("道具", row.get("new_props"))) for row in rows) or "<tr><td colspan='2' class='muted'>未提供按集新增记录</td></tr>"


def issue_rows(rows: list[dict[str, Any]]) -> str:
    return "".join("<tr><td><span class='severity'>{}</span></td><td><b>{}</b></td><td>{}</td><td>{}</td></tr>".format(
        esc(row.get("category", "资产连续性")), esc(row.get("item", "—")), esc(row.get("issue", "—")),
        esc(row.get("minimum_action", "—"))) for row in rows) or "<tr><td colspan='4' class='ok'>未发现需确认的资产连续性问题</td></tr>"


def delta_section(delta: dict[str, Any]) -> str:
    if not delta or not delta.get("changes"):
        return ""
    counts: dict[str, int] = {}
    for change in delta["changes"]:
        counts[change.get("change", "")] = counts.get(change.get("change", ""), 0) + 1
    summary = "　".join(f"{CHANGE_LABELS.get(key, key)} {value}" for key, value in counts.items())
    rows = "".join("<tr><td><b>{}</b></td><td><span class='chip'>{}</span></td><td>{}→{}</td><td>{}</td></tr>".format(
        esc(row.get("item", "—")), esc(CHANGE_LABELS.get(row.get("change"), row.get("change", "—"))),
        esc(row.get("from", "—")), esc(row.get("to", "—")), esc(row.get("reason", "—"))) for row in delta["changes"])
    ref_map = ""
    if delta.get("ref_map"):
        ref_map = "<h3>新旧集号对照</h3><table><thead><tr><th>旧</th><th>新</th></tr></thead><tbody>{}</tbody></table>".format(
            "".join("<tr><td>{}</td><td>{}</td></tr>".format(esc(m.get("old")), esc(m.get("new"))) for m in delta["ref_map"]))
    return ("<section id='delta'><h2>相对旧版变化（基于 {base}）</h2><div class='notice wide'>{summary}</div>"
            "<div class='table-wrap'><table><thead><tr><th>项目</th><th>变化</th><th>层级</th><th>原因</th></tr></thead><tbody>{rows}</tbody></table></div>{ref_map}</section>").format(
        base=esc(delta.get("base_report", "旧清单")), summary=summary, rows=rows, ref_map=ref_map)


def naming_block(registry: list[dict[str, Any]] | None) -> str:
    if not registry:
        return ""
    rows = "".join("<tr><td><b>{}</b></td><td>{}</td><td>{}</td></tr>".format(
        esc(item.get("canonical", "—")), lines(item.get("aliases")), lines(item.get("banned"))) for item in registry)
    return ("<details class='plain'><summary>命名登记（规范名／可接受别名／禁用写法）</summary><table><thead><tr><th>规范名</th>"
            "<th>可接受别名</th><th>禁用写法</th></tr></thead><tbody>{}</tbody></table></details>").format(rows)


# ---------------------------------------------------------------- audio

def tier_rank(tier: str | None) -> int:
    return TIER_ORDER.index(tier) if tier in TIER_ORDER else len(TIER_ORDER)


def voice_rows(rows: list[dict[str, Any]], names: dict[str, str], tiers: dict[str, str]) -> str:
    def tier_of(row: dict[str, Any]) -> str | None:
        return row.get("role_tier") or tiers.get(row.get("character_id", ""))
    ordered = sorted(rows, key=lambda row: tier_rank(tier_of(row)))
    return "".join("<tr><td><b>{}</b></td><td>{}</td><td>{}</td><td>{}</td><td>{}</td></tr>".format(
        esc(row.get("name") or names.get(row.get("character_id", ""), "未命名角色")),
        f"<span class='chip tier'>{esc(tier_of(row))}</span>" if tier_of(row) else "<span class='muted'>—</span>",
        bullets(row.get("voice_profile")), bullets(row.get("state_switches")), bullets(row.get("avoid"))
    ) for row in ordered) or "<tr><td colspan='5' class='muted'>未提供人物音色建议。</td></tr>"


def bgm_rows(rows: list[dict[str, Any]], names: dict[str, str]) -> str:
    out = []
    for row in rows:
        where = [names.get(item, item) for item in row.get("scene_ids", []) or []] + list(row.get("applies_to", []) or [])
        recurrence = row.get("recurrence")
        chip = f"<span class='chip rec-{'fixed' if recurrence == '固定主题' else 'other'}'>{esc(recurrence)}</span>" if recurrence else ""
        out.append("<tr><td><b>{name}</b> {chip}<div class='small muted'>{id}</div></td><td>{where}</td><td>{use}</td><td>{profile}</td>"
                   "<td>{entry}</td><td>{avoid}</td></tr>".format(
                       name=esc(row.get("name", "未命名")), chip=chip, id=esc(row.get("id", "")), where=bullets(where),
                       use=esc(row.get("purpose") or row.get("narrative_function") or "—"), profile=bullets(row.get("music_profile")),
                       entry=bullets(row.get("entry_exit")), avoid=bullets(row.get("avoid"))))
    return "".join(out) or "<tr><td colspan='6' class='muted'>未提供 BGM 建议。</td></tr>"


def scene_bgm_map(data: dict[str, Any], library: list[dict[str, Any]], names: dict[str, str]) -> str:
    mapping: dict[str, list[str]] = {}
    for row in library:
        for asset_id in row.get("scene_ids", []) or []:
            mapping.setdefault(asset_id, []).append(row.get("name", row.get("id", "")))
    scene_ids = [scene.get("id", "") for scene in data["scenes"]]
    extra = [asset_id for asset_id in mapping if asset_id not in scene_ids]
    rows = []
    for asset_id in scene_ids + extra:
        themes = mapping.get(asset_id)
        cell = "、".join(esc(item) for item in themes) if themes else "<span class='muted'>未指定固定 BGM（只留环境声或随段落配乐）</span>"
        rows.append(f"<tr><td><b>{esc(names.get(asset_id, asset_id))}</b></td><td>{cell}</td></tr>")
    return "".join(rows)


def cue_rows(rows: list[dict[str, Any]], music_names: dict[str, str]) -> str:
    return "".join("<tr><td>{}</td><td>{}</td><td>{}</td><td>{}</td><td>{}</td></tr>".format(
        esc(row.get("episodes", "—")), esc(row.get("scene", "—")),
        esc(music_names.get(row.get("bgm_id", ""), row.get("bgm_id")) if row.get("bgm_id") else "无 BGM（只留环境声／Foley）"), esc(row.get("cue", "—")),
        esc(row.get("sound_design", "—"))) for row in rows) or "<tr><td colspan='5' class='muted'>未提供调用表。</td></tr>"


def audio_check_rows(rows: list[dict[str, Any]]) -> str:
    return "".join("<tr><td>{}</td><td>{}</td><td>{}</td></tr>".format(
        esc(row.get("item", "—")), esc(row.get("issue", "—")), esc(row.get("minimum_action", "—"))
    ) for row in rows) or "<tr><td colspan='3' class='ok'>无额外声音待确认项。</td></tr>"


def audio_section(data: dict[str, Any], names: dict[str, str]) -> str:
    audio = data.get("audio_plan") or {}
    if not audio:
        return "<section id='audio'><h2>声音建议</h2><p class='muted'>本次未提供声音建议。</p></section>"
    library = audio.get("bgm_library", [])
    music_names = {item.get("id", ""): item.get("name", item.get("id", "")) for item in library}
    tiers = {a.get("id", ""): a.get("tier") for a in data["characters"]}
    return ("<section id='audio'><h2>声音建议</h2><div class='notice wide'>以下是基于剧本内容的制作建议，需导演／声音指导确认，不是正文设定。"
            "经文、歌曲、现成录音需另行确认授权。</div>"
            "<h3>人物音色</h3><div class='table-wrap'><table><thead><tr><th>角色</th><th>层级</th><th>声线方向</th><th>状态切换</th><th>避免</th></tr></thead>"
            "<tbody>{voice}</tbody></table></div>"
            "<h3>固定 BGM 建议</h3><div class='table-wrap'><table><thead><tr><th>BGM</th><th>适用场景</th><th>用途</th><th>风格与配器</th>"
            "<th>进入与退出</th><th>避免</th></tr></thead><tbody>{bgm}</tbody></table></div>"
            "<h3>场景与固定 BGM 对照</h3><div class='table-wrap'><table><thead><tr><th>场景</th><th>固定 BGM</th></tr></thead><tbody>{smap}</tbody></table></div>"
            "<details class='plain'><summary>按集调用点</summary><div class='table-wrap'><table><thead><tr><th>集数</th><th>场景</th><th>BGM</th><th>入点／出点</th>"
            "<th>环境声／Foley</th></tr></thead><tbody>{cue}</tbody></table></div></details>"
            "<h3>声音待确认</h3><div class='table-wrap'><table><thead><tr><th>事项</th><th>原因</th><th>最小确认动作</th></tr></thead><tbody>{checks}</tbody></table></div></section>").format(
        voice=voice_rows(audio.get("voice_direction", []), names, tiers), bgm=bgm_rows(library, names),
        smap=scene_bgm_map(data, library, names), cue=cue_rows(audio.get("cue_sheet", []), music_names),
        checks=audio_check_rows(audio.get("audio_checks", [])))


# ---------------------------------------------------------------- page

def gate_counts(data: dict[str, Any]) -> dict[str, int]:
    counts = {"R": 0, "E": 0, "D": 0}
    for group, _ in GROUPS:
        for asset in data[group]:
            for gate in asset.get("gates", []) or []:
                if gate in counts:
                    counts[gate] += 1
    return counts


def validate(data: dict[str, Any]) -> None:
    missing = [key for key in REQUIRED if key not in data]
    if missing:
        raise ValueError("缺少顶层字段：" + "、".join(missing))
    if not isinstance(data["meta"], dict):
        raise ValueError("meta 必须是对象")
    for key in REQUIRED[1:]:
        if not isinstance(data[key], list):
            raise ValueError(f"{key} 必须是数组")
    if "audio_plan" in data and not isinstance(data["audio_plan"], dict):
        raise ValueError("audio_plan 必须是对象")


def render(data: dict[str, Any]) -> str:
    validate(data)
    names = {item.get("id", ""): item.get("name", item.get("id", "")) for group, _ in GROUPS for item in data[group]}
    for group, _ in GROUPS:
        for item in data[group]:
            for state in item.get("production_states") or []:
                names.setdefault(state.get("id", ""), state.get("name", ""))
    meta = data["meta"]
    mode = meta.get("mode", "full")
    gates = gate_counts(data)
    total = sum(len(data[group]) for group, _ in GROUPS)
    light = sum(1 for group, _ in GROUPS for a in data[group] if (a.get("deliverable_spec") or {}).get("weight") == "light")
    pending = sum(pending_count(a) for group, _ in GROUPS for a in data[group]) + len(data["continuity_checks"])
    banner = ""
    if mode == "preview" or meta.get("provisional"):
        banner = "<div class='banner preview'>预研／非正式：正文仍在修改，只收录稳定项，数量不作为交付数字；标“不稳定”的资产请勿开工。</div>"
    elif mode == "delta":
        banner = "<div class='banner delta'>增量更新：基于 {}，变化见“相对旧版变化”。</div>".format(esc((data.get("delta") or {}).get("base_report", "旧清单")))
    gate_line = ""
    if any(gates.values()):
        gate_line = ("<p class='gate-line'>入库门分布（一项可通过多道门）：<span class='chip gate-R'>R 复用 {R}</span> "
                     "<span class='chip gate-E'>E 证据 {E}</span> <span class='chip gate-D'>D 难生成 {D}</span></p>").format(**gates)
    tokens = {
        "title": esc(meta.get("title", "未命名项目")), "scope": esc(meta.get("source_scope", "未说明")),
        "version": esc(meta.get("report_version", "1.0")), "date": esc(meta.get("generated_date", "未记录")),
        "banner": banner, "gate_line": gate_line,
        "total": str(total), "chars": str(len(data["characters"])), "scenes": str(len(data["scenes"])),
        "props": str(len(data["props"])), "light": str(light),
        "nonprebuilt": str(len(data.get("non_prebuilt", []))), "pending": str(pending),
        "policy": "".join(f"<li>{esc(item)}</li>" for item in data.get("selection_policy", [])),
        "naming": naming_block(meta.get("naming_registry")),
        "overview": overview_table(data),
        "characters": "".join(asset_card(i, "角色", names) for i in data["characters"]) or "<p class='muted'>暂无。</p>",
        "scene_cards": "".join(asset_card(i, "场景", names) for i in data["scenes"]) or "<p class='muted'>暂无。</p>",
        "prop_cards": "".join(asset_card(i, "道具", names) for i in data["props"]) or "<p class='muted'>暂无。</p>",
        "non_prebuilt": non_prebuilt_rows(data.get("non_prebuilt", [])),
        "delta": delta_section(data.get("delta") or {}),
        "nav_delta": "<a href='#delta'>相对旧版</a>" if (data.get("delta") or {}).get("changes") else "",
        "episodes": episode_rows(data["episode_assets"], names), "issues": issue_rows(data["continuity_checks"]),
        "audio": audio_section(data, names),
    }
    document = TEMPLATE
    for key, value in tokens.items():
        document = document.replace(f"@@{key}@@", value)
    return document


def main() -> None:
    parser = argparse.ArgumentParser(description="Render a script inventory as self-contained HTML.")
    parser.add_argument("inventory", type=Path)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    data = json.loads(args.inventory.read_text(encoding="utf-8"))
    document = render(data)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(document, encoding="utf-8")
    print(f"已生成：{args.out}")


TEMPLATE = """<!doctype html><html lang='zh-CN'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'><title>@@title@@｜制作前资产清单</title><style>
:root{--ink:#1f2630;--muted:#6b7480;--line:#e4e8ee;--paper:#f6f7fa;--panel:#fff;--accent:#5b4bd6;--amber:#fff4da;--amber-ink:#8c5b00}
*{box-sizing:border-box}
body{margin:0;background:var(--paper);color:var(--ink);font:14px/1.6 -apple-system,BlinkMacSystemFont,"PingFang SC","Microsoft YaHei",sans-serif}
.layout{display:grid;grid-template-columns:200px minmax(0,1fr);min-height:100vh}
aside{position:sticky;top:0;height:100vh;padding:24px 16px;background:#1f2330;color:#eef0f9}
.brand{font-size:15px;font-weight:700;line-height:1.35;margin-bottom:22px}
.brand small{display:block;color:#a9b1c9;font-weight:500;margin-top:4px}
nav a{display:block;color:#c9cfe1;text-decoration:none;padding:7px 10px;border-radius:8px;margin:2px 0}
nav a:hover{background:#343a50;color:#fff}
main{padding:30px 32px;max-width:1400px;width:100%;margin:auto}
h1{font-size:25px;line-height:1.3;margin:0 0 8px}
h2{font-size:19px;margin:36px 0 12px;padding-top:6px;border-top:2px solid var(--ink)}
h3{font-size:15px;margin:22px 0 10px}
.meta{color:var(--muted)}.meta b{color:var(--ink)}
.small{font-size:12px}.muted{color:var(--muted)}
.notice{background:#eef0ff;border:1px solid #dce1ff;color:#403b66;padding:10px 14px;border-radius:10px}
.wide{margin-bottom:12px}
.banner{padding:10px 14px;border-radius:10px;margin-bottom:16px;font-weight:600}
.banner.preview{background:#ffe9e5;color:#9c2c1a;border:1px solid #f3c2ba}
.banner.delta{background:#e8f3ff;color:#1c4f82;border:1px solid #c5def7}
.metrics{display:grid;grid-template-columns:repeat(4,minmax(110px,1fr));gap:10px;margin:16px 0 8px}
.metric{background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:12px 14px}
.metric strong{display:block;font-size:24px;color:var(--accent);line-height:1.2}.metric span{color:var(--muted);font-size:12px}
.gate-line{margin:8px 0 0}
.table-wrap{overflow-x:auto;margin:8px 0}
table{width:100%;border-collapse:collapse;background:var(--panel);border:1px solid var(--line);border-radius:10px;overflow:hidden}
th,td{padding:9px 11px;text-align:left;vertical-align:top;border-bottom:1px solid var(--line)}
th{font-size:12px;color:var(--muted);background:#fafbfc;white-space:nowrap}
tr:last-child td{border-bottom:0}
table.overview td:first-child{white-space:nowrap;color:var(--muted)}
a{color:var(--accent);text-decoration:none}a:hover{text-decoration:underline}
.chip{display:inline-block;font-size:12px;font-weight:600;padding:0 8px;border-radius:99px;background:#eceef4;color:#45506a;margin-right:4px;line-height:1.7;white-space:nowrap}
.chip.gate-R{background:#e5f1ff;color:#1c4f82}.chip.gate-E{background:#fff0d6;color:#8c5b00}.chip.gate-D{background:#f3e6ff;color:#6a2fa8}
.chip.w-full{background:#e4f4ea;color:#1f6b45}.chip.w-light{background:#f0f1f4;color:#5c6572}
.chip.tier{background:#e8ecf8;color:#34457a}.chip.cond{background:#fff4da;color:#8c5b00;font-weight:500}
.chip.volatile{background:#ffe9e5;color:#9c2c1a}.chip.rec-fixed{background:#e4f4ea;color:#1f6b45}.chip.rec-other{background:#f0f1f4;color:#5c6572}
.pend{display:inline-block;min-width:22px;text-align:center;background:var(--amber);color:var(--amber-ink);border-radius:99px;font-weight:700}
details.asset{background:var(--panel);border:1px solid var(--line);border-radius:10px;margin:8px 0;padding:0}
details.asset>summary{cursor:pointer;padding:10px 14px;list-style:none;display:flex;gap:8px;align-items:center;flex-wrap:wrap}
details.asset>summary::-webkit-details-marker{display:none}
details.asset>summary::before{content:'▸';color:var(--muted)}details.asset[open]>summary::before{content:'▾'}
.kind{font-size:12px;color:var(--accent);font-weight:700}
.sum-right{margin-left:auto;color:var(--muted);font-size:12px}
details.asset dl{margin:0;padding:2px 16px 14px 32px;display:grid;grid-template-columns:110px minmax(0,1fr);gap:8px 14px}
dt{font-size:12px;color:var(--muted);padding-top:2px}dt.warn{color:var(--amber-ink);font-weight:700}
dd{margin:0}dd div{margin:2px 0}
ul.tight{margin:2px 0;padding-left:18px}ul.tight li{margin:1px 0}
.state{background:#f6f7fb;border-radius:8px;padding:7px 10px;margin:4px 0}.state div{margin:2px 0}
.confirm{background:var(--amber);color:var(--amber-ink);border-radius:8px;padding:6px 10px}.mini-confirm{color:var(--amber-ink)}
details.plain{margin:10px 0;background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:8px 14px}
details.plain summary{cursor:pointer;font-weight:600}
.severity{color:var(--amber-ink);background:var(--amber);border-radius:99px;padding:1px 8px;font-size:12px;white-space:nowrap}
.ok{background:#e9f7ef;color:#237244}
footer{color:var(--muted);padding:28px 0 6px;font-size:12px}
@media(max-width:820px){.layout{display:block}aside{position:static;height:auto}nav{display:flex;gap:4px;overflow:auto}nav a{white-space:nowrap}main{padding:18px 14px}.metrics{grid-template-columns:repeat(2,1fr)}details.asset dl{grid-template-columns:1fr}}
</style></head><body><div class='layout'>
<aside>
<div class='brand'>三义制作前整理<small>资产清单 V@@version@@</small>
</div>
<nav>
<a href='#overview'>总表</a>
<a href='#characters'>角色</a>
<a href='#scenes'>场景</a>
<a href='#props'>道具／规则视觉</a>
<a href='#nonprebuilt'>不预制</a>@@nav_delta@@<a href='#episodes'>按集新增</a>
<a href='#issues'>待确认</a>
<a href='#audio'>声音建议</a>
</nav>
</aside>
<main>@@banner@@<section id='overview'>
<h1>@@title@@</h1>
<div class='meta'>
<b>范围：</b>@@scope@@　<b>生成：</b>@@date@@</div>
<div class='metrics'>
<div class='metric'>
<strong>@@total@@</strong>
<span>主资产（角色 @@chars@@／场景 @@scenes@@／道具类 @@props@@）</span>
</div>
<div class='metric'>
<strong>@@light@@</strong>
<span>其中轻量参考</span>
</div>
<div class='metric'>
<strong>@@nonprebuilt@@</strong>
<span>非预制项（去向见下）</span>
</div>
<div class='metric'>
<strong>@@pending@@</strong>
<span>待确认项</span>
</div>
</div>@@gate_line@@<h2>制作总表</h2>
<div class='notice wide'>每一行都是需要预制的资产：点资产名查看必须包含的内容、可见锚点和待确认项。入库门含义：R 跨镜头／跨集保持一致；E 后续要比对；D 提示词难以稳定生成。</div>@@overview@@<details class='plain'>
<summary>本版入库门槛</summary>
<ul>@@policy@@</ul>
</details>@@naming@@</section>
<section id='characters'>
<h2>角色</h2>@@characters@@</section>
<section id='scenes'>
<h2>场景</h2>@@scene_cards@@</section>
<section id='props'>
<h2>道具／规则视觉／形态素材／版式包</h2>@@prop_cards@@</section>
<section id='nonprebuilt'>
<h2>不预制：去向与重评条件</h2>
<div class='table-wrap'>
<table>
<thead>
<tr>
<th>项目</th>
<th>去向</th>
<th>原因</th>
<th>何时重评</th>
</tr>
</thead>
<tbody>@@non_prebuilt@@</tbody>
</table>
</div>
</section>@@delta@@<section id='episodes'>
<h2>按集新增资产</h2>
<div class='table-wrap'>
<table>
<thead>
<tr>
<th>集数</th>
<th>新增</th>
</tr>
</thead>
<tbody>@@episodes@@</tbody>
</table>
</div>
</section>
<section id='issues'>
<h2>资产连续性待确认</h2>
<div class='table-wrap'>
<table>
<thead>
<tr>
<th>类别</th>
<th>资产</th>
<th>问题</th>
<th>最小确认动作</th>
</tr>
</thead>
<tbody>@@issues@@</tbody>
</table>
</div>
</section>@@audio@@<footer>三义剧本制作前整理 Skill V1.3｜JSON 为事实源，HTML 仅用于预览。</footer>
</main>
</div>
</body>
</html>"""


if __name__ == "__main__":
    main()
