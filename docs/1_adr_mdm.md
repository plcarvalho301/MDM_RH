# MDM-RH — Decisões de Arquitetura (ADR)

Registro das decisões arquiteturais do MDM-RH. Duas seções:

- **Seção 1 — ADRs (numeradas):** decisões FECHADAS. ADR numerada é sagrada — só muda por ADR nova que a supersede explicitamente. Cada uma é da mesa de engenharia/arquitetura (Tech Lead) ou herdada do canon do órgão-mãe (imutável para o piloto).
- **Seção 2 — Decisões em aberto (não numeradas):** fortes, com direção, mas NÃO fechadas. Dependem do dono do domínio (RH), de outro órgão (Corregedoria), ou de fato a apurar. Viram ADR numerada quando o martelo bate.

Convenção: o catálogo (`3_catalogo_eventos_v1.yaml`) é o **o quê** (schema vivo, muda toda hora). Este arquivo é o **porquê** (decisão, imutável quando numerada). O catálogo referencia a ADR; não repete a justificativa.

Data: 2026-06-23. Última atualização: 2026-07-05 (+ADR-008, +ADR-009, +ADR-010, +ADR-011).

---

# SEÇÃO 1 — ADRs (FECHADAS, NUMERADAS)

---

## ADR-001 — Fronteira FOTO × EVENTO

**Decisão.** O modelo tem duas naturezas de dado, ortogonais. **FOTO**: estado vigente live (o que o servidor vê no SouGov), sobrescreve em D-1, não é event sourcing. **EVENTO**: série datada, append-only, replay reconstrói o estado. Um mesmo dado pode ter as duas faces (cargo, lotação, remuneração: vigente na foto + histórico em evento). Um tipo de evento **nasce por uso** — porque precisa ser categorizado (Calculadora) ou exibido (Filme) — **não por completude do mundo**. O MDM é **System of Record, não System of Truth**: o que fica só na foto e ninguém precisa como histórico NÃO vira evento. Porém, uma vez que o tipo de evento existe, a **série é exaustiva** dentro do escopo dele.

**Contexto.** O histórico funcional do servidor não existe hoje como dado consultável (3+ sistemas, planilhas, SEI, PDF). O projeto faz existir. Era preciso uma regra que dissesse o que merece ser modelado como série temporal e o que basta existir como estado atual — sem a qual o modelo incha tentando historizar tudo (ex.: mudança de endereço), ou subentrega deixando de historizar o que o cálculo previdenciário exige.

**Opções consideradas.**
1. Event sourcing puro: tudo é evento, a foto é projeção. Rejeitada — custo de modelagem e ingestão injustificável para dados sem uso histórico (cadastro/endereço); transforma SoR em SoT por construção.
2. Só foto (estado atual): sem série. Rejeitada — inviabiliza cálculo de aposentadoria (exige toda a folha desde o ingresso) e o "Filme" da trajetória funcional, que são entregas do piloto.
3. **Duas naturezas coexistentes, evento por uso, série exaustiva por tipo.** Escolhida.

**Resultado.** Regra de fronteira fechada. Evento só entra no catálogo com uso confirmado (categorizar ou exibir). A divergência entre o replay da série e o estado vigente é tratada como sinal de qualidade / motor de adoção, não como falha. Proveniência e grau de confiança viajam dentro de cada evento; `cod_mecanica` (ingestao/extracao) é ortogonal à natureza. **Escopo e timing de quais usos entram quando é decisão de PM, não da regra.**

---

## ADR-002 — Matrícula como chave soberana exposta; UUID como PK interna

**Decisão.** A `matricula_funcional` é a **chave soberana exposta** do servidor: âncora estável, opaca, que outros domínios usam para pendurar vínculo. Mas a **PK técnica interna** de `vinculo_funcional` é um **UUID**, não a matrícula. A matrícula é atributo único exposto; não é a chave primária física das tabelas de vínculo.

**Contexto.** O canon do órgão-mãe define a matrícula como chave soberana da identidade do servidor (Espec_Entidades, matriz RACI+G). Isso resolve a identidade *para fora* (a plataforma de produção ancora vínculo R6 na matrícula). Mas para *dentro* do MDM há um problema: 1 CPF tem N vínculos (N matrículas), e o SERPRO **não confirma que matrícula não é reciclada** — uma matrícula liberada pode, em tese, ser reatribuída. Usar matrícula como PK física amarra a integridade referencial a um identificador que o provedor da fonte não garante imutável/único no tempo.

**Opções consideradas.**
1. Matrícula = PK física. Rejeitada — risco de colisão por reciclagem não confirmada pelo SERPRO; PK física deve ser garantida pelo MDM, não pela boa-fé da fonte.
2. CPF = PK. Rejeitada — 1 CPF : N vínculos; CPF identifica a pessoa, não o vínculo, que é o grão do golden record funcional.
3. **UUID interno como PK; matrícula como chave soberana exposta + atributo único.** Escolhida — desacopla a integridade interna (garantida pelo MDM) da chave de interoperação (garantida pelo canon, exposta para fora).

**Resultado.** PK física de `vinculo_funcional` = UUID gerado pelo MDM. Matrícula = atributo único, indexado, exposto como âncora de vínculo R6. Aterrissado em `3_depara_vinculo_v0_4.md`: `id_vinculo` (UUID) é PK, `matricula_funcional` é UNIQUE, `cpf_servidor` é FK para `3_depara_cadastro` (grão pessoa).

---

## ADR-003 — Vínculo R6: o MDM não re-modela o domínio de produção

**Decisão.** O MDM é dono do servidor (golden record) e expõe a matrícula como chave estável. Qualquer associação do servidor a temática, aptidão, credenciamento ou qualquer objeto da **produção de inteligência** é criada **do lado da produção**, ancorada na matrícula — o MDM **não guarda** esse vínculo. Anti-padrão recusado: tabela `servidor_tematica` / `servidor_aptidao` / `servidor_credenciamento` dentro do MDM.

