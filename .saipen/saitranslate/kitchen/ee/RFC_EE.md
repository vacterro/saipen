# SAIPEN Protokoll (RFC)

## Osa 1: TUUMIK (Jätkamisprotokoll)

### 1.1 Normatiivsed Reeglid
Võtmesõnu "MUST", "MUST NOT", "REQUIRED", "SHALL", "SHALL NOT", "SHOULD", "SHOULD NOT", "RECOMMENDED", "MAY" ja "OPTIONAL" tõlgendatakse selles dokumendis nii, nagu on kirjeldatud RFC 2119.

- Agent PEAB (MUST) enne täitmist lugema `STATE.md`, `BOARD.md` ja `LOG.md` lõppu. Kõik kolm, ja `KNOWLEDGE/`/`kitchen/`, asuvad projekti juurkaustas `.saipen/` all -- hilisemad mainimised võivad lühiduse mõttes eesliite ära jätta, asukoht ei muutu kunagi. **Kvalifitseerimata tähendab täpselt `.saipen/STATE.md` (ja selle õdesid-vendi) projekti juurkaustas, mitte kunagi pesastatud.** Alates v7.35.0 on `.saipen/extensions/subs/<name>/STATE.md` ja (paralleelse TRANSLATE jooksu ajal) `.saipen/saitranslate/STATE.md` tõelised samade nimedega failid, mis on sügavamal samas puus -- kumbki on selle *teise* instantsi enda olek, mida eristab selle täielik tee, mida ei asendata ega ajeta segi projekti enda omaga. Ära kasuta palja failinime otsimiseks `find`/glob ja ära tegutse selle põhjal, mis esimesena ilmub; kasuta täpset teed.
- Agent EI TOHI (MUST NOT) toetuda projekti oleku osas vestluse kontekstile.
- Agent PEAB degradeerima võimekust, kui hosti tööriistad puuduvad.
- Agent EI TOHI kirjutada saladusi (API võtmeid, tokeneid, paroole, privaatseid mandaate) failidesse `STATE.md`, `BOARD.md`, `LOG.md`, `KNOWLEDGE/`, `.saipen/kitchen/`, `.saipen/extensions/` või `.saipen/saitranslate/kitchen/` -- igaüks neist on mustand või committitud sisu, mis on mõeldud teistele agentidele lugemiseks, kaasa arvatud kitchen failid. Keset ülesannet avastatud saladus redigeeritakse mis tahes kirjutatavas asjas (`sk-***`, mitte tegelik väärtus) ja kasutajal kästakse see välja vahetada, nagu iga muu leiu puhul.
- Agent EI TOHI sooritada hävitavat operatsiooni ilma kasutaja selgesõnalise kinnituseta, välja arvatud juhul, kui aktiivne pilet ise annab eelneva loa JA operatsioon on tagasipööratav. Hävitav hõlmab vähemalt: force-push, haru kustutamine, ajaloo ülekirjutamine, skeemi/andmebaasi drop, massiline failide kustutamine, kasutaja andmete kustutamine ja mis tahes pöördumatu migratsioon. See reguleerib SAIPENi enda tegevust (SHIP, CLEAN ja mis tahes faas, mis puudutab ketast või giti) -- see ei leevenda ega asenda kinnitusdistsipliini, mida opereeriva agendi enda platvorm juba jõustab, see on miinimum, millele iga SAIPEN-iga ühilduv agent PEAB vastama, sõltumata tarnijast.

