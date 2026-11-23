# SAIPEN

## Agent unustas. Projekt mäletab.

**SAIPEN — failipõhine jätkamisprotokoll tehisintellekti agentidele.**

See hoiab projekti mälu mitte vestluses, mitte teenuse häguses "pikaajalises mälus" ja mitte konkreetse mudeli peas, vaid otse koodi kõrval, tavalistes Markdown-failides.

Täna töötab Claude.
Homme GPT.
Ülehomme Gemini, Qwen või mõni muu elektrooniline šamaan.

Mudel vahetub. Kontekst kaob. Projekt jätkab tööd.

**Agent dies. Project remembers.**
**Agent kaob. Projekt mäletab.**
**エージェントは消える。プロジェクトは覚える。**
*[Ējento wa kieru. Purojekuto wa oboeru. Agent kaob. Projekt mäletab.]*

---

## Probleem

Tavaline coding agent elab nagu kuldkala terminali juurdepääsuga.

Ta õpib kakskümmend minutit projekti, mõistab arhitektuuri, leiab vea, hakkab seda parandama — ja jookseb piirangusse või suletakse.

Tuleb uus agent:

> Mida me teeme?
> Millised failid on olulised?
> Mida on juba kontrollitud?
> Mida ei tohi puutuda?
> Jätkata?

Ja inimene jutustab projekti loo uuesti. Siis veel kord. Siis kirjutab tohutu `CLAUDE.md`. Siis muutub fail vanade otsuste, juhuslike keeldude ja fraaside pühaks prügimäeks, mida mudel kunagi valesti mõistis.

SAIPEN ütleb:

> Lõpeta projekti hoidmine vestluses.
> Pane olek projekti kõrvale.
> Uus agent loeb selle ja jätkab.

---

# Mida SAIPEN oskab

## 1. Jätkata tööd ilma vestlusloata

Kasutaja kirjutab:

```text
saipen continue
```

või lühidalt:

```text
cc
```

Külm agent loeb:

```text
STATE.md
BOARD.md
LOG.md saba
human_note
```

Seejärel täidab ta kirja pandud `next_action`i.

Ei korralda intervjuusid.
Ei palu arhitektuuri korrata.
Ei koosta vana plaani peale uut plaani.
Ei teeskle, et "tutvus kontekstiga", olles lugenud esimesed kakskümmend rida.

Ta jätkab tööd konkreetsest kohast.

---

## 2. Hoida projekti mälu lihtsates failides

SAIPEN jagab mälu eesmärgi järgi.

### `STATE.md`

Vastab küsimusele:

> Mida teha praegu?

Seal on praegune faas, aktiivne ticket, töörežiim, täpne järgmine tegevus ja olulised piirangud.

### `BOARD.md`

Vastab:

> Milline töö eksisteerib?

Ülesanded on jagatud:

```text
DOING
TODO
BLOCKED
DONE
```

Igal ülesandel on prioriteet, sõltuvused, kontrollitingimused ja blokeerimise põhjus.

### `LOG.md`

Vastab:

> Mis tegelikult juhtus ja miks me siin oleme?

Mitte "me kavatseme kontrollida".
Mitte "ilmselt parandatud".
Vaid konkreetne sündmus, käsk, tulemus ja seos varasemate otsustega.

### `KNOWLEDGE/`

Vastab:

> Mis on projekti kestev tõde?

Arhitektuurilised otsused, piirangud, kokkulepped ja ADR-id ei upu kilomeetripikkusesse ajutisse logisse.

### `kitchen/`

Töölaud.

Mustandid, vahepealsed materjalid, ettevalmistatud paketid ja lõpetamata töö jäävad sinna, et sessiooni surm ei muudaks poolt tundi tööd tuhaks ja filosoofiaks.

---

## 3. Anda agendile üks täpne järgmine tegevus

SAIPENi süda on väli:

```yaml
next_action:
```

Agent ei pea igal sessioonil uuesti otsustama, mida teha.