**Contexto.** O órgão-mãe é de inteligência; o core é produzir Conhecimento de Inteligência, governado pelo Comitê de Governança de Dados via taxonomias doutrinárias (Temática, Iniciativa — Decreto 8.793/2016, PNI). O piloto de RH é área-meio, mas é o **precedente declarado** do modelo de identidade da plataforma inteira. Existe um cruzamento que *parece* dado de RH — "este servidor está apto na temática X" — mas é governança da produção (política de aptidão materializada via IAM do lado deles), não dado de RH. Modelar isso dentro do MDM seria invadir o domínio de produção e contaminar o precedente.

**Opções consideradas.**
1. Modelar aptidão/credenciamento no MDM (parece conveniente, "já que temos o servidor"). Rejeitada — re-modela o que o canon define como produção; cria a tabela anti-padrão; quebra a fronteira que o piloto existe para provar.
2. **Expor matrícula como âncora; produção cria o vínculo do lado dela (vínculo R6).** Escolhida.

**Resultado.** Regra de ouro para dúvida de fronteira: *de quem é a dor que o dado resolve?* Dor do RH (achar histórico, lotação, competência) → modela. Dor da produção (quem pode produzir sobre o quê) → vínculo, não modela. Herdada do canon (Espec_Entidades, invariante Pessoa-servidor) — imutável para o piloto.

---

## ADR-004 — Motivo no payload, não tipo de evento separado

**Decisão.** Famílias de evento que diferem só pelo **motivo** são modeladas como **um único tipo de evento**, com o motivo no payload referenciando um domínio — não como N tipos distintos. Casos: **AFASTAMENTO** (um tipo; motivo = `cod_afastamento` via `dom_afastamento`, S-2230) e **DESLIGAMENTO** (um tipo; motivo = `cod_motivo_deslig` via `dom_motivo_deslig`, mtvDeslig do S-2299). A situação resultante (ex.: Desligado vs. Inativo na aposentadoria) é **derivada** do código do motivo, não de tipos separados.

**Contexto.** Há ~20 motivos de afastamento e vários de desligamento na Tabela de Domínios eSocial/Sigepe. Cada um carrega parâmetros próprios (conta efetivo exercício, impacto previdenciário, situação resultante). Modelar um tipo de evento por motivo multiplicaria o catálogo por 20+ e espalharia a lógica de cálculo pelo schema em vez de concentrá-la no domínio.

**Opções consideradas.**
1. Um tipo de evento por motivo (AFASTAMENTO_DOENCA, AFASTAMENTO_MATERNIDADE, ...). Rejeitada — explosão de tipos; parâmetros de cálculo viram regra hardcoded por tipo em vez de dado de domínio.
2. **Um tipo, motivo no payload via domínio; parâmetros de cálculo no domínio.** Escolhida — o domínio (`dom_afastamento`, `dom_motivo_deslig`) carrega `conta_efetivo_exercicio` e impacto previdenciário por motivo; a projeção lê do domínio.

**Resultado.** Catálogo enxuto; um envelope de evento por família. Decisão de modelagem do event store — mesa do Tech Lead. Nota: a *taxonomia de subdomínios* onde esses tipos moram é decisão de RH (ver Seção 2) — esta ADR é sobre a forma do tipo de evento, não sobre a gaveta.

---

## ADR-005 — Capacidades o MDM modela; aptidão é da produção

**Decisão.** **Capacitação e competência** do servidor (curso feito, trilha concluída, competência mapeada — KR 3.2 / Sisdip) são desenvolvimento de pessoas: **RH, o MDM modela e expõe**. **Aptidão temática / credenciamento** ("servidor apto a validar produto na temática X") é governança da produção via IAM: **o MDM não modela**. A competência *alimenta* a aptidão, mas não *é* a aptidão.

**Contexto.** As duas coisas parecem a mesma e a linha é sutil: "servidor fez o curso de análise de vínculos" (capacitação, RH) vs. "servidor está apto a validar produto na temática crime organizado" (aptidão, produção). Sem a linha cravada, o MDM acabaria modelando credenciamento — o mesmo anti-padrão da ADR-003, por outra porta.

**Opções consideradas.**
1. Modelar capacitação E aptidão juntas (ambas "parecem RH"). Rejeitada — aptidão é vínculo R6, não dado de RH; cai no anti-padrão da ADR-003.
2. Não modelar nenhuma das duas (jogar tudo pra produção). Rejeitada — capacitação/competência são dor do RH, core do desenvolvimento de pessoas, dentro da fronteira.
3. **Modelar capacidades; expor; deixar aptidão para a produção ancorar via vínculo.** Escolhida.

**Resultado.** Capacidades vivem no eixo profissional (`3_catalogo_estendido_v1.yaml`), dependência externa, fora do passo (a) de descoberta atual. Aptidão nunca entra no schema do MDM. Caso particular da ADR-003, herdado do canon — imutável para o piloto.

---

## ADR-006 — A separação FOTO × EVENTO acontece no pipeline, registro a registro — não na fonte

**Decisão.** A natureza do dado (FOTO ou EVENTO, ADR-001) **não é propriedade da fonte** — é decidida **dentro do fluxo de ingestão**, não na origem. Toda fonte — API viva ou carga batch — pode produzir **as duas naturezas ao mesmo tempo**. A sequência canônica de uma rodada de ingestão é fixa: **`extrai → valida → classifica → {atualiza FOTO | registra EVENTO | rejeita}`**. As mecânicas de gravação são opostas e não coabitam: FOTO faz **upsert por matrícula (SOBRESCREVE)**; EVENTO faz **INSERT (APPEND)**; refugo vai para **quarentena** (`rejeito`), cuja contagem É o delta de incompletude (motor de adoção), não descarte.

