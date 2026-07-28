# Säkerhetspolicy

## Omfattning

SAIPEN är en specifikation plus en liten uppsättning lokala installations-/exportskript (`bootstrap/inject.ps1`/`.sh`, `uninstall.ps1`/`.sh`, `export.ps1`/`.sh`). Det kör inte en server, samlar inte in telemetri och överför ingen data någonstans. Allt skripten gör är lokala filsystemskrivningar till filer du redan kontrollerar (dina egna `~/.claude`, `~/.gemini`, projektets `.saipen/`, etc.).

Två olika nivåer av försiktighet gäller här, och det är värt att vara exakt snarare än att påstå allmän säkerhet:

- **Dina egna konfigurationsfiler** (`CLAUDE.md`, `AGENTS.md`, `GEMINI.md`, `.aider.conf.yml`) redigeras endast genom att lägga till eller ta bort ett avgränsat `SAIPEN:BEGIN`/`END`-block, och originalfilen kopieras till `<file>.bak` före den första ändringen. Avinstallation skriver dessutom `<file>.uninstalled.bak` före borttagning.
- **Katalogerna för färdigheter (skills)** som injectorn skapar (`~/.claude/skills/saipen` och liknande) är SAIPEN-ägda kopior och **säkerhetskopieras inte**: installation skriver över dem helt och avinstallation tar bort dem rekursivt. Det är avsiktligt -- de innehåller inget annat än kopior av detta repots egna filer -- men om du redigerar en lokal färdighetskopia för hand förloras dessa ändringar vid nästa `inject`/`uninstall`. Förvara anpassningar i ditt eget konfigurationsblock eller en fork, inte i den kopierade färdighetskatalogen.

De två saker som faktiskt är värda en säkerhetsrapport:
1. Ett bootstrapskript som gör något med ditt filsystem eller git-historik utöver vad dess egna kommentarer/README beskriver.
2. Protokollets egna regel för hemlighetshygien (RFC.md § 1.1 -- skriv aldrig API-nycklar, tokens, lösenord i `STATE.md`/`BOARD.md`/`LOG.md`/`KNOWLEDGE/`/`kitchen/`/`extensions/`/`saitranslate/kitchen/`/`recovery/`/`logs/`) som har en verklig lucka som skulle få en agent som följer SAIPEN att läcka en hemlighet till en incheckad fil. De två sista är de subtila: Recovery kopierar en korrupt `STATE.md` ordagrant till `.saipen/recovery/`, och LOG-försegling flyttar rader ordagrant till `.saipen/logs/`, så allt som nådde originalfilen arkiveras av mekanismer vars hela uppgift är att inte ändra innehåll.

## Stödda versioner

Endast den senaste taggade utgåvan på `main` stöds. Detta är en protokollspecifikation, inte en långlivad tjänst -- det finns ingen LTS-gren.

## Rapportera en sårbarhet

Öppna ett GitHub-ärende. Om rapporten rör ett verkligt, för närvarande utnyttjbart problem (inte ett hypotetiskt), markera det som en privat/säkerhetsrådgivning (security advisory) via detta repots **Security**-flik ("Report a vulnerability") istället för ett offentligt ärende, så att det inte är offentligt synligt innan en fix släpps.

Inkludera: vilket skript eller RFC-regel, det konkreta scenariot och vad som faktiskt händer jämfört med vad som borde hända. Samma beviskrav som för andra felrapporter (se `CONTRIBUTING.md`).
