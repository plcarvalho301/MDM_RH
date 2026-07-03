-- =============================================================================
-- MDM-RH — Seed dos domínios (carga inicial das tabelas dom_*)
-- versao: v0.1
-- ancora: 3_schema_mdm.sql (v0.5) | 3_catalogo_eventos_v1.yaml (v1)
--         3_depara_foto_v0_3.md | 3_depara_vinculo_v0_4.md
--         Tabela_de_Dominios_do_Sigepe_eSocial (corpus)
-- =============================================================================
-- PROPOSITO: popular as tabelas de dominio ANTES de qualquer carga em servidor/
--   evento. Sem isto, as FKs de servidor (situacao, afastamento, regime) e de
--   evento (tipo_evento) rejeitam todo INSERT. Este e o bloqueador duro #2 da PoC.
--
-- IDEMPOTENTE: todo INSERT usa ON CONFLICT DO NOTHING. Rodar N vezes = mesmo estado.
--   Rode DEPOIS de aplicar 3_schema_mdm.sql (as tabelas precisam existir).
--
-- PROVENIENCIA DOS VALORES (o MDM NAO e dono de nenhum destes):
--   - dom_situacao_vinculo, dom_afastamento, dom_motivo_deslig, dom_regime_juridico:
--       Tabela de Dominios eSocial/Sigepe (corpus), consolidada no catalogo_eventos_v1.
--   - dom_sub_dominio, dom_classe_transicao, dom_tipo_evento:
--       catalogo_eventos_v1 (Partes 1, 2, 3, 4).
--   - dom_cargo/classe/padrao/nivel/funcao: lista controlada A CONFIRMAR na fonte
--       (de-para v0.3/v0.4). NAO semeados aqui — entram como texto solto ate a
--       fonte confirmar lista fechada. Semear valor inventado seria mentir dado.
--   - dom_unidade_eorg: carga por planilha SIORG/E-Org (operacao manual, fora do
--       ciclo diario, Q2 do lifecycle). NAO semeado aqui — ver secao 8 (massa PoC).
--
-- DESVIO SINALIZADO (dom_jornada): ver secao 7. Criada+semeada aqui porque o
--   de-para v0.4 promoveu carga_horaria_base e o schema v0.5 (anterior) nao a tem.
-- =============================================================================


-- =============================================================================
-- 1. dom_situacao_vinculo — estado resolvido do vinculo (FK de servidor.situacao_funcional)
-- Fonte: catalogo_eventos + de-para vinculo. Estado vigente que a FOTO grava.
-- =============================================================================
INSERT INTO dom_situacao_vinculo (cod_situacao, nome_situacao) VALUES
    ('ATIVO',          'Ativo'),
    ('INATIVO',        'Inativo (aposentado)'),           -- S-2299 mtv 38/39
    ('CEDIDO',         'Cedido'),                          -- S-2231
    ('DISPONIBILIDADE','Servidor em disponibilidade'),     -- S-2230 cod.31
    ('DESLIGADO',      'Desligado')                        -- S-2299 mtv 07/08/09/25
ON CONFLICT (cod_situacao) DO NOTHING;


-- =============================================================================
-- 2. dom_regime_juridico — regime do vinculo (FK de servidor.regime_juridico)
-- Fonte: de-para vinculo ("RJU, CLT, etc. Lista pequena e estavel").
-- siglaRegimeJuridico da API. Lista minima ancorada; cresce se a fonte trouxer mais.
-- =============================================================================
INSERT INTO dom_regime_juridico (cod, nome) VALUES
    ('RJU', 'Regime Juridico Unico (Lei 8.112/90)'),
    ('CLT', 'Consolidacao das Leis do Trabalho')
ON CONFLICT (cod) DO NOTHING;