Projekt teab järgmist sammu juba ette:

```text
PHASE SCOUT T-399
RUN validate.py
VERIFY T-501
WAIT: destructive-op
SHIP release
```

Üks state.
Üks käsk.
Üks reaalsus.

Mida vähem agent protsessi juhtimises improviseerib, seda rohkem aju jääb ülesande enda jaoks. Harv juhtum, kus bürokraatia ei sega tööd, vaid hoiab närvivõrku kruvikeerajaga metsa jooksmast.

---

## 4. Juhtida tööd range olekumasinaga

Töö liigub faaside kaupa:

```text
INIT
→ PLAN
→ SCOUT
→ BUILD
→ VERIFY
→ REVIEW
→ SHIP
→ DONE
```

On ka erifaasid:

```text
BLOCKED
HUNT
MARKHUNT
ADD
CLEAN
TRANSLATE
PREPARE
VALIDATE
```

Iga faas teab:

* mida agent peab lugema;
* mida tal on lubatud muuta;
* mis loetakse lõpetamiseks;
* kuhu edasi minna;
* millal peatuda;
* milliseid tõendeid jätta.

Agent ei tohi ülesannet valmis kuulutada kohe pärast esimest rohelist testi. Kõigepealt BUILD, siis VERIFY, siis REVIEW, siis SHIP.

Sest "mul läks üks kord käima" ei ole inseneristandard. See on rahvausk.

---

## 5. Töötada erinevate mudelite ja tööriistadega

SAIPEN ei kuulu ühele firmale.

Ta on loodud töötama:

* Claude Code;
* OpenAI Codex;
* Gemini;
* OpenCode;
* Aider;
* Antigravity;
* DeepSeek;
* Qwen;
* muude agentidega, kes oskavad faile lugeda ja käsklusi täita.

Platvormidele on adapterid ja injektorid, aga alus jääb samaks:

```text
tavalised failid
tavaline Git
tavaline Markdown
```

Ei mingeid proprietary memory lahendusi.
Ei mingit kohustuslikku andmebaasi.
Ei mingit igavest taustadaemoni, mis homme uuendab ennast ja otsustab, et su projekt peab nüüd pilvepotis elama.

---

## 6. Täita pikka eesmärki iseseisvalt

Käsk:

```text
saipen goal <objective>
```

lülitab sisse Goal Mode'i.

SAIPEN:

1. fikseerib eesmärgi;
2. ehitab või ehitab ümber järjekorra;
3. valib järgmise teostatava ticketi;
4. täidab selle;
5. kontrollib;
6. teeb review'd;
7. jätkab järgmisega;
8. ei küsi iga sammu järel: "Jätkata?"

On olemas safety limits lainete ja ticketite arvu kohta. Autonoomia ei tähenda igavest kuu all hulkumist repositooriumis.

Goal Mode töötab ühe ausa lõpptulemuseni:

```text
eesmärk on saavutatud;
töö on blokeeritud;
safety valve käivitus;
saadaolev töömaht on ammendatud.
```

---

## 7. Leida ise järgmine kasulik töö

Kui tavaline backlog saab otsa, võib Maintenance-kiht minna tsüklisse:

```text
HUNT
→ ADD
→ HUNT
```

### HUNT

Otsib:

* päris defekte;
* vastuolusid;
* katkiseid kontrollimisi;
* surnud koodi;
* arhitektuurilist triivi;
* kaitsmata kohustuslikke reegleid;
* lahknevusi dokumentatsiooni ja käitumise vahel.

### ADD

Kui ilmseid defekte enam pole, pakub järgmist loomulikku funktsiooni, mis jätkab olemasolevat arhitektuuri.

Ei korralda loomingulist festivali.

SAIPEN areneb evolutsiooniliselt:

```text
olemasolev muster
→ ilmne lünk
→ minimaalne laiendus
→ kontroll
```

Mitte nii:

```text
agendil hakkas igav
→ kirjutas poole projekti Rusti ümber
→ nimetas seda modern architecture'ks
```

