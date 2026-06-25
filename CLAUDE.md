# CLAUDE.md — Door Policy

**Status:** v0.2.0 (FLEET-155). Backend + Pure-Logic-Tests + Observability-/Shadow-Panel.
Live-Verify offen.
**Letzte Aktualisierung:** 2026-06-25

## Was ist dieses Modul

Türschloss-Policy (Aqara Smart Lock U200, Matter via M3-Hub). L2-Policy: verriegelt
bei Abwesenheit, entriegelt bei Heimkehr (Heimband `home`), öffnet **nie** automatisch.
Strangler-Quelle: `haos_benni/packages/70_safety/50_automations/10_lock_auto_control.yaml`.

**Lastenheft:** `einhornzentrale/docs/lastenhefte/reviewed/tuerschloss/` (führend, R-01..R-08).

## Architektur-Entscheidungen (2026-06-25, beim Bau)

- **Standalone-Integration**, Skeleton-Pattern aus `benni_blind_policy`
  (manifest/__init__/const/entity/storage/coordinator/config_flow + sensor/binary_sensor).
  Kein Frontend-Panel im Erstentwurf (kann später wie blind_policy ergänzt werden).
- **Profil-Modell (FLEET-16):** Slug `<profile>_door_policy_<feature>` via `has_entity_name`
  + Device-Name `"{Label} Door Policy"`. Default-Route `benni`; `eltern` Prefill leer.
- **Pure Engine** (`policy.py`, HA-frei + pytest) trennt Decision (combined_state + action)
  von Apply. Coordinator = HA-Brücke mit **gated**, **stabilisiertem** Schaltbefehl
  (R-01: 60 s, R-02: 5 s; Re-Check nach Delay gegen Flaps).
- **R-06 hart:** Coordinator ruft NUR `lock.lock`/`lock.unlock`. `open` existiert nirgends.
- **Shadow-safe:** `apply_enabled` Default False.
- **Quellen** nur als Entity-IDs aus dem Flow (Prefill via HA-MCP ermittelt):
  Lock `lock.aqara_smart_lock_u200`, Presence `sensor.benni_core_state_presence_personal`,
  Heimband `sensor.benni_core_state_presence_band`.

## Offen / Live-Verify

- Band-Token (`home`/`near`/`preheat`/`far`) gegen den realen Wertebereich von
  `sensor.benni_core_state_presence_band` prüfen.
- Batterie-Quelle: eigene Entity vs. Attribut `battery_level` am U200 — live bestätigen.
- Nach Live-OK: `apply_enabled` aktivieren, dann auf der alten VM
  `automation.lock_auto_control_leave_arrival` deaktivieren (Strangler-Cut).

## Tests lokal

```
../benni-core-state/.venv/Scripts/python.exe -m pytest tests/door_policy/test_policy.py -q
```

## Git-Freigabe (stehend)

Committen/PR/merge/Release frei, solange < v1.0.0 (siehe `D:\Dokumente\GitHub\CLAUDE.md`).
