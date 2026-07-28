# Contribuyendo a SAIPEN

SAIPEN es una especificación primero, una implementación después. La mayoría de las contribuciones son cambios en `saipen/RFC.md`, un archivo `phases/*.md` o las herramientas de conformidad en `tests/` -- no código de aplicación.

## Antes de proponer un cambio

Ejecute la [Prueba de Fuego SAIPEN](SPEC.md#the-saipen-litmus-test) en su idea:
1. ¿Hace que la transición entre agentes sea más confiable?
2. ¿Hace que el comportamiento de los diferentes modelos sea más uniforme?
3. ¿Reduce la probabilidad de pérdida de contexto?

Si la respuesta es "no" a al menos dos de estas preguntas, está fuera del alcance de este protocolo, por muy útil que pueda ser en otro lugar.

## Reportando una brecha

Abra un issue describiendo:
- en qué archivo/sección está la brecha (RFC.md, un documento de fase, un esquema, una prueba)
- la evidencia concreta (una cita, un comando y su salida, un escenario donde el comportamiento actual falla)
- lo que esperaría en su lugar

Los informes vagos ("esto se siente raro") son más difíciles de actuar que un `grep`/reproducción específico. Vea la plantilla de reporte de errores para la forma que esto debería tomar.

## Haciendo un cambio

1. Lea `saipen/RFC.md` y los archivos `phases/*.md` relevantes por completo antes de editar -- la mayoría de las brechas aparentes resultan estar ya abordadas en otro lugar, o deliberadamente delimitadas de cierta manera por una razón documentada.
2. Verifique `CHANGELOG.md` y `.saipen/KNOWLEDGE/decisions.md` en busca de arte previo. No reabra silenciosamente una decisión que ya fue tomada y rechazada -- si tiene nueva evidencia de que un rechazo pasado fue erróneo, dígalo explícitamente en la descripción del PR.
3. Todo cambio normativo (un DEBE/NO DEBE/DEBERÍA) necesita una entrada en `CHANGELOG.md` y, donde sea práctico, cobertura en `tests/validate.sh` + `tests/validate.ps1` (ambas plataformas) o un accesorio (fixture) bajo `tests/scenarios/`.
4. Ejecute el validador canónico antes de abrir un PR:
   ```bash
   python tools/validate.py
   ```
   Este es el que importa -- comprueba STATE.md contra extensions/schemas/state.schema.json, recorre el grafo de eventos de LOG.md a través de segmentos sellados y verifica el manifiesto de runtime y el cableado del inyector. tests/validate.sh / validate.ps1 son el piso portátil congelado para hosts sin Python (lo dicen en la parte superior de cada archivo): menos comprobaciones, mantenidos solo para que un host sin Python no se quede sin nada. Ejecútelos también si su cambio toca alguno de ellos, pero nunca en su lugar -- pasar solo el piso demuestra mucho menos de lo que parece. CI ejecuta el validador canónico en cada push y PR independientemente (.github/workflows/validate.yml).
5. Aumente la versión `VERSION` según el esquema en `phases/ship.md` (patch para aclaraciones solo de documentos, minor para nuevo comportamiento normativo, major para cambios de contrato que rompen compatibilidad) y mantenga sincronizada la insignia de versión de `README.md` -- `tests/validate.sh`/`.ps1` verifican esto automáticamente cuando se ejecutan desde un clon de este repositorio.

## Estilo

- Documentos de protocolo y fases: concisos, palabras clave RFC-2119 donde importen, sin relleno. Ver `saipen/STYLE.md`.
- Todo en este archivo, mensajes de commit, comentarios de código y el CHANGELOG: simple y profesional. Las propias voces de chat/LOG del proyecto (`saipen/STYLE.md`) no se aplican a los artefactos.

## Lo que está fuera de alcance

- Convertir SAIPEN en un sistema de consenso distribuido. Ver la sección Concurrency & Distribution Boundaries de `SPEC.md`.
- Gramática de marcadores LOG analizable por máquina más allá del esqueleto existente. `LOG.md` se mantiene en prosa alrededor de una forma fija.
- Un comando `saipen doctor` o similar redundante con `saipen validate` + `saipen status`.

Estos han sido propuestos y evaluados cada uno antes; reabrirlos necesita nueva evidencia, no solo volver a preguntar.

