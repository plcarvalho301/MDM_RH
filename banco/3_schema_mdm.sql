-- =============================================================================
-- MDM-RH — Schema do golden record (FOTO + EVENTO)
-- versao: v0.16
-- ancora: 3_depara_foto_v0_3.md | 3_catalogo_eventos_v1.yaml (v1.3) | ADR-007 | ADR-008 | ADR-009 | ADR-010 | ADR-011 | ADR-012 | ADR-013
-- =============================================================================
-- HISTORICO DE VERSAO (versao dentro do arquivo; nome sem versao)
--   v0.16 (este) — ESTRUTURA DERIVADA DO DECRETO (ADR-013): esqueleto de unidades
--                 e cargos/funcoes derivado do decreto de estrutura regimental
--                 (Anexos I/II), ponto de ingestao versionado por (numero_decreto,
--                 data_vigencia). Fecha a fonte da "arvore de cargos" do Filme-Gestor
--                 (2_prespec_lentes §3b) sem depender de acesso SIORG.
--                 (1) dom_estrutura_decreto — tabela nova, SEPARADA de dom_unidade_eorg
--                     (esqueleto de referencia x lotacao viva reconciliada). trilha (1o
--                     digito) e nivel_ordinal (2o numero) derivados do codigo CCE/FCE —
--                     a hierarquia que o schema nao decodificava (funcao_comissionada
--                     era texto cru). Seed = artefato GERADO (decreto animalizado, 2
--                     vigencias 11.816/2023 -> 12.503/2025). Nesta leva so a trilha-1.
--                 (2) vw_orfao_estrutura_decreto — 2o espelho da KR 2.1: unidade no
--                     decreto (vigencia corrente) ausente no E-Org, e vice-versa.
--                 Aditivo puro: nenhuma view existente reordenada/removida.
--   v0.15 — CAMADA DE VITRINE POR PAINEL (ADR-012, handoff vitrine PBI
--                 2026-07-05, spec_vitrine_pbi_v0_1 N1-N11): uma view
--                 vw_painel_<superficie> por superficie de tela, com o shape EXATO
--                 do painel — rotulo humano, booleano 0/1, percentual, cor, frase,
--                 sinal e eixo chegam prontos do SQL. O Power BI nao calcula, nao
--                 relaciona, nao traduz, nao formata: zero DAX, zero relacao, zero
--                 Power Query, zero jsonb atravessando o ODBC (N7).
--                 (1) dom_situacao_vinculo ganha cor_fundo/cor_fonte (N5) — paleta
--                     e DADO na dimensao (principio v0.11); seed_dominios semeia;
--                     migracao em banco vivo = ALTER + UPDATE (handoff §1).
--                 (2) vw_painel_consulta — FRONTEIRA NOVA (excecao unica, ADR-012):
--                     GRANT largo, recorte de coluna MAIS ESTREITO que vw_foto (sem
--                     situacao/afastado/funcao — dado de gestao que o publico nao
--                     recebe). Entra no mapa da ADR-007. Telefone/ramal PENDENTE
--                     (coluna nao existe na FOTO; entra quando subir).
--                 (3) vw_painel_foto, vw_painel_lente, vw_painel_filme_servidor,
--                     vw_painel_filme_gestor — VITRINES: herdam a fronteira/GRANT
--                     do objeto-base (nao redefinem). frase_evento = escada de
--                     fallback do descritor (2_descritores_eventos_v0_1, nivel 2 —
--                     template por tipo + dom_*.nome), NUNCA frase autorada aqui;
--                     nivel 3 (nome_exibicao) NAO entra nesta leva (ADR-012).
--                     Casts de payload guardados por regex (payload sujo nao
--                     derruba a view); jsonb nunca vira coluna de vitrine.
--                 (4) vw_mv_calculadora_folha/_pss ganham competencia_data (N9) e
--                     valor_assinado (N10) — colunas ANEXADAS NO FIM: CREATE OR
--                     REPLACE VIEW so anexa, nao reordena nem remove coluna.
--                 (5) vw_painel_calc_dias (dias liquidos) NAO criada — QUARENTENA
--                     (ADR-012 Pendencias): sobreposicao de afastamento soma em
--                     dobro; 'parcial' sem regra de desconto. Esboco em comentario.
--                 Materializacao ZERO: todas views comuns sobre objeto ja
--                 materializado — nenhum REFRESH novo (relogio Airflow intacto).
--   v0.14 — 6o ESTADO DE VINCULO: TRANSFERIDO (redistribuicao, motivos 29/37).
--                 dom_situacao_vinculo ganha 'TRANSFERIDO'; ck_motivo_resultado passa a
--                 aceitar TRANSFERIDO (era TRANSFERE — valor ORFAO: nao existia em
--                 dom_situacao_vinculo, violaria fk_situacao no dia em que o replay
--                 gravasse a situacao derivada de um DESLIGAMENTO motivo 29/37). Inerte
--                 ate agora so porque a massa nao emite 29/37 (config: 07/38). Fecha o
--                 risco 1b da reconciliacao. FRASEAMENTO do estado (a frase tem de dizer
--                 origem->destino->data) fica PENDENTE — ver ADR Secao 2; consequencia:
--                 o payload de DESLIGAMENTO 29/37 tera de capturar o orgao destino (hoje
--                 ausente), senao a frase nao se monta.
--   v0.13 — VITRINE ODBC DA CALCULADORA SEM jsonb: vw_mv_calculadora_folha e
--                 vw_mv_calculadora_pss deixam de ser SELECT * e listam coluna nomeada
--                 SEM `payload`. Motivo: psqlODBC nao expoe tipo jsonb ao Power BI
--                 (Navegador acusa "coluna sem tipo suportado"). NAO e recorte de
--                 fronteira — payload cru segue na MV (SELECT direto; e onde moram os
--                 arrays datados do PSS, insumo de dias-liquidos). E compat de TIPO
--                 com o conector. Views de Filme seguem SELECT * (titular le o proprio
--                 payload; corte de tipo se aplica igual se forem pro mesmo conector).
--   v0.12 — CALCULADORA COMPLETA: folha planificada + evento PSS novo
--                 (handoff 2026-07-05, catalogo v1.2, ADR-011):
--                 (1) CONTRIBUICAO_PSS entra em dom_tipo_evento (compensacao) —
--                     faltava; a folha e a UNICA fonte migrada, o prespec pede as duas.
--                 (2) mv_calculadora (uma MV, payload cru) vira DUAS MVs por
--                     FRONTEIRA de payload (ADR-011, mesmo principio da ADR-007
--                     "objeto por fronteira, nao por painel" que ja separa Filme
--                     S/G): mv_calculadora_folha e mv_calculadora_pss. FECHAMENTO_
--                     FOLHA e CONTRIBUICAO_PSS sao shapes incompativeis sob o mesmo
--                     cod_sub_dominio='compensacao' — MV por cod_tipo_evento, nao
--                     CASE numa MV so.
--                 (3) mv_calculadora_folha planifica as chaves do payload da folha
--                     em coluna (padrao Filme v0.9) E EXPLODE rubricas (grao =
--                     1 linha por rubrica, jsonb_to_recordset): Power BI le coluna
--                     plana direto, sem "Expandir" lista JSON na Power Query —
--                     ergonomia p/ usuario novo no PBI. payload cru fica ao lado.
--                     Indice unico muda de (id_evento) p/ (id_evento, numero_seq).
--                 (4) mv_calculadora_pss planifica os campos apurados (grao = 1
--                     linha por evento, sem lista a explodir). Os arrays datados do
--                     mesmo payload 4.22 (ferias/lpa/afastamentos/reclusao) ficam
--                     SO no payload cru — insumo de dias-liquidos, nao duplicar
--                     como evento AFASTAMENTO (ver catalogo, obs do campo).
--                 (5) vitrine ODBC (v0.7) ganha vw_mv_calculadora_folha e
--                     vw_mv_calculadora_pss; vw_mv_calculadora (unica) sai.
--   v0.11 — REGRAS DE MODELO viram DADO (o gerador/replay leem do banco, nao
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
    nome_situacao  text NOT NULL,
    -- v0.15 (ADR-012, N5): cor do estado e DADO da dimensao, nao regra por painel.
    -- PBI formata "por valor de campo" (configura uma vez); RH muda cor por UPDATE
    -- sem deploy (principio v0.11). Paleta semeada em seed_dominios.sql.
    cor_fundo      text,             -- hex '#RRGGBB'
    cor_fonte      text              -- hex '#RRGGBB'
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
    situacao_resultante text NOT NULL,          -- {DESLIGADO, INATIVO, TRANSFERIDO}
    e_esocial          boolean NOT NULL DEFAULT true,
    CONSTRAINT ck_motivo_resultado CHECK (situacao_resultante IN ('DESLIGADO','INATIVO','TRANSFERIDO'))
);

