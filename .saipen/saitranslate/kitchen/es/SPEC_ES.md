# Especificación SAIPEN

## Resumen
**Objetivo de Diseño #1: Un agente en frío con historial de chat cero debe ser capaz de ejecutar `/saipen continue` y reanudar el trabajo productivo dentro de un minuto, sin pedirle al usuario que repita el contexto.**

SAIPEN garantiza que cualquier agente de IA compatible pueda continuar con seguridad cualquier proyecto sin recibir nuevas instrucciones. Es una ABI (Interfaz Binaria de Aplicación) para agentes de IA de ingeniería — una capa de compatibilidad que resuelve el problema de la amnesia. Ya sea que use Claude hoy, Gemini mañana y GPT pasado mañana, todos operarán contra el mismo estado del proyecto sin requerir que usted reitere el contexto.

### Filosofía Central: Estado del Proyecto > Memoria del Modelo
La memoria debe vivir junto al código, no dentro de la cabeza de otro modelo. SAIPEN cambia el paradigma de `Proyecto -> Memoria -> LLM` a `Proyecto -> Estado SAIPEN -> LLM`. La memoria pertenece al proyecto.

En su núcleo, SAIPEN usa un protocolo de continuación portátil, respaldado por archivos, para agentes LLM. Las implementaciones PUEDEN variar. El contrato en disco DEBE permanecer estable. Todo en este protocolo existe para servir a la Prueba de Continuación.

SAIPEN es evolutivo, no creativo. Su propósito es completar software, no reinventarlo. ADD extiende los patrones de diseño existentes, las convenciones de la industria y la simetría obvia de características.

- **`STATE`**: Existe para responder *"¿Qué hago ahora mismo?"*
- **`BOARD`**: Existe para responder *"¿Qué tarea estoy retomando?"*
- **`LOG`**: Existe para responder *"¿Por qué llegamos a este punto?"*
- **`KNOWLEDGE`**: Existe para responder *"¿Cuál es la verdad duradera de este proyecto?"*
- **`next_action`**: El corazón de SAIPEN. Responde *"¿Qué comando exacto ejecuto en este mismo segundo para reanudar el trabajo?"*

## La Prueba de Fuego SAIPEN

Cualquier cambio propuesto o nueva idea para el protocolo DEBE superar las siguientes tres preguntas:
1. ¿Hace que la transición entre agentes sea más confiable?
2. ¿Hace que el comportamiento de los diferentes modelos sea más uniforme?
3. ¿Reduce la probabilidad de pérdida de contexto?

Si la respuesta es "no" a al menos dos de estas preguntas, la idea es rechazada. SAIPEN prioriza la disciplina, la reproducibilidad y la confiabilidad sobre la novedad.

## Arquitectura

El protocolo es estrictamente normativo. SAIPEN se divide conceptualmente en dos capas: **Central (Core)** y **Mantenimiento**. 
- **La capa Central** garantiza una continuación de tareas segura y neutral al proveedor. 
- **La capa de Mantenimiento** es un modelo de evolución de software autónomo construido sobre la Central.

Debajo de las dos capas, SAIPEN separa tres preocupaciones que nunca se enredan:
**corrección y continuación** (Central -- `STATE`/`BOARD`/`LOG`/`KNOWLEDGE`, negociación de
capacidades, puntos de control), **evolución desatendida** (Mantenimiento -- `HUNT`/`ADD`/`CLEAN`,
completamente funcional bajo el valor predeterminado `saipen`/`saipen continue`), y **rendimiento**
(Modo Goal, Subagentes -- ambos con opt-in explícito, §1.3/§2.4). Desactive el Modo Goal: el
protocolo no cambia, un ticket a la vez. Desactive los Subagentes: `HUNT` ejecuta las mismas
seis categorías secuencialmente, mismo resultado. Use la capa Central sola, sin capa de Mantenimiento en
absoluto: todavía se sostiene -- un agente en frío aún reanuda correctamente. Cada capa se basa en la
que está debajo sin que lo inverso sea cierto alguna vez; nada aguas arriba depende de que una
característica aguas abajo exista.

