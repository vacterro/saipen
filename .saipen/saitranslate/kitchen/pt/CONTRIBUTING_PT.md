# Contribuindo com o SAIPEN

O SAIPEN é primariamente uma especificação, e uma implementação em segundo plano. A maioria das contribuições
são mudanças no `saipen/RFC.md`, em um arquivo `phases/*.md`, ou nas ferramentas de conformidade
em `tests/` -- não em código de aplicação.

## Antes de propor uma mudança

Execute o [Teste Decisivo SAIPEN](SPEC.md#the-saipen-litmus-test) contra a sua ideia:
1. Isso torna a transição entre agentes mais confiável?
2. Isso torna o comportamento de diferentes modelos mais uniforme?
3. Isso reduz a probabilidade de perda de contexto?

Se a resposta for "não" para pelo menos duas delas, isso está fora do escopo deste
protocolo, por mais útil que possa ser em outro lugar.

## Reportando uma lacuna

Abra uma issue descrevendo:
- em qual arquivo/seção a lacuna está (RFC.md, um documento de fase, um esquema, um teste)
- a evidência concreta (uma citação, um comando e sua saída, um cenário onde o
  comportamento atual quebra)
- o que você esperaria no lugar

Relatórios vagos ("isso parece estranho") são mais difíceis de agir do que uma
reprodução/`grep` específica. Veja o template de issue para relatórios de bugs sobre a forma que
isso deve tomar.

## Fazendo uma mudança

1. Leia `saipen/RFC.md` e o(s) arquivo(s) relevante(s) `phases/*.md` completamente antes
   de editar -- a maioria das lacunas aparentes já estão abordadas em outro lugar,
   ou deliberadamente limitadas a um certo escopo por uma razão documentada.
2. Verifique `CHANGELOG.md` e `.saipen/KNOWLEDGE/decisions.md` quanto a arte prévia.
   Não reabra silenciosamente uma decisão que já foi tomada e rejeitada --
   se você tiver novas evidências de que uma rejeição passada foi incorreta, diga expressamente
   na descrição do PR.
3. Toda mudança normativa (um MUST/MUST NOT/SHOULD) precisa de uma entrada no `CHANGELOG.md`
   e, onde prático, cobertura em `tests/validate.sh` +
   `tests/validate.ps1` (ambas as plataformas) ou uma fixture sob
   `tests/scenarios/`.
4. Execute o validador canônico antes de abrir um PR:
   ```bash
   python tools/validate.py
   ```
   Este é o que importa -- ele verifica `STATE.md` contra `extensions/schemas/state.schema.json`, percorre o grafo de eventos do `LOG.md` através de segmentos selados, e verifica o manifesto de tempo de execução e a fiação do injetor. `tests/validate.sh` / `validate.ps1` são o **piso portátil congelado** para hosts sem Python (eles dizem isso no topo de cada arquivo): menos verificações, mantidos apenas para que um host sem Python não fique sem nada. Execute-os também se sua alteração tocar em algum deles, mas nunca *em vez de* -- passar apenas no piso prova muito menos do que parece. O CI executa o validador canônico em todo push e PR, independentemente (`.github/workflows/validate.yml`).
5. Aumente o `VERSION` conforme o esquema em `phases/ship.md` (patch para esclarecimentos
   apenas de documentação, minor para novo comportamento normativo, major para quebras
   no contrato) e mantenha o badge de versão do `README.md` sincronizado --
   `tests/validate.sh`/`.ps1` verificam isso automaticamente quando executados de um
   clone deste repositório.

## Estilo

- Documentos de protocolo e fases: curtos, palavras-chave da RFC-2119 onde importam, sem
  enchimento. Veja `saipen/STYLE.md`.
- Tudo neste arquivo, mensagens de commit, comentários de código e o
  CHANGELOG: claros e profissionais. As vozes do próprio chat/LOG do projeto
  (`saipen/STYLE.md`) não se aplicam aos artefatos.

## O que está fora do escopo

- Transformar o SAIPEN em um sistema de consenso distribuído. Veja a
  seção Limites de Concorrência & Distribuição em `SPEC.md`.
- Gramática de marcadores parseáveis por máquina no LOG além do esqueleto existente.
  `LOG.md` permanece como prosa ao redor de uma forma fixa.
- Um comando `saipen doctor` ou semelhante redundante com `saipen validate` +
  `saipen status`.

Estes já foram propostos e avaliados antes; reabri-los precisa de
novas evidências, não apenas perguntar novamente.
