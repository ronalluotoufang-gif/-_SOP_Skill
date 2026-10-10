#!/usr/bin/env python3
"""Regression tests for the inventory validator and renderer (standard library only).

Run from anywhere:  python3 tests/run_tests.py
Each case mutates assets/example_inventory.json, runs the validator and checks the exit code and
that the expected message appears. Also checks that a V1.2-style inventory still validates and renders.
"""

from __future__ import annotations

import copy
import json
import subprocess
import sys
import tempfile
from html.parser import HTMLParser
from pathlib import Path

SKILL = Path(__file__).resolve().parent.parent
VALIDATE = SKILL / "scripts" / "validate_inventory.py"
RENDER = SKILL / "scripts" / "render_asset_inventory_html.py"
EXAMPLE = json.loads((SKILL / "assets" / "example_inventory.json").read_text(encoding="utf-8"))

results: list[tuple[bool, str]] = []


def run_validate(path: Path) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, "-I", str(VALIDATE), str(path)], capture_output=True, text=True)


def case(tmp: Path, name: str, mutate, expect_error: bool, fragment: str) -> None:
    data = copy.deepcopy(EXAMPLE)
    mutate(data)
    path = tmp / f"{name}.json"
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    proc = run_validate(path)
    ok = (proc.returncode == 1) == expect_error and fragment in proc.stdout
    results.append((ok, name))
    if not ok:
        print(f"--- {name} failed (exit {proc.returncode}, expected error={expect_error}, fragment={fragment!r})\n{proc.stdout}")


class Balance(HTMLParser):
    VOID = {"meta", "br", "hr", "img", "input", "link"}

    def __init__(self) -> None:
        super().__init__()
        self.stack: list[str] = []
        self.bad: list[str] = []

    def handle_starttag(self, tag, attrs):
        if tag not in self.VOID:
            self.stack.append(tag)

    def handle_endtag(self, tag):
        if tag in self.VOID:
            return
        if self.stack and self.stack[-1] == tag:
            self.stack.pop()
        else:
            self.bad.append(tag)


def render_ok(tmp: Path, name: str, data: dict, must_contain: list[str]) -> None:
    src = tmp / f"{name}.json"
    out = tmp / f"{name}.html"
    src.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    proc = subprocess.run([sys.executable, "-I", str(RENDER), str(src), "--out", str(out)], capture_output=True, text=True)
    ok = proc.returncode == 0 and out.exists()
    if ok:
        text = out.read_text(encoding="utf-8")
        parser = Balance()
        parser.feed(text)
        ok = not parser.stack and not parser.bad and all(item in text for item in must_contain)
    results.append((ok, f"render:{name}"))
    if not ok:
        print(f"--- render:{name} failed\n{proc.stderr}")


