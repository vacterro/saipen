#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""FORCE-FRESH translation pass (SAIT-011): sync kitchen locale READMEs and
non-Core guides to the current README.md truth (v7.219.0, HEAD 24d4375a).

English prose moved since SAIT-008 (0c73f36):
  1. fast-keys callout: `cc` keeps an active Goal Mode run moving
     -> `cc` continues the project context to convergence (resuming a
        running goal if one is set)
  2. no-install line: <clone>/saipen/RFC.md + <clone>/saipen/STYLE.md
     -> <clone>/saipen/INDEX.md + <clone>/saipen/STYLE.md
  3. README.md normalized digest moved (badge bumps are normalized out).

Core-owned kitchen copies (et/ru/ded/ja) already carry the new callout
(Core updated them); this pass only fixes their no-install line and restamps
their digest. The 28 non-Core kitchen READMEs get new callouts + no-install
line + digest; their guides are synced link-adjusted.
"""
from pathlib import Path
import hashlib
import re

KITCHEN = Path(".saipen/saitranslate/kitchen")
GUIDES = Path("guides")
README = Path("README.md")

# ---- new digest: sha256 of README.md with version strings normalized out ----
_want = hashlib.sha256(re.sub(
    r"\d+\.\d+\.\d+", "VERSION",
    README.read_text(encoding="utf-8-sig")).encode("utf-8")).hexdigest()
print("new digest:", _want)
OLD_DIGEST = re.compile(r"(<!-- source-digest: README\.md sha256:)[0-9a-f]+( -->)")
NEW_MARKER = r"\g<1>" + _want + r"\g<2>"

# ---- new callout per non-Core locale (full line, kitchen link form) ----
NEW_CALLOUT = {
    "ar": "**مفاتيح سريعة:** `cc` يواصل سياق المشروع إلى التقارب (يستأنف الهدف النشط إذا كان مضبوطًا)، `sss` يعرض الحالة دون لمس الكود، و`ss` يحفظ نقطة تحقق ويتوقف. [انظر خريطة المفاتيح الكاملة 15](saipen/RFC.md#110-command-surface). التوائم السيريلية تعمل أيضًا: `сс`, `ссс`, `аа`, `ее`, `еее`, `рр`.",
    "bg": "**Бързи клавиши:** `cc` продължава контекста на проекта до конвергенция (подновява текущата цел, ако е зададена), `sss` показва статус без допиране до кода, а `ss` запазва контролна точка и спира. [Виж пълната карта с 15 клавиша](saipen/RFC.md#110-command-surface). Кирилските близнаци също работят: `сс`, `ссс`, `аа`, `ее`, `еее`, `рр`.",
    "cs": "**Rychlé klávesy:** `cc` pokračuje v konvergenci projektového kontextu (obnoví běžící cíl, pokud je nastaven), `sss` zobrazí stav bez dotyku kódu a `ss` uloží kontrolní bod a zastaví. [Podívej se na úplnou mapu 15 kláves](saipen/RFC.md#110-command-surface). Fungují i cyrilské dvojníky: `сс`, `ссс`, `аа`, `ее`, `еее`, `рр`.",
    "da": "**Hurtigtaster:** `cc` fortsætter projektets kontekst til konvergens (genoptager et aktivt mål, hvis et er sat), `sss` viser status uden at røre koden, og `ss` gemmer et kontrolpunkt og stopper. [Se hele 15-tasters kortet](saipen/RFC.md#110-command-surface). Kyrilliske tvillinger virker også: `сс`, `ссс`, `аа`, `ее`, `еее`, `рр`.",
    "de": "**Schnellzugriff:** `cc` führt den Projektkontext bis zur Konvergenz fort (setzt ein laufendes Ziel fort, falls eines gesetzt ist), `sss` meldet Status ohne Code anzufassen und `ss` speichert einen Checkpoint und stoppt. [Siehe die komplette 15-Tasten-Karte](saipen/RFC.md#110-command-surface). Kyrillische Zwillinge funktionieren auch: `сс`, `ссс`, `аа`, `ее`, `еее`, `рр`.",
    "el": "**Συντομεύσεις:** το `cc` συνεχίζει το πλαίσιο του έργου μέχρι τη σύγκλιση (συνεχίζει έναν ενεργό στόχο, αν έχει οριστεί), το `sss` εμφανίζει την κατάσταση χωρίς να αγγίζει κώδικα και το `ss` αποθηκεύει σημείο ελέγχου και σταματάει. [Δες τον πλήρη χάρτη 15 πλήκτρων](saipen/RFC.md#110-command-surface). Λειτουργούν και τα κυριλλικά δίδυμα: `сс`, `ссс`, `аа`, `ее`, `еее`, `рр`.",
    "es": "**Atajos rápidos:** `cc` continúa el contexto del proyecto hasta la convergencia (reanuda un objetivo activo si hay uno fijado), `sss` informa del estado sin tocar código y `ss` guarda un punto de control y se detiene. [Ver el mapa completo de 15 teclas](saipen/RFC.md#110-command-surface). Los gemelos cirílicos también funcionan: `сс`, `ссс`, `аа`, `ее`, `еее`, `рр`.",
    "fi": "**Pikanäppäimet:** `cc` jatkaa projektin kontekstia konvergenssiin (jatkaa käynnissä olevaa tavoitetta, jos sellainen on asetettu), `sss` näyttää tilan koskematta koodiin ja `ss` tallentaa tarkistuspisteen ja pysähtyy. [Katso täydellinen 15 näppäimen kartta](saipen/RFC.md#110-command-surface). Kyrilliset kaksoset toimivat myös: `сс`, `ссс`, `аа`, `ее`, `еее`, `рр`.",
    "fr": "**Raccourcis clavier :** `cc` poursuit le contexte du projet jusqu'à la convergence (reprend un objectif actif s'il en existe un), `sss` signale l'état sans toucher au code et `ss` enregistre un point de contrôle puis s'arrête. [Voir la carte complète des 15 touches](saipen/RFC.md#110-command-surface). Les jumeaux cyrilliques fonctionnent aussi : `сс`, `ссс`, `аа`, `ее`, `еее`, `рр`.",
    "he": "**מקשים מהירים:** `cc` ממשיך את ההקשר של הפרויקט עד להתכנסות (מחדש יעד פעיל אם הוגדר), `sss` מציג סטטוס ללא נגיעה בקוד ו-`ss` שומר נקודת ביקורת ועוצר. [ראה את מפת 15 המקשים המלאה](saipen/RFC.md#110-command-surface). גם התאומים הקיריליים עובדים: `сс`, `ссс`, `аа`, `ее`, `еее`, `рр`.",
    "hi": "**त्वरित कुंजियाँ:** `cc` परियोजना संदर्भ को अभिसरण तक जारी रखता है (यदि कोई लक्ष्य निर्धारित है तो उसे फिर से शुरू करता है), `sss` कोड छुए बिना स्थिति दिखाता है और `ss` चेकपॉइंट सहेज कर रुक जाता है. [पूरा 15-कुंजी नक्शा देखें](saipen/RFC.md#110-command-surface). सिरिलिक जुड़वाँ भी काम करती हैं: `сс`, `ссс`, `аа`, `ее`, `еее`, `рр`.",
    "hr": "**Brzi prečaci:** `cc` nastavlja kontekst projekta do konvergencije (nastavlja aktivni cilj ako je postavljen), `sss` prikazuje status bez diranja koda, a `ss` sprema kontrolnu točku i zaustavlja se. [Pogledaj punu kartu od 15 tipki](saipen/RFC.md#110-command-surface). Ćirilični blizanci također rade: `сс`, `ссс`, `аа`, `ее`, `еее`, `рр`.",
    "hu": "**Gyorsbillentyűk:** a `cc` a projekt kontextusát konvergenciáig folytatja (folytat egy futó célt, ha be van állítva), az `sss` kód érintése nélkül jelzi az állapotot, az `ss` pedig menti az ellenőrzőpontot és megáll. [Lásd a teljes 15 billentyűs térképet](saipen/RFC.md#110-command-surface). A cirill ikrek is működnek: `сс`, `ссс`, `аа`, `ее`, `еее`, `рр`.",
    "id": "**Tombol cepat:** `cc` melanjutkan konteks proyek hingga konvergensi (melanjutkan tujuan aktif jika ada yang ditetapkan), `sss` melaporkan status tanpa menyentuh kode, dan `ss` menyimpan titik periksa lalu berhenti. [Lihat peta 15 tombol lengkap](saipen/RFC.md#110-command-surface). Kembar Sirilik juga berfungsi: `сс`, `ссс`, `аа`, `ее`, `еее`, `рр`.",
    "it": "**Tasti rapidi:** `cc` prosegue il contesto del progetto fino alla convergenza (riprende un obiettivo attivo se ne è impostato uno), `sss` segnala lo stato senza toccare il codice e `ss` salva un checkpoint e si ferma. [Guarda la mappa completa degli 15 tasti](saipen/RFC.md#110-command-surface). Funzionano anche i gemelli cirillici: `сс`, `ссс`, `аа`, `ее`, `еее`, `рр`.",
    "ko": "**빠른 키:** `cc`는 프로젝트 컨텍스트를 수렴까지 계속합니다 (설정된 실행 중인 목표가 있으면 재개합니다), `sss`는 코드를 건드리지 않고 상태를 보여주며, `ss`는 체크포인트를 저장하고 멈춥니다. [전체 15 키 맵 보기](saipen/RFC.md#110-command-surface). 키릴 문자 쌍둥이도 작동합니다: `сс`, `ссс`, `аа`, `ее`, `еее`, `рр`.",
    "nl": "**Sneltoetsen:** `cc` zet de projectcontext voort tot convergentie (hervat een actief doel als er een is ingesteld), `sss` meldt status zonder code aan te raken en `ss` slaat een checkpoint op en stopt. [Bekijk de volledige 15-toetsenkaart](saipen/RFC.md#110-command-surface). Cyrillische tweelingen werken ook: `сс`, `ссс`, `аа`, `ее`, `еее`, `рр`.",
    "no": "**Hurtigtaster:** `cc` fortsetter prosjektets kontekst til konvergens (gjenopptar et aktivt mål hvis et er satt), `sss` viser status uten å røre koden, og `ss` lagrer et sjekkpunkt og stopper. [Se hele 15-tasters kartet](saipen/RFC.md#110-command-surface). Kyrilliske tvillinger fungerer også: `сс`, `ссс`, `аа`, `ее`, `еее`, `рр`.",
    "pl": "**Szybkie klawisze:** `cc` kontynuuje kontekst projektu do konwergencji (wznawia bieżący cel, jeśli jest ustawiony), `sss` pokazuje stan bez dotykania kodu, a `ss` zapisuje punkt kontrolny i zatrzymuje się. [Zobacz pełną mapę 15 klawiszy](saipen/RFC.md#110-command-surface). Cyrylickie bliźniaki też działają: `сс`, `ссс`, `аа`, `ее`, `еее`, `рр`.",
    "pt": "**Atalhos rápidos:** `cc` continua o contexto do projeto até a convergência (retoma um objetivo ativo, se houver um definido), `sss` informa o estado sem tocar no código e `ss` salva um ponto de verificação e para. [Veja o mapa completo de 15 teclas](saipen/RFC.md#110-command-surface). Os gêmeos cirílicos também funcionam: `сс`, `ссс`, `аа`, `ее`, `еее`, `рр`.",
    "ro": "**Comenzi rapide:** `cc` continuă contextul proiectului până la convergență (reia un obiectiv activ dacă este setat), `sss` afișează starea fără să atingă codul, iar `ss` salvează un punct de control și se oprește. [Vezi harta completă cu 15 taste](saipen/RFC.md#110-command-surface). Gemenii chirilici funcționează și ei: `сс`, `ссс`, `аа`, `ее`, `еее`, `рр`.",
    "sk": "**Rýchle klávesy:** `cc` pokračuje v konvergencii projektového kontextu (obnoví bežiaci cieľ, ak je nastavený), `sss` zobrazí stav bez dotyku kódu a `ss` uloží kontrolný bod a zastaví. [Pozri si úplnú mapu 15 kláves](saipen/RFC.md#110-command-surface). Fungujú aj cyrilské dvojníky: `сс`, `ссс`, `аа`, `ее`, `еее`, `рр`.",
    "sv": "**Snabbkommandon:** `cc` fortsätter projektets kontext till konvergens (återupptar ett aktivt mål om ett är satt), `sss` visar status utan att röra koden och `ss` sparar en kontrollpunkt och stannar. [Se hela 15-tangentkartan](saipen/RFC.md#110-command-surface). Kyrilliska tvillingar fungerar också: `сс`, `ссс`, `аа`, `ее`, `еее`, `рр`.",
    "th": "**คีย์ลัด:** `cc` ให้ดำเนินการต่อบริบทของโปรเจกต์จนถึงจุดบรรจบ (ดำเนินเป้าหมายที่กำลังทำงานต่อไปหากมีการตั้งไว้), `sss` แสดงสถานะโดยไม่แตะโค้ด และ `ss` บันทึกจุดตรวจสอบแล้วหยุด [ดูแผนที่ปุ่มลัดทั้ง 15 รายการ](saipen/RFC.md#110-command-surface) ปุ่มอักษรซีริลลิกที่มีรูปเหมือนกันก็ใช้ได้: `сс`, `ссс`, `аа`, `ее`, `еее`, `рр`",
    "tr": "**Kısayol tuşları:** `cc` proje bağlamını yakınsamaya kadar sürdürür (ayarlanmışsa çalışan hedefi sürdürür), `sss` koda dokunmadan durumu bildirir ve `ss` kontrol noktası kaydedip durur. [15 tuşluk tam haritaya bakın](saipen/RFC.md#110-command-surface). Kiril ikizleri de çalışır: `сс`, `ссс`, `аа`, `ее`, `еее`, `рр`.",
    "uk": "**Швидкі клавіші:** `cc` продовжує контекст проєкту до конвергенції (відновлює активну ціль, якщо вона встановлена), `sss` показує статус без правок коду, а `ss` зберігає контрольну точку і зупиняється. [Повна карта з 15 клавіш](saipen/RFC.md#110-command-surface). Кириличні двійники теж працюють: `сс`, `ссс`, `аа`, `ее`, `еее`, `рр`.",
    "vi": "**Phím tắt:** `cc` tiếp tục bối cảnh dự án đến hội tụ (tiếp tục mục tiêu đang chạy nếu có), `sss` báo trạng thái mà không đụng vào mã và `ss` lưu điểm kiểm tra rồi dừng. [Xem bản đồ đầy đủ 15 phím](saipen/RFC.md#110-command-surface). Các cặp song sinh Cyrillic cũng hoạt động: `сс`, `ссс`, `аа`, `ее`, `еее`, `рр`.",
    "zh": "**快捷键:** `cc` 继续项目上下文直至收敛（如果设置了正在运行的目标，则恢复该目标），`sss` 在不触碰代码的情况下报告状态，`ss` 保存检查点并停止。[查看完整的 15 键快捷键地图](saipen/RFC.md#110-command-surface)。西里尔字母的同型键也可用：`сс`、`ссс`、`аа`、`ее`、`еее`、`рр`。",
}

CORE_LOCALES = {"et", "ru", "ded", "ja"}  # callout already current; no-install+digest only

NOINSTALL_OLD = "<clone>/saipen/RFC.md + <clone>/saipen/STYLE.md"
NOINSTALL_NEW = "<clone>/saipen/INDEX.md + <clone>/saipen/STYLE.md"


def rw(path: Path, text: str):
    """Write back preserving CRLF endings."""
    with open(path, "w", encoding="utf-8", newline="") as fh:
        fh.write(text)


def transform(readme_path: Path, new_callout: str | None, core: bool):
    text = readme_path.read_text(encoding="utf-8-sig")
    changed = []
    lines = text.splitlines(keepends=True)
    callout_replaced = False
    noinstall_replaced = False
    for i, line in enumerate(lines):
        if new_callout is not None and "`cc`" in line and "110-command-surface" in line:
            assert line.rstrip("\r\n").strip() != new_callout, \
                f"{readme_path} already has new callout?"
            lines[i] = new_callout + line[len(line.rstrip("\r\n")):]
            # keep trailing newline style
            lines[i] = new_callout + "\r\n" if line.endswith("\r\n") else new_callout + "\n"
            callout_replaced = True
        elif NOINSTALL_OLD in line:
            lines[i] = line.replace(NOINSTALL_OLD, NOINSTALL_NEW)
            noinstall_replaced = True
    new_text = "".join(lines)
    new_text = OLD_DIGEST.sub(NEW_MARKER, new_text)
    if new_text != text:
        rw(readme_path, new_text)
        changed.append("callout" if callout_replaced else None)
        changed.append("noinstall" if noinstall_replaced else None)
        changed.append("digest")
    else:
        print(f"  !! no change: {readme_path}")
    return readme_path, callout_replaced, noinstall_replaced


# ---- kitchen locale READMEs ----
print("== kitchen ==")
n_callout = n_noinstall = n_digest = 0
for d in sorted(p for p in KITCHEN.iterdir() if p.is_dir()):
    code = d.name
    src = d / f"README_{code.upper()}.md"
    if not src.is_file():
        print(f"  !! missing {src}")
        continue
    if code in NEW_CALLOUT:
        new_callout = NEW_CALLOUT[code]
    elif code in CORE_LOCALES:
        new_callout = None
    else:
        print(f"  !! no callout mapping for {code}")
        continue
    p, cr, nr = transform(src, new_callout, code in CORE_LOCALES)
    tag = []
    if cr: tag.append("callout")
    if nr: tag.append("noinstall")
    digest_changed = OLD_DIGEST.search(p.read_text(encoding="utf-8-sig")) is None
    if digest_changed: tag.append("digest")
    if tag:
        n_callout += cr; n_noinstall += nr
        print(f"  {code}: {', '.join(tag)}")
print(f"callout={n_callout} noinstall={n_noinstall}")

# ---- non-Core guides (link-adjusted) ----
print("== guides ==")
n_guide = 0
for code, line in NEW_CALLOUT.items():
    g = GUIDES / f"GUIDE_{code.upper()}.md"
    if not g.is_file():
        print(f"  !! missing guide {g}")
        continue
    new_guide_line = line.replace("](saipen/RFC.md#110-command-surface)",
                                  "](../saipen/RFC.md#110-command-surface)")
    text = g.read_text(encoding="utf-8-sig")
    lines = text.splitlines(keepends=True)
    replaced = False
    for i, ln in enumerate(lines):
        if "`cc`" in ln and "110-command-surface" in ln:
            if ln.rstrip("\r\n").strip() == new_guide_line:
                print(f"  {code}: already current")
                replaced = True
                break
            lines[i] = new_guide_line + ("\r\n" if ln.endswith("\r\n") else "\n")
            replaced = True
            break
    if replaced and "".join(lines) != text:
        rw(g, "".join(lines))
        n_guide += 1
        print(f"  {code}: callout")
    elif not replaced:
        print(f"  !! {code}: callout line not found")

print(f"guides updated={n_guide}")
print("DONE")