-- =============================================================================
-- 3. dom_afastamento — motivos S-2230 (FK de servidor.cod_afastamento_vigente
--    e referenciado pelo payload de AFASTAMENTO).
-- Carrega conta_efetivo_exercicio (gancho KR 2.2) e impacto_previdenciario.
-- Fonte: catalogo_eventos_v1 Parte 6 (dom_afastamento.valores), que consolida a
--   Tabela de Dominios eSocial/Sigepe. Codigos compostos ("17-20,35,43") sao
--   agrupamentos da tabela — mantidos como no corpus; se o dev precisar de 1 linha
--   por codigo atomico, e decisao de loader (nao de seed).
-- impacto_previdenciario: texto do corpus preservado (nao normalizado em enum aqui).
-- =============================================================================
INSERT INTO dom_afastamento
    (cod_afastamento, nome_afastamento, conta_efetivo_exercicio, impacto_previdenciario) VALUES
    ('01',          'Acidente/Doenca do Trabalho',                    'sim',     'mantem (Ativo)'),
    ('03',          'Acidente/Doenca nao relacionada ao trabalho',    'sim',     'mantem (Ativo) - ate 24 meses'),
    ('07',          'Acompanhamento Familiar',                        'parcial', 'suspende salvo facultativo - apos 30 dias sem remuneracao'),
    ('06',          'Aposentadoria por Invalidez',                    'nao',     'transicao inativo - contribui so sobre excedente do teto RPPS'),
    ('15',          'Gozo de Ferias ou Recesso',                      'sim',     'mantem (Ativo)'),
    ('17-20,35,43', 'Licenca Maternidade (e variantes)',              'sim',     'mantem (Ativo)'),
    ('10',          'Licenca Estatutaria COM remuneracao',            'sim',     'mantem (Ativo)'),
    ('05',          'Licenca Estatutaria SEM remuneracao',            'nao',     'suspende - salvo recolhimento facultativo'),
    ('40',          'Exercicio em outro orgao (Cedido)',              'sim',     'mantem na origem - exige controle de repasse do cessionario'),
    ('22,36',       'Mandato Eleitoral / Eletivo em Comissao',        'sim',     'recolhe como se em exercicio na origem'),
    ('12,13',       'Cargo Eletivo - Candidato',                      'parcial', 'suspende salvo facultativo - periodo sem remuneracao'),
    ('24',          'Mandato Sindical',                               'sim',     'recolhe como se em exercicio na origem'),
    ('29',          'Servico Militar',                                'sim',     'mantem - CLT/RGPS: orgao continua obrigado a recolher FGTS'),
    ('11',          'Carcere',                                        'sim',     'suspende - se houver suspensao total de remuneracao'),
    ('25',          'Mulher vitima de violencia',                     'sim',     'mantem (Ativo)'),
    ('21,39,45',    'Suspensao contratual',                           'nao',     'suspende salvo facultativo'),
    ('31',          'Servidor em Disponibilidade',                    'sim',     'proporcional - base = valor dos proventos de disponibilidade')
ON CONFLICT (cod_afastamento) DO NOTHING;


-- =============================================================================
-- 4. dom_sub_dominio — as gavetas (catalogo_eventos Parte 1)
-- classe_transicao_aplicavel: TRUE so em vinculos e intercorrencias (maquina de
--   estados). Aditivos (cadastro, jornada, compensacao) = FALSE.
-- =============================================================================
INSERT INTO dom_sub_dominio (cod_sub_dominio, descricao, classe_transicao_aplicavel) VALUES
    ('cadastro',        'Raiz cadastral do servidor (identidade): nome, CPF, filiacao, endereco.',        false),
    ('vinculos',        'Eventos que transitam o estado do vinculo do servidor.',                          true),
    ('intercorrencias', 'Afastamentos, licencas, ferias - intervalos sobre o vinculo, sem encerra-lo.',    true),
    ('jornada',         'Execucao do trabalho: entregas e planos de trabalho do PGD.',                     false),
    ('compensacao',     'Fechamentos de folha de pagamento (remuneracao historica).',                      false)
ON CONFLICT (cod_sub_dominio) DO NOTHING;


-- =============================================================================
-- 5. dom_classe_transicao — como o evento move o estado do vinculo
-- (catalogo_eventos Parte 2)
-- =============================================================================
INSERT INTO dom_classe_transicao (cod_classe_transicao, descricao) VALUES
    ('INICIO',  'Inicia o vinculo (Ativo).'),
    ('AFASTA',  'Suspende/afasta mantendo o vinculo; tem retorno.'),
    ('RETOMA',  'Retorna de afastamento/inatividade para Ativo.'),
    ('ALTERA',  'Altera atributo do vinculo vigente sem mudar a situacao (cargo/funcao/lotacao).'),
    ('CEDE',    'Move para exercicio em outro orgao (Cedido), vinculo de origem mantido.'),
    ('ENCERRA', 'Encerra o vinculo (Desligado/Inativo).')
