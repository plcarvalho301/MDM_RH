# Handoff → Code — Camada de vitrine PBI (schema v0.14 → v0.15)

**De:** chat (Tech Lead) · **Para:** sessão Code · **Data:** 2026-07-05
**Task:** implementar a camada de vitrine no `3_schema_mdm.sql` (candidata v0.15).
**Decisão que rege:** `1_adr_mdm.md` ADR-012 (constituição da camada — leia antes).
**Contrato campo-a-campo:** `spec_vitrine_pbi_v0_1.md` (N1–N11).
**Frase do evento:** `2_descritores_eventos_v0_1.md` (escada de fallback; a vitrine consome, não reescreve).
**Chaves de payload:** `atributos_eventos_MDM-RH.xlsx`, aba `Atributos por evento` (validada pelo PM).

---

## 0. Já verificado contra o schema v0.14 (não re-derive)

- `servidor` expõe: `matricula_funcional, cpf, nome, data_nascimento, cargo, classe, padrao, sigla_nivel_cargo, funcao_comissionada, cod_unidade_lotacao, cod_unidade_exercicio, situacao_funcional, regime_juridico, data_exercicio_no_orgao, cod_afastamento_vigente, data_referencia`.
- `vw_foto` expõe todos os rótulos que a Foto usa (`nome_unidade_lotacao`, `nome_unidade_exercicio`, `afastado` booleano, `nome_afastamento_vigente`, `nome_regime`).
- `mv_filme_servidor` tem `payload` cheio + planas (`cod_afastamento, cod_motivo_deslig, data_inicio, data_fim, data_desligamento, intervalo_vigente, cod_sub_dominio, grau_confianca, fonte`).
- `mv_filme_gestor` **sem payload** (ADR-010) — só planas + `fonte` (sem `cpf`, sem `grau_confianca`).
- Dimensões existem: `dom_cargo, dom_funcao, dom_classe, dom_padrao, dom_regime_juridico, dom_unidade_eorg, dom_afastamento(nome_afastamento), dom_motivo_deslig(nome_motivo), dom_sub_dominio(descricao), dom_tipo_evento(nome)`.
- Os 6 `cod_situacao` do seed = `ATIVO, INATIVO, CEDIDO, DISPONIBILIDADE, DESLIGADO, TRANSFERIDO` → o `UPDATE` de cor casa, **sem no-op**.
- `nome_exibicao` e `exibe_motivo_gestor` **não existem** e **não entram nesta leva** (ADR-012).

---

## 1. ALTER + UPDATE — cor na dimensão (N5)

```sql
ALTER TABLE dom_situacao_vinculo
    ADD COLUMN cor_fundo text,
    ADD COLUMN cor_fonte text;

UPDATE dom_situacao_vinculo AS d SET cor_fundo = v.f, cor_fonte = v.t
FROM (VALUES
    ('ATIVO',           '#E1F5EE', '#0F6E56'),
    ('CEDIDO',          '#FAEEDA', '#854F0B'),
    ('DISPONIBILIDADE', '#E6F1FB', '#185FA5'),
    ('INATIVO',         '#F1EFE8', '#5F5E5A'),
    ('DESLIGADO',       '#FCEBEB', '#A32D2D'),
    ('TRANSFERIDO',     '#EEEDFE', '#534AB7')
) AS v(cod, f, t)
WHERE d.cod_situacao = v.cod;
```

---

## 2. `vw_painel_consulta` — FRONTEIRA NOVA (não é vitrine)

GRANT largo, recorte de coluna mais estreito que a `vw_foto`. Entra no mapa da ADR-007 como objeto de fronteira. **Sem** situação/afastado/função (dado de gestão que o público não recebe).

```sql
CREATE VIEW vw_painel_consulta AS
SELECT s.matricula_funcional,
       s.nome,
       s.cargo,
       COALESCE(u.nome_unidade, '(unidade não identificada)') AS rotulo_unidade_lotacao,  -- N4
       s.cod_unidade_lotacao,                                                             -- cru, KR 2.1
       -- telefone/ramal: PENDENTE — coluna ainda não existe na FOTO. Entra quando subir.
       s.data_referencia                                                                  -- N8
FROM servidor s
LEFT JOIN dom_unidade_eorg u ON u.cod_unidade = s.cod_unidade_lotacao;
```