CREATE TABLE dom_unidade_eorg (
    cod_unidade   int PRIMARY KEY,
    nome_unidade  text NOT NULL
    -- estrutura SIORG/E-Org VIVA, chega RECONCILIADA (carga por planilha; nao-API).
    -- LOTACAO viva pessoa<->unidade. Distinta do ESQUELETO do decreto abaixo (ADR-013):
    -- o decreto da o galho fixo; o E-Org da onde a pessoa esta hoje.
);

-- v0.16 (ADR-013): ESQUELETO da estrutura organizacional DERIVADO do decreto de
-- estrutura regimental (Anexos I/II), como ponto de ingestao versionado por
-- (numero_decreto, data_vigencia). Separado de dom_unidade_eorg de proposito:
-- esqueleto de referencia (galho fixo do decreto) x lotacao viva reconciliada (E-Org)
-- — e o que habilita o 2o espelho do orfao (vw_orfao_estrutura_decreto).
-- Codigo CCE/FCE: 1o digito = trilha (1 direcao/chefia, 2 assessoramento, 3 projeto);
-- 2o numero = nivel_ordinal (18>17>15>13>10>07>05 — carrega a hierarquia: uma
-- Superintendencia 1.13 e inferior a uma Diretoria 1.15). O schema NAO decodificava
-- funcao_comissionada (texto cru); esta tabela e onde a estrutura de codigo do decreto
-- passa a ser consumida. Seed = artefato GERADO (gerador/decreto_animalizado_v1.yaml
-- -> seed_estrutura_decreto.sql), nao hand-seed. Nesta leva so a trilha-1.
CREATE TABLE dom_estrutura_decreto (
    numero_decreto   text NOT NULL,          -- ex.: '11.816/2023', '12.503/2025'
    data_vigencia    date NOT NULL,          -- inicio de vigencia da redacao
    cod_unidade      int  NOT NULL,
    nome_unidade     text NOT NULL,
    cod_unidade_pai  int,                     -- arvore (Anexo I/II indentacao); null = topo
    tipo_unidade     text,                    -- Direcao-Geral/Secretaria/Diretoria/Superintendencia/Coordenacao-Geral/Coordenacao/Divisao/Servico
    cod_funcao       text NOT NULL,           -- codigo CCE/FCE cru ('FCE 1.07')
    denominacao      text NOT NULL,           -- rotulo human-readable ('Chefe') — NAO chave de ordenacao
    trilha           int  NOT NULL,           -- 1o digito do codigo (1/2/3)
    nivel_ordinal    int  NOT NULL,           -- 2o numero do codigo (18..05) — hierarquia
    quantidade       int  NOT NULL DEFAULT 1, -- Anexo II "CARGO/FUNCAO No" (posicoes iguais agregadas)
    chefia           boolean NOT NULL DEFAULT false,  -- true = cargo que chefia a unidade
    CONSTRAINT pk_estrutura_decreto
        PRIMARY KEY (numero_decreto, data_vigencia, cod_unidade, cod_funcao, denominacao),
    CONSTRAINT ck_estrutura_trilha CHECK (trilha BETWEEN 1 AND 3)
);
CREATE INDEX ix_estrutura_decreto_unidade ON dom_estrutura_decreto(cod_unidade);
CREATE INDEX ix_estrutura_decreto_vigencia ON dom_estrutura_decreto(numero_decreto, data_vigencia);

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

