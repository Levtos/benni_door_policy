from bdp_pure_pkg.sources import effective_presence_entity, migrate_effective_presence
from bdp_const import CONF_PRESENCE_EFFECTIVE, CONF_PROFILE

SYSTEM = "sensor.system_benni_core_state_presence_effective"
LEGACY = "sensor.benni_core_state_presence_effective"


# --- default / prefill resolution -----------------------------------------


def test_effective_presence_source_default_is_system_slug():
    # renamed-device fix: default now points at the live system_-prefixed entity.
    assert effective_presence_entity({CONF_PROFILE: "benni"}) == SYSTEM


def test_effective_presence_source_keeps_explicit_entity():
    assert effective_presence_entity(
        {
            CONF_PROFILE: "benni",
            CONF_PRESENCE_EFFECTIVE: "sensor.custom_presence_effective",
        }
    ) == "sensor.custom_presence_effective"


def test_effective_presence_source_empty_for_unknown_profile():
    assert effective_presence_entity({CONF_PROFILE: "eltern"}) is None


# --- migrate_effective_presence (renamed-device system_ fix) ---------------


def test_migrate_fills_empty_binding_with_system_default():
    assert migrate_effective_presence({}, {}, "benni") == SYSTEM


def test_migrate_repoints_stale_legacy_clean_slug():
    # The core bug: an old build auto-wrote the clean slug (which never existed
    # live) into entry.data → repoint it to the live system_ slug.
    assert migrate_effective_presence({CONF_PRESENCE_EFFECTIVE: LEGACY}, {}, "benni") == SYSTEM


def test_migrate_respects_explicit_options_override():
    # An explicit options override always wins → never migrate.
    assert migrate_effective_presence(
        {CONF_PRESENCE_EFFECTIVE: LEGACY},
        {CONF_PRESENCE_EFFECTIVE: "sensor.custom_presence_effective"},
        "benni",
    ) is None


def test_migrate_keeps_non_legacy_user_value_in_data():
    # A genuine user-chosen entity in data (not a known legacy id) is preserved.
    assert migrate_effective_presence(
        {CONF_PRESENCE_EFFECTIVE: "sensor.custom_presence_effective"}, {}, "benni"
    ) is None


def test_migrate_noop_when_already_system_slug():
    assert migrate_effective_presence({CONF_PRESENCE_EFFECTIVE: SYSTEM}, {}, "benni") is None


def test_migrate_noop_for_unknown_profile():
    assert migrate_effective_presence({}, {}, "eltern") is None
