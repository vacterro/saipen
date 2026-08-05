<p align="center">
  <img src="assets/SAIPEN_design1.png" alt="SAIPEN Guide Title" width="800"/>
</p>

# Guía SAIPEN (Español)

Escucha, novato. El problema es simple: tus agentes de IA tienen la memoria de un pez rojo.

**SAIPEN** es un cuaderno resistente dentro de la carpeta `.saipen/` de tu proyecto.

**Atajos rápidos:** `cc` continúa una ejecución activa de Goal Mode, `sss` informa del estado sin tocar código y `ss` guarda un punto de control y se detiene. [Ver el mapa completo de 15 teclas](../saipen/RFC.md#110-command-surface). Los gemelos cirílicos también funcionan: `сс`, `ссс`, `аа`, `ее`, `еее`, `рр`.

## Inicio Rápido

1. **Instalar una vez por máquina:**
```bash
git clone https://github.com/vacterro/saipen
cd saipen
powershell -ExecutionPolicy Bypass -File .\bootstrap\inject.ps1     # Windows
bash bootstrap/inject.sh                                            # macOS / Linux
```

2. **Iniciar proyecto:**
> `saipen set`

3. **Trabajar:**
> `saipen`

## Comandos

| Comando | Acción |
|---|---|
| `saipen set` | Inicializar carpeta de memoria `.saipen/` |
| `saipen continue` | Reanudar trabajo desde notas |
| `saipen stop` | Guardar progreso y detener |
| `saipen status` | Leer tablero y estado |
| `saipen goal <text>` | Pivotar hacia nuevo objetivo |
| `saipen clean` | Limpieza profunda del repositorio |
| `saipen translate` | Construcción aislada de traducción en 32 idiomas |
| `saipen markhunt` | Auditoría profunda e ilimitada -- solo registra hallazgos |
| `saipen prepare` | Empaqueta el trabajo para entregarlo al siguiente agente |
| `saipen ship` | Desencadenar flujo de lanzamiento |

## Bueno saber
- ¿Cambios sin confirmar al volver al proyecto? Normal -- SAIPEN confirma (commit) solo en `ship`, no en cada paso. El agente verifica primero de quién son esos cambios antes de tocar nada.
- ¿Quieres que recuerde una decisión de arquitectura real? Ponla en `.saipen/KNOWLEDGE/`, como un archivo `decisions.md` o archivos numerados `ADR-001.md`.
- ¿No hay git ni shell en esta máquina? El agente lo dice claramente (`mode`, `WAIT: <category> -- <pregunta>`) en vez de adivinar (la categoría es una de siete: `manual-verify, destructive-op, first-publish, user brake, blocked, safety valve, init`; indica qué tipo de respuesta desbloquea la situación)
- ¿Quieres una red de seguridad? `python <clon-saipen>/tools/install_hook.py` instala una verificación antes de cada commit.

---

**Full command list / complete command reference:** [RFC § 1.10](../saipen/RFC.md#110-command-surface) — the authoritative list of every `saipen` command.
