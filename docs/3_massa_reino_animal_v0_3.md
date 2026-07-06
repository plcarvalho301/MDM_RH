# Massa Reino Animal — requisitos de negócio do gerador (retrofit FOTO) — v0.3

**Escopo:** retrofit da massa FOTO (loader → servidor → views KR → painéis). Cadeia EVENTO fica para o subprojeto seguinte. Os mesmos referenciais alimentarão as duas cadeias.

**Relação com a taxonomia da Plataforma:** importa-se apenas o pacote de conteúdo Reino Animal (nomes, unidades, órgãos). A taxonomia (ref/canon/merge) NÃO entra no MDM. Em conflito, o modelo MDM é soberano.

**Calibração:** escada de níveis, proporção entre unidades e volumetria vêm do decreto de estrutura regimental do órgão (D11816/2023, redação D12503/2025 — quadro vigente), com quantidades perturbadas por jitter de seed. Nomes reais de órgão/unidades/carreiras NÃO aparecem na massa nem neste documento — só análogos Reino Animal.

---

## 1. Nomes de servidores

**Regra:** `[nome humano] + [sobrenome de kind animal]` — ex.: "Marina Lobato-Cerva". Sintetizados por regra, sem lista fechada.

**Exceções fixas (hard-coded):** Diretor-Geral = **Aurélio Leão** (CCE 1.18); Vice Diretor-Geral = **João Equino** (CCE 1.18). A chefe 1.15 da Câmara de Cria gera nome feminino ("a diretora" — sabor, custo zero).

## 2. Estrutura organizacional (dom_unidade_eorg)

**43 unidades**, `cod_unidade` na faixa **100001–100043**:

| Grupo | Unidades | Lotação? |
|---|---|---|
| Fim — sede (6) | Vigília do Continente · Proteção do Reino · Batedores Além-Oceano · Guilda dos Ratos · Oficina de Casulos · Colmeia-Escola | sim |
| Fim — regionais (26) | Tocas-Satélite individualizadas (Seção 3) | sim |
| Meio (3) | Câmara de Cria · Buscadores de Mantimentos · Guarda das Estações | sim |
| Meio pequena (5) | Câmara da Rainha · Conselho das Regras Antigas · Sentinelas de Dentro · Aferidores de Prumo · **Bando de Arribação** | sim |
| Estrutura sem população (3) | Concílio dos Rastros · Conselho das Famílias · Pacto das Colônias Vizinhas | não |

**Bando de Arribação** (novo na v0.3): análogo da assessoria de relações internacionais do quadro real — aves de arribação cruzam fronteiras. Nome editável; a unidade não. Fecha o buraco A1 da v0.2: o Pacto segue "fora do órgão" (interface com externos), a assessoria interna é outra unidade. Com ela o total de chefias volta a bater exato com o quadro (226).

**Comitês cross:** linha de estrutura, população zero na FOTO. Nomeação para colegiado = backlog (candidato a tipo de evento, gaveta a definir).

**Órfão estrutural (KR 2.1):** `n_tocas_orfas` (default 4, sorteadas por seed) ficam FORA do `dom_unidade_eorg`, superintendente 1.13 incluso.

## 3. As 26 Tocas-Satélite

Porte segue o quadro: **2 Nível 1 · 9 Nível 2 · 15 Nível 3**.

- **Nível 1 (2):** Gruta do Sudeste · Manguezal da Baía
- **Nível 2 (9):** Toca do Oeste · Lagoa do Sul · Ninho do Norte · Pântano Central · Chapada do Planalto · Restinga do Litoral · Várzea do Grande Rio · Capão dos Pampas · Igarapé do Noroeste
- **Nível 3 (15):** Brejo do Sertão · Duna do Nordeste · Penhasco da Serra · Clareira da Mata · Charco do Sudoeste · Açude das Secas · Formigueiro do Cerrado · Cupinzeiro do Campo · Alagado do Delta · Campina do Leste · Corredeira das Pedras · Banhado do Extremo-Sul · Recife das Marés · Colina do Vale · Mangue do Estuário

Lista editável; a estrutura porte×quantidade (2/9/15) não.

## 4. Funções comissionadas — escada real, trilha 1

Níveis: **1.05, 1.07, 1.10, 1.13, 1.15** (FCE, com pontos CCE onde o quadro tem), **CCE 1.17** (1), **CCE 1.18** (2). Trilhas 2 e 3 fora do retrofit. Código gravado como texto (`"FCE 1.10"`, `"CCE 1.18"`) em `funcao_comissionada`; semear os códigos usados em `dom_funcao`.

**Alocação-base por unidade (quadro vigente, trilha 1, PRÉ-jitter):**