---

## 3. `vw_painel_foto` — Foto de gestão (ficha + consolidado do time)

Serve as duas camadas da página: a ficha (linha selecionada) e os cards de agregado (agregação implícita sobre `*_num`). Sem `vw_lente`, sem relação. `cpf`/`data_nascimento` excluídos (decisão do PM, reversível em 1 linha).

```sql
CREATE VIEW vw_painel_foto AS
SELECT f.matricula_funcional,
       f.nome,
       f.cargo, f.classe, f.padrao, f.sigla_nivel_cargo,
       f.funcao_comissionada,
       (f.funcao_comissionada IS NOT NULL)::int                     AS com_funcao_num,     -- N2
       CASE WHEN f.funcao_comissionada IS NOT NULL
            THEN 'Sim' ELSE 'Não' END                              AS com_funcao_rotulo,
       COALESCE(f.nome_unidade_lotacao,
                '(unidade não identificada)')                      AS rotulo_unidade_lotacao,   -- N4
       COALESCE(f.nome_unidade_exercicio, f.nome_unidade_lotacao,
                '(unidade não identificada)')                      AS rotulo_unidade_exercicio,
       f.cod_unidade_lotacao,                                                                -- cru, KR 2.1
       f.situacao_funcional,
       sv.nome_situacao,                                                                     -- N1
       sv.cor_fundo AS cor_situacao_fundo,                                                   -- N5
       sv.cor_fonte AS cor_situacao_fonte,
       f.afastado::int                                             AS afastado_num,          -- N2/N3
       CASE WHEN f.afastado THEN 'Sim' ELSE 'Não' END              AS afastado_rotulo,
       f.nome_afastamento_vigente,
       f.nome_regime,
       f.data_exercicio_no_orgao,
       f.data_referencia                                                                     -- N8
FROM vw_foto f
LEFT JOIN dom_situacao_vinculo sv ON sv.cod_situacao = f.situacao_funcional;
```

Cards do consolidado (agregação implícita do MESMO objeto, zero DAX): headcount = `COUNT(matricula_funcional)`; % afastados = `AVG(afastado_num)` (formatar %); % com função = `AVG(com_funcao_num)`.

---

## 4. `vw_painel_lente` — Lente Estratégica (grão uorg)

```sql
CREATE OR REPLACE VIEW vw_painel_lente AS
SELECT l.cod_unidade_lotacao,
       COALESCE(l.nome_unidade_lotacao,
                '(unidade não identificada)')                       AS rotulo_unidade,       -- N4
       l.headcount,
       l.afastados,
       l.com_funcao,
       ROUND(100.0 * l.afastados  / NULLIF(l.headcount,0), 1)       AS pct_afastados,         -- N3
       ROUND(100.0 * l.com_funcao / NULLIF(l.headcount,0), 1)       AS pct_com_funcao,
       (SELECT max(data_referencia) FROM servidor)                  AS data_referencia        -- N8
FROM vw_lente l;
```

---

## 5. `vw_painel_filme_servidor` — Filme do Servidor

`frase_evento` = escada do descritor (nível 2), sobre as chaves validadas. **Casts `::int` do payload guardados por regex** (payload sujo não derruba a view). **JSONB não sai** (N7): o payload é lido no CASE, nunca exposto como coluna.

