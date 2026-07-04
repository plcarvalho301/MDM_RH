-- =============================================================================
-- MDM-RH — Schema do golden record (FOTO + EVENTO)
-- versao: v0.6
-- ancora: 3_depara_foto_v0_3.md | 3_catalogo_eventos_v1.yaml | 3_catalogo_fontes_v0_1.md | ADR-007
-- =============================================================================
-- HISTORICO DE VERSAO (versao dentro do arquivo; nome sem versao)
--   v0.6 (este) — + VIEWS DE EXPOSICAO (ADR-007): objeto por fronteira de recorte,
--                 nao por painel. vw_foto, vw_lente (views); mv_filme_servidor,
--                 mv_filme_gestor, mv_calculadora (MVs). RH/Correg = GRANT direto,
--                 sem objeto. FOTO e KR 2.2 INTACTOS: cod_afastamento_vigente
--                 permanece na FOTO (face-foto); painel exibe booleano derivado.
--   v0.5 (descartado) — schema das DUAS naturezas, alinhado ao pipeline real:
--                 Valida -> Classifica -> {Atualiza FOTO, Registra EVENTO, Rejeita}.
--                 + tabela evento (event store, append) que faltava na v0.4.
--                 + tabela rejeito (quarentena = delta de incompletude / KR).
--                 Toda fonte (API ou Batch) cospe AS DUAS naturezas; a separacao
--                 acontece no Classifica, registro a registro — nao na fonte.
--   v0.4 (descartado) — so a FOTO (servidor). Presumia fonte = uma natureza so.
--                       Erro corrigido: Extrator e legados trazem foto E evento.
--   v0.1 (descartado) — PK = matricula (violava ADR-002).
-- -----------------------------------------------------------------------------
-- AS DUAS NATUREZAS (mecanica oposta — nao cabem na mesma tabela):
--   FOTO   = estado vigente. Tabela `servidor`. UPSERT por matricula = SOBRESCREVE.
--   EVENTO = serie datada. Tabela `evento`. INSERT = APPEND (nunca sobrescreve).
-- ORTOGONAL a isso: cod_mecanica = {ingestao (API viva), extracao (batch/lote)}.
--   A mecanica diz COMO chegou; a natureza diz O QUE e. Independentes.
-- CHAVE DO EVENTO inclui `matricula`, nao `cpf`: 1 CPF = N vinculos, cada vinculo
--   corre sua propria maquina de estados (catalogo_eventos, decisoes_em_aberto).
-- =============================================================================
 
 
-- =============================================================================
-- DOMINIOS (MDM nao e dono; vem do corpus — Tabela de Dominios eSocial/Sigepe)
-- Carregados ANTES de servidor/evento (referenciados por FK onde a lista e estavel).
-- =============================================================================
 
CREATE TABLE dom_situacao_vinculo (
    cod_situacao   text PRIMARY KEY,
    nome_situacao  text NOT NULL
);
 
CREATE TABLE dom_afastamento (
    cod_afastamento          text PRIMARY KEY,
    nome_afastamento         text NOT NULL,
    conta_efetivo_exercicio  text NOT NULL,   -- {sim, nao, parcial} — gancho KR 2.2
    impacto_previdenciario   text,
    CONSTRAINT ck_conta_efetivo
        CHECK (conta_efetivo_exercicio IN ('sim','nao','parcial'))
);
 
CREATE TABLE dom_unidade_eorg (
    cod_unidade   int PRIMARY KEY,
    nome_unidade  text NOT NULL
    -- estrutura SIORG/E-Org, chega RECONCILIADA (carga por planilha; nao-API).
);
 
-- Dominios de evento (catalogo_eventos_v1, Partes 1/2):
CREATE TABLE dom_sub_dominio (
    cod_sub_dominio   text PRIMARY KEY,        -- cadastro, vinculos, intercorrencias, compensacao, jornada
    descricao         text NOT NULL,
    classe_transicao_aplicavel boolean NOT NULL DEFAULT false  -- so vinculos/intercorrencias
);
 
CREATE TABLE dom_classe_transicao (
    cod_classe_transicao text PRIMARY KEY,     -- INICIO, AFASTA, RETOMA, ALTERA, CEDE, ENCERRA
    descricao            text NOT NULL
);
 
