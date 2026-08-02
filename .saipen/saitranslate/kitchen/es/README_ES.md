<p align="center">
  <img src="assets/SAIPEN_TEXT1.png" alt="Logo de SAIPEN"/>
  <br>
  <img src="assets/__SAIPEN_Alpha.png" alt="Sticker de SAIPEN" width="200"/>
</p>

# SAIPEN

**Protocolo de continuación para agentes de código con IA.** Memoria de proyecto persistente en
markdown plano, para que un agente nuevo sin historial de chat ejecute `/saipen continue`
y reanude el trabajo en menos de un minuto: sin explicaciones previas, cualquier proveedor, cualquier día.

**Un comando. Cero amnesia.**

**Atajos rápidos:** `cc` continúa una ejecución activa de Goal Mode, `sss` informa del estado sin tocar código y `ss` guarda un punto de control y se detiene. [Ver el mapa completo de 13 teclas](saipen/RFC.md#110-command-surface). Los gemelos cirílicos también funcionan: `сс`, `ссс`, `аа`, `ее`, `еее`, `рр`.

**v7.169.0** | [Espec](SPEC.md) | [Guía](GUIDE.md) | [RFC](saipen/RFC.md) | [Estilo](saipen/STYLE.md) | [UI](saipen/UI.md) | [Conformidad](saipen/CONFORMANCE.md) | markdown plano | cero dependencias | MIT

[![Guía en Ruso](https://img.shields.io/badge/📖_Guía_ELI5-НА_РУССКОМ-red?style=for-the-badge)](guides/GUIDE_RU.md)
[![Guía en Inglés](https://img.shields.io/badge/📖_Guía_ELI5-IN_ENGLISH-blue?style=for-the-badge)](guides/GUIDE_EN.md)
[![Guía en Estonio](https://img.shields.io/badge/📖_Guía_ELI5-EESTI-black?style=for-the-badge)](guides/GUIDE_EE.md)
[![Guía en Japonés](https://img.shields.io/badge/📖_Guía_ELI5-日本語-red?style=for-the-badge)](guides/GUIDE_JA.md)
[![Voz del Viejo](https://img.shields.io/badge/👴_Guía-ВЕРСИЯ_ДЕДА-brown?style=for-the-badge)](guides/GUIDE_DED.md)

```text
Usuario ->  /saipen continue
Agente  ->  lee STATE ("¿Qué hago ahora mismo?")
Agente  ->  lee BOARD ("¿Qué tarea estoy retomando?")
Agente  ->  lee next_action (ejecuta el comando)
Agente  ->  Trabaja.
```

### Estado del Proyecto > Memoria del Modelo
La memoria vive en el proyecto, no en la cabeza de un modelo. `Proyecto -> Memoria -> LLM` se convierte en `Proyecto -> Estado SAIPEN -> LLM`.

### Lógica Principal del Protocolo y Garantías
- **Máquina de Estados Principal**: `INIT → PLAN → SCOUT → BUILD → VERIFY → REVIEW → SHIP → DONE | BLOCKED`
- **Autonomía sin Prompts**: ¿No quedan tareas pendientes? Transición automática `HUNT` (buscar errores) → `ADD` (desarrollar funcionalidades) → bucle `HUNT`. Sin hacer preguntas.
- **Disparadores Explícitos**: `/saipen clean` (limpieza de repo), `/saipen translate` (fábrica aislada `.saipen/saitranslate/`), `/saipen markhunt` (auditoría en seco sin límites, solo registra), `/saipen prepare` (empaquetar trabajo para transferencia), `/saipen validate` (verificación de conformidad), `/saipen goal` (ejecución autónoma por oleadas). Meta/control: `/saipen status` (informe de solo lectura), `/saipen stop` (punto de control y detención). Lista completa: RFC.md § 1.10.
- **Fiabilidad Estricta**: Análisis sintáctico de entradas en lote (tickets quirúrgicos 1 a 1), adopción de árbol de trabajo con cambios no guardados (nunca borra trabajo sin commit), redacción de secretos (`sk-***`).
- **En desarrollo -- saicrew**: una capa adicional opcional (`extensions/subs/`, sin cambios en el Core) para ejecutar un equipo multiagente -- un Core escritor más trabajadores de solo lectura `saihunt`/`saipython`, que informan a través de su propio `OUTBOX.md`. Actualmente en pruebas en vivo, aún no verificado de extremo a extremo -- ver `extensions/subs/crew.md`.

## Proyectos Impulsados por SAIPEN
- ⚡ **[FastPrompter](https://github.com/vacterro/fastprompter)** — Herramienta de gestión de prompts de alto rendimiento integrada de forma nativa con el protocolo de memoria SAIPEN.

## Dos Capas

| Capa | Requerido | Propósito |
|---|---|---|
| **Core** | ✅ | Continuar el trabajo de forma segura |
| **Mantenimiento** | Sobre la capa Core | Evolucionar el software sin asignación previa de tareas |

**Evolución Automatizada.** No quedan tareas pendientes, escribe `/saipen`: `HUNT` audita en busca de errores, código muerto o pruebas fallidas. ¿Todo limpio? `ADD` construye la siguiente capacidad obvia que falta, la verifica y vuelve a auditar con HUNT. ¿El producto está maduro? Se detiene de forma limpia.

**Modo GOAL.** `/saipen goal <lo que quieres>` reorganiza el tablero (las tareas antiguas se degradan de prioridad, nunca se eliminan) y hace avanzar el nuevo objetivo: sin "¿debo continuar?" entre tickets, VERIFY/REVIEW nunca se omiten. SHIP realiza auto-push a un remoto existente; en un repositorio totalmente nuevo preguntará una vez. Enviar el objetivo tampoco es el punto final: pasa directamente a mantenimiento autónomo HUNT/ADD hasta que el producto esté maduro, bloqueado o la ejecución alcance su límite (3 oleadas / 20 tickets, momento en el que genera un punto de control e informa).

## Inicio Rápido

**1. Instalar una vez por máquina** — enseña a Claude Code, Gemini, OpenCode, Aider, Antigravity, Codex y cualquier lector generico de ~/.agents/skills (FreeBuff, etc.):
```bash
git clone https://github.com/vacterro/saipen
cd saipen
powershell -ExecutionPolicy Bypass -File .\bootstrap\inject.ps1     # Windows
bash bootstrap/inject.sh                                            # macOS / Linux
```

**2. Iniciar un proyecto** — abre un agente en tu carpeta y escribe:
> `saipen set`

¿Sin instalación? Pega una línea en cualquier agente:
> Lee <clon>/saipen/RFC.md + <clon>/saipen/STYLE.md y síguelos.

¿Plataforma no incluida en la lista anterior (DeepSeek, Qwen, OpenAI independiente, etc.)?
Las notas específicas para cada plataforma se encuentran en `extensions/adapters/`.

## Enlaces de Documentación y Especificación
- **[SPEC.md](SPEC.md)** — arquitectura formal, objetivos de diseño, prueba de fuego.
- **[RFC.md](saipen/RFC.md)** — especificación normativa ejecutada por los agentes.
- **[GUIDE.md](GUIDE.md)** — tutorial humano y guías sencillas (ELI5):
  - 🇷🇺 [Русский](guides/GUIDE_RU.md) | 🇺🇸 [English](guides/GUIDE_EN.md) | 🇪🇪 [Eesti](guides/GUIDE_EE.md) | 🇯🇵 [日本語](guides/GUIDE_JA.md) | 👴 [Версия Деда](guides/GUIDE_DED.md)
  - 🇺🇦 [Українська](guides/GUIDE_UK.md) | 🇩🇪 [Deutsch](guides/GUIDE_DE.md) | 🇫🇷 [Français](guides/GUIDE_FR.md) | 🇪🇸 [Español](guides/GUIDE_ES.md) | 🇮🇹 [Italiano](guides/GUIDE_IT.md)
  - 🇵🇹 [Português](guides/GUIDE_PT.md) | 🇳🇱 [Nederlands](guides/GUIDE_NL.md) | 🇵🇱 [Polski](guides/GUIDE_PL.md) | 🇸🇪 [Svenska](guides/GUIDE_SV.md) | 🇩🇰 [Dansk](guides/GUIDE_DA.md)
  - 🇫🇮 [Suomi](guides/GUIDE_FI.md) | 🇳🇴 [Norsk](guides/GUIDE_NO.md) | 🇨🇳 [中文](guides/GUIDE_ZH.md) | 🇰🇷 [한국어](guides/GUIDE_KO.md) | 🇹🇭 [ไทย](guides/GUIDE_TH.md) | 🇻🇳 [Tiếng Việt](guides/GUIDE_VI.md) | 🇸🇦 [العربية](guides/GUIDE_AR.md) | 🇮🇱 [עברית](guides/GUIDE_HE.md)
  - 🇹🇷 [Türkçe](guides/GUIDE_TR.md) | 🇮🇳 [हिन्दी](guides/GUIDE_HI.md) | 🇮🇩 [Bahasa Indonesia](guides/GUIDE_ID.md) | 🇬🇷 [Ελληνικά](guides/GUIDE_EL.md) | 🇨🇿 [Čeština](guides/GUIDE_CS.md) | 🇷🇴 [Română](guides/GUIDE_RO.md)
  - 🇭🇺 [Magyar](guides/GUIDE_HU.md) | 🇧🇬 [Български](guides/GUIDE_BG.md) | 🇸🇰 [Slovenčina](guides/GUIDE_SK.md) | 🇭🇷 [Hrvatski](guides/GUIDE_HR.md)
- **[STYLE.md](saipen/STYLE.md)** — estilo de comunicación del agente y definición de voz.
- **[UI.md](saipen/UI.md)** — directrices de diseño de interfaz en estilo Win95 dorado oscuro.
- **[CONFORMANCE.md](saipen/CONFORMANCE.md)** — escenarios de prueba de comportamiento y reglas de validación.

<p align="center">
  <img src="assets/SAIPEN_design2_alpha.png" alt="Sello de SAIPEN" width="120"/>
</p>