```sql
CREATE VIEW vw_painel_filme_servidor AS
SELECT f.matricula_funcional,
       s.nome,
       f.data_evento,
       te.nome                                            AS nome_tipo_evento,
       sd.descricao                                       AS nome_sub_dominio,
       CASE WHEN f.cod_sub_dominio = 'compensacao'
            THEN 'financeiro' ELSE 'biografia' END        AS eixo,                -- N11 (filtro default = biografia)
       f.data_inicio, f.data_fim,
       f.intervalo_vigente::int                           AS vigente_num,         -- N2
       CASE WHEN f.data_fim IS NULL AND f.intervalo_vigente THEN 'em aberto'
            WHEN f.intervalo_vigente                       THEN 'vigente'
            ELSE 'substituído' END                        AS rotulo_vigencia,
       af.nome_afastamento,                                                        -- rótulo cru p/ slicer
       md.nome_motivo                                     AS nome_motivo_deslig,
       -- ── frase_evento: escada do descritor, nível 2 (template + dom.nome) ──
       --    nível 3 (COALESCE(dom.nome_exibicao, ...)) entra depois por CREATE OR REPLACE.
       --    Datas: intervalo=MM/AAAA, pontual=DD/MM/AAAA (regra do descritor). Valor NUNCA na frase.
       CASE f.cod_tipo_evento
         WHEN 'PROVIMENTO' THEN
              CASE WHEN dc.nome IS NOT NULL THEN 'Ingresso — ' || dc.nome
                   ELSE 'Ingresso no órgão' END
         WHEN 'ALTERACAO_FUNCAO' THEN
              CASE f.payload->>'tipo_movimento'
                WHEN 'designacao'      THEN 'Designação'
                WHEN 'dispensa_pedido' THEN 'Dispensa (a pedido) de função'
                WHEN 'dispensa_oficio' THEN 'Dispensa (de ofício) de função'
                WHEN 'exoneracao'      THEN 'Exoneração de função'
                ELSE 'Movimentação de função'
              END
              || COALESCE(' — ' || COALESCE(f.payload->>'nome_funcao', df.nome, f.payload->>'cod_funcao'), '')
         WHEN 'REMOCAO' THEN
              'Remoção: '
              || COALESCE(uo.nome_unidade, 'unidade ' || (f.payload->>'cod_unidade_origem'))
              || ' → '
              || COALESCE(ud.nome_unidade, 'unidade ' || (f.payload->>'cod_unidade_destino'))
         WHEN 'PROGRESSAO' THEN   -- tipo GATED (ativo=false, regras de carreira RH); frase provisória
              CASE f.payload->>'tipo_progressao' WHEN 'promocao' THEN 'Promoção: ' ELSE 'Progressão: ' END
              || COALESCE(f.payload->>'classe_origem','?') || '/' || COALESCE(f.payload->>'padrao_origem','?')
              || ' → '
              || COALESCE(f.payload->>'classe_destino','?') || '/' || COALESCE(f.payload->>'padrao_destino','?')
         WHEN 'AFASTAMENTO' THEN
              COALESCE(af.nome_afastamento, 'Afastamento')
              || ' — ' || to_char(f.data_inicio, 'MM/YYYY')
              || ' a ' || COALESCE(to_char(f.data_fim, 'MM/YYYY'), 'em curso')
         WHEN 'CESSAO' THEN
              'Cessão'
              || COALESCE(' — ' || (f.payload->>'orgao_cessionario'), '')
              || ' — ' || to_char(f.data_inicio, 'MM/YYYY')
              || COALESCE(' a ' || to_char(f.data_fim, 'MM/YYYY'), ' (em curso)')
         WHEN 'RETORNO_VINCULO' THEN
              CASE f.payload->>'tipo_retorno'
                WHEN 'reintegracao' THEN 'Reintegração'
                WHEN 'reversao'     THEN 'Reversão'
                WHEN 'reconducao'   THEN 'Recondução'
                ELSE 'Retorno ao serviço'
              END
         WHEN 'DESLIGAMENTO' THEN
              COALESCE(md.nome_motivo, 'Desligamento')
              || ' em ' || to_char(f.data_desligamento, 'DD/MM/YYYY')
         WHEN 'FECHAMENTO_FOLHA' THEN
              'Folha ' || to_char(to_date(f.payload->>'mes_competencia','YYYYMM'), 'MM/YYYY')
              || CASE WHEN f.payload->>'tipo_fechamento' = 'suplementar' THEN ' (suplementar)' ELSE '' END
         WHEN 'CONTRIBUICAO_PSS' THEN
              'Contribuição PSS ' || lpad(f.payload->>'mes_contribuicao', 2, '0') || '/' || (f.payload->>'ano_contribuicao')
         ELSE  -- nível 1: tipo novo ou payload pré-arqueologia. JSON cru NUNCA.
              te.nome || ' — ' || to_char(f.data_evento, 'DD/MM/YYYY')
       END                                                AS frase_evento,
       f.fonte, f.grau_confianca
FROM mv_filme_servidor f
JOIN      dom_tipo_evento   te ON te.cod_tipo_evento   = f.cod_tipo_evento
LEFT JOIN dom_sub_dominio   sd ON sd.cod_sub_dominio   = f.cod_sub_dominio
LEFT JOIN dom_afastamento   af ON af.cod_afastamento   = f.cod_afastamento
LEFT JOIN dom_motivo_deslig md ON md.cod_motivo_deslig = f.cod_motivo_deslig
LEFT JOIN dom_cargo         dc ON dc.cod = (f.payload->>'cargo_inicial')
LEFT JOIN dom_funcao        df ON df.cod = (f.payload->>'cod_funcao')
LEFT JOIN dom_unidade_eorg  uo ON uo.cod_unidade =
              (CASE WHEN f.payload->>'cod_unidade_origem'  ~ '^\d+$' THEN (f.payload->>'cod_unidade_origem')::int  END)
LEFT JOIN dom_unidade_eorg  ud ON ud.cod_unidade =
              (CASE WHEN f.payload->>'cod_unidade_destino' ~ '^\d+$' THEN (f.payload->>'cod_unidade_destino')::int END)
LEFT JOIN servidor s ON s.matricula_funcional = f.matricula_funcional;
```

