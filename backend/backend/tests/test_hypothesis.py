"""
member2/tests/test_hypothesis.py
---------------------------------
Unit tests for member2/hypothesis.py.

Covers:
  1.  Single-channel incident
  2.  Two-channel incident
  3.  Multi-channel (3+ channels) incident
  4.  Simultaneous activation
  5.  Overlapping channel windows
  6.  Non-overlapping channel windows
  7.  Missing / empty temporal relationships
  8.  Insufficient evidence case
  9.  Deterministic output
 10.  Invalid input (missing required keys)
 11.  Correct chronological ordering preserved in chain
 12.  No physical-causality language in any output field
 13.  Confidence bounds 0–1
 14.  Chain links reference real channels from activation_order
"""

from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from typing import Any

import pytest

from member2.hypothesis import SCIENTIFIC_CAVEAT, build_hypothesis

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_EPOCH = datetime(2024, 1, 1, tzinfo=timezone.utc)


def _ts(offset_sec: int = 0) -> datetime:
    return _EPOCH + timedelta(seconds=offset_sec)


def _rel(ch_a: str, t_a: int, ch_b: str, t_b: int, overlap: bool = True) -> dict[str, Any]:
    """Build a minimal temporal relationship dict mirroring characteriser output."""
    # channel_a is always the earlier-activating channel
    if t_b < t_a:
        ch_a, t_a, ch_b, t_b = ch_b, t_b, ch_a, t_a
    gap = float(t_b - t_a)
    return {
        "channel_a": ch_a,
        "channel_b": ch_b,
        "channel_a_start": _ts(t_a).isoformat(),
        "channel_b_start": _ts(t_b).isoformat(),
        "temporal_gap_sec": gap,
        "temporal_precedence": "simultaneous" if gap == 0.0 else "A_before_B",
        "windows_overlap": overlap,
    }


def _all_pairs_rels(channels_and_offsets: list[tuple[str, int]], overlap: bool = True) -> list[dict]:
    """Generate all N*(N-1)/2 pair relationships for a channel list."""
    rels = []
    items = sorted(channels_and_offsets, key=lambda x: (x[1], x[0]))
    for i, (ca, ta) in enumerate(items):
        for cb, tb in items[i + 1:]:
            rels.append(_rel(ca, ta, cb, tb, overlap=overlap))
    return rels


def _make_char(
    sid: int,
    activation_order: list[str],
    offsets: list[int],
    rels: list[dict],
    channel_incident_ids: list[str] | None = None,
) -> dict[str, Any]:
    """Build a minimal char_dict compatible with build_hypothesis."""
    n = len(activation_order)
    if channel_incident_ids is None:
        channel_incident_ids = [f"INC-{i+1}" for i in range(n)]
    return {
        "spacecraft_incident_id": sid,
        "n_channels_affected": n,
        "channels_affected": sorted(activation_order),
        "channel_activation_order": activation_order,
        "channel_temporal_relationships": rels,
        "channel_incident_ids": channel_incident_ids,
        "start_time": _ts(offsets[0]) if offsets else _ts(0),
        "end_time": _ts(max(offsets) + 300) if offsets else _ts(300),
    }


def _make_scores() -> dict[str, Any]:
    """Minimal scores_dict (not used for confidence, but must be accepted)."""
    return {
        "significance_score": 50.0,
        "severity_score": 5.0,
        "investigation_confidence": 0.75,
    }


# ---------------------------------------------------------------------------
# TestSingleChannel
# ---------------------------------------------------------------------------

