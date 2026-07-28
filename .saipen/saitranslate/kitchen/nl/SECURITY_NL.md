# Beveiligingsbeleid

## Bereik

SAIPEN is een specificatie plus een kleine set lokale installatie-/export-
scripts (`bootstrap/inject.ps1`/`.sh`, `uninstall.ps1`/`.sh`,
`export.ps1`/`.sh`). Het draait geen server, verzamelt geen
telemetrie, en verzendt geen gegevens ergens naartoe. Alles wat de
scripts doen, zijn lokale bestandssysteem-schrijfacties naar bestanden die u al beheert
(uw eigen `~/.claude`, `~/.gemini`, project `.saipen/`, enz.).

Er zijn twee verschillende niveaus van zorg van toepassing, en het is de moeite waard
om precies te zijn in plaats van een algemene veiligheid te claimen:

- **Uw eigen configuratiebestanden** (`CLAUDE.md`, `AGENTS.md`, `GEMINI.md`,
  `.aider.conf.yml`) worden alleen bewerkt door een afgebakend
  `SAIPEN:BEGIN`/`END`-blok toe te voegen of te verwijderen, en het origineel wordt
  gekopieerd naar `<file>.bak` vóór de eerste wijziging. Bij de-installatie wordt
  bovendien `<file>.uninstalled.bak` geschreven voordat wordt gestript.
- **De vaardigheidsmappen** die de injector aanmaakt (`~/.claude/skills/saipen`
  en dergelijke) zijn SAIPEN-eigendom kopieën en worden **niet** geback-upt: installatie
  overschrijft ze volledig en de-installatie verwijdert ze recursief. Dat is
  intentioneel -- ze bevatten niets dan kopieën van de eigen bestanden van deze repo --
  maar als u een lokale vaardigheidskopie handmatig bewerkt, gaan die wijzigingen verloren
  bij de volgende `inject`/`uninstall`. Houd aanpassingen in uw eigen configuratieblok of een
  fork, niet in de gekopieerde vaardigheidsmap.

De twee dingen die echt een beveiligingsrapportage waard zijn:
1. Een bootstrap-script dat iets met uw bestandssysteem of gitgeschiedenis doet
   buiten wat de eigen opmerkingen/README beschrijven.
2. Een echte tekortkoming in de regelgeving voor geheimenhygiëne van het protocol zelf
   (RFC.md § 1.1 -- schrijf nooit API-sleutels, tokens, wachtwoorden in
   `STATE.md`/`BOARD.md`/`LOG.md`/`KNOWLEDGE/`/`kitchen/`/`extensions/`/
   `saitranslate/kitchen/`/`recovery/`/`logs/`) waardoor een agent die SAIPEN volgt
   een geheim in een gecommit bestand zou kunnen lekken. De laatste twee zijn subtiel:
   Recovery kopieert een corrupt `STATE.md` letterlijk naar `.saipen/recovery/`, en
   LOG-verzegeling verplaatst regels letterlijk naar `.saipen/logs/`, dus alles wat het
   origineel bereikte, wordt gearchiveerd door een mechanisme waarvan het hele doel is
   om inhoud niet te wijzigen.

## Ondersteunde Versies

Alleen de nieuwste getagde release op `main` wordt ondersteund. Dit is een
protocolspecificatie, geen langlopende dienst -- er is geen LTS-
branch.

## Een Kwetsbaarheid Melden

Open een GitHub issue. Als het rapport betrekking heeft op een echt, momenteel exploiteerbaar
probleem (geen hypothetisch), markeer het dan als een privé/beveiligingswaarschuwing via
het tabblad **Security** ("Report a vulnerability") van deze repository in plaats van
een openbaar issue, zodat het niet openbaar zichtbaar is voordat er een fix is uitgebracht.

Vermeld: welk script of welke RFC-regel, het concrete scenario, en wat
er werkelijk gebeurt vs. wat er zou moeten gebeuren. Dezelfde bewijsstandaard als elke
andere foutrapportage (zie `CONTRIBUTING.md`).
