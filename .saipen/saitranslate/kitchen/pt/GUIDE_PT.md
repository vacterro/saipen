<p align="center">
  <img src="assets/SAIPEN_design1.png" alt="SAIPEN Guide Title" width="800"/>
</p>

# Guia SAIPEN (Português)

[TRANSLATED PT]:
It is 2026 and the AI woke up. The assistants stopped being chat toys — they open your project, write the code, run the tests, and finish a job while you go make coffee. There is one thing they cannot do. They cannot remember. Close the window and everything they learned about your work is gone: what you were building, what you already tried, which idea died on Tuesday. Every morning you brief a brilliant stranger from scratch.

This is the fix for that one thing.

## Início Rápido

## Comandos

## Bom saber
- Alterações não commitadas ao voltar ao projeto? Normal -- o SAIPEN só faz commit no `ship`, não a cada passo. O agente verifica primeiro de quem são essas alterações antes de tocar em qualquer coisa.
- Quer que ele lembre uma decisão de arquitetura real? Coloque em `.saipen/KNOWLEDGE/`, como um arquivo `decisions.md` ou arquivos numerados `ADR-001.md`.
- Sem git ou shell nesta máquina? O agente diz isso claramente (`mode`, `WAIT: <category> -- <pergunta>`) em vez de adivinhar (a categoria é uma das sete: `manual-verify, destructive-op, first-publish, user brake, blocked, safety valve, init`; indica que tipo de resposta desbloqueia a situação)
- Quer uma rede de segurança? `python <clone-saipen>/tools/install_hook.py` instala uma verificação pré-commit.