class TestSingleChannel:
    def _char(self):
        return _make_char(1, ["CH_A"], [0], rels=[])

    def test_returns_dict(self):
        result = build_hypothesis(self._char(), _make_scores())
        assert isinstance(result, dict)

    def test_hypothesis_type_single_channel(self):
        result = build_hypothesis(self._char(), _make_scores())
        assert result["hypothesis_type"] == "single_channel"

    def test_chain_is_empty(self):
        result = build_hypothesis(self._char(), _make_scores())
        assert result["chain"] == []

    def test_confidence_is_zero(self):
        result = build_hypothesis(self._char(), _make_scores())
        assert result["hypothesis_confidence"] == 0.0

    def test_scientific_caveat_present(self):
        result = build_hypothesis(self._char(), _make_scores())
        assert result["scientific_caveat"] == SCIENTIFIC_CAVEAT

    def test_n_corroborating_pairs_zero(self):
        result = build_hypothesis(self._char(), _make_scores())
        assert result["n_corroborating_pairs"] == 0

    def test_required_keys_present(self):
        result = build_hypothesis(self._char(), _make_scores())
        for key in [
            "hypothesis_id", "hypothesis_type", "summary", "chain",
            "supporting_evidence", "hypothesis_confidence", "scientific_caveat",
            "observed_evidence", "temporal_relationships", "n_corroborating_pairs",
        ]:
            assert key in result, f"Missing key: {key}"

    def test_supporting_evidence_has_one_item(self):
        result = build_hypothesis(self._char(), _make_scores())
        assert len(result["supporting_evidence"]) == 1
        assert result["supporting_evidence"][0]["channel"] == "CH_A"

    def test_no_causality_language_in_summary(self):
        result = build_hypothesis(self._char(), _make_scores())
        assert "caused" not in result["summary"].lower()

    def test_hypothesis_id_contains_incident_id(self):
        result = build_hypothesis(self._char(), _make_scores())
        assert "1" in result["hypothesis_id"]


# ---------------------------------------------------------------------------
# TestTwoChannel
# ---------------------------------------------------------------------------

class TestTwoChannel:
    def _char(self, gap: int = 30, overlap: bool = True):
        rels = [_rel("CH_A", 0, "CH_B", gap, overlap=overlap)]
        return _make_char(1, ["CH_A", "CH_B"], [0, gap], rels=rels)

    def test_hypothesis_type_multi_channel(self):
        result = build_hypothesis(self._char(), _make_scores())
        assert result["hypothesis_type"] == "multi_channel"

    def test_chain_has_one_link(self):
        result = build_hypothesis(self._char(), _make_scores())
        assert len(result["chain"]) == 1

    def test_chain_source_is_first_channel(self):
        result = build_hypothesis(self._char(), _make_scores())
        assert result["chain"][0]["source_channel"] == "CH_A"

    def test_chain_target_is_second_channel(self):
        result = build_hypothesis(self._char(), _make_scores())
        assert result["chain"][0]["target_channel"] == "CH_B"

    def test_chain_gap_seconds_correct(self):
        result = build_hypothesis(self._char(gap=45), _make_scores())
        assert result["chain"][0]["gap_seconds"] == 45.0

    def test_chain_link_has_evidence_ref(self):
        result = build_hypothesis(self._char(), _make_scores())
        assert "evidence_ref" in result["chain"][0]
        assert len(result["chain"][0]["evidence_ref"]) > 0

    def test_confidence_in_bounds(self):
        result = build_hypothesis(self._char(), _make_scores())
        c = result["hypothesis_confidence"]
        assert 0.0 <= c <= 1.0

    def test_confidence_higher_with_overlap(self):
        r_overlap = build_hypothesis(self._char(overlap=True), _make_scores())
        r_no_overlap = build_hypothesis(self._char(overlap=False), _make_scores())
        assert r_overlap["hypothesis_confidence"] >= r_no_overlap["hypothesis_confidence"]

    def test_no_causality_language_in_chain_evidence_ref(self):
        result = build_hypothesis(self._char(), _make_scores())
        ref = result["chain"][0]["evidence_ref"].lower()
        assert "caused" not in ref
        assert "cause" not in ref

    def test_two_supporting_evidence_items(self):
        result = build_hypothesis(self._char(), _make_scores())
        assert len(result["supporting_evidence"]) == 2

    def test_supporting_evidence_channels_match_activation_order(self):
        result = build_hypothesis(self._char(), _make_scores())
        channels = [e["channel"] for e in result["supporting_evidence"]]
        assert channels == ["CH_A", "CH_B"]

    def test_primary_role_for_first_channel(self):
        result = build_hypothesis(self._char(), _make_scores())
        assert result["supporting_evidence"][0]["role"] == "primary"

    def test_secondary_role_for_second_channel(self):
        result = build_hypothesis(self._char(), _make_scores())
        assert result["supporting_evidence"][1]["role"] == "secondary"


