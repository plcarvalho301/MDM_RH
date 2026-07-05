2 — Solicitação de Informação / Dashboard
Tipo: regra de negócio (processo + critério de aceite).
Versão: v0.1 — 2026-06-22.
Dono do processo: Custodiante (TI / minha área).
Origem do gatilho: RH abre ticket pedindo ver um dado ou indicador, em linguagem de negócio.

0. Por que este documento existe
O RH não pede "evento novo". Ele pede "quero ver X no painel". "Evento", "tipo", "motivo",
"domínio" são vocabulário do Custodiante, não do solicitante — não aparecem no ticket.
O trabalho do Custodiante é traduzir o pedido de dashboard para estrutura, e a maior parte
das vezes a tradução conclui que nada precisa ser catalogado (o dado já existe; é recorte novo).
Este documento é a régua que:

decide quando um pedido vira projeção (Power BI) e quando vira catalogação;
quando vira catalogação, decide se entra por INSERT ou se escala como decisão de modelagem;
justifica recusar um ticket (Portão 1) e escalar um ticket (Portão 3) com critério, não com gosto.

Princípio que originou o doc: o teste de "cabe sem quebrar a modelagem" precisa estar escrito,
não ser folclore do Custodiante. Em produção quem aplica não tem o modelo todo na cabeça.

Nota de fase (enquanto estivermos modelando)
Decisão de domínio (Portões 1 e 2 — coerência de negócio, tipo-vs-motivo, qual gaveta) não é
vinculante nesta fase: é apagável e refazível até o schema fechar. Durante a modelagem, o
julgamento do dono do domínio (PM) substitui o do operador no dia a dia — isso é o processo
normal, não uma divergência a debater. O Custodiante aplica e segue.
O Custodiante só trava e discute em duas situações:

Portão 3 — o pedido quebra o modelo (gaveta/transição/âncora nova, qualquer ALTER); ou
risco LGPD / dado de pessoal.

Fora disso, decisão de domínio do PM entra como dado, não como tese.

Distinção que estrutura tudo: dois portões independentes
PerguntaQuem respondeBloqueia o quêModelagem"cabe na estrutura sem ALTER?"Custodiantecatalogação (entra por INSERT ou escala)Fonte"dá pra puxar o dado hoje?"Custodiante (gestão da informação)ativação, não catalogação
Um evento pode passar na modelagem e morrer na fonte (ex.: PROVA_DE_VIDA cabe no modelo,
mas a origem — Cadprev — não está destravada). Catalogar mesmo assim é correto: o catálogo é
mapa do que existe no mundo, não só do que já flui. Some-se status_fonte e segue.

Os dois julgamentos (não confundir — donos diferentes)
O passo "isso é um evento, ou um valor de um evento que já existe?" parece um só julgamento.
São dois, com donos diferentes, e juntá-los foi o erro que este doc corrige:

Coerência de negócio — "isso existe de verdade no mundo do RH? não é duplicata semântica
de algo que já temos com outro nome?" → RH responde. Requer o vocabulário do mundo.
Se ficar incoerente, a responsabilidade é do RH (Portão 1).
Modelagem — "isso é tipo de evento novo, ou linha de domínio de tipo existente? qual gaveta?
qual transição?" → Custodiante responde. Requer o vocabulário do modelo. O RH não tem como
ver isso. Se ficar feio/desencaixado aqui, a responsabilidade é do Custodiante, não do RH.


Regra de ouro do erro a evitar: o Custodiante impede o que QUEBRA (Portão 3, objetivo).
O que apenas "fica feio mas encaixa" é stress test da modelagem, não motivo de recusa —
mas a autoria do feio é de quem fez o julgamento de modelagem (Custodiante).


