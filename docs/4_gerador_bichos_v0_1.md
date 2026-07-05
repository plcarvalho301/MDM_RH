# Gerador de Bichos — mini-doc do produto (v0.1)

**O que é:** o subsistema que fabrica a massa fictícia do MDM-RH (universo "Reino
Animal"). Produz uma base golden-record coerente — FOTO (estado vigente) + EVENTOS
(trajetória) — carregável no Postgres e consumível pelo Power BI. Determinístico
por seed. Serve para: popular dashboards, exercitar KRs/ADRs, e (fase 2) testar os
conectores de ingestão real.

**Estado:** fluxo canônico FOTO→EVENTO validado ponta a ponta (0 divergências,
commit `f3aebb9`). Schema do banco em v0.9.

---

## 1. Arquitetura — dois geradores, uma população

```
                        config.yaml (seed, volumetria, % — DONO da calibração)
                             │
   gen_massa.py  ───────────┤ FOTO canônica (fonte da população)
   (Reino Animal, v0.2)      │
                             ▼
                    gerador/out/servidor.csv ──────────┐
                             │                          │
   gerador_eventos.py ◄──────┘ (consome a foto)         ▼
   (foto-primeiro, v2)        │              loader/carrega_foto.py → tabela servidor
                              ▼
              gerador/out/eventos_*.csv → load_eventos.sql → event store (particionado)
                              │
                              ▼
              schema v0.9 (MVs de Filme, colunas planas) → Power BI (ODBC)
```

`gen_massa` é **soberano da população**: inventa as pessoas e o estado vigente.
`gerador_eventos` **não inventa gente** — recebe cada linha da foto e emite a
trajetória que **aterrissa** naquele estado (mesma matrícula/CPF). Foi a inversão
do passo 4 (o v1 gerava um universo paralelo — a "cagada" já corrigida).

## 2. Inventário de arquivos

| Arquivo | Papel |
|---|---|
| `gerador/gen_massa.py` | Gera a FOTO (grão vínculo). Estrutura hard-coded = MODELO (43 unidades, quadro FCE, escada de níveis); calibração no config. |
| `gerador/config.yaml` | **Único lugar de calibração ajustável.** Dono de seed/data_ref/percentuais. |
| `gerador/gerador_eventos.py` | Gera EVENTOS aterrissando na foto. Lê `servidor.csv` + seed do config. |
| `gerador/semente_trajetorias_v1.yaml` | 14 arquétipos de trajetória (Gerson, Vicente, Bruno…). **Hoje inativo no fluxo** — insumo da fase 2 (casos-teste ricos). |
| `loader/carrega_foto.py` | Carrega `servidor.csv` → tabela `servidor` (UPSERT, rota de rejeito). |
| `sql/3_schema_mdm.sql` (v0.9) | Schema do golden record + MVs de Filme/Gestor/Calculadora. |
| `sql/seed_dominios.sql` (v0.2) | Domínios-base (FK-obrigatórios). |
| `sql/roteiro_retratacao_adr009.sql` | Retratação operacional ponta a ponta (fixture carga_lixo). |
| `tests/valida_replay_intervalo.py` | Prova que o replay dos eventos re-deriva a foto (0 divergências). |
| `gerador/out/` | Saídas geradas (gitignored): `servidor.csv`, `pessoa.csv`, `eventos_*.csv`, `cargas.json`, `load_eventos.sql`, seeds de unidade/função, `relatorio_massa.md`. |

## 3. Pipeline canônico (o workflow, executável)

```bash
# 1. FOTO canônica (+ seeds de unidade/função + pessoa/acessos)
python gerador/gen_massa.py --config gerador/config.yaml --outdir gerador/out

# 2. Banco: schema + TODOS os domínios PRIMEIRO (o gerador lê as regras deles)
psql -d mdm_rh -c "DROP SCHEMA public CASCADE; CREATE SCHEMA public;" \
     -f sql/3_schema_mdm.sql -f sql/seed_dominios.sql \
     -f gerador/out/seed_unidades_reino_animal.sql \
     -f gerador/out/seed_funcao_reino_animal.sql

# 3. EVENTOS que aterrissam na foto (lê regras de modelo do banco; base+folha+lixo)
python gerador/gerador_eventos.py --foto gerador/out/servidor.csv --out gerador/out --valida

# 4. Carrega FOTO e EVENTOS
python loader/carrega_foto.py --csv gerador/out/servidor.csv
( cd gerador/out && psql -d mdm_rh -f load_eventos.sql )

# 5. Materializa e valida
psql -d mdm_rh -c "REFRESH MATERIALIZED VIEW mv_filme_servidor;" # + gestor, calculadora
python tests/valida_replay_intervalo.py     # meta: 0 divergências
```

Última rodada: 1300 vínculos · 260.465 eventos (7.800 base + 252.635 folha + 30 lixo)
· situação 1152 ATIVO / 55 DESLIGADO / 52 INATIVO / 29 CEDIDO / 12 DISPONIBILIDADE.

## 4. Formatos de I/O

**Entrada:** `config.yaml` (calibração) + `servidor.csv` (foto, para o gera_eventos).
**Saída atual (único registro):** CSV no shape das colunas internas (envelope do
evento / colunas da tabela `servidor`), pronto para `\copy`/loader.

Eixos ainda **não** cobertos (fase 2 — teste de conector):
- **Destino** `banco` direto (hoje só arquivo; o loader já sabe, falta o gerador chamá-lo).
- **Formato de ingestão real**: SIAPE (DDMMYYYY, vocabulário SIAPE), eSocial
  (S-2200/2206/2230/2231/2298/2299), Extrator (retroativo). Hoje só o shape interno.
- **Injeção de defeito** configurável (hoje espalhada: DDMMYYYY em nova_funcao;
  duplicata na carga_lixo).

## 5. Superfície de calibração (`config.yaml`) — cada knob liga um teste

| Knob | Efeito / teste |
|---|---|
| `seed` | Reprodutibilidade (invariante 5). Dono único. |
| `data_referencia` | Instante da foto (o gera_eventos herda). |
| `total_vinculos` | Volume. |
| `n_tocas_orfas` | Nº de unidades órfãs → **KR 2.1** (vw_orfao_estrutural). |
| `afastado_vigente_pct` | % ATIVOs com afastamento → **KR 2.2** (vw_afastado_conta_exercicio). |
| `nova_funcao_pct` | Emite DDMMYYYY → exercita `_data_iso` do loader (teste de conector). |
| `pct_acumulacao` | CPF com 2 matrículas (estado independente por matrícula). |
| `situacao` / `classe_peso` | Distribuição de situação e carreira. |
| `pct_cargo`, `tecnico_pode_fce`, `lotacao_dg_vice`, `sexo`, `geografia`, `idade*`, `regime` | Demografia e regras de cargo/função. |

**Fora do config (MODELO, não parâmetro):** 43 unidades, quadro FCE, escada de níveis.

## 6. Contratos que o gerador tem de honrar

- **Payload (v0.9):** as MVs de Filme leem chaves via `->>`. Não renomear:
  `cod_afastamento, data_inicio, data_fim` (AFASTAMENTO/CESSAO); `cod_motivo_deslig,
  data_desligamento` (DESLIGAMENTO); e as chaves de PROVIMENTO/PROGRESSAO/
  ALTERACAO_FUNCAO/FECHAMENTO_FOLHA.
- **Regras de derivação de situação** (a foto não guarda situação como evento; o
  replay re-deriva por intervalo na data-ref):
  - base ATIVO + CESSÃO vigente → **CEDIDO** (+ afastamento **40** espelho)
  - base ATIVO + afastamento **31** vigente → **DISPONIBILIDADE**
  - base ATIVO + afastamento (outro código) → **ATIVO** afastado
  - DESLIGAMENTO → situação do motivo (dom_motivo_deslig)
  Hoje essas regras vivem em constantes no `gerador_eventos.py`; deveriam virar
  **dado** (decisão #5 — pendente).
- **ADR-008 (coalescência):** fração das intercorrências sai como par
  aberto+fechamento (data_carga mais recente vence); a MV marca `intervalo_vigente`.
- **ADR-009 (retratação):** cada carga tem `id_carga` próprio (partição destacável).

## 7. Status

**Feito e verificado:** fluxo canônico FOTO→EVENTO (0 divergências, núcleo +
estendido); schema v0.9 aplicado; população sincronizada (foto ↔ eventos = mesma
gente); MVs planas para o PBI; retratação ADR-009 com roteiro executável.

**Limites declarados do v2 (bulk):**
1. **Casos-teste ricos ausentes.** Todos os 1300 recebem trajetória MECÂNICA.
   Desligados/inativos saem com motivo único genérico (07/38). Gerson (2
   desligamentos), Vicente (anulação), Bruno (2 vínculos), Célio (cedido+afastado)
   etc. **não** têm sua trajetória característica — a foto snapshot não carrega a
   forma da trajetória.
2. **Regras de modelo em código, não em dado** (situação→afastamento; nomes amigáveis).
3. **Só formato interno** (sem emissores de ingestão real; sem destino=banco direto).
4. **Descritor de evento (frase amigável) inexistente** — só o de-para código→nome
   das dimensões (dom_afastamento, dom_motivo_deslig) existe.

---

## 8. Próximos passos — menu para decidir com precisão

Cada item é independente; a dependência está anotada. Escolha por valor × esforço.

**A. Casos-teste ricos (reconciliação fina).** Devolver a trajetória característica
aos ~14 arquétipos nominais. **Depende de:** `gen_massa` marcar cada servidor com um
arquétipo (coluna nova em `servidor.csv`; a foto snapshot não carrega isso). Depois
`gera_eventos` roteia esses para a lógica rica da `semente_trajetorias_v1.yaml`.
*Maior valor de teste (é onde moram as cadeias que quebram a perna do RH); esforço médio.*

**B. Regras de modelo viram dado (decisão #5). ✅ FEITO (schema v0.11).**
`dom_afastamento.deriva_situacao`/`pausa_folha`; o gerador/replay leem do banco
(fim do `MOTIVO_DESLIG`/`AFAST_*` hardcoded). Rótulos (E-nível-1) ✅ FEITO (v0.10):
todo código resolve p/ nome; `vw_foto`/`vw_filme_*` entregam nome pronto. Falta só
a FRASE amigável (assembler) — refinamento de UX (o "E" grande).*

**C. Destino = banco direto (decisão #6, parte 1).** `gera_eventos --carrega-banco`
chama o loader em vez de escrever CSV intermediário. **Esforço baixo;** conveniência
de pipeline.

**D. Emissores de ingestão real (decisão #6, parte 2 — teste de conector).**
Refatorar o gerador em núcleo + emissores; `--formato {loader|siape|esocial|extrator}`
+ perfil de defeito injetável. **Depende de:** decidir o 1º conector-alvo.
*Maior esforço; é o que valida os conectores. O usuário pediu DEPOIS dos dashboards.*

**E. Descritor de evento (frase amigável).** Construir a escada de fallback do
`docs/2_descritores_eventos_v0_1.md` (CASE em view). **Depende de:** B.

**Recomendação de sequência:** B → A (fecham a massa "de verdade" e destravam os
casos-teste) antes de D (conectores). C encaixa a qualquer momento.