---

## 8. Eristada auditit parandusest

SAIPEN lahutab mitu tegevust, mida mudelid armastavad ühte patta panna.

### `markhunt`

Viib läbi laia auditi ja salvestab leiud.

Ei paranda midagi.

See on oluline: kõigepealt fikseerida fakt, siis muuta projekti.

### `hunt`

Töötleb kinnitatud leiud ja muudab need korralikeks ülesanneteks.

### `validate`

Kontrollib SAIPENi enda oleku struktuurilist terviklikkust ja parandab lubatud kahjustused.

### `test`

Käivitab deklareeritud testid ja teatab PASS või FAIL.

Ei paranda testi kontrollimise ajal salaja.

### `clean`

Eemaldab prügi, puhastab tahvli ja seab struktuuri korda, aga peab enne failide liigutamist või kustutamist linke ja sõltuvusi kontrollima.

Sest fail võib näida orvuna, kuni programm teda kell kolm öösel välja kutsub.

---

## 9. Nõuda tõendeid ilusa aruande asemel

SAIPEN on ehitatud tüüpiliste LLM-harjumuste vastu:

* väita, et fail on loetud, kuigi seda ei loetud;
* öelda, et testid läksid läbi, ilma neid käivitamata;
* välja mõelda usutav tee;
* peatuda pärast esimest rohelist tulemust;
* ülesanne ümber jutustada selle täitmise asemel;
* võtta kasutaja viimane repliik projekti uue tõena;
* muuta ajutine oletus püsivaks reegliks.

Sellepärast jätab töö maha jälje:

```text
faili muutus;
LOG-sündmus;
BOARD-i muutus;
STATE-i muutus;
käsk ja selle tulemus;
verification evidence.
```

Kui agent midagi ei teinud, peab ta seda ütlema, mitte koostama aruannet suurest sisemisest ettevalmistusest.

SAIPENis kaalub sõna "valmis" üksi umbes sama palju kui poekviitung ilma kauba nimeta.

---

## 10. Kontrollida protokolli ennast

SAIPENil on oma conformance-kiht.

See kontrollib:

* oleku õigsust;
* lubatud faasisiirdeid;
* ticketite kuju;
* sõltuvusi;
* sündmuste järjekorda;
* linke dokumentide vahel;
* skeemidele vastavust;
* reeglite katet kontrollidega;
* tööd PowerShellis ja shellis;
* rikkumise ja taastamise stsenaariume;
* mutatsioonilisi red control'e.

Kontroll peab suutma punaseks minna, kui reegel on katki.

Kui test on alati roheline, pole see test. See on toalill.

---

## 11. Üle elada katkestusi ja agendi vahetust

SAIPEN kasutab checkpointe.

Enne ohtlikku üleminekut salvestab agent:

* praeguse faasi;
* aktiivse ticketi;
* tehtud osa;
* kontrollimise tulemused;
* järgmise sammu;
* töökataloogi oleku.

Kui agent suri, jäi kinni, jooksis limiiti või suleti, ei alusta järgmine vestluses arheoloogilisi kaevamisi.

Ta loeb checkpointi ja jätkab.

**継続 — keizoku — jätkamine.**

Mitte kangelaslik mälutaastamine. Tavaline rutiinne operatsioon.

---

## 12. Mitte hävitada kellegi teise lõpetamata tööd

Määrdunud Git tree on SAIPENi jaoks projekti normaalne seisund.

Agent peab kindlaks tegema:

* millised muudatused kuuluvad tema ticketile;
* millised jättis kasutaja;
* millised kuuluvad teise lõpetamata töö alla;
* mida võib praegusesse release'i kaasata;
* mida ei tohi puutuda.

SAIPEN keelab:

* ootamatud `reset`id;
* teiste inimeste failide tagasikerimise;
* commitimata töö kustutamise;
* massilise ülekirjutamise ilma kontrollita;
* teeseldud "puhastamise" arusaamatu kustutamise kaudu.