O que o ticket deve trazer  (antes de qualquer portão)
O RH não fala a língua de evento — não manda status_fonte, classe_transicao nem gaveta
(isso é julgamento do Custodiante). Mas há três coisas que o solicitante tem como saber (são
linguagem de negócio/origem) e sem as quais o Custodiante não roda os portões sem garimpar a fonte:
Campo do ticketO que éAlimentaBase jurídicaLei / decreto / IN / portaria que sustenta o fatoPortão 1 (prova que o fato existe no mundo)Origem sistêmicaOnde o dado nasce (qual módulo/sistema)Portões 0 e 2 (dado novo ou recorte? quem é dono?)Forma de disponibilizaçãoComo o dado sai: API SIAPE Consultas / Extrator-Fita / outro sistema nomeado / planilhaPortões 0 e 4 (já ingiro essa fonte? status_fonte?)
Regra do "outro sistema": se a forma de disponibilização for "outro sistema", o ticket tem de
nomear qual (SisREF, SIASS, Petrvs, BGP, banco das escolas de governo, etc.). "Outro sistema"
genérico deixa o Portão 4 cego — não dá pra setar status_fonte.
Ticket incompleto → DEVOLVE (não bloqueia, não recusa)
Faltando campo, o ticket volta pro solicitante preencher. Não é bloqueio (Portão 3, modelo
quebrado) nem recusa (Portão 1, negócio incoerente): o fato pode ser ótimo, só veio sem o que
o Custodiante precisa pra trabalhar. É a saída mais barata — checagem de formulário, zero
julgamento. Por isso roda antes do Portão 0.

Base jurídica e Origem ausentes → devolve sempre (sem elas não há Portão 0/1).
Forma de disponibilização vaga / "outro sistema" sem nome → devolve (sem ela o Portão 4 é cego).


O fluxo — 5 portões, executados pelo Custodiante ao receber o ticket
ticket RH ("quero ver X")
   │
   ▼
[checagem] campos presentes? (base jurídica · origem · disponibilização nomeada)
   │            NÃO → DEVOLVE pro solicitante preencher. (mais barata; zero julgamento)
   │  SIM
   │
   ▼
[0] TRADUÇÃO ─────────── já é derivável do que existe (FOTO ou evento catalogado)?
   │                        SIM → PROJEÇÃO / Power BI. Sai do fluxo. (maioria para aqui)
   │  NÃO (precisa de estrutura nova)
   ▼
[1] COERÊNCIA (RH) ───── existe no mundo? não é duplicata semântica?
   │                        NÃO → RECUSA o ticket. Responsabilidade do RH.
   │  SIM
   ▼
[2] TIPO ou MOTIVO ───── é tipo de evento novo, ou linha de domínio de tipo existente?
   │                        MOTIVO → INSERT em domínio (ex.: dom_afastamento). Caminho barato.
   │  TIPO NOVO
   ▼
[3] NÃO-QUEBRA ───────── os 4 critérios abaixo. Algum "NÃO"?
   │                        SIM (exige ALTER) → ESCALA como decisão de modelagem. Sai do fluxo de ticket.
   │  TODOS "SIM" (INSERT puro)
   ▼
[4] FONTE ────────────── seta status_fonte. NÃO bloqueia catalogação; trava ativo se inexistente.
   │
   ▼
catalogado (INSERT no 3_catalogo_eventos_v1.yaml)

Portão 0 — Tradução  (Custodiante)
O que o RH quer ver já é derivável do que existe?

está na FOTO (estado vigente)? → painel direto.
é recorte/projeção de evento já catalogado? → painel sobre a série existente.

Se sim → trabalho de projeção (Power BI), não de catalogação. Sai do fluxo aqui.
Espera-se que a maioria dos tickets pare neste portão.
Função de proteção: impede inflar o catálogo por pedido de dashboard. A pergunta certa é
"isso é dado novo no mundo, ou recorte novo de dado que já tenho?" — recorte é Power BI,
custo quase zero, não toca a modelagem.

Portão 1 — Coerência de negócio  (RH responde, Custodiante registra)

O fato existe no mundo do RH (lei/portaria/processo real)?
Não é duplicata semântica de algo que já temos com outro nome?

