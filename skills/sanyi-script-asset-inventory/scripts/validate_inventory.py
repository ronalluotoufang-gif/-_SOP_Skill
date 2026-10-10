#!/usr/bin/env python3
"""Validate a Sanyi pre-production inventory JSON before rendering.

Exit code 0: no errors (warnings may exist). Exit code 1: at least one error.
Inventories without meta.schema_version "1.3" are checked leniently: problems that
only concern V1.3 fields are reported as warnings so older reports still pass.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

ASSET_GROUPS = ("characters", "scenes", "props")
REQUIRED_ARRAYS = ("characters", "scenes", "props", "episode_assets", "continuity_checks")
GATES = {"R", "E", "D"}
RISK_TYPES = {"T", "S", "P", "F", "M", "X"}
FORMS = {
    "character_sheet", "form_sheet", "pose_pack", "space_plan",
    "layout_pages", "evidence_sheet", "fx_keyframes", "photo_ref",
}
PROP_TYPES = {"证物道具", "规则视觉", "版式包", "形态素材"}
MODES = {"full", "delta", "preview"}
DELTA_CHANGES = {"kept", "added", "upgraded", "downgraded", "removed", "relocated"}
VISIBILITY = {"always", "conditional", "one_shot"}
VOICE_TIERS = {"主角", "配角", "群声"}
BGM_RECURRENCE = {"固定主题", "段落氛围", "不固定"}
REF_PATTERN = re.compile(r"^[A-Za-z]+\d+[A-Za-z]?(-\d+[A-Za-z]?)?$")


class Report:
    def __init__(self) -> None:
        self.errors: list[str] = []
        self.warnings: list[str] = []
        self.legacy: dict[str, int] = {}

    def error(self, path: str, message: str) -> None:
        self.errors.append(f"{path}：{message}")

    def warn(self, path: str, message: str) -> None:
        self.warnings.append(f"{path}：{message}")

    def strict_or_warn(self, strict: bool, path: str, message: str) -> None:
        if strict:
            self.error(path, message)
        else:
            # Older inventories lack many V1.3 fields; summarise instead of one line per asset.
            self.legacy[message] = self.legacy.get(message, 0) + 1


def is_nonempty_list(value: Any) -> bool:
    return isinstance(value, list) and len(value) > 0


def check_anchors(report: Report, path: str, anchors: Any) -> None:
    if anchors is None:
        return
    if not isinstance(anchors, list):
        report.error(path, "visible_anchors 必须是数组")
        return
    for index, anchor in enumerate(anchors):
        here = f"{path}[{index}]"
        if isinstance(anchor, str):
            continue
        if not isinstance(anchor, dict) or not anchor.get("text"):
            report.error(here, "锚点应为字符串，或带 text 的对象")
            continue
        visibility = anchor.get("visibility", "always")
        if visibility not in VISIBILITY:
            report.error(here, f"visibility 取值应为 {sorted(VISIBILITY)}")
        if visibility != "always" and not anchor.get("visible_when"):
            report.error(here, "条件可见锚点必须写 visible_when")


def check_v13_fields(report: Report, strict: bool, path: str, asset: dict[str, Any]) -> None:
    gates = asset.get("gates")
    if not is_nonempty_list(gates) or not set(gates) <= GATES:
        report.strict_or_warn(strict, path, "gates 必须是 R／E／D 的非空子集")
        gates = []
    reasons = asset.get("gate_reasons")
    if not isinstance(reasons, dict):
        if gates:
            report.strict_or_warn(strict, path, "缺少 gate_reasons")
        reasons = {}
    for gate in gates:
        if not str(reasons.get(gate, "")).strip():
            report.strict_or_warn(strict, path, f"{gate} 门缺少 gate_reasons 说明")

    spec = asset.get("deliverable_spec")
    if not isinstance(spec, dict):
        report.strict_or_warn(strict, path, "缺少 deliverable_spec（预制形态）")
    else:
        forms = spec.get("forms")
        if not is_nonempty_list(forms) or not set(forms) <= FORMS:
            report.strict_or_warn(strict, path, f"deliverable_spec.forms 取值应为 {sorted(FORMS)}")
        weight = spec.get("weight")
        if weight not in {"light", "full"}:
            report.strict_or_warn(strict, path, "deliverable_spec.weight 应为 light 或 full")
        elif weight == "light" and ({"R", "E"} & set(gates)) and not str(asset.get("weight_note", "")).strip():
            report.warn(path, "含 R／E 门的资产通常应为 full；确需轻量请在 weight_note 写明理由")
        if not is_nonempty_list(spec.get("must_include")):
            report.warn(path, "deliverable_spec.must_include 为空：下游不知道必须包含什么")

    if "D" in gates:
        risk = asset.get("generation_risk")
        if not isinstance(risk, dict):
            report.strict_or_warn(strict, path, "含 D 门必须写 generation_risk")
        else:
            types = risk.get("types")
            if not is_nonempty_list(types) or not set(types) <= RISK_TYPES:
                report.strict_or_warn(strict, path, f"generation_risk.types 取值应为 {sorted(RISK_TYPES)}")
            if not str(risk.get("failure_mode", "")).strip():
                report.strict_or_warn(strict, path, "generation_risk.failure_mode 不能为空：没有具体失败表现不能走 D 门")


def check_asset(report: Report, strict: bool, group: str, index: int, asset: Any,
                seen_ids: dict[str, str], preview: bool) -> None:
    path = f"{group}[{index}]"
    if not isinstance(asset, dict):
        report.error(path, "必须是对象")
        return
    asset_id = asset.get("id")
    if not asset_id:
        report.error(path, "缺少 id")
    elif asset_id in seen_ids:
        report.error(path, f"id 重复：{asset_id}（已用于 {seen_ids[asset_id]}）")
    else:
        seen_ids[asset_id] = path
    path = f"{group}[{index}]({asset.get('name') or asset_id or '?'})"
    if not asset.get("name"):
        report.error(path, "缺少 name")
    if not is_nonempty_list(asset.get("source_refs")):
        report.error(path, "缺少 source_refs")
    if not str(asset.get("inclusion_reason", "")).strip() and not asset.get("gate_reasons"):
        report.strict_or_warn(strict, path, "缺少入库理由（V1.3 用 gate_reasons，旧版用 inclusion_reason）")
    if strict:
        for key in ("narrative_function", "dramatic_function", "usage"):
            if asset.get(key):
                report.warn(path, f"{key} 属剧情功能，与制作无关，清单不显示，建议删除")
    if "needs_confirmation" not in asset:
        report.warn(path, "缺少 needs_confirmation 字段（没有待确认时也应写空数组）")
    if group == "props":
        if asset.get("asset_type") not in PROP_TYPES:
            report.strict_or_warn(strict, path, f"asset_type 必填，取值应为 {sorted(PROP_TYPES)}")
    check_anchors(report, f"{path}.visible_anchors", asset.get("visible_anchors"))
    check_v13_fields(report, strict, path, asset)
    if preview and asset.get("stability") not in {"stable", "volatile"}:
        report.strict_or_warn(strict, path, "preview 模式每条资产必须标 stability")
    states = asset.get("production_states") or []
    state_ids: set[str] = set()
    for s_index, state in enumerate(states):
        s_path = f"{path}.production_states[{s_index}]"
        if not isinstance(state, dict) or not state.get("id") or not state.get("name"):
            report.error(s_path, "状态卡需要 id 与 name")
            continue
        if state["id"] in state_ids or state["id"] in seen_ids:
            report.error(s_path, f"状态卡 id 重复：{state['id']}")
        state_ids.add(state["id"])


def iter_refs(node: Any, path: str = ""):
    """Yield (path, ref) for every source_refs entry and first_seen value."""
    if isinstance(node, dict):
        for key, value in node.items():
            here = f"{path}.{key}" if path else key
            if key == "source_refs" and isinstance(value, list):
                for ref in value:
                    yield here, ref
            elif key == "first_seen" and isinstance(value, str):
                yield here, value
            elif key != "scene_index":
                yield from iter_refs(value, here)
    elif isinstance(node, list):
        for i, item in enumerate(node):
            yield from iter_refs(item, f"{path}[{i}]")


def check_refs(report: Report, data: dict[str, Any]) -> None:
    index = data.get("meta", {}).get("scene_index")
    index_set = set(index) if isinstance(index, list) else None
    if index_set is None:
        report.warn("meta.scene_index", "未提供场次索引，无法核对 source_refs 是否真实存在（建议提供）")
    for path, ref in iter_refs(data):
        if not isinstance(ref, str) or not REF_PATTERN.match(ref):
            report.warn(path, f"来源定位格式异常：{ref!r}（期望如 E03-2）")
            continue
        if index_set is None:
            continue
        if ref in index_set:
            continue
        if "-" not in ref and any(item.startswith(ref + "-") for item in index_set):
            continue
        report.error(path, f"来源定位 {ref} 不在 scene_index 中")


def walk_strings(node: Any, path: str = ""):
    if isinstance(node, str):
        yield path, node
    elif isinstance(node, dict):
        for key, value in node.items():
            if key == "naming_registry":
                continue
            yield from walk_strings(value, f"{path}.{key}" if path else key)
    elif isinstance(node, list):
        for i, item in enumerate(node):
            yield from walk_strings(item, f"{path}[{i}]")


def check_naming(report: Report, data: dict[str, Any]) -> None:
    registry = data.get("meta", {}).get("naming_registry")
    if registry is None:
        report.warn("meta.naming_registry", "未建命名登记，无法检查称谓漂移（建议建立）")
        return
    if not isinstance(registry, list):
        report.error("meta.naming_registry", "必须是数组")
        return
    for entry in registry:
        if not isinstance(entry, dict) or not entry.get("canonical"):
            report.error("meta.naming_registry", "每条需要 canonical")
            continue
        for banned in entry.get("banned", []):
            if not banned:
                continue
            for path, text in walk_strings(data):
                if banned in text:
                    report.warn(path, f"出现禁用写法“{banned}”，规范名应为“{entry['canonical']}”")


def check_links(report: Report, data: dict[str, Any], all_ids: set[str], strict: bool) -> None:
    for group in ASSET_GROUPS:
        for index, asset in enumerate(data.get(group, [])):
            for related in asset.get("related_assets", []) or []:
                if related not in all_ids:
                    report.error(f"{group}[{index}]({asset.get('name', '?')}).related_assets", f"引用了不存在的资产 id：{related}")
    for index, row in enumerate(data.get("episode_assets", [])):
        for key in ("new_characters", "new_scenes", "new_props"):
            for asset_id in row.get(key, []) or []:
                if asset_id not in all_ids:
                    report.error(f"episode_assets[{index}].{key}", f"引用了不存在的资产 id：{asset_id}")
    for index, row in enumerate(data.get("non_prebuilt", [])):
        path = f"non_prebuilt[{index}]({row.get('item', '?')})"
        for key in ("item", "tier", "reason"):
            if not str(row.get(key, "")).strip():
                report.error(path, f"缺少 {key}")
        if not is_nonempty_list(row.get("source_refs")):
            report.warn(path, "缺少 source_refs")
    for index, row in enumerate(data.get("continuity_checks", [])):
        path = f"continuity_checks[{index}]({row.get('item', '?')})"
        for key in ("category", "item", "issue", "minimum_action"):
            if not str(row.get(key, "")).strip():
                report.warn(path, f"缺少 {key}")
    audio = data.get("audio_plan") or {}
    if audio:
        tiers = {a.get("id"): a.get("tier") for a in data.get("characters", [])}
        bgm_ids = {item.get("id") for item in audio.get("bgm_library", [])}
        for index, row in enumerate(audio.get("cue_sheet", [])):
            if row.get("bgm_id") and row["bgm_id"] not in bgm_ids:  # empty bgm_id means "no BGM here"
                report.error(f"audio_plan.cue_sheet[{index}]", f"bgm_id 不存在：{row.get('bgm_id')}")
        for index, row in enumerate(audio.get("voice_direction", [])):
            path = f"audio_plan.voice_direction[{index}]({row.get('name', row.get('character_id', '?'))})"
            if row.get("character_id") and row["character_id"] not in all_ids:
                report.warn(path, f"character_id 不在角色清单中：{row['character_id']}")
            tier = row.get("role_tier") or tiers.get(row.get("character_id"))
            if tier not in VOICE_TIERS:
                report.strict_or_warn(strict, path, f"需要层级 role_tier（{'／'.join(sorted(VOICE_TIERS))}），音色建议要区分主角与配角")
            required_keys = ("voice_profile", "avoid") if tier == "群声" else ("voice_profile", "state_switches", "avoid")
            for key in required_keys:
                if not is_nonempty_list(row.get(key)):
                    report.warn(path, f"{key} 为空")
        for index, row in enumerate(audio.get("bgm_library", [])):
            path = f"audio_plan.bgm_library[{index}]({row.get('name', row.get('id', '?'))})"
            if not is_nonempty_list(row.get("scene_ids")) and not is_nonempty_list(row.get("applies_to")):
                report.strict_or_warn(strict, path, "必须写适用场景（scene_ids 或 applies_to）：BGM 要能回答“用在哪些场景”")
            for scene_id in row.get("scene_ids", []) or []:
                if scene_id not in all_ids:
                    report.error(path, f"scene_ids 引用了不存在的资产 id：{scene_id}")
            if row.get("recurrence") not in BGM_RECURRENCE:
                report.strict_or_warn(strict, path, f"recurrence 取值应为 {sorted(BGM_RECURRENCE)}")
            for key in ("music_profile", "entry_exit", "avoid"):
                if not is_nonempty_list(row.get(key)):
                    report.warn(path, f"{key} 为空：缺少可执行的 BGM 建议")


def check_mode(report: Report, data: dict[str, Any], strict: bool) -> str:
    meta = data["meta"]
    mode = meta.get("mode", "full")
    if mode not in MODES:
        report.error("meta.mode", f"取值应为 {sorted(MODES)}")
        return "full"
    if mode == "preview":
        if meta.get("provisional") is not True:
            report.strict_or_warn(strict, "meta.provisional", "preview 模式必须为 true，首页才会标注非正式")
        if data.get("episode_assets"):
            report.warn("episode_assets", "preview 模式不建议写按集新增表（集号可能变动）")
    if mode == "delta":
        delta = data.get("delta")
        if not isinstance(delta, dict) or not is_nonempty_list(delta.get("changes")):
            report.error("delta", "delta 模式必须提供 delta.changes")
        else:
            if not delta.get("base_report"):
                report.warn("delta.base_report", "建议注明基于哪一版旧清单")
            for index, change in enumerate(delta["changes"]):
                path = f"delta.changes[{index}]"
                if change.get("change") not in DELTA_CHANGES:
                    report.error(path, f"change 取值应为 {sorted(DELTA_CHANGES)}")
                if not str(change.get("reason", "")).strip():
                    report.error(path, "缺少 reason：变化必须有理由")
    return mode


def summarize(data: dict[str, Any]) -> list[str]:
    lines = []
    for group, label in (("characters", "角色"), ("scenes", "场景"), ("props", "道具／规则视觉／版式包")):
        lines.append(f"{label}：{len(data.get(group, []))}")
    gate_count = {gate: 0 for gate in sorted(GATES)}
    for group in ASSET_GROUPS:
        for asset in data.get(group, []):
            for gate in asset.get("gates", []) or []:
                if gate in gate_count:
                    gate_count[gate] += 1
    lines.append("按门计数（可重叠）：" + "、".join(f"{k}={v}" for k, v in gate_count.items()))
    lines.append(f"非预制项：{len(data.get('non_prebuilt', []))}")
    pending = sum(len(a.get("needs_confirmation", []) or []) for g in ASSET_GROUPS for a in data.get(g, []))
    lines.append(f"资产内待确认：{pending}；连续性检查：{len(data.get('continuity_checks', []))}")
    return lines


def validate(data: Any) -> tuple[Report, list[str]]:
    report = Report()
    if not isinstance(data, dict):
        report.error("根对象", "必须是 JSON 对象")
        return report, []
    if not isinstance(data.get("meta"), dict):
        report.error("meta", "缺少 meta 或不是对象")
        return report, []
    missing = [key for key in REQUIRED_ARRAYS if key not in data]
    for key in missing:
        report.error(key, "缺少顶层字段")
    for key in REQUIRED_ARRAYS:
        if key in data and not isinstance(data[key], list):
            report.error(key, "必须是数组")
    if missing:
        return report, []
    for key in ("selection_policy", "non_prebuilt"):
        if key not in data:
            report.warn(key, "缺少该字段（没有内容时应写空数组）")
    if "audio_plan" in data and not isinstance(data["audio_plan"], dict):
        report.error("audio_plan", "必须是对象")

    strict = str(data["meta"].get("schema_version", "")).startswith("1.3")
    if not strict:
        report.warn("meta.schema_version", "未声明 1.3：按旧版宽松检查，V1.3 新字段缺失只给警告")
    mode = check_mode(report, data, strict)
    if strict and mode == "full" and not data.get("audio_plan") and not data["meta"].get("audio_skipped"):
        report.warn("audio_plan", "full 模式默认应附人物音色与固定 BGM 建议；确实不需要请在 meta 写 audio_skipped: true")

    seen_ids: dict[str, str] = {}
    for group in ASSET_GROUPS:
        for index, asset in enumerate(data[group]):
            check_asset(report, strict, group, index, asset, seen_ids, mode == "preview")
    all_ids = set(seen_ids)
    check_links(report, data, all_ids, strict)
    check_refs(report, data)
    check_naming(report, data)
    return report, summarize(data)


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate a Sanyi asset inventory JSON.")
    parser.add_argument("inventory", type=Path)
    args = parser.parse_args()
    try:
        data = json.loads(args.inventory.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"无法读取或解析 JSON：{exc}")
        return 1
    report, summary = validate(data)
    for line in summary:
        print(line)
    print()
    for message in report.errors:
        print(f"[错误] {message}")
    for message in report.warnings:
        print(f"[警告] {message}")
    for message, count in sorted(report.legacy.items(), key=lambda item: -item[1]):
        print(f"[旧版清单] {count} 处：{message}")
    print(f"\n错误 {len(report.errors)} 条，警告 {len(report.warnings)} 条。")
    return 1 if report.errors else 0


if __name__ == "__main__":
    sys.exit(main())
