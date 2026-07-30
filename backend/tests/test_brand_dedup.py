"""Brand fuzzy-dedup tests (spec §7, a Phase 1 gap closed this session): rapidfuzz + prefix-
containment merge logic used by scripts/ingest_flipkart.py's brand-loading step. Synthetic cases
plus one check against the real raw dataset (skipped if it isn't present) — see done.MD for why
prefix-containment ended up being the load-bearing signal for *this* dataset specifically (its
brand strings are truncated at a fixed length, not just casing/typo variants)."""

import json
import re
from collections import defaultdict
from pathlib import Path

import pytest

from scripts.ingest_flipkart import fuzzy_merge_brands

RAW_DATASET_PATH = Path(__file__).resolve().parents[2] / "data" / "raw" / "flipkart_fashion_products_dataset.json"


def test_word_order_variants_merge_via_rapidfuzz_not_prefix_containment():
    """Neither string is a literal prefix of the other (different word order), so this exercises
    the rapidfuzz token_sort_ratio signal specifically, not the prefix-containment one."""
    counts = {"nike international": 100, "international nike": 3}
    remap = fuzzy_merge_brands(counts)
    assert remap["international nike"] == "nike international"
    assert remap["nike international"] == "nike international"


def test_truncated_forms_of_the_same_brand_merge_via_prefix_containment():
    counts = {"u.s.polo as": 5, "u.s.polo associati": 12}
    remap = fuzzy_merge_brands(counts)
    # Both truncated forms of "U.S. Polo Association" — the more frequent one wins as canonical.
    assert remap["u.s.polo as"] == remap["u.s.polo associati"] == "u.s.polo associati"


def test_short_generic_brand_names_are_not_swallowed_by_prefix_matching():
    """A single-letter or very short brand entry (this dataset genuinely has "A", "C", "D" as
    distinct brands) must never prefix-match into an unrelated longer brand just because it
    happens to be a literal prefix of it."""
    counts = {"a": 10, "aj styl": 5, "almova": 8, "almova we": 3}
    remap = fuzzy_merge_brands(counts)
    assert remap["a"] == "a"  # too short to ever be a merge anchor
    assert remap["aj styl"] == "aj styl"  # must not get pulled in just because it starts with "a"
    # "almova"/"almova we" both clear the minimum length, so this pair is still expected to merge.
    assert remap["almova"] == remap["almova we"]


def test_unrelated_brands_sharing_only_a_truncated_suffix_do_not_merge():
    """Two different brands truncated to the same generic trailing word (e.g. "...Clothing") must
    not merge just because they share a suffix — only genuine prefix containment should count."""
    counts = {"fuel clothi": 4, "ecoline clothi": 6}
    remap = fuzzy_merge_brands(counts)
    assert remap["fuel clothi"] == "fuel clothi"
    assert remap["ecoline clothi"] == "ecoline clothi"


def test_merge_result_is_deterministic_across_runs():
    counts = {"nike international": 100, "international nike": 3, "adidas originals": 50, "adidas original": 2}
    first = fuzzy_merge_brands(counts)
    second = fuzzy_merge_brands(counts)
    assert first == second


def test_against_the_real_dataset_finds_exactly_the_one_verified_merge():
    """Documented in done.MD: testing this against the actual raw dataset (not just synthetic
    cases) showed the "~325 brands probably have near-duplicates" assumption mostly didn't hold —
    only one genuine pair exists once truncation-driven false positives are correctly excluded."""
    if not RAW_DATASET_PATH.exists():
        pytest.skip("raw dataset not present on this machine")

    with open(RAW_DATASET_PATH, encoding="utf-8") as f:
        records = json.load(f)

    brand_counts: dict[str, int] = defaultdict(int)
    for r in records:
        brand = (r.get("brand") or "").strip()
        brand = re.sub(r"\s+", " ", brand)
        if not brand:
            brand = "Unbranded"
        brand_counts[brand.lower()] += 1

    remap = fuzzy_merge_brands(dict(brand_counts))
    merges = [k for k, canonical in remap.items() if k != canonical]
    assert merges == ["u.s.polo as"]
