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


def _decide(raw=None, presence=None, band=None, battery=None, *, apply=True, ready=True):
    return policy.decide(
        policy.Context(
            raw_lock_state=raw,
            presence_personal=presence,
            home_band=band,
            battery_percent=battery,
        ),
        apply_enabled=apply,
        startup_ready=ready,
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
    d = _decide(raw="unlocked", presence="abwesend", band="far")
    assert d.action == ACTION_LOCK
    assert d.auto_lock_active is True
    assert d.apply_allowed is True


def test_r01_no_lock_when_already_locked():
    d = _decide(raw="locked", presence="abwesend", band="far")
    assert d.action == ACTION_NONE
    assert d.auto_lock_active is False


# ----- R-02 Auto-Unlock -----
def test_r02_autounlock_home_band_and_locked_unlocks():
    d = _decide(raw="locked", presence="abwesend", band="home")
    assert d.action == ACTION_UNLOCK
    assert d.auto_unlock_active is True


def test_r02_no_unlock_when_already_home_presence():
    # Anwesenheit zuhause → Auto-Unlock-Bedingung (≠ zuhause) verfehlt.
    d = _decide(raw="locked", presence="zuhause", band="home")
    assert d.action == ACTION_NONE


def test_r02_no_unlock_on_near_or_preheat():
    for band in ("near", "preheat", "far"):
        d = _decide(raw="locked", presence="abwesend", band=band)
        assert d.action == ACTION_NONE, band


# ----- R-04 unsichere Zustände -----
def test_r04_no_action_when_unknown():
    d = _decide(raw="unknown", presence="abwesend", band="home")
    assert d.action == ACTION_NONE
    assert d.apply_allowed is False
    assert any(b.startswith("source_unsafe") for b in d.blockers)


def test_r04_no_action_when_unavailable():
    d = _decide(raw="unavailable", presence="abwesend", band="far")
    assert d.action == ACTION_NONE
    assert d.apply_allowed is False


# ----- R-05 keine Verriegelung bei Anwesenheit -----
def test_r05_no_autolock_when_present():
    d = _decide(raw="unlocked", presence="zuhause", band="home")
    assert d.action == ACTION_NONE
    assert d.auto_lock_active is False
    assert "present_no_autolock" in d.blockers


# ----- Gating: Shadow + Startup -----
def test_gating_shadow_blocks_apply_but_keeps_action():
    d = _decide(raw="unlocked", presence="abwesend", band="far", apply=False)
    assert d.action == ACTION_LOCK          # Aktion bleibt sichtbar
    assert d.apply_allowed is False
    assert "apply_disabled" in d.blockers


def test_gating_startup_blocks_apply():
    d = _decide(raw="unlocked", presence="abwesend", band="far", ready=False)
    assert d.apply_allowed is False
    assert "startup_block" in d.blockers


# ----- presence unknown → konservativ -----
def test_presence_unknown_no_autolock():
    d = _decide(raw="unlocked", presence=None, band="far")
    assert d.action == ACTION_NONE
    assert "presence_unknown" in d.blockers


# ----- Batterie -----
def test_battery_critical_attribute():
    d = _decide(raw="locked", presence="zuhause", band="home", battery=12)
    assert d.battery_critical is True
    d2 = _decide(raw="locked", presence="zuhause", band="home", battery=55)
    assert d2.battery_critical is False