**Contexto.** Duas premissas erradas foram derrubadas ao desenhar o pipeline. A primeira: "há uma DAG da foto e uma DAG do evento", que amarrava a natureza do dado ao fluxo físico. A segunda, mais sutil: "uma fonte tem uma natureza" — tratar o Extrator como fonte de foto. Ambas falsas: o Extrator traz `SIAPE-SERVIDOR-EXTR` (estado) **e** `SIAPE-ANO-MES-SSER` (série datada) no mesmo acervo; a carga inicial dos legados (SQL, Oracle, Excel, papel) traz o vigente **e** o histórico de quem entrou em 1982, no mesmo lote. Natureza (foto/evento) e mecânica de carga (`cod_mecanica` = ingestao/extracao) são **ortogonais** — já dito na ADR-001, mas não aterrissado no desenho do fluxo. Sem um passo que separe registro a registro, ou se historiza o que é estado, ou se perde a série que veio junto. E como dado de sistema de governo chega sujo (data faltando, matrícula que devia repetir e não repete, campo que mente), o passo de separação **tem** de absorver a bagunça — refugo é saída esperada e medida, não exceção rara.

**Opções consideradas.**
1. Uma DAG por natureza (DAG-foto, DAG-evento). Rejeitada — amarra natureza a fluxo; a mesma fonte teria de aparecer em duas DAGs, e a separação real (registro a registro) não tem onde acontecer.
2. Classificar na fonte (a fonte declara "sou foto" ou "sou evento"). Rejeitada — nenhuma fonte tem uma natureza só; e confiar na declaração da fonte presume limpeza que o dado de governo não tem.
3. **Separação no pipeline, registro a registro, num passo `classifica` que também carimba proveniência e manda refugo para quarentena.** Escolhida — a natureza é decidida no único lugar que vê o registro individual; FOTO e EVENTO recebem o que lhes cabe; a quarentena vira métrica.

**Resultado.** Sequência de ingestão fixada em `3_dag_ingestao.mermaid`; schema das duas tabelas de pouso (`servidor` = foto/upsert, `evento` = série/append) + `rejeito` (quarentena) em `3_schema_mdm.sql`. **Proveniência e grau de confiança são carimbados no `classifica`** (campos `fonte`, `cod_mecanica`, `grau_confianca` no envelope do evento) — é o que permite desempatar divergência entre fontes depois (ex.: Extrator diz X, API diz Y). Ordem `valida` **antes** de `classifica` é deliberada: descarta lixo estrutural antes de decidir natureza, senão classifica-se lixo. **A decisão de natureza pode ser pré-computada — o passo `classifica` é roteamento + quarentena, não necessariamente julgamento em runtime.** Onde a fonte permite pré-classificar (varredura do Extrator, `3_arqueologia_extrator_v0_1.yaml`, critério "matrícula repete com data distinta = evento"), a natureza de cada um dos 274 arquivos já vem decidida antes da extração; o `classifica` só lê a marca e roteia. Onde o registro chega cru sem marca, o `classifica` decide ali. O pipeline acomoda os dois — e `valida` checa adequação ao schema do mesmo jeito (mandando refugo à quarentena) independentemente de a natureza ter vindo pronta. Se o dev implementa um check de flag (`evento=true`) ou passa reto é detalhe de implementação, indiferente ao modelo. O `diff` da FOTO pós-go-live é **uma origem secundária** de EVENTO (entra como mais uma fonte no topo do fluxo), não o eixo — o grosso da série vem do histórico que já chega dentro do Extrator e dos legados. Decisão da mesa de engenharia (Tech Lead).

---

## ADR-007 — Constituição das views de exposição: objeto por fronteira, não por painel

**Decisão.** Cada painel Power BI lê um **objeto de exposição** (view ou materialized view), **nunca** as tabelas-base (`servidor`, `evento`). O número de objetos segue o número de **fronteiras de recorte distintas**, não o número de painéis — um painel pode virar N objetos, N painéis podem compartilhar um. Duas superfícies compartilham objeto se, e só se, têm **mesmo payload e mesmo recorte de linha**; payload diferente → objetos separados.

Materialização (view comum × MV) é decisão **ortogonal** à fronteira e decidida por **custo**: **MV só quando a cópia física paga aluguel** — densidade que dói no clique (Calculadora: série de 30+ anos por matrícula) ou isolamento do banco vivo de query pesada. Onde o corte é só de coluna sobre base leve (FOTO), **view comum basta**. Entre os dois desenhos, o de menos peças vence.

Mapa de objetos do piloto:

| Painel | Objeto | Tipo | Recorte |
|---|---|---|---|
| Foto de Hoje | `vw_foto` | view (default) | público institucional |
| Lente Estratégica | `vw_lente` | **view sobre a Foto** | agrega números sobre o que a Foto já expõe |
| Filme-Servidor | `mv_filme_servidor` | **MV** | payload cheio; RLS → própria matrícula |
| Filme-Gestor | `mv_filme_gestor` | **MV** | payload **reduzido** (gerencial); RLS → sub-árvore |
| Calculadora | `mv_calculadora` | **MV** | série densa PSS/financeiro |
| RH / Corregedoria | *nenhum* | **GRANT SELECT direto** em `servidor`+`evento` | acesso privilegiado documentado — não é painel |

**Contexto.** O painel lendo objeto de exposição (não tabela-base) serve a dois propósitos: **isolar o banco vivo** (o painel nunca abre conexão contra a base transacional; lê snapshot ou recorte) e **cortar o payload por conveniência de painel** (o gestor vê o recorte gerencial porque é o que lhe serve). O corte de payload é feito **no DDL do objeto**, não no Power BI — payload no BI é retrabalho e o objeto é o lugar certo do recorte. Segurança de acesso não entra nesta ADR: a infra é on-prem com acesso controlado pessoa a pessoa, meia dúzia de acessos privilegiados, sem PAM — sensibilidade é não-questão resolvida por infraestrutura, não variável de design.

