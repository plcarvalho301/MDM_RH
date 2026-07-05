# Handoff — pós-validação do eixo EVENTO (sessão Code 2026-07-05)

**De:** sessão Code · **Para:** retorno ao Project (claude.ai) / próxima sessão
**Fecha:** as duas pendências do `handoff_gerador_v1.md` §3 e §5 — replay por intervalo (ADR-008) validado contra o Postgres real, e roteiro de retratação (ADR-009) exercitado ponta a ponta.

---

## 1. O que rodou (banco `mdm_rh`, PG 18.4, banco limpo)

Ordem do handoff §2, executada sem desvio: `DROP SCHEMA public CASCADE` → schema v0.8 → seed v0.2 (9 tipos de evento, 17 afastamentos, 11 motivos de desligamento) → `load_eventos.sql` (3 partições via `fn_particao_carga` + `\copy`: 16.217 + 290.074 + 30 = 306.321 eventos) → REFRESH das 3 MVs (`mv_filme_servidor` 306.321 · `mv_calculadora` 290.074 · `mv_filme_gestor` 15.578 = subdomínio vínculos menos os 669 AFASTAMENTOs).

## 2. ADR-008 fechada — `valida_replay_intervalo.py` (novo, raiz)

Porta fiel do `replay()` do gerador lendo da tabela `evento` real: coalescência por `(cod_tipo_evento, data_inicio)` com `data_carga` mais recente vencendo; CEDIDO derivado por intervalo só sobre ATIVO; fim de cessão devolve sem evento; mapa motivo→situação lido de `dom_motivo_deslig` (é DADO, não código). Substitui a leitura por-evento dos smoke tests de 2026-07-04 (deletados).

- **Núcleo (contrato da referência): `situacao_funcional` — 0 divergências em 1300 vínculos.**
- **Estendido (além da referência): `cod_afastamento_vigente`, `funcao_comissionada`, `classe`/`padrao` — 0 divergências.** Lotação fica fora (não reconstruível: PROVIMENTO não carrega unidade; `muda_unidade` troca sem evento).
- Teste de mutação: com `--data-ref 2016-06-30` o validador acusa 60+85 divergências (Célio cedido, afastamentos vigentes trocados) e sai com exit 1 — ele morde.
- `--incluir-lixo`: **o lixo passa limpo pelo replay** (30 duplicatas bem-formadas; a amostra da seed 20260705 não pegou nenhum DESLIGAMENTO, então a mutação `1900-01-01` nem se aplicou) — confirmação empírica da tese ADR-009: a superfície de detecção é o manifesto/painel, nunca a validação.

## 3. ADR-009 exercitada — `roteiro_retratacao_adr009.sql` (novo, raiz)

Sequência documentada no schema, executada de verdade: manifesto (`fn_manifesto_carga`, digest `4825f23755aca2c4a02ae5d4eb659bc9`) → protocolo fictício SEI referenciando o digest → INSERT no `ledger_delecao` (o MESMO jsonb, fora das partições) → DETACH (306.321→306.291, instantâneo) → **digest re-verificado contra a partição fria = `t` (prova de custódia)** → REFRESH CONCURRENTLY sem órfão → **re-ATTACH devolve os 30 (reversibilidade provada)** → re-DETACH final. Estado que ficou: carga_lixo retratada (cold, tabela `evento_c_d5a00117...` destacada), ledger com 1 registro, replay ainda 0 divergências.

## 4. Achados da sessão (para o corpus)

1. **21 segundos-vínculos do Bruno Vespertílio têm PROVIMENTO no futuro** (2027–2030, via `inicia_apos_anos`) e mesmo assim entram ATIVOS na foto de 2026-06-30. A referência não corta fato futuro e a projeção também não — os dois lados combinam, então o `--valida` passa; mas é vínculo que ainda não existe na data da foto. Candidato a clamp no gerador v1.1 (flag `--corte-futuro` do validador expõe os 21).
2. **A descrição da carga_lixo no handoff §2 descreve o mecanismo, não a amostra**: a mutação `data_desligamento=1900-01-01` só se aplica a payloads com essa chave, e a amostra sorteada (30 de 16.217, uniforme) não pegou DESLIGAMENTO — o lixo real são 26 PROGRESSAO + 4 outros, todos duplicatas exatas com fonte trocada.
3. **Duas inconsistências de schema/seed** (não bloqueiam nada hoje): (a) `mv_filme_gestor` filtra `cod_sub_dominio IN ('vinculos','desempenho','jornada')` mas `'desempenho'` não existe em `dom_sub_dominio` — letra morta; (b) `dom_motivo_deslig.situacao_resultante` admite `'TRANSFERE'` (motivos 29/37) que não existe em `dom_situacao_vinculo` — se um dia o replay gravar em `servidor.situacao_funcional`, viola FK. Candidatas ao v0.9.

## 5. Atenção: `servidor` está VAZIA

O rebuild limpo zerou a FOTO. Não recarreguei de propósito: a massa FOTO (gen_massa v0.2 Reino Animal, retrofit ainda não rodado) e a massa EVENTO são universos NÃO reconciliados — matrículas 1000001+ colidiriam significando pessoas diferentes. Recarregar a FOTO (e o painel Power BI que lê `vw_foto`) é decisão à parte; a reconciliação dos eixos segue como primeiro alvo do próximo incremento (handoff anterior §4.4).

## 6. Fora daqui (inalterado)

Gerador de desvios; rótulos finais dos motivos locais com RH/Corregedoria; ADR-007 payload fino campo a campo; reconciliação FOTO×EVENTO.
