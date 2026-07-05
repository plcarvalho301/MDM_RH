# Handoff — Calculadora completa: folha + PSS (sessão Code 2026-07-05)

**De:** sessão Code · **Para:** retorno ao Project (claude.ai) / próxima sessão
**Fecha:** o `handoff Calculadora completa` (folha + PSS) — Parte A (planificar o
FECHAMENTO_FOLHA existente) e Parte B (criar o evento PSS que faltava). Migração
aplicada no `mdm_rh` vivo e validada ponta a ponta contra Postgres 18 real, inclusive
o caminho ODBC/Power BI (confirmado pelo Pedro: "deu certo").

---

## 1. Arquivos alterados (substituem os homônimos do corpus — versão dentro do arquivo)

| Arquivo | Versão | O que mudou | Commit |
|---|---|---|---|
| `sql/3_schema_mdm.sql` | v0.11 → **v0.13** | `mv_calculadora` (única, payload cru) vira **duas MVs por fronteira de payload**: `mv_calculadora_folha` (rubrica EXPLODIDA, grão 1 linha/rubrica via `jsonb_to_recordset`) e `mv_calculadora_pss`. Vitrine ODBC: `vw_mv_calculadora` sai; entram `vw_mv_calculadora_folha`/`_pss`, **sem `payload`** (coluna nomeada, não `SELECT *` — jsonb não vai pro psqlODBC/Power BI). | `044ef38`, `0eab012` |
| `docs/3_catalogo_eventos_v1.yaml` | v1.1 → **v1.2** | Novo tipo `CONTRIBUICAO_PSS` em `compensacao` (payload do WS_SIAPE_CONSULTAS 4.22: campos apurados + arrays datados ferias/lpa/afastamentos/reclusao como ATRIBUTO, não evento-espelho). Descrição do sub-domínio `compensacao` atualizada (duas fontes). | `044ef38` |
| `sql/seed_dominios.sql` | (mesma) | + linha `CONTRIBUICAO_PSS` em `dom_tipo_evento`; descrição de `compensacao` atualizada. | `044ef38` |
| `docs/1_adr_mdm.md` | +**ADR-011** | ADR-011 — Calculadora: MV por fronteira de payload (folha × PSS); rubrica explodida por grão. Registra as duas pendências do Code (uma MV × duas; grão da rubrica) e o porquê da escolha. | `044ef38` |
| `gerador/gerador_eventos.py` | (mesma) | `gera_pss()` espelha `gera_folha()`; nova `carga_pss`; flag `--sem-pss`. Emitida DEPOIS de base/folha/lixo de propósito (não perturba o rng das cargas já carregadas). | `742a838` |

**Fora do git (one-shot):** `migra_calculadora_pss.sql` — migração operacional que trouxe o
`mdm_rh` já povoado ao v0.13 (INSERT do tipo → `\copy` da carga_pss → swap das MVs). Ficou no
scratchpad porque hardcoda o `id_carga` da carga PSS (seed 42) e o caminho reproduzível de
zero é `3_schema_mdm.sql` v0.13 + seed + gerador. **PENDÊNCIA LEVE:** decidir se promove pra
`sql/` como script operacional (modelo do `roteiro_retratacao_adr009.sql`) ou descarta.

---

## 2. O que rodou no banco `mdm_rh` (PG 18, banco já povoado)

Migração transacional (rollback automático se falhar), na ordem:

1. **Registra** `CONTRIBUICAO_PSS` em `dom_tipo_evento` (aditivo; FK exige antes do COPY).
2. **Carga PSS** — partição própria (ADR-009, `fn_particao_carga`) + `\copy` de
   `eventos_carga_pss.csv`: **271.933 eventos** (1 por mês × vínculo × vida funcional inteira).
3. **Swap das MVs** — `DROP mv_calculadora CASCADE` (leva junto a `vw_mv_calculadora` velha) →
   cria `mv_calculadora_folha` (271.933, popula dos FECHAMENTO_FOLHA já presentes — cada folha
   tem 1 rubrica, então explode 1:1 na massa atual) e `mv_calculadora_pss` (271.933) + as duas
   views finas.
4. **v0.13 (2º passo, commit `0eab012`):** `DROP`+`CREATE` das duas views finas **sem `payload`**
   (fix do aviso Power BI "coluna sem tipo suportado" — o driver não expõe jsonb).

**Estado final:** `evento` = **561.695 linhas** (289.762 anteriores + 271.933 PSS). 4 partições
de carga. `REFRESH MATERIALIZED VIEW CONCURRENTLY` OK nas duas MVs novas (caminho Airflow D-1).

