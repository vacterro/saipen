<p align="center">
  <img src="assets/SAIPEN_TEXT1.png" alt="SAIPEN Logo"/>
</p>

<div align="center">
  <h3><a href="README.ee.md">🇪🇪 LOE SEDA EESTI KEELES / ESTONIAN 🇪🇪</a></h3>
  <a href="README.md">🇬🇧 English</a> &nbsp;|&nbsp;
  <a href="README.ded.md">👴 Дед-Версия (Russian)</a> &nbsp;|&nbsp;
  <a href="README.ja.md">🇯🇵 日本語 (Japanese)</a>
</div>

# SAIPEN

**Protocolo de continuidad para agentes de codificación de IA.**La memoria del proyecto vive en archivos
Markdown dentro del proyecto(`.saipen/`), por lo tanto, cualquier agente frío compatible —
sin historial de chat, sin memoria de sesión — puede ejecutarse`/saipen continue`, leer el
persistido`next_action`, y reanudar el trabajo sin pedir al usuario que lo explique de nuevo
nada. El estado pertenece al proyecto, no a la memoria de un solo proveedor de modelos.

**Un solo comando para reanudar. Estado en archivos planos. Contratos verificados por máquina.**

El repositorio se valida a sí mismo en cada push; instalar, estado, verificaciones y
la desinstalación es local — no hay servicio en la nube, ningún demonio, ninguna base de datos.

