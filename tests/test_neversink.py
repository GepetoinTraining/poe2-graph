"""Tests for the NeverSink filter recommender."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import neversink  # noqa: E402


# ----- strictness ladder -----

def test_early_levelling_gets_regular():
    rec = neversink.recommend_filter({"current_level": 12})
    assert rec.strictness == "regular"
    assert "12" in rec.rationale


def test_mid_campaign_gets_semi_strict():
    rec = neversink.recommend_filter({"current_level": 45})
    assert rec.strictness == "semi-strict"


def test_endgame_entry_no_wealth_stays_semi_strict():
    rec = neversink.recommend_filter({"current_level": 72})
    assert rec.strictness == "semi-strict"


def test_endgame_entry_with_high_wealth_goes_strict():
    rec = neversink.recommend_filter(
        {"current_level": 72},
        player_fm={"peak_wealth_tier": "divine"},
    )
    assert rec.strictness == "strict"


def test_late_endgame_with_wealth_goes_very_strict():
    rec = neversink.recommend_filter(
        {"current_level": 90},
        player_fm={"peak_wealth_tier": "mirror"},
    )
    assert rec.strictness == "very-strict"


def test_uber_endgame_mapper_gets_uber_strict():
    rec = neversink.recommend_filter(
        {"current_level": 97},
        player_fm={"peak_wealth_tier": "mirror", "grind_capacity": "top"},
    )
    assert rec.strictness == "uber-strict"


def test_racing_time_budget_loosens_strictness():
    """Racing → loosen one step from the level-derived strictness."""
    baseline = neversink.recommend_filter(
        {"current_level": 90},
        player_fm={"peak_wealth_tier": "mirror"},
    )
    racing = neversink.recommend_filter(
        {"current_level": 90},
        player_fm={"peak_wealth_tier": "mirror", "time_budget": "racing"},
    )
    idx_b = neversink.STRICTNESS_LEVELS.index(baseline.strictness)
    idx_r = neversink.STRICTNESS_LEVELS.index(racing.strictness)
    assert idx_r == idx_b - 1
    assert "racing" in racing.rationale.lower()


# ----- class-driven customizations -----

def test_sorceress_gets_spirit_modifier_customization():
    rec = neversink.recommend_filter(
        {"current_level": 50, "class": "Sorceress"},
    )
    assert any("Spirit-modifier" in c for c in rec.customizations)
    assert any("wand" in c.lower() and "sceptre" in c.lower() for c in rec.customizations)


def test_huntress_gets_spear_bow_customization():
    rec = neversink.recommend_filter(
        {"current_level": 50, "class": "Huntress"},
    )
    assert any("spear" in c.lower() and "bow" in c.lower() for c in rec.customizations)


def test_warrior_gets_2h_and_strength_armour():
    rec = neversink.recommend_filter(
        {"current_level": 50, "class": "Warrior"},
    )
    customizations = " ".join(rec.customizations).lower()
    assert "2h" in customizations or "maces" in customizations
    assert "strength" in customizations


def test_witch_minion_archetype_gets_minion_customization():
    rec = neversink.recommend_filter(
        {
            "current_level": 50,
            "class": "Witch",
            "ascendancy": "Infernalist",
            "archetype_tags": ["minion", "caster"],
        },
    )
    assert any("minion" in c.lower() for c in rec.customizations)


# ----- ascendancy customizations -----

def test_stormweaver_gets_lightning_jewel_customization():
    rec = neversink.recommend_filter(
        {"current_level": 50, "class": "Sorceress", "ascendancy": "Stormweaver"},
    )
    assert any("lightning" in c.lower() for c in rec.customizations)


def test_titan_gets_armour_life_jewel_customization():
    rec = neversink.recommend_filter(
        {"current_level": 50, "class": "Warrior", "ascendancy": "Titan"},
    )
    assert any("armour" in c.lower() and "life" in c.lower() for c in rec.customizations)


def test_infernalist_gets_fire_resist_discipline():
    rec = neversink.recommend_filter(
        {"current_level": 50, "class": "Witch", "ascendancy": "Infernalist"},
    )
    assert any("fire-resist" in c.lower() for c in rec.customizations)


# ----- edge-driven customizations -----

def test_marginal_capability_edge_keeps_upgrade_items_visible():
    rec = neversink.recommend_filter(
        {"current_level": 85, "class": "Sorceress"},
        player_fm={"peak_wealth_tier": "divine"},
        edges_of_interest=["marginal_capability_thinking"],
    )
    assert any("upgrade-pacing" in c for c in rec.customizations)


def test_option_value_edge_shows_uniques_unconditionally():
    rec = neversink.recommend_filter(
        {"current_level": 85, "class": "Sorceress"},
        edges_of_interest=["option_value_vs_face_value"],
    )
    assert any("unique" in c.lower() for c in rec.customizations)


def test_posture_under_drop_edge_adds_divine_alert():
    rec = neversink.recommend_filter(
        {"current_level": 85, "class": "Sorceress"},
        edges_of_interest=["posture_under_drop"],
    )
    assert any("divine" in c.lower() for c in rec.customizations)


# ----- wealth-tier -----

def test_high_wealth_adds_mirror_exalt_highlights():
    rec = neversink.recommend_filter(
        {"current_level": 95, "class": "Sorceress"},
        player_fm={"peak_wealth_tier": "mirror"},
    )
    assert any("mirror" in c.lower() and "exalt" in c.lower() for c in rec.customizations)


# ----- rendering -----

def test_render_recommendation_has_all_sections():
    rec = neversink.FilterRecommendation(
        strictness="strict",
        rationale="testing",
        customizations=["First note", "Second note"],
    )
    text = neversink.render_recommendation(rec)
    assert "## Filter recommendation" in text
    assert "`strict`" in text
    assert "testing" in text
    assert "First note" in text
    assert "Second note" in text
    assert "NeverSinkDev" in text
    assert "MIT" in text


def test_render_recommendation_works_with_no_customizations():
    rec = neversink.FilterRecommendation(
        strictness="regular",
        rationale="early game",
    )
    text = neversink.render_recommendation(rec)
    assert "regular" in text
    assert "Customizations" not in text  # no customizations section when empty
    assert "NeverSinkDev" in text


def test_write_recommendation_creates_file(tmp_path):
    rec = neversink.FilterRecommendation(
        strictness="strict",
        rationale="endgame",
        customizations=["Highlight wands"],
    )
    out = tmp_path / "char.filter.md"
    neversink.write_recommendation(rec, out)
    assert out.exists()
    text = out.read_text(encoding="utf-8")
    assert "endgame" in text
    assert "Highlight wands" in text


# ----- composition: realistic Stormweaver player -----

def test_realistic_stormweaver_recommendation():
    """A typical mid-endgame Stormweaver: lvl 85, divine wealth, upgrade-pacing focus."""
    rec = neversink.recommend_filter(
        character_fm={
            "current_level": 85,
            "class": "Sorceress",
            "ascendancy": "Stormweaver",
            "archetype_tags": ["caster"],
        },
        player_fm={
            "peak_wealth_tier": "divine",
            "grind_capacity": "high",
            "time_budget": "standard",
        },
        edges_of_interest=["marginal_capability_thinking", "posture_under_drop"],
    )
    # Endgame entry + divine wealth at lvl 85 (< 95) → very-strict
    assert rec.strictness == "very-strict"
    # Should have all of: caster + Stormweaver + upgrade-pacing + posture customizations
    text = " ".join(rec.customizations).lower()
    assert "spirit" in text  # caster
    assert "lightning" in text  # stormweaver
    assert "upgrade-pacing" in text  # marginal_capability
    assert "divine" in text  # wealth + posture


# ----- live release URL -----

def test_fetch_latest_release_url_returns_str_or_none():
    """Network call — must not raise; may return None offline. Validates the
    contract, not the value."""
    result = neversink.fetch_latest_release_url(timeout=3.0)
    assert result is None or isinstance(result, str)


def test_neversink_repo_constants():
    assert "NeverSink" in neversink.NEVERSINK_REPO
    assert neversink.NEVERSINK_REPO_URL.startswith("https://github.com")
    assert "releases" in neversink.NEVERSINK_RELEASES_LATEST