CREATE TABLE dom_tipo_evento (
    cod_tipo_evento      text PRIMARY KEY,      -- ADMISSAO, AFASTAMENTO, CESSAO, FECHAMENTO_FOLHA...
    cod_sub_dominio      text NOT NULL REFERENCES dom_sub_dominio(cod_sub_dominio),
    cod_classe_transicao text REFERENCES dom_classe_transicao(cod_classe_transicao), -- nulo se aditivo
    codigo_esocial       text,                  -- S-2200, S-2230... (nulo se sem leiaute)
    ativo                boolean NOT NULL DEFAULT true  -- false = catalogado mas fora da Calculadora
);
 
-- Dominios de cargo/carreira — lista controlada A CONFIRMAR (de-para v0.3).
-- Criados; FK aplicada so quando a fonte confirmar lista. Ate la, text solto.
CREATE TABLE dom_cargo          ( cod text PRIMARY KEY, nome text NOT NULL );
CREATE TABLE dom_classe         ( cod text PRIMARY KEY, nome text NOT NULL );
CREATE TABLE dom_padrao         ( cod text PRIMARY KEY, nome text NOT NULL );
CREATE TABLE dom_nivel_cargo    ( cod text PRIMARY KEY, nome text NOT NULL );
CREATE TABLE dom_funcao         ( cod text PRIMARY KEY, nome text NOT NULL );
CREATE TABLE dom_regime_juridico( cod text PRIMARY KEY, nome text NOT NULL );
 
 
-- =============================================================================
-- FOTO — tabela `servidor`. Destino do passo "Atualiza".
-- 1 linha por VINCULO vigente (N vinculos por CPF). UPSERT = SOBRESCREVE.
-- =============================================================================
CREATE TABLE servidor (
    id_vinculo            uuid PRIMARY KEY DEFAULT gen_random_uuid(),  -- ADR-002
    matricula_funcional   text NOT NULL UNIQUE,        -- chave soberana exposta, 7 digitos
    cpf                   text NOT NULL,
    nome                  text NOT NULL,
    data_nascimento       date NOT NULL,
    -- (idade NAO existe — derivado; de-para v0.3)
 
    cargo                 text NOT NULL,               -- alfanumerico
    classe                text,                        -- alfanumerico ('C')
    padrao                text,                        -- alfanumerico ('II')
    sigla_nivel_cargo     text,                        -- NS/NI/NA...
 
    funcao_comissionada       text,
    nova_funcao               text,                    -- funcao em transicao (raro)
    data_ingresso_nova_funcao date,
 
    cod_unidade_lotacao   int NOT NULL,                -- SEM FK de proposito (orfao = KR 2.1)
    cod_unidade_exercicio int,
    origem_unidade        text NOT NULL,               -- {SIAPE, SIORG}
 
    situacao_funcional    text NOT NULL,               -- estado resolvido vigente
    regime_juridico       text,
    data_exercicio_no_orgao date,
 
    cod_afastamento_vigente text,                      -- nulo = exercicio normal
 
    data_referencia       date NOT NULL,               -- D-1 desta foto
    cod_mecanica          text NOT NULL DEFAULT 'ingestao',
 
    CONSTRAINT fk_situacao FOREIGN KEY (situacao_funcional)
        REFERENCES dom_situacao_vinculo(cod_situacao),
    CONSTRAINT fk_afastam  FOREIGN KEY (cod_afastamento_vigente)
        REFERENCES dom_afastamento(cod_afastamento),
    CONSTRAINT fk_regime   FOREIGN KEY (regime_juridico)
        REFERENCES dom_regime_juridico(cod),
    CONSTRAINT ck_cpf       CHECK (cpf ~ '^[0-9]{11}$'),
    CONSTRAINT ck_matricula CHECK (matricula_funcional ~ '^[0-9]{7}$'),
    CONSTRAINT ck_mecanica  CHECK (cod_mecanica IN ('ingestao','extracao'))
);
 
