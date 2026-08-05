<p align="center">
  <img src="assets/SAIPEN_TEXT1.png" alt="SAIPEN Logo"/>
  <br>
  <img src="assets/__SAIPEN_Alpha.png" alt="SAIPEN Sticker" width="200"/>
</p>

# SAIPEN

**Protocolo de continuação para agentes de código AI.** Memória persistente de projeto em
markdown simples, para que um agente frio sem histórico de chat execute `/saipen continue`
e retome o trabalho em menos de um minuto -- sem re-instruções, qualquer fornecedor, qualquer dia.

**Um comando. Zero amnésia.**

**Atalhos rápidos:** `cc` continua uma execução ativa de Goal Mode, `sss` informa o estado sem tocar no código e `ss` salva um ponto de verificação e para. [Veja o mapa completo de 14 teclas](saipen/RFC.md#110-command-surface). Os gêmeos cirílicos também funcionam: `сс`, `ссс`, `аа`, `ее`, `еее`, `рр`.

**Idioma de resposta.** O agente responde por padrão **em estoniano** — é uma configuração, não uma excentricidade, e nada mais no SAIPEN está em estoniano. Muda-se em um único lugar: a linha `reply_language:` no topo de [`saipen/STYLE.md`](saipen/STYLE.md). `et` estoniano, `en` inglês, `ru` russo, `auto` escolhe pelo idioma da sua mensagem. O protocolo, o código, os commits e todos os documentos permanecem em inglês em qualquer valor.

**v7.192.0** | [Espec](SPEC.md) | [Guia](GUIDE.md) | [RFC](saipen/RFC.md) | [Estilo](saipen/STYLE.md) | [UI](saipen/UI.md) | [Conformidade](saipen/CONFORMANCE.md) | markdown simples | zero deps | MIT

```text
Usuário ->  /saipen continue
Agente  ->  lê STATE ("O que faço agora?")
Agente  ->  lê BOARD ("Qual tarefa estou pegando?")
Agente  ->  lê next_action (executa o comando)
Agente  ->  Trabalha.
```

### Estado do Projeto > Memória do Modelo
A memória vive no projeto, não na cabeça do modelo. `Projeto -> Memória -> LLM` torna-se `Projeto -> Estado SAIPEN -> LLM`.

### Lógica Principal e Garantias do Protocolo
- **Máquina de Estado Principal**: `INIT → PLAN → SCOUT → BUILD → VERIFY → REVIEW → SHIP → DONE | BLOCKED`
- **Autonomia Sem Prompt**: Sem tarefas pendentes? Transiciona automaticamente no ciclo `HUNT` (busca bugs) → `ADD` (evolui recursos) → `HUNT`. Zero perguntas feitas.
- **Gatilhos Explícitos**: `/saipen clean` (limpeza do repositório), `/saipen translate` (fábrica isolada `.saipen/saitranslate/`), `/saipen markhunt` (auditoria completa sem correções, apenas registros), `/saipen prepare` (empacota trabalho para transferência), `/saipen validate` (verificação de conformidade), `/saipen goal` (execução autônoma em ondas). Meta/controle: `/saipen status` (relatório de leitura), `/saipen stop` (ponto de verificação e pausa). Lista completa: RFC.md § 1.10.
- **Confiabilidade Estrita**: Processamento em lote de entradas (tickets cirúrgicos 1 a 1), adoção de árvore com alterações não salvas (nunca apaga trabalho não commitado), redação de segredos (`sk-***`).
- **Em desenvolvimento -- saicrew**: uma camada bônus opcional (`extensions/subs/`, sem alterações no Core) para executar uma equipe multiagente -- um Core escritor mais trabalhadores somente leitura `saihunt`/`saipython`, que reportam via seu próprio `OUTBOX.md`. Em teste ativo ao vivo no momento, ainda não verificado de ponta a ponta -- veja `extensions/subs/crew.md`.

## Projetos Movidos a SAIPEN
- ⚡ **[FastPrompter](https://github.com/vacterro/fastprompter)** — Ferramenta de gerenciamento de prompts de alto desempenho integrada nativamente com o protocolo de memória SAIPEN.

## Duas Camadas

| Camada | Obrigatório | Propósito |
|---|---|---|
| **Core** | ✅ | Continuar o trabalho com segurança |
| **Manutenção** | Sobre a Core | Evoluir o software sem tarefas explícitas |

**Evolução Automatizada.** Sem tarefas pendentes, digite `/saipen`: `HUNT` audita bugs, código morto, testes falhando. Limpo? `ADD` constrói a próxima capacidade ausente óbvia, verifica e audita novamente. Produto maduro -> para de forma suave.

**Modo GOAL.** `/saipen goal <o que você quer>` reorienta o quadro (tickets antigos são rebaixados, nunca deletados) e avança com o novo objetivo -- sem perguntas "devo continuar?" entre tickets, VERIFY/REVIEW nunca são ignorados. SHIP faz push automático para um repositório remoto existente; um repositório novinho ainda pergunta uma vez. Enviar (SHIP) o objetivo não é o ponto final -- ele passa diretamente para a manutenção autônoma HUNT/ADD até que o produto esteja maduro, bloqueado, ou a execução atinja seu limite (3 ondas / 20 tickets, então faz o checkpoint e reporta).

## Início Rápido

**1. Instale uma vez por máquina** -- ensina Claude Code, Gemini, OpenCode, Aider, Antigravity, Codex e qualquer leitor generico de ~/.agents/skills (FreeBuff, etc.):
```bash
git clone https://github.com/vacterro/saipen
cd saipen
powershell -ExecutionPolicy Bypass -File .\bootstrap\inject.ps1     # Windows
bash bootstrap/inject.sh                                            # macOS / Linux
```

**2. Inicie um projeto** -- abra um agente na sua pasta e digite:
> `saipen set`

Sem instalação? Cole uma linha em qualquer agente:
> Read <clone>/saipen/RFC.md + <clone>/saipen/STYLE.md and follow them.

Plataforma não listada acima (DeepSeek, Qwen, OpenAI autônomo, etc.)?
Notas específicas por plataforma estão em `extensions/adapters/`.

## Links de Documentação e Especificação
- **[SPEC.md](SPEC.md)** -- arquitetura formal, objetivos de design, teste decisivo.
- **[RFC.md](saipen/RFC.md)** -- especificação normativa executada por agentes.
- **[GUIDE.md](GUIDE.md)** -- tutorial para humanos e guias simplificados (ELI5):
  - 🇷🇺 [Русский](guides/GUIDE_RU.md) | 🇺🇸 [English](guides/GUIDE_EN.md) | 🇪🇪 [Eesti](guides/GUIDE_EE.md) | 🇯🇵 [日本語](guides/GUIDE_JA.md) | 👴 [Версия Деда](guides/GUIDE_DED.md)
  - 🇺🇦 [Українська](guides/GUIDE_UK.md) | 🇩🇪 [Deutsch](guides/GUIDE_DE.md) | 🇫🇷 [Français](guides/GUIDE_FR.md) | 🇪🇸 [Español](guides/GUIDE_ES.md) | 🇮🇹 [Italiano](guides/GUIDE_IT.md)
  - 🇵🇹 [Português](guides/GUIDE_PT.md) | 🇳🇱 [Nederlands](guides/GUIDE_NL.md) | 🇵🇱 [Polski](guides/GUIDE_PL.md) | 🇸🇪 [Svenska](guides/GUIDE_SV.md) | 🇩🇰 [Dansk](guides/GUIDE_DA.md)
  - 🇫🇮 [Suomi](guides/GUIDE_FI.md) | 🇳🇴 [Norsk](guides/GUIDE_NO.md) | 🇨🇳 [中文](guides/GUIDE_ZH.md) | 🇰🇷 [한국어](guides/GUIDE_KO.md) | 🇹🇭 [ไทย](guides/GUIDE_TH.md) | 🇻🇳 [Tiếng Việt](guides/GUIDE_VI.md) | 🇸🇦 [العربية](guides/GUIDE_AR.md) | 🇮🇱 [עברית](guides/GUIDE_HE.md)
  - 🇹🇷 [Türkçe](guides/GUIDE_TR.md) | 🇮🇳 [हिन्दी](guides/GUIDE_HI.md) | 🇮🇩 [Bahasa Indonesia](guides/GUIDE_ID.md) | 🇬🇷 [Ελληνικά](guides/GUIDE_EL.md) | 🇨🇿 [Čeština](guides/GUIDE_CS.md) | 🇷🇴 [Română](guides/GUIDE_RO.md)
  - 🇭🇺 [Magyar](guides/GUIDE_HU.md) | 🇧🇬 [Български](guides/GUIDE_BG.md) | 🇸🇰 [Slovenčina](guides/GUIDE_SK.md) | 🇭🇷 [Hrvatski](guides/GUIDE_HR.md)
- **[STYLE.md](saipen/STYLE.md)** -- estilo de comunicação do agente e definição de voz.
- **[UI.md](saipen/UI.md)** -- diretrizes de design de UI Win95 Vintage Golden.
- **[CONFORMANCE.md](saipen/CONFORMANCE.md)** -- cenários de testes comportamentais e regras de validação.

<p align="center">
  <img src="assets/SAIPEN_design2_alpha.png" alt="SAIPEN Stamp" width="120"/>
</p>

## ## Capturas de tela

<details>
<summary>Clique para expandir</summary>

<img src="assets/screenshot-freebuff.png" alt="Instruções do agente FreeBuff" width="600"/>

<img src="assets/screenshot-nomadcode1.png" alt="saipen set no nomadcode" width="600"/>

<img src="assets/screenshot-20260801-003853.png" alt="Captura de tela saipen 2026-08-01" width="600"/>

</details>

<!-- source-digest: README.md sha256:951d8044313a6456 -->
