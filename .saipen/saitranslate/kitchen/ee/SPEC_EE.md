# SAIPEN Spetsifikatsioon

## Abstraktne
**Disaini Eesmärk #1: Külm agent ilma vestlusajaloota peab suutma käivitada `/saipen continue` ja jätkata produktiivset tööd ühe minuti jooksul, ilma et ta paluks kasutajal konteksti korrata.**

SAIPEN garanteerib, et mis tahes ühilduv AI-agent saab turvaliselt jätkata mis tahes projekti ilma uue briifinguta. See on ABI (rakenduse binaarliides) inseneride AI-agentidele -- ühilduvuskiht, mis lahendab amneesiaprobleemi. Olenemata sellest, kas kasutate täna Claude'i, homme Geminit ja ülehomme GPT-d, tegutsevad nad kõik sama projekti oleku alusel, ilma et peaksite konteksti kordama.

### Põhifilosoofia: Projekti Olek > Mudeli Mälu
Mälu peaks elama koodi kõrval, mitte teise mudeli peas. SAIPEN muudab paradigmat `Projekt -> Mälu -> LLM` asemel `Projekt -> SAIPEN Olek -> LLM`. Mälu kuulub projektile.

Oma tuumas kasutab SAIPEN portatiivset, failipõhist jätkamisprotokolli LLM agentidele. Implementatsioonid VÕIVAD erineda. Kettal olev leping PEAB jääma stabiilseks. Kõik selles protokollis eksisteerib Jätkamistesti teenimiseks.

SAIPEN on evolutsiooniline, mitte loominguline. Selle eesmärk on tarkvara lõpule viia, mitte seda uuesti leiutada. ADD laiendab olemasolevaid disainimustreid, tööstuskonventsioone ja ilmselget funktsioonide sümmeetriat.

- **`STATE`**: Eksisteerib, et vastata küsimusele *"Mida ma praegu teen?"*
- **`BOARD`**: Eksisteerib, et vastata küsimusele *"Millise ülesande ma võtan?"*
- **`LOG`**: Eksisteerib, et vastata küsimusele *"Miks me siia jõudsime?"*
- **`KNOWLEDGE`**: Eksisteerib, et vastata küsimusele *"Mis on selle projekti püsiv tõde?"*
- **`next_action`**: SAIPENi süda. See vastab küsimusele *"Millise täpse käsu ma kohe praegu käivitan, et tööd jätkata?"*

## SAIPEN Lakmustest

Iga pakutud muudatus või uus idee protokollis PEAB läbima järgmised kolm küsimust:
1. Kas see muudab agentide vahelise ülemineku töökindlamaks?
2. Kas see muudab erinevate mudelite käitumise ühtlasemaks?
3. Kas see vähendab konteksti kaotamise tõenäosust?

Kui vastus on "ei" vähemalt kahele neist küsimustest, lükatakse idee tagasi. SAIPEN eelistab distsipliini, reprodutseeritavust ja töökindlust uudsusele.

## Arhitektuur

Protokoll on rangelt normatiivne. SAIPEN jaguneb kontseptuaalselt kaheks kihiks: **Tuumik** (Core) ja **Hooldus** (Maintenance).
- **Tuumikkiht** tagab turvalise, tootjast sõltumatu ülesannete jätkamise.
- **Hoolduskiht** on tuumikule ehitatud autonoomne tarkvara arengumudel.

Nende kahe kihi all eraldab SAIPEN kolm valdkonda, mis kunagi ei põimu:
**õigsus ja jätkamine** (Tuumik -- `STATE`/`BOARD`/`LOG`/`KNOWLEDGE`, võimekuse
läbirääkimine, kontrollpunktid), **järelevalveta areng** (Hooldus -- `HUNT`/`ADD`/`CLEAN`,
täielikult funktsionaalne tavalise `saipen`/`saipen continue` vaikeseadistuse all) ja **läbilaskevõime**
(Goal Režiim, Alamagendid -- mõlemad selgesõnaliselt vabatahtlikud, §1.3/§2.4). Lülita Goal Režiim välja:
protokoll on muutumatu, üks pilet korraga. Lülita Alamagendid välja: `HUNT` käivitab samad
kuus kategooriat järjestikku, sama tulemus. Kasuta ainult Tuumikut, ilma Hoolduskihita
üldse: see kehtib endiselt -- külm agent jätkab endiselt õigesti. Iga kiht toetub
allpool olevale, ilma et vastupidine oleks kunagi tõsi; miski ülesvoolu ei sõltu
allavoolu funktsiooni olemasolust.