# ---------------------------------------------------------------------------
# TestMultiChannel (3+ channels)
# ---------------------------------------------------------------------------

class TestMultiChannel:
    def _char_three(self, overlap: bool = True):
        rels = _all_pairs_rels([("CH_A", 0), ("CH_B", 30), ("CH_C", 60)], overlap=overlap)
        return _make_char(1, ["CH_A", "CH_B", "CH_C"], [0, 30, 60], rels=rels)

    def _char_four(self):
        rels = _all_pairs_rels([("CH_A", 0), ("CH_B", 20), ("CH_C", 40), ("CH_D", 60)])
        return _make_char(1, ["CH_A", "CH_B", "CH_C", "CH_D"], [0, 20, 40, 60], rels=rels)

    def _char_five(self):
        rels = _all_pairs_rels([
            ("CH_A", 0), ("CH_B", 10), ("CH_C", 20), ("CH_D", 30), ("CH_E", 40)
        ])
        return _make_char(1, ["CH_A", "CH_B", "CH_C", "CH_D", "CH_E"], [0, 10, 20, 30, 40], rels=rels)

    def test_three_channels_two_chain_links(self):
        result = build_hypothesis(self._char_three(), _make_scores())
        assert len(result["chain"]) == 2

    def test_four_channels_three_chain_links(self):
        result = build_hypothesis(self._char_four(), _make_scores())
        assert len(result["chain"]) == 3

    def test_five_channels_four_chain_links(self):
        result = build_hypothesis(self._char_five(), _make_scores())
        assert len(result["chain"]) == 4

    def test_chain_order_follows_activation_order(self):
        result = build_hypothesis(self._char_three(), _make_scores())
        sources = [l["source_channel"] for l in result["chain"]]
        assert sources == ["CH_A", "CH_B"]

    def test_chain_links_reference_real_channels(self):
        result = build_hypothesis(self._char_three(), _make_scores())
        channels = {"CH_A", "CH_B", "CH_C"}
        for link in result["chain"]:
            assert link["source_channel"] in channels
            assert link["target_channel"] in channels

    def test_n_corroborating_pairs_all_overlap(self):
        result = build_hypothesis(self._char_three(overlap=True), _make_scores())
        assert result["n_corroborating_pairs"] == 3  # C(3,2) = 3

    def test_n_corroborating_pairs_none_overlap(self):
        result = build_hypothesis(self._char_three(overlap=False), _make_scores())
        assert result["n_corroborating_pairs"] == 0

    def test_confidence_higher_with_full_overlap(self):
        r_overlap = build_hypothesis(self._char_three(overlap=True), _make_scores())
        r_no = build_hypothesis(self._char_three(overlap=False), _make_scores())
        assert r_overlap["hypothesis_confidence"] > r_no["hypothesis_confidence"]

    def test_five_channels_ten_pairs_all_corroborate(self):
        result = build_hypothesis(self._char_five(), _make_scores())
        assert result["n_corroborating_pairs"] == 10

    def test_supporting_evidence_count_equals_n_channels(self):
        result = build_hypothesis(self._char_three(), _make_scores())
        assert len(result["supporting_evidence"]) == 3

    def test_type_is_multi_channel(self):
        result = build_hypothesis(self._char_three(), _make_scores())
        assert result["hypothesis_type"] == "multi_channel"


# ---------------------------------------------------------------------------
# TestSimultaneousActivation
# ---------------------------------------------------------------------------

