# MDM-RH — Catálogo de Descritores de Evento (human-readable)

**versão:** v0.1 (rascunho de trabalho)
**âncora:** `3_catalogo_eventos_v1.yaml` | `1_adr_mdm.md` (ADR-007, pendência "Descrição human-readable") | `2_prespec_lentes_v0_1.md`
**data:** 2026-07-04

---

## O que este documento é

O catálogo da **frase textual** que descreve cada evento no Filme (e, futuramente, nas demais lentes). Hoje o `payload` aparece como JSON cru no painel — ilegível para o analista. Este catálogo define, tipo a tipo, a frase que o substitui.

É o artefato de **revisão em um passe pelo RH**: uma tabela, todas as frases, as perguntas secas ao final. Não exige reunião por evento.

## O que este documento NÃO é

- **Não é ADR.** A decisão de onde o parse mora (view SQL, não Power BI) está registrada como pendência na ADR-007; este catálogo a consome, não a fecha.
- **Não fecha sensibilidade.** O recorte fino "o que é sensível campo a campo" é decisão em aberto (RH/diretora — inclui a questão CID). Este catálogo **propõe o mecanismo** e **lista os candidatos**; não decide.
- **Não é DDL.** O payload exato de cada MV ainda é ADR aberta. O Apêndice A é esqueleto ilustrativo do formato de implementação, não schema.

---

## Regras de estilo (fechadas na mesa técnica — território Tech Lead)

1. **Estilo nominal, não verbal.** "Remoção: SGP → COGEP", nunca "Foi removido(a) da...". Elimina conjugação, tempo e gênero; escaneia melhor em timeline.
2. **Valor nunca entra na frase.** A frase diz *que* o fato ocorreu, não *quanto*. Campo sensível/financeiro fica só no payload cru, sob GRANT largo (RH/auditoria).
3. **Proveniência fora da frase.** `fonte` e `grau_confianca` são metadados do envelope — o painel os mostra em coluna/ícone próprio, não misturados à descrição do fato.
4. **A frase descreve o fato do vínculo, não julga.** Sem adjetivo, sem inferência ("afastamento prolongado", "movimentação atípica" — nunca).

---

## A escada de fallback (garantia: JSON cru nunca aparece)

| Nível | Fonte da frase | Quando aplica |
|---|---|---|
| 3 — curada | `dom_*.nome_exibicao` (coluna nova, RH preenche/abençoa) | onde o vocabulário oficial soa duro |
| 2 — template | frase por tipo (tabela abaixo), preenchida de payload + `dom_*.nome` | os 9 tipos do catálogo |
| 1 — genérica | `dom_tipo_evento.nome` + `data_evento` | tipo novo sem template; payload de extração ainda desconhecido |

Mecânica: `COALESCE` em cascata na view. Ajuste de palavra no nível 3 é `UPDATE` em tabela de domínio — nem recria a view.

---

## Catálogo — frase por tipo

Legenda da coluna **Fonte da palavra**: de onde a frase tira o texto — quanto mais à esquerda da escada, menor o custo de manutenção.
Legenda de **Sensibilidade (Gestor)**: `—` = frase idêntica nas duas lentes do Filme; `⚠ candidato` = proposta de variante reduzida na lente Gestor, **pendente decisão RH**.