**Opções consideradas.**
1. Um objeto por painel (4 painéis = 4 MVs). Rejeitada — ignora que Foto e Lente compartilham recorte (uma serve as duas) e que o Filme precisa de **dois** objetos (payloads diferentes). O número bate com fronteira, não com painel.
2. Uma MV central consolidada alimentando todos os painéis (o que o `3_lifecycle_mdm.mermaid` v0.1 desenhou). Rejeitada — cópia física gorda servindo recortes distintos sem ganho; contradiz a Q3 (sem pré-materialização de snapshot histórico) que o próprio lifecycle declara. O nó `MV` fantasma do lifecycle sai.
3. Painel lê tabela-base direto. Rejeitada como padrão — não isola o banco vivo. Aceita **só** para RH/Corregedoria, onde o recorte é "tudo" (não há o que cortar) e o acesso replica o que já existe hoje no Sigepe live.
4. **Objeto por fronteira de recorte; materialização por custo; base-direto só para o acesso privilegiado.** Escolhida.

**Resultado.**
- **Foto**: view comum sobre `servidor` (base leve, upsert D-1 — MV não paga aluguel aqui). A coluna `cod_afastamento_vigente` **permanece na FOTO** — é a face-foto do afastamento (estado vigente resolvido, gravado no D-1, mesmo padrão de `situacao_funcional`); a série datada completa vive no evento `AFASTAMENTO` (`intercorrencias`; faces distintas do mesmo fato, ADR-001). A view de exposição deriva `afastado? (S/N)` de `cod_afastamento_vigente IS NOT NULL` — o painel exibe o booleano, não o código cru. Decisão de exposição, não de modelagem: a coluna existe, o painel não a mostra.
- **Lente**: view comum sobre a Foto (`GROUP BY uorg` etc.). Enquanto agregar **sobre Foto**, não toca EVENTO. Indicador agregado sobre EVENTO (ex.: suspensões × uorg) é outra fonte, outro objeto — fora do escopo desta view.
- **Filme**: duas MVs. A diferença de payload (Servidor cheio × Gestor reduzido) manda objetos separados — o recorte gerencial do Gestor é DDL da MV, não SELECT sobre base comum. RLS recorta linha dentro de cada MV (Servidor → própria matrícula via de-para AD↔matrícula; Gestor → sub-árvore via árvore de cargos).
- **Calculadora**: MV — a materialização paga aluguel por densidade (série longa por matrícula).
- **RH/Corregedoria**: GRANT SELECT direto em `servidor`+`evento`, role mínimo (grão de tabela nomeada, não database). Fora do escopo "4 painéis" → acesso privilegiado documentado.
- **REFRESH das MVs**: processamento — relógio do Airflow, ciclo D-1, credencial do Airflow. Passo novo no `3_dag_ingestao.mermaid` (hoje o DAG para nos 3 objetos persistidos). O SELECT do usuário é uso.
- **KR 2.2 intacto**: `vw_afastado_conta_exercicio` segue lendo `servidor.cod_afastamento_vigente` (a coluna fica na FOTO). Nenhuma cascata.
- **Vitrine ODBC das MVs** (aterrissado no schema v0.7): o driver psqlODBC não enumera `relkind='m'` no Navegador do Power BI — MV existe e responde, mas fica invisível pro conector. Fix: uma view fina de passagem por MV (`vw_mv_filme_servidor`, `vw_mv_filme_gestor`, `vw_mv_calculadora`, `SELECT *` sobre a MV homônima). **Não é nova fronteira**: quem materializa continua a MV; o recorte de payload/linha já foi aplicado na MV uma camada abaixo; GRANT/RLS continuam desenhados sobre a MV. A view fina é transparente (compat de catálogo, não recorte) — por isso `SELECT *`, que auto-espelha o shape e dispensa manter uma segunda superfície em sincronia. Se algum dia precisar cortar algo a mais, vira outra fronteira e sai de "vitrine". Provado e2e contra Postgres 18.4 em 2026-07-04.

Decisão da mesa de engenharia (Tech Lead). O **payload campo-a-campo** de cada objeto (o que entra/não entra em cada MV do Filme, colunas exatas da Lente) é refinamento subsequente, aterrissado no DDL do `3_schema_mdm.sql` — esta ADR fixa a **constituição** (quantos objetos, por que, view×MV, quem faz REFRESH), não o payload.

**Pendências (não bloqueiam o fechamento):**
- **Estratégia de REFRESH da Calculadora**: full trava a MV durante o refresh; `CONCURRENTLY` não trava mas exige índice único e é mais lento. Série densa pode não caber na janela D-1 em full — decidir na implementação; vira decisão de arquitetura só se a janela apertar.
- **Vazamento de domínio implícito por código SIAPE**: verificar contra a Tabela de Domínios eSocial se há leiaute S-XXXX que exponha CID/diagnóstico. Não confirmado; verificação ao abrir o payload dos eventos de afastamento-saúde. Não afeta a Foto (não tem o campo).
- **Descrição human-readable do evento** (levantada na sessão 2026-07-04): no Filme, `payload` aparece como JSON cru; falta uma frase textual não-sensível por evento ("Assumiu cargo em [unidade]", "Licença-capacitação"). Direção coerente com o princípio já fechado (corte no DDL, não no BI): parse na camada de view SQL — `CASE` por `cod_tipo_evento` + JOIN nos `dom_*` para traduzir código em nome; campo sensível fica fora da frase e só no payload cru sob GRANT largo. **Não fecha aqui** — esbarra em duas coisas ainda abertas: o payload campo-a-campo de cada MV (acima) e o recorte fino de "o que é sensível" campo a campo. Trade-off a decidir: travar a frase no schema dá consistência entre as 4 lentes mas cada ajuste vira `CREATE OR REPLACE VIEW`, não edição de medida no BI.

---

## ADR-008 — Intercorrência é intervalo: data_fim no payload; fechamento por segundo registro; coalescência