class TestSimultaneousActivation:
    def _char(self):
        rels = [_rel("CH_A", 0, "CH_B", 0, overlap=True)]
        return _make_char(1, ["CH_A", "CH_B"], [0, 0], rels=rels)

    def test_gap_is_zero(self):
        result = build_hypothesis(self._char(), _make_scores())
        assert result["chain"][0]["gap_seconds"] == 0.0

    def test_precedence_is_simultaneous(self):
        result = build_hypothesis(self._char(), _make_scores())
        assert result["chain"][0]["precedence"] == "simultaneous"

    def test_evidence_ref_mentions_simultaneous(self):
        result = build_hypothesis(self._char(), _make_scores())
        ref = result["chain"][0]["evidence_ref"].lower()
        assert "simultaneous" in ref

    def test_type_is_multi_channel(self):
        result = build_hypothesis(self._char(), _make_scores())
        assert result["hypothesis_type"] == "multi_channel"

    def test_confidence_in_bounds(self):
        result = build_hypothesis(self._char(), _make_scores())
        assert 0.0 <= result["hypothesis_confidence"] <= 1.0


# ---------------------------------------------------------------------------
# TestOverlappingChannels
# ---------------------------------------------------------------------------

class TestOverlappingChannels:
    def _char(self):
        rels = [_rel("CH_A", 0, "CH_B", 50, overlap=True)]
        return _make_char(1, ["CH_A", "CH_B"], [0, 50], rels=rels)

    def test_windows_overlap_true_in_chain(self):
        result = build_hypothesis(self._char(), _make_scores())
        assert result["chain"][0]["windows_overlap"] is True

    def test_n_corroborating_pairs_one(self):
        result = build_hypothesis(self._char(), _make_scores())
        assert result["n_corroborating_pairs"] == 1

    def test_summary_mentions_overlap(self):
        result = build_hypothesis(self._char(), _make_scores())
        # 1 of 1 pairs overlap
        assert "1 of 1" in result["summary"] or "1 of" in result["summary"]


# ---------------------------------------------------------------------------
# TestNonOverlappingChannels
# ---------------------------------------------------------------------------

class TestNonOverlappingChannels:
    def _char(self):
        rels = [_rel("CH_A", 0, "CH_B", 500, overlap=False)]
        return _make_char(1, ["CH_A", "CH_B"], [0, 500], rels=rels)

    def test_windows_overlap_false_in_chain(self):
        result = build_hypothesis(self._char(), _make_scores())
        assert result["chain"][0]["windows_overlap"] is False

    def test_n_corroborating_pairs_zero(self):
        result = build_hypothesis(self._char(), _make_scores())
        assert result["n_corroborating_pairs"] == 0

    def test_confidence_lower_with_large_gap(self):
        r_far = build_hypothesis(self._char(), _make_scores())
        rels_close = [_rel("CH_A", 0, "CH_B", 10, overlap=True)]
        char_close = _make_char(1, ["CH_A", "CH_B"], [0, 10], rels=rels_close)
        r_close = build_hypothesis(char_close, _make_scores())
        assert r_close["hypothesis_confidence"] >= r_far["hypothesis_confidence"]


# ---------------------------------------------------------------------------
# TestMissingTemporalRelationships
# ---------------------------------------------------------------------------

class TestMissingTemporalRelationships:
    def test_empty_rels_returns_insufficient_evidence(self):
        char = _make_char(1, ["CH_A", "CH_B"], [0, 30], rels=[])
        result = build_hypothesis(char, _make_scores())
        assert result["hypothesis_type"] == "insufficient_evidence"

    def test_empty_rels_chain_is_empty(self):
        char = _make_char(1, ["CH_A", "CH_B"], [0, 30], rels=[])
        result = build_hypothesis(char, _make_scores())
        assert result["chain"] == []

    def test_empty_rels_confidence_is_zero(self):
        char = _make_char(1, ["CH_A", "CH_B"], [0, 30], rels=[])
        result = build_hypothesis(char, _make_scores())
        assert result["hypothesis_confidence"] == 0.0

    def test_empty_rels_scientific_caveat_present(self):
        char = _make_char(1, ["CH_A", "CH_B"], [0, 30], rels=[])
        result = build_hypothesis(char, _make_scores())
        assert result["scientific_caveat"] == SCIENTIFIC_CAVEAT

    def test_insufficient_evidence_message_in_summary(self):
        char = _make_char(1, ["CH_A", "CH_B"], [0, 30], rels=[])
        result = build_hypothesis(char, _make_scores())
        assert "insufficient" in result["summary"].lower()