Tela: tabela cronológica desc (`data_evento, frase_evento, rotulo_vigencia`) + slicer `eixo` **default=biografia** + slicer `nome_sub_dominio`. RLS por matrícula é camada de acesso, fora daqui.

---

## 6. `vw_painel_filme_gestor` — Filme do Gestor

**Sem payload** (ADR-010) → a frase usa só coluna plana + dimensão. Gestor **vê a categoria S-2230** do afastamento (`af.nome_afastamento`) — decisão travada (ADR-010 + aba de fronteira validada). **Sem flag de sigilo** nesta leva. `compensacao` não entra no WHERE da MV → `eixo` constante, não exposto.

**Limitação por construção:** eventos de vínculo (PROVIMENTO/ALTERACAO_FUNCAO/REMOCAO/PROGRESSAO/RETORNO) caem no fallback nível 1 (`tipo em data`), porque o detalhe deles mora no payload que a MV do gestor não carrega. Enriquecer = adicionar coluna nomeada à allowlist da MV (decisão de exposição, fora do escopo da vitrine — ver ADR-012 Pendências).

```sql
CREATE VIEW vw_painel_filme_gestor AS
SELECT g.matricula_funcional,
       s.nome,
       g.data_evento,
       te.nome                                            AS nome_tipo_evento,
       sd.descricao                                       AS nome_sub_dominio,
       g.data_inicio, g.data_fim,
       g.intervalo_vigente::int                           AS vigente_num,
       CASE WHEN g.data_fim IS NULL AND g.intervalo_vigente THEN 'em aberto'
            WHEN g.intervalo_vigente                       THEN 'vigente'
            ELSE 'substituído' END                        AS rotulo_vigencia,
       CASE g.cod_tipo_evento
         WHEN 'AFASTAMENTO' THEN
              COALESCE(af.nome_afastamento, 'Afastamento')
              || ' — ' || to_char(g.data_inicio, 'MM/YYYY')
              || ' a ' || COALESCE(to_char(g.data_fim, 'MM/YYYY'), 'em curso')
         WHEN 'DESLIGAMENTO' THEN
              COALESCE(md.nome_motivo, 'Desligamento')
              || ' em ' || to_char(g.data_desligamento, 'DD/MM/YYYY')
         WHEN 'CESSAO' THEN
              'Cessão — ' || to_char(g.data_inicio, 'MM/YYYY')
              || COALESCE(' a ' || to_char(g.data_fim, 'MM/YYYY'), ' (em curso)')
         ELSE  -- vínculos sem payload no Gestor (ADR-010): nível 1
              te.nome || ' em ' || to_char(g.data_evento, 'DD/MM/YYYY')
       END                                                AS frase_evento,
       g.fonte
FROM mv_filme_gestor g
JOIN      dom_tipo_evento   te ON te.cod_tipo_evento   = g.cod_tipo_evento
LEFT JOIN dom_sub_dominio   sd ON sd.cod_sub_dominio   = g.cod_sub_dominio
LEFT JOIN dom_afastamento   af ON af.cod_afastamento   = g.cod_afastamento
LEFT JOIN dom_motivo_deslig md ON md.cod_motivo_deslig = g.cod_motivo_deslig
LEFT JOIN servidor s ON s.matricula_funcional = g.matricula_funcional;
```

