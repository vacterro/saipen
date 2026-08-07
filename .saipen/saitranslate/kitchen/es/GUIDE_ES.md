<p align="center">
  <img src="assets/SAIPEN_design1.png" alt="SAIPEN Guide Title" width="800"/>
</p>

# Guía SAIPEN (Español)

[TRANSLATED ES]:
It is 2026 and the AI woke up. The assistants stopped being chat toys — they open your project, write the code, run the tests, and finish a job while you go make coffee. There is one thing they cannot do. They cannot remember. Close the window and everything they learned about your work is gone: what you were building, what you already tried, which idea died on Tuesday. Every morning you brief a brilliant stranger from scratch.

This is the fix for that one thing.

**SAIPEN** es un cuaderno resistente dentro de la carpeta `.saipen/` de tu proyecto.

## Inicio Rápido

## Comandos

## Bueno saber
- ¿Cambios sin confirmar al volver al proyecto? Normal -- SAIPEN confirma (commit) solo en `ship`, no en cada paso. El agente verifica primero de quién son esos cambios antes de tocar nada.
- ¿Quieres que recuerde una decisión de arquitectura real? Ponla en `.saipen/KNOWLEDGE/`, como un archivo `decisions.md` o archivos numerados `ADR-001.md`.
- ¿No hay git ni shell en esta máquina? El agente lo dice claramente (`mode`, `WAIT: <category> -- <pregunta>`) en vez de adivinar (la categoría es una de siete: `manual-verify, destructive-op, first-publish, user brake, blocked, safety valve, init`; indica qué tipo de respuesta desbloquea la situación)
- ¿Quieres una red de seguridad? `python <clon-saipen>/tools/install_hook.py` instala una verificación antes de cada commit.