**Decisão.** Término e renovação de cessão e afastamento **não** são tipos de evento. A duração é **atributo do próprio evento** (`data_inicio` + `data_fim` no payload de AFASTAMENTO e CESSAO; `data_fim` nula = vigente em aberto). **Renovação sucessiva** = N eventos do mesmo tipo com `data_inicio` distintas. **Fechamento de evento aberto** (a `data_fim` não veio na emissão — o caso normal da vida real): emite-se um **segundo registro imutável do mesmo tipo, com a mesma chave de intercorrência** (`matricula`, `cod_afastamento`/cessão, `data_inicio`) e a `data_fim` preenchida; a **projeção coalesce** — vale o registro de `data_carga` mais recente (mesmo padrão da folha suplementar, FECHAMENTO_FOLHA). Consequência no replay: **intercorrência é intervalo que expira por data**, não par de transições AFASTA/RETOMA; expirada a `data_fim` de uma cessão, o vínculo volta à origem **sem evento de retorno**.

**Contexto.** As trajetórias do designer (handoff Reino Animal, 2026-07-05) expuseram a lacuna ⚠3: fim de cessão, fim de licença e renovações apareciam como marcos "sem tipo próprio". Três formas candidatas: atributo de duração, evento-espelho de término, ou N eventos encadeados. O catálogo v1 já carregava `data_fim` nos payloads — faltava fechar a mecânica de *preencher* uma `data_fim` desconhecida num store append-only, e a consequência no replay.

**Opções consideradas.**
1. Evento-espelho de término (FIM_AFASTAMENTO etc.). Rejeitada — dobra o catálogo, cria par órfão (término sem início e vice-versa) e re-modela como transição o que é intervalo.
2. Mutar o evento aberto (UPDATE da data_fim). Rejeitada — viola append-only; queima proveniência.
3. **Atributo de duração + segundo registro de fechamento + coalescência na projeção.** Escolhida — zero tipo novo; reusa o padrão de coalescência já fechado para a folha; o event store guarda os dois registros imutáveis e a projeção decide.

**Resultado.** Catálogo v1.1 (obs nos payloads de AFASTAMENTO e CESSAO). O replay do pipeline passa a tratar intercorrência como intervalo — mudança real na reconstrução de estado, validada por smoke test antes da massa (higiene barata: base minúscula, replay é SELECT, re-roda em segundos). O gerador de massa emite os dois modos (registro único com data_fim; par aberto+fechamento) para exercitar a coalescência. A chave de dedup do loader `(matricula, cod_afastamento, data_inicio)` é a mesma chave da coalescência — coerência de graça. Decisão da mesa de engenharia (Tech Lead, 2026-07-05).

---

## ADR-009 — Retratação operacional por partição de carga: id_carga, DETACH, ledger, manifesto pré-assinatura

**Decisão.** Defeito de dado em massa (carga com erro material que passou limpa pela validação) sai da base quente por **retirada completa da carga** — nunca linha a linha, nunca `DELETE` em massa. Mecânica: `evento` é **particionada por LIST(`id_carga`)** (uma partição por carga; `id_carga` uuid NOT NULL no envelope; sem partição default — carga sem partição aberta erra na cara). Remoção = **`DETACH PARTITION`**: instantâneo, sem DELETE/bloat, **reversível** (re-`ATTACH`), e a partição destacada **é** o cold storage. Destino condicional à fonte: re-executável (ingestão API) pode descartar; **extração/papel/OCR nunca** — o garimpo não volta. Governança: **o MDM entrega o meio; o RH assina e é dono da consequência.** Acesso exclusivo diretora do RH + TI, com **aceite protocolado**; o protocolo é a proveniência da carga-de-deleção. O **manifesto** (`fn_manifesto_carga`: contagem, vínculos/pessoas afetados, faixa de fatos, quebra por tipo/fonte, amostra, digest md5 da lista ordenada de `id_evento`) roda **antes** do detach como superfície de decisão da assinatura — não se responsabiliza quem não pôde ver o alcance — e o mesmo jsonb aterrissa **depois** no `ledger_delecao`, tabela que mora **fora das partições** de propósito (a prova sobrevive ao ato que audita).

**Distinção que rege a ADR.** Reversão de **domínio** (cassação, anulação, reintegração — o fato aconteceu e reverte estado legítimo) é **evento**, com motivo próprio, série honesta — nada sai da base (ADR-004, motivos locais). Retratação **operacional** (o registro nunca deveria ter existido) é **defeito de dado** — é o que esta ADR remove. As fixtures de teste das duas coisas não se confundem.

**Contexto.** O `rejeito` captura malformação **na porta**; não existe mecanismo para o que passa limpo e está errado contra a realidade (carga de aposentados com erro material = milhões de linhas de folha poluindo para sempre). Erro material semântico não tem assinatura pré-commit — só a realidade o desmente, e a superfície de detecção é o próprio painel (o valor do MDM é tornar visível para que o RH possa pegar). Checkpoint de reconciliação mecânica foi considerado e descartado: pega descasamento de contagem, não erro semântico — o cenário real seria pego em produção do mesmo jeito.

**Opções consideradas.**
1. DELETE + log simples (quem/o quê/por quê). Rejeitada como desenho único — transação pesada em milhões de linhas (lock/WAL/bloat), perde payload de fonte não-re-executável, e log-frase é trilha fina para dado previdenciário.
2. Deleção como carga própria + log externo + auditoria. **Frame correto** — absorvido: a unidade é a carga; a deleção é registrada; o protocolo amarra na proveniência.
3. Cold storage por cópia (move antes de deletar). Absorvida — mas como *consequência do detach* (a partição destacada já é o apartado), não como caminho separado de move+delete.
4. **Particionamento por id_carga + DETACH + ledger + manifesto.** Escolhida — unifica 1+2+3 num mecanismo só, com menos peças; deleção vira operação de catálogo, não de dados.

**Resultado.** Schema v0.8: `evento` particionada, `fn_particao_carga`, `fn_manifesto_carga`, `ledger_delecao`, `rejeito.id_carga`, procedimento documentado (manifesto → protocolo → ledger → detach → destino → refresh). **Invariante permanente:** toda projeção (MVs, FOTO) é **sempre re-derivada do cru** — nenhuma projeção cacheia efeito de evento sem rastro de carga, senão o detach limpa a base e deixa órfão na projeção (hoje vale: upsert D-1 + REFRESH; proteger em qualquer evolução). A FOTO não ganha `id_carga`: sobrescreve em D-1, retratação dela é o próximo upsert. Decisão da mesa de engenharia com governança confirmada pelo PM (2026-07-05).