Foto do Gestor (consolidado do time): lê `vw_painel_foto` filtrada por uorg (agregação implícita) — não precisa de objeto próprio.

---

## 7. Calculadora — N9 (data real) e N10 (valor com sinal)

⚠ **`CREATE OR REPLACE VIEW` no Postgres só ANEXA coluna no fim — não reordena nem remove.** A spec §3.6 pôs as novas colunas no meio; aqui elas vão **no fim**, preservando a ordem existente da v0.13 (senão dá `ERROR: cannot change name of view column`).

```sql
CREATE OR REPLACE VIEW vw_mv_calculadora_folha AS
SELECT id_evento, matricula_funcional, cpf, cod_tipo_evento, data_evento,
       mes_competencia, mes_pagamento, tipo_fechamento,
       cod_rubrica, nome_rubrica, valor_rubrica, indicador_rd, numero_seq,
       prazo_rubrica, periodo_rubrica, data_ano_mes_rubrica,
       fonte, grau_confianca,
       to_date(mes_competencia,'YYYYMM')                  AS competencia_data,   -- N9 (anexada)
       CASE WHEN indicador_rd = 'D' THEN -valor_rubrica
            ELSE valor_rubrica END                        AS valor_assinado      -- N10 (anexada)
FROM mv_calculadora_folha;

CREATE OR REPLACE VIEW vw_mv_calculadora_pss AS
SELECT id_evento, matricula_funcional, cpf, cod_tipo_evento, data_evento,
       gr_matricula, ano_contribuicao, mes_contribuicao, indice_reajuste,
       pss_apurado, pss_informado, remuneracao_pss, remuneracao_pss_ajustada,
       fonte, grau_confianca,
       make_date(ano_contribuicao, mes_contribuicao, 1)   AS competencia_data    -- N9 (anexada)
FROM mv_calculadora_pss;
```

Tela: slicer matrícula + card dias_liquidos (**quando §8 sair da quarentena**) + matriz rubrica × `competencia_data` (`SUM(valor_assinado)` = líquido) + linha PSS por `competencia_data`.

---

## 8. `vw_painel_calc_dias` — NÃO CRIAR NESTA LEVA (quarentena)

Objeto de dias líquidos **não estampar** até fechar (a) e (b) abaixo — o número sai plausível e errado. Esboço fichado para não perder; **não executar**:

```sql
-- QUARENTENA (ADR-012 Pendências) — NÃO CRIAR. Ressalvas abertas:
--  (a) afastamentos SOBREPOSTOS somam em dobro → precisa merge de intervalos
--      (gaps-and-islands) antes do SUM.
--  (b) conta_efetivo_exercicio='parcial' sem regra de desconto (esboço ignora
--      = chute conservador, não regra).
--  (c) proveniência multi-fonte do afastamento (4.1×4.21×4.22) = ADR aberta.
-- CREATE VIEW vw_painel_calc_dias AS
-- WITH afast_nao_conta AS (
--     SELECT f.matricula_funcional,
--            SUM((COALESCE(f.data_fim, CURRENT_DATE) - f.data_inicio) + 1) AS dias_descontados
--     FROM mv_filme_servidor f
--     JOIN dom_afastamento a ON a.cod_afastamento = f.cod_afastamento
--     WHERE f.cod_tipo_evento = 'AFASTAMENTO'
--       AND f.intervalo_vigente
--       AND a.conta_efetivo_exercicio = 'nao'
--     GROUP BY 1)
-- SELECT s.matricula_funcional, s.nome, s.data_exercicio_no_orgao,
--        (CURRENT_DATE - s.data_exercicio_no_orgao) + 1 AS dias_brutos,
--        COALESCE(an.dias_descontados, 0)               AS dias_descontados,
--        (CURRENT_DATE - s.data_exercicio_no_orgao) + 1 - COALESCE(an.dias_descontados,0) AS dias_liquidos,
--        s.data_referencia
-- FROM servidor s LEFT JOIN afast_nao_conta an USING (matricula_funcional);
-- NB extra: CURRENT_DATE anda durante o dia; quando sair da quarentena, ancorar em data_referencia (D-1),
--          senão dias_brutos diverge do próprio carimbo.
```

