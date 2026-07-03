2 — Pré-Spec das 4 Lentes
Tipo: especificação conceitual (pré-refinamento).
Versão: v0.1 — 2026-06-26.
Dono: PM (Pedro) define função e recorte de negócio; Custodiante (TI) define MV, GRANT, payload.
Status: rascunho-base. Cada lente tem pendências marcadas; o detalhe fino vem em sessões de refinamento futuras e na ADR de constituição das views.

0. O que este doc é (e o que não é)
É a definição conceitual dos 4 painéis executivos do TAP — A Foto de Hoje, O Filme do Servidor,
Lente Estratégica, Calculadora do RH — antes do refinamento campo a campo. Fixa, por lente:
função de negócio, UI base, fonte, natureza da materialized view e fronteira de acesso.
Não é o payload final de cada MV (isso é a ADR das views). Não é mapeamento dado→fonte
(isso é mapeamento_dados_eventos). Não é o catálogo de fontes (isso é 3_catalogo_fontes).
Aqui é a régua conceitual de cada tela.

1. Princípio transversal — a MV é a fronteira de acesso
O ambiente não tem IAM granular. Acesso é binário por aplicação: concedido pessoa × aplicação,
e quem entra numa app vê tudo dentro dela. Não há RBAC interno que recorte linha por papel.
Consequência que governa todo este doc: a única fronteira de autorização real é o objeto físico
atrás de cada conexão. O GRANT no objeto Postgres (tabela/MV) é o RBAC. Filtro no Power BI
(RLS por USERNAME()) recorta a apresentação, não o acesso — o dado restrito continua na MV,
o painel só escolhe não mostrar. Logo:

Separação que precisa ser real → objetos físicos distintos, GRANTs distintos (ex.: servidor × gestor).
Separação tolerável como cosmética → RLS, com o risco explicitamente aceito e registrado
(ex.: gestor-A × gestor-B — população pequena, nominal, baixa capacidade técnica de furar).


Regra: o número de MVs segue o número de fronteiras de acesso distintas, não o número de painéis.
Um painel pode virar N MVs (Filme); N painéis podem compartilhar substrato (Foto/Lente).

Materialized view aqui é decisão arquitetural fechada: usuário nunca toca o banco vivo. O REFRESH
é processamento (relógio do Airflow, D-1); o SELECT do Power BI é uso. A MV é a fronteira física.

2. Lente 1 — A Foto de Hoje
Função (negócio). Ver o estado vigente de um servidor: o que ele tem hoje (lotação, cargo/função
vigente, contato institucional). É o que o servidor veria no SouGov, consolidado numa tela.
UI base.

Input: nome | matrícula | uorg (três modos de busca, mesma tela).
matrícula → resolve 1 Foto. nome → pode dar N (homônimo ou N vínculos do mesmo CPF). uorg → N lotados.
Resultado múltiplo → lista → clica → abre a Foto daquele servidor. Lista e Foto são a mesma tela em dois estados.

Natureza. Lê a face FOTO (estado vigente, sobrescrito em D-1). Cada linha = um servidor.
Fonte.

Foto do servidor: ConsultaDadosFuncionais (vigente) — já é a fonte primária da FOTO no schema.
Busca por uorg: listaServidores (entrada uorg → CPFs lotados nela). Motor da busca-por-uorg e do drill da Lente.

Acesso. Dado público institucional não-sensível. Fronteira mais larga do conjunto — não há indivíduo sensível a vazar.
Pendências.

Recorte fino de campos (o que é "público institucional"): decisão RH/PM, não bloqueia a estrutura.
Servidor em uorg órfã (KR 2.1 reconciliação SIORG/E-Org): aparece na uorg-pai, some, ou marcado órfão? Decisão de UI/negócio.


