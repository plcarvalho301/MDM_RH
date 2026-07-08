-- =============================================================================
-- ROTEIRO DE RETRATACAO OPERACIONAL (ADR-009) — ponta a ponta, executavel
-- fixture: carga_lixo (30 eventos, fonte CARGA_APOSENTADOS_DEFEITUOSA)
-- -----------------------------------------------------------------------------
-- Segue a sequencia documentada no schema v0.8 (secao RETRATACAO):
--   1. manifesto (fn_manifesto_carga)  — a diretora LE o alcance ANTES de assinar
--   2. aceite protocolado referenciando o digest do manifesto (SEI ficticio aqui)
--   3. INSERT no ledger_delecao        — a prova mora FORA das particoes
--   4. DETACH PARTITION                — instantaneo, sem DELETE, sem bloat
--   5. destino 'cold'                  — a particao destacada E o cold storage
--      (fonte e extracao de papel: NUNCA descarta — o garimpo nao volta)
--   6. REFRESH das projecoes           — MV re-deriva do cru, sem orfao
--   +  prova de REVERSIBILIDADE: re-ATTACH da MESMA particao, contagem volta,
--      e re-DETACH final (o estado que fica: carga retratada, ledger assinado).
--
-- NAO confundir com reversao de DOMINIO (Gerson CASS_APOSENT / Vicente
-- ANUL_PROVIMENTO): aquilo e EVENTO legitimo e fica na base para sempre.
-- Aqui o registro NUNCA deveria ter existido — sai a CARGA inteira.
--
-- Uso:  psql -d mdm_rh -f roteiro_retratacao_adr009.sql
-- =============================================================================
\set ON_ERROR_STOP on
\set id_lixo '''d5a00117-eb9c-416f-bc61-925d130282f8'''
-- nome deterministico: 'evento_c_' || uuid sem hifens (fn_particao_carga)
\set particao evento_c_d5a00117eb9c416fbc61925d130282f8
\set protocolo '''SEI-2026/00042 (ficticio — PoC)'''

\echo '=== [0] estado ANTES: contagem por carga ==='
SELECT id_carga, count(*) AS eventos FROM evento GROUP BY id_carga ORDER BY 2;

\echo ''
\echo '=== [1] MANIFESTO — superficie de decisao (roda ANTES do detach) ==='
SELECT fn_manifesto_carga(:id_lixo::uuid) AS manifesto \gset
SELECT jsonb_pretty(:'manifesto'::jsonb - 'amostra') AS manifesto_sem_amostra;
\echo '--- amostra (ate 20 linhas), o que a diretora ve: ---'
SELECT jsonb_pretty(:'manifesto'::jsonb -> 'amostra' -> 0) AS primeira_linha_da_amostra;
SELECT :'manifesto'::jsonb ->> 'digest' AS digest \gset
\echo '--- digest md5 da lista ordenada de id_evento: ---'
SELECT :'digest' AS digest_do_manifesto;

\echo ''
\echo '=== [2] PROTOCOLO — aceite referenciando o digest (RH assina, TI executa) ==='
SELECT :'protocolo' AS protocolo, :'digest' AS digest_referenciado;

\echo ''
\echo '=== [3] LEDGER — o MESMO jsonb do manifesto aterrissa fora das particoes ==='
INSERT INTO ledger_delecao
       (id_carga, manifesto, digest, protocolo,
        autorizado_por, executado_por, motivo, destino)
VALUES (:id_lixo::uuid, :'manifesto'::jsonb, :'digest', :protocolo,
        'Diretora de RH (ficticio)', 'TI — sessao Code 2026-07-05',
        'erro material deliberado da fixture: fonte CARGA_APOSENTADOS_DEFEITUOSA '
        '(30 duplicatas bem-formadas de eventos da carga_base; passou limpo pela '
        'validacao — deteccao pelo manifesto/painel, tese da ADR-009)',
        'cold')
RETURNING id_delecao, protocolo, destino, data_execucao;

\echo ''
\echo '=== [4] DETACH — operacao de catalogo, nao de dados ==='
ALTER TABLE evento DETACH PARTITION :particao;
SELECT count(*) AS eventos_apos_detach FROM evento;

\echo ''
\echo '=== [5] destino=cold: a particao destacada E o cold storage ==='
\echo '(PoC: fica no mesmo tablespace; producao: SET TABLESPACE frio / pg_dump)'
\echo '--- digest re-verificavel contra a particao destacada (prova de custodia): ---'
SELECT md5(string_agg(id_evento::text, ',' ORDER BY id_evento)) = :'digest'
       AS digest_confere_na_particao_fria
  FROM :particao;

\echo ''
\echo '=== [6] REFRESH — projecoes re-derivam do cru (nenhum orfao de carga) ==='
REFRESH MATERIALIZED VIEW CONCURRENTLY mv_filme_servidor;
REFRESH MATERIALIZED VIEW CONCURRENTLY mv_filme_gestor;
REFRESH MATERIALIZED VIEW CONCURRENTLY mv_calculadora;
SELECT 'mv_filme_servidor' AS mv, count(*) FROM mv_filme_servidor
UNION ALL SELECT 'mv_filme_gestor', count(*) FROM mv_filme_gestor
UNION ALL SELECT 'mv_calculadora', count(*) FROM mv_calculadora;

\echo ''
\echo '=== [7] REVERSIBILIDADE — re-ATTACH da MESMA particao desfaz a retratacao ==='
ALTER TABLE evento ATTACH PARTITION :particao FOR VALUES IN (:id_lixo);
SELECT count(*) AS eventos_apos_reattach FROM evento;

\echo ''
\echo '=== [8] re-DETACH final — o estado que fica: carga retratada, ledger de pe ==='
\echo '(mesmo protocolo: o attach/detach acima e o ensaio de reversibilidade previsto'
\echo ' no procedimento, nao uma segunda retratacao — nao gera novo registro no ledger)'
ALTER TABLE evento DETACH PARTITION :particao;
REFRESH MATERIALIZED VIEW CONCURRENTLY mv_filme_servidor;
REFRESH MATERIALIZED VIEW CONCURRENTLY mv_filme_gestor;
REFRESH MATERIALIZED VIEW CONCURRENTLY mv_calculadora;

\echo ''
\echo '=== [9] estado FINAL ==='
SELECT id_carga, count(*) AS eventos FROM evento GROUP BY id_carga ORDER BY 2;
SELECT 'mv_filme_servidor' AS mv, count(*) FROM mv_filme_servidor
UNION ALL SELECT 'mv_filme_gestor', count(*) FROM mv_filme_gestor
UNION ALL SELECT 'mv_calculadora', count(*) FROM mv_calculadora;
SELECT id_carga, protocolo, destino, digest = :'digest' AS digest_ok, data_execucao
  FROM ledger_delecao ORDER BY data_execucao DESC LIMIT 3;
