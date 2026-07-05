# Handoff — PoC MDM-RH, pós-teste em Code (2026-07-04)

Volta pro Project do claude.ai depois de uma sessão completa em Claude Code: ambiente
local, cadeia FOTO, cadeia EVENTO, e primeiro dashboard funcionando no Power BI Desktop.

## a) O teste como um todo, e por que foi sucesso

**Objetivo original:** provar a arquitetura ponta a ponta — massa fictícia → carga →
banco → view → dashboard — sem tocar API real nem gerar eventos de verdade (eram
deferidos de propósito). Meta: validar arquitetura, não entregar valor de negócio.

**O que rodou, na ordem:**

1. **Ambiente.** Postgres 18.4 local, banco `mdm_rh` criado, schema (`3_schema_mdm.sql`)
   aplicado limpo na primeira tentativa real contra o banco, 11 domínios semeados.
2. **Eixo FOTO.** `gen_massa.py` gerou 1200 vínculos fictícios (1166 CPFs distintos,
   8,2% órfãos estruturais de propósito). Carga via `carrega_foto.py`: 1200/1200 depois
   de um fix (ver seção b). Views KR (`vw_orfao_estrutural`, `vw_afastado_conta_exercicio`,
   `vw_delta_incompletude`) e `vw_foto`/`vw_lente` todas responderam com números batendo
   1:1 entre banco e Power BI.
3. **Eixo EVENTO** (destravado nesta sessão, não estava no escopo original). Provado em
   3 camadas crescentes de exigência:
   - `smoke_test_evento.py`: regra nova "matrícula precisa existir em `servidor` antes
     de gerar evento" — 9 casos, todos rejeitados corretamente (comportamento esperado
     e confirmado por você).
   - `smoke_test_misto.py`: lote com FOTO e EVENTO misturados, exercitando um
     `classifica()` de verdade (decide por linha, não mais um leitor de tipo único) —
     3 cenários pedidos por você, os 3 bateram: (a) foto+evento no mesmo lote carregou
     certo, (b) evento pra servidor inexistente rejeitou, (c) evento com JSON quebrado
     rejeitou pelo motivo certo (Postgres recusando o cast).
   - `gera_filme_servidor.py`: 30 eventos por matrícula, datas 2005-2024, **inseridos em
     ordem embaralhada de propósito** — provou que o replay ordena por `data_evento`,
     não por ordem de carga.
4. **Dashboard.** Power BI Desktop conectado via ODBC (driver psqlODBC + DSN `mdm_rh`
   criada nesta sessão). Painel "Lente Estratégica" (`vw_lente`) e painel "Filme do
   Servidor" (`vw_mv_filme_servidor`) montados e funcionando, com relacionamento correto
   entre as tabelas, formatação de data resolvida.

**Estado atual do banco (2026-07-04):** `servidor` 1201 linhas, `vw_orfao_estrutural` 99
(~8,2%), `evento` 31 linhas (todas da matrícula de teste `5000001`), `rejeito` 11 linhas
(motivos de teste, não sujeira real), `vw_lente` 69 unidades agregadas.

**Por que isso conta como sucesso:** a cadeia inteira — gerador → loader → schema →
views de exposição → conector ODBC → visual — funcionou sem nenhum ajuste de arquitetura.
Os únicos ajustes foram bugs pontuais de implementação (seção b), não redesenho. O eixo
evento, que não estava no escopo original, também se provou sozinho: a regra de negócio
nova (matrícula-órfã) e o encanamento misto (classifica por linha) funcionaram no primeiro
desenho, só precisando da correção de visibilidade das MVs no ODBC.

## b) Mudanças pequenas feitas ao longo do teste

Nenhuma foi redesenho de arquitetura — todas são fixes de implementação ou passos de
setup que o handoff original não previa:

1. **Reorganização de diretório.** Os arquivos chegaram soltos na raiz de `D:\MDM`;
   movidos pra `sql/`, `gerador/`, `loader/`, `beta/` (a estrutura que o handoff original
   já assumia).
