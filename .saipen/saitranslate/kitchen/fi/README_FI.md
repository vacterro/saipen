<p align="center">
  <img src="assets/SAIPEN_TEXT1.png" alt="SAIPEN Logo"/>
  <br>
  <img src="assets/__SAIPEN_Alpha.png" alt="SAIPEN Sticker" width="200"/>
</p>

# SAIPEN

**Jatkuvuusprotokolla tekoäly-koodausagenteille.** Pysyvä projektimuisti
selkeässä markdown-muodossa, jotta kylmä agentti ilman keskusteluhistoriaa suorittaa `/saipen continue`
ja jatkaa työtä alle minuutissa -- ilman uudelleenohjeistusta, millä tahansa alustalla, milloin vain.

**Yksi komento. Nolla muistinmenetystä.**

**v7.112.0** | [Määrittely](SPEC.md) | [Opas](GUIDE.md) | [RFC](saipen/RFC.md) | [Tyyli](saipen/STYLE.md) | [Käyttöliittymä](saipen/UI.md) | [Yhteensopivuus](saipen/CONFORMANCE.md) | selkeä markdown | nolla riippuvuutta | MIT

[![Russian Guide](https://img.shields.io/badge/📖_ELI5_Guide-НА_РУССКОМ-red?style=for-the-badge)](guides/GUIDE_RU.md)
[![English Guide](https://img.shields.io/badge/📖_ELI5_Guide-IN_ENGLISH-blue?style=for-the-badge)](guides/GUIDE_EN.md)
[![Eesti Guide](https://img.shields.io/badge/📖_ELI5_Guide-EESTI-black?style=for-the-badge)](guides/GUIDE_EE.md)
[![Japanese Guide](https://img.shields.io/badge/📖_ELI5_Guide-日本語-red?style=for-the-badge)](guides/GUIDE_JA.md)
[![Ded Voice](https://img.shields.io/badge/👴_Guide-ВЕРСИЯ_ДЕДА-brown?style=for-the-badge)](guides/GUIDE_DED.md)

```text
Käyttäjä -> /saipen continue
Agentti  -> lukee STATE:n ("Mitä teen juuri nyt?")
Agentti  -> lukee BOARD:n ("Mitä tehtävää olen ottamassa?")
Agentti  -> lukee next_action:n (suorittaa komennon)
Agentti  -> Työskentelee.
```

### Projektin tila > Mallin muisti
Muisti sijaitsee projektissa, ei tekoälymallin päässä. `Projekti -> Muisti -> LLM` muuttuu muotoon `Projekti -> SAIPEN-tila -> LLM`.

### Keskeinen protokollalogiikka ja takuut
- **Ydintilakone**: `INIT → PLAN → SCOUT → BUILD → VERIFY → REVIEW → SHIP → DONE | BLOCKED`
- **Täysi autonomia ilman kehotteita**: Ei avoimia tehtäviä jäljellä? Siirtyy automaattisesti silmukkaan `HUNT` (skannaa virheet) → `ADD` (kehittää ominaisuuksia) → `HUNT`. Nolla kysymystä esitetty.
- **Explitsiittiset liipaisimet**: `/saipen clean` (repositorion siivous), `/saipen translate` (eristetty `.saipen/saitranslate/`-tehdas), `/saipen markhunt` (kuiva rajoittamaton auditointi, vain tallentaa), `/saipen prepare` (paketa työ luovutusta varten), `/saipen validate` (yhteensopivuustarkistus), `/saipen goal` (autonominen aallon suoritus). Meta/ohjaus: `/saipen status` (vain luku -raportti), `/saipen stop` (tarkistuspiste ja pysäytys). Täysi lista: RFC.md § 1.10.
- **Tiukka luotettavuus**: Eräsyötteen jäsennys (kirurgiset 1-kerrallaan tehtävät), likaisen puun hyväksyntä (ei koskaan pyyhi sitomattomia muutoksia), salaisuuksien suodatus (`sk-***`).

## SAIPEN-protokollaa käyttävät projektit
- ⚡ **[FastPrompter](https://github.com/vacterro/fastprompter)** — Suorituskykyinen kehotteiden hallintatyökalu, joka on natiivisti integroitu SAIPEN-muistiprotokollaan.

## Kaksi kerrosta

| Kerros | Vaaditaan | Tarkoitus |
|---|---|---|
| **Ydin (Core)** | ✅ | Jatka työtä turvallisesti |
| **Ylläpito (Maintenance)** | Ytimen päällä | Kehitä ohjelmistoa ilman erillistä tehtävänantoa |

**Automaattinen kehitys.** Ei avoimia tehtäviä jäljellä, kirjoita `/saipen`: `HUNT` auditoi virheet, kuolleen koodin, epäonnistuneet testit. Puhdas? `ADD` rakentaa seuraavan ilmeisen puuttuvan ominaisuuden, varmistaa sen ja auditoi uudelleen. Tuote valmis -> pysähtyy hallitusti.

**GOAL-tila.** `/saipen goal <mitä haluat>` kääntää tehtäväboardin (vanhat tehtävät alennetaan, ei koskaan poisteta) ja vie uutta tavoitetta eteenpäin -- ei "pitäisikö minun jatkaa?" -kysymyksiä tehtävien välillä, VERIFY/REVIEW-vaiheita ei koskaan ohiteta. SHIP tekee automaattisen pushin olemassa olevaan etärepositorioon; upouusi repositorio kysyy vielä kerran. Tavoitteen julkaisu ei myöskään ole pysähtymiskohta -- se siirtyy suoraan autonomiseen HUNT/ADD-ylläpitoon, kunnes tuote on valmis, estetty tai ajokerta saavuttaa rajansa (3 aaltoa / 20 tehtävää, minkä jälkeen se tekee tarkistuspisteen ja raportoi).

## Pika-aloitus

**1. Asenna kerran koneelle** -- opettaa Claude Coden, Geminin, OpenCoden, Aiderin, Codexin, Antigravityn ja mikä tahansa yleinen `~/.agents/skills`-lukija (FreeBuff, jne.):
```bash
git clone https://github.com/vacterro/saipen
cd saipen
powershell -ExecutionPolicy Bypass -File .\bootstrap\inject.ps1     # Windows
bash bootstrap/inject.sh                                            # macOS / Linux
```

**2. Aloita projekti** -- avaa agentti kansiossasi, kirjoita:
> `saipen set`

Ei asennusta? Liitä yksi rivi mille tahansa agentille:
> Read <clone>/saipen/RFC.md + <clone>/saipen/STYLE.md and follow them.

Alusta ei ole yllä olevassa listassa (DeepSeek, Qwen, erillinen OpenAI jne.)?
Alustakohtaiset muistiinpanot löytyvät kansiosta `extensions/adapters/`.

## Dokumentaatio- ja määrittelylinkit
- **[SPEC.md](SPEC.md)** -- muodollinen arkkitehtuuri, suunnittelutavoitteet, lakmustesti.
- **[RFC.md](saipen/RFC.md)** -- normatiivinen määrittely, jonka agentit suorittavat.
- **[GUIDE.md](GUIDE.md)** -- ihmisille suunnattu opas ja ELI5-oppaat:
  - 🇷🇺 [Русский](guides/GUIDE_RU.md) | 🇺🇸 [English](guides/GUIDE_EN.md) | 🇪🇪 [Eesti](guides/GUIDE_EE.md) | 🇯🇵 [日本語](guides/GUIDE_JA.md) | 👴 [Версия Деда](guides/GUIDE_DED.md)
  - 🇺🇦 [Українська](guides/GUIDE_UK.md) | 🇩🇪 [Deutsch](guides/GUIDE_DE.md) | 🇫🇷 [Français](guides/GUIDE_FR.md) | 🇪🇸 [Español](guides/GUIDE_ES.md) | 🇮🇹 [Italiano](guides/GUIDE_IT.md)
  - 🇵🇹 [Português](guides/GUIDE_PT.md) | 🇳🇱 [Nederlands](guides/GUIDE_NL.md) | 🇵🇱 [Polski](guides/GUIDE_PL.md) | 🇸🇪 [Svenska](guides/GUIDE_SV.md) | 🇩🇰 [Dansk](guides/GUIDE_DA.md)
  - 🇫🇮 [Suomi](guides/GUIDE_FI.md) | 🇳🇴 [Norsk](guides/GUIDE_NO.md) | 🇨🇳 [中文](guides/GUIDE_ZH.md) | 🇰🇷 [한국어](guides/GUIDE_KO.md) | 🇹🇭 [ไทย](guides/GUIDE_TH.md) | 🇻🇳 [Tiếng Việt](guides/GUIDE_VI.md) | 🇸🇦 [العربية](guides/GUIDE_AR.md) | 🇮🇱 [עברית](guides/GUIDE_HE.md)
  - 🇹🇷 [Türkçe](guides/GUIDE_TR.md) | 🇮🇳 [हिन्दी](guides/GUIDE_HI.md) | 🇮🇩 [Bahasa Indonesia](guides/GUIDE_ID.md) | 🇬🇷 [Ελληνικά](guides/GUIDE_EL.md) | 🇨🇿 [Čeština](guides/GUIDE_CS.md) | 🇷🇴 [Română](guides/GUIDE_RO.md)
  - 🇭🇺 [Magyar](guides/GUIDE_HU.md) | 🇧🇬 [Български](guides/GUIDE_BG.md) | 🇸🇰 [Slovenčina](guides/GUIDE_SK.md) | 🇭🇷 [Hrvatski](guides/GUIDE_HR.md)
- **[STYLE.md](saipen/STYLE.md)** -- agentin viestintätyylin ja äänen määrittely.
- **[UI.md](saipen/UI.md)** -- Tumma kultainen Win95 UI -suunnitteluohjeisto.
- **[CONFORMANCE.md](saipen/CONFORMANCE.md)** -- käyttäytymistestitilanteet ja validaattorisäännöt.

<p align="center">
  <img src="assets/SAIPEN_design2_alpha.png" alt="SAIPEN Stamp" width="120"/>
</p>