| Unidade Reino Animal | 1.18 | 1.17 | 1.15 | 1.13 | 1.10 | 1.07 | 1.05 | Σ |
|---|---|---|---|---|---|---|---|---|
| Topo (DG + Vice) | 2 CCE | — | — | — | — | — | — | 2 |
| Câmara da Rainha | — | — | 1 | 2 | 5¹ | 4¹ | — | 12 |
| Bando de Arribação | — | — | — | 1 | — | — | — | 1 |
| Conselho das Regras Antigas | — | — | — | 1 | 1 | 1 | — | 3 |
| Aferidores de Prumo | — | — | — | 1 | — | — | — | 1 |
| Sentinelas de Dentro | — | — | — | 1 | 2 | 1 | — | 4 |
| Guarda das Estações | — | 1 CCE | — | 1 | 2 | — | — | 4 |
| Oficina de Casulos | — | — | 1 | 3 | 8 | 7 | — | 19 |
| Buscadores de Mantimentos | — | — | 1 CCE | 2 | 6¹ | 9¹ | 2 | 20 |
| Câmara de Cria | — | — | 1 | 2 | 5 | 3 | — | 11 |
| Colmeia-Escola | — | — | 1 | 2 | 7¹ | 4 | — | 14 |
| Vigília do Continente | — | — | 1 | 3 | 7 | 2 | — | 13 |
| Proteção do Reino | — | — | 1 | 3 | 8 | 4 | — | 16 |
| Batedores Além-Oceano | — | — | 1 | 2 | 5 | 4 | — | 12 |
| Guilda dos Ratos | — | — | 1 | 3 | 5 | 3 | — | 12 |
| Tocas Nível 1 (2×) | — | — | — | 1 cada | 2 cada | — | 1 cada | 8 |
| Tocas Nível 2 (grupo de 9) | — | — | — | 1 cada | 11 no grupo² | — | 1 cada¹ | 29 |
| Tocas Nível 3 (15×) | — | — | — | 1 cada | — | 1 cada | 1 cada¹ | 45 |
| **Total** | **2** | **1** | **9** | **53** | **75** | **56** | **28** | **226** |

¹ mistura CCE+FCE no quadro original — o gerador preserva a partição.
² 11 coordenações para 9 tocas: duas recebem 2, sete recebem 1, sorteio por seed.

**Chefias:** departamentos-fim de sede, Oficina, Colmeia, Câmara de Cria, Buscadores e Câmara da Rainha têm chefe 1.15; demais meio-pequenas e superintendentes de Toca têm chefe 1.13; Guarda das Estações é CCE 1.17 (única).

**Regra do piso — reinstalada como SOFT FLOOR (v0.3):** alvo "toda área ≥2 × 1.10, cada 1.10 com ≥1 × 1.07", aplicado *até onde a alocação permite*. Mecânica: o jitter não pode rebaixar abaixo do soft floor uma unidade cuja alocação-base o atende; unidades cuja base já não o atende (Aferidores, Bando de Arribação, Guarda das Estações, Tocas N3) seguem a base sem forçar. O piso limita o jitter para baixo; nunca infla acima do quadro.

**Jitter:** fator global por seed ∈ [0,85; 1,15], arredondamento por maior resto preservando razões entre unidades. Posições unitárias (1.18×2, 1.17×1, chefes ×1) invariantes; soft floor respeitado.

## 5. Cargos efetivos

Texto solto (sem FK; `dom_cargo` não recebe valor fictício):

| Cargo | % | Restrição de lotação | FCE? |
|---|---|---|---|
| Analista | ~85% (residual) | nenhuma | sim |
| Técnico | 10% | meio + meio-pequenas + Oficina de Casulos | sim (param) |
| Agente | 5% | qualquer unidade | **NUNCA** |

## 6. População e lotação

- Total default **1300 vínculos** (param, pode subir). Todo servidor tem lotação.
- Split sede/regionais default 75/25 (param — A3).
- Dentro do grupo, população proporcional ao peso de FCE da unidade, com piso que acomode as próprias chefias.
- Acumulação lícita: 3% dos CPFs com 2 matrículas (param — A4).
- Matrícula 7 dígitos (schema v0.7, `ck_matricula`).

## 7. Regra de gestor e populações de acesso (FECHADO — v0.3)

**Gestor (`mv_filme_gestor`): detentor de função ≥ 1.13** — CCE 1.18, CCE 1.17, 1.15, 1.13. Coordenadores 1.10 NÃO são gestores para fins de painel. A5 encerrada.

**Populações de acesso por painel (base do GRANT na MV — a autorização real; RLS é cosmético):**

