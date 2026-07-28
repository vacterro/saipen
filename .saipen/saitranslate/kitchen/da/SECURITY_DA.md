# Sikkerhedspolitik

## Omfang

SAIPEN er en specifikation plus et lille sæt lokale installations-/eksportscripts (`bootstrap/inject.ps1`/`.sh`, `uninstall.ps1`/`.sh`, `export.ps1`/`.sh`). Den kører ikke en server, indsamler ikke telemetri, og overfører ikke nogen data nogen steder hen. Alt, hvad scripts gør, er lokale filsystemskrivninger til filer, du allerede kontrollerer (dine egne `~/.claude`, `~/.gemini`, projekt `.saipen/`, osv.).

Der gælder to forskellige omhyggelighedsniveauer her, og det er værd at være præcis i stedet for at påstå blanket sikkerhed:

- **Dine egne konfigurationsfiler** (`CLAUDE.md`, `AGENTS.md`, `GEMINI.md`, `.aider.conf.yml`) redigeres kun ved at tilføje eller fjerne en afgrænset `SAIPEN:BEGIN`/`END`-blok, og originalen kopieres til `<file>.bak` før den første ændring. Afinstallation skriver desuden `<file>.uninstalled.bak` før fjernelse.
- **Færdighedsmapperne** som injektoren opretter (`~/.claude/skills/saipen` og lignende) er SAIPEN-ejede kopier og bliver **ikke** sikkerhedskopieret: installation overskriver dem helt og afinstallation fjerner dem rekursivt. Det er tilsigtet -- de indeholder intet andet end kopier af dette repos egne filer -- men hvis du redigerer en lokal færdighedskopi i hånden, går disse redigeringer tabt ved næste `inject`/`uninstall`. Behold tilpasninger i din egen konfigurationsblok eller et fork, ikke inde i den kopierede færdighedsmappe.

De to ting, der faktisk er værd at lave en sikkerhedsrapport over:
1. Et bootstrap-script der gør noget ved dit filsystem eller din git-historik udover hvad dets egne kommentarer/README beskriver.
2. Protokollens egen regel for hemmelighedshygiejne (RFC.md § 1.1 -- skriv aldrig API-nøgler, tokens, adgangskoder i `STATE.md`/`BOARD.md`/`LOG.md`/`KNOWLEDGE/`/`kitchen/`/`extensions/`/`saitranslate/kitchen/`/`recovery/`/`logs/`) der har en reel mangel, som ville få en agent, der følger SAIPEN, til at lække en hemmelighed til en committet fil. De sidste to er de subtile: Recovery kopierer en korrupt `STATE.md` ordret til `.saipen/recovery/`, og LOG-forsegling flytter linjer ordret til `.saipen/logs/`, så alt der nåede originalen, arkiveres af maskineri, hvis hele opgave er ikke at ændre indhold.

## Understøttede Versioner

Kun den seneste taggede udgivelse på `main` understøttes. Dette er en protokolspecifikation, ikke en langlivet tjeneste -- der er ingen LTS-gren.

## Rapportering af en Sårbarhed

Åbn et GitHub issue. Hvis rapporten involverer et virkeligt problem, der i øjeblikket kan udnyttes (ikke hypotetisk), så marker det som en privat/sikkerhedsadvisory via dette repositorys **Security** fane ("Report a vulnerability") i stedet for et offentligt issue, så det ikke er offentligt synligt før en rettelse er udgivet.

Inkluder: hvilket script eller RFC-regel, det konkrete scenarie, og hvad der faktisk sker vs. hvad der burde ske. Samme bevisstandard som enhver anden fejlrapport (se `CONTRIBUTING.md`).
