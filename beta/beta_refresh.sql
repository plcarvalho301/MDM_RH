-- beta_refresh.sql — REFRESH das MVs de exposicao (ADR-007).
-- IMPORTANTE: o PRIMEIRO refresh de cada MV NAO pode ser CONCURRENTLY
-- (Postgres exige que a MV ja tenha sido populada uma vez). Este script
-- usa refresh normal — serve pro primeiro carregamento do beta.
-- Refreshes seguintes (producao, via Airflow) podem usar CONCURRENTLY,
-- pois os indices unicos ux_* ja existem no schema.
--
-- vw_foto e vw_lente sao VIEWS COMUNS — nao materializam, nao entram aqui.
-- Resolvem no SELECT automaticamente.

REFRESH MATERIALIZED VIEW mv_filme_servidor;
REFRESH MATERIALIZED VIEW mv_filme_gestor;
-- v0.12 (ADR-011): mv_calculadora dividiu em folha x PSS
REFRESH MATERIALIZED VIEW mv_calculadora_folha;
REFRESH MATERIALIZED VIEW mv_calculadora_pss;