[![Validation](https://github.com/vacterro/saipen/actions/workflows/validate.yml/badge.svg)](https://github.com/vacterro/saipen/actions/workflows/validate.yml)
[![Release](https://img.shields.io/github/v/release/vacterro/saipen?sort=semver&label=release)](https://github.com/vacterro/saipen/releases)
[![License: MIT](https://img.shields.io/github/license/vacterro/saipen?color=blue)](LICENSE)

**v7.246.1** | [Especificación](SPEC.md) | [Guía](GUIDE.md) | [Núcleo](saipen/CORE.md) | [Mantenimiento](saipen/MAINTENANCE.md) | [Estilo](saipen/STYLE.md) | [Interfaz de usuario](saipen/UI.md) | [Conformidad](saipen/CONFORMANCE.md) |MIT

**Atajos rápidos:** `cc` continúa el contexto del proyecto hasta la convergencia (reanuda un objetivo activo si hay uno fijado), `sss` informa del estado sin tocar código y `ss` guarda un punto de control y se detiene. [Ver el mapa completo de 19 teclas](saipen/RFC.md#110-command-surface). Los gemelos cirílicos también funcionan: `сс`, `ссс`, `аа`, `ее`, `еее`, `рр`. `ff` → `focus`; `xx` → `cut`; `vv` → `build`; `zz` → `undo`.

```text
Project
  |
  +-- .saipen/STATE.md ------ what is happening right now (phase, ticket, mode, next_action)
  +-- .saipen/BOARD.md ------ what work exists (DOING / TODO / DONE / BLOCKED)
  +-- .saipen/LOG.md -------- why the project reached this state (event history)
  +-- .saipen/KNOWLEDGE/ ---- what durable facts must survive sessions
          |
          v
   /saipen continue
          |
          v
      cold agent
          |
          v
     next_action -> work -> checkpoint -> next ticket
```

## ¿Qué persiste

La memoria del proyecto en vivo vive en`.saipen/`— archivos planos que puedes leer, diferenciar y
commit junto al código. Un agente frío responde cinco preguntas de los archivos
solos:

|Archivo / campo|Respuestas|
|---|---|
| `STATE.md` |¿Qué está sucediendo ahora?(fase, ticket activo, modo de operación, bloqueador) |
| `BOARD.md` |¿Qué trabajo existe / qué está activo?(grafo de tickets: DOING, TODO, DONE, BLOCKED) |
| `LOG.md` |¿Por qué el proyecto llegó a este estado?(grafo de eventos de solo lectura) |
| `KNOWLEDGE/` |¿Qué hechos duraderos del proyecto deben sobrevivir a las sesiones?|
| `next_action` (en`STATE.md`) |¿Qué acción exacta debe ejecutar el siguiente agente?|

Este es un contrato de punto de control, no una sugerencia de diseño:`saipen stop`y cada
transición de ticket escribe los archivos en un orden fijo, y el resultado es verificado por
un validador. Nada se almacena en una base de datos alojada, y nada se pierde cuando un
la sesión termina.

## Inicio rápido

**1. Instale una vez por máquina**— enseña a Claude Code, Codex, Gemini, OpenCode,
Aider, Antigravity y cualquier lector`~/.agents/skills`genérico(FreeBuff, etc.):

```bash
git clone https://github.com/vacterro/saipen
cd saipen
powershell -ExecutionPolicy Bypass -File .\bootstrap\inject.ps1     # Windows
bash bootstrap/inject.sh                                            # macOS / Linux
```

<sub>What that touches, so nothing is a surprise: it appends a marked
`<!-- SAIPEN:BEGIN -->...<!-- SAIPEN:END -->`bloquear la instrucción del agente
archivos que ya tiene(`~/.claude/CLAUDE.md`, `~/.config/opencode/AGENTS.md`,
`~/.codex/AGENTS.md`, `~/.gemini/GEMINI.md`)— respaldando cada uno en`.bak`primero —
y copia el protocolo en las carpetas de habilidades correspondientes. Nada fuera de esas
rutas, sin demonio, sin llamadas de red.</sub>

**2. Iniciar un proyecto**— abrir un agente en tu carpeta, escribe:

> `saipen set`

**¿Sin instalación?**Pega una línea en cualquier agente:

> Leer&lt;clone&gt;/saipen/BOOT.md primero(kernel de inicio frío), luego&lt;clone&gt;/saipen/INDEX.md +&lt;clonar&gt;/saipen/STYLE.md y síguelos.

**¿Cambió de opinión?**Un comando lo restablece:

```bash
powershell -ExecutionPolicy Bypass -File .\bootstrap\uninstall.ps1  # Windows
bash bootstrap/uninstall.sh                                         # macOS / Linux
```

Quita exactamente el bloque marcado(dejando el resto de tu archivo intacto), guarda
a `.uninstalled.bak`haz una copia primero, y elimina las carpetas de habilidades.

## ¿Por qué no simplemente el historial de chat?

SAIPEN se enfoca en un fallo específico: un agente de codificación de IA que no recuerda nada
una vez que termina la sesión. Otras herramientas y hábitos cubren parte de ese problema:

|Enfoque|Para qué sirve|Lo que no transporta|
|---|---|---|
|Historial de chat / memoria del modelo|Conveniente, sin configuración previa|Dependiente de la sesión y del proveedor; no se almacena con el proyecto, por lo tanto, un agente frío nunca lo ve|
|Estático`AGENTS.md`Archivo / instrucción|Reglas y convenciones duraderas|No representa por sí mismo el estado de tarea en vivo,`next_action`, o historial de recuperación|
|Seguimiento de problemas / TODO|Gestión de tareas y lista de pendientes|No define por sí misma la semántica de continuidad del agente — lo que un agente frío debe leer y ejecutar al reanudar|
| **SAIPEN** |Estado de ejecución en vivo, cola de trabajo, historial de eventos, conocimiento duradero y reglas de continuidad verificadas por máquina — en archivos planos junto al código|Nada; esa combinación es el contrato|

La diferencia no es ningún solo archivo. Es que SAIPEN realiza el paso de reanudación
verificable por máquina: la primera acción de un agente frío después de`/saipen continue`es
dictada por el persistido`next_action`y verificada por un validador, no
reconstruida de la memoria.

## Evidencia de ingeniería

SAIPEN combina un protocolo de archivo plano normativo con uno ejecutable, orientado a fallos
verificaciones. El repositorio demuestra el diseño de protocolo/máquina de estados, Python
herramientas, estado basado en esquema, razonamiento de recuperación, pruebas de regresión,
límites de flujo de trabajo multiagente, y disciplina de especificación.

- **Contrato diseñado.** [SPEC.md](SPEC.md)define el modelo de continuidad respaldado por archivos
y el contrato estable en disco;[CORE.md](saipen/CORE.md)
y[MAINTENANCE.md](saipen/MAINTENANCE.md)definen el comportamiento normativo actual.
- **Estado verificado por máquina.**El validador canónico basado únicamente en stdlib
  [validador](tools/validate.py)lee el estado
  [esquema de estado](extensions/schemas/state.schema.json)y verifica la transición de fase
dependencias de tickets, enlaces del gráfico de eventos, invariantes transdocumentales
invariantes, capacidades y estado de recuperación.
- **Cobertura de fallos.** [CONFORMANCE.md](saipen/CONFORMANCE.md)mapea
requisitos a[fixture de escenario](tests/scenarios/); el
  [ejecutor de escenarios](tools/run_scenarios.py)ejecuta casos de prueba estructurales de paso/fallo
incluyendo estado de recuperación corrupto, transiciones inválidas, ciclos de dependencia y
restricciones de solo lectura.
- **Controles de regresión.** [audit_checks.py](tools/audit_checks.py)modifica
copias conocidas como buenas y demuestra que las verificaciones del validador aún pueden fallar, en lugar de
tratar una verificación permanentemente verde como evidencia.
- **Capa ejecutable.** [saipen.py](tools/saipen.py)proporciona estado con registro
operaciones;[bootstrap/](bootstrap/)contiene instalación, desinstalación y exportación
helpers, con una opción de[instalador de pre-commit](tools/install_hook.py).
- **Toma de decisiones explícitas.**El estado del protocolo principal son archivos normales sin dependencia de tiempo de ejecución
dependencia. La validación canónica y las herramientas de CLI requieren Python, pero utilizan solo
su biblioteca estándar y no necesitan`pip`instalación.

## Arquitectura

Tres capas, dependencias estrictamente unidireccionales:

```text
CORE            continuation / state / checkpoint / validation       required
  └─ MAINTENANCE   autonomous HUNT / ADD / CLEAN evolution           optional, on top of Core
       └─ GOAL MODE / SUBAGENTS   opt-in throughput/execution        optional
```

Core no depende de Maintenance: con la evolución autónoma deshabilitada, SAIPEN
aún es un protocolo de continuidad completa — un agente frío aún puede reanudarse.

- **Máquina de estado del núcleo** — `INIT → PLAN → SCOUT → BUILD → VERIFY → REVIEW → SHIP → DONE | BLOCKED`.
- **Mantenimiento autónomo**— tablero detenido(nada funcional en`## TODO`,
nada en`## DOING`)y no`BLOCKED`? Transiciones automáticas`HUNT` (detectar errores)
  → `ADD` (evolucionar características) → `HUNT`, cero preguntas formuladas. Una sesión sentada en
  `BLOCKED`nunca auto-hunt
  ([Mantenimiento § 2.1](saipen/MAINTENANCE.md#21-autonomous-transitions)).
- **Modo Objetivo** — `/saipen goal <objective>`gira la placa y ejecuta el
objetivo hacia adelante a través de VERIFY/REVIEW, cayendo en mantenimiento autónomo
hasta que se active la regla de finalización o la ejecución alcance su límite(3 olas / 20 tickets,
luego puntos de control y reportes) ([Mantenimiento § 2.4](saipen/MAINTENANCE.md#24-goal-mode-autonomous-execution)).
- **Endurecimiento**— la entrada por lotes se analiza en tickets uno por uno quirúrgicos
  (CORE § 1.8); la continuidad del árbol sucio preserva el trabajo no comprometido(CORE § 1.5);
los valores similares a secretos se eliminan de los registros(`sk-***`) (CORE § 1.2).

## Comandos comunes

Puntos de entrada cotidianos; la superficie actual completa vive en
[Core § 1.10](saipen/CORE.md#110-command-surface).

|Comando|Hace|
|---|---|
| `/saipen set` |Adoptar un proyecto: crear`.saipen/`estado|
| `/saipen continue` |Resumir desde el estado persistido del proyecto — sin rebriefing|
| `/saipen plan` |Convertir una solicitud o lista de tareas bruta en tickets|
| `/saipen goal <text>` |Ejecución autónoma de onda contra un nuevo objetivo|
| `/saipen validate` |Ejecutar las verificaciones de conformidad|
| `/saipen status` |Informe de solo lectura: fase, tickets, obstáculos, antigüedad|
| `/saipen stop` |Punto de verificación y detener|

<details>
<summary><b>More commands</b></summary>

|Comando|Hace|
|---|---|
| `/saipen hunt` |Forzar la revisión de defectos/mejoras ahora|
| `/saipen markhunt` |Auditoría seca sin límite — registra hallazgos, no corrige nada|
| `/saipen ship` |Puertas de liberación; comprometer, etiquetar y empujar cuando se permita|
| `/saipen clean` |Limpieza de tablero y estado|
| `/saipen translate` |Fábrica de traducción aislada|
| `/saipen prepare` / `/saipen collect` |Trabajo de paquete para entrega / integrar un paquete listo|
| `/saipen test` |Ejecutar la suite de pruebas declarada, reportar solo|
| `/saipen crew` |Circuito de tripulación en orden fijo(hunt → reproduce → intake → build → translate → document → ship) |
| `/saipen improve` |Auditoría de mejora del protocolo de control meta|
| `/saipen sub ...` |Spawn/adoptar subagentes de solo lectura|

**Claves de paquete.** `ee`/`qq`Preparar paquetes completos de traducción/wiki sin
integrar;`eee`/`qqq`Aceptar solo paquetes listos, luego integrar, verificar,
revisar y empujar.

**saicrew.** `sc` / `saipen crew` (`extensions/subs/crew.md`)camina por completo
equipo integrado en un orden fijo — sensores(saihunt, saitest, saipython, saiui),
productores(saitranslate, saiwiki)y Core como el único escritor del árbol principal —
hasta que otra pasada reciente no tenga nada real que cambiar. Añade exactamente uno
mecanismo propio: el objetivo de orquestación duradero(execution_intent:
converge` with `converge_target: crew`)que hace que el circuito sea reanudable y
derivable de un fallo a partir de evidencia.`saipen crew --dry-run --json`deriva el
circuito de solo lectura;`bootstrap/saipen_crew.*`es un AUXILIAR MANUAL OPCIONAL
de múltiples ventanas, nunca lo que`saipen crew`significa. Ver
[extensions/subs/crew.md](extensions/subs/crew.md).
</details>

## ¿Qué no es SAIPEN

- **Un LLM o un modelo**— es un protocolo que siguen los agentes, no una inteligencia.
- **Un IDE o una base de datos de memoria alojada**— el estado son archivos planos en tu proyecto;
nada está alojado.
- **Un reemplazo para Git**— Git aún posee el historial de versiones; compromete tu
  `.saipen/`como cualquier otro código.
- **Consenso distribuido**— ve el límite de concurrencia a continuación.
- **Una garantía de que un LLM tomará decisiones de ingeniería correctas**— ello
reduce la pérdida de contexto y el desvío comportamental; no hace agentes estocásticos
infalibles.

El trabajo de SAIPEN es un contrato de continuidad/estado más validación y herramientas —
entregando al siguiente agente un punto de inicio verificado por máquina, no magia.

**Límite de concurrencia.**Mutaciones de estado registradas(SAIOPS)use a
un bloqueo del sistema operativo con alcance de proyecto y un diario de recuperación([OPS § 5](saipen/OPS.md#5-locks)).
Ediciones ordinarias del proyecto y escritores desconectados están fuera de ese bloqueo. SAIPEN
no es consenso distribuido, por lo tanto, los escritores desconectados requieren coordinación externa
coordinación([SPEC](SPEC.md#concurrency--distribution-boundaries)).

## Ecosistema

|Proyecto|Relación con SAIPEN|
|---|---|
| [SAIPENVIEW](https://github.com/vacterro/saipenview) |Centro de control local de Windows para proyectos SAIPEN — descubre automáticamente`.saipen/`espacios de trabajo, visualiza el estado en vivo y los veredictos de conformidad, gestiona tickets y lanza CLI de IA. Un compañero, no la autoridad.|
| [SAIWORK](https://github.com/vacterro/saiwork) |Fork descendiente de CodeNomad que integra SAIPEN: inyecta`BOOT.md`/`STYLE.md`en lanzamientos de OpenCode, expone atajos de SAIPEN y vistas del estado del proyecto, y agrega una cola de prompts persistente.|
| [FastPrompter](https://github.com/vacterro/fastprompter) |Bloc de notas portátil de Windows y administrador de fragmentos que detecta automáticamente`.saipen/`carpetas y agrega un visor de STATE/BOARD/LOG en solo lectura.|

## Documentación

|Document|Qué es|
|---|---|
| [SPEC.md](SPEC.md) |Arquitectura formal, objetivos de diseño, prueba de litmus|
| [CORE.md](saipen/CORE.md) |Continuación normativa, máquina de estados y contrato de comando|
| [MAINTENANCE.md](saipen/MAINTENANCE.md) |Mantenimiento autónomo y Modo de objetivo|
| [CONFORMANCE.md](saipen/CONFORMANCE.md) |Requisitos ejecutables/comportamentales y reglas del validador|
| [GUIDE.md](GUIDE.md) |Tutoriales para humanos|
| [RFC.md](saipen/RFC.md) |Redirección de compatibilidad a los documentos normativos divididos|
| [STYLE.md](saipen/STYLE.md) |Estilo y voz de la comunicación del agente|
| [UI.md](saipen/UI.md) |Directrices del diseño de la interfaz de usuario Vintage Golden|
|Brochure|Brochure de presentación —[EN](BROCHURE_EN.md) / [RU](BROCHURE_RU.md) / [ET](BROCHURE_ET.md) / [DED](BROCHURE_DED.md) / [JA](BROCHURE_JA.md) |

<details>
<summary><b>All 33 translated guides</b></summary>

🇷🇺 [Русский](guides/GUIDE_RU.md) · 🇺🇸 [Inglés](guides/GUIDE_EN.md) · 🇪🇪 [Estonio](guides/GUIDE_EE.md) · 🇯🇵 [日本語](guides/GUIDE_JA.md) · 👴 [Версия Деда](guides/GUIDE_DED.md)

🇺🇦 [Українська](guides/GUIDE_UK.md) · 🇩🇪 [Alemán](guides/GUIDE_DE.md) · 🇫🇷 [Francés](guides/GUIDE_FR.md) · 🇪🇸 [Español](guides/GUIDE_ES.md) · 🇮🇹 [Italiano](guides/GUIDE_IT.md)

🇵🇹 [Portugués](guides/GUIDE_PT.md) · 🇳🇱 [Neerlandés](guides/GUIDE_NL.md) · 🇵🇱 [Polaco](guides/GUIDE_PL.md) · 🇸🇪 [Sueco](guides/GUIDE_SV.md) · 🇩🇰 [Danés](guides/GUIDE_DA.md)

🇫🇮 [Finés](guides/GUIDE_FI.md) · 🇳🇴 [Noruego](guides/GUIDE_NO.md) · 🇨🇳 [中文](guides/GUIDE_ZH.md) · 🇰🇷 [한국어](guides/GUIDE_KO.md) · 🇹🇭 [ไทย](guides/GUIDE_TH.md)

🇻🇳 [Vietnamita](guides/GUIDE_VI.md) · 🇸🇦 [العربية](guides/GUIDE_AR.md) · 🇮🇱 [עברית](guides/GUIDE_HE.md) · 🇹🇷 [Turco](guides/GUIDE_TR.md) · 🇮🇳 [हिन्दी](guides/GUIDE_HI.md)

🇮🇩 [Indonesio](guides/GUIDE_ID.md) · 🇬🇷 [Ελληνικά](guides/GUIDE_EL.md) · 🇨🇿 [Checo](guides/GUIDE_CS.md) · 🇷🇴 [Rumano](guides/GUIDE_RO.md) · 🇭🇺 [Húngaro](guides/GUIDE_HU.md)

🇧🇬 [Български](guides/GUIDE_BG.md) · 🇸🇰 [Eslovaco](guides/GUIDE_SK.md) · 🇭🇷 [Croata](guides/GUIDE_HR.md)

</details>

## Notas de configuración

**Idioma de respuesta.**El agente responde en**estonio**por defecto — eso es una
configuración, no un requisito del protocolo, y nada más sobre SAIPEN es en estonio.
El protocolo, el código, los commits y cada documento permanecen en inglés en cada
valor. Cambia en un solo lugar: la`reply_language:`línea en la parte superior de
[`saipen/STYLE.md`](saipen/STYLE.md). `et`estonio,`en`inglés,`ru`ruso,
`auto`elige desde el mensaje que enviaste.

**Adaptadores.**Plataforma no cubierta por el inyector(DeepSeek, Qwen, standalone
OpenAI, etc.)? Notas por plataforma viven en`extensions/adapters/`.

## Capturas de pantalla

<details>
<summary><b>Click to expand</b></summary>

<img src="assets/screenshot-freebuff.png" alt="FreeBuff agent instructions" width="600"/>

<img src="assets/screenshot-nomadcode1.png" alt="saipen set in nomadcode" width="600"/>

<img src="assets/screenshot-20260801-003853.png" alt="saipen screenshot 2026-08-01" width="600"/>

</details>

<p align="center">
  <img src="assets/SAIPEN_design2_alpha.png" alt="SAIPEN Stamp" width="120"/>
</p>

<!-- translation-model: qwen3:14b contract:structured-markdown-v2 -->
<!-- source-digest: README.md sha256:bb47f7158db4a7a4fd99298427c1e4bc6859433c36435640e129cc6dad2a63b7 -->