# ---------------------------------------------------------------------------
# TestDeterministic
# ---------------------------------------------------------------------------

class TestDeterministic:
    def _char(self):
        rels = _all_pairs_rels([("CH_A", 0), ("CH_B", 20), ("CH_C", 40)])
        return _make_char(1, ["CH_A", "CH_B", "CH_C"], [0, 20, 40], rels=rels)

    def test_same_confidence_repeated_calls(self):
        char = self._char()
        scores = _make_scores()
        r1 = build_hypothesis(char, scores)
        r2 = build_hypothesis(char, scores)
        assert r1["hypothesis_confidence"] == r2["hypothesis_confidence"]

    def test_same_chain_repeated_calls(self):
        char = self._char()
        scores = _make_scores()
        r1 = build_hypothesis(char, scores)
        r2 = build_hypothesis(char, scores)
        assert r1["chain"] == r2["chain"]

    def test_same_summary_repeated_calls(self):
        char = self._char()
        scores = _make_scores()
        r1 = build_hypothesis(char, scores)
        r2 = build_hypothesis(char, scores)
        assert r1["summary"] == r2["summary"]

    def test_same_type_repeated_calls(self):
        char = self._char()
        scores = _make_scores()
        r1 = build_hypothesis(char, scores)
        r2 = build_hypothesis(char, scores)
        assert r1["hypothesis_type"] == r2["hypothesis_type"]


# ---------------------------------------------------------------------------
# TestInvalidInput
# ---------------------------------------------------------------------------

class TestInvalidInput:
    def test_missing_spacecraft_incident_id_raises(self):
        char = {
            "n_channels_affected": 1,
            "channels_affected": ["CH_A"],
            "channel_activation_order": ["CH_A"],
            "channel_temporal_relationships": [],
        }
        with pytest.raises(ValueError, match="spacecraft_incident_id"):
            build_hypothesis(char, _make_scores())

    def test_missing_n_channels_affected_raises(self):
        char = {
            "spacecraft_incident_id": 1,
            "channels_affected": ["CH_A"],
            "channel_activation_order": ["CH_A"],
            "channel_temporal_relationships": [],
        }
        with pytest.raises(ValueError, match="n_channels_affected"):
            build_hypothesis(char, _make_scores())

    def test_missing_channel_activation_order_raises(self):
        char = {
            "spacecraft_incident_id": 1,
            "n_channels_affected": 1,
            "channels_affected": ["CH_A"],
            "channel_temporal_relationships": [],
        }
        with pytest.raises(ValueError, match="channel_activation_order"):
            build_hypothesis(char, _make_scores())

    def test_missing_channel_temporal_relationships_raises(self):
        char = {
            "spacecraft_incident_id": 1,
            "n_channels_affected": 1,
            "channels_affected": ["CH_A"],
            "channel_activation_order": ["CH_A"],
        }
        with pytest.raises(ValueError, match="channel_temporal_relationships"):
            build_hypothesis(char, _make_scores())


# ---------------------------------------------------------------------------
# TestChronologicalOrdering
# ---------------------------------------------------------------------------

