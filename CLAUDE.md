# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

MDM-RH: a golden-record HR event store for a fictional federal agency ("Reino Animal" universe). It reconciles two data natures — **FOTO** (current-state snapshot) and **EVENTO** (append-only historical series) — into read-only surfaces (views/materialized views) for Power BI. Everything (schema, generator, docs) is written in Portuguese (pt-BR); keep new code/docs/comments in Portuguese to match the existing corpus.

The project is driven by a documented set of Architecture Decision Records (ADRs) — do not casually contradict a closed, numbered ADR without the user explicitly reopening it.

## Core model — read before touching schema or generators

- **FOTO** = table `servidor`, 1 row per active vínculo (employment record), **UPSERT by `matricula_funcional`** (overwrites).
- **EVENTO** = table `evento`, partitioned by `id_carga` (LIST partitioning, one partition per load/carga), **INSERT-only, never overwritten**. This is what the "replay" reconstructs FOTO from.
- The FOTO/EVENTO split happens **in the pipeline, per record** (`extrai → valida → classifica → {atualiza FOTO | registra EVENTO | rejeita}`), not per source (ADR-006).
- Sub-domains (`cod_sub_dominio`): `cadastro`, `vinculos`, `intercorrencias`, `compensacao`, `jornada` (+ `desempenho`/`capacidades` external). `vinculos` and `intercorrencias` are state machines (`ATIVO`, `CEDIDO`, `DISPONIBILIDADE`, `INATIVO`, `DESLIGADO`, `TRANSFERIDO`); the rest are purely additive series.
- Intercorrências (afastamento/cessão) are **intervals**, not paired transition events: duration lives in the payload (`data_inicio`/`data_fim`); a still-open interval is closed by emitting a **second immutable record with the same key**, and the projection coalesces on most-recent `data_carga` (ADR-008). There is no "return" event — an interval just expires by date.
- Retraction of bad data is by **whole-load `DETACH PARTITION`** on `id_carga`, never row-level `DELETE` (ADR-009). Any new projection/MV must always be re-derivable from raw `evento` — never cache an effect without a load trail.
- Exposure objects are one-per-**cut boundary**, never one-per-dashboard, and dashboards never read `servidor`/`evento` directly (ADR-007). On top of those, a further "vitrine" (showcase) view layer exists per-dashboard-surface (`vw_painel_<superficie>`) that pre-computes labels/colors/phrases/percentages so Power BI does zero DAX/relationships/Power Query (ADR-012).
- Read `docs/1_adr_mdm.md` (ADR-001..012 closed, Section 2 open decisions) before making any modeling call — it documents *why*, and the catalog (`docs/3_catalogo_eventos_v1.yaml`) documents the current *what* (schema for event payloads, changes often).

## Repository layout

The repo is organized in 4 single-responsibility top-level folders — `geradores/` (make synthetic data), `pipeline/` (orchestrated ingestion), `banco/` (state & DDL), `docs/` — plus `geradores/` and every dir under `pipeline/` are Python **packages** (`__init__.py`). Scripts run as modules from the repo root (`python -m geradores.gen_massa`, `python -m pipeline.tests.valida_replay_intervalo`) — that puts the repo root on `sys.path`, so cross-package imports (`from pipeline.contrato import siape_envelope`) resolve with zero `sys.path` hacks. See `docs/proposta_refactor_estrutura_v0_1.md`.

```
geradores/                       # FABRICATE synthetic data (massa + simulated SERPRO)
  gen_massa.py        # generates FOTO (archetype-first): servidor.csv + pessoa.csv + unit/function seeds
  gerador_eventos.py  # re-runs the SAME per-vínculo trajectory and emits the EVENTO series
  trajetorias.py      # single trajectory engine, shared by both generators (rng keyed by seed:matricula:traj_salt)
  emissor_siape.py    # simulated SERPRO (Card 3): serializes the massa into the SOAP envelope
  semente_trajetorias_v1.yaml  # the 14 designer archetypes — the heart of the generation logic
  decreto_animalizado_v1.yaml  # org structure "decree" (ADR-013): units + FCE quadro, versioned by (numero_decreto, data_vigencia); base vigência drives the massa
  config.yaml          # tunable calibration + seed (never hardcode volumetrics elsewhere)
  out/                 # gitignored (massa + synthetic XML)
pipeline/                        # ORCHESTRATED ingestion (the DAG and everything that persists)
  contrato/
    siape_envelope.py  # boundary contract, shared by emissor (geradores) and conector (pipeline)
  conectores/
    conector_siape.py  # Card 6: parse SOAP envelope A/B -> FOTO rows / AFASTAMENTO events (quarantine, ADR-014 stamp)
  loaders/
    carrega_foto.py    # servidor.csv -> `servidor` table (UPSERT, reject-quarantine path)
    .env.example       # credential template (.env itself is gitignored)
  tests/
    valida_replay_intervalo.py   # proves event replay re-derives FOTO against the real Postgres DB
    valida_roundtrip_siape.py    # emissor->conector round-trip (offline, no DB)
banco/                           # STATE & DDL
  3_schema_mdm.sql              # from-scratch DDL, source of truth (see version header at top of file)
  seed_dominios.sql             # domain/lookup table seeds — must run before any data load
  roteiro_retratacao_adr009.sql # operational retraction runbook (partition DETACH)
docs/
  1_adr_mdm.md                 # ADRs — architecture "why", closed sections are immutable
  3_catalogo_eventos_v1.yaml   # event catalog — schema "what", changes frequently
  4_gerador_bichos_v0_1.md     # generator product mini-doc
  handoff_*.md                 # session handoffs between design (Project) and implementation (Code) sessions
```

