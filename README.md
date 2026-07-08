# MDM-RH — Master Data Management de Recursos Humanos

Golden record de RH de um órgão público federal: um **event store** que reconcilia
duas naturezas de dado — a **FOTO** (estado vigente do servidor) e o **EVENTO**
(a série histórica datada) — e as expõe em superfícies prontas para Power BI.

Piloto sobre um universo fictício ("Reino Animal"): massa **determinística por seed**,
1.300 vínculos, ~562 mil eventos, coerente ponta a ponta (a FOTO é reconstruível
pelo replay dos eventos, com 0 divergências).

---

## As duas naturezas (o coração do modelo)

| | FOTO | EVENTO |
|---|---|---|
| Tabela | `servidor` | `evento` (particionada por `id_carga`) |
| Grão | 1 linha por vínculo vigente | série datada, append-only |
| Mecânica | UPSERT por matrícula (**sobrescreve**) | INSERT (**nunca sobrescreve**) |
| Pergunta | "como está hoje?" | "como chegou aqui?" |

As duas mecânicas são opostas e não cabem na mesma tabela. Ortogonal a isso, a
`cod_mecanica` diz **como** o dado chegou (`ingestao` = API viva · `extracao` = lote).
A separação FOTO×EVENTO acontece no pipeline, registro a registro — não na fonte
(ADR-006).

## Sub-domínios do event store

`cadastro` · `vinculos` · `intercorrencias` · `compensacao` · `jornada`
(+ `desempenho`/`capacidades` no catálogo estendido, dependência externa).

`vinculos` e `intercorrencias` são máquina de estados (o vínculo transita entre
`ATIVO`, `CEDIDO`, `DISPONIBILIDADE`, `INATIVO`, `DESLIGADO`, `TRANSFERIDO`); os
demais são aditivos (só somam à série).

## Superfícies de exposição (o que o Power BI lê)

Objeto por **fronteira de recorte**, não por painel (ADR-007). O painel nunca lê a
base — lê estes objetos:

- **`vw_foto`**, **`vw_lente`** — views sobre a FOTO (base leve).
- **`mv_filme_servidor`** — replay da série do próprio servidor (payload cheio; o titular lê o próprio dado).
- **`mv_filme_gestor`** — série do subordinado, allowlist de coluna nomeada, zero JSONB (ADR-010).
- **`mv_calculadora_folha`** / **`mv_calculadora_pss`** — a Calculadora de aposentadoria, uma MV por fronteira de payload (ADR-011): folha rubrica-a-rubrica + contribuição PSS mensal.

As MVs têm views finas de passagem `vw_mv_*` porque o driver psqlODBC não enumera
materialized views no Navegador do Power BI (as da Calculadora omitem `payload`,
já que o conector não consome `jsonb`).

---

## Estrutura do repositório

Quatro pastas de responsabilidade única. `geradores/` e tudo sob `pipeline/` são
**pacotes** Python (`__init__.py`): os scripts rodam como módulos a partir da raiz
(`python -m geradores.gen_massa`), o que coloca a raiz no `sys.path` e faz os imports
cross-pacote resolverem sem gambiarra de `sys.path`.

```
geradores/                  # FABRICA dado sintético (massa + SERPRO simulada)
  gen_massa.py              # gera a FOTO (arquétipo-primeiro): servidor.csv + arquétipo
  gerador_eventos.py        # re-roda a MESMA trajetória por vínculo e emite os eventos
  trajetorias.py            # MOTOR ÚNICO de trajetória (usado pelos dois geradores)
  emissor_siape.py          # SERPRO simulada (Card 3): serializa a massa no envelope SOAP
  semente_trajetorias_v1.yaml    # 14 arquétipos do designer — o coração do fluxo
  config.yaml               # calibração + seed (reprodutibilidade)
  out/                      # gitignored (massa + XML sintético)
pipeline/                   # INGESTÃO orquestrada (o DAG e tudo que persiste)
  contrato/siape_envelope.py     # contrato de fronteira (emissor × conector)
  conectores/conector_siape.py   # Card 6: parseia o envelope SOAP → FOTO/EVENTO (carimbo ADR-014)
  loaders/
    carrega_foto.py         # servidor.csv → tabela servidor (UPSERT, rota de rejeito)
    .env.example            # modelo de credenciais (o .env real é gitignored)
  tests/
    valida_replay_intervalo.py   # prova que o replay dos eventos re-deriva a FOTO
    valida_roundtrip_siape.py    # round-trip emissor→conector (offline, sem DB)
banco/                      # ESTADO & DDL
  3_schema_mdm.sql          # schema do golden record (v0.14) — DDL do-zero, fonte da verdade
  seed_dominios.sql         # carga dos domínios (FK-obrigatórios) ANTES de qualquer dado
  roteiro_retratacao_adr009.sql  # retratação operacional por DETACH de partição
docs/
  1_adr_mdm.md              # decisões de arquitetura (ADR-001..011 + Seção 2 em aberto)
  3_catalogo_eventos_v1.yaml     # catálogo de eventos (v1.3) — o "o quê" (schema vivo)
  4_gerador_bichos_v0_1.md  # mini-doc do produto gerador (v0.2)
  2_*, 3_*                  # prespec das lentes, descritores, massa, solicitação
  handoff_*.md              # histórico de sessões (handoffs entre Project e Code)
```

> **Dados não são versionados.** A massa gerada (`geradores/out/`, CSVs, `load_eventos.sql`)
> e as credenciais (`pipeline/loaders/.env`) são gitignored — a massa é reprodutível pelos geradores.

---

## Rodar do zero

Requer PostgreSQL 18 e Python 3 (`pip install pyyaml psycopg2-binary`). Copie
`pipeline/loaders/.env.example` para `pipeline/loaders/.env` e ajuste as credenciais.
Os comandos Python rodam como **módulos a partir da raiz** (`python -m ...`).

```bash
# 1. Banco: schema + domínios-base PRIMEIRO (os geradores leem as regras deles)
psql -d mdm_rh -f banco/3_schema_mdm.sql -f banco/seed_dominios.sql

# 2. FOTO canônica (arquétipo-primeiro) + seeds de unidade/função
python -m geradores.gen_massa --config geradores/config.yaml --outdir geradores/out
psql -d mdm_rh -f geradores/out/seed_unidades_reino_animal.sql \
               -f geradores/out/seed_funcao_reino_animal.sql

# 3. EVENTOS: re-roda as MESMAS trajetórias e emite (base+folha+pss+lixo)
python -m geradores.gerador_eventos --valida

# 4. Carrega FOTO e EVENTOS (load_eventos.sql já faz o REFRESH das 4 MVs ao final)
python -m pipeline.loaders.carrega_foto --csv geradores/out/servidor.csv
( cd geradores/out && psql -d mdm_rh -f load_eventos.sql )

# 5. Valida: o replay dos eventos re-deriva a FOTO
python -m pipeline.tests.valida_replay_intervalo     # meta: 0 divergências
```

---

## Como o corpus se organiza

- **`3_catalogo_eventos_v1.yaml`** é o **o quê** — schema vivo dos eventos, muda toda hora.
- **`1_adr_mdm.md`** é o **porquê** — decisão de arquitetura, imutável quando numerada.
  O catálogo referencia a ADR; não repete a justificativa.
- **`handoff_*.md`** é o rastro das sessões — cada handoff passa o bastão entre a
  sessão de design (Project) e a de implementação (Code), com o estado do banco e
  as pendências abertas.

Versões atuais: schema **v0.14** · catálogo **v1.3** · seed de domínios · mini-doc
gerador **v0.2**.