-- KR 2.1 (2o espelho, ADR-013) — orfao estrutural DECRETO x E-Org: unidade que
-- existe no decreto (vigencia CORRENTE = max data_vigencia) e nao no E-Org, e
-- vice-versa. Complementa vw_orfao_estrutural (lotacao x E-Org) com o espelho
-- esqueleto x lotacao viva. `lado` diz de que fonte a unidade orfa veio.
CREATE VIEW vw_orfao_estrutura_decreto AS
WITH corrente AS (
    SELECT DISTINCT cod_unidade, nome_unidade
    FROM dom_estrutura_decreto
    WHERE data_vigencia = (SELECT max(data_vigencia) FROM dom_estrutura_decreto)
)
SELECT 'so_no_decreto'::text AS lado, c.cod_unidade, c.nome_unidade
FROM corrente c
LEFT JOIN dom_unidade_eorg u ON u.cod_unidade = c.cod_unidade
WHERE u.cod_unidade IS NULL
UNION ALL
SELECT 'so_no_eorg'::text AS lado, u.cod_unidade, u.nome_unidade
FROM dom_unidade_eorg u
LEFT JOIN corrente c ON c.cod_unidade = u.cod_unidade
WHERE c.cod_unidade IS NULL;

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
--   Calculadora  -> 2 MVs (folha x PSS; payloads distintos, ADR-011).
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
       nome_unidade_lotacao,                           -- rotulo (nulo = toca orfa, KR 2.1)
       count(*)                                        AS headcount,
       count(*) FILTER (WHERE afastado)                AS afastados,
       count(*) FILTER (WHERE funcao_comissionada IS NOT NULL) AS com_funcao
