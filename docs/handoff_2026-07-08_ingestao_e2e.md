# Handoff — Ingestão E2E de produção MDM-RH (o que falta) — 2026-07-08

**De:** sessão Claude Code (Cards 3+6) · **Para:** próxima sessão (Airflow + E2E)
**Objetivo declarado pelo usuário desde o início:** um **teste de ingestão E2E de produção** — dado sintético entrando pelo pipeline real (conectores → valida/classifica → persiste em `servidor`/`evento` → REFRESH → juiz), não um round-trip offline.

---

## 1. Leitura honesta do que aconteceu

**Feito hoje (Cards 3+6, commit `378f6fb` na `main`):**
- **Emissor** (`geradores`… hoje `gerador/emissor_siape.py`): `gerador_eventos.py --formato siape` serializa a massa no envelope SOAP (`consultaDadosFuncionais` + `consultaDadosAfastamentoHistorico` §4.21) + `--injeta-defeito`.
- **Conector** (`conector/conector_siape.py`): parseia o envelope → 14 colunas FOTO / eventos AFASTAMENTO carimbados (ADR-014), com quarentena (rejeito).
- **Contrato** (`gerador/siape_envelope.py`) + **round-trip offline** (`tests/valida_roundtrip_siape.py`): (a) `foto'==servidor.csv`; (b) `replay(eventos')==FOTO`. 1300 vínculos / 965 afastamentos, 0 divergências.

**NÃO feito (e é o objetivo):** a **ingestão E2E de produção**. O que existe prova o *envelope* (ida-e-volta em memória/CSV); **não** exercita o pipeline que **persiste** o dado no Postgres por um fluxo orquestrado. O conector para no CSV — de propósito, seguindo a convenção do repo (cada peça emite artefato; um loader/DAG persiste), mas o passo de ingestão **não existe como código**.

**O gap em uma frase:** falta o DAG que pega a saída dos conectores e a leva às tabelas, e falta rodá-lo fim-a-fim com dado sintético e validar pelo juiz do DB.

## 2. Backlog completo, sequenciado

### Passo 0 — Refactor do repo em 4 pastas (proposta `proposta_refactor_estrutura_v0_1.md`)
Fazer **antes** de o Airflow entrar, isolado, com os testes como rede. Pastas: `geradores/` · `pipeline/` · `banco/` · `docs/`. Decisão pendente: local do `siape_envelope.py` (recomendado `pipeline/contrato/`).

### Passo 1 — Loaders faltantes (a "fiação de persistência")
- **`carrega_evento.py`** (novo): recebe os eventos do conector B → `fn_particao_carga(id_carga)` + `\copy evento` (hoje essa lógica só existe embutida no `load_eventos.sql` gerado). Carimbo ADR-014 já vem do conector.
- **Reconciliação de colunas do conector A → `carrega_foto.py`**: o conector A emite 14 colunas SIAPE; o `servidor` tem mais colunas (nome, data_nascimento, origem_unidade, etc.). Decidir: (i) API real traz nome/nascimento em outras tags → mapear; (ii) colunas internas (`arquetipo`/`traj_salt`) não existem em produção → schema aceita NULL/derivar. **Ponto de modelagem, não trivial.**

### Passo 2 — DAG Airflow `ingestao_siape` (card DGP criado; spec `5_spec_pipeline_airflow_v0_1.md`)
`extrai → conecta_A/B → valida → classifica → persiste_{foto,evento} → refresh_mvs → valida_replay`. Reusa os steps puros do loader (ADR-006) e o parse dos conectores. Swap de fonte no `extrai`: `xml` (teste) | `api` (prod).

### Passo 3 — Teste E2E com dado sintético (**o objetivo**)
```
gen_massa + gerador_eventos              # massa sintética
gerador_eventos --formato siape          # SERPRO simulada emite os XML
airflow dags test ingestao_siape <data>  # fonte=xml, roda o pipeline inteiro
tests/valida_replay_intervalo.py         # 0 divergências no DB (juiz ADR-008)
```
Aceite: 0 aborts, `servidor`/`evento` populados a partir do XML dos conectores, replay=0, carga retratável por DETACH.

### Passo 4 — Go-live (produção real; NÃO bloqueia o E2E sintético)
- Acesso à API SIAPE Consultas + **rotina de REQUEST** (por CPF, janela `ano/mes` no §4.21, paginação) — hoje o conector só lê *response*.
- Auth JWT Bearer 2h (`/oauth2/jwt-token`, ICP-Brasil) + `x-cpf-usuario`.
- De-para fino de `DadosAfastamento` (WSDL `<xsd:types>` vazio) — 1º retorno real confirma.
- Extrator retroativo (sub-domínio vinculos) — outra fonte, fora daqui.

## 3. Peças reutilizáveis (o DAG orquestra, não reescreve)

- `carrega_foto.py`: `valida/classifica/upsert` **puros, testáveis sem DB** (ADR-006, "leitor agnóstico a fonte" — o conector É esse leitor).
- `conector_siape.parse_funcionais / parse_afastamento`: parse + rejeito prontos.
- `load_eventos.sql`: padrão `fn_particao_carga`+COPY+REFRESH (extrair p/ `carrega_evento.py`).
- `tests/valida_replay_intervalo.py`: o juiz E2E contra o DB (já existe).
- `roteiro_retratacao_adr009.sql`: DETACH de carga defeituosa.

## 4. Decisões pendentes (precisam de humano)

1. Local do `siape_envelope.py` no refactor.
2. Reconciliação FOTO: como preencher as colunas não-SIAPE do `servidor` na ingestão via API (nome/nascimento/origem).
3. Ordem: refactor antes ou depois do DAG? (Recomendo antes — o DAG já nasce no lugar certo.)

## 5. Entregue hoje (na `main`)

`gerador/siape_envelope.py` · `gerador/emissor_siape.py` · `conector/conector_siape.py` · `tests/valida_roundtrip_siape.py` · hook `--formato siape`/`--injeta-defeito` em `gerador_eventos.py`. Card de produto do Airflow criado no Todoist (projeto DGP). Specs: `5_spec_pipeline_airflow_v0_1.md`, `proposta_refactor_estrutura_v0_1.md`, este handoff.