### 1.2 Failimudel
- **STATE.md**: PEAB sisaldama frontmatterit: `phase`, `task`, `next_action`, `blocker`, `agent`, `saipen_version`, `mode`, `updated`. `saipen_version` (täisarv) salvestab, milline protokolli versioon selle oleku kirjutas, ja kahekordistub allpool oleva versioonikaitseks -- üks väli, mitte kaks. `saipen_home` (string) on tunnustatud VÕIB (MAY) väli: § 1.7 alglaaduri osuti, SAIPENi kodu absoluuttee masinas, mis viimati tegi kontrollpunkti. `next_action` PEAB olema koheselt täidetav käsk -- see hõlmab täpset vormi `WAIT: <spetsiifiline küsimus või vajalik otsus>`.
- **Versioonikaitse**: Kui projekti `saipen_version` on KÕRGEM kui see, mida see agendi enda RFC.md koopia defineerib kehtivana, kirjutas uudem protokoll selle oleku -- agent EI TOHI vaikselt jätkata. Degradeeru režiimi `mode: read-only` ja teata mittevastavusest.
- **BOARD.md**: PEAB jälgima pileti staatust läbi jaotiste `## DOING` / `## TODO` / `## DONE` / `## BLOCKED`. Iga piletirida PEAB järgima kuju: `- [ ] T-### kirjeldus`, märkeruut `[ ]` avatud / `[x]` tehtud / `[/]` pooleli, lisaks valikulised väljad `needs:`, `owner:`, `claim_time:`, `blocker:`, `verify:`. Piletite IDs (T-###) peavad olema unikaalsed.
- **LOG.md**: Ainult-lisa sündmuste graaf. PEAB järgima kuju: `- DATE [E-###] [parent: E-###] [T-###] TAXONOMY: text`.
- **KNOWLEDGE/**: Kataloog püsivate tõdede jaoks. EI TOHI sisaldada sündmuste ajalugusid.
- **kitchen/**: Kataloog vahepealsete, pooleliolevate failide, mustandite ja tööandmete jaoks.

### 1.3 Võimekuse Läbirääkimine
1. Protokolli nõuded.
2. Agendi võimed.
3. Režiimi lukk (`mode: full | read-only | no-publish | manual-verify`).
4. Valikuline Paralleelne Täitmine (`subagents`).

### 1.4 Nõudlus & Omand
- Nõude esitamine: `owner: <AgentID>` ja `claim_time: <ISO8601 UTC>`.
- Aktiivne nõue: `claim_time` alla 15 minuti vana.
- Aegunud nõue: 15+ minutit -> loobumine.

### 1.5 Kontrollpunktid & Taastumine
- **Kontrollpunkt (Checkpointing)**: PEAB tegema kontrollpunkti pärast iga piletit. Järjekord: (1) LOG, (2) BOARD, (3) STATE.
- **Räpane puu**: Salvestamata muudatused on NORMAALNE protokolli olek.
- **Taastumine (Recovery)**: Kui STATE.md on aegunud, taasta viimasest LOG.md kandest.

### 1.6 Tuumik Olekumasin & Pileti DAG
`INIT → PLAN → SCOUT → BUILD → VERIFY → REVIEW → SHIP → DONE | BLOCKED`
- Piletite DAG (`needs: [T-XXX]`).
- VERIFY: Tuleb täita.
- DONE: Ei tohi märkida tehtuks ilma eduka VERIFY-ta.

### 1.7 Tööruumi Hügieen
Protokoll elab SAIPEN kodus; projekt hoiab tööd.

### 1.8 Partii Sisendi Parsimine ("Pole Kiiret" Reegel)
Loo üksikud TODO piletid. Jälgi trailing extrapolatsiooni ('etc.').

### 1.9 Laienduste Avastamine
`.saipen/extensions/<name>/` on valikuline projekti-põhine hook.

### 1.10 Käsupind
- `saipen set` / `saipen init`
- `saipen continue`
- `saipen goal <text>`
- `saipen plan`
- `saipen clean`
- `saipen translate`
- `saipen ship`
- `saipen validate`
- `saipen status`
- `saipen stop`

---

## Osa 2: HOOLDUS (Autonoomne Areng)

### 2.1 Autonoomsed Üleminekud
- TAVAKÄITUMINE: `saipen` on alias `saipen continue` jaoks.
- NULL-VIIBA AUTONOOMIA: Kui töölaud on tühi, mine `HUNT` faasi. Puhas? Mine `ADD` faasi.
- HUNT, CLEAN, TRANSLATE reeglid.

### 2.2 Evolutsiooniline ADD
- Hindab lisa rangelt (bugfix, complementary_feature, jne). Pärast ADD-i mine VERIFY.

### 2.3 Tööstuslik Lõpetamisreegel
Hinda töövoo lõpuni ehitamist üle pimeda lisamise. "Tähista kogu tervik" -- kõige väiksem terviklik lahendus võidab.

### 2.4 Goal Režiim (Autonoomne Täitmine)
`saipen goal <text>` on eesmärgile orienteeritud, jooksu-ulatuses. See kohandab lauda, jätkab peatumata läbi piletite, kuni tabab kaitseklappi (3 lainet / 20 piletit) või toode valmis.
