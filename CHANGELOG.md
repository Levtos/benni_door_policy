# Changelog

## 0.2.6

- **Root-Cause-Fix Auto-Unlock (R-02).** Die v0.2.4-Umstellung auf das Presence-
  Band hatte die Lastenheft-Bedingung „Persönliche Anwesenheit ≠ `zuhause`"
  (§4.3) aus dem Auto-Unlock verloren. Dadurch feuerte `home` + hohe Confidence +
  `verriegelt` auch, **wenn Benni schon zuhause war** (z. B. nachts verriegelt) →
  ungewolltes Entriegeln, das am open-fähigen U200 die Falle zog.
- **Guard wiederhergestellt:** Auto-Unlock verlangt jetzt wieder
  `home`/`arriving` **UND** `raw_presence != zuhause` **UND** `verriegelt`.
  Unbekannte persönliche Anwesenheit wird konservativ als `zuhause` behandelt
  (kein Unlock). Neuer Debug-Blocker `present_no_autounlock`.
- **v0.2.5-Hardblock entfernt.** `auto_unlock_blocked_open_capable_lock` war eine
  Über-Reaktion auf das Symptom und hätte auch das legitime Heimkehr-Entriegeln
  dauerhaft abgeschaltet. Die Falle wurde nie durch `lock.unlock` an sich
  gezogen, sondern nur, weil bei Anwesenheit fälschlich entriegelt wurde. R-06
  bleibt gewahrt: der Coordinator ruft ausschließlich `lock.lock`/`lock.unlock`.
- `lock_supported_features` / `lock_supports_open` bleiben als reine
  Observability-Attribute erhalten.

## 0.2.5

- **Safety-Fix R-06:** Auto-Unlock wird bei Open-faehigen Lock-Entities nicht
  mehr ausgefuehrt. Live-Test mit dem Aqara U200 hat gezeigt, dass
  `lock.unlock` die Falle ziehen kann, obwohl `lock.open` nicht aufgerufen
  wurde.
- Auto-Unlock bleibt als Szenario/Debug sichtbar, bekommt aber den Blocker
  `auto_unlock_blocked_open_capable_lock`; dadurch wird kein Pending-Apply und
  kein Schloss-Service-Call erzeugt.
- Debug-/Statusattribute zeigen `lock_supported_features` und
  `lock_supports_open`.

## 0.2.4

- **Fix Auto-Unlock im Home-Band.** `effective_presence=home` mit hoher
  Confidence und verriegeltem Schloss ist jetzt ein Auto-Unlock-Kandidat wie
  `arriving`. Damit bleibt die Door Policy konsistent mit dem Lastenheft:
  Heimkommen entriegelt, im Home-Kontext wird nicht automatisch verriegelt.
- **Fix Auto-Lock bei Eltern-Anwesenheit.** Auto-Lock verlangt jetzt zusätzlich
  `raw_presence=abwesend`; `bei_eltern` und `zuhause` blockieren Auto-Lock auch
  dann, wenn `presence_effective` policy-seitig als `away` erscheint.
- **Tests angepasst:** Der alte Test, der Unlock bei `home` explizit verhindert
  hat, wurde durch Home-/Arriving-Unlock-Tests plus Low-Confidence-Gate ersetzt.
  Der konkrete `bei_eltern`-Auto-Lock-Fall ist als Regressionstest abgedeckt.

## 0.2.3

- **Fix `presence_effective_missing` (renamed-device `system_` Entity-IDs).** Der
  Default/PREFILL für `presence_effective_entity` zeigt jetzt auf die live
  existierende Entity `sensor.system_benni_core_state_presence_effective` (statt
  auf den clean slug, der live nie existierte → Auto-Lock/Unlock war blockiert).
- **Setup-Migration repointet** einen stale, von einer älteren Version
  auto-geschriebenen clean-slug-Default in `entry.data` auf den live-Slug — nur
  wenn keine explizite Options-Override vorliegt. Explizit vom User gesetzte
  Entities bleiben respektiert.
- **Missing-Handling unverändert:** fehlt/`unavailable`/`unknown` die konfigurierte
  Presence-Effective-Entity, bleibt `presence_effective_missing` aktiv und
  Auto-Lock/Unlock blockiert (kein stilles Ignorieren).
- **Keine Änderung an der Lock-/Unlock-Entscheidungslogik.** Kein Core-State-,
  kein Media-State-Change.

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