---

## ADR-010 — Payload do Filme-Gestor por allowlist de coluna nomeada, não JSONB cru

**Decisão.** `mv_filme_gestor` **não expõe `payload` bruto**. Em vez de subir o JSONB inteiro (ou uma denylist de chaves subtraídas dele), a MV extrai, por **allowlist nomeada**, só as colunas que o recorte gerencial precisa — hoje `cod_afastamento`, `cod_motivo_deslig`, `data_inicio`, `data_fim`, `data_desligamento` (`payload->>'chave'`, tipadas). Cada código sobe **cru** (a tradução para nome humano é responsabilidade da dimensão relacionada — `dom_afastamento`, `dom_motivo_deslig` —, não desta view). Se o payload de um tipo de evento carregar um campo novo, sensível ou não, **ele não aparece na MV** até alguém adicionar a coluna explicitamente. `mv_filme_servidor` é o objeto oposto e complementar: payload **cheio**, porque ali o titular lê o próprio dado (nada a esconder dele mesmo) — a ADR não fecha o payload do Filme-Servidor, só o do Gestor.

**Contexto.** A primeira versão de `mv_filme_gestor` (schema v0.7/v0.8) usava **denylist**: `(payload - 'valor' - 'remuneracao' - 'base_calculo')` — subtrai três chaves financeiras conhecidas e deixa passar o resto do JSONB. O desenho é frágil por construção: **um campo sensível novo, se não estiver na lista de subtração, vaza por padrão** — o oposto do princípio de exposição mínima. A correção veio no schema v0.9 (sessão de reconciliação FOTO×EVENTO, 2026-07-05, handoff PBI rodada 1), motivada por duas dores conjuntas: (a) o Power BI não relaciona chave dentro de JSONB — toda chave que o painel usa como filtro/relação precisa ser coluna plana; (b) o filme-gestor precisava passar a ver **intercorrências** (o gestor tem que enxergar afastamento do subordinado — é o descasamento que "quebra a perna do RH" quando passa batido), e abrir esse subdomínio tornava a denylist ainda mais arriscada (afastamento carrega motivo administrativo, não diagnóstico — mas o próximo campo do payload pode não ser tão inofensivo). A correção resolveu os dois problemas com o mesmo movimento: trocar denylist por allowlist.

**Opções consideradas.**
1. **Manter denylist, ampliar a lista de subtração.** Rejeitada — não resolve a fragilidade estrutural (todo campo novo exige lembrar de adicioná-lo à lista negativa; esquecimento = vazamento silencioso); e não resolve o problema de relação do Power BI (o resto do JSONB continua opaco pro filtro).
2. **Vitrine ODBC nova, sem mudar o payload.** Rejeitada — ataca só o sintoma de relação do PBI, não o de exposição; o payload cru continua subindo por baixo.
3. **Allowlist de coluna nomeada via `->>`, com nome resolvido por dimensão relacionada (não hardcoded na frase).** Escolhida — inversão do padrão de risco: campo novo no payload **não aparece** até virar coluna explícita (fail-safe por omissão, não por lembrança); cada coluna já sai relacionável no PBI sem `->>` no cliente; o nome humano (dom_afastamento.nome_afastamento etc.) fica na dimensão, RH-editável, sem depender de reescrever a MV.

**Resultado.** `mv_filme_gestor` (schema v0.9, endurecido em v0.10/v0.11): `SELECT id_evento, matricula_funcional, cod_tipo_evento, cod_sub_dominio, data_evento, (payload->>'cod_afastamento'), (payload->>'cod_motivo_deslig'), (payload->>'data_inicio')::date, (payload->>'data_fim')::date, (payload->>'data_desligamento')::date, intervalo_vigente, fonte` — sem a coluna `payload`. `WHERE cod_sub_dominio IN ('vinculos','intercorrencias','desempenho','jornada')` (intercorrências somada nesta mesma correção). `mv_filme_servidor` permanece com `payload` cheio, por ser o objeto do titular (fronteira já fixada na ADR-007 — Filme-Servidor × Filme-Gestor são objetos separados por *terem payload diferente*; esta ADR só formaliza a forma que o payload do Gestor toma). Regra geral daqui pra frente: **todo objeto de exposição que recorta payload gerencial/externo faz allowlist de coluna nomeada — denylist sobre JSONB não é padrão aceito no MDM.** Índices de apoio (`ix_mv_filme_gestor_afast`, `ix_mv_filme_gestor_deslig`) vêm de graça por a coluna já existir plana. Fecha a pendência de payload campo-a-campo do Filme-Gestor deixada em aberto na ADR-007 (nota "vazamento de domínio implícito por código SIAPE" — resolvida por desenho, não por auditoria caso a caso). Formalizada retroativamente (decisão já implementada em produção); decisão da mesa de engenharia (Tech Lead), 2026-07-05.

---

## ADR-011 — Calculadora: MV por fronteira de payload (folha × PSS), rubrica explodida por grão

**Decisão.** `mv_calculadora` (uma MV, `payload` cru, filtro só por `cod_sub_dominio='compensacao'`) vira **duas MVs**, uma por tipo de evento: `mv_calculadora_folha` (`FECHAMENTO_FOLHA`) e `mv_calculadora_pss` (`CONTRIBUICAO_PSS`). Cada uma planifica as chaves do próprio payload em coluna (padrão Filme v0.9: `payload->>'chave'` ao lado do `payload` cru, não em vez dele — a Calculadora não tem a restrição de vazamento gerencial da ADR-010, é o mesmo titular). Dentro da folha, o grão muda de **1 linha por evento** para **1 linha por rubrica** (`CROSS JOIN LATERAL jsonb_to_recordset(payload->'rubricas')`); a chave do índice único acompanha, de `(id_evento)` para `(id_evento, numero_seq)`. A PSS fica em 1 linha por evento — não tem lista a explodir no número apurado.