2. **Bug no loader (`loader/carrega_foto.py`).** `DATE_COLS` estava declarado mas nunca
   usado em `prepara_linha`. O gerador emite `data_ingresso_nova_funcao` no formato
   `DDMMYYYY` (imitando o formato real da API SIAPE) e isso quebrava o INSERT
   (`DatetimeFieldOverflow`) na 1 em 1200 linhas que tinha esse campo preenchido. Fix:
   função `_data_iso()` que normaliza `DDMMYYYY` → ISO antes do INSERT.
3. **Ambiente Power BI.** Criada uma DSN de usuário `mdm_rh` no ODBC do Windows (driver
   psqlODBC, sem credencial gravada no registro — Power BI pede login na hora de
   conectar). Não existia antes desta sessão.
4. **Vitrine ODBC das MVs.** O driver psqlODBC não enumera `relkind='m'`
   (materialized view) no Navegador do Power BI — as 3 MVs de evento
   (`mv_filme_servidor`, `mv_filme_gestor`, `mv_calculadora`) ficavam invisíveis pro
   conector, mesmo existindo no banco. Fix: 3 views finas de passagem
   (`vw_mv_filme_servidor`, `vw_mv_filme_gestor`, `vw_mv_calculadora`) adicionadas ao
   schema — compatibilidade de catálogo, não mudança de fronteira de acesso (ADR-007
   continua valendo: quem materializa continua sendo a MV).
5. **Scripts novos de smoke test** (`smoke_test_evento.py`, `payloads_afastamento_smoke.py`,
   `smoke_test_misto.py`, `gera_filme_servidor.py`) — descartáveis, não fazem parte do
   pipeline de produção, só provam encanamento.

**Commits no repo** (branch `master`, sem push a remoto ainda):
- `d34516b` — PoC eixo FOTO completa (schema, seed, gerador, loader + fix).
- `198e895` — specs de corpus (triagem de tickets, pré-spec das 4 lentes).
- `f8d4300` — eixo evento (smoke tests, encanamento misto, vitrine ODBC das MVs).

## c) Apontamento pra refinar no Project: descrição human-readable do evento

Ao montar o "Filme do Servidor" no Power BI, a coluna `payload` aparece como JSON cru
(ex. `{"cod_afastamento": "15", "data_inicio": "2026-06-01", "data_fim": null}`). Pra
próxima fase, você levantou a necessidade de uma **descrição textual human-readable e
não-sensível** por evento — algo como "Assumiu cargo em [unidade]" ou "Licença-capacitação"
em vez do JSON cru.

**Recomendação levantada na sessão** (ainda não implementada, fica pra discutir/refinar
no Project): o parse deveria morar na **camada de view SQL**, não em DAX/Power Query
dentro do Power BI — segue o mesmo princípio já fechado no schema (ADR-007: "corte de
payload no DDL, não no Power BI"). Desenho provável: um `CASE` por `cod_tipo_evento`,
com `JOIN` em `dom_afastamento`/`dom_cargo`/etc. pra traduzir código em nome, montando
uma frase; campos sensíveis (ex. `valor_liquido` de `FECHAMENTO_FOLHA`) ficam de fora da
frase e continuam só no `payload` cru para quem tiver GRANT mais largo.

**Trade-off a discutir:** travar o formato da frase no schema é bom pra consistência
entre as 4 lentes (Foto/Filme/Lente/Calculadora todas vão precisar de leitura humana em
algum momento), mas é mais lento de iterar do que texto montado no Power BI — cada ajuste
de frase vira um `CREATE OR REPLACE VIEW`, não uma edição de medida.

**Pendências que essa decisão vai esbarrar** (já mapeadas nos docs de corpus lidos nesta
sessão, `2_prespec_lentes_v0_1.md`): payload exato de cada MV ainda é ADR aberta;
recorte fino de "o que é sensível" ainda não foi decidido campo a campo.