```text
saipen/
  RFC.md                    normatiivne spetsifikatsioon (jagatud Tuumikuks ja Hoolduseks)
  CONFORMANCE.md             enese-kontrolli vektorid + stsenaariumide katvustabel
  SKILL.md                  õhuke sisenemispunkt oskusi-lugevatele platvormidele
  STYLE.md                  hääled: vestlus, LOG.md, artefaktid
  UI.md                     Dark Golden Win95 UI spetsifikatsioon (kohustuslik kasutajaliidese tööks)
  phases/                   range olekumasina loogika
    [Tuumikfaasid]
    init.md / plan.md / scout.md / build.md / verify.md / review.md / ship.md / done.md / blocked.md
    [Hooldusfaasid]
    hunt.md / add.md / clean.md / translate.md
    
    validate.md             vastavuse testimine

extensions/                 <- KOHANDUV KIHT
  adapters/                 mudelipõhised juhiste sillad, platvormidele, mida
                             injektor automaatselt ei tuvasta (README.md viitab siia)
  schemas/                  state.schema.json on masinloetav tööriistaga tools/validate.py
                             (STATE kuju ainuke tõeallikas); board/log
                             skeemid jäävad ainult viitamiseks (vaata schemas/README.md)
  templates/                värske .saipen/ standardmall
  security/                 NÄIDIS hook kopeerimiseks projekti (RFC § 1.9, kinnitub VERIFY külge)
  performance/              NÄIDIS hook kopeerimiseks projekti (RFC § 1.9, kinnitub REVIEW külge)
  subs/                     NÄIDIS kirjutuskaitstud uurimisalamagendid (RFC § 1.9) -- oma
                             STATE/BOARD/LOG iga alamagendi kohta, leiud ainult OUTBOX kaudu,
                             mitte kunagi teist kirjutusteed projekti

bootstrap/                  <- PAIGALDUS/EKSPORT/EEMALDAMINE, üks masin korraga
  inject.ps1 / .sh          paigaldab SAIPEN ploki + oskuste koopiad (README Kiirjuhend)
  uninstall.ps1 / .sh       tühistab paigalduse -- eemaldab plokid + oskuste koopiad
  export.ps1 / .sh          arhiveerib projekti .saipen/ varukoopiaks

tools/                      <- KANOONILINE VALIDAATOR & REPO UTILIIDID
  validate.py               kanooniline vastavuse validaator (stdlib Python, null
                             paigaldust; valideerib STATE otse state.schema.json
                             vastu, pluss graafikontrollid, mida kestapaar teha ei saa)
  install_hook.py           paigaldab pre-commit hooki, mis käivitab validate.py
  uninstall_hook.py         eemaldab täpselt selle hooki (taastab varasema)

tests/                      <- VASTAVUSE KIHT
  validate.ps1 / .sh        külmutatud portatiivne põhi hostidele ilma Pythonita --
                             uued kontrollid maanduvad ainult tools/validate.py sees
  scenarios/                näidisolekud (krahhist-taastumine, nõuete-konfliktid jne)
```

## Kahesuunaline Võimekuse Läbirääkimine
Agendid ei deklareeri lihtsalt, mida nad teha suudavad; protokoll nõuab, mis on vajalik.
Projekt defineerib oma olekus `requires: [filesystem, git, shell, python]`. Agent võrdleb oma hosti võimekusi nõuetega ja lukustub `mode` režiimi (nt `full`, `read-only`).

## Graafipõhine Sündmuste Logimine
Logid SAIPENis ei ole lineaarsed stringid. Nad moodustavad atsüklilise otsuste graafi, kasutades Sündmuse ID-sid (`E-001`). See võimaldab keerulist hargnemist, agentide ühendamist ja täpseid auditeerimisjälgi.

## Arhitektuuri Otsuste Kirjed (ADR)
Mööduvad sündmustelogid ei sisalda püsivaid teadmisi. SAIPEN nõuab, et struktuursed arhitektuursed otsused salvestataks ADR-idena (nt `KNOWLEDGE/ADR-001-use-sqlite.md`).

## Konkurents & Jaotumise Piirid
SAIPEN tagab oleku terviklikkuse failipõhiste nõuete (`owner`, `claim_time`) ja järjestikuste graafide (`LOG.md`) kaudu. Kuid **SAIPEN on olekuprotokoll, mitte hajutatud konsensusalgoritm.**
- **Lokaalne/Jagatud Failisüsteem**: Konfliktide lahendamine tugineb atomaarsetele failisüsteemi kirjutamistele ("esimene commit võidab").
- **Võrgu/Hajutatud Keskkonnad**: Kui agendid töötavad lahtiühendatud masinates ilma reaalajas failide sünkroonimiseta, tekivad võidujooksud (race conditions) `BOARD.md` nõuetele. Väga hajutatud seadistustes PEAB SAIPEN kettal olev protokolli leping jääma stabiilseks -- projekti olek ise muteerub endiselt pidevalt, läbi SAIPENi enda reeglite (§ 1.5 kontrollpunktid), mitte kunagi protokolli kuju, mida need reeglid järgivad.

<p align="center">
  <img src="assets/SAIPEN_design2_alpha.png" alt="SAIPEN Stamp" width="120"/>
</p>