**Contexto.** O handoff "Calculadora completa" (2026-07-05) fechou uma lacuna: `compensacao` só tinha `FECHAMENTO_FOLHA` migrado do `catalogo_financeiro_v0_1`; o prespec §5 pede duas fontes (folha **e** PSS, via `listaContribuicoesPSS`, WS_SIAPE_CONSULTAS 4.22). Ao nascer `CONTRIBUICAO_PSS` como segundo tipo do mesmo sub-domínio, `mv_calculadora` passou a ter duas famílias de payload sob o mesmo filtro — folha carrega lista de rubricas, PSS carrega campos apurados escalares + arrays de dias-líquidos (férias, LPA, afastamentos, reclusão). Duas perguntas separadas, as duas já sinalizadas como pendência do Code no handoff: (a) uma MV com `CASE` por tipo, ou duas MVs; (b) grão da rubrica aninhado (payload como veio) ou explodido (1 linha por rubrica).

**Opções consideradas — pergunta (a), MV única × MV por tipo.**
1. **Uma MV, `CASE`/`FILTER` por `cod_tipo_evento` pra popular cada família de coluna.** Rejeitada — produz uma tabela larga com metade das colunas sempre nula por linha (nula quando o tipo é o outro), o anti-padrão que a própria ADR-007 já evitou ao separar Filme-Servidor de Filme-Gestor ("payloads distintos → objetos distintos"). Menos objeto no banco, mas empurra a ambiguidade pro consumidor Power BI (que precisa saber filtrar por tipo antes de confiar em qualquer coluna PSS ou rubrica).
2. **Duas MVs, uma por fronteira de payload (`mv_calculadora_folha`, `mv_calculadora_pss`).** Escolhida — mesmo princípio já em produção pra Filme S/G: cada MV tem shape limpo, sem coluna sempre-nula; o Power BI relaciona as duas por `matricula_funcional`/data como duas tabelas normais do modelo, sem precisar aprender a filtrar por `cod_tipo_evento` primeiro. Um objeto adicional no banco (GRANT idêntico ao de finanças, mesmo padrão do bloco existente) é custo baixo frente à ambiguidade evitada — especialmente relevante com o usuário-alvo ainda aprendendo a interface do Power BI.

**Opções consideradas — pergunta (b), grão da rubrica.**
1. **Aninhado — payload sobe como veio, lista `rubricas` fica dentro do JSONB da coluna `payload`.** Rejeitada como ÚNICA forma de acesso — obrigaria o usuário a rodar "Expandir" de lista JSON na Power Query (transformação de nível intermediário) só pra ver `valor_rubrica` numa tabela, na frente exatamente do usuário que ainda está aprendendo os cliques básicos do Power BI.
2. **Explodido — `jsonb_to_recordset` no `SELECT` da MV, 1 linha por rubrica.** Escolhida — a coluna `valor_rubrica`/`cod_rubrica`/`indicador_rd` chega pronta, sem transformação no cliente. Custo aceito: o índice único muda de grão (`id_evento` deixa de identificar linha; `numero_seq` preserva a chave dentro do evento, já que o payload garante `numeroSeq` obrigatório) e colunas de competência (`mes_competencia` etc.) repetem por rubrica — denormalização esperada nesse grão, não bug.

**Resultado.** Schema v0.12: `mv_calculadora_folha` (colunas de competência planas + rubrica explodida + `payload` cru; `ux_mv_calculadora_folha(id_evento, numero_seq)`) e `mv_calculadora_pss` (campos apurados do 4.22 planos + `payload` cru, arrays de dias-líquidos só no cru; `ux_mv_calculadora_pss(id_evento)`). Vitrine ODBC (ADR/v0.7) ganha `vw_mv_calculadora_folha` e `vw_mv_calculadora_pss`; `vw_mv_calculadora` (única) é removida — não há dado nela hoje (massa de evento ainda não gerada pra PSS/folha; MVs compilam vazias, mesmo caso já registrado no schema v0.9). Regra geral: **quando um sub-domínio aditivo ganha um segundo tipo de payload incompatível, a MV se divide por tipo — sub-domínio é chave de gaveta do catálogo, não union implícito de shape na projeção.** Decisão do Code (task assignment explícito no handoff), 2026-07-05.

---

# SEÇÃO 2 — DECISÕES EM ABERTO (FORTES, NÃO FECHADAS)

Direção definida, martelo não batido. Não numeradas de propósito: ficam visivelmente distintas das ADRs sagradas. Promovem-se a ADR numerada quando o dono fecha.

---

### Taxonomia de subdomínios — dono é o RH

**Direção atual.** Sete gavetas em uso: `cadastro`, `vinculos`, `intercorrencias`, `compensacao`, `jornada`, `desempenho`, `capacidades`. Subdomínio = decisão de **negócio**; abaixo dele (tipo de evento, payload, campo) = decisão de Tech Lead.

**Por que está aberta.** O dono Accountable do domínio é GP/RH, não o Tech Lead (Contexto_Firma, matriz RACI+G). Logo nenhuma fronteira de subdomínio é do Tech Lead para cravar — quantas gavetas, quais, e onde cada coisa mora é decisão do dono, que ainda não passou formalmente por isso. A taxonomia atual é hipótese de trabalho boa, não canon fechado.

**O que falta.** RH validar a taxonomia como dono.

---

### Afastamento em `intercorrencias`, separado de `vinculos`

**Direção atual.** Afastamento/licença mora em `intercorrencias`, não em `vinculos` — justificativa de engenharia: afastamento não encerra o laço (classe_transicao AFASTA/RETOMA vs. ENCERRA); é um intervalo sobre o vínculo, não uma transição que o termina.

