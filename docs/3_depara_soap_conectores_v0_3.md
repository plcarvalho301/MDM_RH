# De-para SOAP → payload de evento — conectores SIAPE (v0.3)

**Versão:** v0.3 · **Data:** 2026-07-14 · **Escopo:** Card 6 (envelope de *resposta* SIAPE → payload
do evento MDM). **Não** edita schema, catálogo de tipos, ADR nem código do contrato (mas ver o
follow-up de correção de catálogo em §5.6).

**Âncora primária:** WSDL íntegro do serviço `ConsultaSIAPE` (`targetNamespace=http://servico.wssiapenet`),
carregado em `docs/WSDL Siapenet/consultaDadosFinanceirosHistorico` (1904 linhas, 32 operations, um
único serviço). Referências de linha abaixo (`WSDL:NNN`) apontam para esse arquivo. Os tipos vivem
em `http://tipo.servico.wssiapenet` (prefixo `ns1:`).

> **▶ Decisões do TL aplicadas (2026-07-14):** as 8 pendências da §5 foram **decididas** (marcadas
> `✔ RESOLVIDO` inline e na §5). Consequências maiores: (a) o mapa §4.20 está **desbloqueado**
> (`mesAnoPagamento` = competência); (b) `consultaHistoricoPCA` foi **promovido a fonte ativa** de
> PROVIMENTO/DESLIGAMENTO retroativo (§7) — o "buraco de vínculos" estreita. Restam 2
> confirmações no 1º payload *live* (§5.2 semântica de `mesAnoPagamento`; §5.3 homogeneidade do
> suplementar) e 1 pendência **pós-live** (`codigoOrgao`).

**Proveniência das versões:** não existe `3_depara_soap_conectores_v0_2.md` nem `v0_1` como arquivo
commitado — nunca existiram no repo (verificado em working tree, todos os branches e histórico). O
de-para "v0.1/v0.2" viveu **codificado** nos mapas `FUNCIONAIS`/`AFASTAMENTO` de
[`pipeline/contrato/siape_envelope.py`](../pipeline/contrato/siape_envelope.py) + comentários,
citado como "âncora" no header do emissor. **Este é o primeiro de-para *standalone* escrito**, e o
primeiro ancorado no WSDL íntegro em vez de "1º retorno real".

**Fronteira (não reabrir):** [ADR-014](1_adr_mdm.md) está fechada e commitada — a proveniência do
evento AFASTAMENTO (§4.21 fonte única; §4.1 face-FOTO; §4.22 atributo; Ocorrências fora) **não se
toca**. Este documento é sobre *estrutura de campo* (envelope → payload), não sobre autoridade de
fonte.

**Estado de fechamento:** a **estrutura** dos quatro shapes fecha (o `<xsd:complexType>` interno
está no WSDL); a **modelagem** foi decidida pelo TL (§5). O retorno real segue necessário só para
validar **conteúdo** (formato de valor — ex.: `valorRubrica` em centavos ou com vírgula? — e as 2
confirmações §5.2/§5.3), não estrutura. Falta ainda um **de-para de código** para o PCA
(`formaProvimento`/`formaVacancia` → domínios de ingresso/desligamento — §7), aberto.

---

## §0 — Fato estrutural que o WSDL íntegro crava

O serviço tem **32 operations** (`portType`, `WSDL:1105+`). Quatro entregam série datada relevante
ao event store:

| Operação | `wsdl:message` resposta | `part out` (tipo) | Evento MDM | § |
|---|---|---|---|---|
| `consultaDadosAfastamentoHistorico` | `WSDL:1448` | `ArrayOfArrayDadosAfastamento` (`WSDL:1449`) | AFASTAMENTO (`intercorrencias`) | 4.21 |
| `consultaDadosFinanceirosHistorico` | `WSDL:1273` | `ArrayOfArrayDadosFinanceiros` (`WSDL:1274`) | FECHAMENTO_FOLHA (`compensacao`) | 4.20 |
| `listaContribuicoesPSS` | `WSDL:1224` | `ArrayOfArrayContribuicoesPSS` (`WSDL:1225`) | CONTRIBUICAO_PSS (`compensacao`) | 4.22 |
| `consultaHistoricoPCA` | `WSDL:1168` | `ArrayOfCargoPca` (`WSDL:1169`) | **PROVIMENTO / PROGRESSAO / RETORNO_VINCULO / DESLIGAMENTO** (`vinculos`, retroativo — §7) | — |

**Cobertura de `vinculos` após §5.8 + a tabela de códigos do PCA (§7):** o `consultaHistoricoPCA`
alimenta **PROVIMENTO, PROGRESSAO, RETORNO_VINCULO e DESLIGAMENTO** (as formas de provimento/vacância
mapeiam nesses 4 tipos). Os **3 restantes** — `ALTERACAO_FUNCAO`, `REMOCAO` (lotação), `CESSAO` —
**não têm shape histórico no WSDL**: seguem por FOTO-diff pós-go-live + Extrator. O "buraco de
vínculos" **estreita de 7 para 3** tipos.

---

## §1 — AFASTAMENTO — §4.21 `consultaDadosAfastamentoHistorico`

**Saída:** `ArrayOfArrayDadosAfastamento` (`WSDL:671`). Hierarquia real (dois ramos por vínculo):

```
ArrayOfArrayDadosAfastamento                          (WSDL:671)
 └─ ArrayDadosAfastamento          unbounded          (WSDL:70)   → por vínculo
     ├─ dadosAfastamentoPorCPF : ArrayOfDadosAfastamentoPorCpf
     │   └─ DadosAfastamentoPorCpf  unbounded
     │       ├─ ocorrencias : ArrayOfDadosOcorrencias
     │       └─ reclusao    : ArrayOfDadosReclusao
     └─ dadosAfastamentoPorMatricula : ArrayOfDadosAfastamentoPorMatricula
         └─ DadosAfastamentoPorMatricula  unbounded    (WSDL:124)
             ├─ grMatricula : string                    ← CHAVE do vínculo (deste nível)
             ├─ ferias      : ArrayOfDadosFerias
             ├─ lpa         : ArrayOfDadosLpa
             ├─ ocorrencias : ArrayOfDadosOcorrencias
             └─ reclusao    : ArrayOfDadosReclusao
```

**O ramo que alimenta o evento AFASTAMENTO é `ocorrencias` → `DadosOcorrencias` (`WSDL:92`).**
Todos os campos-folha são `xsd:string`, `minOccurs=0`, `nillable=true`:

| Tag XML (`DadosOcorrencias`) | Payload AFASTAMENTO | Nota |
|---|---|---|
| `codOcorrencia` | `cod_afastamento` | FK `dom_afastamento` (eixo S-2230) |
| `dataIni` | `data_inicio` | DDMMYYYY→ISO (coerção no conector) |
| `dataFim` | `data_fim` | vazio = aberto (vigente) |
| `descOcorrencia` | (descarta) | nome vem do domínio |
| `codDiplomaAfastamento` | (descarta — legado) | ✔ §5.1 |
| `numeroDiplomaAfastamento` | (descarta — legado) | ✔ §5.1 |
| `dataPublicacaoAfastamento` | (descarta — legado) | ✔ §5.1 |
| `descDiplomaAfastamento` | (descarta — legado) | ✔ §5.1 |

`grMatricula` (chave do vínculo) vem no nível `DadosAfastamentoPorMatricula` (`WSDL:124`), **não**
em `DadosOcorrencias`. A matrícula do evento sai de lá.