| Tipo | Frase (template) | Exemplo renderizado | Fonte da palavra | Sensibilidade (Gestor) | Pendência |
|---|---|---|---|---|---|
| PROVIMENTO | `Ingresso — {cargo_inicial}` · sem cargo: `Ingresso no órgão` | Ingresso — EPPGG | `dom_cargo.nome` | — | — |
| ALTERACAO_FUNCAO | `{Designação\|Dispensa de função\|Exoneração de função} — {nome_funcao}` | Designação — FCE 1.13 Coordenador | enum `tipo_movimento` (de-para fixo, 3 valores) + `nome_funcao` do payload | — | — |
| REMOCAO | `Remoção: {origem} → {destino}` · origem nula: `Remoção → {destino}` · unidade que não resolve: `unidade {cod}` | Remoção: SGP → COGEP | `dom_unidade_eorg.nome_unidade` | — | fallback de órfão expõe o KR 2.1 na UX (de graça) |
| PROGRESSAO | `{Progressão\|Promoção}: {classe_o}/{padrao_o} → {classe_d}/{padrao_d}` | Progressão: B/III → B/IV | payload | — | **atrás do gate** `ativo=false` — a palavra (progressão × promoção) sai junto das regras de carreira (RH) |
| AFASTAMENTO | `{motivo} — {data_inicio} a {data_fim \| "em curso"}` | Licença Maternidade — 01/2024 a 07/2024 | `dom_afastamento.nome` (a tabela **é** o catálogo de motivos) | **⚠ candidato** — ver §Sensibilidade | — |
| CESSAO | `Cessão — {orgao_cessionario}` (+ `em curso` se aberta) | Cessão — Ministério da Gestão | payload | — | duplicata S-2231 × S-2230 cód.40 fica **visível** no Filme até a reconciliação fechar — ver §Cessão |
| RETORNO_VINCULO | `{Reintegração\|Reversão\|Recondução}` | Reversão | enum `tpReint` (de-para fixo, 3 valores) | — | RH decide se quer aposto explicativo (ex.: "Reversão — retorno de inatividade") |
| DESLIGAMENTO | `{motivo}` | Aposentadoria voluntária · Exoneração a pedido · Falecimento | `dom_motivo_deslig.nome` (a tabela **é** a frase) | — | confirmar com RH a palavra para óbito ("Falecimento") |
| FECHAMENTO_FOLHA | `Folha {mes_competencia} ({normal\|suplementar})` | Folha 06/2019 (suplementar) | payload | — (valor **nunca** entra — regra de estilo 2) | — |
| *(fallback nível 1)* | `{dom_tipo_evento.nome} — {data_evento}` | Afastamento / licença — 15/03/2011 | `dom_tipo_evento.nome` | herda a regra do tipo | cobre tipo novo e payload de extração pré-arqueologia |

**Formato de data na frase:** competência = `MM/AAAA`; fato pontual = `DD/MM/AAAA`; intervalo = `MM/AAAA a MM/AAAA` (dia raramente agrega em timeline longa). Proposta técnica — ajustável sem custo (view).

---

## §Sensibilidade — variante da lente Gestor (PROPOSTA, não decisão)

O mesmo evento pode precisar de duas frases: **cheia** no Filme-Servidor (o próprio), **reduzida** no Filme-Gestor (o subordinado). Único tipo candidato hoje: **AFASTAMENTO** — o *motivo* pode expor condição de saúde ou situação protegida do subordinado.

**Mecanismo proposto:** coluna booleana `exibe_motivo_gestor` em `dom_afastamento`. Motivo flagado → a lente Gestor renderiza só `Afastamento — {período}`, sem motivo. A lente Servidor sempre renderiza cheio.

**Candidatos a flag (inferência da mesa técnica — o RH/diretora decide, linha a linha):**

| cod | motivo | por quê candidato |
|---|---|---|
| 01, 03 | Acidente/Doença (do trabalho e não relacionada) | condição de saúde |
| 06 | Aposentadoria por Invalidez | condição de saúde |
| 07 | Acompanhamento Familiar | saúde de terceiro |
| 11 | Cárcere | situação protegida |
| 25 | Mulher vítima de violência | situação protegida — candidato mais forte da lista |

Os demais motivos (férias, capacitação, cessão cód.40, mandatos, maternidade¹) seguem por nome nas duas lentes.

¹ Maternidade é caso de borda: é saúde, mas é também o afastamento mais operacionalmente relevante pro gestor planejar a unidade. Vai como pergunta, não como proposta.

**Relação com a pendência CID:** este mecanismo opera no *motivo* (S-2230), que já está no payload. CID/diagnóstico é campo distinto, ainda **fora do escopo** até a diretora decidir — nada aqui o expõe.

---

## §Cessão — a duplicata vira visível

Enquanto a reconciliação S-2231 × S-2230 cód.40 não fechar (pendência já registrada no catálogo de eventos), o mesmo fato pode entrar duas vezes no store — e com descritor, o analista **vê** as duas linhas ("Cessão — órgão X" e "Exercício em outro órgão (Cedido) — período").

Duas posturas possíveis, a decidir junto com a reconciliação:
- **(a)** a projeção deduplica antes da frase → Filme limpo, reconciliação invisível;
- **(b)** a duplicata aparece de propósito → sinal de qualidade na UX, coerente com "quarentena é métrica, não falha" (motor de adoção).

