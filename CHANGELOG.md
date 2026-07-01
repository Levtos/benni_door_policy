# Changelog

## 0.2.2

- Runtime-Fallback fuer bestehende ConfigEntries ohne `presence_effective_entity`:
  Door Policy nutzt dann das profilierte Effective-Presence-Master-Default
  `sensor.benni_core_state_presence_effective`.
- Verhindert, dass migrierte Live-Instanzen nach dem Restart im Gate
  `presence_effective_missing` haengen bleiben.

## 0.2.1

- Door Policy konsumiert fuer Auto-Lock/Auto-Unlock `sensor.benni_core_state_presence_effective`
  statt selbst aus Person/Heimband zu arbitrieren.
- Auto-Unlock ist nur noch bei `arriving` mit hoher Confidence moeglich.
- Anti-Flap/Cooldown-Gates fuer schnelle Lock/Unlock-Gegenaktionen, wiederholte
  Unlocks und frische Roh-Schlosszustandswechsel.
- ConfigEntry-Migration auf den neuen Effective-Presence-Source-Slot.

## 0.2.0

- **Observability-/Shadow-Panel** (FLEET-155). Sidebar-Panel „Door Policy" im
  Fleet-Stil (Vanilla Web Component, kein Build-Step) — Muster wie blind/plug/light.
  - WS-Contract `benni_door_policy/get_status` (+ `apply_now` / `resync` /
    `set_apply_enabled`, Schreib-Commands admin-gated).
  - Zeigt: Combined-State + Batterie, Live-Inputs (Anwesenheit/Heimband/Roh-Schloss),
    Auto-Lock/Auto-Unlock-Szenarien + Begründung, **Shadow/Live-Toggle**,
    Pending-Action mit Stabilisierungs-Countdown, Diagnose-Attribute, Safety-Regeln
    (R-04/05/06) und Logik-Ablauf.
  - Pending-Countdown wird **nur** angezeigt, wenn wirklich geplant (während des
    HA-Start-Blocks bewusst keiner — kein Widerspruch Startup vs. Pending).
  - `manifest.json` deps: http / websocket_api / frontend.
- Coordinator: `status_snapshot()` + Pending-/Startup-Restzeit für die WS-API.
- Schaltlogik unverändert; Panel schaltet selbst nichts (alles gated an apply_enabled,
  Default Shadow).

## 0.1.0

- Erster Entwurf der Türschloss-Policy (Aqara U200, L2) nach Lastenheft
  `tuerschloss/` (R-01..R-08): combined_state, Auto-Lock/Auto-Unlock, gated +
  stabilisierter Apply, R-06 (nie open), Shadow-safe. 13/13 pure-logic tests.
