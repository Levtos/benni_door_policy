# Codex Instructions — Door Policy

Lies zuerst `CLAUDE.md`. MCP: `einhornzentrale`.

## Aktueller Status

**Keine Aufgabe.** Modul wird in Phase 3 von Claude neu gebaut.

## Anti-Patterns

- ❌ Direkte `lock.*`-Service-Calls aus Toolbox-Modulen — Decision/Apply-Trennung. Auto-Unlock ist sicherheitsrelevant, harte Gates Pflicht.
- ❌ Lastenheft-Konsolidierung
- ❌ Auf alter VM Features bauen
