"""Verify that every translation_key referenced in code exists in en+fr.

Why this test (G23): rc.5 shipped to a real user with three SelectSelectors
whose ``translation_key`` had no matching translation block in the JSON
files. HA rendered the radio buttons with the raw values (``fixed_cutoff``,
``event_based``, …) instead of human labels. This test catches that
regression before it ships.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent / "custom_components" / "morning_brief"


def _collect_translation_keys() -> set[str]:
    """Scan every .py file for `translation_key="..."` references."""
    keys: set[str] = set()
    for path in ROOT.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        for match in re.finditer(r'translation_key=["\']([^"\']+)["\']', text):
            keys.add(match.group(1))
    return keys


def _load_lang(lang: str) -> dict[str, object]:
    with (ROOT / "translations" / f"{lang}.json").open(encoding="utf-8") as fp:
        return json.load(fp)  # type: ignore[no-any-return]


@pytest.mark.parametrize("lang", ["en", "fr"])
def test_every_translation_key_in_code_has_selector_block(lang: str) -> None:
    """For each `translation_key="X"` in code, expect `selector.X` in JSON."""
    refs = _collect_translation_keys()
    data = _load_lang(lang)
    selectors = set(data.get("selector", {}).keys())  # type: ignore[union-attr]
    missing = refs - selectors
    assert not missing, (
        f"{lang}.json is missing selector.<key> for translation_keys "
        f"used in code: {sorted(missing)}"
    )


@pytest.mark.parametrize("lang", ["en", "fr"])
def test_selector_blocks_have_options_subtree(lang: str) -> None:
    """Every selector.<key> block must carry an `options` dict (non-empty)."""
    data = _load_lang(lang)
    selectors: dict[str, dict[str, object]] = data.get("selector", {})  # type: ignore[assignment]
    bad: list[str] = []
    for key, block in selectors.items():
        if not isinstance(block, dict):
            bad.append(f"{key}: not a dict")
            continue
        opts = block.get("options")
        if not isinstance(opts, dict) or not opts:
            bad.append(f"{key}: missing/empty 'options' dict")
    assert not bad, f"{lang}.json malformed selector blocks: {bad}"


def test_en_and_fr_selector_keys_match() -> None:
    """EN and FR must declare the same selector translation keys (R13)."""
    en_keys = set(_load_lang("en").get("selector", {}).keys())  # type: ignore[union-attr]
    fr_keys = set(_load_lang("fr").get("selector", {}).keys())  # type: ignore[union-attr]
    only_en = en_keys - fr_keys
    only_fr = fr_keys - en_keys
    assert not only_en and not only_fr, (
        f"selector keys differ between EN and FR. Only in EN: {sorted(only_en)}. "
        f"Only in FR: {sorted(only_fr)}."
    )
