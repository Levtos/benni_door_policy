# CLAUDE.md — Door Policy

## GitLab Workflow

- GitLab project `ha-platform/control` is the central workflow truth.
- Relevant work requires a GitLab issue in `ha-platform/control`.
- Before work starts, read the issue description and all issue notes.
- Document current state, decisions, scope changes, tests, commits, merge requests, blockers, and completion in the issue.
- Code changes happen in the matching GitLab repository. `origin` must point to GitLab.
- GitHub is only the public distribution and HACS mirror. Do not develop directly on GitHub and do not push manually to GitHub.
- Plane and Forgejo are historical sources only and are not used for active work.
- Full rules live in `ha-platform/control/AGENTS.md`, `ha-platform/control/CLAUDE.md`, and `ha-platform/control/docs/workflow/`.

## Project-Memory Bootstrap

- Before significant work, read the matching GitLab issue description and all notes, then `ha-platform/control/docs/workflow/README.md`, its linked workflow documents, and relevant `ha-platform/control` wiki pages.
- GitLab is the workflow truth. GitHub is only the distribution/HACS mirror; do not develop there directly. Plane is frozen historical context, and Forgejo is out of service.
- Stay inside the decided issue scope: no side quests and no overwriting foreign branches or dirty worktrees.
- Use the smallest sufficient verification for the risk tier. Stable changes to behavior, contracts, operations, or rules belong in the wiki; use live evidence when runtime behavior must be proved. Completion notes must document wiki impact, verification/tests, release state where applicable, and required live evidence.

## Safety

- Do not put secrets in issues, commits, logs, or reports.
- Do not touch production Home Assistant systems without explicit approval.
- No admin, delete, runner, or bulk actions without explicit approval.

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