> **✔ RESOLVIDO (§5.1, TL 2026-07-14):** os 4 campos de DIPLOMA (`codDiplomaAfastamento`,
> `numeroDiplomaAfastamento`, `dataPublicacaoAfastamento`, `descDiplomaAfastamento`) **descartam** —
> provável legado. Revisar se algo relevante aparecer no 1º payload *live*. O payload AFASTAMENTO
> segue com os 3 já modelados (`cod_afastamento`, `data_inicio`, `data_fim`).

**Ramos que NÃO viram evento AFASTAMENTO** (ADR-014 item 3 / catálogo v1.2 — atributo, não
evento-espelho):
- `ferias` (`ArrayOfDadosFerias`), `lpa`, `reclusao` dentro de `PorMatricula`; `ocorrencias`/
  `reclusao` dentro de `PorCpf`.
- **`DadosFerias` (`WSDL:138`) tem 13 campos**, mas por decisão §5.7 (TL) só `data_ini`/`data_fim`
  entram como insumo de dias-líquidos; os outros 11 (`adiantamentoSalarioFerias`, `anoExercicio`,
  `dataFimAquisicao`, `dataInicioAquisicao`, `dataInicioFeriasInterrompidas`, `diasRestantes`,
  `gratificacaoNatalina`, `numeroDaParcela`, `parcelaContinuacaoInterrupcao`, `parcelaInterrompida`,
  `qtdeDias`) descartam. **Este é o mesmo ramo de onde o PSS puxa férias/LPA — ver §5.6.**

**Carimbo de ingestão** (ADR-014, imutável): `fonte='WS_SIAPE:consultaDadosAfastamentoHistorico'`,
`cod_mecanica='ingestao'`, `grau_confianca='alto'`.

---

## §2 — FECHAMENTO_FOLHA — §4.20 `consultaDadosFinanceirosHistorico`

**Saída:** `ArrayOfArrayDadosFinanceiros` (`WSDL:257`). Hierarquia:

```
ArrayOfArrayDadosFinanceiros                    (WSDL:257)
 └─ ArrayDadosFinanceiros    unbounded          (WSDL:4)    → por vínculo/competência
     ├─ codigoOrgao      : xsd:int                          ← wrapper (ver pend. pós-live)
     ├─ matricula        : xsd:int                          ← wrapper (chave)
     ├─ mesAnoPagamento  : xsd:string  → mes_competencia    ← CHAVE de coalescência [✔ §5.2 TL]
     └─ dadosFinanceiros : ArrayOfDadosFinanceiros
         └─ DadosFinanceiros  unbounded          (WSDL:17)   → por rubrica
```

`DadosFinanceiros` (a rubrica, `WSDL:17`) — todos `xsd:string`, `minOccurs=0`, `nillable=true`:

| Tag XML | Payload `FECHAMENTO_FOLHA.rubricas[]` | Nota |
|---|---|---|
| `codRubrica` | `cod_rubrica` | catálogo tipa int; WSDL é string → **coerção no conector** |
| `nomeRubrica` | `nome_rubrica` | — |
| `valorRubrica` | `valor_rubrica` | COM SINAL; catálogo tipa numeric; WSDL string → coerção |
| `indicadorRD` | `indicador_rd` | {R,D} |
| `numeroSeq` | `numero_seq` | preserva ordem |
| `pzRubrica` | `prazo_rubrica` | — |
| `peRubrica` | `periodo_rubrica` | — |
| `dataAnoMesRubrica` | `data_ano_mes_rubrica` | — |
| `indicadorMovSupl` | → `tipo_fechamento` | ✔ §5.3 |

**Chave de coalescência (payload):** `mes_competencia` (= `mesAnoPagamento`) + vínculo.

> **✔ RESOLVIDO (§5.2, TL 2026-07-14) — desbloqueia o mapa §4.20:** `mesAnoPagamento` **É** a
> competência (define a série histórica) → mapeia para `mes_competencia`, a chave de coalescência.
> O `mes_pagamento` do catálogo **não é modelado como campo separado** — pagamento só interessa para
> saber se o desembolso ocorreu, não é chave. **Confirmação *live* (única):** o campo se chama
> "Pagamento"; se o payload real mostrar que ele traz o mês de *desembolso* (≠ referência em folha
> suplementar/retroativa), a competência cai em `dataAnoMesRubrica` (por rubrica). Verificar no 1º
> retorno.

