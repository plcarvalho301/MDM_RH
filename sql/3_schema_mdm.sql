-- =============================================================================
-- MDM-RH — Schema do golden record (FOTO + EVENTO)
-- versao: v0.11
-- ancora: 3_depara_foto_v0_3.md | 3_catalogo_eventos_v1.yaml (v1.1) | ADR-007 | ADR-008 | ADR-009
-- =============================================================================
-- HISTORICO DE VERSAO (versao dentro do arquivo; nome sem versao)
--   v0.11 (este) — REGRAS DE MODELO viram DADO (o gerador/replay leem do banco, nao
--                 hardcode; regra nova = UPDATE na dimensao, sem deploy):
--                 (1) dom_afastamento ganha `deriva_situacao` (afast vigente que muda
--                     a situacao: 40->CEDIDO, 31->DISPONIBILIDADE) e `pausa_folha`
--                     (afast sem remuneracao: folha pula o mes; hoje so o 05).
--                 (2) vw_foto: revertido o nome de funcao_comissionada (CCE/FCE ja e
--                     legivel; nome REAL e sensivel, so no modelo live).
--   v0.10 — ROTULOS (nomes amigaveis) p/ o painel parar de mostrar codigo cru:
--                 (1) dom_tipo_evento ganha coluna `nome` (era a UNICA dimensao sem
--                     rotulo — o Filme mostrava o codigo cru do tipo).
--                 (2) vw_foto enriquecida: nome_unidade_lotacao/exercicio,
--                     nome_afastamento_vigente, nome_regime, nome_funcao_comissionada
--                     (LEFT JOIN; codigo permanece na coluna).
--                 (3) vw_filme_servidor / vw_filme_gestor: views REGULARES (ODBC ve)
--                     sobre as MVs com os codigos resolvidos em nome — ponto de
--                     conexao do painel que le plano, sem montar relacao no PBI.
--                 Frase amigavel (descritor/assembler) fica p/ o refinamento de UX.
--   v0.9 — PLANIFICACAO DE CHAVES DE PAYLOAD NAS MVs DE FILME + GESTOR VE
--                 INTERCORRENCIAS (sessao 2026-07-05, handoff PBI rodada 1):
--                 (1) O painel nao relaciona chave embutida em JSONB. Chaves que o
--                     Power BI precisa como FILTRO (relacao com dimensao) sao
--                     EXTRAIDAS do payload como COLUNA PLANA via ->> no SELECT da MV.
--                     Filme-servidor e filme-gestor ganham: cod_afastamento,
--                     data_inicio, data_fim (AFASTAMENTO/CESSAO); cod_motivo_deslig,
--                     data_desligamento (DESLIGAMENTO). A COLUNA CARREGA O CODIGO;
--                     a TRADUCAO (friendly name) vive na DIMENSAO (dom_afastamento,
--                     dom_motivo_deslig), RH-editavel por UPDATE sem rebuild de MV.
--                     PRINCIPIO: codigo nunca aparece cru pro humano — sempre ha
--                     friendly name na dimensao relacionada. Vale p/ todo codigo.
--                 (2) Filme-gestor passa a ver INTERCORRENCIAS (WHERE ganha o
--                     sub-dominio). Decisao de negocio: o gestor tem que ver
--                     afastamento do subordinado — descasamento nessa serie e
--                     exatamente o que quebra a perna do RH quando passa batido.
--                     cod_afastamento e CATEGORIA administrativa (S-2230), NAO
--                     diagnostico clinico — o eSocial nao carrega CID. Sem vazamento.
--                 (3) Filme-gestor DEIXA DE SUBIR payload cru. Antes: payload_gerencial
--                     (payload menos 3 chaves financeiras, denylist). Agora: envelope
--                     + SO as colunas planas nomeadas. O JSONB nunca sobe no gestor —
--                     o motivo fino (se existisse) fica na base (evento), acessivel
--                     so por GRANT direto (RH/Correg). Vazamento fechado por
--                     CONSTRUCAO (nao ha payload na view), nao por denylist fragil.
--                 (4) COALESCENCIA DE INTERVALO (ADR-008): afastamento/cessao fecham
--                     por SEGUNDO registro imutavel (data_fim preenchida; data_carga
--                     mais recente vence). A MV NAO colapsa a linha (Filme mostra a
--                     SERIE — dois registros sao dois fatos de carga). Em vez disso,
--                     coluna derivada `intervalo_vigente` (bool) marca, por janela
--                     (matricula, cod_afastamento/cessao-chave, data_inicio), o
--                     registro de data_carga mais recente. PBI filtra por ela p/
--                     "estado do intervalo"; mostra tudo p/ "trajetoria". Tipos
--                     ADITIVOS (folha, provimento etc.) sao sempre intervalo_vigente=
--                     true (nao tem par a coalescer) — por isso DISTINCT ON global
--                     seria ERRADO: quebraria folha suplementar (2 fechamentos da
--                     mesma competencia que SOMAM, nao coalescem).
--                 (5) CESSAO aparece 2x de proposito (evento CESSAO em vinculos +
--                     AFASTAMENTO cod.40 em intercorrencias): o gestor ve os dois. E
--                     o descasamento-espelho que o RH PRECISA ver. Colapso/filtro
--                     disso e UX do PBI (se trepar linha demais), NAO corte no dado.
--                     Reconciliacao S-2231 x S-2230 cod.40 segue aberta (catalogo).
--                 (6) mv_calculadora NAO recebe as planas de afastamento/desligamento:
--                     le so `compensacao` (FECHAMENTO_FOLHA). Afastamento nao e insumo
--                     de folha; cod_afastamento nao esta no payload de compensacao.
--                 (7) vw_mv_* seguem SELECT * (auto-espelham as colunas novas; vitrine
--                     ODBC nao muda — a tese da v0.7 se confirma na pratica).
--                 SHAPE DA MASSA: a cadeia EVENTO ainda nao tem massa gerada (massa
--                 v0.3 e retrofit so da FOTO). Estas MVs compilam e ficam VAZIAS ate
--                 a massa de evento existir — esperado. O DDL segue o shape do
--                 catalogo_eventos_v1.yaml (fonte do payload), nao dado existente.
--   v0.8 — RETRATACAO OPERACIONAL + MOTIVOS LOCAIS (ADR-008/ADR-009, sessao 2026-07-05):
--                 (1) `evento` vira TABELA PARTICIONADA por LIST(id_carga). id_carga (uuid,
--                     NOT NULL) entra no envelope; PK composta (id_carga, id_evento) —
--                     exigencia do Postgres p/ PK em particionada. Uma particao por carga
--                     (fn_particao_carga cria; SEM particao default DE PROPOSITO: carga sem
--                     particao aberta = erro na cara, nao stray silencioso).
--                     Remocao de carga defeituosa = DETACH PARTITION (instantaneo, sem DELETE
--                     de milhoes de linhas, sem bloat, reversivel por re-ATTACH). Particao
--                     destacada = cold storage. Ver ADR-009 + procedimento na secao RETRATACAO.
--                 (2) `ledger_delecao` (fora das particoes — sobrevive ao DETACH) +
--                     fn_manifesto_carga(uuid): o MESMO manifesto roda ANTES (superficie de
--                     decisao da assinatura: contagem, quebra, faixa, digest, amostra) e fica
--                     gravado DEPOIS (proveniencia da carga-de-delecao). Digest md5 da lista
--                     ordenada de id_evento = prova do que saiu.
--                 (3) `rejeito` tambem carimba id_carga (rastreio simetrico).
--                 (4) dom_motivo_deslig CRIADA (seed v0.2 popula: mtvDeslig eSocial + 3
--                     motivos LOCAIS nao-eSocial: DEMI_OFICIO, CASS_APOSENT, ANUL_PROVIMENTO —
--                     via ADR-004, motivo no payload; dom aberto por dado, carga xlsx/csv).
--                 (5) FOTO (servidor) NAO ganha id_carga: sobrescreve em D-1, a "carga" dela
--                     e a ultima; retratacao de FOTO = proximo upsert. Fora do problema.
--                 INVARIANTE (ADR-009): projecoes SEMPRE re-derivadas do cru (REFRESH MV,
--                 upsert FOTO) — nunca patch incremental que perca rastro de carga; senao o
--                 DETACH limpa a base e deixa orfao na projecao.
--   v0.7 — + VITRINE ODBC DAS MVs (compat de catalogo, NAO nova fronteira):
--                 3 views finas de passagem (vw_mv_filme_servidor, vw_mv_filme_gestor,
--                 vw_mv_calculadora), SELECT * sobre a MV homonima. Motivo: o driver
--                 psqlODBC nao enumera relkind='m' (materialized view) no Navegador do
--                 Power BI — as MVs existem no banco mas ficam invisiveis pro conector.
--                 A view fina reexpoe a MV no catalogo. NAO move a fronteira da ADR-007:
--                 quem materializa continua sendo a MV (a view fina nao materializa nada);
--                 o GRANT/RLS continua desenhado sobre a MV. SELECT * de proposito —
--                 a fronteira de payload ja foi aplicada na MV; a view fina e transparente,
--                 entao alterar a MV nao exige tocar a view fina (auto-espelha o shape).
--                 Validado e2e contra Postgres 18.4 real em 2026-07-04 (cadeia FOTO +
--                 cadeia EVENTO + 1o dashboard Power BI via DSN ODBC).
--   v0.6 (estendido por v0.7) — + VIEWS DE EXPOSICAO (ADR-007): objeto por fronteira de recorte,
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
    -- v0.11: REGRAS DE MODELO viram DADO (o gerador/replay leem daqui, nao hardcode).
    deriva_situacao          text,            -- afast vigente que MUDA a situacao derivada
                                              --   (CEDIDO/DISPONIBILIDADE); null = mantem ATIVO
    pausa_folha              boolean NOT NULL DEFAULT false,  -- afast sem remuneracao: folha pula o mes
    CONSTRAINT ck_conta_efetivo
        CHECK (conta_efetivo_exercicio IN ('sim','nao','parcial')),
    CONSTRAINT ck_deriva_situacao
        CHECK (deriva_situacao IS NULL OR deriva_situacao IN ('CEDIDO','DISPONIBILIDADE'))
);