Falhou → RECUSA o ticket. É o único portão que recusa o RH. A responsabilidade pela
incoerência é do solicitante.

Portão 2 — Tipo ou motivo?  (Custodiante — julgamento de modelagem)
Não-formalizável em lógica fechada; é julgamento, e é do Custodiante (o RH não tem
vocabulário pra saber se "falta injustificada" é tipo ou linha de domínio).

É valor de um tipo que já existe → INSERT em domínio, não tipo novo.
Ex.: gala/nojo, doação de sangue, alistamento, falta injustificada, abandono de posto,
afastamento preventivo → linhas em dom_afastamento (ou irmão), não tipos AFASTAMENTO novos.
O modelo já ensina o padrão: AFASTAMENTO é um tipo; o motivo (S-2230) vive no payload.
Caminho barato, encerra aqui (sujeito ao Portão 4 de fonte).
É fato estrutural novo → segue para o Portão 3.


Portão 3 — Não-quebra  (Custodiante — 4 critérios objetivos)
Tipo de evento novo só entra por INSERT se todos os 4 forem "sim":

Gaveta existe — cai numa das 7 (cadastro · vinculos · intercorrencias ·
compensacao · jornada · desempenho · capacidades). Gaveta nova = decisão de
sub-domínio (minha/PM), fora do ticket.
Transição existe — se a gaveta tem classe_transicao (vinculos, intercorrencias),
a transição usada já está em classe_transicao_dom
(INICIO/AFASTA/RETOMA/ALTERA/CEDE/ENCERRA). Transição nova = ALTER.
Payload com tipos+domínios existentes — campos de tipo já suportado, referenciando
domínio existente ou novo domínio (domínio novo é INSERT, permitido — não é ALTER de schema).
Âncora = servidor — o evento pendura no servidor (matrícula→UUID). Evento ancorado em
outra entidade (ex.: unidade/UORG) é ALTER de modelo (nova âncora), não INSERT.

Qualquer "não" → ESCALA como decisão de modelagem. Não é recusa do RH (o negócio é válido);
é que o modelo precisa mudar e isso sai do fluxo automático de ticket. Separa limpo:

ticket recusado = negócio incoerente (Portão 1);
ticket escalado = negócio ok, modelo precisa de ALTER (Portão 3).


Portão 4 — Fonte  (Custodiante — gestão da informação)
Seta status_fonte no tipo de evento. Não bloqueia catalogação; trava ativação.
status_fonte ∈ { disponivel, pendente_acesso, inexistente_digital }

disponivel → pode ativar (ativo: true), entra na Calculadora/Filme.
pendente_acesso → cataloga, mantém ativo: false até a fonte abrir (ex.: Extrator/Fita).
inexistente_digital → cataloga como mapa; alimentação é garimpo/OCR/papel (não-estimável).

Distinto de cod_origem/cod_mecanica do envelope. Origem = de qual sistema viria;
mecânica = {ingestao, extracao}. status_fonte = já dá pra puxar hoje?. PROVA_DE_VIDA tem
origem (Cadprev) e mesmo assim não é alimentável — por isso é campo novo, não reuso de origem.

Saídas possíveis do fluxo (resumo)
SaídaOnde paraCustoToca catálogo?Devolvido (ticket incompleto)checagem inicialmínimo (formulário)nãoProjeção/Power BIPortão 0quase zeronãoTicket recusadoPortão 1zeronãoINSERT em domínio (motivo)Portão 2baixosim (domínio)Ticket escalado (decisão de modelagem)Portão 3altodepende da decisãoINSERT de tipo novoPortões 3→4médiosim (tipo + payload)

Pendências deste documento

Validação de campo vs. regra de processo pura: as regras fechadas com o RH em tempo de
projeto viram (a) validação de campo, quando aplicável, ou (b) regra de processo (ex.: recusa
de ticket). Mapear quais caem em cada caso ainda não foi feito.
status_fonte é proposto aqui; precisa ser inserido formalmente no envelope/catálogo
(hoje só existe cod_origem/cod_mecanica).