ON CONFLICT (cod_classe_transicao) DO NOTHING;


-- =============================================================================
-- 6. dom_tipo_evento — catalogo de tipos (catalogo_eventos Partes 3 e 4)
-- codigo_esocial nulo quando nao ha leiaute proprio. ativo=false = catalogado
--   mas fora da Calculadora (PROGRESSAO: gate ate RH fechar regras de carreira).
-- NB: o schema tem coluna `ativo`, nao `evento_esocial` — este ultimo vive so no
--   catalogo (informativo). Aqui gravamos o que a tabela comporta.
-- =============================================================================
INSERT INTO dom_tipo_evento
    (cod_tipo_evento, cod_sub_dominio, cod_classe_transicao, codigo_esocial, ativo) VALUES
    ('PROVIMENTO',       'vinculos',        'INICIO',  'S-2200', true),
    ('ALTERACAO_FUNCAO', 'vinculos',        'ALTERA',  'S-2206', true),
    ('REMOCAO',          'vinculos',        'ALTERA',  'S-2206', true),
    ('PROGRESSAO',       'vinculos',        'ALTERA',  NULL,     false),  -- gate: sem leiaute, aguarda RH
    ('AFASTAMENTO',      'intercorrencias', 'AFASTA',  'S-2230', true),
    ('CESSAO',           'vinculos',        'CEDE',    'S-2231', true),
    ('RETORNO_VINCULO',  'vinculos',        'RETOMA',  'S-2298', true),
    ('DESLIGAMENTO',     'vinculos',        'ENCERRA', 'S-2299', true),
    ('FECHAMENTO_FOLHA', 'compensacao',     NULL,      NULL,     true)   -- aditivo, sem classe_transicao
ON CONFLICT (cod_tipo_evento) DO NOTHING;


-- =============================================================================
-- 7. [DESVIO SINALIZADO] dom_jornada — NAO existe no schema v0.5
-- -----------------------------------------------------------------------------
-- O de-para v0.4 promoveu `carga_horaria_base` (FK -> dom_jornada) DEPOIS que o
-- schema v0.5 foi escrito. A tabela nao existe no DDL atual. Duas saidas:
--   (a) adicionar dom_jornada + coluna carga_horaria_base ao schema (correcao real);
--   (b) deixar de fora da PoC ate reconciliar schema x de-para.
-- Aqui deixo o CREATE+seed COMENTADO: nao invento coluna nem crio tabela orfa que
-- o schema nao referencia. Descomente SO se voce ja adicionou a coluna em servidor.
-- Valores ancorados: de-para v0.4 (codJornada=40 / "40 HORAS SEMANAIS").
-- =============================================================================
-- CREATE TABLE IF NOT EXISTS dom_jornada ( cod int PRIMARY KEY, nome text NOT NULL );
-- INSERT INTO dom_jornada (cod, nome) VALUES
--     (40, '40 HORAS SEMANAIS'),
--     (30, '30 HORAS SEMANAIS'),
--     (20, '20 HORAS SEMANAIS')
-- ON CONFLICT (cod) DO NOTHING;


-- =============================================================================
-- 8. NAO SEMEADOS AQUI (registrado p/ nao parecer esquecimento)
-- -----------------------------------------------------------------------------
-- dom_cargo, dom_classe, dom_padrao, dom_nivel_cargo, dom_funcao:
--     lista controlada A CONFIRMAR na fonte (Sigepe). Ate confirmar, servidor.cargo
--     etc. carregam como TEXTO SOLTO (schema nao aplica a FK ate a lista fechar).
--     Semear valor inventado = mentir dado de dominio. Fica vazio de proposito.
-- dom_unidade_eorg:
--     carga por planilha SIORG/E-Org (manual, Q2 lifecycle). Na PoC de massa,
--     semeie um punhado de UORGs FICTICIAS junto do gerador de massa — e DEIXE
--     algumas lotacoes apontando p/ UORG inexistente, senao vw_orfao_estrutural
--     (KR 2.1) vem vazia e o painel delta nao prova o motor de adocao.
-- dom_motivo_deslig:
--     referenciado pelo PAYLOAD de DESLIGAMENTO (jsonb), NAO por FK de coluna.
--     O schema v0.5 nao criou a tabela dom_motivo_deslig. Na PoC de FOTO nao entra
--     evento, entao nao bloqueia. Quando o eixo evento entrar, criar a tabela
--     (valores no catalogo_eventos Parte 6) ou validar o codigo na aplicacao.
-- =============================================================================