-- v0.8 — referenciada pelo PAYLOAD de DESLIGAMENTO (jsonb), sem FK de coluna
-- (o payload valida na aplicacao/classifica). Comporta codigos eSocial (mtvDeslig)
-- E motivos LOCAIS nao-eSocial (dono=interno; entram por carga xlsx/csv — a via
-- "acrescentar evento novo no futuro"). e_esocial distingue as duas origens para
-- que codigo local NUNCA seja tratado como leiaute eSocial rio abaixo.
CREATE TABLE dom_motivo_deslig (
    cod_motivo_deslig  text PRIMARY KEY,       -- '07','38'... (eSocial) | 'CASS_APOSENT'... (local)
    nome_motivo        text NOT NULL,
    situacao_resultante text NOT NULL,          -- {DESLIGADO, INATIVO, TRANSFERE}
    e_esocial          boolean NOT NULL DEFAULT true,
    CONSTRAINT ck_motivo_resultado CHECK (situacao_resultante IN ('DESLIGADO','INATIVO','TRANSFERE'))
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
    nome                 text NOT NULL,         -- rotulo humano p/ o painel (o Filme mostra ISTO, nao o codigo)
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
-- v0.8: PARTICIONADA POR LIST(id_carga) — a unidade de retratacao e a CARGA (ADR-009).
-- PK composta (id_carga, id_evento): Postgres exige a chave de particao na PK.
-- id_evento continua uuid — unicidade global e estatistica (uuid), nao por constraint.
-- SEM particao DEFAULT de proposito: INSERT com id_carga sem particao aberta ERRA —
-- forca a disciplina "toda carga abre sua particao" (fn_particao_carga) e impede
-- stray silencioso que o DETACH nao alcancaria.
CREATE TABLE evento (
    id_evento         uuid NOT NULL DEFAULT gen_random_uuid(),
    id_carga          uuid NOT NULL,           -- v0.8: unidade de retratacao (ADR-009)
    matricula_funcional text NOT NULL,         -- CHAVE por VINCULO, nao por CPF (acumulacao licita)
    cpf               text NOT NULL,           -- denormalizado p/ agregacao; nao e a chave da serie
    cod_tipo_evento   text NOT NULL REFERENCES dom_tipo_evento(cod_tipo_evento),
    data_evento       date NOT NULL,           -- data do FATO (nao da carga) — ordena o replay
    payload           jsonb NOT NULL,          -- shape por tipo (catalogo_eventos)

    -- Proveniencia viaja DENTRO do evento (carimbada no Classifica):
    cod_mecanica      text NOT NULL,           -- {ingestao, extracao}
    fonte             text NOT NULL,           -- 'API_SIAPE_OCORRENCIAS', 'EXTRATOR:SIAPE-ANO-MES-SSER', 'OCR_PAPEL'...
    grau_confianca    text NOT NULL DEFAULT 'alto',  -- alto | medio | baixo (OCR/papel = baixo)
    data_carga        timestamptz NOT NULL DEFAULT now(),  -- desempate de coalescencia (ADR-008: mais recente vence)

    CONSTRAINT pk_evento       PRIMARY KEY (id_carga, id_evento),
    CONSTRAINT ck_ev_cpf       CHECK (cpf ~ '^[0-9]{11}$'),
    CONSTRAINT ck_ev_matricula CHECK (matricula_funcional ~ '^[0-9]{7}$'),
    CONSTRAINT ck_ev_mecanica  CHECK (cod_mecanica IN ('ingestao','extracao')),
    CONSTRAINT ck_ev_confianca CHECK (grau_confianca IN ('alto','medio','baixo'))
) PARTITION BY LIST (id_carga);

-- Abre a particao de UMA carga. O loader chama ANTES do primeiro INSERT/COPY da carga.
-- Nome deterministico: evento_c_<uuid sem hifens> (39 chars, cabe no limite de 63).
CREATE OR REPLACE FUNCTION fn_particao_carga(p_id_carga uuid) RETURNS text
LANGUAGE plpgsql AS $$
DECLARE v_nome text := 'evento_c_' || replace(p_id_carga::text, '-', '');
BEGIN
    EXECUTE format('CREATE TABLE IF NOT EXISTS %I PARTITION OF evento FOR VALUES IN (%L)',
                   v_nome, p_id_carga);
    RETURN v_nome;
END $$;

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
    id_carga       uuid NOT NULL,              -- v0.8: rastreio simetrico ao evento
    fonte          text NOT NULL,
    cod_mecanica   text NOT NULL,
    motivo         text NOT NULL,              -- 'matricula_malformada', 'data_ausente', 'fk_situacao_inexistente'...
    registro_bruto jsonb NOT NULL,             -- a linha torta, crua, p/ auditoria/reprocesso
    data_rejeicao  timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX ix_rejeito_fonte  ON rejeito(fonte);
CREATE INDEX ix_rejeito_motivo ON rejeito(motivo);
CREATE INDEX ix_rejeito_carga  ON rejeito(id_carga);


-- =============================================================================
-- RETRATACAO OPERACIONAL DE CARGA (v0.8, ADR-009)
-- -----------------------------------------------------------------------------
-- DUAS COISAS QUE NAO SE CONFUNDEM:
--   Reversao de DOMINIO  = o fato aconteceu e reverte estado legitimo (cassacao,
--                          anulacao, reintegracao). E EVENTO, com motivo proprio.
--                          Serie honesta, nada sai da base.
--   Retratacao OPERACIONAL = o registro nunca deveria ter existido (carga com erro
--                          material, duplicata, OCR trocado). E DEFEITO DE DADO.
--                          Sai da base quente — por CARGA, nunca linha a linha.
-- MECANICA: DETACH PARTITION. Instantaneo, sem DELETE em massa, sem bloat, e
-- REVERSIVEL (a propria delecao pode estar errada — re-ATTACH desfaz). A particao
-- destacada E o cold storage (mover de tablespace/dump e opcional, por fonte:
-- re-executavel pode descartar; extracao/papel NAO — o garimpo nao volta).
-- GOVERNANCA: RH e soberano. O MDM entrega o MEIO (manifesto + protocolo + detach);
-- quem assina e dono da consequencia. Acesso: exclusivo diretora RH + TI, com
-- aceite protocolado — o protocolo E a proveniencia da carga-de-delecao.
-- =============================================================================

-- Ledger — FORA das particoes de proposito: o registro da delecao sobrevive ao
-- DETACH que ele audita. Se morasse na particao, a prova sairia junto com o dado.
CREATE TABLE ledger_delecao (
    id_delecao      uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    id_carga        uuid NOT NULL,
    manifesto       jsonb NOT NULL,            -- resultado de fn_manifesto_carga NO MOMENTO da assinatura
    digest          text  NOT NULL,            -- copia de 1o nivel do digest (busca sem abrir o jsonb)
    protocolo       text  NOT NULL,            -- n. do aceite protocolado (SEI) — a autorizacao
    autorizado_por  text  NOT NULL,            -- diretora do RH
    executado_por   text  NOT NULL,            -- TI
    motivo          text  NOT NULL,            -- 'erro material na carga de aposentados 2026-08', ...
    destino         text  NOT NULL,            -- {cold, descartado} — descartado SO p/ fonte re-executavel
    data_execucao   timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT ck_destino CHECK (destino IN ('cold','descartado'))
);
CREATE INDEX ix_ledger_carga ON ledger_delecao(id_carga);

-- Manifesto de carga — UM SELECT, DOIS USOS (mesma query, dois momentos):
--   ANTES do DETACH: superficie de decisao — o que a diretora VE antes de assinar.
--   DEPOIS: o mesmo jsonb aterrissa em ledger_delecao.manifesto (prova do que saiu).
-- digest = md5 da lista ordenada de id_evento: determinisco, re-verificavel contra
-- a particao destacada enquanto ela existir em cold.
CREATE OR REPLACE FUNCTION fn_manifesto_carga(p_id_carga uuid) RETURNS jsonb
LANGUAGE sql STABLE AS $$
SELECT jsonb_build_object(
    'id_carga',          p_id_carga,
    'gerado_em',         now(),
    'total_eventos',     (SELECT count(*)                            FROM evento WHERE id_carga = p_id_carga),
    'vinculos_afetados', (SELECT count(DISTINCT matricula_funcional) FROM evento WHERE id_carga = p_id_carga),
    'pessoas_afetadas',  (SELECT count(DISTINCT cpf)                 FROM evento WHERE id_carga = p_id_carga),
    'fato_de',           (SELECT min(data_evento)                    FROM evento WHERE id_carga = p_id_carga),
    'fato_ate',          (SELECT max(data_evento)                    FROM evento WHERE id_carga = p_id_carga),
    'por_tipo',          (SELECT coalesce(jsonb_object_agg(cod_tipo_evento, n), '{}'::jsonb)
                          FROM (SELECT cod_tipo_evento, count(*) n FROM evento
                                WHERE id_carga = p_id_carga GROUP BY 1) t),
    'por_fonte',         (SELECT coalesce(jsonb_object_agg(fonte, n), '{}'::jsonb)
                          FROM (SELECT fonte, count(*) n FROM evento
                                WHERE id_carga = p_id_carga GROUP BY 1) t),
    'digest',            (SELECT md5(string_agg(id_evento::text, ',' ORDER BY id_evento))
                          FROM evento WHERE id_carga = p_id_carga),
    'amostra',           (SELECT coalesce(jsonb_agg(a), '[]'::jsonb) FROM (
                              SELECT matricula_funcional, cod_tipo_evento, data_evento, payload
                              FROM evento WHERE id_carga = p_id_carga
                              ORDER BY data_evento LIMIT 20) a)
);
$$;

-- PROCEDIMENTO (manual, 2 pessoas, passos na ordem — nao ha atalho):
--   1. SELECT fn_manifesto_carga(:carga);            -- diretora LE o alcance
--   2. Aceite protocolado (SEI) referenciando o digest do manifesto.
--   3. INSERT INTO ledger_delecao (id_carga, manifesto, digest, protocolo,
--        autorizado_por, executado_por, motivo, destino) VALUES (...);
--   4. ALTER TABLE evento DETACH PARTITION evento_c_<uuid>;
--   5. destino='cold':      ALTER TABLE evento_c_<uuid> SET TABLESPACE <frio>;  (ou pg_dump)
--      destino='descartado': DROP TABLE evento_c_<uuid>;  -- SO fonte re-executavel
--   6. REFRESH das MVs + proximo ciclo FOTO — a projecao re-deriva do cru
--      (INVARIANTE ADR-009: nenhuma projecao cacheia efeito de evento sem rastro de carga).
--   Reversao da propria delecao (destino=cold): ALTER TABLE evento ATTACH PARTITION
--      evento_c_<uuid> FOR VALUES IN ('<uuid>'); + REFRESH.
-- ACESSO (aterrissar por GRANT no ambiente; roles ilustrativos):
--   REVOKE ALL ON ledger_delecao FROM PUBLIC;
--   GRANT SELECT, INSERT ON ledger_delecao TO role_delecao_rh_ti;  -- diretora RH + TI, so
--   (DETACH exige ownership da tabela — operacao de TI por definicao.)


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
-- v0.10: + ROTULOS resolvidos (LEFT JOIN nas dimensoes). O painel le nome, nao
--   codigo; LEFT JOIN p/ orfao/nulo nao sumir a linha (orfao => nome_unidade nulo,
--   que E o sinal do KR 2.1). Codigo permanece na coluna (relacao no PBI ainda
--   possivel); o nome vem pronto p/ quem nao quer montar relacao.
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
       s.data_referencia,
       -- rotulos humanos (o que o painel exibe):
       ul.nome_unidade      AS nome_unidade_lotacao,
       ue.nome_unidade      AS nome_unidade_exercicio,
       af.nome_afastamento  AS nome_afastamento_vigente,
       rj.nome              AS nome_regime
       -- funcao_comissionada (CCE/FCE) NAO resolve p/ nome: o codigo ja e legivel
       --   e o nome REAL da funcao e sensivel (so no modelo live), nao ficticio.
FROM servidor s
LEFT JOIN dom_unidade_eorg    ul ON ul.cod_unidade     = s.cod_unidade_lotacao
LEFT JOIN dom_unidade_eorg    ue ON ue.cod_unidade     = s.cod_unidade_exercicio
LEFT JOIN dom_afastamento     af ON af.cod_afastamento = s.cod_afastamento_vigente
LEFT JOIN dom_regime_juridico rj ON rj.cod             = s.regime_juridico;

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
-- MV: replay da serie de eventos do proprio servidor. Payload CHEIO (o servidor
-- le o proprio dado — nada a esconder dele mesmo).
-- RLS no Power BI recorta linha -> propria matricula (de-para AD<->matricula).
-- REFRESH CONCURRENTLY exige indice unico (abaixo).
-- v0.9: + colunas planas extraidas do payload (o Power BI relaciona coluna, nao
--   chave-de-JSONB). Codigo na coluna; friendly name na dimensao (dom_afastamento,
--   dom_motivo_deslig). payload CHEIO permanece (aqui e o proprio titular).
-- v0.9: + intervalo_vigente — marca, por (matricula, cod_afastamento, data_inicio),
--   o registro de data_carga mais recente (fechamento ADR-008 vence o aberto).
--   NAO colapsa linha: o Filme mostra a SERIE. Tipos sem par de intervalo => true.
CREATE MATERIALIZED VIEW mv_filme_servidor AS
SELECT e.id_evento,
       e.matricula_funcional,
       e.cpf,
       e.cod_tipo_evento,
       te.cod_sub_dominio,
       e.data_evento,
       -- planas (relacionaveis no PBI; nulas p/ tipos que nao tem o campo):
       (e.payload->>'cod_afastamento')   AS cod_afastamento,     -- ref dom_afastamento
       (e.payload->>'cod_motivo_deslig') AS cod_motivo_deslig,   -- ref dom_motivo_deslig
       (e.payload->>'data_inicio')::date AS data_inicio,         -- AFASTAMENTO/CESSAO
       (e.payload->>'data_fim')::date    AS data_fim,            -- nula = intervalo em aberto
       (e.payload->>'data_desligamento')::date AS data_desligamento,
       -- vigencia do intervalo (ADR-008: 2o registro fecha o 1o; data_carga vence):
       (row_number() OVER (
           PARTITION BY e.matricula_funcional,
                        (e.payload->>'cod_afastamento'),
                        (e.payload->>'data_inicio')
           ORDER BY e.data_carga DESC
       ) = 1) AS intervalo_vigente,
       e.payload,          -- CHEIO — titular le o proprio dado
       e.fonte,
       e.grau_confianca
FROM evento e
JOIN dom_tipo_evento te ON te.cod_tipo_evento = e.cod_tipo_evento;

CREATE UNIQUE INDEX ux_mv_filme_servidor ON mv_filme_servidor(id_evento);
CREATE INDEX ix_mv_filme_servidor_mat ON mv_filme_servidor(matricula_funcional, data_evento);
CREATE INDEX ix_mv_filme_servidor_afast ON mv_filme_servidor(cod_afastamento);
CREATE INDEX ix_mv_filme_servidor_deslig ON mv_filme_servidor(cod_motivo_deslig);

-- ── Filme-Gestor ────────────────────────────────────────────────────────────
-- MV: ENVELOPE + COLUNAS PLANAS, ZERO JSONB. Objeto SEPARADO do Filme-Servidor
-- porque a fronteira difere: o gestor le dado do SUBORDINADO, nao o proprio.
-- v0.9: payload cru SAIU. Antes subia payload_gerencial (denylist de 3 chaves
--   financeiras) — fragil (campo novo passa por padrao). Agora sobe SO o que e
--   nomeado como coluna plana. O motivo fino, se existisse, fica na base (evento),
--   so por GRANT direto (RH/Correg). Sem payload na view => nada a vazar por
--   construcao. Codigo na coluna; friendly name na dimensao.
-- v0.9: WHERE ganha 'intercorrencias' — o gestor VE afastamento do subordinado.
--   cod_afastamento e categoria administrativa (S-2230), nao diagnostico (o eSocial
--   nao carrega CID). Descasamento nessa serie e o que quebra a perna do RH.
-- Gestor = detentor de funcao >= 1.13 (massa v0.3 sec.7); recorte de linha (sub-arvore
--   do gestor) e RLS/GRANT, insumo externo (arvore de cargos) — nao mora aqui.
-- CESSAO aparece 2x (evento CESSAO + AFASTAMENTO cod.40): de proposito; e o espelho
--   que o RH precisa ver. Colapso e UX do PBI, nao corte de dado.
CREATE MATERIALIZED VIEW mv_filme_gestor AS
SELECT e.id_evento,
       e.matricula_funcional,
       e.cod_tipo_evento,
       te.cod_sub_dominio,
       e.data_evento,
       -- planas gerenciais (codigo; traducao na dimensao). SEM payload cru:
       (e.payload->>'cod_afastamento')   AS cod_afastamento,     -- ref dom_afastamento
       (e.payload->>'cod_motivo_deslig') AS cod_motivo_deslig,   -- ref dom_motivo_deslig
       (e.payload->>'data_inicio')::date AS data_inicio,
       (e.payload->>'data_fim')::date    AS data_fim,
       (e.payload->>'data_desligamento')::date AS data_desligamento,
       (row_number() OVER (
           PARTITION BY e.matricula_funcional,
                        (e.payload->>'cod_afastamento'),
                        (e.payload->>'data_inicio')
           ORDER BY e.data_carga DESC
       ) = 1) AS intervalo_vigente,
       e.fonte
FROM evento e
JOIN dom_tipo_evento te ON te.cod_tipo_evento = e.cod_tipo_evento
WHERE te.cod_sub_dominio IN ('vinculos','intercorrencias','desempenho','jornada');

CREATE UNIQUE INDEX ux_mv_filme_gestor ON mv_filme_gestor(id_evento);
CREATE INDEX ix_mv_filme_gestor_mat ON mv_filme_gestor(matricula_funcional, data_evento);
CREATE INDEX ix_mv_filme_gestor_afast ON mv_filme_gestor(cod_afastamento);
CREATE INDEX ix_mv_filme_gestor_deslig ON mv_filme_gestor(cod_motivo_deslig);

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

-- ── RH / Corregedoria — NAO e objeto de exposicao ──────────────────────────
-- Acesso privilegiado documentado (ADR-007): GRANT SELECT direto em
-- servidor+evento, role minimo (grao de TABELA nomeada, nao database).
-- Fora do escopo "4 paineis". Exemplo (role e nome ilustrativos):
--   GRANT SELECT ON servidor, evento TO role_rh_correg;


-- =============================================================================
-- VITRINE ODBC DAS MVs (v0.7) — compat de catalogo, NAO nova fronteira.
-- -----------------------------------------------------------------------------
-- PROBLEMA: o driver psqlODBC nao enumera relkind='m' (materialized view) no
-- Navegador do Power BI. As 3 MVs de exposicao existem no banco, respondem a
-- SELECT, mas ficam INVISIVEIS pro conector — o usuario nao as ve na lista de
-- objetos ao montar o painel.
-- FIX: uma view fina de passagem por MV. View comum (relkind='v') o driver
-- enumera; ela reexpoe a MV no catalogo ODBC.
-- -----------------------------------------------------------------------------
-- ISSO NAO MOVE A FRONTEIRA DA ADR-007:
--   - quem MATERIALIZA continua sendo a MV (a view fina nao materializa nada;
--     resolve no SELECT contra a MV ja materializada pelo REFRESH do Airflow).
--   - o RECORTE de payload/linha ja foi aplicado NA MV, uma camada abaixo.
--   - GRANT e RLS continuam desenhados sobre a MV — a view fina herda, nao redefine.
-- SELECT * DE PROPOSITO: como a fronteira ja esta na MV, a view fina e transparente.
--   Alterar coluna na MV NAO exige tocar a view fina (auto-espelha o shape) — sem
--   segunda superficie pra manter em sincronia. Se um dia a view fina precisar
--   cortar algo a mais, isso vira OUTRA fronteira e sai deste bloco (nao e o caso).
-- =============================================================================

CREATE VIEW vw_mv_filme_servidor AS SELECT * FROM mv_filme_servidor;
CREATE VIEW vw_mv_filme_gestor   AS SELECT * FROM mv_filme_gestor;
CREATE VIEW vw_mv_calculadora    AS SELECT * FROM mv_calculadora;

-- ── Filme AMIGAVEL (v0.10) ──────────────────────────────────────────────────
-- View regular (o ODBC ENXERGA, ao contrario da MV) sobre o Filme, com os codigos
-- ja resolvidos em NOME. E o ponto de conexao do painel que quer ler PLANO, sem
-- montar relacao no Power BI. Codigo continua na coluna (quem quiser relacao, tem);
-- o nome vem pronto ao lado. Principio v0.9 preservado: nome mora na dimensao —
-- aqui so o JOIN de apresentacao. Traducao muda por UPDATE na dimensao, sem tocar MV.
CREATE VIEW vw_filme_servidor AS
SELECT f.*,
       te.nome              AS nome_tipo_evento,
       sd.descricao         AS nome_sub_dominio,
       af.nome_afastamento  AS nome_afastamento,
       md.nome_motivo       AS nome_motivo_deslig
FROM mv_filme_servidor f
LEFT JOIN dom_tipo_evento  te ON te.cod_tipo_evento   = f.cod_tipo_evento
LEFT JOIN dom_sub_dominio  sd ON sd.cod_sub_dominio   = f.cod_sub_dominio
LEFT JOIN dom_afastamento  af ON af.cod_afastamento   = f.cod_afastamento
LEFT JOIN dom_motivo_deslig md ON md.cod_motivo_deslig = f.cod_motivo_deslig;

CREATE VIEW vw_filme_gestor AS
SELECT g.*,
       te.nome              AS nome_tipo_evento,
       sd.descricao         AS nome_sub_dominio,
       af.nome_afastamento  AS nome_afastamento,
       md.nome_motivo       AS nome_motivo_deslig
FROM mv_filme_gestor g
LEFT JOIN dom_tipo_evento  te ON te.cod_tipo_evento   = g.cod_tipo_evento
LEFT JOIN dom_sub_dominio  sd ON sd.cod_sub_dominio   = g.cod_sub_dominio
LEFT JOIN dom_afastamento  af ON af.cod_afastamento   = g.cod_afastamento
LEFT JOIN dom_motivo_deslig md ON md.cod_motivo_deslig = g.cod_motivo_deslig;