**Por que está aberta.** Para o RH, afastamento e vínculo são essencialmente sinônimos — ser "positivo" ou "negativo" é contingência, não categoria. Ou seja: a separação que o schema faz é uma fronteira que o **dono do domínio não traça**. É decisão de engenharia sobre o domínio do RH, à revelia da visão deles. Boa justificativa técnica não é o mesmo que martelo batido pelo dono. Caso particular da taxonomia aberta acima.

**O que falta.** RH validar se a separação intercorrencias/vinculos faz sentido para eles, ou se afastamento deve morar junto do vínculo.

---

### Disciplinar como subdomínio próprio

**Direção atual.** Penalidade disciplinar e afastamento preventivo (PAD) estão hoje em `intercorrencias`. Candidatos a um subdomínio `disciplinar` próprio.

**Por que está aberta.** O argumento estrutural (não o de acesso) é que o **dono do dado é a Corregedoria, não o RH** — isso quebra o default "dono = RH" e seria a justificativa para separar. Mas: (a) a taxonomia inteira é do RH para fechar; (b) ainda não se falou com a Corregedoria; (c) não se sabe sequer se o RH tem o acesso a esse dado (fonte: Extrator c/ impacto folha + API CGU/e-Aud) — é possível que o RH descubra na mesa que tem o acesso e não usa. Fica em `intercorrencias` por ora; passa com RH.

**O que falta.** Conversa com RH (e Corregedoria) sobre dono, acesso e se vira gaveta própria. Mesma mesa pode revisitar se Saúde (CID/perícia) merece recorte mais granular — hoje tratada colada aos afastamentos.

---

### Reconciliação CESSÃO: S-2231 vs. S-2230 cód.40

**Direção atual.** A cessão aparece como evento próprio (S-2231) **e** como afastamento (S-2230 cód.40). Decidir qual ingere, ou como reconciliar, para não duplicar.

**Por que está aberta.** É dúvida de fato a apurar na ingestão, não decisão tomada. Depende de ver o comportamento real das duas fontes.

**O que falta.** Definir na ingestão (mesa do Tech Lead) — vira ADR quando resolvido.

---

### Fraseamento do estado TRANSFERIDO (redistribuição)

**Direção atual.** Redistribuição (DESLIGAMENTO motivos 29/37) resolve para a situação **TRANSFERIDO** — 6º estado de `dom_situacao_vinculo`, criado no schema v0.14. Isso fecha o risco do valor órfão `TRANSFERE` (levantado na reconciliação do Project, 2026-07-05): `dom_motivo_deslig.situacao_resultante` admitia `TRANSFERE`, que não existia em `dom_situacao_vinculo` e violaria a FK `fk_situacao` no dia em que o replay gravasse a situação derivada — inerte só porque a massa não emite 29/37. **O ESTADO está fechado e implementado**; o que fica aberto é o **fraseamento**.

**Por que está aberta.** Ligada à pendência de fraseamento (descritor de evento / frase amigável — `2_descritores_eventos_v0_1.md`, item E do roadmap do gerador), ainda não modelada. Decisão do Pedro (2026-07-05): quando o fraseamento for modelado, a frase de TRANSFERIDO **tem de indicar origem E destino** — algo como "Transferido do órgão X para o órgão Y em «data»", não um "transferido" solto. Isso impõe uma **consequência de dado ainda não resolvida**: o payload de DESLIGAMENTO para 29/37 precisará capturar o **órgão destino** (a origem é o próprio órgão do vínculo). Hoje o payload só tem `cod_motivo_deslig` + `data_desligamento` — sem o destino, a frase não se monta.

**O que falta.** (a) Modelar o fraseamento (pendência E do gerador); (b) nesse momento, estender o payload de DESLIGAMENTO 29/37 com o órgão destino (campo novo, ex. `orgao_destino`); (c) confirmar se a origem sai do vínculo ou precisa ser gravada. Vira ADR numerada quando o fraseamento fechar.

---

### PROGRESSAO sem leiaute eSocial

**Direção atual.** Progressão/promoção não tem S-22xx próprio — é inferida de diff de classe/padrão. Tipo existe no catálogo com `ativo=false` (fora da Calculadora) até o RH fechar as regras de carreira (interstício, requisitos). Também é candidata forte a evento de **extração** no retroativo (a série de classe/padrão antiga não vem da API).

**Por que está aberta.** Depende de duas coisas não fechadas: regras de carreira (RH) e a fonte do retroativo (varredura do Extrator, agosto).

**O que falta.** RH fechar regras de carreira; varredura do Extrator confirmar a fonte da série retroativa.

---

### Integração Conecta: adesão e limite de consumo das APIs SIAPE

**Direção atual.** As APIs SIAPE (Consultas, Ocorrências) são consumidas via Conecta.gov, que governa o uso por **Plano de Consumo** — cada adesão de órgão tem um `Limite` (inteiro) e uma `periodicidade`, verificáveis no Relatório de Consumo do Gerenciador. A FOTO diária é loop de ~5k chamadas 1-CPF (`ConsultaDadosFuncionais`); o teto que o Conecta impõe a esse volume define se o loop cabe na janela 23h-07h sem bloqueio.

**Por que está aberta.** Fato a apurar, e **entregável de projeto** — a integração com o Conecta ainda NÃO está fechada. O número do limite não existe hoje: é negociado/descoberto quando a adesão for formalizada, não antes. Não é decisão de arquitetura (o desenho do leitor já está fechado no ADR-006); é dependência de terceiros (SERPRO/Conecta) com dono fora da engenharia.

**O que falta.** (a) Formalizar adesão do órgão às APIs SIAPE no Conecta — entregável de projeto, dono PM. (b) Uma vez aderido, ler o limite e a periodicidade reais no Relatório de Consumo. (c) Engenharia: o leitor de API deve ser agnóstico ao número — ritmo configurável + backoff adaptativo (descobre o teto em runtime, recua no 429), de modo que o limite real entre como parâmetro de config, não como reescrita. A janela larga (8h) é o colchão que torna o ritmo lento seguro.