> **✔ RESOLVIDO (§5.3, TL 2026-07-14):** suplementar é uma **folha contingente própria** (se deu
> problema num mês, emite-se folha suplementar para pagar depois). `tipo_fechamento` deriva de
> `indicadorMovSupl`; espera-se **homogeneidade** dentro de um `ArrayDadosFinanceiros` (todas as
> rubricas do fechamento com o mesmo indicador). Regra do catálogo preservada: suplementar **SOMA**
> à competência (valor pode ser negativo). **Confirmação *live*:** se vier misto, tratar o
> fechamento como suplementar.

> **⏸ PENDENTE PÓS-LIVE (`codigoOrgao`, TL 2026-07-14):** `codigoOrgao` (wrapper, `xsd:int`) — entra
> ou descarta? **Fica pendente até o go-live:** o TL não sabe se o valor varia quando o servidor
> está cedido (exercício em outro órgão). Decidir com o 1º retorno real.

**Não confundir:** existe um shape gêmeo no WSDL — `FichaFinaceiraBeneficiario` (dentro de
`PensaoRecebida`/`PensoesInstituidas`) com as mesmas tags de rubrica + `codigoAssunto`/
`codIdentCempFuncao`/`codSistemaClassifCempFuncao`. **NÃO é fonte de FECHAMENTO_FOLHA de servidor
ativo** (é ficha de pensionista). Ignorar para o evento.

**Carimbo de ingestão:** `fonte='WS_SIAPE:consultaDadosFinanceirosHistorico'`,
`cod_mecanica='ingestao'`, `grau_confianca='alto'`.

---

## §3 — CONTRIBUICAO_PSS — §4.22 `listaContribuicoesPSS`

**Saída:** `ArrayOfArrayContribuicoesPSS` (`WSDL:170`). Aqui o shape real DIVERGE do PDF (pág. 45) e
do catálogo v1.2: **não é lista plana — é aninhada ano → mês → contribuição:**

```
ArrayOfArrayContribuicoesPSS                    (WSDL:170)
 └─ ArrayContribuicoesPSS    unbounded          (WSDL:175)   → por vínculo
     └─ anoContribuicoesPSS : ArrayOfAnoContribuicoesPSS
         └─ AnoContribuicoesPSS  unbounded       (WSDL:185)   → por ano
             ├─ ano : xsd:string                              ← NÍVEL → achata p/ ano_contribuicao
             └─ mes : ArrayOfMesContribuicoesPSS
                 └─ MesContribuicoesPSS  unbounded (WSDL:196)  → por mês
                     ├─ mes : xsd:string                       ← NÍVEL → achata p/ mes_contribuicao
                     └─ contribuicoesPSS : ContribuicoesPSS    (WSDL:202)
```

`ContribuicoesPSS` (folha, `WSDL:202`) — todos `xsd:string`, `minOccurs=0`, `nillable=true`:

| Tag XML | Payload `CONTRIBUICAO_PSS` | Nota |
|---|---|---|
| `pssApurado` | `pss_apurado` | catálogo int; WSDL string → coerção |
| `pssInformado` | `pss_informado` | — |
| `remuneracaoPss` | `remuneracao_pss` | base de cálculo |
| `remuneracaoPssAjustada` | `remuneracao_pss_ajustada` | — |
| `indiceReajuste` | `indice_reajuste` | — |
| `percentualRemunerado` | (descarta) | ✔ §5.5 |
| `remuneracaoConsiderada` | (descarta) | ✔ §5.5 |
| `remuneracaoInformada` | (descarta) | ✔ §5.5 |