Põhimõte on lihtne:

> Kui sa ei tea, kelle oma see on — ära puutu.

---

## 13. Peatuda ausalt

Kui töö tõesti jätkuda ei saa, kasutab SAIPEN selget `WAIT:` või viib ticketi `BLOCKED`i.

Põhjus peab olema konkreetne:

```text
vajalik käsitsi kontroll;
destruktiivseks toiminguks on vaja luba;
puudub capability;
kohustuslik otsus on teadmata;
vajalik esimene publish;
on olemas väline blocker;
käivitus safety valve.
```

Agent ei tohi arvata.

Aga ta ei tohi ka iseenda laiskuse tõttu blokeeruda.

Info puudumine — stop.
Soovimatus faili vaadata — ei ole stop.

---

## 14. Näidata projekti tegelikku olekut

Käsk:

```text
saipen status
```

töötab ainult lugemisel.

See näitab:

* praegust faasi;
* aktiivset ülesannet;
* järgmist tööd;
* mis ootab kasutajat;
* millised tulemused on kuulutatud, aga veel tõestamata;
* millal conformance-kontroll viimati läbis;
* kui aegunud on praegune olek;
* millised ülesanded on blokeeritud.

SAIPEN ei kuuluta oma projekti "terveks" ega "production ready'ks".

Ta näitab fakte. Järelduse teeb inimene.

Agent, kes iseendale medali andis, on ikkagi agent, kes iseendale medali andis.

---

## 15. Anda töö üle spetsialiseeritud tehastele

SAIPEN toetab isoleeritud producer-protsesse.

Nad töötavad põhipuust eraldi ja annavad tulemuse üle `OUTBOX.md` kaudu.

Näited:

### `saihunt`

Otsib defekte ja kahtlaseid kohti.

Andur. Mitte remondimees.

### `saitest`

Muudab kahtluse reprodutseeritavaks faktiks või tapab valehüpoteesi.

Ta loob adversarial-scenariume:

* vale sisend;
* piirväärtused;
* järjekorra rikkumine;
* korduvad väljakutsed;
* rikutud olek;
* resource pressure;
* hostile environment.

### `saipython`

Võtab väiksed Python-defektid, parandab koopia isoleeritud tööruumis, kontrollib ja annab üle valmis patch'i.

Põhipuud ise ei redigeeri.

### `saitranslate`

Valmistab mitmekeelse paketi Core'ist eraldi.

### `saiwiki`

Valmistab dokumentatsiooni ja wiki-paketi, mis on seotud konkreetse lähtekoodi olekuga.

Core võtab vastu ainult värske, kontrollitud ja täieliku paketi.

Ei mingeid:

> Ma nagu midagi tegin seal, vaata naabervestlusest.

Ainult payload, instructions, source commit ja evidence.

---

## 16. Viia töö läbi tööstusliku konveieriga

Crew Circuiti käsk ajab projekti läbi jadast:

```text
sense
→ reproduce
→ intake
→ build
→ verify
→ review
→ translate
→ document
→ publish
```

Iga etapp annab järgmisele edasi mitte lubaduse, vaid:

```text
reproduktsiooni;
otsuse;
ticketi;
paketi;
tõendi.
```

Kui etapp on tühi — fikseeritakse see tulemusena.

Kui etapp on blokeeritud — konveier peatub.

Osalist tulemust ei anta edasi märkusega "seal nagu on korras".

Praegune Crew Circuit on jadaline. Täisväärtuslik konkureeriv Crew Mode koos atomaarsete claim'ide, epoch'ide, worktree'de ja release captain'iga projekteeritakse eraldi ega esitleta juba lahendatud ülesandena.

---

## 17. Säästa konteksti

SAIPEN kasutab lazy loadingut.

Agent loeb kõigepealt väikese BOOT-kernel'i ja INDEXi.

Seejärel laeb ta ainult:

