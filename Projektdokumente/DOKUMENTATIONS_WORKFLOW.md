# Dokumentations-Workflow: OK vor Übernahme

## Grundregel

**Keine automatische Übernahme** neuer Funktionen ins Bedienungshandbuch oder in die technische Dokumentation — **ohne Ihre ausdrückliche Bestätigung mit `OK`** (nur GROSSBUCHSTABEN).

---

## Ablauf für Sie

1. Feature oder Fix wird umgesetzt (Code).
2. Sie erhalten eine **Kurzzusammenfassung**, was sich geändert hat.
3. Sie prüfen die Funktion in DigiWiki (ggf. nach Neustart via `start.bat`).
4. Sind Sie zufrieden, antworten Sie mit: **`OK`**
5. Erst dann werden aktualisiert:
   - **Bedienung:** `Anleitung_Nutzer_Bedienung.md` (+ ggf. Kurzreferenz)
   - **Technik:** `PROJEKT_STATUS.md`, `README.md`, Admin-Anleitung
6. Der Eintrag wandert in `Aenderungsprotokoll.md` von **Ausstehend** → **Bestätigt**.

---

## Was zählt nicht als OK?

| Eingabe | Wirkung |
|---------|---------|
| `OK` | ✅ Dokumentation wird übernommen |
| `ok`, `Ok`, `okay`, `ja` | ❌ Keine Doc-Übernahme — bitte erneut `OK` |
| Schweigen / anderes Thema | ❌ Eintrag bleibt ausstehend |

---

## Wo wird mitgeschrieben?

| Datei | Inhalt |
|-------|--------|
| [Aenderungsprotokoll.md](Aenderungsprotokoll.md) | Alle Änderungen, Status ausstehend/bestätigt |
| `.cursor/rules/ok-dokumentation.mdc` | Regel für den KI-Assistenten in Cursor |

---

## Aktuell ausstehend

Siehe Tabelle **„Ausstehend“** in [Aenderungsprotokoll.md](Aenderungsprotokoll.md).

**Zuletzt bestätigt (OK):** Antworten exportieren, Antwort ausblenden (18.06.2026).