-- =============================================================================
-- VERIFICACAO (rode apos o seed; contagem esperada entre parenteses)
-- =============================================================================
-- SELECT 'situacao_vinculo' t, count(*) n FROM dom_situacao_vinculo      -- (5)
-- UNION ALL SELECT 'regime_juridico',    count(*) FROM dom_regime_juridico  -- (2)
-- UNION ALL SELECT 'afastamento',        count(*) FROM dom_afastamento       -- (17)
-- UNION ALL SELECT 'sub_dominio',        count(*) FROM dom_sub_dominio       -- (5)
-- UNION ALL SELECT 'classe_transicao',   count(*) FROM dom_classe_transicao  -- (6)
-- UNION ALL SELECT 'tipo_evento',        count(*) FROM dom_tipo_evento;      -- (9)


-- =============================================================================
-- 9. GRADE DE CARREIRA — EPPGG (principal)  [ADICIONADO apos confirmacao]
-- -----------------------------------------------------------------------------
-- FONTE: Portal gov.br do Servidor (carreira EPPGG) + Decreto 5.176/2004 +
--   Lei 11.890/2008. Estrutura: 4 classes (A, B, C, Especial), 5 padroes cada,
--   20 padroes no total, ~20 anos ate o topo.
--
-- CONFLITO DE FONTE REGISTRADO: a ANESP descreve 3 padroes/classe (4 na Especial,
--   =13 total). O portal OFICIAL diz 5/classe (=20, e o "20 anos" casa com isso).
--   Adotado 5/classe (versao oficial + confirmada pelo PM). Se o Sigepe do orgao
--   devolver codPadrao > V, a grade real diverge desta e precisa reconciliar.
--
-- AVISO DE VIGENCIA: MP 1.286/2024 (31/12/2024) reposicionou EPPGG em nova grade
--   (anexos CI-CIII). O desenho pos-MP NAO foi confirmado aqui. Esta grade e a
--   pre-MP. Para a FK de PRODUCAO, confirmar a estrutura vigente no Sigepe.
--   Para a PoC (massa ficticia), esta grade e suficiente e plausivel.
--
-- ESCOPO: SO EPPGG. O legado tera outras carreiras (cada uma com sua grade) —
--   deixado p/ depois por decisao do PM. Ate la, cargos fora de EPPGG carregam
--   classe/padrao como TEXTO SOLTO (a FK abaixo so cobre os valores EPPGG).
--
-- CONSEQUENCIA DE MODELAGEM: aplicar a FK dom_classe/dom_padrao em `servidor`
--   AGORA rejeitaria qualquer servidor de carreira nao-EPPGG (classe/padrao fora
--   desta lista -> rejeito). Na PoC so-EPPGG, tudo bem. Quando o legado entrar,
--   ou a lista cresce (semear as outras grades), ou a FK sai e vira validacao
--   por aplicacao. Decisao adiada — coerente com "deixa pra testar depois".
-- =============================================================================

INSERT INTO dom_classe (cod, nome) VALUES
    ('A',         'Classe A (inicial)'),
    ('B',         'Classe B'),
    ('C',         'Classe C'),
    ('ESPECIAL',  'Classe Especial (final)')
ON CONFLICT (cod) DO NOTHING;

-- Padroes I..V (romano — espelha codPadrao=II do de-para). Grade EPPGG: 5 por classe.
-- dom_padrao NAO amarra padrao-a-classe (a tabela e lista plana de codigos de padrao);
-- a combinacao valida classe x padrao, se precisar ser restringida, e regra de
-- aplicacao/validacao, nao de FK simples. Aqui semeio os 5 codigos de padrao.
INSERT INTO dom_padrao (cod, nome) VALUES
    ('I',   'Padrao I'),
    ('II',  'Padrao II'),
    ('III', 'Padrao III'),
    ('IV',  'Padrao IV'),
    ('V',   'Padrao V')
ON CONFLICT (cod) DO NOTHING;