3. Lente 2 — O Filme do Servidor
Função (negócio). Ver, numa tela, tudo que aconteceu na vida funcional do servidor — a série de
eventos encadeados, sob um filtro. Foto e Filme têm a mesma função plana de negócio ("ver a vida
do servidor"); a diferença é só de gravação: não se faz event sourcing de raiz cadastral → cadastro
é Foto (estado, sobrescreve); o que tem série datada é Filme (evento, append). Distinção de engenharia,
invisível ao RH, não vira dois propósitos.
UI base. Mesma do painel 1 (busca → resolve servidor), mas a lista de baixo é a série de eventos
daquele servidor, recortada pelo filtro X.
Quebra em 2 painéis + 1 credencial (consequência do §1 — sem IAM, a única separação real é física):
3a. Filme-Servidor

Universo: órgão inteiro (muita gente). Recorte: RLS → própria matrícula (USERNAME() → matrícula; o de-para AD↔matrícula existe).
Payload: quase tudo dele.
Nota de risco: é a MV de maior superfície (todo o órgão atrás de um filtro cosmético). Se entrar dado sensível no Filme, é aqui que o corte precisa ser mais conservador.

3b. Filme-Gestor

Universo: poucos gestores conhecidos. Recorte: RLS → sub-árvore do gestor.
Escopo computável sem chefia cpf-a-cpf: matrícula → cargo (último provimento) → uorg que o cargo chefia (árvore de cargos, input Excel) → todos lotados na uorg (listaServidores).
Payload reduzido (gerencial): provimento/cargo, cessão, PGD (desempenho), mérito. O corte de campo compensa a fraqueza do RLS — vazamento lateral gestor-A × gestor-B expõe só o subconjunto gerencial, não o filme cheio.
Risco aceito: separação gestor-A × gestor-B é RLS (cosmética). Aceito por população pequena/nominal/baixa capacidade técnica. Registrado como decisão, não como descuido.

3c. Acesso RH / Corregedoria — não é painel

Read puro, super restrito, é o que a gestão de RH/Corregedoria já faz hoje com token no Sigepe live.
Não tem RLS (vê tudo de todos), não tem recorte de payload (é o banco), o usuário é fonte-de-verdade humana.
Implementação: GRANT de SELECT D-1 nas tabelas-fonte (servidor, evento), role mínimo, controle por quem-ganha-role. Sai do escopo dos "4 painéis" → vira acesso privilegiado documentado (governança, PM resolve).
D-1 é suficiente: o caso onde D-0 importaria (mudança hoje, ver hoje) é fringe.

Pendências.

Payload do Filme (o que entra/não entra em cada variante): ADR das views.
Árvore de cargos (Excel): é a tabela que faz o Filme-Gestor existir. Não bloqueia desenhar; bloqueia funcionar.


4. Lente 3 — Lente Estratégica
Função (negócio). Congregar agregados gerenciais para a gestão/diretoria. Indicadores sobre o
corpo funcional sem expor o indivíduo: servidores × uorg, PGD × uorg, servidor × perfil, afastamentos
× uorg, etc. Capaz de puxar indicador sobre dado sensível sem identificar (ex. hipotético:
"suspensões por uorg").
Natureza. Agregado (cada linha = célula uorg × dimensão, com um número) com drill-through pro
detalhe não-sensível. O drill não cruza fronteira nova: quem tem a Lente já tem a Foto pública;
descer de "uorg X tem N ausências" para a lista de quem está na uorg X é o mesmo dado do painel 1.
Provável que Lente e Foto compartilhem substrato (a Lente agrega em cima, desce pra linha no clique) —
decisão de implementação Power BI, não de DDL.
Fonte. Nasce com as dimensões que têm fonte hoje (headcount, lotação, cargo). Dimensões
dependentes de fonte ainda fechada entram conforme destravam: PGD × uorg (PGD/Petrvs, adesão hoje
parcial — KR 3.1), afastamento × uorg (API/serviços de afastamento), disciplinar × uorg
(Corregedoria — depende da decisão da 8ª gaveta). É o painel cujo conteúdo mais depende de fonte aberta.
Acesso. Por ser agregado sem indivíduo, é a fronteira mais larga — painel da diretoria sem risco de privacidade. Enquanto for só agregado banal.
Pendências.

Re-identificação por célula pequena (agregação ≠ anonimização): num órgão pequeno (~1.500 ativos,
caudas de n=1, n=2), "suspensões: 1" numa uorg de 3 pessoas re-identifica. Risco só no ramo sensível
(disciplinar, saúde); headcount não re-identifica. Controle (supressão de célula / segregar como no Filme)
é decisão da ADR das views — não se fecha agora; provavelmente só visível na PoC. Se entrar
indicador sensível, tende a ser outra MV/GRANT, não regra dentro da Lente.


5. Lente 4 — Calculadora do RH
Função (negócio). Por matrícula, entregar a finanças a matéria de cálculo previdenciário/financeiro
consolidada numa tela — incluindo os eventos não-financeiros que impactam (afastamento), que hoje
o financeiro não vê junto no Sigepe. Ganho #1 do projeto: puxa a matrícula, e sai a contribuição
previdenciária, a base de cálculo, os dias líquidos de contribuição (descontando afastamentos).
Reenquadramento pós-RTFS (não é engine). O SIAPE já apura PSS e base. A Calculadora do piloto
exibe o que a fonte apurou + replay; não recalcula do zero. Os três entregáveis do ganho #1:
EntregávelFonteEngine?Contribuição previdenciáriapssApurado / pssInformado (listaContribuicoesPSS)Não — fonte apuraBase de cálculoremuneracaoPss / remuneracaoPssAjustada (listaContribuicoesPSS)Não — fonte apuraDias líquidos (desconta afastamento)série de afastamento (listaContribuicoesPSS) × dom_afastamento.conta_efetivo_exercicioNão — replay existente
Fonte.

listaContribuicoesPSS — coração. PSS apurado + base + reajuste, mês a mês; e no mesmo payload férias, LPA, afastamentos, reclusão datados.
consultaDadosFinanceirosHistorico — folha rubrica a rubrica, datada, R/D, por vínculo.
dom_afastamento.conta_efetivo_exercicio — regra (já no schema) que decide se cada afastamento conta pra tempo efetivo.

Natureza. MV mais densa do conjunto — série temporal longa por matrícula (servidor de 1992 = 30+ anos
de competência). Exaustividade é requisito duro: buraco na série = número errado. O delta de
incompletude aqui não é cosmético — é selo de confiabilidade do número exibido.
Acesso. MV própria, GRANT pro role de finanças. Universo = financeiro + PSS + afastamento de
qualquer servidor (é o trabalho deles). Sem RLS; corte pela app/role (modelo binário).
Fora de escopo (decisão de não-fazer, registrada). Engine de recálculo — auditar o que o SIAPE
apurou, recalcular do zero, projetar cenário de aposentadoria, IR. Isso exige tabela de regras
versionadas por vigência (alíquota × data, base × data) + validação legal + responsabilização por
número com consequência legal. É app separada, Fase 6/roadmap, consumidora do MDM por GRANT —
não embarcada no BI. O MDM é o substrato suficiente pra ela rodar depois sem caçar dado
(toda a tabela evento é append-only e auditável por construção).
Pendências.

Valor monetário por rubrica no consultaDadosFinanceirosHistorico: o manual (OCR truncado) lista
rubrica/data/R-D mas não confirma o valor. Afeta só a engine de recálculo (o ganho #1 vem do PSS
já apurado, não disto). Confirmar no WSDL ao vivo ao fechar o payload do evento financeiro — não antes.


6. Quadro-resumo
LenteFunçãoNatureza MVUniversoRecorte/fronteiraFonte-chaveFoto de Hojeestado vigente de um servidorFOTO (1 linha = servidor)órgãopúblico institucional; GRANT largoConsultaDadosFuncionais + listaServidoresFilme-Servidorvida funcional, só deleEVENTO (replay)órgão inteiroRLS → própria matrículatabela eventoFilme-Gestorvida gerencial dos subordinadosEVENTO (replay), payload reduzidopoucos gestoresRLS → sub-árvore (listaServidores + árvore de cargos)tabela eventoFilme — acesso RH/Correg.read puro do banconão é MVtudoGRANT SELECT D-1, role mínimoservidor + eventoLente Estratégicaagregados gerenciaisagregado + drill-through—GRANT largo (agregado banal); sensível → segregarheadcount/lotação hoje; PGD/afast./discipl. ao destravarCalculadoramatéria de cálculo PSS/financeiro por matrículasérie temporal densaqualquer servidorGRANT finanças, sem RLSlistaContribuicoesPSS + *FinanceirosHistorico

7. Pendências transversais (entram nas sessões de refinamento)

ADR de constituição das views — payload exato de cada MV; o que entra/não entra no Filme; regra de
proveniência do afastamento multi-fonte (4.1 vigente / 4.21 histórico / 4.22 PSS / API Afastamento write).
Primeiro evento do projeto que nasce de N fontes — precisa de regra escrita de qual é autoritativa.
Recorte de campos da Foto (público institucional) — RH/PM.
Árvore de cargos (Excel) — pré-requisito funcional do Filme-Gestor.
Re-identificação por célula pequena na Lente — controle a definir na PoC.
Valor-por-rubrica no *FinanceirosHistorico — confirmar no WSDL; afeta só a engine futura.