class TestChronologicalOrdering:
    def test_chain_follows_activation_order_exactly(self):
        """The chain must link channels in the order given by activation_order."""
        rels = _all_pairs_rels([("CH_X", 0), ("CH_Y", 40), ("CH_Z", 80)])
        char = _make_char(1, ["CH_X", "CH_Y", "CH_Z"], [0, 40, 80], rels=rels)
        result = build_hypothesis(char, _make_scores())
        assert result["chain"][0]["source_channel"] == "CH_X"
        assert result["chain"][0]["target_channel"] == "CH_Y"
        assert result["chain"][1]["source_channel"] == "CH_Y"
        assert result["chain"][1]["target_channel"] == "CH_Z"

    def test_gap_seconds_are_non_negative(self):
        rels = _all_pairs_rels([("CH_A", 0), ("CH_B", 60), ("CH_C", 120)])
        char = _make_char(1, ["CH_A", "CH_B", "CH_C"], [0, 60, 120], rels=rels)
        result = build_hypothesis(char, _make_scores())
        for link in result["chain"]:
            gap = link.get("gap_seconds")
            if gap is not None:
                assert gap >= 0.0, f"Negative gap in chain: {link}"

    def test_supporting_evidence_follows_activation_order(self):
        rels = _all_pairs_rels([("CH_A", 0), ("CH_B", 50), ("CH_C", 100)])
        char = _make_char(1, ["CH_A", "CH_B", "CH_C"], [0, 50, 100], rels=rels)
        result = build_hypothesis(char, _make_scores())
        channels = [e["channel"] for e in result["supporting_evidence"]]
        assert channels == ["CH_A", "CH_B", "CH_C"]


# ---------------------------------------------------------------------------
# TestNoCausalityLanguage
# ---------------------------------------------------------------------------

_CAUSALITY_PATTERN = re.compile(
    r"\bcause[sd]?\b|\bcausal\b|\bcausality\b|\bcaused\b",
    re.IGNORECASE,
)

_ALLOWED_CAVEAT_PATTERN = re.compile(
    r"physical causality not confirmed|does not establish physical causality",
    re.IGNORECASE,
)


def _strip_caveats(text: str) -> str:
    """Remove the allowed caveat phrases before checking for forbidden language."""
    return _ALLOWED_CAVEAT_PATTERN.sub("", text)


class TestNoCausalityLanguage:
    """Ensure no forbidden causal language appears outside the mandatory caveat."""

    def _all_text(self, result: dict) -> list[tuple[str, str]]:
        """Return (field_name, text) pairs for all string fields in result."""
        fields = []
        for k, v in result.items():
            if k == "scientific_caveat":
                continue  # caveat is allowed to mention causality
            if isinstance(v, str):
                fields.append((k, v))
            elif isinstance(v, list):
                for i, item in enumerate(v):
                    if isinstance(item, str):
                        fields.append((f"{k}[{i}]", item))
                    elif isinstance(item, dict):
                        for sub_k, sub_v in item.items():
                            if isinstance(sub_v, str):
                                fields.append((f"{k}[{i}].{sub_k}", sub_v))
        return fields

    def test_no_causality_in_single_channel(self):
        char = _make_char(1, ["CH_A"], [0], rels=[])
        result = build_hypothesis(char, _make_scores())
        for field, text in self._all_text(result):
            cleaned = _strip_caveats(text)
            assert not _CAUSALITY_PATTERN.search(cleaned), (
                f"Causal language found in {field!r}: {text!r}"
            )

    def test_no_causality_in_multi_channel(self):
        rels = _all_pairs_rels([("CH_A", 0), ("CH_B", 30), ("CH_C", 60)])
        char = _make_char(1, ["CH_A", "CH_B", "CH_C"], [0, 30, 60], rels=rels)
        result = build_hypothesis(char, _make_scores())
        for field, text in self._all_text(result):
            cleaned = _strip_caveats(text)
            assert not _CAUSALITY_PATTERN.search(cleaned), (
                f"Causal language found in {field!r}: {text!r}"
            )

    def test_caveat_contains_required_disclaimer(self):
        char = _make_char(1, ["CH_A"], [0], rels=[])
        result = build_hypothesis(char, _make_scores())
        caveat = result["scientific_caveat"].lower()
        assert "physical causality not confirmed" in caveat

    def test_temporal_language_used_instead(self):
        """Chain evidence refs must use 'preceded' or 'simultaneous', not 'caused'."""
        rels = [_rel("CH_A", 0, "CH_B", 30, overlap=True)]
        char = _make_char(1, ["CH_A", "CH_B"], [0, 30], rels=rels)
        result = build_hypothesis(char, _make_scores())
        ref = result["chain"][0]["evidence_ref"].lower()
        assert "preceded" in ref or "simultaneous" in ref


