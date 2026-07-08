# Proposta de refactor — estrutura do repositório em 4 pastas — v0.1

**Status:** proposta (2026-07-08). Não executada — precisa de aval (mexe em import paths e no CLAUDE.md).
**Motivação:** hoje as ferramentas estão espalhadas (`gerador/`, `loader/`, `conector/`, `sql/`, `tests/`, `beta/`) e o pipeline de ingestão vai nascer (spec `5_spec_pipeline_airflow_v0_1.md`). Consolidar em 4 pastas de responsabilidade única antes de o Airflow entrar evita retrabalho.

---

## 1. As 4 pastas

| Pasta | Responsabilidade | O que entra |
|---|---|---|
| `geradores/` | **Fabricar dado sintético** (massa + SERPRO simulada) | `gen_massa.py`, `gerador_eventos.py`, `trajetorias.py`, `emissor_siape.py`, os `*.yaml` (config, semente, decreto), `out/` |
| `pipeline/` | **Ingestão orquestrada** (o DAG e tudo que persiste) | `airflow/dags/`, conectores, loaders, steps puros valida/classifica, testes de replay/round-trip |
| `banco/` | **Estado e DDL** | `3_schema_mdm.sql`, `seed_dominios.sql`, `roteiro_retratacao_adr009.sql` |
| `docs/` | **Documentação** | ADRs, catálogo, specs, handoffs (inalterada) |

`beta/` (smoke test histórico) → `geradores/beta/` ou arquivar; não é pipeline atual.

## 2. Árvore-alvo

```
MDM_RH/
├── geradores/
│   ├── gen_massa.py  gerador_eventos.py  trajetorias.py
│   ├── emissor_siape.py            # SERPRO simulada (Card 3)
│   ├── config.yaml  semente_trajetorias_v1.yaml  decreto_animalizado_v1.yaml
│   └── out/                        # gitignored (massa + XML sintético)
├── pipeline/
│   ├── contrato/
│   │   └── siape_envelope.py       # contrato de fronteira (compartilhado)
│   ├── conectores/
│   │   └── conector_siape.py       # Card 6 (parse A/B, quarentena, carimbo)
│   ├── loaders/
│   │   ├── carrega_foto.py         # UPSERT servidor (valida/classifica/upsert puros)
│   │   └── carrega_evento.py       # NOVO: fn_particao_carga + COPY (hoje é load_eventos.sql)
│   ├── airflow/
│   │   └── dags/ingestao_siape.py  # NOVO: o DAG
│   └── tests/
│       ├── valida_replay_intervalo.py
│       └── valida_roundtrip_siape.py
├── banco/
│   ├── 3_schema_mdm.sql  seed_dominios.sql  roteiro_retratacao_adr009.sql
├── docs/  (inalterada)
├── CLAUDE.md  README.md
```

## 3. Decisão pendente — onde mora o contrato `siape_envelope.py`

É importado pelo **emissor** (geradores) **e** pelo **conector** (pipeline). Opções:
1. **`pipeline/contrato/`** (recomendado) — o pipeline é dono do contrato de ingestão; o gerador importa cross-pasta. Fronteira conceitual correta (a ingestão define o shape que a fonte deve entregar).
2. `geradores/` — o emissor "produz o shape", mas amarra o pipeline ao gerador (ruim: pipeline não deveria depender de geradores).
3. Pacote `comum/` de 5ª pasta — evita a discussão mas fura a regra das 4 pastas.

Proposta: **opção 1**.

## 4. Impactos técnicos (o que quebra e precisa ajustar)

- **Import paths / `sys.path`:** `conector_siape.py` faz `sys.path.insert(... '../gerador')` para achar `siape_envelope`; muda para o novo local. `valida_roundtrip_siape.py` insere `gerador`+`conector` no path — reapontar. Idealmente virar **pacote** (`__init__.py`) e imports relativos, matando os `sys.path.insert`.
- **`trajetorias.carrega_env()`** procura `../loader/.env` — reapontar para o novo local do `.env`.
- **Caminhos de `out/`:** defaults `gerador/out` viram `geradores/out` (argumentos `--out`, e o `conector` que lê de lá).
- **`load_eventos.sql`:** hoje é gerado em `out/` pelo `gerador_eventos.py`; extrair a lógica de carga para `pipeline/loaders/carrega_evento.py` (ou manter o SQL gerado, mas chamado pelo DAG).
- **CLAUDE.md:** a seção "Repository layout" e os "Common commands" precisam refletir as 4 pastas.
- **`.gitignore`:** `gerador/out/` → `geradores/out/`.

## 5. Plano de migração (git-friendly, um passo por commit)

1. `git mv` das pastas/arquivos para a árvore-alvo (preserva histórico).
2. Converter `pipeline/` em pacote (`__init__.py`), trocar `sys.path.insert` por imports de pacote.
3. Reapontar caminhos (`.env`, `out/`, defaults de CLI).
4. Rodar as duas suítes de teste (`valida_replay_intervalo`, `valida_roundtrip_siape`) — devem passar idênticas.
5. Atualizar CLAUDE.md + `.gitignore`.
6. Commit único de refactor **sem mudança de comportamento** (diff = movimentação + paths), para revisar fácil.

## 6. Riscos

- Refactor amplo mexe em muitos paths → fazer **isolado** (sem misturar com feature), com os testes como rede.
- Power BI / GRANTs apontam para **objetos de banco**, não arquivos — o refactor de repo **não** os afeta (tranquilo).
- `emissor_siape` nos geradores + contrato no pipeline cria uma dependência geradores→pipeline; aceitável (fonte sintética conhece o contrato de ingestão), mas registrar para não inverter.