`ano`/`mes` (níveis da árvore) → `ano_contribuicao`/`mes_contribuicao` no payload (achatados). Chave
de coalescência: `(ano_contribuicao, mes_contribuicao)` + vínculo.

> **✔ RESOLVIDO (§5.4, TL 2026-07-14):** **achata.** O conector planifica (`ano`,`mes`) da árvore
> para dentro do payload de cada competência.

> **✔ RESOLVIDO (§5.5, TL 2026-07-14):** os 3 campos novos (`percentualRemunerado`,
> `remuneracaoConsiderada`, `remuneracaoInformada`) **descartam**.

> **✔ Não era pendência real — catálogo v1.2 correto:** o payload de dias-líquidos (contribuição PSS
> + férias/LPA/afastamentos/reclusão) é como o catálogo v1.2 modela. O conector monta esse payload no
> fluxo de ingestão; de onde cada campo é lido no serviço é detalhe de *wiring*, não muda a decisão.
> Férias entram só com `data_ini`/`data_fim` (§5.7). **Nada a revisar no catálogo.**

**Carimbo de ingestão:** `fonte='WS_SIAPE:listaContribuicoesPSS'`, `cod_mecanica='ingestao'`,
`grau_confianca='alto'`. Sem piso temporal — a série cobre a vida funcional inteira do vínculo.

---

## §4 — Regras de valor (comuns aos shapes, do WSDL)

1. **TODOS os campos-folha dos shapes são `xsd:string`** — inclusive numéricos (`valorRubrica`,
   `pssApurado`, `numeroSeq`) e datas. **A coerção de tipo é responsabilidade do CONECTOR, nunca
   presumida no de-para.** O de-para só registra a coerção-alvo; não a executa.
2. **Datas:** o manual dá `DDMMYYYY` sem separador; o WSDL só diz `string`. O conector re-parseia
   (`ddmmyyyy_para_iso`); **validar o formato real no 1º retorno**.
3. **Vazio vs. ausente:** `minOccurs=0` + `nillable=true` em tudo. Distinguir tag vazia (NULL
   legítimo) de tag ausente (defeito) continua valendo (degradação graciosa, ADR-009).
4. **`xsd:int`:** só no wrapper financeiro (`codigoOrgao`, `matricula` em `ArrayDadosFinanceiros`,
   `WSDL:4`) e em `CargoPca` (§7). Nos demais, tudo `string`.
5. **Ordem dos elementos:** as árvores acima exibem os filhos em ordem de leitura (chave primeiro,
   array aninhado por último). A ordem *on-wire* segue a `xsd:sequence` do WSDL (alfabética); não
   afeta o parse — o conector casa por *local-name* (namespace/ordem-agnóstico).

---

## §5 — Decisões do Tech Lead (2026-07-14)

Todas decididas. As que restam "abertas" são confirmações de **conteúdo** contra o 1º payload
*live*, não de estrutura.

1. **✔ AFASTAMENTO / 4 campos de diploma** → **descarta** (legado); revisar se aparecer no live.
2. **✔ FECHAMENTO_FOLHA / competência** → `mesAnoPagamento` **é** a competência (`mes_competencia`,
   chave); `mes_pagamento` não modelado. **Desbloqueia o mapa §4.20.** *Live:* confirmar que
   `mesAnoPagamento` é referência, não desembolso (senão, competência ← `dataAnoMesRubrica`).
3. **✔ FECHAMENTO_FOLHA / `tipo_fechamento`** → deriva de `indicadorMovSupl`; suplementar é folha
   contingente própria (esperado homogêneo). *Live:* se vier misto, tratar como suplementar.
