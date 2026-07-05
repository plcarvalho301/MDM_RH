# Gerador de Bichos — mini-doc do produto (v0.2)

**O que é:** o subsistema que fabrica a massa fictícia do MDM-RH (universo "Reino
Animal"). Produz uma base golden-record coerente — FOTO (estado vigente) + EVENTOS
(trajetória) — carregável no Postgres e consumível pelo Power BI. Determinístico
por seed. Serve para: popular dashboards, exercitar KRs/ADRs, e (fase 2) testar os
conectores de ingestão real.

**Estado:** fluxo canônico FOTO→EVENTO validado ponta a ponta (0 divergências).
Schema do banco em **v0.13**: rótulos em todas as superfícies do painel (`vw_foto`,
`vw_lente`, `vw_filme_servidor`, `vw_filme_gestor`) + regras de modelo como dado +
**Calculadora completa (folha + PSS)**. A Calculadora deixou de ser uma MV: virou
duas por fronteira de payload — `mv_calculadora_folha` (rubrica explodida) e
`mv_calculadora_pss` (contribuição PSS mensal), ADR-011. O gerador emite os dois
tipos de `compensacao`: `FECHAMENTO_FOLHA` e `CONTRIBUICAO_PSS`.

---

## 1. Arquitetura — ARQUÉTIPO-PRIMEIRO (o alinhamento com o designer)

```
      semente_trajetorias_v1.yaml          config.yaml (seed, volumetria)
      (14 arquétipos do designer:           │
       Camada A por PESO, Camada B          │        dom_* no banco
       PLANTADA: Elias×2 Gerson×2           │        (regras de modelo — decisão #5)
       Vicente×1, DG/Vice fixos)            │             │
                  │                         │             │
                  ▼                         ▼             ▼
             ┌──────────────── trajetorias.py (MOTOR ÚNICO) ────────────────┐
             │  rng por vínculo (seed:matricula:salt) → mesma vida nos 2 lados │
             └──────────────┬───────────────────────────────┬───────────────┘
                            │                               │
   gen_massa.py (v0.3) ─────┘                               └───── gerador_eventos.py (v3)
   ASSENTO (43 unidades, quadro FCE,                        re-RODA a mesma trajetória
   órfãos) + estampa o arquétipo:                           e emite os EVENTOS dela
   a VIDA (situação/classe/afastamento)                     (assert estado == foto)
   DERIVA da trajetória                                              │
        │                                                            │
        ▼                                                            ▼
   servidor.csv (+arquetipo, traj_salt) → carrega_foto      eventos_*.csv → load_eventos
                            │                                        │
                            └────────── replay (--valida + tests/) ──┘
                                        = 0 divergências
```

O `situacao:`/`classe_peso:` demográfico do v0.2 **morreu** — era desalinhado do
handoff do designer. A situação **emerge** dos arquétipos: Camada A estampada em
arco EM CURSO (truncamento u), Camada B com arco completo (os casos-limite). A
costura arquétipo×assento vive no motor: lotação/função finais = quadro (a última
designação/REMOCAO corretiva aterrissa no assento); a vida = designer.

## 2. Inventário de arquivos

| Arquivo | Papel |
|---|---|
| `gerador/trajetorias.py` | **O MOTOR ÚNICO** de trajetória: marcos da semente, truncamento de arco, costura arquétipo×assento, regras do banco. Usado pelos dois geradores. |
| `gerador/gen_massa.py` (v0.3) | ASSENTO (43 unidades, quadro FCE, órfãos) + estampa arquétipos (Camada A por peso, B plantada). A vida deriva do motor. |
| `gerador/config.yaml` | Calibração estrutural + `disponibilidade_pct`. Dono da seed. |
| `gerador/gerador_eventos.py` (v3) | Re-roda a MESMA trajetória por vínculo (`arquetipo`+`traj_salt` do csv) e emite os eventos. Sem máquina de estados própria. |
| `gerador/semente_trajetorias_v1.yaml` | 14 arquétipos do designer (v0.2 normalizado). **É o coração do fluxo** — pesos A, contagens B, marcos. |
| `loader/carrega_foto.py` | Carrega `servidor.csv` → tabela `servidor` (UPSERT, rota de rejeito). |
| `sql/3_schema_mdm.sql` (v0.13) | Schema do golden record + 4 MVs de exposição (Filme-Servidor, Filme-Gestor, Calculadora-Folha, Calculadora-PSS) + views amigáveis (`vw_foto`, `vw_lente`, `vw_filme_*`) com rótulos resolvidos. Vitrine ODBC da Calculadora sem `payload` (jsonb não sobe pro Power BI). |
| `sql/seed_dominios.sql` (v0.2) | Domínios-base (FK-obrigatórios). |
| `sql/roteiro_retratacao_adr009.sql` | Retratação operacional ponta a ponta (fixture carga_lixo). |
| `tests/valida_replay_intervalo.py` | Prova que o replay dos eventos re-deriva a foto (0 divergências). |
| `gerador/out/` | Saídas geradas (gitignored): `servidor.csv`, `pessoa.csv`, `eventos_*.csv`, `cargas.json`, `load_eventos.sql`, seeds de unidade/função, `relatorio_massa.md`. |

## 3. Pipeline canônico (o workflow, executável)

```bash
# 1. Banco: schema + domínios-base PRIMEIRO (os DOIS geradores leem as regras deles)
psql -d mdm_rh -c "DROP SCHEMA public CASCADE; CREATE SCHEMA public;" \
     -f sql/3_schema_mdm.sql -f sql/seed_dominios.sql

# 2. FOTO canônica arquétipo-primeiro (+ seeds de unidade/função + pessoa/acessos)
python gerador/gen_massa.py --config gerador/config.yaml --outdir gerador/out
psql -d mdm_rh -f gerador/out/seed_unidades_reino_animal.sql \
               -f gerador/out/seed_funcao_reino_animal.sql

# 3. EVENTOS: re-roda as MESMAS trajetórias e emite (base+folha+pss+lixo; --sem-pss desliga PSS)
python gerador/gerador_eventos.py --valida

# 4. Carrega FOTO e EVENTOS (load_eventos.sql já faz o REFRESH das 4 MVs ao final)
python loader/carrega_foto.py --csv gerador/out/servidor.csv
( cd gerador/out && psql -d mdm_rh -f load_eventos.sql )

# 5. Valida contra o banco real (REFRESH já rodou no passo 4)
python tests/valida_replay_intervalo.py     # meta: 0 divergências
```

Última rodada: 1300 vínculos · **561.695 eventos** (17.799 base + 271.933 folha +
271.933 PSS + 30 lixo) · situação 1100 ATIVO / 113 INATIVO / 40 DESLIGADO /
26 DISPONIBILIDADE / 21 CEDIDO.

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
| `pct_acumulacao` | CPF com 2 matrículas = arquétipo **Bruno** (estado independente por matrícula). |
| `disponibilidade_pct` | dos elegíveis (ATIVO sem função, casa antiga) → DISPONIBILIDADE via afast 31 iniciado 1991-2000. |
| `pct_cargo`, `tecnico_pode_fce`, `lotacao_dg_vice`, `sexo`, `geografia`, `idade*`, `regime` | Demografia e regras de cargo/função. |

**Mortos no v0.3 (eram desalinhados do designer):** `situacao:`, `classe_peso:`,
`afastado_vigente_pct:` — situação/carreira/afastamento **emergem** das trajetórias
(pesos da Camada A + arcos truncados). A distribuição realizada sai no
`relatorio_massa.md`.

**Fora do config (MODELO, não parâmetro):** 43 unidades, quadro FCE, escada de níveis.

## 6. Contratos que o gerador tem de honrar

- **Payload (v0.9):** as MVs de Filme leem chaves via `->>`. Não renomear:
  `cod_afastamento, data_inicio, data_fim` (AFASTAMENTO/CESSAO); `cod_motivo_deslig,
  data_desligamento` (DESLIGAMENTO); e as chaves de PROVIMENTO/PROGRESSAO/
  ALTERACAO_FUNCAO/FECHAMENTO_FOLHA.
- **Payload da Calculadora (v0.13):** `mv_calculadora_folha` explode `rubricas`
  (`jsonb_to_recordset`) — não renomear `cod_rubrica, nome_rubrica, valor_rubrica`
  (COM sinal), `indicador_rd, numero_seq` + `mes_competencia/mes_pagamento/
  tipo_fechamento`. `mv_calculadora_pss` planifica `gr_matricula, ano_contribuicao,
  mes_contribuicao, pss_apurado` (int), `remuneracao_pss` (numeric) etc. Os arrays
  datados do 4.22 (`ferias/lpa/afastamentos/reclusao`) ficam SÓ no payload cru —
  insumo de dias-líquidos, NÃO viram evento AFASTAMENTO (não duplicar).
- **Regras de derivação de situação** (a foto não guarda situação como evento; o
  replay re-deriva por intervalo na data-ref) — **dado desde v0.11**, lido de
  `dom_afastamento`/`dom_motivo_deslig` (não hardcoded no gerador):
  - base ATIVO + CESSÃO vigente → **CEDIDO** (+ afastamento **40** espelho, `deriva_situacao`)
  - base ATIVO + afastamento com `deriva_situacao='DISPONIBILIDADE'` (**31**) → **DISPONIBILIDADE**
  - base ATIVO + afastamento (outro código) → **ATIVO** afastado
  - DESLIGAMENTO → situação do motivo (`dom_motivo_deslig.situacao_resultante`)
  - `pausa_folha` (hoje só **05**) → folha E PSS pulam o mês (sem remuneração = sem contribuição)
- **ADR-008 (coalescência):** fração das intercorrências sai como par
  aberto+fechamento (data_carga mais recente vence); a MV marca `intervalo_vigente`.
- **ADR-009 (retratação):** cada carga tem `id_carga` próprio (partição destacável).

## 7. Status

**Feito e verificado:** fluxo canônico FOTO→EVENTO (0 divergências, núcleo +
estendido); população sincronizada (foto ↔ eventos = mesma gente); MVs planas
para o PBI; retratação ADR-009 com roteiro executável; **rótulos** em todas as
4 superfícies do painel (v0.10 + fix da `vw_lente`); **regras de modelo como
dado** (v0.11) — gerador/replay leem `dom_afastamento`/`dom_motivo_deslig` do
banco, zero regra de domínio hardcoded; **Calculadora completa (v0.13)** — folha
planificada (rubrica explodida) + `CONTRIBUICAO_PSS` (série mensal SEM piso
temporal: fonte SIAPE 4.22, cobre a vida funcional inteira, não trunca no eSocial).

**Item A (casos ricos) ✅ FEITO (massa v0.3, arquétipo-primeiro):** todos os 1300
carregam arquétipo do designer; os plantados têm suas cadeias-assinatura no banco
(Gerson ×2 fuga+cassação, Vicente demissão+anulação, Elias disciplinar, Olga
reversão, Bruno 39 pares, Célio cedido+afastado…). Situação EMERGE dos arcos
(1100 ATIVO / 113 INATIVO / 40 DESLIGADO / 21 CEDIDO / 26 DISPONIBILIDADE ≈2%).

**Limites declarados:**
1. **Só formato interno** (sem emissores de ingestão real; sem destino=banco direto).
2. **Descritor de evento (frase amigável) inexistente** — rótulos prontos em toda
   superfície; a composição narrativa fica pro futuro (decisão do PM).
3. **Pesos realizados ≠ pesos nominais** (levemente): a costura com o quadro FCE
   (função-holders preferem moldes com função; cargo do assento restringe) desloca
   a distribuição (~Wallace 33% vs 39.6% nominal). Relatório reporta o realizado.
4. **Bifurcações do designer** (a reintegração "de ouro" do Elias etc.) seguem
   fora — gerador de desvios é o incremento previsto.

---

## 8. Próximos passos — menu para decidir com precisão

Cada item é independente; a dependência está anotada. Escolha por valor × esforço.

**A. Casos-teste ricos. ✅ FEITO (massa v0.3 — arquétipo-primeiro).** Foi além do
plano: não só os ~14 nominais — TODA a massa nasce de arquétipo (Camada A por peso
do designer, Camada B plantada), com o motor único `trajetorias.py` garantindo que
foto e eventos são a mesma vida (rng por vínculo + `traj_salt`).

**B. Regras de modelo viram dado (decisão #5). ✅ FEITO (schema v0.11).**
`dom_afastamento.deriva_situacao`/`pausa_folha`; o gerador/replay leem do banco
(fim do `MOTIVO_DESLIG`/`AFAST_*` hardcoded). Rótulos (E-nível-1) ✅ FEITO (v0.10 +
fix `vw_lente` em v0.11): todo código resolve p/ nome nas 4 superfícies
(`vw_foto`, `vw_lente`, `vw_filme_servidor`, `vw_filme_gestor`). Falta só a
FRASE amigável (assembler) — refinamento de UX (o "E" grande).

**C. Destino = banco direto (decisão #6, parte 1).** `gera_eventos --carrega-banco`
chama o loader em vez de escrever CSV intermediário. **Esforço baixo;** conveniência
de pipeline.

**D. Emissores de ingestão real (decisão #6, parte 2 — teste de conector).**
Refatorar o gerador em núcleo + emissores; `--formato {loader|siape|esocial|extrator}`
+ perfil de defeito injetável. **Depende de:** decidir o 1º conector-alvo.
*Maior esforço; é o que valida os conectores. O usuário pediu DEPOIS dos dashboards.*

**E. Descritor de evento (frase amigável).** Construir a escada de fallback do
`docs/2_descritores_eventos_v0_1.md` (assembler que compõe frase a partir dos
rótulos, não CASE hardcoded — ver discussão de sessão). **Depende de:** B
(✅ satisfeita — rótulos e regras já são dado).

**Recomendação de sequência:** com B feito, os próximos naturais são **A**
(casos-teste ricos) e **E** (frase amigável) — ambos já desbloqueados. D
(conectores) fica para depois dos dashboards, como definido. C encaixa a
qualquer momento.