CREATE INDEX ix_servidor_cpf      ON servidor(cpf);
CREATE INDEX ix_servidor_lotacao  ON servidor(cod_unidade_lotacao);
CREATE INDEX ix_servidor_situacao ON servidor(situacao_funcional);
 
 
-- =============================================================================
-- EVENTO — event store. Destino do passo "Registra". INSERT = APPEND.
-- Envelope tipado + payload JSONB (o shape de cada tipo vive no catalogo, nao
-- em coluna — evita ALTER a cada tipo novo). NB: nao ha tabela de staging; a
-- forma crua/parseada vive em memoria do leitor e some. So persistem os 3
-- objetos: servidor, evento, rejeito (ver ADR-006 e 3_dag_ingestao v0.4).
-- =============================================================================
CREATE TABLE evento (
    id_evento         uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    matricula_funcional text NOT NULL,         -- CHAVE por VINCULO, nao por CPF (acumulacao licita)
    cpf               text NOT NULL,           -- denormalizado p/ agregacao; nao e a chave da serie
    cod_tipo_evento   text NOT NULL REFERENCES dom_tipo_evento(cod_tipo_evento),
    data_evento       date NOT NULL,           -- data do FATO (nao da carga) — ordena o replay
    payload           jsonb NOT NULL,          -- shape por tipo (catalogo_eventos)
 
    -- Proveniencia viaja DENTRO do evento (carimbada no Classifica):
    cod_mecanica      text NOT NULL,           -- {ingestao, extracao}
    fonte             text NOT NULL,           -- 'API_SIAPE_OCORRENCIAS', 'EXTRATOR:SIAPE-ANO-MES-SSER', 'OCR_PAPEL'...
    grau_confianca    text NOT NULL DEFAULT 'alto',  -- alto | medio | baixo (OCR/papel = baixo)
    data_carga        timestamptz NOT NULL DEFAULT now(),
 
    CONSTRAINT ck_ev_cpf       CHECK (cpf ~ '^[0-9]{11}$'),
    CONSTRAINT ck_ev_matricula CHECK (matricula_funcional ~ '^[0-9]{7}$'),
    CONSTRAINT ck_ev_mecanica  CHECK (cod_mecanica IN ('ingestao','extracao')),
    CONSTRAINT ck_ev_confianca CHECK (grau_confianca IN ('alto','medio','baixo'))
);
 