| Painel | População (GRANT) | Tamanho na massa |
|---|---|---|
| Lente do RH | lotados na **Câmara de Cria** | ~unidade inteira (default: todos; ver A6) |
| Calculadora / financeiro | divisão financeira da Câmara de Cria (**1 × 1.10 + 1 × 1.13 + a diretora 1.15**) + gestores **1.13+ dos Buscadores de Mantimentos** (2 × 1.13 + chefe CCE 1.15) | **6 pessoas nomeadas** |
| Filme do Gestor | todos os gestores 1.13+ | 65 (53×1.13 + 9×1.15 + 1.17 + 2×1.18) |
| Filme do Servidor | o próprio (recorte matrícula) | todos |

A população da Calculadora — 6 nomes — é exatamente o perfil "população pequena e nomeada" que o modelo de risco tolerado do GRANT-na-MV pressupõe. O gerador marca essas pessoas (flag ou lista derivável) para o PoC de GRANT.

O financeiro como **divisão interna da Câmara de Cria** consome 1 das 5 coordenações 1.10 e 1 das 2 CGs 1.13 da alocação — não adiciona posição, nomeia posição existente.

## 8. Órgãos externos (cessão futura)

Sisbin animalizado, lista editável: Polícia Ursa da Federação Animal · Polícia Rodoviária das Capivaras · Agência Central da Alcateia · Esquadra dos Golfinhos · Exército das Formigas · Aeronáutica dos Falcões · Conselho de Controle das Corujas Financeiras · Receita Federal das Abelhas · Banco Central dos Castores · Chancelaria dos Albatrozes · Gabinete de Segurança do Ninho.

## 9. Parâmetros (consolidado)

| Parâmetro | Default |
|---|---|
| `total_vinculos` | 1300 |
| `split_sede_regionais` | 75/25 |
| `jitter_range` | [0,85; 1,15] |
| `soft_floor` | ativo (≥2×1.10; 1.07 por 1.10) |
| `n_tocas_orfas` | 4 |
| `pct_cargo` (Analista/Técnico/Agente) | 85/10/5 |
| `tecnico_pode_fce` | sim |
| `pct_acumulacao` | 3% |
| `lotacao_dg_vice` | Câmara da Rainha |
| `regra_gestor` | função ≥ 1.13 |
| `seed` | obrigatório |

## 10. Assunções e pendências

- **A2 — "<10 pessoas" cai para a Câmara da Rainha** (12 chefias trilha-1 no quadro); demais pequenas seguem <10. Proporção do quadro vence — condição de aceite do Pedro.
- **A3 — Split 75/25 sede/regionais:** default meu, sem fonte.
- **A4 — Acumulação 3%:** sugestão não vetada, não confirmada.
- **A6 — Lente do RH = Câmara de Cria inteira:** o Pedro disse "eles têm acesso"; li como todos os lotados. Alternativa mais restrita: só gestores 1.13+ da unidade. Um parâmetro resolve.
- **A7 — Interpretação do soft floor:** "segue até onde dá" implementado como *piso que limita o jitter, nunca infla acima do quadro*. Se a intenção era inflar unidades pequenas até o piso, é o inverso — confirmar se a mecânica descrita na Seção 4 é a pretendida.
- **Backlog:** nomeação para colegiado (comitês cross) como candidato a tipo de evento — gaveta a definir no passe de descoberta com RH.
- **Nota (fora de escopo):** camada real de gratificações de representação (centenas) + gratificações militares — não entra no retrofit; relevante um dia para `compensacao` e para o add-on de scoring.

## 11. Invariantes MDM

1. Matrícula `^[0-9]{7}$` (schema v0.7).
2. Lotação sem FK — órfão precisa CARREGAR para ser contado (KR 2.1).
3. Domínios de cargo/classe permanecem texto solto; só `dom_funcao` ganha seed.
4. FOTO sobrescreve por matrícula (UPSERT D-1) — massa é estado vigente, não série.
5. Massa carrega carimbo de versão de esquema + seed; regenerável, nunca migra.
6. Volumetria fictícia = quadro real × jitter — nunca quantidades exatas; populações e lotações inventadas, nunca calibradas em dado real não-público.

---

*v0.3 — 2026-07-04. Substitui v0.2 integralmente. Fechado nesta rodada: piso reinstalado como soft floor; 43ª unidade (Bando de Arribação — análogo da assessoria esquecida), total de chefias bate exato com o quadro (226); regra de gestor = 1.13+ (A5 encerrada); populações de acesso das lentes mapeadas na massa (Lente do RH = Câmara de Cria; financeiro = 6 nomeados: divisão da Cria + CGs+ dos Buscadores).*