---

## 3. Decisão registrada — ADR-011 (as duas pendências do Code, fechadas)

- **Uma MV × duas MVs → DUAS.** `compensacao` passou a ter dois payloads incompatíveis sob o
  mesmo sub-domínio. Uma MV com `CASE` deixaria metade das colunas sempre-nula por linha (o
  anti-padrão que a ADR-007 já evitou no Filme S/G). Duas MVs = shape limpo; o Power BI relaciona
  como duas tabelas normais por `matricula_funcional`, sem precisar filtrar por tipo antes.
- **Grão da rubrica → EXPLODIDA** (1 linha/rubrica). Aninhada obrigaria "Expandir lista JSON" na
  Power Query — degrau ruim pro usuário novo em Power BI. Custo aceito: índice único vira
  `(id_evento, numero_seq)`; colunas de competência repetem por rubrica (denormalização esperada).

---

## 4. Validação (checklist do handoff — passou)

1. `evento`: `FECHAMENTO_FOLHA` = 271.933, `CONTRIBUICAO_PSS` = 271.933. ✔
2. `vw_mv_calculadora_pss` (caminho ODBC) devolve `pss_apurado`, `remuneracao_pss`, `ano/mes`. ✔
3. `vw_mv_calculadora_folha` devolve `mes_competencia`, `valor_rubrica`, `indicador_rd`. ✔
4. Sinal negativo (rubrica suplementar) preservado — verificado em banco de teste (IRRF −600 fez
   round-trip; a massa v0.3 só emite VENCIMENTO positivo, então 0 negativos no vivo, esperado). ✔
5. Nenhum AFASTAMENTO duplicado a partir do payload PSS (0 eventos AFASTAMENTO com fonte PSS). ✔
6. Replay-de-intervalo do gerador segue **0 divergências** em 1300 vínculos (PSS é aditivo, não
   entra na máquina de estados — não mexeu no replay). ✔
7. Views finas: **0 colunas jsonb**, dado íntegro (271.933 cada). ✔

---

## 5. Escolhas de modelagem da massa PSS (a saber, para o cálculo futuro)

- **Sem piso temporal (B.2.1 do handoff):** série do provimento à competência atual — a fonte é
  o SIAPE, não o eSocial. Bichos de provimento antigo geram série longa DE PROPÓSITO.
- **`pss_apurado` = 11% da base** (alíquota RPPS), inteiro; `remuneracao_pss` numérico. Valores
  fictícios plausíveis, independentes da folha (fontes distintas na vida real — 4.20 × 4.22).
- **Arrays datados (ferias/lpa/afastamentos/reclusao) FORA da massa base.** São insumo de
  dias-líquidos, não número apurado. Ficam só no payload cru da MV quando existirem; se o cálculo
  de dias-líquidos precisar deles na massa, é acréscimo pequeno no `gera_pss()`.
- **Pausa de folha = pausa de PSS:** o mês sem remuneração (afastamento em `afast_pausa`) não gera
  nem folha nem contribuição — mesma lógica das duas.

---

## 6. Pendências (fora desta rodada — não travam nada)

- **PENDÊNCIA DO PEDRO — proveniência multi-fonte do afastamento** (4.1 vigente × 4.22 PSS × API
  Ocorrências): ADR aberta (prespec §7.1). Esta rodada só garantiu NÃO duplicar; qual fonte vence
  é decisão de negócio + ADR.
- **PENDÊNCIA DO PEDRO — dias líquidos:** onde a conta mora (cruzar arrays de afastamento do 4.22
  × `dom_afastamento.conta_efetivo_exercicio`). O mecanismo v0.11 (regra-como-dado) provavelmente
  absorve; confirmar quando o cálculo for construído.
- **PENDÊNCIA LEVE — `migra_calculadora_pss.sql`:** promover a `sql/` ou descartar (ver §1).
- **B.2 loader real:** o loader Python de produção precisará do ramo para o payload 4.22 quando a
  ingestão viva abrir (hoje a massa entra por `\copy`, mecânica=extracao). Não urgente.

---

## 7. Onde o Power BI conecta agora (nota de operação)

A `vw_mv_calculadora` (singular) **não existe mais**. O painel da Calculadora liga em **duas**
fontes: `vw_mv_calculadora_folha` e `vw_mv_calculadora_pss`, relacionadas no modelo por
`matricula_funcional` (e data/competência). Sem `payload` nas views → sem o aviso "coluna sem tipo
suportado". Relatório antigo que apontava pra view velha precisa ser reapontado.