4. **✔ CONTRIBUICAO_PSS / achatamento ano-mês** → **achata** no conector.
5. **✔ CONTRIBUICAO_PSS / 3 campos novos** → **descarta**.
6. **✔ CONTRIBUICAO_PSS / dias-líquidos** → não era pendência real: o catálogo v1.2 está correto. Os
   arrays entram no payload PSS como o catálogo modela; de onde o conector lê cada campo é wiring,
   não muda decisão. Nada a revisar.
7. **✔ `DadosFerias`** → só `data_ini`/`data_fim`; os outros 11 campos descartam.
8. **✔ `consultaHistoricoPCA`** → **TOCA** o retroativo (não redundante com FOTO-diff). De-para de
   código **fechado** com a tabela do TL (§7): as formas mapeiam PROVIMENTO/PROGRESSAO/
   RETORNO_VINCULO/DESLIGAMENTO; 5 arestas anotadas no §7.

**⏸ Pós-live:** `codigoOrgao` (folha) — entra ou descarta? Depende de saber se varia com cessão.

---

## §6 — Carimbos de ingestão por face (ADR-014, imutáveis)

| Evento | `fonte` | `cod_mecanica` | `grau_confianca` |
|---|---|---|---|
| AFASTAMENTO | `WS_SIAPE:consultaDadosAfastamentoHistorico` | `ingestao` | `alto` |
| FECHAMENTO_FOLHA | `WS_SIAPE:consultaDadosFinanceirosHistorico` | `ingestao` | `alto` |
| CONTRIBUICAO_PSS | `WS_SIAPE:listaContribuicoesPSS` | `ingestao` | `alto` |
| PROVIMENTO/PROGRESSAO/RETORNO_VINCULO/DESLIGAMENTO (retroativo) | `WS_SIAPE:consultaHistoricoPCA` | `ingestao` | `alto` |

---

## §7 — PCA `consultaHistoricoPCA` — fonte ativa de entrada/saída de vínculo (decisão §5.8)

`consultaHistoricoPCA` → `ArrayOfCargoPca` (`WSDL:755`) → `CargoPca` (`WSDL:760`, `unbounded` por
matrícula). É a **única fonte SIAPE com histórico datado de provimento/vacância de cargo**. Por
decisão do TL (2026-07-14) alimenta, no retroativo, **PROVIMENTO, PROGRESSAO, RETORNO_VINCULO e
DESLIGAMENTO** — cada `CargoPca` é um intervalo de ocupação de cargo; a *forma* decide o tipo.

`CargoPca` (campos): `matriculaSiape`/`matriculaSiapecad` (`int`, chave), `codigoCargo`/`codigoVaga`/
`codigoOrgao` (`int`), `nomeCargo`, `dataInicio`, `dataFim`, `formaProvimento`, `formaVacancia`,
`numeroDlProvimento`/`dataPublicacaoDlProvimento`/`tipoDlProvimento`/`dlProvimentoLegado`,
`numeroDlVacancia`/`dataPublicacaoDlVacancia`/`tipoDlVacancia`/`dlVacanciaLegado`, `situacaoPca`,
`siglaNivelCargo` (todos `string` salvo os `int` acima).

**De-para de evento (código fechado com a tabela do TL, 2026-07-14).** Campos comuns:
`dataInicio`→`data_evento` da entrada; `dataFim`→`data_evento` da saída (vazio = ainda no cargo);
`codigoCargo`/`nomeCargo`→`cargo` (ref `dom_cargo`); `numero`/`dataPublicacao Dl*`→proveniência
documental (descarta ou payload-extra). A **forma** decide o tipo do evento:

**`formaProvimento` → evento de ENTRADA:**