FROM vw_foto
GROUP BY cod_unidade_lotacao, nome_unidade_lotacao;

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
-- 2 MVs por FRONTEIRA de payload (ADR-011 — mesmo principio da ADR-007 que ja
-- separa Filme S/G): compensacao tem duas familias de payload incompativeis
-- (FECHAMENTO_FOLHA x CONTRIBUICAO_PSS) sob o mesmo cod_sub_dominio. MV por
-- cod_tipo_evento, nao CASE numa MV so. Serie densa por matricula (servidor
-- de 1992 = 30+ anos) — materializa porque a densidade doi no clique.

-- Fechamento de folha: planifica as chaves do payload em coluna (padrao Filme
-- v0.9) E EXPLODE rubricas — grao = 1 linha por rubrica (jsonb_to_recordset),
-- nao 1 linha por evento. Power BI le coluna plana direto, sem "Expandir"
-- lista JSON na Power Query (ADR-011). Colunas de competencia repetem por
-- rubrica (denormalizado, esperado no grao fino). payload cru fica ao lado.
CREATE MATERIALIZED VIEW mv_calculadora_folha AS
SELECT e.id_evento,
       e.matricula_funcional,
       e.cpf,
       e.cod_tipo_evento,
       e.data_evento,
       (e.payload->>'mes_competencia') AS mes_competencia,
       (e.payload->>'mes_pagamento')   AS mes_pagamento,
       (e.payload->>'tipo_fechamento') AS tipo_fechamento,
       r.cod_rubrica,
       r.nome_rubrica,
       r.valor_rubrica,
       r.indicador_rd,
       r.numero_seq,
       r.prazo_rubrica,
       r.periodo_rubrica,
       r.data_ano_mes_rubrica,
       e.payload,
       e.fonte,
       e.grau_confianca
