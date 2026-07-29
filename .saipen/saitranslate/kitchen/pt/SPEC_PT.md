# Especificação SAIPEN

## Resumo
**Objetivo de Design #1: Um agente frio sem histórico de chat deve ser capaz de executar `/saipen continue` e retomar o trabalho produtivo dentro de um minuto, sem pedir ao usuário para repetir o contexto.**

SAIPEN garante que qualquer agente de IA compatível possa continuar com segurança qualquer projeto sem receber um novo briefing. É uma ABI (Application Binary Interface) para agentes de IA de engenharia — uma camada de compatibilidade que resolve o problema da amnésia. Não importa se você usa o Claude hoje, Gemini amanhã, e GPT depois de amanhã, todos operarão no mesmo estado do projeto sem exigir que você reformule o contexto.

### Filosofia Principal: Estado do Projeto > Memória do Modelo
A memória deve viver junto ao código, não dentro da cabeça de outro modelo. SAIPEN muda o paradigma de `Projeto -> Memória -> LLM` para `Projeto -> Estado SAIPEN -> LLM`. A memória pertence ao projeto.

Em sua essência, SAIPEN usa um protocolo de continuação portátil apoiado em arquivos para agentes LLM. As implementações PODEM variar. O contrato em disco DEVE permanecer estável. Tudo neste protocolo existe para servir ao Teste de Continuação.

SAIPEN é evolutivo, não criativo. Seu propósito é completar software, não reinventá-lo. ADD estende os padrões de design existentes, convenções da indústria, e simetria de features óbvias.

- **`STATE`**: Existe para responder *"O que eu faço agora mesmo?"*
- **`BOARD`**: Existe para responder *"Qual tarefa estou pegando?"*
- **`LOG`**: Existe para responder *"Por que chegamos a este ponto?"*
- **`KNOWLEDGE`**: Existe para responder *"Qual é a verdade duradoura deste projeto?"*
- **`next_action`**: O coração do SAIPEN. Responde *"Que comando exato eu executo neste exato segundo para retomar o trabalho?"*

## O Teste Decisivo SAIPEN

Qualquer mudança proposta ou nova ideia para o protocolo DEVE passar pelas três perguntas a seguir:
1. Isso torna a transição entre agentes mais confiável?
2. Isso torna o comportamento de modelos diferentes mais uniforme?
3. Isso reduz a probabilidade de perda de contexto?

Se a resposta for "não" para pelo menos duas destas perguntas, a ideia é rejeitada. SAIPEN prioriza disciplina, reprodutibilidade e confiabilidade sobre a novidade.

## Arquitetura

O protocolo é estritamente normativo. SAIPEN se divide conceitualmente em duas camadas: **Core** e **Maintenance**. 
- **A camada Core** garante uma continuação de tarefa segura e neutra em relação a fornecedores. 
- **A camada Maintenance** é um modelo autônomo de evolução de software construído sobre o Core.

Abaixo das duas camadas, SAIPEN separa três preocupações que nunca se misturam:
**correção e continuação** (Core -- `STATE`/`BOARD`/`LOG`/`KNOWLEDGE`, negociação de capacidade, checkpointing), **evolução autônoma** (Maintenance -- `HUNT`/`ADD`/`CLEAN`, totalmente funcional sob o padrão `saipen`/`saipen continue` padrão), e **rendimento** (Modo Goal, Subagentes -- ambos estritamente opcionais, §1.3/§2.4). Desative o Modo Goal: o protocolo não muda, um ticket de cada vez. Desative Subagentes: `HUNT` executa as mesmas seis categorias sequencialmente, o mesmo resultado. Use o Core sozinho, sem camada Maintenance nenhuma: ainda funciona -- um agente frio ainda retoma corretamente. Cada camada se constrói na subjacente sem que o reverso seja verdade; nada a montante depende da existência de uma funcionalidade a jusante.