| cód | Forma | Evento MDM | Nota |
|---|---|---|---|
| 001 | Nomeação | PROVIMENTO | originário; abre o vínculo |
| 002 | Promoção | **PROGRESSAO** | classe/padrão superior — não é PROVIMENTO |
| 003 | Readaptação | PROVIMENTO (derivado) | investidura em cargo compatível c/ limitação ⚠ |
| 004 | Reversão | **RETORNO_VINCULO** | `tipo_retorno=reversao` |
| 005 | Aproveitamento | **RETORNO_VINCULO** | retorno de disponibilidade ⚠ (tipo fora do enum do catálogo) |
| 006 | Reintegração | **RETORNO_VINCULO** | `tipo_retorno=reintegracao` (tpReint=1) |
| 007 | Redistribuição | REMOCAO / transferência | par do 007 vacância (mesmo fato ent/saída) ⚠ |
| 008 | Recondução | **RETORNO_VINCULO** | `tipo_retorno=reconducao`. ⚠ PCA 008 ≠ S-2299 08 (exoneração) |

**`formaVacancia` → evento de SAÍDA (DESLIGAMENTO salvo nota; `situacao_resultante` derivada):**

| cód | Forma | Evento MDM | situação | Nota |
|---|---|---|---|---|
| 007 | Redistribuição | DESLIGAMENTO | TRANSFERIDO | saída p/ outro quadro; par do 007 provimento |
| 534 | Transformação | — | — | alteração de estrutura do cargo ⚠ não-evento de pessoa → provável descarte |
| 601 | Exoneração a pedido | DESLIGAMENTO | DESLIGADO | — |
| 602 | Exoneração de ofício | DESLIGAMENTO | DESLIGADO | ex.: reprovação em estágio probatório |
| 603 | Demissão | DESLIGAMENTO | DESLIGADO | penalidade disciplinar |
| 606 | Aposentadoria | DESLIGAMENTO | **INATIVO** | não é Desligado |
| 608 | Falecimento | DESLIGAMENTO | DESLIGADO (óbito) | — |
| 611 | Posse em cargo inacumulável | DESLIGAMENTO | DESLIGADO | vacância por assumir outro cargo |
| 615 | Destituição de cargo em comissão | ALTERACAO_FUNCAO **ou** DESLIGAMENTO | depende | ⚠ vínculo=cargo em comissão → DESLIGAMENTO; só a função → dispensa |

> **⚠ 5 arestas (mapeadas com o default acima; corrija se quiser outro roteamento):** 003 Readaptação
> (PROVIMENTO derivado?), 005 Aproveitamento (RETORNO_VINCULO sem `tipo` no enum), 007 (entrada+saída
> são o mesmo fato — dedup), 534 Transformação (não-evento?), 615 Destituição (função × vínculo). Os
> demais são 1:1. **Seed:** `dom_motivo_deslig` usa códigos S-2299; estes são códigos PCA — o domínio
> precisa das entradas correspondentes (ou tradução PCA→S-2299).

> **Reconciliação com FOTO-diff (ADR-008):** a mesma nomeação pode chegar por PCA (retroativo) e por
> FOTO-diff (presente). Dedup/coalescência por chave (`matricula`, `dataInicio`) + `data_carga` mais
> recente, como qualquer evento. Não é fonte concorrente na acepção da ADR-014 (faces distintas no
> tempo), mas o replay precisa não duplicar a abertura.

---

## Rodapé — o que este documento faz e NÃO faz

- **Registra** as decisões do TL de 2026-07-14 (§5) sobre o de-para; **não** edita schema, ADR nem
  código do contrato.
- **Não** coage tipos (coerção é do conector; o de-para só registra o alvo).
- **Follow-ups fechados.** O de-para de código do PCA foi fechado com a tabela do TL (§7); restam só
  as 5 arestas anotadas lá e um seed de `dom_motivo_deslig` com os códigos PCA. Catálogo v1.2 não
  precisa de correção (§5.6).
- **Desbloqueado:** com §5.2 decidida, os mapas `FINANCEIRO`/`PSS` podem ser escritos no
  [`siape_envelope.py`](../pipeline/contrato/siape_envelope.py) (ao lado de `FUNCIONAIS`/
  `AFASTAMENTO`, que são o de-para "v0.2" das faces FOTO e afastamento).
