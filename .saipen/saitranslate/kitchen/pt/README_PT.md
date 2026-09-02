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

**Protocolo de continuação para agentes de codificação de IA.**A memória do projeto vive em arquivos
Markdown dentro do projeto(`.saipen/`), então qualquer agente frio compatível —
sem histórico de chat, sem memória de sessão — pode executar`/saipen continue`, ler o
persistido`next_action`, e retomar o trabalho sem pedir ao usuário para reexplicar
qualquer coisa. O estado pertence ao projeto, não à memória de um fornecedor de modelos.

**Um comando para retomar. Estado em arquivos simples. Contratos verificados pela máquina.**

O repositório valida-se a cada push; instalação, estado, verificações e
desinstalar são todos locais — nenhum serviço em nuvem, nenhum daemon, nenhuma base de dados.

[![Validation](https://github.com/vacterro/saipen/actions/workflows/validate.yml/badge.svg)](https://github.com/vacterro/saipen/actions/workflows/validate.yml)
[![Release](https://img.shields.io/github/v/release/vacterro/saipen?sort=semver&label=release)](https://github.com/vacterro/saipen/releases)
[![License: MIT](https://img.shields.io/github/license/vacterro/saipen?color=blue)](LICENSE)

**v7.238.3** | [Especificações](SPEC.md) | [Guia](GUIDE.md) | [Núcleo](saipen/CORE.md) | [Manutenção](saipen/MAINTENANCE.md) | [Estilo](saipen/STYLE.md) | [UI](saipen/UI.md) | [Conformidade](saipen/CONFORMANCE.md) |MIT

**Atalhos rápidos:** `cc` continua o contexto do projeto até a convergência (retoma um objetivo ativo, se houver um definido), `sss` informa o estado sem tocar no código e `ss` salva um ponto de verificação e para. [Veja o mapa completo de 19 teclas](saipen/RFC.md#110-command-surface). Os gêmeos cirílicos também funcionam: `сс`, `ссс`, `аа`, `ее`, `еее`, `рр`. `ff` → `focus`; `xx` → `cut`; `vv` → `build`; `zz` → `undo`.

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

## O que persiste

A memória do projeto em execução vive em`.saipen/`— arquivos simples que você pode ler, diff e
commit ao lado do código. Um agente frio responde cinco perguntas dos arquivos
sozinho:

|Arquivo / campo|Respostas|
|---|---|
| `STATE.md` |O que está acontecendo agora?(fase, ticket ativo, modo de operação, bloqueador) |
| `BOARD.md` |Qual trabalho existe / qual está ativo?(gráfico de tickets: FAZENDO, PARA FAZER, CONCLUÍDO, BLOQUEADO) |
| `LOG.md` |Por que o projeto chegou a esse estado?(gráfico de eventos apenas-append) |
| `KNOWLEDGE/` |Quais fatos duráveis do projeto devem sobreviver às sessões?|
| `next_action` (em`STATE.md`) |Qual ação exata o próximo agente deve executar?|

Este é um contrato de ponto de verificação, não uma sugestão de design:`saipen stop`e cada
transição de ticket escreve os arquivos em uma ordem fixa, e o resultado é verificado por
um validador. Nada é armazenado em um banco de dados hospedado, e nada é perdido quando um
a sessão termina.

## Início rápido

**1. Instale uma vez por máquina**— ensina Claude Code, Codex, Gemini, OpenCode,
Aider, Antigravity e qualquer leitor genérico`~/.agents/skills`de arquivos(FreeBuff, etc.):

```bash
git clone https://github.com/vacterro/saipen
cd saipen
powershell -ExecutionPolicy Bypass -File .\bootstrap\inject.ps1     # Windows
bash bootstrap/inject.sh                                            # macOS / Linux
```

<sub>What that touches, so nothing is a surprise: it appends a marked
`<!-- SAIPEN:BEGIN -->...<!-- SAIPEN:END -->`bloco para a instrução do agente
arquivos que você já possui(`~/.claude/CLAUDE.md`, `~/.config/opencode/AGENTS.md`,
`~/.codex/AGENTS.md`, `~/.gemini/GEMINI.md`)— fazendo backup de cada um para`.bak`primeiro —
e copia o protocolo para as pastas de habilidades correspondentes. Nada fora dessas
caminhos, sem daemon, sem chamadas de rede.</sub>

**2. Inicie um projeto**— abra um agente na sua pasta, digite:

> `saipen set`

**Sem instalação?**Cole uma linha em qualquer agente:

> Ler&lt;clone&gt;/saipen/BOOT.md primeiro(núcleo de inicialização fria), depois&lt;clone&gt;/saipen/INDEX.md +&lt;clonar&gt;/saipen/STYLE.md e siga-as.

**Mudou de ideia?**Um comando coloca-o de volta:

```bash
powershell -ExecutionPolicy Bypass -File .\bootstrap\uninstall.ps1  # Windows
bash bootstrap/uninstall.sh                                         # macOS / Linux
```

Ele remove exatamente o bloco marcado(deixando o resto do seu arquivo intacto), salva
a `.uninstalled.bak`faça uma cópia primeiro, e remova as pastas de habilidades.

## Por que não apenas o histórico de chat?

SAIPEN visa um falha específica: um agente de codificação de IA que não lembra nada
uma vez que a sessão termina. Outras ferramentas e hábitos cobrem parte desse problema:

|Abordagem|Para o que serve|O que não transporta|
|---|---|---|
|Histórico de chat / memória do modelo|Conveniente, sem configuração necessária|Depende da sessão e do fornecedor; não é armazenado com o projeto, então um agente frio nunca o vê|
|Estático`AGENTS.md`Arquivo / instrução|Regras e convenções duráveis|Não representa por si só o estado vivo da tarefa,`next_action`, ou histórico de recuperação|
|Rastreador de problemas / TODO|Gerenciamento de tarefas e backlog|Não define por si só a semântica de continuação do agente — o que um agente frio deve ler e executar ao retomar|
| **SAIPEN** |Estado de execução em tempo real, fila de trabalho, histórico de eventos, conhecimento durável e regras de continuação verificáveis por máquina — em arquivos comuns ao lado do código|Nada; essa combinação é o contrato|

A diferença não é nenhum único arquivo. É que o SAIPEN executa o passo de retomada
verificável por máquina: a primeira ação de um agente frio após`/saipen continue`é
determinada pelo persistido`next_action`e verificada por um validador, não
reconstruída da memória.

## Evidência de engenharia

O SAIPEN combina um protocolo de arquivo comum normativo com um executável orientado a falhas
verificações. O repositório demonstra o design de protocolo/máquina de estado, Python
ferramentas, estado direcionado por esquema, raciocínio de recuperação, testes de regressão,
limites de fluxo de trabalho multi-agente, e disciplina de especificação.

- **Contrato projetado.** [SPEC.md](SPEC.md)define o modelo de continuação com suporte de arquivo
e o contrato estável no disco;[CORE.md](saipen/CORE.md)
e[MAINTENANCE.md](saipen/MAINTENANCE.md)possuem o comportamento normativo atual.
- **Estado verificado por máquina.**O validador canônico apenas da stdlib
  [validador](tools/validate.py)lê o estado
  [esquema de estado](extensions/schemas/state.schema.json)e verifica a transição de fase
dependências de bilhetes, links do gráfico de eventos, invariantes interdocumentais
capacidades e estado de recuperação.
- **Cobertura de falhas.** [CONFORMANCE.md](saipen/CONFORMANCE.md)mapeia
requisitos para[fixtures de cenário](tests/scenarios/); o
  [executador de cenários](tools/run_scenarios.py)executa casos de pass/fail estruturais
incluindo estado de recuperação corrompido, transições inválidas, ciclos de dependência e
restrições de somente leitura.
- **Controles de regressão.** [audit_checks.py](tools/audit_checks.py)modifica
cópias conhecidas como boas e demonstra que as verificações do validador ainda podem falhar, em vez de
tratar uma verificação permanentemente verde como evidência.
- **Camada executável.** [saipen.py](tools/saipen.py)fornece estado com registro
operações;[bootstrap/](bootstrap/)mantém instalação, desinstalação e exportação
ajudantes, com um opcional[instalador de hook pre-commit](tools/install_hook.py).
- **Compromissos explícitos.**O estado do protocolo principal é arquivos comuns sem dependência de tempo de execução
dependência. Validação canônica e ferramentas de CLI exigem Python, mas usam apenas
sua biblioteca padrão e não necessitam de`pip`instalação.

## Arquitetura

Três camadas, dependências estritamente unidirecionais:

```text
CORE            continuation / state / checkpoint / validation       required
  └─ MAINTENANCE   autonomous HUNT / ADD / CLEAN evolution           optional, on top of Core
       └─ GOAL MODE / SUBAGENTS   opt-in throughput/execution        optional
```

O núcleo não depende da manutenção: com a evolução autônoma desativada, SAIPEN
ainda é um protocolo de continuação completa — um agente frio ainda retoma.

- **Máquina de estado do núcleo** — `INIT → PLAN → SCOUT → BUILD → VERIFY → REVIEW → SHIP → DONE | BLOCKED`.
- **Manutenção autônoma**— placa parada(nada funcional em`## TODO`,
nada em`## DOING`)e não`BLOCKED`? Transições automáticas`HUNT` (verificar bugs)
  → `ADD` (evoluir funcionalidades) → `HUNT`, zero perguntas feitas. Uma sessão sentada em
  `BLOCKED`nunca caça automaticamente
  ([Manutenção § 2.1](saipen/MAINTENANCE.md#21-autonomous-transitions)).
- **Modo de Objetivo** — `/saipen goal <objective>`gira o tabuleiro e executa o
objetivo para frente através de VERIFY/REVIEW, caindo na manutenção autônoma
até que a regra de conclusão seja acionada ou a execução atinja seu limite(3 ondas / 20 tickets,
depois pontos de verificação e relatórios) ([Manutenção § 2.4](saipen/MAINTENANCE.md#24-goal-mode-autonomous-execution)).
- **Aprimoramento**— a entrada em lote é analisada em tickets um por um cirúrgicos
  (CORE § 1.8); a continuação da árvore suja preserva o trabalho não confirmado(CORE § 1.5);
valores semelhantes a segredos são omitidos dos logs(`sk-***`) (CORE § 1.2).

## Comandos comuns

Pontos de entrada cotidianos; a superfície completa atual vive em
[Core § 1.10](saipen/CORE.md#110-command-surface).

|Comando|Faz|
|---|---|
| `/saipen set` |Adote um projeto: crie`.saipen/`estado|
| `/saipen continue` |Retomar do estado persistido do projeto — sem rebriefing|
| `/saipen plan` |Transformar uma solicitação ou backlog bruto em tickets|
| `/saipen goal <text>` |Execução autônoma de onda contra um novo objetivo|
| `/saipen validate` |Executar as verificações de conformidade|
| `/saipen status` |Relatório somente leitura: fase, tickets, bloqueadores, obsolescência|
| `/saipen stop` |Ponto de verificação e parada|

<details>
<summary><b>More commands</b></summary>

|Comando|Faz|
|---|---|
| `/saipen hunt` |Forçar a varredura de defeitos/melhorias agora|
| `/saipen markhunt` |Auditoria seca, sem limites — registra achados, não corrige nada|
| `/saipen ship` |Portas de liberação; commit, tag e push quando permitido|
| `/saipen clean` |Limpeza do quadro e estado|
| `/saipen translate` |Fábrica de tradução isolada|
| `/saipen prepare` / `/saipen collect` |Trabalho de pacote para transferência / integrar um pacote pronto|
| `/saipen test` |Execute o conjunto de testes declarado, relatório apenas|
| `/saipen crew` |Circuito de equipe em ordem fixa(caçar → reproduzir → entrada → construir → traduzir → documentar → enviar) |
| `/saipen improve` |Auditoria de meta-controle de melhorias no protocolo|
| `/saipen sub ...` |Spawn/adoptar sub-agentes somente leitura|

**Chaves do pacote.** `ee`/`qq`preparar pacotes de tradução/wiki completos sem
integrar;`eee`/`qqq`aceitar apenas pacotes prontos, depois integrar, verificar,
revisar e enviar.

**saicrew.** `sc` / `saipen crew` (`extensions/subs/crew.md`)percorre todo o
crew embutido em uma ordem fixa — sensores(saihunt, saitest, saipython, saiui),
produtores(saitranslate, saiwiki)e Core como o único escritor da árvore principal —
até que outra passada fresca não tenha mais nada real para alterar. Ele adiciona exatamente um
mecanismo próprio: o alvo de orquestração durável(`execution_intent:
convergir` with `converge_target: crew`)que torna o circuito reumável e
derivável a partir de evidências.`saipen crew --dry-run --json`deriva o
circuito somente leitura;`bootstrap/saipen_crew.*`é um AUXILIAR MANUAL OPCIONAL
de janelas múltiplas, nunca o que`saipen crew`significa. Veja
[extensions/subs/crew.md](extensions/subs/crew.md).
</details>

## O que o SAIPEN não é

- **Um LLM ou um modelo**— é um protocolo que agentes seguem, não uma inteligência.
- **Um IDE ou um banco de dados de memória hospedado**— o estado são arquivos comuns no seu projeto;
nada é hospedado.
- **Um substituto do Git**— o Git ainda possui a história de versão; faça o commit do
  `.saipen/`como qualquer outro código.
- **Consenso distribuído**— veja a fronteira de concorrência abaixo.
- **Uma garantia de que um LLM tomará decisões de engenharia corretas**— ele
reduz a perda de contexto e o desvio comportamental; ele não torna agentes estocásticos
infalíveis.

A tarefa do SAIPEN é um contrato de continuação/estado mais validação e ferramentas —
entregando ao próximo agente um ponto de partida verificado por máquina, não magia.

**Fronteira de concorrência.**Mutação de estado registrada(SAIOPS)use um
bloqueio do sistema operacional com escopo de projeto e um jornal de recuperação([OPS § 5](saipen/OPS.md#5-locks)).
Edições comuns de projeto e escritores desconectados estão fora desse bloqueio. SAIPEN
não é consenso distribuído, portanto, escritores desconectados exigem coordenação externa
coordenação([SPEC](SPEC.md#concurrency--distribution-boundaries)).

## Ecosistema

|Projeto|Relação com o SAIPEN|
|---|---|
| [SAIPENVIEW](https://github.com/vacterro/saipenview) |Centro de controle local do Windows para projetos SAIPEN — descobre automaticamente`.saipen/`workspaces, visualiza o estado em tempo real e os resultados de conformidade, gerencia tickets e lança CLIs de IA. Um complemento, não a autoridade.|
| [SAIWORK](https://github.com/vacterro/saiwork) |Fork downstream do CodeNomad que integra o SAIPEN: injeta`BOOT.md`/`STYLE.md`nas inicializações do OpenCode, expõe atalhos do SAIPEN e visualizações do estado do projeto, e adiciona uma fila de prompts persistente.|
| [FastPrompter](https://github.com/vacterro/fastprompter) |Bloco de notas portátil do Windows e gerenciador de snippets que detecta automaticamente`.saipen/`pastas e adiciona um visualizador de STATE/BOARD/LOG somente leitura.|

## Documentação

|Document|O que é|
|---|---|
| [SPEC.md](SPEC.md) |Arquitetura formal, objetivos de design, teste de litmus|
| [CORE.md](saipen/CORE.md) |Continuação normativa, máquina de estado e contrato de comando|
| [MAINTENANCE.md](saipen/MAINTENANCE.md) |Manutenção autônoma e Modo de Objetivo|
| [CONFORMANCE.md](saipen/CONFORMANCE.md) |Requisitos executáveis/behaviorais e regras do validador|
| [GUIDE.md](GUIDE.md) |Tutorial humano|
| [RFC.md](saipen/RFC.md) |Redirecionamento de compatibilidade para os documentos normativos divididos|
| [STYLE.md](saipen/STYLE.md) |Estilo e voz de comunicação do agente|
| [UI.md](saipen/UI.md) |Diretrizes de design da interface do Vintage Golden UI|
|Brochura|Brochura de apresentação —[EN](BROCHURE_EN.md) / [RU](BROCHURE_RU.md) / [ET](BROCHURE_ET.md) / [DED](BROCHURE_DED.md) / [JA](BROCHURE_JA.md) |

<details>
<summary><b>All 33 translated guides</b></summary>

🇷🇺 [Русский](guides/GUIDE_RU.md) · 🇺🇸 [Inglês](guides/GUIDE_EN.md) · 🇪🇪 [Estoniano](guides/GUIDE_EE.md) · 🇯🇵 [日本語](guides/GUIDE_JA.md) · 👴 [Версия Деда](guides/GUIDE_DED.md)

🇺🇦 [Українська](guides/GUIDE_UK.md) · 🇩🇪 [Alemão](guides/GUIDE_DE.md) · 🇫🇷 [Francês](guides/GUIDE_FR.md) · 🇪🇸 [Espanhol](guides/GUIDE_ES.md) · 🇮🇹 [Italiano](guides/GUIDE_IT.md)

🇵🇹 [Português](guides/GUIDE_PT.md) · 🇳🇱 [Holandês](guides/GUIDE_NL.md) · 🇵🇱 [Polonês](guides/GUIDE_PL.md) · 🇸🇪 [Sueco](guides/GUIDE_SV.md) · 🇩🇰 [Dinamarquês](guides/GUIDE_DA.md)

🇫🇮 [Finlandês](guides/GUIDE_FI.md) · 🇳🇴 [Norueguês](guides/GUIDE_NO.md) · 🇨🇳 [中文](guides/GUIDE_ZH.md) · 🇰🇷 [한국어](guides/GUIDE_KO.md) · 🇹🇭 [ไทย](guides/GUIDE_TH.md)

🇻🇳 [Vietnamita](guides/GUIDE_VI.md) · 🇸🇦 [العربية](guides/GUIDE_AR.md) · 🇮🇱 [עברית](guides/GUIDE_HE.md) · 🇹🇷 [Turco](guides/GUIDE_TR.md) · 🇮🇳 [हिन्दी](guides/GUIDE_HI.md)

🇮🇩 [Indonésio](guides/GUIDE_ID.md) · 🇬🇷 [Ελληνικά](guides/GUIDE_EL.md) · 🇨🇿 [Tcheco](guides/GUIDE_CS.md) · 🇷🇴 [Romeno](guides/GUIDE_RO.md) · 🇭🇺 [Húngaro](guides/GUIDE_HU.md)

🇧🇬 [Български](guides/GUIDE_BG.md) · 🇸🇰 [Eslovaco](guides/GUIDE_SK.md) · 🇭🇷 [Croata](guides/GUIDE_HR.md)

</details>

## Notas de configuração

**Idioma de resposta.**O agente responde em**estoniano**por padrão — isso é uma
configuração, não uma exigência do protocolo, e nada mais sobre SAIPEN é em estoniano.
O protocolo, o código, as commits e todos os documentos permanecem em inglês em cada
valor. Mude isso em um único lugar: a`reply_language:`linha no topo do
[`saipen/STYLE.md`](saipen/STYLE.md). `et`estoniano,`en`inglês,`ru`russo,
`auto`escolhe a partir da mensagem que você enviou.

**Adaptadores.**Plataforma não coberta pelo injetor(DeepSeek, Qwen, standalone
OpenAI, etc.)? Notas por plataforma vivas em`extensions/adapters/`.

## Capturas de tela

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
