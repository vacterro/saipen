# Política de Segurança

## Escopo

SAIPEN é uma especificação mais um pequeno conjunto de scripts locais de instalação/exportação
(`bootstrap/inject.ps1`/`.sh`, `uninstall.ps1`/`.sh`,
`export.ps1`/`.sh`). Ele não roda um servidor, não coleta
telemetria e não transmite dados para lugar nenhum. Tudo o que os
scripts fazem são gravações locais no sistema de arquivos em arquivos que você já controla
(o seu próprio `~/.claude`, `~/.gemini`, projeto `.saipen/`, etc.).

Dois níveis diferentes de cuidado se aplicam aqui, e vale a pena ser exato
em vez de reivindicar segurança genérica:

- **Seus próprios arquivos de configuração** (`CLAUDE.md`, `AGENTS.md`, `GEMINI.md`,
  `.aider.conf.yml`) são editados apenas adicionando ou removendo um
  bloco delimitado `SAIPEN:BEGIN`/`END`, e o original é copiado para
  `<file>.bak` antes da primeira modificação. A desinstalação adicionalmente
  escreve `<file>.uninstalled.bak` antes de remover.
- **Os diretórios de habilidades** que o injetor cria (`~/.claude/skills/saipen`
  e similares) são cópias de propriedade do SAIPEN e **não** têm backup: a instalação
  os sobrescreve por completo e a desinstalação os remove recursivamente. Isso é
  intencional -- eles contêm apenas cópias dos próprios arquivos deste repositório --
  mas se você editar manualmente uma cópia de habilidade local, essas edições serão
  perdidas no próximo `inject`/`uninstall`. Mantenha personalizações em seu próprio
  bloco de configuração ou um fork, não dentro da pasta de habilidade copiada.

As duas coisas que realmente merecem um relatório de segurança:
1. Um script de inicialização (bootstrap) fazendo algo no seu sistema de arquivos ou histórico do git
   além do que seus próprios comentários/README descrevem.
2. A própria regra de higiene de segredos do protocolo (RFC.md § 1.1 -- nunca escreva
   chaves de API, tokens, senhas em `STATE.md`/`BOARD.md`/`LOG.md`/
   `KNOWLEDGE/`/`kitchen/`/`extensions/`/`saitranslate/kitchen/`/
   `recovery/`/`logs/`) tendo uma brecha real que faria um
   agente seguindo o SAIPEN vazar um segredo em um arquivo comitado. Os dois últimos
   são sutis: Recovery copia um `STATE.md` corrompido literalmente para
   `.saipen/recovery/`, e o selamento (sealing) do LOG move linhas literalmente para
   `.saipen/logs/`, então tudo que atingiu o original é arquivado por uma maquinaria
   cujo trabalho inteiro é não alterar conteúdo.

## Versões Suportadas

Apenas o lançamento marcado mais recente na `main` tem suporte. Esta é uma
especificação de protocolo, não um serviço de longa duração -- não existe branch
LTS.

## Reportando uma Vulnerabilidade

Abra uma issue no GitHub. Se o relatório envolver um problema real, atualmente explorável
(não uma hipótese), marque-o como um aviso privado/de segurança pela
aba **Security** deste repositório ("Report a vulnerability") em vez de
uma issue pública, para que não fique publicamente visível antes de lançar a correção.

Inclua: qual script ou regra da RFC, o cenário concreto, e o que
realmente acontece versus o que deveria acontecer. O mesmo padrão de evidência de qualquer
outro relatório de bug (veja `CONTRIBUTING.md`).
