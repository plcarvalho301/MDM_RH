# Spec base — Pipeline de ingestão MDM-RH no Airflow — v0.1

**Status:** rascunho de trabalho (2026-07-08). Deriva do corpus existente; não reabre ADR fechada.
**Âncoras:** ADR-006 (classifica por registro), ADR-008 (replay-juiz), ADR-009 (retratação por DETACH), ADR-012 (vitrine), ADR-014 (carimbo do afastamento). Código: `loader/carrega_foto.py` (valida/classifica/upsert puros), `gerador/out/load_eventos.sql` (`fn_particao_carga`+COPY+REFRESH), `conector/conector_siape.py` (parse A/B), `tests/valida_replay_intervalo.py` (juiz contra o DB), `sql/roteiro_retratacao_adr009.sql`.

---

## 1. Por que existe

O corpus sempre pressupôs um **DAG de ingestão** (Airflow, ciclo D-1) — a âncora `3_dag_ingestao.mermaid` é citada em `schema`/`loader`, mas o DAG **nunca foi materializado como código**. Persistência hoje = scripts loaders rodados à mão (`carrega_foto.py`, `load_eventos.sql`), que são os passos do DAG **desembrulhados**. Esta spec os re-embrulha num DAG executável e observável, e define o **teste E2E de ingestão de produção** com dado sintético.

**Princípio-chave já pago pelo corpus:** `carrega_foto.py` foi escrito como **leitor agnóstico a fonte (ADR-006)** — a metade `valida/classifica/upsert` é função pura, testável sem DB, e o cabeçalho já prevê "trocar por leitor SOAP depois é outro arquivo". Os conectores de hoje (Cards 3+6) **são** esse leitor. O DAG só orquestra peças que já existem.

## 2. Topologia do DAG `ingestao_siape`

```
extrai ──> conecta_A ──> valida_A ──> classifica_A ──> persiste_foto ─┐
      └──> conecta_B ──> valida_B ──> classifica_B ──> persiste_evento ┤
                                                                        ├─> refresh_mvs ──> valida_replay
                                                        rejeitos ───────┘   (CONCURRENTLY)     (juiz ADR-008)
```

Duas raias paralelas (FOTO / EVENTO — os dois eixos ortogonais, ADR-006), barreira antes do `refresh_mvs`, e um juiz final. `rejeitos` de qualquer tarefa vão para a quarentena (tabela `rejeito`, carimbada com `id_carga`) **sem abortar** a carga.

## 3. Contrato de cada tarefa

| Tarefa | Entrada | Saída | Reusa |
|---|---|---|---|
| **extrai** | fonte (ver §4) | `siape_funcionais.xml`, `siape_afastamento.xml` (ou stream) | — |
| **conecta_A** | XML funcionais | linhas FOTO (14 col) + rejeitos | `conector_siape.parse_funcionais` |
| **conecta_B** | XML §4.21 | eventos AFASTAMENTO carimbados (ADR-014) + rejeitos | `conector_siape.parse_afastamento` |
| **valida_A/B** | linhas/eventos | idem, defeituosos → `rejeito` | metade `valida` de `carrega_foto.py` |
| **classifica_A/B** | idem | destino {FOTO\|EVENTO\|rejeito} por registro (ADR-006) | metade `classifica` de `carrega_foto.py` |
| **persiste_foto** | linhas FOTO | UPSERT em `servidor` (por `matricula_funcional`) | `carrega_foto.py` (upsert) |
| **persiste_evento** | eventos | `fn_particao_carga(id_carga)` + `\copy evento` | lógica do `load_eventos.sql` |
| **refresh_mvs** | — | REFRESH das 4 MVs de exposição, CONCURRENTLY | `load_eventos.sql` (bloco final) |
| **valida_replay** | DB | 0 divergências replay-vs-FOTO, senão falha o run | `tests/valida_replay_intervalo.py` |

## 4. Swap de fonte (teste × produção) — o único ponto que muda

A tarefa **extrai** é a única com dois modos; **tudo a jusante é idêntico** (é o valor da tacada):

- **Teste E2E (dado sintético):** `extrai` lê o XML produzido por `gerador_eventos.py --formato siape` — o emissor faz de **SERPRO simulada**. Roda sem API, sem auth.
- **Produção (go-live):** `extrai` chama a API SIAPE Consultas (por CPF, com janela `anoInicial/anoFinal` no §4.21), autentica (JWT/ICP-Brasil), pagina. O XML de resposta entra no **mesmo** `conecta_*`.

Parametrizado por `Variable`/`Param` do Airflow: `fonte = xml | api`.

## 5. Idempotência, id_carga e retratação (ADR-009)

- Cada **run** do DAG gera um `id_carga` (uuid) — entra no envelope de todo evento e no `rejeito`. A FOTO (`servidor`) **não** ganha `id_carga` (sobrescreve em D-1).
- Re-executar um run com o mesmo `id_carga` é idempotente para o EVENTO (partição já existe → skip/replace controlado); a FOTO é UPSERT (idempotente por natureza).
- **Carga defeituosa → `DETACH PARTITION`** por `id_carga` (nunca DELETE) — runbook `sql/roteiro_retratacao_adr009.sql`, com `ledger_delecao` fora das partições.

## 6. Observabilidade e quarentena

- `rejeito` (tabela) recebe toda linha defeituosa com motivo + `id_carga` (rastreio simétrico). O DAG **não aborta** por rejeito — degradação graciosa (mesma semântica já provada no conector, defeitos §C: data mal-formada, tag ausente, cpf mascarado, alfanum coagido).
- Métricas por run: nº lido, nº persistido (FOTO/EVENTO), nº rejeitado, divergências do replay. Falha o run só se `valida_replay` divergir.

## 7. Config / conexões

- Conexão Postgres via `.env`/Airflow Connection (`PGHOST/PGPORT/PGDATABASE/PGUSER/PGPASSWORD`), como o loader já lê.
- Domínios semeados **antes** (`schema + seed_dominios`) — o `valida/classifica` lê `dom_*`.
- Prod adicional: segredo JWT, cert ICP-Brasil, `x-cpf-usuario` — Airflow Connections/Secrets (fora do teste).

## 8. Modo de teste E2E com dado sintético (o objetivo)

```
gen_massa + gerador_eventos           # massa sintética (FOTO + eventos)
gerador_eventos --formato siape       # SERPRO simulada: emite os XML
airflow dags test ingestao_siape <d>  # fonte=xml → conecta → valida → persiste → refresh → replay
tests/valida_replay_intervalo.py      # confirmação externa: 0 divergências
```
Aceite: run 0-abort, `servidor`/`evento` populados **a partir do XML dos conectores**, replay = 0, carga retratável por DETACH.

## 9. Fora de escopo (v1) / pendências

- **Extract de produção real** (API/auth/paginação) — go-live; não bloqueia o E2E sintético.
- **Extrator retroativo** (sub-domínio vinculos) — outra fonte, fora daqui.
- **De-para fino de `DadosAfastamento`** (WSDL `<xsd:types>` vazio) — 1º retorno real confirma.

## 10. Estrutura-alvo (pós-refactor, ver proposta separada)

DAG e tarefas vivem em `pipeline/airflow/dags/` + `pipeline/` (conectores, loaders, steps puros). O emissor SIAPE (`emissor_siape.py`) fica com os geradores (é fonte sintética). O contrato `siape_envelope.py` é compartilhado (decisão de local na proposta de refactor).