-- Replay deriva estado por VINCULO numa data: filtra matricula, ordena por data_evento.
CREATE INDEX ix_evento_replay ON evento(matricula_funcional, data_evento);
CREATE INDEX ix_evento_tipo   ON evento(cod_tipo_evento);
CREATE INDEX ix_evento_cpf    ON evento(cpf);
-- Dedup de afastamento (chave candidata do catalogo; edge cancelado/reiniciado e do dev):
CREATE INDEX ix_evento_payload ON evento USING gin (payload);
 
 
-- =============================================================================
-- REJEITO — quarentena. Destino do passo "Rejeita". NAO e descarte:
-- a contagem aqui E o delta de incompletude (motor de adocao). Saida medida.
-- =============================================================================
CREATE TABLE rejeito (
    id_rejeito     uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    fonte          text NOT NULL,
    cod_mecanica   text NOT NULL,
    motivo         text NOT NULL,              -- 'matricula_malformada', 'data_ausente', 'fk_situacao_inexistente'...
    registro_bruto jsonb NOT NULL,             -- a linha torta, crua, p/ auditoria/reprocesso
    data_rejeicao  timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX ix_rejeito_fonte  ON rejeito(fonte);
CREATE INDEX ix_rejeito_motivo ON rejeito(motivo);
 
 
-- =============================================================================
-- VIEWS DE KR (caem direto do schema)
-- =============================================================================
 
-- KR 2.1 — orfao estrutural: lotacao que NAO resolve em unidade E-Org valida.
-- Anti-join — por isso lotacao nao tem FK (orfao precisa CARREGAR p/ ser contado).
CREATE VIEW vw_orfao_estrutural AS
SELECT s.id_vinculo, s.matricula_funcional, s.nome,
       s.cod_unidade_lotacao, s.origem_unidade
FROM servidor s
LEFT JOIN dom_unidade_eorg u ON u.cod_unidade = s.cod_unidade_lotacao
WHERE u.cod_unidade IS NULL;
 
-- KR 2.2 (gancho) — afastado que ainda conta como exercicio efetivo.
-- NAO fecha o KR sozinho (depende de tempestividade — dado do HISTORICO).
CREATE VIEW vw_afastado_conta_exercicio AS
SELECT s.id_vinculo, s.matricula_funcional, s.nome,
       a.cod_afastamento, a.nome_afastamento, a.conta_efetivo_exercicio
FROM servidor s
JOIN dom_afastamento a ON a.cod_afastamento = s.cod_afastamento_vigente
WHERE a.conta_efetivo_exercicio IN ('sim','parcial');
 
-- Delta de incompletude — quarentena por fonte. Motor de adocao (motivo de painel).
CREATE VIEW vw_delta_incompletude AS
SELECT fonte, motivo, count(*) AS qtd
FROM rejeito
GROUP BY fonte, motivo;
 
 
-- =============================================================================
-- VIEWS DE EXPOSICAO (ADR-007) — o painel le ESTES objetos, nunca a base.
-- Objeto por FRONTEIRA DE RECORTE, nao por painel. Materializacao (view x MV)
-- por CUSTO: MV so quando a copia fisica paga aluguel (densidade que doi no
-- clique ou isolamento do banco vivo). Corte de payload no DDL, nao no Power BI.
-- Seguranca de acesso NAO mora aqui — e infra (on-prem, acesso pessoa a pessoa).
--   Foto/Lente   -> view comum (base leve; MV nao paga aluguel).
--   Filme S/G    -> 2 MVs (payloads distintos -> objetos distintos).
--   Calculadora  -> MV (serie densa por matricula).
--   RH/Correg    -> sem objeto; GRANT SELECT direto em servidor+evento.
-- REFRESH das MVs = processamento (relogio Airflow, D-1). Ver 3_dag_ingestao.
-- =============================================================================
 
-- ── Foto de Hoje ────────────────────────────────────────────────────────────
-- View comum sobre a FOTO. `afastado` e booleano DERIVADO (painel nao mostra
-- codigo cru). A coluna cod_afastamento_vigente PERMANECE na FOTO (face-foto;
-- serie datada vive no evento AFASTAMENTO) — ADR-007.
CREATE VIEW vw_foto AS
SELECT s.id_vinculo,
       s.matricula_funcional,
       s.cpf,
       s.nome,
       s.data_nascimento,
       s.cargo, s.classe, s.padrao, s.sigla_nivel_cargo,
       s.funcao_comissionada, s.nova_funcao, s.data_ingresso_nova_funcao,
       s.cod_unidade_lotacao, s.cod_unidade_exercicio, s.origem_unidade,
       s.situacao_funcional, s.regime_juridico, s.data_exercicio_no_orgao,
       (s.cod_afastamento_vigente IS NOT NULL) AS afastado,   -- booleano de exposicao
       s.data_referencia
FROM servidor s;
 
-- ── Lente Estrategica ───────────────────────────────────────────────────────
-- View comum SOBRE A FOTO (agrega numeros sobre o que a Foto ja expoe). Mesma
-- fronteira da Foto. Enquanto agregar sobre FOTO nao toca EVENTO — o sensivel
-- e EVENTO por natureza (afastamento-saude, disciplinar). Indicador agregado
-- sobre EVENTO (ex.: suspensoes x uorg) e outra fonte, outro objeto: fora daqui.
CREATE VIEW vw_lente AS
SELECT cod_unidade_lotacao,
       count(*)                                        AS headcount,
       count(*) FILTER (WHERE afastado)                AS afastados,
       count(*) FILTER (WHERE funcao_comissionada IS NOT NULL) AS com_funcao
FROM vw_foto
GROUP BY cod_unidade_lotacao;
 
-- ── Filme-Servidor ──────────────────────────────────────────────────────────
-- MV: replay da serie de eventos do proprio servidor. Payload CHEIO.
-- RLS no Power BI recorta linha -> propria matricula (de-para AD<->matricula).
-- REFRESH CONCURRENTLY exige indice unico (abaixo).
CREATE MATERIALIZED VIEW mv_filme_servidor AS
SELECT e.id_evento,
       e.matricula_funcional,
       e.cpf,
       e.cod_tipo_evento,
       te.cod_sub_dominio,
       e.data_evento,
       e.payload,
       e.fonte,
       e.grau_confianca
FROM evento e
JOIN dom_tipo_evento te ON te.cod_tipo_evento = e.cod_tipo_evento;
 
CREATE UNIQUE INDEX ux_mv_filme_servidor ON mv_filme_servidor(id_evento);
CREATE INDEX ix_mv_filme_servidor_mat ON mv_filme_servidor(matricula_funcional, data_evento);
 
-- ── Filme-Gestor ────────────────────────────────────────────────────────────
-- MV: payload REDUZIDO (gerencial). Objeto SEPARADO do Filme-Servidor porque o
-- payload difere (o corte gerencial e DDL, nao SELECT sobre base comum).
-- Recorte gerencial = subconjunto de tipos de evento com leitura de gestao
-- (provimento/cargo, cessao, desempenho/PGD). RLS -> sub-arvore do gestor
-- (arvore de cargos, insumo externo). O payload sai reduzido: expoe o envelope
-- e um recorte do JSONB, nao o payload cheio.
CREATE MATERIALIZED VIEW mv_filme_gestor AS
SELECT e.id_evento,
       e.matricula_funcional,
       e.cod_tipo_evento,
       te.cod_sub_dominio,
       e.data_evento,
       -- payload reduzido: so as chaves gerenciais (o recorte fino fecha no refinamento)
       (e.payload - 'valor' - 'remuneracao' - 'base_calculo') AS payload_gerencial,
       e.fonte
FROM evento e
JOIN dom_tipo_evento te ON te.cod_tipo_evento = e.cod_tipo_evento
WHERE te.cod_sub_dominio IN ('vinculos','desempenho','jornada');
 
CREATE UNIQUE INDEX ux_mv_filme_gestor ON mv_filme_gestor(id_evento);
CREATE INDEX ix_mv_filme_gestor_mat ON mv_filme_gestor(matricula_funcional, data_evento);
 
-- ── Calculadora do RH ───────────────────────────────────────────────────────
-- MV: serie densa PSS/financeiro por matricula (servidor de 1992 = 30+ anos).
-- Materializa porque a densidade doi no clique — nao por fronteira.
-- Le eventos do sub-dominio compensacao (PSS apurado, base, afastamento datado).
CREATE MATERIALIZED VIEW mv_calculadora AS
SELECT e.id_evento,
       e.matricula_funcional,
       e.cpf,
       e.cod_tipo_evento,
       e.data_evento,
       e.payload,
       e.fonte,
       e.grau_confianca
FROM evento e
JOIN dom_tipo_evento te ON te.cod_tipo_evento = e.cod_tipo_evento
WHERE te.cod_sub_dominio = 'compensacao';
 
CREATE UNIQUE INDEX ux_mv_calculadora ON mv_calculadora(id_evento);
CREATE INDEX ix_mv_calculadora_mat ON mv_calculadora(matricula_funcional, data_evento);
 
-- ── Vitrine ODBC das MVs ────────────────────────────────────────────────────
-- Casca fina: SQLTables do driver psqlODBC nao enumera relkind='m' (MV) no
-- Navegador do Power BI, so 'r'/'v'. Sem isto a MV existe no banco mas fica
-- invisivel pro conector — nao e redesenho da fronteira (ADR-007), so
-- compatibilidade de catalogo. SELECT trivial sobre a MV ja materializada,
-- nao toca evento.
CREATE VIEW vw_mv_filme_servidor AS SELECT * FROM mv_filme_servidor;
CREATE VIEW vw_mv_filme_gestor    AS SELECT * FROM mv_filme_gestor;
CREATE VIEW vw_mv_calculadora     AS SELECT * FROM mv_calculadora;

-- ── RH / Corregedoria — NAO e objeto de exposicao ──────────────────────────
-- Acesso privilegiado documentado (ADR-007): GRANT SELECT direto em
-- servidor+evento, role minimo (grao de TABELA nomeada, nao database).
-- Fora do escopo "4 paineis". Exemplo (role e nome ilustrativos):
--   GRANT SELECT ON servidor, evento TO role_rh_correg;