* aktiivse faasi dokumendi;
* vajaliku Core reegli;
* spetsialiseeritud dokumendi praeguseks tööks;
* asjakohase kestva projektimälu.

Ta ei pea igal sessioonil üle lugema kogu põhiseadust, riigi ajalugu ja validaatori sugupuud.

See vähendab:

* token costi;
* tähelepanu hajumise tõenäosust;
* vanade juhiste konflikti;
* ebaoluliste reeglite mõju;
* cold-start aega.

**Vähem müra, rohkem tööd.**

---

## 18. Töötada ilma kohustusliku infrastruktuurita

SAIPENi alus:

```text
Markdown
Git
failisüsteem
stdlib Python täisvalidaatori jaoks
```

Ilma Pythonita jääb alles kaasaskantav shell/PowerShell validation floor.

Projekti saab avada Obsidian vault'ina.

`KNOWLEDGE/` on graafis nähtav.
Tavalised lingid töötavad.
Olek on inimesele loetav.
Git näitab kogu muudatuste ajalugu.

Ei mingit varjatud maagiat.

Kui SAIPEN katki läheb, saab selle notepadis avada ja aru saada, mis juhtus.

Seda kutsutakse süsteemiks. Kõike muud kutsutakse vahel dashboard'iks.

---

# Põhikäsud

```text
saipen set                 võta projekt
saipen continue            jätka tööd
saipen plan                loo plaan ja ticketid
saipen goal <text>         täida eesmärk autonoomselt
saipen status              näita olekut, ära muuda midagi
saipen stop                salvesta checkpoint ja peatu
saipen hunt                otsi defekte
saipen markhunt            viia läbi lai audit
saipen test                käivita testid
saipen validate            kontrolli struktuuri
saipen clean               puhasta projekt
saipen prepare             valmista handoff
saipen collect             võta vastu valmis pakett
saipen translate           valmista tõlked
saipen ship                lase välja release
saipen crew                läbi kogu tootmistsükkel
```

Sagedasteks toiminguteks on lühikesed klahvid:

```text
cc     jätka
sss    näita olekut
ss     salvesta checkpoint ja peatu
```

Käsk on kogu sõnum. Mitte ühtegi nelja lõigu loitsu.

---

# Mida SAIPEN ei tee

SAIPEN ei ole uus LLM.

Ta ei tee nõrgast mudelist geniaalset.

Ta ei garanteeri, et agent ei eksi kunagi.

Ta ei ole sadade masinate jaoks mõeldud hajus konsensus-algoritm.

Ta ei asenda teste, Giti ja insenerimõtlemist.

Ta ei tohi hoida saladusi ega kasutajaandmeid ilma vajaduseta.

Ta teeb teisiti:

> Viga muutub nähtavaks.
> Töö muutub jätkatavaks.
> Olek muutub kontrollitavaks.
> Agent muutub asendatavaks.

---

# Kellele see on

SAIPEN on kasulik, kui:

* töötad mitme AI coding agent'iga;
* jooksed pidevalt session limits'i;
* vahetad mudeleid hinna, saadavuse või ülesande järgi;
* juhid projekti kauem kui üks vestlus;
* oled väsinud agendile sama asja seletamast;
* tahad ülesannete järjekorda ilma iga sammu järel käsitsi `continue`ta;
* tahad näha vahet "tehtud" ja "tõestatud" vahel;
* ei usalda vestluse maagilist mälu;
* eelistad avatud faile kinnisele infrastruktuurile;
* tahad, et projekt elaks üle iga konkreetse agendi surma.

---

# Ühes lauses

**SAIPEN muudab tehisintellekti unustavast vestluskaaslasest asendatavaks tööliseks, kes tuleb tsehhi, loeb projekti oleku, võtab järgmise ülesande, jätab tõendid maha ja ei nõua kogu tehase eluloo ümberjutustamist.**

```text
Vestlus kadus.
Mudel vahetus.
Limiit sai otsa.
Projekt ei unustanud.
```

**SAIPEN. One command. Zero dependencies. Zero amnesia.**