```text
saipen/
  RFC.md                    especificação normativa (dividida em Core e Maintenance)
  CONFORMANCE.md             vetores de autoverificação + tabela de cobertura de cenário
  SKILL.md                  ponto de entrada fino para plataformas de leitura de habilidades
  STYLE.md                  vozes: chat, LOG.md, artefatos
  UI.md                     especificação de UI Wintage Golden (obrigatório para trabalhos de UI)
  BOOT.md                   ~kernel de inicialização a frio: o caminho rápido
                             que um `continue` básico precisa, antes de qualquer
                             um dos acima ser carregado
  phases/                   lógica estrita da máquina de estado -- 16 docs, um por
                             valor de enumeração da RFC § 1.6 (verificado
                             mecanicamente em ambos os sentidos por tools/validate.py)
    [Fases Core]
    init.md / plan.md / scout.md / build.md / verify.md / review.md / ship.md / done.md / blocked.md
    [Fases Maintenance]
    hunt.md / markhunt.md / add.md / clean.md / translate.md

    [Infrastructure]
    prepare.md              empacotar trabalho para entrega ao próximo agente
    validate.md             teste de conformidade

extensions/                 <- A CAMADA ADAPTATIVA
  adapters/                 pontes de instrução por modelo, para plataformas que
                             o injetor não autodetecta (README.md aponta para cá)
  schemas/                  state.schema.json é lido por máquina por tools/validate.py
                             (única fonte de verdade para a forma do STATE); os esquemas board/log
                             permanecem apenas como referência (veja schemas/README.md)
  templates/                código padrão fresco .saipen/
  security/                 EXEMPLO de hook para copiar para um projeto (RFC § 1.9, anexa-se ao VERIFY)
  performance/              EXEMPLO de hook para copiar para um projeto (RFC § 1.9, anexa-se ao REVIEW)
  subs/                     EXEMPLOS de subagentes de pesquisa somente leitura (RFC § 1.9) -- têm
                             STATE/BOARD/LOG próprios por subagente, achados só pela OUTBOX,
                             nunca um segundo caminho de escrita no projeto

bootstrap/                  <- INSTALAÇÃO/EXPORTAÇÃO/DESINSTALAÇÃO, uma máquina por vez
  inject.ps1 / .sh          instala o bloco SAIPEN + cópias de habilidades (Início Rápido no README)
  uninstall.ps1 / .sh       reverte a injeção -- remove os blocos + cópias de habilidades
  export.ps1 / .sh          arquiva a pasta .saipen/ de um projeto para backup
  saipen_crew.bat / .sh     abre o layout de crew de 3 janelas (bônus, extensions/subs/crew.md)

tools/                      <- VALIDADOR CANÔNICO & UTILITÁRIOS DO REPOSITÓRIO
  validate.py               validador de conformidade canônico (stdlib do Python, zero
                             instalações; valida o STATE contra state.schema.json
                             diretamente, além de fazer verificações de grafo que a dupla de shell não faz)
  install_hook.py           instala um hook pre-commit executando validate.py
  uninstall_hook.py         remove exatamente esse hook (restaura qualquer anterior)

tests/                      <- CAMADA DE CONFORMIDADE
  validate.ps1 / .sh        limite portátil congelado para hosts sem Python --
                             novas verificações chegam apenas em tools/validate.py
  scenarios/                estados simulados (recuperação de crash, conflitos de reivindicação, etc.)
```

## Negociação de Capacidade de Duas Vias
Os agentes não simplesmente declaram o que podem fazer; o protocolo exige o que é necessário.
O projeto define `requires: [filesystem, git, shell, python]` em seu estado. O agente cruza as informações com as capacidades do hospedeiro e se fixa num `mode` (ex., `full`, `read-only`).

## Registro de Eventos Baseado em Grafos
Os logs no SAIPEN não são strings lineares. Eles formam um grafo acíclico de decisões usando IDs de Evento (`E-001`). Isso permite ramificações complexas, fusões de agentes e trilhas de auditoria precisas.

## Registros de Decisão de Arquitetura (ADR)
Os logs de eventos temporários não abrigam conhecimento permanente. O SAIPEN determina que as decisões de arquitetura estruturais sejam persistidas como ADRs (ex., `KNOWLEDGE/ADR-001-use-sqlite.md`).

## Limites de Concorrência & Distribuição
SAIPEN garante a integridade do estado através de reivindicações baseadas em arquivos (`owner`, `claim_time`) e grafos sequenciais (`LOG.md`). No entanto, **SAIPEN é um protocolo de estado, não um algoritmo de consenso distribuído.**
- **Sistema de Arquivos Local/Compartilhado**: A resolução de conflitos depende de escritas atômicas ("o primeiro commit vence").
- **Ambientes em Rede/Distribuídos**: Se os agentes operam através de máquinas desconectadas sem sincronização de arquivos em tempo real, ocorrerão condições de corrida nas reivindicações em `BOARD.md`. Em configurações altamente distribuídas, o contrato do protocolo em disco do SAIPEN DEVE permanecer estável -- o próprio estado do projeto sofre mutações constantemente, através das próprias regras do SAIPEN (§ 1.5 checkpointing), nunca a forma do protocolo que essas regras seguem.


<p align="center">
  <img src="assets/SAIPEN_design2_alpha.png" alt="SAIPEN Stamp" width="120"/>
</p>