Generated data (`geradores/out/`, CSVs, `load_eventos.sql`) and credentials (`pipeline/loaders/.env`) are gitignored — the corpus is reproducible from the generators and a fixed seed.

## Common commands

Everything below runs from the repo root unless noted. Requires PostgreSQL 18 and Python 3 (`pip install pyyaml psycopg2-binary`).

All Python commands run **as modules from the repo root** (the `-m` form is required — running a file directly, `python geradores/gen_massa.py`, breaks the cross-package imports).

```bash
# 0. one-time: copy pipeline/loaders/.env.example -> pipeline/loaders/.env and set PGHOST/PGPORT/PGDATABASE/PGUSER/PGPASSWORD

# 1. Schema + base domains FIRST (generators read model rules from the seeded domains)
psql -d mdm_rh -f banco/3_schema_mdm.sql -f banco/seed_dominios.sql

# 2. Canonical FOTO (archetype-first) + unit/function/structure seeds
python -m geradores.gen_massa --config geradores/config.yaml --outdir geradores/out
psql -d mdm_rh -f geradores/out/seed_unidades_reino_animal.sql \
               -f geradores/out/seed_funcao_reino_animal.sql \
               -f geradores/out/seed_estrutura_decreto.sql   # dom_estrutura_decreto (ADR-013, 2 vigências)

# 3. EVENTOS: re-run the same trajectories, emit base+folha+pss+lixo loads
python -m geradores.gerador_eventos --valida

# 4. Load FOTO and EVENTOS (load_eventos.sql refreshes all MVs at the end)
python -m pipeline.loaders.carrega_foto --csv geradores/out/servidor.csv
( cd geradores/out && psql -d mdm_rh -f load_eventos.sql )

# 5. Validate: event replay re-derives FOTO exactly (target: 0 divergences)
python -m pipeline.tests.valida_replay_intervalo
python -m pipeline.tests.valida_replay_intervalo --incluir-lixo   # also exercise the retraction fixture (should still pass clean)
python -m pipeline.tests.valida_replay_intervalo --nucleo-so       # only check situacao_funcional
python -m pipeline.tests.valida_replay_intervalo --corte-futuro    # filter data_evento <= reference date (see caveat in file header)
```

Other useful single-file checks:
- `python -m pipeline.loaders.carrega_foto --csv geradores/out/servidor.csv --dry-run` — validate/classify without touching the DB.
- `python -m geradores.gerador_eventos --valida` runs its own internal replay check (pure Python, no DB) before you ever touch Postgres — always pass `--valida` when regenerating events.
- `python -m pipeline.tests.valida_roundtrip_siape --sem-db` — emissor->conector round-trip, 100% offline.
- Determinism: everything is seeded (`config.yaml: seed`) — same seed must always produce the same massa. Never hardcode volumetrics outside `config.yaml`; structural model constants (unit counts, career ladder) intentionally live in `gen_massa.py`, not the config.

There is no linter/formatter or automated test runner configured in this repo (no package.json/pytest config) — correctness is validated end-to-end against a real Postgres instance via `pipeline/tests/valida_replay_intervalo.py`.

## Working conventions

- Schema changes go in `banco/3_schema_mdm.sql` as `-- vX.Y` entries appended to the version-history header comment at the top of the file — don't silently bump the version number without documenting what changed and why, matching the existing header style.
- New event-driven modeling decisions should reference or add an ADR in `docs/1_adr_mdm.md` rather than being justified inline in code comments.
- `CREATE OR REPLACE VIEW` should only *append* columns at the end, never reorder/remove — several views promise this for backward compatibility with already-wired Power BI reports.
- Any new dashboard-facing object should ask "is this a new cut boundary (ADR-007) or a showcase over an existing one (ADR-012)?" before deciding view vs. materialized view vs. new GRANT.
