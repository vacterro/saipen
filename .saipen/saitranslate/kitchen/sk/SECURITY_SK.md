<!-- TRANSLATED TO SK -->
# Security Policy

## Rozsah

SAIPEN je špecifikácia plus malá sada lokálnych inštalačných/exportných
skriptov (`bootstrap/inject.ps1`/`.sh`, `uninstall.ps1`/`.sh`,
`export.ps1`/`.sh`). Nespúšťa server, nezbiera telemetriu
a nikde neprenáša žiadne dáta. Všetko, čo skripty robia, sú lokálne
zápisy do súborového systému na súbory, ktoré už ovládate
(vlastné `~/.claude`, `~/.gemini`, projektový `.saipen/` atď.).

Platia tu dve rôzne úrovne starostlivosti a stojí za to byť presný
namiesto tvrdenia o všeobecnej bezpečnosti:

- **Vaše vlastné konfiguračné súbory** (`CLAUDE.md`, `AGENTS.md`, `GEMINI.md`,
  `.aider.conf.yml`) sú upravované iba pridaním alebo odstránením
  ohraničeného bloku `SAIPEN:BEGIN`/`END` a originál je skopírovaný do
  `<file>.bak` pred prvou úpravou. Odinštalovanie navyše zapíše
  `<file>.uninstalled.bak` pred odstránením.
- **Adresáre zručností**, ktoré injector vytvára (`~/.claude/skills/saipen`
  a podobne) sú kópie vlastnené SAIPENom a **nie sú** zálohované: inštalácia
  ich hromadne prepisuje a odinštalovanie ich rekurzívne odstraňuje. To je
  zámerné -- neobsahujú nič iné ako kópie súborov tohto repozitára --
  ale ak ručne upravíte lokálnu kópiu zručnosti, tieto úpravy sa stratia pri
  najbližšom `inject`/`uninstall`. Vlastné úpravy uchovávajte vo vlastnom
  konfiguračnom bloku alebo forku, nie v skopírovanom priečinku zručnosti.

Dve veci, ktoré skutočne stoja za bezpečnostnú správu:
1. Bootstrap skript robiaci niečo s vaším súborovým systémom alebo git históriou
   nad rámec toho, čo popisujú jeho vlastné komentáre/README.
2. Vlastné pravidlo hygieny tajomstiev protokolu (RFC.md § 1.1 -- nikdy nezapisovať
   API kľúče, tokeny, heslá do `STATE.md`/`BOARD.md`/`LOG.md`/
   `KNOWLEDGE/`/`kitchen/`/`extensions/`/`saitranslate/kitchen/`/
   `recovery/`/`logs/`) s reálnou medzerou, ktorá by spôsobila, že agent
   dodržiavajúci SAIPEN unikne tajomstvo do skommitovaného súboru. Posledné dve
   sú tie záludné: Recovery skopíruje poškodený `STATE.md` doslovne do
   `.saipen/recovery/` a LOG sealing presúva riadky doslovne do
   `.saipen/logs/`, takže čokoľvek, čo sa dostalo do originálu, je archivované
   mechanizmom, ktorého celou úlohou je nemeniť obsah.

## Supported Versions

Only the latest tagged release on `main` is supported. This is a
protocol specification, not a long-lived service -- there is no LTS
branch.

## Reporting a Vulnerability

Open a GitHub issue. If the report involves a real, currently-exploitable
problem (not a hypothetical), mark it as a private/security advisory via
this repository's **Security** tab ("Report a vulnerability") instead of
a public issue, so it isn't publicly visible before a fix ships.

Include: which script or RFC rule, the concrete scenario, and what
actually happens vs. what should happen. Same evidence standard as any
other bug report (see `CONTRIBUTING.md`).
