# Bijdragen aan SAIPEN

SAIPEN is in de eerste plaats een specificatie, en pas daarna een implementatie. De meeste bijdragen
zijn wijzigingen aan `saipen/RFC.md`, een `phases/*.md` bestand, of de conformiteitstools
in `tests/` -- niet aan applicatiecode.

## Voordat u een wijziging voorstelt

Voer de [SAIPEN Lakmoesproef](SPEC.md#de-saipen-lakmoesproef) uit tegen uw
idee:
1. Maakt het de overgang tussen agenten betrouwbaarder?
2. Maakt het het gedrag van verschillende modellen uniformer?
3. Vermindert het de kans op contextverlies?

Als het antwoord "nee" is op minstens twee hiervan, valt het buiten het bereik van dit
protocol, hoe nuttig het elders ook mag zijn.

## Een tekortkoming melden

Open een issue en beschrijf:
- in welk bestand/sectie de tekortkoming zit (RFC.md, een fasedocument, een schema, een test)
- het concrete bewijs (een citaat, een commando en de bijbehorende uitvoer, een scenario waarin
  het huidige gedrag faalt)
- wat u in plaats daarvan zou verwachten

Vage rapportages ("dit voelt niet goed") zijn moeilijker om actie op te ondernemen dan een specifieke
`grep`/reproductie. Zie het bugrapport issue-sjabloon voor de vorm die dit
zou moeten aannemen.

## Een wijziging aanbrengen

1. Lees `saipen/RFC.md` en het/de relevante `phases/*.md` bestand(en) volledig voordat
   u bewerkingen uitvoert -- de meeste schijnbare tekortkomingen blijken elders al te zijn behandeld,
   of zijn bewust op een bepaalde manier afgebakend om een gedocumenteerde reden.
2. Controleer `CHANGELOG.md` en `.saipen/KNOWLEDGE/decisions.md` voor eerdere werken.
   Heropen niet stilletjes een beslissing die al is genomen en afgewezen --
   als u nieuw bewijs heeft dat een eerdere afwijzing onjuist was, vermeld dit dan expliciet
   in de PR-beschrijving.
3. Elke normatieve wijziging (een MUST/MUST NOT/SHOULD) vereist een vermelding in `CHANGELOG.md`
   en, waar praktisch mogelijk, dekking in `tests/validate.sh` +
   `tests/validate.ps1` (beide platformen) of een testscenario onder
   `tests/scenarios/`.
4. Voer de canonieke validator uit voordat u een PR opent:
   ```bash
   python tools/validate.py
   ```
   Dit is degene die ertoe doet -- het controleert `STATE.md` tegen `extensions/schemas/state.schema.json`, doorloopt de `LOG.md` gebeurtenisgrafiek over verzegelde segmenten heen, en verifieert het runtime-manifest en de injector-bedrading. `tests/validate.sh` / `validate.ps1` zijn de **bevroren draagbare vloer** voor hosts zonder Python (dat staat bovenaan elk bestand): minder controles, alleen bewaard zodat een host zonder Python niet met lege handen staat. Voer ze ook uit als uw wijziging een van hen raakt, maar nooit *in plaats van* -- alleen de vloer doorstaan bewijst veel minder dan het lijkt. CI voert de canonieke validator uit bij elke push en PR, ongeacht (`.github/workflows/validate.yml`).
5. Verhoog `VERSION` volgens het schema in `phases/ship.md` (patch voor alleen-documentatie
   verduidelijkingen, minor voor nieuw normatief gedrag, major voor wijzigingen in het contract
   die compatibiliteit verbreken) en houd de versiebadge in `README.md` synchroon --
   `tests/validate.sh`/`.ps1` controleren dit automatisch wanneer ze worden uitgevoerd vanuit een
   kloon van deze repository.

## Stijl

- Protocol- en fasedocumenten: beknopt, RFC-2119 sleutelwoorden waar ze ertoe doen, geen
  opvulling. Zie `saipen/STYLE.md`.
- Alles in dit bestand, commitberichten, codeopmerkingen, en de
  CHANGELOG: neutraal en professioneel. De eigen chat/LOG stemmen van het project
  (`saipen/STYLE.md`) zijn niet van toepassing op artefacten.

## Wat buiten bereik valt

- SAIPEN omvormen tot een gedistribueerd consensussysteem. Zie
  de sectie Gelijktijdigheid & Distributiegrenzen in `SPEC.md`.
- Machinaal leesbare LOG markeergrammatica voorbij het bestaande skelet.
  `LOG.md` blijft proza rond een vaste vorm.
- Een `saipen doctor` commando of iets vergelijkbaars dat overbodig is met `saipen validate` +
  `saipen status`.

Deze zijn elk al eerder voorgesteld en geëvalueerd; om ze te heropenen is
nieuw bewijs nodig, niet enkel opnieuw vragen.