# ---------------------------------------------------------------------------
# TestConfidenceBounds
# ---------------------------------------------------------------------------

class TestConfidenceBounds:
    def test_confidence_zero_single_channel(self):
        char = _make_char(1, ["CH_A"], [0], rels=[])
        result = build_hypothesis(char, _make_scores())
        assert result["hypothesis_confidence"] == 0.0

    def test_confidence_zero_insufficient_evidence(self):
        char = _make_char(1, ["CH_A", "CH_B"], [0, 30], rels=[])
        result = build_hypothesis(char, _make_scores())
        assert result["hypothesis_confidence"] == 0.0

    def test_confidence_between_zero_and_one_two_channels(self):
        rels = [_rel("CH_A", 0, "CH_B", 30, overlap=True)]
        char = _make_char(1, ["CH_A", "CH_B"], [0, 30], rels=rels)
        result = build_hypothesis(char, _make_scores())
        c = result["hypothesis_confidence"]
        assert 0.0 <= c <= 1.0

    def test_confidence_between_zero_and_one_five_channels(self):
        rels = _all_pairs_rels([
            ("CH_A", 0), ("CH_B", 10), ("CH_C", 20), ("CH_D", 30), ("CH_E", 40)
        ])
        char = _make_char(
            1,
            ["CH_A", "CH_B", "CH_C", "CH_D", "CH_E"],
            [0, 10, 20, 30, 40],
            rels=rels,
        )
        result = build_hypothesis(char, _make_scores())
        c = result["hypothesis_confidence"]
        assert 0.0 <= c <= 1.0

    def test_confidence_increases_with_overlap(self):
        """Full overlap set should give higher confidence than zero overlap."""
        rels_full = _all_pairs_rels([("CH_A", 0), ("CH_B", 30)], overlap=True)
        rels_none = _all_pairs_rels([("CH_A", 0), ("CH_B", 30)], overlap=False)
        char_full = _make_char(1, ["CH_A", "CH_B"], [0, 30], rels=rels_full)
        char_none = _make_char(1, ["CH_A", "CH_B"], [0, 30], rels=rels_none)
        c_full = build_hypothesis(char_full, _make_scores())["hypothesis_confidence"]
        c_none = build_hypothesis(char_none, _make_scores())["hypothesis_confidence"]
        assert c_full >= c_none

    def test_confidence_is_float(self):
        char = _make_char(1, ["CH_A"], [0], rels=[])
        result = build_hypothesis(char, _make_scores())
        assert isinstance(result["hypothesis_confidence"], float)


# ---------------------------------------------------------------------------
# TestChainLinksReferenceRealChannels
# ---------------------------------------------------------------------------

class TestChainLinksReferenceRealChannels:
    def test_two_channel_chain_links_real_channels(self):
        rels = [_rel("CH_ALPHA", 0, "CH_BETA", 20, overlap=True)]
        char = _make_char(1, ["CH_ALPHA", "CH_BETA"], [0, 20], rels=rels)
        result = build_hypothesis(char, _make_scores())
        valid = {"CH_ALPHA", "CH_BETA"}
        for link in result["chain"]:
            assert link["source_channel"] in valid
            assert link["target_channel"] in valid

    def test_five_channel_chain_links_all_real(self):
        channels = ["CH_1", "CH_2", "CH_3", "CH_4", "CH_5"]
        offsets = [0, 15, 30, 45, 60]
        rels = _all_pairs_rels(list(zip(channels, offsets)))
        char = _make_char(1, channels, offsets, rels=rels)
        result = build_hypothesis(char, _make_scores())
        valid = set(channels)
        for link in result["chain"]:
            assert link["source_channel"] in valid
            assert link["target_channel"] in valid

    def test_source_not_equal_to_target(self):
        rels = [_rel("CH_A", 0, "CH_B", 30, overlap=True)]
        char = _make_char(1, ["CH_A", "CH_B"], [0, 30], rels=rels)
        result = build_hypothesis(char, _make_scores())
        for link in result["chain"]:
            assert link["source_channel"] != link["target_channel"]
