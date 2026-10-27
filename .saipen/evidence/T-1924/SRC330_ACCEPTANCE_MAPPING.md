# SRC-330 acceptance mapping (T-1924)

Mõõdetud 2026-10-27. See dokument **ei väida taastamist**. Ta kaardistab iga
SRC-330 acceptance-punkti kas otsese, käesolevas repos korratava tõendi või
selgesõnaliselt avatud kohustusega, mille omanik on nimetatud.

Alus: `.saipen/archive/source/SRC-330.md`, SHA-256
`eee73aad905e76b0adef553fcef4938029393f7614606acb35b06e504d8ea41e`,
22 789 baiti. FastPrompteri HEAD mõõtmise hetkel:
`e1f0cadcc64d17b7420c293be3b0cf815f06771e`.

## 1. Miks T-1921 suleti ja mida see ei tõestanud

T-1921 suleti `own_patch`-ina ning selle LOG-kirjed E-18305/E-18306 viitavad
T-1912 seitsme testi ingress-receiptile. See receipt tõestab SAIPEN-i origin-
reconcilation'it ehk host-ingressi ennast. See ei puuduta FastPrompteri heli,
`resolve_sound_ref()`-i ega ühtegi SRC-330 R-punkti. Dokumenteeritud analüüs
ei ole heli taastamine.

T-1924 ei muuda SRC-330 lähteteksti ega väida, et missioon on täidetud.

## 2. Blokeerija faktiline kontroll

Blokeerija väitis, et FastPrompteri kanooniline ingress võttis SRC-330 missiooni
vastu targetina SRC-134 ja keeldus projekteerimast `WAIT_OPERATOR`-iga.

Mõõdetud faktid:

- FastPrompteri `SRC-134.md` on **22 926 baiti**, SHA-256
  `4c2c534a309cd4ba733ee274642d13f8bd47c35174459c49c15454c934b3a155`, ja see
  **ei ole** SRC-330 baithaaval. Erinevus on täpselt 7-rialine ingress-päis
  (`# User request`, `priority`, `verify`, `## Request`), mille SAIPEN ise
  juurde lisab. Sisu on sama.
- SRC-134 on FastPrompteri `intake/index.json`-is staatuses `ACTIVE` ja
  `linked_work` on **T-1556**.
- T-1556 on FastPrompteri BOARD-il `[x]` suletud, kuid tema pealkiri on
  "repair T-1553 review findings: enforce DETAILS authorization, field char
  budgets, single NEXT EXACT ACTION, init carrier claim" — see on SAIPEN-i
  protokollitöö, **mitte** helitaastamine.
- FastPrompteri BOARD-il on avatud täpselt üks pilet (T-1402, LIMISAW/Google
  konto), mis ei puuduta heli. `BLOCKED_EXTERNAL`/`WAIT_OPERATOR` märke
  FastPrompteri BOARD-il ei ole.

Järeldus: blokeerija väide "üks projektipõhine operaatoriotsus on avatud" ei ole
FastPrompteri praeguses olekus tõendatav. Vastupidi — SRC-134 on `ACTIVE` ja
suletud **vale** Work'i (T-1556) alla, mis on iseenesest jälgitav viga, aga see
on FastPrompteri enda intake'i seis, mitte takistus siinsele kaardistusele.
Seetõttu ei ole T-1924 õige koht selle otsuse ootamiseks: T-1924 verify-klausel
on täidetav siin repos.

## 3. R1–R20 kaardistus

