"""Pure-Logic-Tests der Door-Policy (HA-frei).

Deckt das Lastenheft tuerschloss/ ab: Combined-State-Mapping (§4.1) und die
Regeln R-01..R-08 inkl. Gating. Lauf:

    ../benni-core-state/.venv/Scripts/python.exe -m pytest tests/door_policy/test_policy.py -q
"""
from __future__ import annotations

import bdp_const as const  # noqa: E402  (synthetisches Paket via conftest)
import bdp_policy as policy  # noqa: E402

ACTION_LOCK = const.ACTION_LOCK
ACTION_UNLOCK = const.ACTION_UNLOCK
ACTION_NONE = const.ACTION_NONE
STATE_VERRIEGELT = const.STATE_VERRIEGELT
STATE_ENTRIEGELT = const.STATE_ENTRIEGELT
STATE_UNBEKANNT = const.STATE_UNBEKANNT
STATE_NICHT_ERREICHBAR = const.STATE_NICHT_ERREICHBAR


def _decide(
    raw=None,
    effective=None,
    confidence=None,
    raw_presence=None,
    battery=None,
    *,
    apply=True,
    ready=True,
    recent_action=None,
    recent_age=None,
    raw_age=999,
):
    return policy.decide(
        policy.Context(
            raw_lock_state=raw,
            effective_presence=effective,
            presence_confidence=confidence,
            raw_presence=raw_presence,
            battery_percent=battery,
        ),
        apply_enabled=apply,
        startup_ready=ready,
        recent_lock_action=recent_action,
        recent_lock_action_age_s=recent_age,
        raw_lock_changed_age_s=raw_age,
    )


# ----- §4.1 Combined-State-Mapping -----
def test_combined_state_mapping():
    assert policy.combined_state("locked") == STATE_VERRIEGELT
    assert policy.combined_state("unlocked") == STATE_ENTRIEGELT
    assert policy.combined_state("unlocking") == STATE_ENTRIEGELT
    assert policy.combined_state("unavailable") == STATE_NICHT_ERREICHBAR
    assert policy.combined_state("unknown") == STATE_UNBEKANNT
    assert policy.combined_state(None) == STATE_UNBEKANNT


# ----- R-01 Auto-Lock -----
def test_r01_autolock_away_and_unlocked_locks():
    d = _decide(raw="unlocked", effective="away", raw_presence="abwesend")
    assert d.action == ACTION_LOCK
    assert d.auto_lock_active is True
    assert d.apply_allowed is True


def test_r01_no_lock_when_already_locked():
    d = _decide(raw="locked", effective="away", raw_presence="abwesend")
    assert d.action == ACTION_NONE
    assert d.auto_lock_active is False


def test_r01_no_lock_when_at_parents_even_if_effective_away():
    d = _decide(raw="unlocked", effective="away", confidence=0.9, raw_presence="bei_eltern")
    assert d.action == ACTION_NONE
    assert d.auto_lock_active is False
    assert "personal_present_no_autolock" in d.blockers


def test_r01_no_lock_when_personal_presence_missing():
    d = _decide(raw="unlocked", effective="away", confidence=0.9)
    assert d.action == ACTION_NONE
    assert d.auto_lock_active is False
    assert "presence_personal_missing" in d.blockers


# ----- R-02 Auto-Unlock -----
def test_r02_autounlock_home_or_arriving_high_confidence_and_locked_unlocks():
    for effective in ("home", "arriving"):
        d = _decide(raw="locked", effective=effective, confidence=0.93)
        assert d.action == ACTION_UNLOCK, effective
        assert d.auto_unlock_active is True


def test_r02_no_unlock_on_uncertain_or_stale():
    for effective in ("uncertain", "stale", "away", "leaving"):
        d = _decide(raw="locked", effective=effective, confidence=0.95)
        assert d.action == ACTION_NONE, effective


def test_r02_no_unlock_when_arriving_confidence_low():
    d = _decide(raw="locked", effective="arriving", confidence=0.55)
    assert d.action == ACTION_NONE
    assert "arriving_confidence_low" in d.blockers