O catálogo não decide; registra que o descritor **antecipa a cobrança** dessa pendência.

---

## O que o RH precisa decidir (as perguntas secas — um passe)

1. **Valida as frases da tabela?** Ajuste de palavra entra na coluna `nome_exibicao` (nível 3 da escada) — vocês editam a palavra, o mecanismo não muda.
2. **Quais motivos de afastamento aparecem por nome no Filme-Gestor?** Revisar a lista de candidatos do §Sensibilidade, linha a linha (inclui a borda maternidade).
3. **"Falecimento" é a palavra para óbito no Filme?**
4. **RETORNO_VINCULO com ou sem aposto explicativo?** ("Reversão" seco × "Reversão — retorno de inatividade")
5. *(já na fila por outro motivo)* Progressão × promoção — sai junto das regras de carreira.

---

## Pendências que este catálogo esbarra (todas JÁ registradas — nenhuma nova)

| Pendência | Onde está registrada | O que trava aqui |
|---|---|---|
| Payload campo-a-campo das MVs | ADR-007, Pendências | DDL final da coluna `descricao_evento` |
| Sensibilidade campo a campo / CID | ADR-007 Pendências + decisão diretora | fechamento do §Sensibilidade |
| Reconciliação CESSAO | `3_catalogo_eventos_v1.yaml`, Parte 7 | postura (a)×(b) do §Cessão |
| Regras de carreira (gate PROGRESSAO) | catálogo, `ativo=false` | frase de PROGRESSAO |
| Arqueologia Extrator (agosto) | `3_arqueologia_extrator_v0_1.yaml` | frase enriquecida p/ eventos de extração (até lá: fallback nível 1) |

---

## Apêndice A — Esqueleto de implementação (ilustrativo, não DDL)

Formato acordado: **CASE inline na camada de view**, um `WHEN` por tipo, bloco comentado — sem função PL/pgSQL por ora (menos peças; revisita se o catálogo estendido multiplicar os tipos). A frase mora na view, nunca gravada no evento: apresentação itera, e store append-only não recebe UPDATE — `CREATE OR REPLACE VIEW` re-frase o passado inteiro de graça.

```sql
-- ── descricao_evento ─────────────────────────────────────────────────────────
-- Escada de fallback (2_descritores_eventos): template por tipo > generica.
-- Nivel 3 (nome_exibicao) entra via COALESCE nos JOINs de dominio.
-- REGRAS: nominal, sem valor, sem proveniencia (regras de estilo 1-4).
CASE e.cod_tipo_evento

    -- AFASTAMENTO: dom_afastamento.nome E a frase (vocabulario oficial S-2230).
    -- Lente Gestor: variante reduzida por flag exibe_motivo_gestor (§Sensibilidade).
    WHEN 'AFASTAMENTO' THEN
        COALESCE(da.nome_exibicao, da.nome_afastamento)
        || ' — ' || to_char((e.payload->>'data_inicio')::date, 'MM/YYYY')
        || ' a ' || COALESCE(to_char((e.payload->>'data_fim')::date, 'MM/YYYY'), 'em curso')

    -- DESLIGAMENTO: dom_motivo_deslig.nome E a frase.
    WHEN 'DESLIGAMENTO' THEN
        COALESCE(dm.nome_exibicao, dm.nome)

    -- REMOCAO: fallback de orfao ("unidade {cod}") expoe o KR 2.1 na UX.
    WHEN 'REMOCAO' THEN
        'Remoção: '
        || COALESCE(uo.nome_unidade, 'unidade ' || (e.payload->>'cod_unidade_origem'), '?')
        || ' → '
        || COALESCE(ud.nome_unidade, 'unidade ' || (e.payload->>'cod_unidade_destino'))

    -- ... (demais tipos: 1 WHEN por linha da tabela do catalogo) ...

    -- FALLBACK (nivel 1): tipo novo ou payload pre-arqueologia. JSON cru NUNCA.
    ELSE
        te.nome || ' — ' || to_char(e.data_evento, 'DD/MM/YYYY')
END AS descricao_evento
```

---

*Fim do v0.1. Próximo passo: revisão RH (perguntas secas acima) → ajustes viram v0.2 → coluna `nome_exibicao` + flag `exibe_motivo_gestor` entram no schema quando as respostas chegarem.*
