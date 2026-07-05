# Handoff — Reconciliação FOTO×EVENTO + Rótulos (sessão 2026-07-05, tarde)

**De:** sessão Code · **Para:** retorno ao Project (claude.ai) / próxima sessão
**Fecha:** a inversão do gerador de eventos (era a pendência nº1 dos handoffs anteriores), rótulos amigáveis em todo o painel, e regras de modelo viram dado.

---

## 1. O que mudou — visão executiva

No início desta sessão, o eixo EVENTO tinha uma "cagada" descoberta em conjunto com o usuário: o `gerador_eventos.py` era **trajetória-primeiro** — inventava a própria população e projetava uma foto, gerando um universo **paralelo** ao do `gen_massa.py` (a mesma matrícula era pessoas diferentes em cada gerador). Corrigido: o gerador agora é **foto-primeiro**, consome o `servidor.csv` canônico do `gen_massa.py` e faz cada trajetória **aterrissar** no estado fotografado. Além disso, o painel ganhou rótulos amigáveis em toda superfície, e as regras de derivação de estado deixaram de ser hardcode — viram dado no banco.

**Estado final do banco** (`mdm_rh`, schema **v0.11**): 1300 vínculos na FOTO, 260.465 eventos, mesma população nos dois lados. Situação: 1152 ATIVO / 55 DESLIGADO / 52 INATIVO / 29 CEDIDO / 12 DISPONIBILIDADE.

## 2. O schema mudou 3 vezes (v0.9 → v0.10 → v0.11)

| Versão | Autoria | O que fez |
|---|---|---|
| **v0.9** | sessão PBI (claude.ai), já estava no arquivo quando esta sessão começou | Colunas planas nas MVs de Filme (`cod_afastamento`, `data_inicio`, `data_fim`, `cod_motivo_deslig`, `data_desligamento` extraídas do payload via `->>`) + `intervalo_vigente` (coalescência ADR-008 em SQL) + filme-gestor passa a ver intercorrências sem subir JSONB cru. |
| **v0.10** | esta sessão | **Rótulos**: `dom_tipo_evento` ganhou coluna `nome` (era a única dimensão sem rótulo — o Filme mostrava `ALTERACAO_FUNCAO` cru); `vw_foto` ganhou `nome_unidade_lotacao/exercicio`, `nome_afastamento_vigente`, `nome_regime`; `vw_filme_servidor`/`vw_filme_gestor` viraram views **regulares** (o driver ODBC enxerga, ao contrário de MV) com os códigos já resolvidos em nome. |
| **v0.11** | esta sessão | **Regras de modelo viram dado**: `dom_afastamento` ganhou `deriva_situacao` (40→CEDIDO, 31→DISPONIBILIDADE) e `pausa_folha` (05). O gerador e o validador passaram a **ler essas regras do banco** em vez de hardcode Python — regra nova agora é `UPDATE` na dimensão, sem deploy. + fix da `vw_lente` (não tinha `nome_unidade_lotacao`, só foto e filmes tinham). + reversão: `funcao_comissionada` (CCE/FCE) **não** resolve mais para nome — o código já é legível e o nome real é sensível (fica só no modelo live). |

**Nota sobre v0.9:** essa versão já estava no `sql/3_schema_mdm.sql` quando esta sessão começou (o usuário avisou "teve alteração do schema decorrentes dos testes do PBI, confere lá antes de prosseguir"). O banco vivo ainda estava em v0.8; testei o SELECT v0.9 contra os eventos reais antes de aplicar, e ele funcionou de primeira.

## 3. A reconciliação FOTO×EVENTO (o trabalho principal)

`gerador/gerador_eventos.py` reescrito (era v1, agora v2). Muda de "inventa gente + projeta foto" para "recebe foto + gera trajetória que aterrissa nela":

- **Ingresso** = `data_exercicio_no_orgao` da foto (não mais sorteado).
- **Progressão** anda da grade `(A,I)` até `(classe, padrao)` da foto.
- **Função comissionada** aterrissa via `ALTERACAO_FUNCAO` se a foto tem `funcao_comissionada` e situação ATIVO/CEDIDO.
- **Situação** aterrissa por regra (agora dado, ver v0.11): DESLIGADO/INATIVO → `DESLIGAMENTO` (motivo default calibrável em `config.yaml:deslig_default`, pois vários motivos mapeiam pra mesma situação); CEDIDO → `CESSAO` + `AFASTAMENTO` espelho (código 40); DISPONIBILIDADE → `AFASTAMENTO` código 31; ATIVO com afastamento vigente → `AFASTAMENTO` do código correspondente.
- Preserva a mecânica ADR-008/009 herdada do v1: coalescência por par aberto+fechamento, carga_lixo como fixture de retratação.

**Validado:** 0 divergências (núcleo + estendido: situação, afastamento vigente, função, classe, padrão) contra a foto canônica, tanto no `--valida` interno do gerador quanto no `tests/valida_replay_intervalo.py` rodando contra o Postgres real.

**Pipeline mudou de ordem**: domínios agora são semeados **antes** do gerador de eventos (ele lê as regras deles). Sequência completa em `docs/4_gerador_bichos_v0_1.md` §3.

