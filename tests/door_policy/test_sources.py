from bdp_pure_pkg.sources import effective_presence_entity
from bdp_const import CONF_PRESENCE_EFFECTIVE, CONF_PROFILE


def test_effective_presence_source_falls_back_for_old_benni_entries():
    assert effective_presence_entity({CONF_PROFILE: "benni"}) == (
        "sensor.benni_core_state_presence_effective"
    )


def test_effective_presence_source_keeps_explicit_entity():
    assert effective_presence_entity(
        {
            CONF_PROFILE: "benni",
            CONF_PRESENCE_EFFECTIVE: "sensor.custom_presence_effective",
        }
    ) == "sensor.custom_presence_effective"


def test_effective_presence_source_empty_for_unknown_profile():
    assert effective_presence_entity({CONF_PROFILE: "eltern"}) is None