FROM evento e
CROSS JOIN LATERAL jsonb_to_recordset(e.payload->'rubricas') AS r(
    cod_rubrica          int,
    nome_rubrica         text,
    valor_rubrica        numeric,
    indicador_rd         text,
    numero_seq           int,
    prazo_rubrica        int,
    periodo_rubrica      int,
    data_ano_mes_rubrica text
)
WHERE e.cod_tipo_evento = 'FECHAMENTO_FOLHA';

CREATE UNIQUE INDEX ux_mv_calculadora_folha ON mv_calculadora_folha(id_evento, numero_seq);
CREATE INDEX ix_mv_calculadora_folha_mat  ON mv_calculadora_folha(matricula_funcional, data_evento);
CREATE INDEX ix_mv_calculadora_folha_comp ON mv_calculadora_folha(mes_competencia);

-- Contribuicao PSS: grao = 1 linha por evento (payload sem lista a explodir
-- no numero apurado). Os arrays datados do MESMO payload 4.22 (ferias, lpa,
-- afastamentos, reclusao — catalogo v1.2) ficam SO no payload cru: sao insumo
-- de dias-liquidos, nao planificados aqui p/ nao sugerir que sao coluna de
-- calculo pronta, e p/ nao duplicar o evento AFASTAMENTO (intercorrencias).
CREATE MATERIALIZED VIEW mv_calculadora_pss AS
SELECT e.id_evento,
       e.matricula_funcional,
       e.cpf,
       e.cod_tipo_evento,
       e.data_evento,
       (e.payload->>'gr_matricula')::int               AS gr_matricula,
       (e.payload->>'ano_contribuicao')::int            AS ano_contribuicao,
       (e.payload->>'mes_contribuicao')::int            AS mes_contribuicao,
       (e.payload->>'indice_reajuste')::int             AS indice_reajuste,
       (e.payload->>'pss_apurado')::int                 AS pss_apurado,
       (e.payload->>'pss_informado')::int               AS pss_informado,
       (e.payload->>'remuneracao_pss')::numeric         AS remuneracao_pss,
       (e.payload->>'remuneracao_pss_ajustada')::numeric AS remuneracao_pss_ajustada,
       e.payload,
       e.fonte,
       e.grau_confianca
FROM evento e
WHERE e.cod_tipo_evento = 'CONTRIBUICAO_PSS';

CREATE UNIQUE INDEX ux_mv_calculadora_pss ON mv_calculadora_pss(id_evento);
CREATE INDEX ix_mv_calculadora_pss_mat  ON mv_calculadora_pss(matricula_funcional, data_evento);
CREATE INDEX ix_mv_calculadora_pss_comp ON mv_calculadora_pss(ano_contribuicao, mes_contribuicao);

-- ── RH / Corregedoria — NAO e objeto de exposicao ──────────────────────────
-- Acesso privilegiado documentado (ADR-007): GRANT SELECT direto em
-- servidor+evento, role minimo (grao de TABELA nomeada, nao database).
-- Fora do escopo "4 paineis". Exemplo (role e nome ilustrativos):
--   GRANT SELECT ON servidor, evento TO role_rh_correg;