def main() -> int:
    with tempfile.TemporaryDirectory() as raw:
        tmp = Path(raw)

        # baseline
        proc = run_validate(SKILL / "assets" / "example_inventory.json")
        results.append((proc.returncode == 0 and "错误 0 条" in proc.stdout, "example validates"))

        # structure and gates
        case(tmp, "d_without_failure_mode", lambda d: d["props"][1]["generation_risk"].update(failure_mode=""), True, "failure_mode")
        case(tmp, "ref_not_in_scene_index", lambda d: d["props"][0]["source_refs"].append("E09-9"), True, "不在 scene_index")
        case(tmp, "missing_asset_type", lambda d: d["props"][0].pop("asset_type"), True, "asset_type")
        case(tmp, "gate_without_reason", lambda d: d["scenes"][0]["gate_reasons"].pop("D"), True, "gate_reasons")
        case(tmp, "duplicate_id", lambda d: d["props"][1].update(id=d["props"][0]["id"]), True, "id 重复")
        case(tmp, "bad_forms", lambda d: d["props"][0]["deliverable_spec"].update(forms=["三视图"]), True, "forms")
        case(tmp, "conditional_anchor_without_when", lambda d: d["characters"][0]["visible_anchors"][1].pop("visible_when"), True, "visible_when")
        case(tmp, "unknown_episode_asset", lambda d: d["episode_assets"][0].update(new_props=["prop-ghost"]), True, "不存在的资产 id")
        case(tmp, "related_asset_missing", lambda d: d["characters"][0].update(related_assets=["prop-ghost"]), True, "related_assets")

        # modes
        case(tmp, "delta_without_changes", lambda d: d["meta"].update(mode="delta"), True, "delta.changes")
        case(tmp, "preview_without_stability", lambda d: (d["meta"].update(mode="preview", provisional=True), d.update(episode_assets=[])), True, "stability")

        # audio
        case(tmp, "bgm_without_scene", lambda d: d["audio_plan"]["bgm_library"][0].update(scene_ids=[], applies_to=[]), True, "适用场景")
        case(tmp, "bgm_scene_missing", lambda d: d["audio_plan"]["bgm_library"][0].update(scene_ids=["scene-ghost"]), True, "scene_ids 引用了不存在")
        case(tmp, "bgm_bad_recurrence", lambda d: d["audio_plan"]["bgm_library"][0].update(recurrence="随便"), True, "recurrence")
        case(tmp, "voice_without_tier", lambda d: d["audio_plan"]["voice_direction"][1].pop("role_tier"), True, "role_tier")
        case(tmp, "cue_bgm_missing", lambda d: d["audio_plan"]["cue_sheet"][0].update(bgm_id="bgm-ghost"), True, "bgm_id 不存在")

        # warnings only
        case(tmp, "banned_naming_warns", lambda d: d["scenes"][0]["continuity_notes"].append("伙计头站在布帘旁"), False, "禁用写法")
        case(tmp, "plot_field_warns", lambda d: d["characters"][0].update(narrative_function=["剧情说明"]), False, "剧情功能")
        case(tmp, "missing_audio_warns", lambda d: d.update(audio_plan={}), False, "audio_skipped")

        skipped = copy.deepcopy(EXAMPLE)
        skipped["audio_plan"] = {}
        skipped["meta"]["audio_skipped"] = True
        path = tmp / "audio_skipped.json"
        path.write_text(json.dumps(skipped, ensure_ascii=False), encoding="utf-8")
        proc = run_validate(path)
        results.append((proc.returncode == 0 and "audio_skipped" not in proc.stdout, "audio_skipped suppresses warning"))

        # backward compatibility: a V1.2-style inventory (no schema_version, gates or audio)
        legacy = {
            "meta": {"title": "旧版示例", "report_version": "1.1", "source_scope": "示例", "source_files": [], "generated_date": "2026-01-01"},
            "characters": [{"id": "c1", "name": "甲", "source_refs": ["E01-1"], "inclusion_reason": "跨集复用", "visible_anchors": ["青布长衫"], "needs_confirmation": []}],
            "scenes": [{"id": "s1", "name": "堂屋", "source_refs": ["E01-1"], "inclusion_reason": "跨集复用", "visible_anchors": ["长桌"], "needs_confirmation": []}],
            "props": [{"id": "p1", "name": "字条", "source_refs": ["E02-1"], "inclusion_reason": "后续比对", "visible_anchors": ["三行字"], "needs_confirmation": []}],
            "selection_policy": [], "non_prebuilt": [], "episode_assets": [], "continuity_checks": [],
        }
        path = tmp / "legacy.json"
        path.write_text(json.dumps(legacy, ensure_ascii=False), encoding="utf-8")
        proc = run_validate(path)
        results.append((proc.returncode == 0, "legacy validates leniently"))
        render_ok(tmp, "legacy", legacy, ["制作总表"])

        # rendering of the example, with the pieces a reader must see
        render_ok(tmp, "example", copy.deepcopy(EXAMPLE), ["制作总表", "固定 BGM 建议", "场景与固定 BGM 对照", "人物音色", "最可能出的错"])

    failed = [name for ok, name in results if not ok]
    print(f"{len(results) - len(failed)}/{len(results)} 通过")
    for name in failed:
        print("失败：", name)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
