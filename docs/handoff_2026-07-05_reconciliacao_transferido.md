# Handoff — Reconciliação do corpus + estado TRANSFERIDO (sessão Code 2026-07-05, cont.)

**De:** sessão Code · **Para:** retorno ao Project (claude.ai) / próxima sessão
**Fecha:** a reconciliação que o Project fez lendo o corpus pós-`handoff_2026-07-05_calculadora_completa_pss.md`
— duas lacunas documentais e dois riscos de schema apontados; três das quatro pontas resolvidas
nesta rodada, uma (Lacuna 1) explicada e não exigia ação de código.

---

## 1. Contexto — por que este handoff existe

O Project leu o corpus na ordem âncora→handoffs e apontou 4 achados sobre o estado deixado pelo
handoff anterior. Os dois commits que fecham 3 desses achados (`58f086a`, `470ad60`) **não tinham
handoff próprio** — este documento cobre esse buraco.

## 2. Os 4 achados e o desfecho de cada um

| # | Achado do Project | Desfecho | Onde |
|---|---|---|---|
| Lacuna 1 | `gerador_eventos.py` em disco está em v3 (arquétipo-primeiro), mais adiantado que os handoffs anteriores descreviam | **Explicado, sem ação de código.** Commit `7363d8e` ("Massa v0.3 ARQUETIPO-PRIMEIRO"), posterior ao `handoff_2026-07-05_reconciliacao_e_rotulos.md`, implementou o item A e não deixou handoff próprio. A sessão PSS já rodou em cima do v3 — 561.695/v0.13 é estado corrente, não obsoleto. | — |
| Lacuna 2 | `docs/4_gerador_bichos_v0_1.md` presa em "schema v0.11, 260.465 eventos, Calculadora=1 MV" — 2 versões atrás do código | **Corrigida.** Mini-doc → v0.2: schema v0.13, 4 MVs de exposição, `CONTRIBUICAO_PSS` no pipeline, `load_eventos.sql` com auto-REFRESH, contrato de payload da Calculadora, `pausa_folha` gateia PSS também. Números da Seção 3 corrigidos (eram pré-arquétipo). | `58f086a` |
| Risco 1a | `mv_filme_gestor` filtra `cod_sub_dominio IN (...,'desempenho',...)`, mas `desempenho` não existe em `dom_sub_dominio` (5 gavetas) | **Analisado, sem ação — risco baixo, não é dívida a pagar agora.** FK `dom_tipo_evento.cod_sub_dominio → dom_sub_dominio` impede qualquer evento de desempenho existir antes da gaveta ser semeada; `desempenho` vive no catálogo estendido (dependência externa, não carregada). O filtro é provisionamento pra frente, auto-corrigível quando o estendido entrar. Decisão do Pedro: deixar como está. | — |
| Risco 1b | `dom_motivo_deslig.situacao_resultante` admitia `'TRANSFERE'` (motivos 29/37), valor **órfão** — não existia em `dom_situacao_vinculo` (5 estados). Inerte só porque `config.yaml` nunca emite 29/37; no dia em que emitir, violaria `fk_situacao` | **Corrigido — 6º estado criado.** `TRANSFERIDO` entra em `dom_situacao_vinculo`; `ck_motivo_resultado` e o seed passam a apontar 29/37 para ele. Fraseamento (frase deve indicar origem→destino→data) registrado como pendência na ADR Seção 2, **de propósito adiado** — decisão do Pedro. | `470ad60` |

---

## 3. Arquivos alterados nesta rodada (substituem os homônimos do corpus)

| Arquivo | Versão | O que mudou | Commit |
|---|---|---|---|
| `docs/4_gerador_bichos_v0_1.md` | v0.1 → **v0.2** | Sincronizado com schema v0.13 + Calculadora PSS (ver Lacuna 2 acima). | `58f086a` |
| `sql/3_schema_mdm.sql` | v0.13 → **v0.14** | `dom_situacao_vinculo` ganha `TRANSFERIDO` (6º estado); `ck_motivo_resultado` troca `TRANSFERE`→`TRANSFERIDO`. | `470ad60` |
| `sql/seed_dominios.sql` | (mesma) | Semeia `TRANSFERIDO`; motivos 29/37 corrigidos para apontar pra ele. | `470ad60` |
| `docs/3_catalogo_eventos_v1.yaml` | v1.2 → **v1.3** | `resultado` dos motivos 29/37 passa de texto livre `"transfere vínculo"` para `TRANSFERIDO` (valor de domínio). | `470ad60` |
| `docs/1_adr_mdm.md` | (Seção 2) | Novo item aberto: "Fraseamento do estado TRANSFERIDO" — registra que a frase precisa origem→destino→data e que isso exige campo novo no payload de DESLIGAMENTO 29/37 (`orgao_destino`, hoje ausente). | `470ad60` |

---

## 4. Validação (banco `mdm_rh` vivo + rebuild limpo)

1. `dom_situacao_vinculo` = **6 estados** (era 5). ✔
2. `dom_motivo_deslig` motivos 29/37 → `situacao_resultante='TRANSFERIDO'`, e esse valor **existe**
   na dimensão (join direto, sem `LEFT JOIN` retornando nulo). ✔
3. **Zero órfãos**: nenhuma linha de `dom_motivo_deslig.situacao_resultante` fica de fora de
   `dom_situacao_vinculo` (`count(*) = 0` na consulta anti-join). ✔
4. **Rebuild do zero** (banco descartável): `3_schema_mdm.sql` v0.14 + `seed_dominios.sql` aplicam
   limpos — o `ck_motivo_resultado` novo aceita os valores `TRANSFERIDO` que o seed grava (não
   houve descompasso entre o CHECK e os dados). ✔
5. Nenhum código do gerador/loader/tests tinha `TRANSFERE` hardcoded — confirmado por grep antes da
   mudança; o valor é lido do banco (`dom_motivo_deslig`), então a correção não exigiu tocar
   `gerador_eventos.py`. ✔

---

## 5. Nota — a massa ainda não exercita TRANSFERIDO

`config.yaml` (`deslig_default`) só emite motivos `07` (exoneração a pedido) e `38` (aposentadoria
voluntária). **Nenhum bicho da massa atual passa por redistribuição** (29/37) — o estado existe no
modelo e no banco, mas está com **0 linhas** em `servidor.situacao_funcional`. Se for útil ter um
caso-teste de redistribuição na massa (arquétipo ou ajuste de `deslig_default`), é trabalho pequeno,
não solicitado nesta rodada — fica como sugestão, não pendência.

---

## 6. Pendências que atravessam para a próxima sessão (herdadas, sem mudança)

- Proveniência multi-fonte do afastamento (4.1 vigente × 4.22 PSS × API Ocorrências) — ADR aberta,
  prespec §7.1.
- Dias líquidos: onde a conta mora (cruzar arrays 4.22 × `dom_afastamento.conta_efetivo_exercicio`).
- **Nova (desta rodada):** fraseamento de `TRANSFERIDO` (origem→destino→data) + payload de
  DESLIGAMENTO 29/37 precisando de `orgao_destino` — ver `1_adr_mdm.md` Seção 2, item novo.
- Reconciliação CESSÃO S-2231 × S-2230.40, PROGRESSAO/regras de carreira, taxonomia de
  subdomínios, disciplinar como gaveta própria — todas dependentes de RH/Corregedoria, sem
  mudança nesta rodada.