Iga rida: **seis** = `DIRECT` (otsene, korratav tõend selles repos või
FastPrompteri checkout'is), `PARTIAL` (osaline tõend, kitsendus kirjas) või
`OPEN` (avatud, omanik nimetatud). Ükski `OPEN` rida ei ole siin peidetud
"tehtud" alla.

| R | Nõue | Seis | Tõend / omanik |
|---|------|------|----------------|
| R1 | Personaalne originaal ja avalik fallback jagavad nime; personaalrežiim valib originaali | **DIRECT** (negatiivne) | Cache-defekt isoleeritud: `.saipen/evidence/T-1924/reconnect-control.json` punane haar valib bundled. Positiivne valik toimib ainult cache'i tühjendamisega — sama fail, roheline haar. Reegel ise on `sound_library.py:319-323`. |
| R2 | Personaalne originaal puudub; avalik fallback mängib | **DIRECT** | `tests/test_sound_ref_integrity.py:178` (`D_shipped_defaults_still_answer`), `:182` (`missing_override_still_falls_back_to_the_default`), `:218` (`J_genuinely_missing_ref_keeps_the_fallback_policy` — salvestatud viide säilib, taasesitus langeb shipped-default'ile). |
| R3 | Selgesõnaline `user:` resolvub ainult managed-juures | **DIRECT** | `tests/test_sound_ref_integrity.py:159` (`A_valid_user_ref_returns_the_exact_token`), `:194` (migratsioon säilitab byte-for-byte). |
| R4 | Selgesõnaline `addon:` resolvub ainult addon-juures | **DIRECT** | `tests/test_addon_sounds_t1457.py:149` ja `:155` (`the_managed_root_is_not_searched_for_an_addon_ref`). |
| R5 | Selgesõnaline `builtin:` järgib dokumenteeritud poliitikat | **DIRECT** | `tests/test_sound_ref_integrity.py:164` (`C_builtin_namespace_ref_is_preserved`), `:169` (vault). |
| R6 | Legacy bare ID varasemast profiilist säilitab operaatori valiku | **DIRECT** | `tests/test_sound_ref_integrity.py:194` (`B_valid_user_ref_survives_migration_byte_for_byte`), `:201`, `:207` (kordus ei triivi). |
| R7 | Ajutine personaalajami katkestus ei kustuta salvestatud eelistust | **OPEN** | Ükski test ei kata salvestatud eelistuse püsimist draivi kadumisel. Eelistus elab `local_data_v15.db`-s, mida testid ei puuduta (R19). Omanik: FastPrompteri enda Work. |
| R8 | Draivi taasühendus taastab personaalse taasesituse automaatselt | **FAIL — reprodutseeritud** | `.saipen/evidence/T-1924/reconnect-control.json`: punane haar valib bundled ka pärast personaalfaili ilmumist; roheline haar (ainus erinevus: `_RESOLVE_CACHE.clear()`) valib personaalfaili. `cache_isolates_cause: true`. Juurpõhjus: `_cache_key()` (`sound_library.py:257`) = `(ref, builtin, user, addon)` — ei kanna režiimi ega kandidaadi olemasolu. |
| R9 | Seadete migratsioon on idempotentne | **DIRECT** | `tests/test_sound_ref_integrity.py:207` (`H_repeated_migration_and_rebind_never_drift`). |
| R10 | Ambience säilitab kohandatud reeglinimed ja helitugevused | **DIRECT** | Nimi: `tests/test_t1455_computalk1_default.py:253` (`a_renamed_default_keeps_the_users_name` — "Night bed" jääb alles) ja `:243` (id, volume 0.01, enabled säilivad). Helitugevus: `tests/test_ambience_rule_reconcile.py:139` (volume-only muutus kohapeal), `:148` (fade ajal uus siht), `:159` (muutumatu reegel ei restarti), `:237` (pause/edit/resume). Reeglinimi hoiab `ambience_store.py:129-136` teadlikult. |
| R11 | Valitud `computalk1.wav` jääb lokaalselt mängitavaks, kui originaal on saadaval | **PARTIAL** | `tests/test_t1455_computalk1_default.py:181` tõestab, et **vaikeviide** resolvub packaged-puust. Operaatori enda `computalk1.wav` originaalhash'e ega valikut ei ole mõõdetud. See on `ORIGINAL_FILES_VERIFIED` puudujääk, mitte testi viga. |
| R12 | Puhas avalik install kasutab `ambient_loop.wav` fallback'i õigesti | **DIRECT** | `tests/test_t1455_computalk1_default.py:181-200`: vaikeviide resolvub packaged-puust ilma user/addon kaustadeta, on manifestis ja byte-reprodutseeritav. Fail on olemas: `src/fastprompter/sound/ambient_loop.wav`, 176 444 baiti. |
| R13 | Preview ja tegelik event-taasesitus valivad identsed baidid | **DIRECT** | `tests/test_sound_ref_integrity.py:277` (`M_one_ref_one_physical_file_for_both_routes`), `:256` (preview täpne path), `:296` (legacy exit sama leping). |
| R14 | Puhas avalik source ei sisalda personaalset heli | **DIRECT** | `tests/test_audio_packaging.py:160` (checkout läbib guard'i), `:192` (repos ei ole heli väljaspool sound-kausta). Mõõdetud: 49 trackitud WAV = 49 manifestikirjet = 49 faili kettal. |
| R15 | Avalik EXE ei sisalda piiratud heli | **OPEN** | `tools/verify_sound_allowlist.py` on build-gate'is (`tools/build.py:146-148`), aga valmis EXE-d ei ole selles mõõtmises ehitatud ega auditeeritud. Omanik: FastPrompteri release-Work. |
| R16 | Tuntud piiratud heli trackitud ZIP-i sees lükatakse tagasi | **PARTIAL — lünk leitud** | `archive_audio_leaks()` on `tools/verify_sound_allowlist.py:150` **defineeritud, aga mitte kusagilt kutsutud**. Mõõdetud: `grep -rn archive_audio_leaks` leiab ainult definitsiooni. Nii et rekursiivne ZIP-kontroll on olemas, aga ei jookse. Ainus teadaolev ZIP (`sound.zip`, 414 WAV-i) on `.gitignore:31 *.zip` all ja `git ls-files` ei tunne seda — seega täna ei publitseerita, aga gate ei kaitseks, kui see lisataks. |
| R17 | Ignoreeritud privaatne ZIP ei ole valesti klassifitseeritud avaliku push'ina | **DIRECT** | Mõõdetud: `git check-ignore -v` vastab `.gitignore:31:*.zip`; `git ls-files --error-unmatch` ei tunne faili. `git_published_audio()` kasutab Git'i tõde, mitte kettapinda. |
| R18 | Uus FastPrompter build ei muuda personaalseid helieelistusi | **OPEN** | Puudub test, mis tõestaks eelistuste püsimist build'i üle. Sama juur kui R7: eelistused on live-DB-s, mida testid ei tohi puutuda. Omanik: FastPrompteri enda Work. |
| R19 | Operaatori aktiivset andmebaasi ei muuda ükski disposable acceptance-test | **DIRECT** | Kõik siin viidatud testid kasutavad `tmp_path`/fixture-juuri. Kontroll katab enda kohta: `reconnect-control.json` kannab `live_configuration_accessed: false`, `live_configuration_written: false`. |
| R20 | Testid ei kirjuta fixture-WAV-e reaalsesse shipped sound-kausta | **DIRECT** | `tests/test_audio_packaging.py:192`; lisaks `reconnect-control.json` `fixture_audio_claimed_as_original: false` — fixture-baidid on skripti enda kirjutatud. |

Kokkuvõte: **13 DIRECT, 2 PARTIAL (R11, R16), 1 FAIL (R8), 4 OPEN (R7, R15, R18 + R11 kitsendus)**.
`OPEN` read on ausalt avatud; ükski neist ei ole siin repos sulgemiseks
kättesaadav, sest need nõuavad kas operaatori live-profiili lugemist või
tegelikku build/release artefakti.

## 4. R8 enne/pärast-kontroll

Kontroll on `.saipen/evidence/T-1924/reconnect_control.py`, jooksutatav:

```
python .saipen/evidence/T-1924/reconnect_control.py \
  "V:/___VAC/__K/__CODE/_PY/_FastPrompter" \
  .saipen/evidence/T-1924/reconnect-control.json
```

Tulemus (`reconnect-control.json`, `reconnect-control.log`):

- Punane haar: enne = bundled, pärast personaalfaili ilmumist = **bundled**
  (`defect_reproduced: true`).
- Roheline haar: enne = bundled, pärast = **personal**
  (`defect_reproduced: false`).
- Ainus erinevus haarade vahel: `_RESOLVE_CACHE.clear()` enne teist
  resolutsiooni (`discriminating_variable`).
- `cache_isolates_cause: true`.
- `cache_key_carries_personal_mode: false` — võti on `(ref, builtin, user, addon)`.

See isoleerib põhjuse: probleem ei ole juurte järjestuses ega `contained_path`
loogikas, vaid selles, et cache võti ei muutu, kui kõrgema prioriteediga
kandidaat tekib. Kontroll ei puuduta operaatori live-profiili ega väida
fixture-baite originaalideks.

## 5. Mida see dokument ei väida

- Ei väida, et heli on taastatud (`LOCAL_AUDIO_RESTORED` jääb tõestamata).
- Ei väida, et avalik source või build on puhas — R15 ja EXE-audit on avatud.
- Ei väida, et release on vastu võetud või GitHubi publitseeritud.
- Ei sisalda ühtegi operaatori isikliku heli hash'i, sest neid ei ole selles
  mõõtmises loetud.

## 6. Järelejäänud töö ja selle omanik

| Kohustus | Omanik | Miks siin ei sulgu |
|---|---|---|
| R7, R18 — eelistuste püsimine katkestuse ja build'i üle | FastPrompteri Work | Nõuab live-DB lugemist, mille R19 keelab disposable-testilt |
| R15 — EXE-sisene heliaudit | FastPrompteri release-Work | Nõuab tegelikku build-artefakti |
| R11 — operaatori `computalk1.wav` originaalhash | FastPrompteri Work + operaator | Nõuab operaatori tegelikku valikut |
| R8 — cache-defekti parandus | FastPrompteri source | Parandus on `_cache_key`-s; siinne repo ei oma FastPrompteri source't |
| R16 — `archive_audio_leaks` ühendamine | FastPrompteri source | Sama: gate elab FastPrompteri `tools/`-is |
| SRC-134 `linked_work` viitab T-1556-le | FastPrompteri intake | Vale Work'i sidumine on FastPrompteri intake'i seis |

Iga rida nimetab projekti, kes saab selle sulgeda. Ükski ei ole T-1924 enda
verify-klausli osa: T-1924 nõuab kaardistust, kontrolli ja ausust, mitte
FastPrompteri source-muudatust.