---

## 9. GRANT

Vitrines **herdam a fronteira** do objeto-base (mesmo recorte), mas o Postgres não propaga GRANT — cada view nova precisa do seu `GRANT SELECT` ao(s) role(s) que já leem o objeto-base. `vw_painel_consulta` é **fronteira nova** (GRANT próprio, largo). **Nomes de role são do ambiente** (ilustrativos no schema; Code/PM substitui pelos reais):

```sql
-- roles ILUSTRATIVOS — substituir pelos do ambiente:
GRANT SELECT ON vw_painel_foto, vw_painel_lente, vw_painel_filme_servidor
      TO <role_gestao>;
GRANT SELECT ON vw_painel_filme_gestor
      TO <role_gestor>;
GRANT SELECT ON vw_painel_consulta                                   -- FRONTEIRA NOVA (GRANT largo)
      TO <role_publico_institucional>;
-- Calculadora: as vw_mv_calculadora_* já têm GRANT (v0.13); REPLACE não o derruba.
```

RLS (Filme-Servidor→própria matrícula; Filme-Gestor→sub-árvore) é camada de acesso, desenhada sobre a MV — não muda aqui.

---

## 10. Travado / o que NÃO fazer

- **Não** criar `nome_exibicao` nem `exibe_motivo_gestor` (ADR-012).
- **Não** autorar frase paralela à do descritor — a frase acima É a escada nível 2.
- **Não** reordenar/remover coluna nas vitrines da Calculadora (§7) — só anexar.
- **Não** criar `vw_painel_calc_dias` (§8, quarentena).
- **Não** expor `payload` (jsonb) em nenhuma vitrine (N7) — nem na de Filme-Servidor (a v0.7 `vw_mv_filme_servidor` que sobe payload pode ser aposentada como ponto de conexão do painel quando estas subirem; limpeza, não urgência).
- **Zero REFRESH novo** — todas são views comuns sobre objeto já materializado.

---

## 11. Smoke pós-aplicação (rode e reporte)

```sql
-- 1. cor semeada nos 6 estados (espera 6, nenhum nulo):
SELECT count(*) FILTER (WHERE cor_fundo IS NOT NULL) AS com_cor, count(*) AS total
FROM dom_situacao_vinculo;

-- 2. nenhuma frase caiu em JSON cru nem ficou nula (espera 0):
SELECT count(*) FROM vw_painel_filme_servidor
WHERE frase_evento IS NULL OR frase_evento LIKE '{%';

-- 3. fallback de órfão aparece como rótulo, não some (KR 2.1):
SELECT count(*) FROM vw_painel_consulta
WHERE rotulo_unidade_lotacao = '(unidade não identificada)';

-- 4. líquido da folha por SUM implícito (D negativo): amostra 1 matrícula/competência
SELECT matricula_funcional, competencia_data, SUM(valor_assinado) AS liquido
FROM vw_mv_calculadora_folha GROUP BY 1,2 ORDER BY 2 DESC LIMIT 5;

-- 5. gestor NÃO expõe payload nem grau_confianca (espera as colunas planas só):
SELECT * FROM vw_painel_filme_gestor LIMIT 1;

-- 6. cast guardado não quebra REMOCAO com destino não-numérico (espera: sem erro):
SELECT frase_evento FROM vw_painel_filme_servidor
WHERE nome_tipo_evento IS NOT NULL LIMIT 20;
```

Se algo falhar, o suspeito nº1 é nome de coluna divergente entre o que este handoff assumiu e a MV real — reporta a coluna, não adivinha.