def test_r02_no_unlock_when_home_confidence_low():
    d = _decide(raw="locked", effective="home", confidence=0.55)
    assert d.action == ACTION_NONE
    assert "home_confidence_low" in d.blockers


# ----- R-04 unsichere Zustände -----
def test_r04_no_action_when_unknown():
    d = _decide(raw="unknown", effective="arriving", confidence=0.93)
    assert d.action == ACTION_NONE
    assert d.apply_allowed is False
    assert any(b.startswith("source_unsafe") for b in d.blockers)


def test_r04_no_action_when_unavailable():
    d = _decide(raw="unavailable", effective="away")
    assert d.action == ACTION_NONE
    assert d.apply_allowed is False


# ----- R-05 keine Verriegelung bei Anwesenheit -----
def test_r05_no_autolock_when_present():
    d = _decide(raw="unlocked", effective="home", raw_presence="zuhause")
    assert d.action == ACTION_NONE
    assert d.auto_lock_active is False
    assert "present_no_autolock" in d.blockers


# ----- Gating: Shadow + Startup -----
def test_gating_shadow_blocks_apply_but_keeps_action():
    d = _decide(raw="unlocked", effective="away", raw_presence="abwesend", apply=False)
    assert d.action == ACTION_LOCK          # Aktion bleibt sichtbar
    assert d.apply_allowed is False
    assert "apply_disabled" in d.blockers


def test_gating_startup_blocks_apply():
    d = _decide(raw="unlocked", effective="away", raw_presence="abwesend", ready=False)
    assert d.apply_allowed is False
    assert "startup_block" in d.blockers


# ----- presence unknown → konservativ -----
def test_presence_effective_missing_no_autolock():
    d = _decide(raw="unlocked", effective=None)
    assert d.action == ACTION_NONE
    assert "presence_effective_missing" in d.blockers


# ----- Batterie -----
def test_battery_critical_attribute():
    d = _decide(raw="locked", effective="home", battery=12)
    assert d.battery_critical is True
    d2 = _decide(raw="locked", effective="home", battery=55)
    assert d2.battery_critical is False


def test_leaving_with_stale_home_band_locks_but_does_not_unlock():
    d = _decide(raw="unlocked", effective="leaving", raw_presence="abwesend")
    assert d.action == ACTION_LOCK
    assert d.auto_lock_active is True
    assert d.auto_unlock_active is False


def test_arriving_after_stable_away_is_unlock_candidate():
    d = _decide(raw="locked", effective="arriving", confidence=0.95)
    assert d.action == ACTION_UNLOCK
    assert d.auto_unlock_active is True


def test_away_near_without_clear_trend_uncertain_no_unlock():
    d = _decide(raw="locked", effective="uncertain", confidence=0.35)
    assert d.action == ACTION_NONE
    assert "presence_uncertain" in d.blockers


def test_lock_unlock_anti_flap_blocks_fast_opposite_action():
    d = _decide(
        raw="locked",
        effective="arriving",
        confidence=0.95,
        recent_action=ACTION_LOCK,
        recent_age=30,
    )
    assert d.action == ACTION_UNLOCK
    assert d.apply_allowed is False
    assert "lock_unlock_anti_flap" in d.blockers


def test_unlock_cooldown_blocks_fast_repeated_unlock():
    d = _decide(
        raw="locked",
        effective="arriving",
        confidence=0.95,
        recent_action=ACTION_UNLOCK,
        recent_age=30,
    )
    assert d.action == ACTION_UNLOCK
    assert d.apply_allowed is False
    assert "unlock_cooldown" in d.blockers


def test_external_raw_lock_change_suppresses_policy_oscillation():
    d = _decide(raw="locked", effective="arriving", confidence=0.95, raw_age=30)
    assert d.action == ACTION_UNLOCK
    assert d.apply_allowed is False
    assert "raw_lock_recently_changed" in d.blockers
