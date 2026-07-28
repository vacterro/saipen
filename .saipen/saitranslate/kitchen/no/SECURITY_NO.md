# Sikkerhetspolicy

## Omfang

SAIPEN er en spesifikasjon pluss et lite sett med lokale installasjons-/eksportskript (`bootstrap/inject.ps1`/`.sh`, `uninstall.ps1`/`.sh`, `export.ps1`/`.sh`). Den kjører ikke en server, samler ikke inn telemetri, og overfører ingen data noen steder. Alt skriptene gjør er lokale filsystemskrivinger til filer du allerede kontrollerer (din egen `~/.claude`, `~/.gemini`, prosjektets `.saipen/`, etc.).

To forskjellige nivåer av forsiktighet gjelder her, og det er verdt å være presis i stedet for å påstå generell sikkerhet:

- **Dine egne konfigurasjonsfiler** (`CLAUDE.md`, `AGENTS.md`, `GEMINI.md`, `.aider.conf.yml`) blir kun redigert ved å legge til eller fjerne en avgrenset `SAIPEN:BEGIN`/`END`-blokk, og originalen blir kopiert til `<file>.bak` før den første endringen. Avinstallering skriver i tillegg `<file>.uninstalled.bak` før stripping.
- **Ferdighetskatalogene** injektoren oppretter (`~/.claude/skills/saipen` og lignende) er SAIPEN-eide kopier og blir **ikke** sikkerhetskopiert: installasjon overskriver dem fullstendig og avinstallering fjerner dem rekursivt. Det er tilsiktet -- de inneholder ingenting annet enn kopier av denne repoens egne filer -- men hvis du redigerer en lokal ferdighetskopi manuelt, går disse endringene tapt ved neste `inject`/`uninstall`. Hold tilpasninger i din egen konfigurasjonsblokk eller en fork, ikke inne i den kopierte ferdighetsmappen.

De to tingene som faktisk er verdt en sikkerhetsrapport:
1. Et bootstrap-skript som gjør noe med filsystemet ditt eller git-historikken din
   utover det dets egne kommentarer/README beskriver.
2. Protokollens egen regel for hemmelighets-hygiene (RFC.md § 1.1 -- skriv aldri
   API-nøkler, tokens, passord inn i `STATE.md`/`BOARD.md`/`LOG.md`/
   `KNOWLEDGE/`/`kitchen/`/`extensions/`/`saitranslate/kitchen/`/
   `recovery/`/`logs/`) som har et reelt hull som vil forårsake at en
   agent som følger SAIPEN lekker en hemmelighet inn i en forpliktet (committed) fil.
   De to siste er subtile: Gjenoppretting kopierer en korrupt `STATE.md` ordrett til
   `.saipen/recovery/`, og LOG-forsegling flytter linjer ordrett til `.saipen/logs/`,
   så alt som nådde originalen blir arkivert av maskineri hvis hele jobb er å ikke endre innhold.

## Støttede Versjoner

Kun den siste taggede utgivelsen på `main` støttes. Dette er en protokollspesifikasjon, ikke en langvarig tjeneste -- det er ingen LTS-gren.

## Rapportere et Sårbarhet

Åpne en GitHub-sak (issue). Hvis rapporten involverer et reelt problem som kan utnyttes akkurat nå (ikke et hypotetisk et), merk det som en privat/sikkerhetsrådgivning (security advisory) via
dette depotets **Security**-fane ("Report a vulnerability") i stedet for
en offentlig sak, slik at det ikke er offentlig synlig før en fiks rulles ut.

Inkluder: hvilket skript eller RFC-regel, det konkrete scenariet, og hva
som faktisk skjer i motsetning til hva som burde skje. Samme bevisstandard som enhver
annen feilrapport (se `CONTRIBUTING.md`).