**Limite declarado, não resolvido nesta sessão:** todos os 1300 vínculos recebem trajetória **mecânica**. Os ~14 arquétipos ricos da `semente_trajetorias_v1.yaml` (Gerson com 2 desligamentos, Vicente com anulação de provimento, Bruno com 2 vínculos, Célio cedido+afastado, DG/Vice) **não têm sua trajetória característica** — hoje um desligado qualquer sai com motivo genérico 07 ou 38. Para devolver isso, o `gen_massa.py` precisa **marcar** cada servidor com um arquétipo (campo novo no `servidor.csv`) — a foto snapshot não carrega a forma da trajetória. É o item **A** do roadmap.

## 4. Arquivos do corpus — o que de fato mudou vs. o que só foi commitado

Isso responde diretamente sua pergunta. Tem três categorias bem diferentes:

### 4a. Conteúdo que EU mudei nesta sessão

| Arquivo | O que mudou |
|---|---|
| `sql/3_schema_mdm.sql` | v0.9 (já vinha) → **v0.10 → v0.11** (rótulos + regras como dado), ver §2 |
| `sql/seed_dominios.sql` | `dom_tipo_evento` ganhou coluna+valores de `nome`; `dom_afastamento` ganhou `deriva_situacao`/`pausa_folha` com valores |
| `gerador/gerador_eventos.py` | **reescrito por completo** (v1 trajetória-primeiro → v2 foto-primeiro); depois ajustado para ler regras do banco em vez de hardcode |
| `gerador/config.yaml` | + bloco `deslig_default` (motivo por situação-alvo, calibração) |
| `loader/carrega_foto.py` | 1 linha: `NULLABLE` incluía `data_exercicio_no_orgao` (estava faltando desde schema v0.5; sem isso a carga inteira ia pra rejeito) |
| `tests/valida_replay_intervalo.py` | **novo nesta sessão anterior**, estendido hoje para 5 situações e para ler `deriva_situacao` do banco |
| `sql/roteiro_retratacao_adr009.sql` | **novo** (sessão anterior) |
| `docs/4_gerador_bichos_v0_1.md` | **novo** — a mini-doc do produto que você pediu |
| `docs/handoff_2026-07-05_pos-validacao.md` | **novo** (handoff da sessão anterior, mesma tarde) |
| `.gitignore` | passou a ignorar todos os dados gerados (CSVs de evento, foto, cargas.json — o `eventos_carga_folha.csv` sozinho tem 121MB) |

### 4b. Conteúdo que JÁ EXISTIA em disco (não editei), só entrou no git agora

Estes apareceram como "arquivo novo" no diff só porque nunca tinham sido commitados — você os entregou junto com o handoff no início desta conversa, ficaram como untracked, e eu os movi para `docs/` e commitei pela primeira vez. **Não mudei o conteúdo de nenhum destes:**

- `docs/1_adr_mdm.md` (as ADRs 001-009)
- `docs/2_descritores_eventos_v0_1.md`
- `docs/3_catalogo_eventos_v1.yaml` (catálogo v1.1)
- `docs/3_massa_reino_animal_v0_3.md` (spec do gen_massa)
- `docs/handoff_gerador_v1.md` (o handoff com que você abriu esta conversa)
- `gerador/semente_trajetorias_v1.yaml` (os 14 arquétipos — ainda não usado no fluxo, é insumo do item A)
- `gerador/gen_massa.py` e `gerador/config.yaml` (a versão v0.2 Reino Animal já existia modificada em disco quando comecei; só toquei o `config.yaml` para adicionar `deslig_default`, ver 4a)

### 4c. Deletado (obsoleto, substituído pelo fluxo atual)

`smoke_test_evento.py`, `smoke_test_misto.py`, `payloads_afastamento_smoke.py`, `gera_filme_servidor.py`, `HANDOFF_2026-07-04_pos-teste.md` — já estavam deletados na working tree quando comecei (transição por-evento → por-intervalo da sessão anterior); só formalizei a deleção no commit.

## 5. Pendências para a próxima sessão (roadmap vivo em `docs/4_gerador_bichos_v0_1.md` §8)

- **A — Casos-teste ricos**: devolver a trajetória característica aos 14 arquétipos nominais. Depende de marcar arquétipo no `gen_massa.py`.
- **E — Frase amigável (descritor/assembler)**: por decisão do usuário nesta sessão, **fica para o futuro** — os rótulos (código→nome) já são suficientes para testar agora. Fundação pronta (colunas planas + nomes em toda dimensão); falta só compor a narrativa.
- **C — destino=banco direto** no gerador (baixo esforço, a qualquer momento).
- **D — Emissores de ingestão real** (SIAPE/eSocial) + injeção de defeito: reservado para depois dos dashboards, por pedido explícito do usuário.

## 6. Comandos de referência

Pipeline completo, `valida_replay_intervalo.py`, e o mapa de arquivos: ver `docs/4_gerador_bichos_v0_1.md`.

Commits desta sessão (mais recente primeiro): `677e3e1` `57dd5a8` `cdf8c7d` `e9d93fa` `e813cd2` `2ebc476` `f3aebb9` `609c3ee`.