-- =============================================================================
-- 10. ESCOLARIDADE — dom_nivel_cargo  [PoC: so Superior]
-- -----------------------------------------------------------------------------
-- sigla_nivel_cargo (NS/NI/NA) = escolaridade/complexidade do cargo, NAO degrau
--   de carreira. Lista federal estavel. Para a PoC, PM confirmou: so Superior.
--   NS e o que a massa EPPGG usa (EPPGG e cargo de nivel superior). NI/NA ficam
--   registrados comentados p/ quando o legado (cargos de nivel medio/auxiliar) entrar.
-- =============================================================================
INSERT INTO dom_nivel_cargo (cod, nome) VALUES
    ('NS', 'Nivel Superior')
    -- ('NI', 'Nivel Intermediario'),   -- legado, depois
    -- ('NA', 'Nivel Auxiliar')          -- legado, depois
ON CONFLICT (cod) DO NOTHING;


-- =============================================================================
-- 11. dom_cargo — PoC: so EPPGG
-- -----------------------------------------------------------------------------
-- Um cargo na PoC. codCargo real do Sigepe do orgao NAO confirmado — uso codigo
-- mnemonico 'EPPGG'. Se a massa quiser espelhar o codCargo numerico real da API,
-- troca aqui (1 linha). dom_funcao (funcao comissionada DAS/FCPE) NAO semeado:
-- e opcional na FOTO (funcao_comissionada nula = sem funcao), nao bloqueia a carga.
-- Entra quando/se a massa incluir comissionados.
-- =============================================================================
INSERT INTO dom_cargo (cod, nome) VALUES
    ('EPPGG', 'Especialista em Politicas Publicas e Gestao Governamental')
ON CONFLICT (cod) DO NOTHING;

