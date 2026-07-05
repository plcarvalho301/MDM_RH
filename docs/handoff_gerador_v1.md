# Handoff — Gerador de Eventos v1 + estrutura v0.8 (sessão 2026-07-05)

**De:** Claude (chat) · **Para:** sessão Code / Pedro
**Fecha:** as decisões da sessão do handoff do designer (⚠1–3, motivos locais, PROGRESSAO, retratação ADR-009) executadas em artefato.

---

## 1. Arquivos entregues (substituem os homônimos do corpus — versão dentro do arquivo)

| Arquivo | Versão | O que mudou |
|---|---|---|
| `3_schema_mdm.sql` | v0.8 | `evento` particionada por LIST(`id_carga`), PK (id_carga,id_evento), `fn_particao_carga`, `fn_manifesto_carga`, `ledger_delecao`, `rejeito.id_carga`, `dom_motivo_deslig` criada, procedimento de retratação documentado |
| `seed_dominios.sql` | v0.2 | + §12 `dom_motivo_deslig` (mtvDeslig eSocial + `DEMI_OFICIO`/`CASS_APOSENT`/`ANUL_PROVIMENTO` locais, `e_esocial=false`); §8 atualizada |
| `3_catalogo_eventos_v1.yaml` | v1.1 | `tipo_movimento` desdobra dispensa a pedido × de ofício; ⚠3 fechado nos payloads (data_fim + 2º registro + coalescência); motivos locais; decisões em aberto atualizadas (PROGRESSAO esclarecida; ⚠1–3 marcadas FECHADAS) |
| `1_adr_mdm.md` | +ADR-008/009 | ADR-008 (intercorrência = intervalo; fechamento por 2º registro; coalescência) · ADR-009 (retratação operacional por partição de carga; manifesto pré-assinatura; ledger; governança RH-soberano) |
| `semente_trajetorias_v1.yaml` | v1 | 14 arquétipos do designer NORMALIZADOS ao catálogo v1.1 + DG/Vice hard-coded. **Este é o insumo do gerador**; o xlsx do designer permanece artefato dele (linhas "(fim ...)" e `repetição=0` superadas aqui — MDM soberano) |
| `gerador_eventos.py` | v1 | trajetória-primeiro; FOTO = estado projetado; `--valida` embutido |
| `saida/` | — | rodada de produção: seed 20260705, 1300 vínculos |

## 2. A rodada entregue (`saida/`, seed 20260705)

1300 vínculos · ~1264 pessoas (Bruno-tipo com 2 matrículas) · 16.217 eventos de trajetória · 290.074 FECHAMENTO_FOLHA · 30 eventos-lixo. FOTO projetada: 1090 ATIVO / 133 INATIVO / 54 DESLIGADO / 23 CEDIDO. **`--valida` passou com 0 divergências**: o replay-de-intervalo (ADR-008: data_fim expira estado; coalescência por data_carga; cessão devolve à origem sem evento) reproduz exatamente a FOTO projetada — a premissa que muda o replay está provada dentro do gerador, antes de tocar o banco.

**Três cargas de propósito** (ADR-009 exercitada desde o nascimento):
- `carga_base` — trajetórias (inclui as reversões de DOMÍNIO legítimas: Gerson 38→CASS_APOSENT sobre Inativo; Vicente demissão→ANUL_PROVIMENTO; ambas verificadas no dado).
- `carga_folha` — só FECHAMENTO_FOLHA (o volume; destacável isolado se atrapalhar um teste). Entregue também `.gz`.
- `carga_lixo` — fixture de RETRATAÇÃO OPERACIONAL: 30 eventos bem-formados com erro material deliberado (`data_desligamento=1900-01-01`, fonte `CARGA_APOSENTADOS_DEFEITUOSA`). É o teste "remover evento errado": manifesto → ledger → DETACH → re-ATTACH. **Não confundir com Gerson/Vicente** — aqueles ficam na base para sempre.

**Ordem de carga:** schema v0.8 (banco limpo — massa regenera, nunca migra) → seed v0.2 → `saida/load_eventos.sql` (abre partição por carga via `fn_particao_carga` e faz `\copy`) → REFRESH das MVs. 271 pares aberto+fechamento na base exercitam a coalescência.

## 3. O que MUDA no código da sessão Code (pendência real)

O `classifica()`/replay atual transita estado **por evento**. A ADR-008 exige **intervalo**: (a) AFASTAMENTO/CESSAO não mudam `situacao_funcional` por transição — CEDIDO/afastado-vigente derivam de `data_inicio ≤ hoje ≤ data_fim`; (b) coalescência por chave `(matricula, cod_afastamento|cessão, data_inicio)`, `data_carga` mais recente vence; (c) fim de cessão devolve à origem **sem** evento. A função `replay()` do gerador é a referência da lógica; o smoke test (`smoke_test_evento.py`) valida contra o Postgres real.

## 4. Assunções sinalizadas (minhas, reversíveis)

1. **Truncamento (Camada A)**: carreiras estampadas majoritariamente EM CURSO (u∈[0,25;1,15] do arco) — sem isso a foto saía 57% INATIVO (as sementes são histórias que terminam; a foto de órgão não). Camada B completa o arco sempre.
2. **Dois modos de emissão de intercorrência** (item 2 que tu não respondeu explicitamente): default 25% em par aberto+fechamento; Célio e Bruno forçados. Parametrizável.
3. **Heitor virou Analista e Elias perdeu a FCE 1.05**: massa §5 crava Agente-NUNCA-tem-FCE; o designer não sabia. Cadeias de teste preservadas.
4. **Quadro de 226 chefias NÃO reconciliado** (limite declarado do v1): funções vêm do arquétipo, não da alocação por unidade. Idem lotação órfã (KR 2.1 segue com a massa FOTO). É o primeiro alvo do próximo incremento.
5. **Elias base sem reintegração** — "a de ouro" é bifurcação, pertence ao gerador de DESVIOS (próximo incremento), não à semente.

## 5. Fora daqui (registrado, não executado)

Gerador de desvios (bifurcações §4 do designer); rótulos finais dos motivos locais com RH/Corregedoria; ADR-007 write-up de payload fino; ancoragem da `carga_lixo` num roteiro de teste do procedimento ADR-009 ponta a ponta (manifesto→protocolo→detach→re-attach) — os objetos existem, o roteiro é da sessão Code.