-- =============================================================================
-- VITRINE ODBC DAS MVs (v0.7) — compat de catalogo, NAO nova fronteira.
-- -----------------------------------------------------------------------------
-- PROBLEMA: o driver psqlODBC nao enumera relkind='m' (materialized view) no
-- Navegador do Power BI. As 4 MVs de exposicao existem no banco, respondem a
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
-- SELECT * DE PROPOSITO (regra geral): como a fronteira ja esta na MV, a view fina
--   e transparente. Alterar coluna na MV NAO exige tocar a view fina (auto-espelha o
--   shape) — sem segunda superficie pra manter em sincronia.
-- EXCECAO (v0.13) — as duas views de CALCULADORA NAO sobem `payload` (jsonb):
--   o driver psqlODBC nao expoe tipo jsonb ao Power BI (Navegador acusa "coluna sem
--   tipo suportado" e, quando e a unica/ultima, chega a desabilitar a carga). Nao e
--   fronteira de recorte (o payload cru NAO some do banco — segue na MV, acessivel por
--   SELECT direto; e ali, no PSS, que moram os arrays datados ferias/lpa/afastamentos/
--   reclusao, insumo de dias-liquidos do calculo, nao da superficie do painel). E so
--   compat de TIPO com o conector: o que o Power BI consome sao as colunas planas.
--   Por isso estas duas listam coluna nomeada (sem payload) em vez de SELECT *. As
--   views de Filme seguem SELECT * (o titular le o proprio payload; se um dia forem
--   pro mesmo conector e o jsonb incomodar, aplica-se o mesmo corte de TIPO aqui).
-- =============================================================================

CREATE VIEW vw_mv_filme_servidor  AS SELECT * FROM mv_filme_servidor;
CREATE VIEW vw_mv_filme_gestor    AS SELECT * FROM mv_filme_gestor;
-- calculadora: coluna nomeada SEM payload (jsonb nao vai pro ODBC/Power BI — ver acima)
-- v0.15 (ADR-012): + competencia_data (N9) e valor_assinado (N10), ANEXADAS NO FIM.
-- CREATE OR REPLACE VIEW no Postgres so ANEXA coluna no fim — nao reordena nem
-- remove (senao ERROR: cannot change name of view column). Ordem v0.13 preservada.
CREATE VIEW vw_mv_calculadora_folha AS
SELECT id_evento, matricula_funcional, cpf, cod_tipo_evento, data_evento,
       mes_competencia, mes_pagamento, tipo_fechamento,
       cod_rubrica, nome_rubrica, valor_rubrica, indicador_rd, numero_seq,
       prazo_rubrica, periodo_rubrica, data_ano_mes_rubrica,
       fonte, grau_confianca,
       to_date(mes_competencia,'YYYYMM')                  AS competencia_data,   -- N9 (anexada)
       CASE WHEN indicador_rd = 'D' THEN -valor_rubrica
            ELSE valor_rubrica END                        AS valor_assinado      -- N10 (anexada)
FROM mv_calculadora_folha;
CREATE VIEW vw_mv_calculadora_pss AS
SELECT id_evento, matricula_funcional, cpf, cod_tipo_evento, data_evento,
       gr_matricula, ano_contribuicao, mes_contribuicao, indice_reajuste,
       pss_apurado, pss_informado, remuneracao_pss, remuneracao_pss_ajustada,
       fonte, grau_confianca,
       make_date(ano_contribuicao, mes_contribuicao, 1)   AS competencia_data    -- N9 (anexada)
FROM mv_calculadora_pss;

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


-- =============================================================================
-- CAMADA DE VITRINE POR PAINEL (v0.15, ADR-012) — o shape EXATO de cada tela.
-- -----------------------------------------------------------------------------
-- Entre o objeto de fronteira (ADR-007) e o Power BI: uma view vw_painel_<superficie>
-- por superficie, com cada campo que a tela usa ja PRONTO (rotulo, 0/1, %, cor,
-- frase, sinal, eixo). O PBI marca campo -> vira visual -> posiciona. Zero DAX,
-- zero relacao no modelo, zero Power Query, zero jsonb no ODBC (N7). Agregado de
-- time = agregacao implicita (SUM/AVG) sobre colunas 0/1 do MESMO objeto.
-- A vitrine NAO e fronteira: resolve no SELECT contra objeto ja materializado e
-- HERDA o GRANT dele (Postgres nao propaga GRANT — cada view nova precisa do seu
-- GRANT SELECT ao role que ja le o objeto-base; ver bloco GRANT no fim da secao).
-- Materializacao ZERO: views comuns, nenhum REFRESH novo.
-- EXCECAO: vw_painel_consulta E fronteira nova (GRANT largo, recorte de coluna
-- mais estreito que vw_foto) — entra no mapa da ADR-007, GRANT proprio.
-- frase_evento = escada de fallback do descritor (2_descritores_eventos_v0_1),
-- NIVEL 2 (template por tipo + dom_*.nome). Nivel 3 (dom_*.nome_exibicao,
-- RH-editavel) NAO entra nesta leva — entra depois por CREATE OR REPLACE, que
-- re-frase o passado inteiro de graca. Datas na frase: intervalo = MM/AAAA,
-- pontual = DD/MM/AAAA (regra do descritor). Valor financeiro NUNCA na frase.
-- Chaves de payload: atributos_eventos_MDM-RH.xlsx, aba "Atributos por evento"
-- (validada pelo PM, 2026-07-05).
-- =============================================================================

-- ── Consulta Cadastral — FRONTEIRA NOVA (nao e vitrine; ADR-012 excecao) ─────
-- Publica (todo o orgao): GRANT largo, coluna estreita. SEM situacao/afastado/
-- funcao — dado de gestao que o publico nao recebe. Orfao de unidade aparece
-- como rotulo de fallback, nao some (KR 2.1: o buraco e visivel).
CREATE VIEW vw_painel_consulta AS
SELECT s.matricula_funcional,
       s.nome,
       s.cargo,
       COALESCE(u.nome_unidade, '(unidade não identificada)') AS rotulo_unidade_lotacao,  -- N4
       s.cod_unidade_lotacao,                                                             -- cru, KR 2.1
       -- telefone/ramal: PENDENTE — coluna ainda nao existe na FOTO. Entra quando subir.
       s.data_referencia                                                                  -- N8
FROM servidor s
LEFT JOIN dom_unidade_eorg u ON u.cod_unidade = s.cod_unidade_lotacao;

-- ── Foto de gestao (ficha + consolidado do time) ────────────────────────────
-- Serve as DUAS camadas da pagina: ficha (linha selecionada) e cards de agregado
-- (agregacao implicita sobre *_num: headcount = COUNT(matricula_funcional);
-- % afastados = AVG(afastado_num); % com funcao = AVG(com_funcao_num) — zero DAX).
-- Sem vw_lente, sem relacao. cpf/data_nascimento EXCLUIDOS (decisao PM,
-- reversivel em 1 linha).
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

-- ── Lente Estrategica (grao uorg) ───────────────────────────────────────────
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

-- ── Filme do Servidor ───────────────────────────────────────────────────────
-- frase_evento = escada do descritor (nivel 2) sobre as chaves validadas.
-- Casts ::int do payload GUARDADOS POR REGEX (payload sujo nao derruba a view).
-- JSONB NAO SAI (N7): o payload e lido no CASE, nunca exposto como coluna.
-- Tela: tabela cronologica desc (data_evento, frase_evento, rotulo_vigencia) +
-- slicer eixo DEFAULT=biografia + slicer nome_sub_dominio. RLS por matricula e
-- camada de acesso, fora daqui.
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
       af.nome_afastamento,                                                        -- rotulo cru p/ slicer
       md.nome_motivo                                     AS nome_motivo_deslig,
       -- ── frase_evento: escada do descritor, nivel 2 (template + dom.nome) ──
       --    nivel 3 (COALESCE(dom.nome_exibicao, ...)) entra depois por CREATE OR REPLACE.
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
         WHEN 'PROGRESSAO' THEN   -- tipo GATED (ativo=false, regras de carreira RH); frase provisoria
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
         ELSE  -- nivel 1: tipo novo ou payload pre-arqueologia. JSON cru NUNCA.
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

-- ── Filme do Gestor ─────────────────────────────────────────────────────────
-- SEM payload (ADR-010) -> frase usa SO coluna plana + dimensao. Gestor VE a
-- categoria S-2230 do afastamento (decisao travada, ADR-010 + aba de fronteira
-- validada). SEM flag de sigilo nesta leva. compensacao nao entra no WHERE da
-- MV -> eixo seria constante, nao exposto.
-- LIMITACAO POR CONSTRUCAO: eventos de vinculo (PROVIMENTO/ALTERACAO_FUNCAO/
-- REMOCAO/PROGRESSAO/RETORNO) caem no fallback nivel 1 (tipo em data) — o
-- detalhe mora no payload que a MV do gestor nao carrega. Enriquecer = coluna
-- nomeada na allowlist da MV (decisao de exposicao ADR-010, fora da vitrine).
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
         ELSE  -- vinculos sem payload no Gestor (ADR-010): nivel 1
              te.nome || ' em ' || to_char(g.data_evento, 'DD/MM/YYYY')
       END                                                AS frase_evento,
       g.fonte
FROM mv_filme_gestor g
JOIN      dom_tipo_evento   te ON te.cod_tipo_evento   = g.cod_tipo_evento
LEFT JOIN dom_sub_dominio   sd ON sd.cod_sub_dominio   = g.cod_sub_dominio
LEFT JOIN dom_afastamento   af ON af.cod_afastamento   = g.cod_afastamento
LEFT JOIN dom_motivo_deslig md ON md.cod_motivo_deslig = g.cod_motivo_deslig
LEFT JOIN servidor s ON s.matricula_funcional = g.matricula_funcional;
-- Foto do Gestor (consolidado do time): le vw_painel_foto filtrada por uorg
-- (agregacao implicita) — nao precisa de objeto proprio.

-- ── vw_painel_calc_dias — NAO CRIAR (QUARENTENA, ADR-012 Pendencias) ────────
-- Dias liquidos NAO estampa ate fechar (a) e (b) — o numero sai plausivel e
-- ERRADO. Esboco fichado p/ nao perder; NAO executar:
--  (a) afastamentos SOBREPOSTOS somam em dobro -> precisa merge de intervalos
--      (gaps-and-islands) antes do SUM.
--  (b) conta_efetivo_exercicio='parcial' sem regra de desconto (esboco ignora
--      = chute conservador, nao regra).
--  (c) proveniencia multi-fonte do afastamento (4.1x4.21x4.22) = ADR aberta.
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
-- NB extra: CURRENT_DATE anda durante o dia; quando sair da quarentena, ancorar
--          em data_referencia (D-1), senao dias_brutos diverge do proprio carimbo.

-- ── GRANT da leva (aterrissar por role real do ambiente) ────────────────────
-- Vitrines HERDAM a fronteira do objeto-base (mesmo recorte), mas o Postgres nao
-- propaga GRANT — cada view nova precisa do seu GRANT SELECT ao(s) role(s) que ja
-- leem o objeto-base. vw_painel_consulta e FRONTEIRA NOVA (GRANT proprio, largo).
-- Roles ILUSTRATIVOS — substituir pelos reais (Code/PM aterra):
--   GRANT SELECT ON vw_painel_foto, vw_painel_lente, vw_painel_filme_servidor
--         TO role_gestao;
--   GRANT SELECT ON vw_painel_filme_gestor
--         TO role_gestor;
--   GRANT SELECT ON vw_painel_consulta                    -- FRONTEIRA NOVA (largo)
--         TO role_publico_institucional;
--   (Calculadora: vw_mv_calculadora_* ja tem GRANT desde a v0.13; REPLACE nao derruba.)
-- RLS (Filme-Servidor -> propria matricula; Filme-Gestor -> sub-arvore) e camada
-- de acesso, desenhada sobre a MV — nao muda aqui.