```text
saipen/
  RFC.md                    especificación normativa (dividida en Central y Mantenimiento)
  CONFORMANCE.md             vectores de autocomprobación + tabla de cobertura de escenarios
  SKILL.md                  punto de entrada delgado para plataformas que leen habilidades
  STYLE.md                  voces: chat, LOG.md, artefactos
  UI.md                     Especificación de interfaz Wintage Golden (obligatorio para trabajo de UI)
  BOOT.md                   secuencia de arranque / orquestación de inicio en frío
  phases/                   16 docs, one per RFC § 1.6 enum value (machine-checked both ways by tools/validate.py)
    [Fases Centrales]
    init.md / plan.md / scout.md / build.md / verify.md / review.md / ship.md / done.md / blocked.md
    [Fases de Mantenimiento]
    hunt.md / add.md / clean.md / translate.md / markhunt.md

  [Infrastructure]
  prepare.md                preparación del espacio de trabajo
  validate.md               pruebas de conformidad entre fases

extensions/                 <- LA CAPA ADAPTATIVA
  adapters/                 puentes de instrucción por modelo, para plataformas que el
                             inyector no detecta automáticamente (README.md apunta aquí)
  schemas/                  state.schema.json es leído por máquina mediante tools/validate.py
                             (única fuente de verdad para la forma de STATE); los esquemas de
                             board/log se mantienen solo como referencia (ver schemas/README.md)
  templates/                código repetitivo fresco para .saipen/
  security/                 EJEMPLO de hook para copiar a un proyecto (RFC § 1.9, se adjunta a VERIFY)
  performance/              EJEMPLO de hook para copiar a un proyecto (RFC § 1.9, se adjunta a REVIEW)
  subs/                     EJEMPLO de subagentes de investigación de solo lectura (RFC § 1.9) -- propio
                             STATE/BOARD/LOG por subagente, hallazgos solo vía OUTBOX,
                             nunca una segunda vía de escritura hacia el proyecto

bootstrap/                  <- INSTALACIÓN/EXPORTACIÓN/DESINSTALACIÓN, una máquina a la vez
  inject.ps1 / .sh          instala el bloque SAIPEN + copias de habilidades (Inicio Rápido en README)
  uninstall.ps1 / .sh       revierte inject -- elimina bloques + copias de habilidades
  export.ps1 / .sh          archiva el .saipen/ de un proyecto para respaldo
  saipen_crew.bat / .sh     lanza la herramienta de equipo SAIPEN

tools/                      <- VALIDADOR CANÓNICO Y UTILIDADES DE REPOSITORIO
  validate.py               validador canónico de conformidad (Python stdlib, cero
                             instalaciones; valida STATE contra state.schema.json
                             directamente, además de revisiones de grafo que el par de shell no puede hacer)
  install_hook.py           instala un hook pre-commit que ejecuta validate.py
  uninstall_hook.py         elimina exactamente ese hook (restaura cualquier anterior)

tests/                      <- CAPA DE CONFORMIDAD
  validate.ps1 / .sh        piso portátil congelado para hosts sin Python --
                             las nuevas comprobaciones aterrizan solo en tools/validate.py
  scenarios/                estados simulados (recuperación de fallas, conflictos de reclamos, etc.)
```

## Negociación de Capacidades Bidireccional
Los agentes no simplemente declaran lo que pueden hacer; el protocolo exige lo que se requiere.
El proyecto define `requires: [filesystem, git, shell, python]` en su estado. El agente cruza las referencias de sus capacidades de host contra los requisitos y se bloquea en un `mode` (ej. `full`, `read-only`).

## Registro de Eventos Basado en Grafos
Los registros en SAIPEN no son cadenas lineales. Forman un grafo acíclico de decisiones usando IDs de Evento (`E-001`). Esto permite bifurcaciones complejas, fusión de agentes y pistas de auditoría precisas.

## Registros de Decisiones de Arquitectura (ADR)
Los registros de eventos transitorios no albergan conocimiento permanente. SAIPEN exige que las decisiones arquitectónicas estructurales se persistan como ADRs (ej., `KNOWLEDGE/ADR-001-use-sqlite.md`).

## Concurrencia y Límites de Distribución
SAIPEN garantiza la integridad del estado a través de reclamos basados en archivos (`owner`, `claim_time`) y grafos secuenciales (`LOG.md`). Sin embargo, **SAIPEN es un protocolo de estado, no un algoritmo de consenso distribuido.**
- **Sistema de archivos Local/Compartido**: La resolución de conflictos se basa en escrituras atómicas en el sistema de archivos ("el primer commit gana").
- **Entornos de Red/Distribuidos**: Si los agentes operan en máquinas desconectadas sin sincronización de archivos en tiempo real, ocurrirán condiciones de carrera en los reclamos de `BOARD.md`. En configuraciones altamente distribuidas, el contrato de protocolo SAIPEN en disco DEBE permanecer estable -- el estado del proyecto en sí mismo muta constantemente, a través de las propias reglas de SAIPEN (checkpointing de § 1.5), nunca la forma del protocolo que siguen esas reglas.

<p align="center">
  <img src="assets/SAIPEN_design2_alpha.png" alt="Sello SAIPEN" width="120"/>
</p>