-- =============================================================================
-- 12. dom_funcao — CCE/FCE (Anexo I, Decreto 10.829/2021)  [matriz COMPLETA nacional]
-- -----------------------------------------------------------------------------
-- FONTE: Anexo I do Decreto 10.829/2021 (matriz categoria x nivel), regra de piso
--   da categoria 4 confirmada pelo Anexo IV (FCT->FCE 4.01..4.11).
-- ESTRUTURA DO CODIGO: '[T]CE C.NN' onde:
--   T  = C (Cargo, livre nomeacao) ou F (Funcao, exclusiva de efetivo)
--   C  = categoria/TRILHA (1=direcao, 2=assessoramento, 3=direcao de projetos,
--        4=assessoramento tecnico especializado) — PRIMEIRO DIGITO = trilha,
--        derivavel por SUBSTR (Decreto 10.829; casa com a regra do corpus).
--   NN = nivel hierarquico (01..18).
-- REGRAS DA MATRIZ (por que nao e produto cartesiano cheio):
--   cat 1: niveis 1..18 (CCE+FCE); nivel 18 = SO CCE 1.18 (sem FCE).
--   cat 2: niveis 1..17 (CCE+FCE).
--   cat 3: niveis 1..16 (CCE+FCE).
--   cat 4: niveis 1..13, SO FCE (nunca CCE) — assessoramento tecnico especializado.
-- ESCOPO REAL: esta e a matriz NACIONAL inteira. O quadro do ORGAO e um SUBCONJUNTO
--   registrado no SIORG (estrutura regimental). Ter a matriz cheia nao custa (uns
--   codigos sem uso na massa); a FK, se aplicada, aceita qualquer FCE valido — bom.
--   Quando o SIORG do orgao for carregado, pode-se restringir a lista ao quadro real.
-- OBS: 'nome' guarda a categoria por extenso + nivel, p/ leitura. A trilha usada
--   pelo produto de scoring (fora do MDM) sai do primeiro digito, nao deste texto.
-- =============================================================================
INSERT INTO dom_funcao (cod, nome) VALUES
    ('CCE 1.18', 'CCE - Direcao - nivel 18'),
    ('CCE 1.17', 'CCE - Direcao - nivel 17'),
    ('CCE 1.16', 'CCE - Direcao - nivel 16'),
    ('CCE 1.15', 'CCE - Direcao - nivel 15'),
    ('CCE 1.14', 'CCE - Direcao - nivel 14'),
    ('CCE 1.13', 'CCE - Direcao - nivel 13'),
    ('CCE 1.12', 'CCE - Direcao - nivel 12'),
    ('CCE 1.11', 'CCE - Direcao - nivel 11'),
    ('CCE 1.10', 'CCE - Direcao - nivel 10'),
    ('CCE 1.09', 'CCE - Direcao - nivel 09'),
    ('CCE 1.08', 'CCE - Direcao - nivel 08'),
    ('CCE 1.07', 'CCE - Direcao - nivel 07'),
    ('CCE 1.06', 'CCE - Direcao - nivel 06'),
    ('CCE 1.05', 'CCE - Direcao - nivel 05'),
    ('CCE 1.04', 'CCE - Direcao - nivel 04'),
    ('CCE 1.03', 'CCE - Direcao - nivel 03'),
    ('CCE 1.02', 'CCE - Direcao - nivel 02'),
    ('CCE 1.01', 'CCE - Direcao - nivel 01'),
    ('CCE 2.17', 'CCE - Assessoramento - nivel 17'),
    ('CCE 2.16', 'CCE - Assessoramento - nivel 16'),
    ('CCE 2.15', 'CCE - Assessoramento - nivel 15'),
    ('CCE 2.14', 'CCE - Assessoramento - nivel 14'),
    ('CCE 2.13', 'CCE - Assessoramento - nivel 13'),
    ('CCE 2.12', 'CCE - Assessoramento - nivel 12'),
    ('CCE 2.11', 'CCE - Assessoramento - nivel 11'),
    ('CCE 2.10', 'CCE - Assessoramento - nivel 10'),
    ('CCE 2.09', 'CCE - Assessoramento - nivel 09'),
    ('CCE 2.08', 'CCE - Assessoramento - nivel 08'),
    ('CCE 2.07', 'CCE - Assessoramento - nivel 07'),
    ('CCE 2.06', 'CCE - Assessoramento - nivel 06'),
    ('CCE 2.05', 'CCE - Assessoramento - nivel 05'),
    ('CCE 2.04', 'CCE - Assessoramento - nivel 04'),
    ('CCE 2.03', 'CCE - Assessoramento - nivel 03'),
    ('CCE 2.02', 'CCE - Assessoramento - nivel 02'),
    ('CCE 2.01', 'CCE - Assessoramento - nivel 01'),
    ('CCE 3.16', 'CCE - Direcao de Projetos - nivel 16'),
    ('CCE 3.15', 'CCE - Direcao de Projetos - nivel 15'),
    ('CCE 3.14', 'CCE - Direcao de Projetos - nivel 14'),
    ('CCE 3.13', 'CCE - Direcao de Projetos - nivel 13'),
    ('CCE 3.12', 'CCE - Direcao de Projetos - nivel 12'),
    ('CCE 3.11', 'CCE - Direcao de Projetos - nivel 11'),
    ('CCE 3.10', 'CCE - Direcao de Projetos - nivel 10'),
    ('CCE 3.09', 'CCE - Direcao de Projetos - nivel 09'),
    ('CCE 3.08', 'CCE - Direcao de Projetos - nivel 08'),
    ('CCE 3.07', 'CCE - Direcao de Projetos - nivel 07'),
    ('CCE 3.06', 'CCE - Direcao de Projetos - nivel 06'),
    ('CCE 3.05', 'CCE - Direcao de Projetos - nivel 05'),
    ('CCE 3.04', 'CCE - Direcao de Projetos - nivel 04'),
    ('CCE 3.03', 'CCE - Direcao de Projetos - nivel 03'),
    ('CCE 3.02', 'CCE - Direcao de Projetos - nivel 02'),
    ('CCE 3.01', 'CCE - Direcao de Projetos - nivel 01'),
    ('FCE 1.17', 'FCE - Direcao - nivel 17'),
    ('FCE 1.16', 'FCE - Direcao - nivel 16'),
    ('FCE 1.15', 'FCE - Direcao - nivel 15'),
    ('FCE 1.14', 'FCE - Direcao - nivel 14'),
    ('FCE 1.13', 'FCE - Direcao - nivel 13'),
    ('FCE 1.12', 'FCE - Direcao - nivel 12'),
    ('FCE 1.11', 'FCE - Direcao - nivel 11'),
    ('FCE 1.10', 'FCE - Direcao - nivel 10'),
    ('FCE 1.09', 'FCE - Direcao - nivel 09'),
    ('FCE 1.08', 'FCE - Direcao - nivel 08'),
    ('FCE 1.07', 'FCE - Direcao - nivel 07'),
    ('FCE 1.06', 'FCE - Direcao - nivel 06'),
    ('FCE 1.05', 'FCE - Direcao - nivel 05'),
    ('FCE 1.04', 'FCE - Direcao - nivel 04'),
    ('FCE 1.03', 'FCE - Direcao - nivel 03'),
    ('FCE 1.02', 'FCE - Direcao - nivel 02'),
    ('FCE 1.01', 'FCE - Direcao - nivel 01'),
    ('FCE 2.17', 'FCE - Assessoramento - nivel 17'),
    ('FCE 2.16', 'FCE - Assessoramento - nivel 16'),
    ('FCE 2.15', 'FCE - Assessoramento - nivel 15'),
    ('FCE 2.14', 'FCE - Assessoramento - nivel 14'),
    ('FCE 2.13', 'FCE - Assessoramento - nivel 13'),
    ('FCE 2.12', 'FCE - Assessoramento - nivel 12'),
    ('FCE 2.11', 'FCE - Assessoramento - nivel 11'),
    ('FCE 2.10', 'FCE - Assessoramento - nivel 10'),
    ('FCE 2.09', 'FCE - Assessoramento - nivel 09'),
    ('FCE 2.08', 'FCE - Assessoramento - nivel 08'),
    ('FCE 2.07', 'FCE - Assessoramento - nivel 07'),
    ('FCE 2.06', 'FCE - Assessoramento - nivel 06'),
    ('FCE 2.05', 'FCE - Assessoramento - nivel 05'),
    ('FCE 2.04', 'FCE - Assessoramento - nivel 04'),
    ('FCE 2.03', 'FCE - Assessoramento - nivel 03'),
    ('FCE 2.02', 'FCE - Assessoramento - nivel 02'),
    ('FCE 2.01', 'FCE - Assessoramento - nivel 01'),
    ('FCE 3.16', 'FCE - Direcao de Projetos - nivel 16'),
    ('FCE 3.15', 'FCE - Direcao de Projetos - nivel 15'),
    ('FCE 3.14', 'FCE - Direcao de Projetos - nivel 14'),
    ('FCE 3.13', 'FCE - Direcao de Projetos - nivel 13'),
    ('FCE 3.12', 'FCE - Direcao de Projetos - nivel 12'),
    ('FCE 3.11', 'FCE - Direcao de Projetos - nivel 11'),
    ('FCE 3.10', 'FCE - Direcao de Projetos - nivel 10'),
    ('FCE 3.09', 'FCE - Direcao de Projetos - nivel 09'),
    ('FCE 3.08', 'FCE - Direcao de Projetos - nivel 08'),
    ('FCE 3.07', 'FCE - Direcao de Projetos - nivel 07'),
    ('FCE 3.06', 'FCE - Direcao de Projetos - nivel 06'),
    ('FCE 3.05', 'FCE - Direcao de Projetos - nivel 05'),
    ('FCE 3.04', 'FCE - Direcao de Projetos - nivel 04'),
    ('FCE 3.03', 'FCE - Direcao de Projetos - nivel 03'),
    ('FCE 3.02', 'FCE - Direcao de Projetos - nivel 02'),
    ('FCE 3.01', 'FCE - Direcao de Projetos - nivel 01'),
    ('FCE 4.13', 'FCE - Assessoramento Tecnico Especializado - nivel 13'),
    ('FCE 4.12', 'FCE - Assessoramento Tecnico Especializado - nivel 12'),
    ('FCE 4.11', 'FCE - Assessoramento Tecnico Especializado - nivel 11'),
    ('FCE 4.10', 'FCE - Assessoramento Tecnico Especializado - nivel 10'),
    ('FCE 4.09', 'FCE - Assessoramento Tecnico Especializado - nivel 09'),
    ('FCE 4.08', 'FCE - Assessoramento Tecnico Especializado - nivel 08'),
    ('FCE 4.07', 'FCE - Assessoramento Tecnico Especializado - nivel 07'),
    ('FCE 4.06', 'FCE - Assessoramento Tecnico Especializado - nivel 06'),
    ('FCE 4.05', 'FCE - Assessoramento Tecnico Especializado - nivel 05'),
    ('FCE 4.04', 'FCE - Assessoramento Tecnico Especializado - nivel 04'),
    ('FCE 4.03', 'FCE - Assessoramento Tecnico Especializado - nivel 03'),
    ('FCE 4.02', 'FCE - Assessoramento Tecnico Especializado - nivel 02'),
    ('FCE 4.01', 'FCE - Assessoramento Tecnico Especializado - nivel 01')
ON CONFLICT (cod) DO NOTHING;