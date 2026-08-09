<p align="center">
  <img src="assets/SAIPEN_design1.png" alt="SAIPEN Guide Title" width="800"/>
</p>

# Guia SAIPEN (Português)

SAIPEN é um caderno de memória persistente na pasta .saipen/ para agentes de IA.

AI agents have one fatal flaw: they forget. Close the window and everything they learned about your project is gone — what you were building, what failed, which idea died on Tuesday. Every morning you brief a brilliant stranger from scratch. SAIPEN is the fix: a persistent notebook in the .saipen/ folder. The agent reads STATE and BOARD on startup, sees exactly where it left off, and gets back to work without a single repeated word.

**Atalhos rápidos:** `cc` continua o contexto do projeto até a convergência (retoma um objetivo ativo, se houver um definido), `sss` informa o estado sem tocar no código e `ss` salva um ponto de verificação e para. [Veja o mapa completo de 15 teclas](../saipen/RFC.md#110-command-surface). Os gêmeos cirílicos também funcionam: `сс`, `ссс`, `аа`, `ее`, `еее`, `рр`.

## Início Rápido

1. **Instale uma vez por máquina:**
```bash
git clone https://github.com/vacterro/saipen
cd saipen
powershell -ExecutionPolicy Bypass -File .\bootstrap\inject.ps1     # Windows
bash bootstrap/inject.sh                                            # macOS / Linux
```

2. **Iniciar projeto:**
> `saipen set`

3. **Trabalhar:**
> `saipen`

## Comandos

| Comando | Ação |
|---|---|
| `saipen set` | Inicializar pasta de memória `.saipen/` |
| `saipen continue` | Retomar trabalho das notas |
| `saipen stop` | Salvar progresso e parar |
| `saipen status` | Ler quadro e estado |
| `saipen goal <text>` | Mudar para novo objetivo |
| `saipen clean` | Limpeza profunda do repositório |
| `saipen translate` | Construção isolada de tradução em 32 idiomas |
| `saipen markhunt` | Auditoria profunda e sem limite -- apenas registra achados |
| `saipen prepare` | Empacota o trabalho para entrega ao próximo agente |
| `saipen ship` | Disparar fluxo de lançamento |

## Bom saber
- Alterações não commitadas ao voltar ao projeto? Normal -- o SAIPEN só faz commit no `ship`, não a cada passo. O agente verifica primeiro de quem são essas alterações antes de tocar em qualquer coisa.
- Quer que ele lembre uma decisão de arquitetura real? Coloque em `.saipen/KNOWLEDGE/`, como um arquivo `decisions.md` ou arquivos numerados `ADR-001.md`.
- Sem git ou shell nesta máquina? O agente diz isso claramente (`mode`, `WAIT: <category> -- <pergunta>`) em vez de adivinhar (a categoria é uma das sete: `manual-verify, destructive-op, first-publish, user brake, blocked, safety valve, init`; indica que tipo de resposta desbloqueia a situação)
- Quer uma rede de segurança? `python <clone-saipen>/tools/install_hook.py` instala uma verificação pré-commit.

---

**Full command list / complete command reference:** [RFC § 1.10](../saipen/RFC.md#110-command-surface) — the authoritative list of every `saipen` command.


