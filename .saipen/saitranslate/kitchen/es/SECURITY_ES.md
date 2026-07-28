# Política de Seguridad

## Alcance

SAIPEN es una especificación más un pequeño conjunto de scripts locales de instalación/exportación (`bootstrap/inject.ps1`/`.sh`, `uninstall.ps1`/`.sh`, `export.ps1`/`.sh`). No ejecuta un servidor, no recopila telemetría y no transmite ningún dato a ninguna parte. Todo lo que hacen los scripts son escrituras en el sistema de archivos local en archivos que usted ya controla (su propio `~/.claude`, `~/.gemini`, `.saipen/` del proyecto, etc.).

Se aplican dos niveles diferentes de cuidado, y vale la pena ser precisos en lugar de afirmar seguridad absoluta:

- **Sus propios archivos de configuración** (`CLAUDE.md`, `AGENTS.md`, `GEMINI.md`, `.aider.conf.yml`) solo se editan agregando o eliminando un bloque delimitado `SAIPEN:BEGIN`/`END`, y el original se copia a `<file>.bak` antes de la primera modificación. La desinstalación adicionalmente escribe `<file>.uninstalled.bak` antes de eliminar.
- **Los directorios de habilidades** que crea el inyector (`~/.claude/skills/saipen` y similares) son copias propiedad de SAIPEN y **no** tienen respaldo: la instalación los sobrescribe por completo y la desinstalación los elimina recursivamente. Eso es intencional -- solo contienen copias de los archivos propios de este repositorio -- pero si edita manualmente una copia de habilidad local, esas ediciones se pierden en la próxima ejecución de `inject`/`uninstall`. Mantenga las personalizaciones en su propio bloque de configuración o en un fork, no dentro de la carpeta de habilidad copiada.

Las dos únicas cosas que realmente ameritan un reporte de seguridad son:
1. Un script de inicio (bootstrap) haciendo algo en su sistema de archivos o historial de git más allá de lo que describen sus propios comentarios/README.
2. La propia regla de higiene de secretos del protocolo (RFC.md § 1.1 -- nunca escribir claves de API, tokens, contraseñas en `STATE.md`/`BOARD.md`/`LOG.md`/`KNOWLEDGE/`/`kitchen/`/`extensions/`/`saitranslate/kitchen/`/`recovery/`/`logs/`) que tenga una brecha real que causaría que un agente que sigue SAIPEN filtre un secreto en un archivo comprometido (committed). Los dos últimos son los sutiles: Recovery copia un `STATE.md` corrupto textualmente a `.saipen/recovery/`, y el sellado de LOG mueve líneas textualmente a `.saipen/logs/`, por lo que cualquier cosa que llegó al original es archivada por maquinaria cuyo trabajo completo es no alterar el contenido.

## Versiones Soportadas

Solo la última versión etiquetada en `main` tiene soporte. Esta es una especificación de protocolo, no un servicio de larga duración -- no hay rama LTS.

## Reportar una Vulnerabilidad

Abra un issue en GitHub. Si el reporte involucra un problema real y actualmente explotable (no hipotético), márquelo como un aviso privado/de seguridad a través de la pestaña **Security** de este repositorio ("Report a vulnerability") en lugar de un issue público, para que no sea visible públicamente antes de que se publique una solución.

Incluya: qué script o regla de RFC, el escenario concreto y qué sucede realmente frente a lo que debería suceder. El mismo estándar de evidencia que cualquier otro reporte de error (ver `CONTRIBUTING.md`).
