#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# =============================================================================
# MDM-RH — Gerador de massa ficticia (FOTO) — Reino Animal
# versao: v0.3 (ARQUETIPO-PRIMEIRO — a vida vem do designer, o assento do quadro)
# ancora: 3_massa_reino_animal_v0_3.md | semente_trajetorias_v1.yaml (14 arquetipos
#         do designer v0.2) | trajetorias.py (motor unico) | 3_schema_mdm.sql (v0.11)
# -----------------------------------------------------------------------------
# v0.3: o sorteio DEMOGRAFICO de situacao/classe/afastamento (v0.2) MORREU — era
#   desalinhado do handoff do designer. Agora cada servidor nasce de um ARQUETIPO:
#   Camada A estampada por PESO (Wallace 39.6%...), Camada B PLANTADA por contagem
#   (Elias x2, Gerson x2, Vicente x1 — os casos-limite que nao escalam), DG/Vice
#   fixos. A trajetoria do arquetipo (motor trajetorias.py, rng por vinculo) DERIVA
#   situacao/classe/padrao/afastamento/ingresso; o QUADRO estrutural (43 unidades,
#   FCE trilha-1) continua dono de lotacao/funcao/cargo — costura no motor.
#   servidor.csv ganha `arquetipo` + `traj_salt` (o gerador de eventos re-roda a
#   MESMA trajetoria e emite os eventos que aterrissam neste estado).
#   REQUER banco com dominios semeados (regras de modelo vem de la — decisao #5).
# -----------------------------------------------------------------------------
# Le config.yaml e gera massa de FOTO (tabela servidor). NAO gera eventos.
# Deterministico por seed (config; obrigatorio — invariante 5 da spec).
#
# ESTRUTURA (spec Secoes 2-4 / ADR-013): as 43 unidades, o quadro FCE trilha-1 e a
#   escada de niveis sao MODELO (decreto animalizado), nao parametro. Desde a ADR-013
#   vivem em decreto_animalizado_v1.yaml, VERSIONADO por (numero_decreto, vigencia):
#   a vigencia base 11.816/2023 GERA a massa (ordem preservada = seed 42 estavel); a
#   vigencia delta 12.503/2025 so alimenta o dominio. Nomes de unidade sao editaveis;
#   a estrutura porte x quantidade e a ORDEM nao (reordenar quebra o determinismo).
#   Parametros ajustaveis (Secao 9 + comportamentos herdados do v0.1) vivem no
#   config.yaml — nenhum numero de calibracao hardcoded fora do quadro.
#
# Saidas em ./out/:
#   servidor.csv                     FOTO (grao vinculo), pronto p/ carrega_foto.py
#   pessoa.csv                       cadastro (grao CPF): sexo, naturalidade
#   acessos_paineis.csv              populacoes de acesso (GRANT) — spec Secao 7
#   seed_unidades_reino_animal.sql   dom_unidade_eorg (orfas EXCLUIDAS — KR 2.1)
#   seed_funcao_reino_animal.sql     dom_funcao (codigos CCE/FCE usados)
#   seed_estrutura_decreto.sql       dom_estrutura_decreto (esqueleto, 2 vigencias — ADR-013)
#   relatorio_massa.md               contagens + verificacao de invariantes
#
# COERENCIA TEMPORAL (contrato com o futuro gerador de eventos — herdado do v0.1):
#   nascimento -> ingresso -> tempo de casa -> classe/padrao possivel.
#   Nao gera ESPECIAL-V com 2 anos de casa; INATIVO exige idade/tempo.
#
# Uso: python gen_massa.py  [--config config.yaml] [--outdir out]
# Dep: PyYAML  (pip install pyyaml --break-system-packages)
# =============================================================================
import argparse, csv, random, os, re, sys
import datetime as dt
from pathlib import Path
try:
    import yaml
except ImportError:
    sys.exit("Falta PyYAML: pip install pyyaml --break-system-packages")

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import trajetorias as traj   # motor unico de trajetoria (arquetipos do designer)

# ============================================================================
# 1. ESTRUTURA — derivada do decreto ANIMALIZADO versionado (ADR-013).
# Antes hardcoded aqui; agora vem de decreto_animalizado_v1.yaml, vigencia BASE
# (11.816/2023). ORDEM preservada byte-a-byte: `unidades` define cod 100001..
# (e a ordem de iteracao); `quadro` define o stream de rng.shuffle. Reordenar o
# YAML muda a massa (seed 42) — o diff de determinismo pega qualquer deriva.
# A vigencia DELTA (12.503/2025) NAO gera massa: so alimenta o dominio.
# ============================================================================
_DECRETO_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                             "decreto_animalizado_v1.yaml")

def carrega_decreto(path=_DECRETO_PATH):
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)

DECRETO   = carrega_decreto()
_VIG_BASE = DECRETO["vigencia_base"]
_BASE     = DECRETO["vigencias"][_VIG_BASE]

# UNIDADES: lista ordenada (nome, grupo) — cod = COD_BASE + indice, pela ordem.
UNIDADES = [(u["nome"], u["grupo"]) for u in _BASE["unidades"]]
COD_BASE = DECRETO["constantes"]["cod_base"]

# QUADRO FCE trilha-1 (PRE-jitter): unidade -> {chefia, "1.NN": (fce, cce)} na
# ORDEM do `quadro` YAML (e dos niveis dentro de cada unidade). tuple() reproduz
# os pares como estavam no literal antigo.
QUADRO = {
    q["unidade"]: {"chefia": q["chefia"],
                   **{niv: tuple(par) for niv, par in q["niveis"].items()}}
    for q in _BASE["quadro"]
}

# constantes de toca (grupos de Superintendencia). Comentarios nominais:
# toca1: chefia 1.13 + 2x1.10 + 1x1.05 | toca2: chefia 1.13 + coord 1.10 (11 no
# grupo de 9) + 1.05 (9 no grupo) | toca3: chefia 1.13 + 1x1.07 + 1x1.05.
TOCA2_COORDS_GRUPO = DECRETO["constantes"]["toca2_coords_grupo"]
TOCA2_105 = tuple(DECRETO["constantes"]["toca2_105"])   # (fce, cce) no grupo de 9
TOCA3_105 = tuple(DECRETO["constantes"]["toca3_105"])   # (fce, cce) no grupo de 15

NOMES_FUNCAO = dict(DECRETO["funcoes"])

# ============================================================================
# 1b. DOMINIO dom_estrutura_decreto (ADR-013) — derivacao do ESQUELETO a partir
# do decreto animalizado. Puro (SEM rng): so estrutura -> linhas de dominio.
# Codigo CCE/FCE: 1o digito = trilha, 2o numero = nivel_ordinal (hierarquia).
# ============================================================================
_TIPO_POR_NIVEL = {18: "Direção-Geral", 17: "Secretaria", 15: "Diretoria",
                   13: "Superintendência/Coordenação-Geral", 10: "Coordenação",
                   7: "Divisão", 5: "Serviço"}
_DENOM_POR_NIVEL = {18: "Dirigente Máximo", 17: "Secretário", 15: "Diretor",
                    13: "Coordenador-Geral", 10: "Coordenador",
                    7: "Chefe de Divisão", 5: "Chefe de Serviço"}

def _parse_cod_funcao(cod):
    """'FCE 1.07' -> (trilha=1, nivel_ordinal=7)."""
    _, num = cod.split()
    t, n = num.split(".")
    return int(t), int(n)

def _resolve_sede(vig_nome):
    """{unidade: {'chefia': cod, 'posicoes': {cod_funcao: qtd}}} da vigencia (aplica
    deltas se for redacao derivada). So unidades de sede (quadro); tocas/topo a parte."""
    vig = DECRETO["vigencias"][vig_nome]
    quadro_list = vig.get("quadro") or DECRETO["vigencias"][vig["base"]]["quadro"]
    res = {}
    for q in quadro_list:
        pos = {}
        for niv, (fce, cce) in q["niveis"].items():
            if fce: pos[f"FCE {niv}"] = pos.get(f"FCE {niv}", 0) + fce
            if cce: pos[f"CCE {niv}"] = pos.get(f"CCE {niv}", 0) + cce
        res[q["unidade"]] = {"chefia": q["chefia"], "posicoes": pos}
    for d in vig.get("deltas", []):
        alvo = res[d["unidade"]]
        if "set_chefia" in d:
            alvo["chefia"] = d["set_chefia"]
        for cod, qtd in d.get("adiciona", {}).items():
            alvo["posicoes"][cod] = alvo["posicoes"].get(cod, 0) + qtd
    return res

def _rows_unidade(numero, data_vig, cod, nome, pai, chefia_cod, posicoes, chefia_qtd=1):
    ct, cn = _parse_cod_funcao(chefia_cod)
    tipo = _TIPO_POR_NIVEL.get(cn, "")
    linha = lambda c, q, ch: dict(
        numero_decreto=numero, data_vigencia=data_vig, cod_unidade=cod,
        nome_unidade=nome, cod_unidade_pai=pai, tipo_unidade=tipo, cod_funcao=c,
        denominacao=_DENOM_POR_NIVEL.get(_parse_cod_funcao(c)[1], c),
        trilha=_parse_cod_funcao(c)[0], nivel_ordinal=_parse_cod_funcao(c)[1],
        quantidade=q, chefia=ch)
    out = [linha(chefia_cod, chefia_qtd, True)]
    out += [linha(c, q, False) for c, q in posicoes.items()]
    return out

def linhas_estrutura_decreto(unidades):
    """Linhas de dom_estrutura_decreto p/ TODAS as vigencias. Inclui unidades orfas
    de proposito (viram 'so_no_decreto' em vw_orfao_estrutura_decreto); pula as de
    grupo 'estrutura' (sem cargo-funcao no decreto)."""
    qtoca = DECRETO["quadro_toca"]
    topo = DECRETO["topo"]
    cod_topo = DECRETO["constantes"]["cod_topo"]
    rows = []
    for vig_nome, vig in DECRETO["vigencias"].items():
        data_vig = vig["data_vigencia"]
        sede = _resolve_sede(vig_nome)
        rows += _rows_unidade(vig_nome, data_vig, cod_topo, topo["nome"], None,
                              topo["chefia"], {}, chefia_qtd=topo["quantidade"])
        for nome, u in unidades.items():
            grupo = u["grupo"]
            if grupo == "estrutura":
                continue
            if grupo.startswith("toca"):
                qt = qtoca[grupo]
                chefia, posic = qt["chefia"], dict(qt["niveis"])
            elif nome in sede:
                chefia, posic = sede[nome]["chefia"], sede[nome]["posicoes"]
            else:
                continue
            rows += _rows_unidade(vig_nome, data_vig, u["cod"], nome, cod_topo, chefia, posic)
    return rows

def _sql_lit(v):
    if v is None:            return "NULL"
    if isinstance(v, bool):  return "true" if v else "false"
    if isinstance(v, int):   return str(v)
    return "'" + str(v).replace("'", "''") + "'"

# ============================================================================
# 3. NOMES — [nome humano] + [sobrenome kind animal], por sexo (spec Secao 1;
#    sexo alimenta pessoa.csv, grao CPF). 30% ganham sobrenome humano
#    intermediario: "Marina Lobato-Cerva".
# ============================================================================
PRIMEIROS_M = ["Carlos","Pedro","Rafael","Lucas","Bruno","Diego","Gustavo","Rodrigo","Felipe","Thiago",
    "Marcelo","Andre","Vinicius","Eduardo","Fabio","Leandro","Ricardo","Sergio","Alexandre","Paulo",
    "Marcio","Roberto","Daniel","Antonio","Jorge","Mauricio","Henrique","Otavio","Caio","Emerson"]
PRIMEIROS_F = ["Marina","Ana","Julia","Beatriz","Camila","Larissa","Fernanda","Patricia","Amanda","Vanessa",
    "Leticia","Renata","Carolina","Debora","Priscila","Tatiane","Simone","Aline","Monica","Cristina",
    "Sandra","Claudia","Adriana","Luciana","Regina","Elaine","Silvia","Rosana","Ingrid","Natalia"]
SOBRE_HUMANO = ["Lobato","Ferreira","Sales","Rocha","Prado","Nogueira","Campos","Peixoto","Barros",
    "Teles","Fontes","Rezende","Sampaio","Dutra","Vilela","Farias","Braga","Serra","Matos","Pires"]
SOBRE_ANIMAL = ["Cerva","Jaguatirica","Capivara","Tamanduá","Onça","Ariranha","Quati","Irara","Cutia",
    "Paca","Anta","Veado","Graxaim","Jaguar","Suçuarana","Gato-Maracajá","Lobo-Guará","Raposa","Furão",
    "Tatu","Preá","Mocó","Sagui","Bugio","Muriqui","Cuíca","Gambá","Ouriço","Serelepe","Morcego",
    "Gavião","Coruja","Seriema","Jaburu","Tuiuiú","Arara","Tucano","Bem-te-vi","Sabiá","Curió",
    "Carcará","Urubu-Rei","Colhereiro","Anu","Quero-Quero","Jacu","Mutum","Inhambu","Ema","Harpia",
    "Jacaré","Teiú","Iguana","Jiboia","Sucuri","Cascavel","Jararaca","Tartaruga","Cágado","Perereca",
    "Pirarucu","Tambaqui","Dourado","Lambari","Traíra","Tucunaré","Piranha","Bagre","Arraia","Boto",
    "Formiga","Cigarra","Besouro","Mariposa","Vespa","Abelha","Cupim","Louva-Deus","Vaga-Lume","Grilo"]

CAPITAIS = [
    ("AC","Rio Branco"),("AL","Maceio"),("AP","Macapa"),("AM","Manaus"),
    ("BA","Salvador"),("CE","Fortaleza"),("ES","Vitoria"),("GO","Goiania"),
    ("MA","Sao Luis"),("MT","Cuiaba"),("MS","Campo Grande"),("MG","Belo Horizonte"),
    ("PA","Belem"),("PB","Joao Pessoa"),("PR","Curitiba"),("PE","Recife"),
    ("PI","Teresina"),("RJ","Rio de Janeiro"),("RN","Natal"),("RS","Porto Alegre"),
    ("RO","Porto Velho"),("RR","Boa Vista"),("SC","Florianopolis"),("SP","Sao Paulo"),
    ("SE","Aracaju"),("TO","Palmas"),
]

CARGOS = ["Analista", "Técnico", "Agente"]
CLASSES_ORD = ["A", "B", "C", "ESPECIAL"]
PADROES = ["I", "II", "III", "IV", "V"]
# anos MINIMOS de casa p/ estar em cada classe (coerencia: nao dar ESPECIAL a novato)
ANOS_MIN_CLASSE = {"A": 0, "B": 5, "C": 10, "ESPECIAL": 15}

# codigos de dom_afastamento sorteaveis p/ afastado vigente (seed_dominios.sql).
# 40 (Cedido) e 31 (Disponibilidade) NAO entram no sorteio: sao amarrados a
# situacao_funcional CEDIDO/DISPONIBILIDADE (coerencia FOTO).
AFASTAMENTOS_SORTEAVEIS = ["01", "03", "05", "07", "10", "15", "24", "29"]

# spec Secao 8 — orgaos externos (cessao futura; nao usado na FOTO, fica p/ o eixo evento)
ORGAOS_EXTERNOS = ["Polícia Ursa da Federação Animal","Polícia Rodoviária das Capivaras",
    "Agência Central da Alcateia","Esquadra dos Golfinhos","Exército das Formigas",
    "Aeronáutica dos Falcões","Conselho de Controle das Corujas Financeiras",
    "Receita Federal das Abelhas","Banco Central dos Castores","Chancelaria dos Albatrozes",
    "Gabinete de Segurança do Ninho"]


def weighted(d, rng):
    """sorteia chave de dict {valor: peso}."""
    ks, ws = list(d.keys()), list(d.values())
    return rng.choices(ks, weights=ws, k=1)[0]


def maior_resto(pesos, total):
    """Distribui `total` inteiro proporcional a `pesos` por maior resto."""
    s = sum(pesos)
    if s == 0:
        return [0] * len(pesos)
    brutos = [p * total / s for p in pesos]
    base = [int(b) for b in brutos]
    falta = total - sum(base)
    ordem = sorted(range(len(pesos)), key=lambda i: brutos[i] - base[i], reverse=True)
    for i in ordem[:falta]:
        base[i] += 1
    return base


def cpf_valido(rng):
    n = [rng.randint(0, 9) for _ in range(9)]
    for k in (10, 11):
        s = sum(a * b for a, b in zip(n, range(k, 1, -1)))
        n.append((s * 10 % 11) % 10)
    return "".join(map(str, n))


def fmt_ddmmyyyy(d):
    """Formato da API real (SIAPE) — o loader normaliza via _data_iso()."""
    return d.strftime("%d%m%Y")


def gerar(cfg, outdir):
    if cfg.get("seed") is None:
        sys.exit("config: `seed` e obrigatorio (invariante 5 da spec — massa regeneravel)")
    rng = random.Random(cfg["seed"])
    outdir.mkdir(parents=True, exist_ok=True)

    if cfg["data_referencia"] == "ontem":
        d_ref = dt.date.today() - dt.timedelta(days=1)
    else:
        d_ref = dt.date.fromisoformat(str(cfg["data_referencia"]))

    # v0.3: arquetipos (semente do designer) + regras de modelo (banco, decisao #5)
    semente = traj.carrega_semente()
    regras = traj.carrega_regras()
    par = {**semente["parametros_default"],
           "disponibilidade_pct": cfg.get("disponibilidade_pct", 0)}

    unidades = {nome: {"cod": COD_BASE + i, "grupo": grupo} for i, (nome, grupo) in enumerate(UNIDADES)}
    lotaveis = [n for n, u in unidades.items() if u["grupo"] != "estrutura"]
    tocas = [n for n in lotaveis if unidades[n]["grupo"].startswith("toca")]
    sede = [n for n in lotaveis if n not in tocas]

    # ---- orfas (KR 2.1): sorteio por seed, fora do seed_unidades.sql --------
    orfas = set(rng.sample(tocas, cfg["n_tocas_orfas"]))

    # ---- posicoes FCE por unidade: base -> jitter -> soft floor -------------
    fator = rng.uniform(*cfg["jitter_range"])
    posicoes = {}     # unidade -> list[str codigo]  (inclui chefia na posicao 0)

    def expandir(fce, cce, nivel):
        return [f"FCE {nivel}"] * fce + [f"CCE {nivel}"] * cce

    def jitter_unidade(base):  # base: nivel -> (fce, cce)
        out = {}
        for nivel, (fce, cce) in base.items():
            tot = fce + cce
            j = round(tot * fator)
            if nivel == "1.10" and tot >= 2:
                j = max(j, 2)          # soft floor: >=2 coordenacoes onde a base atende
            out[nivel] = min(j, tot)   # piso limita p/ baixo; teto = base (nunca infla)
        # soft floor: cada 1.10 com >=1 x 1.07, ate onde a base 1.07 permite
        if "1.07" in out and "1.10" in out:
            b107 = sum(base["1.07"])
            out["1.07"] = max(out["1.07"], min(out.get("1.10", 0), b107))
        return out

    for nome, q in QUADRO.items():
        pos = [q["chefia"]]
        base = {k: v for k, v in q.items() if k != "chefia"}
        jit = jitter_unidade(base)
        for nivel, n in jit.items():
            fce, cce = base[nivel]
            pool = expandir(fce, cce, nivel)
            rng.shuffle(pool)
            pos += pool[:n]
        posicoes[nome] = pos
    posicoes["__topo__"] = ["CCE 1.18", "CCE 1.18"]  # DG + Vice (invariantes)

    # tocas nivel 1
    for t in (n for n in tocas if unidades[n]["grupo"] == "toca1"):
        base = {"1.10": (2, 0), "1.05": (1, 0)}
        jit = jitter_unidade(base)
        posicoes[t] = ["FCE 1.13"] + expandir(jit.get("1.10", 0), 0, "1.10") + expandir(jit.get("1.05", 0), 0, "1.05")

    # tocas nivel 2: 11 coordenacoes no grupo, jitter p/ baixo (nunca infla),
    # minimo 1 por toca; as que sobram acima de 9 viram a 2a coordenacao.
    t2 = [n for n in tocas if unidades[n]["grupo"] == "toca2"]
    total_coords = min(TOCA2_COORDS_GRUPO, max(len(t2), round(TOCA2_COORDS_GRUPO * fator)))
    duplas = set(rng.sample(range(len(t2)), total_coords - len(t2)))
    n105_t2 = min(len(t2), round(len(t2) * fator))
    com105 = set(rng.sample(range(len(t2)), n105_t2))
    pool105 = expandir(*TOCA2_105, "1.05"); rng.shuffle(pool105)
    for i, t in enumerate(t2):
        posicoes[t] = ["FCE 1.13"] + ["FCE 1.10"] * (2 if i in duplas else 1) \
                      + ([pool105.pop()] if i in com105 else [])

    # tocas nivel 3: chefia + 1.07 + 1.05 (posicoes unitarias — invariantes)
    t3 = [n for n in tocas if unidades[n]["grupo"] == "toca3"]
    pool105 = expandir(*TOCA3_105, "1.05"); rng.shuffle(pool105)
    for t in t3:
        posicoes[t] = ["FCE 1.13", "FCE 1.07", pool105.pop()]

    # ---- populacao por unidade ----------------------------------------------
    n_extra = round(cfg["total_vinculos"] * cfg["pct_acumulacao"])
    n_pessoas = cfg["total_vinculos"] - n_extra
    pop_sede = round(n_pessoas * cfg["split_sede_regionais"] / 100)
    pop_toca = n_pessoas - pop_sede
    peso = lambda n: max(len(posicoes.get(n, [])), 1)
    pops = {}
    for grupo, alvo in ((sede, pop_sede - 2), (tocas, pop_toca)):  # -2 = DG/Vice
        dist = maior_resto([peso(n) for n in grupo], alvo)
        for n, p in zip(grupo, dist):
            pops[n] = max(p, len(posicoes.get(n, [])) + 1)  # piso: acomoda chefias +1

    # ---- pessoas (grao CPF) e vinculos (grao matricula) ----------------------
    usados, servidores = set(), []
    pessoas = {}  # cpf -> {sexo, uf, mun, nasc, nome}

    def nome_novo(rng, sexo):
        lista = PRIMEIROS_F if sexo == "F" else PRIMEIROS_M
        for _ in range(300):
            p = rng.choice(lista)
            meio = rng.choice(SOBRE_HUMANO) + "-" if rng.random() < 0.30 else ""
            nm = f"{p} {meio}{rng.choice(SOBRE_ANIMAL)}"
            if nm not in usados:
                usados.add(nm); return nm
        raise RuntimeError("esgotou combinacoes de nome")

    def nova_pessoa(sexo=None, nome=None):
        sexo = sexo or weighted(cfg["sexo"], rng)
        if rng.random() < cfg["geografia"]["DF_Brasilia"]:
            uf, mun = "DF", "Brasilia"
        else:
            uf, mun = rng.choice(CAPITAIS)
        idade = rng.randint(cfg["idade"]["min"], cfg["idade"]["max"])
        nasc = dt.date(d_ref.year - idade, rng.randint(1, 12), rng.randint(1, 28))
        cpf = cpf_valido(rng)
        while cpf in pessoas:
            cpf = cpf_valido(rng)
        p = {"cpf": cpf, "sexo": sexo, "uf": uf, "mun": mun, "nasc": nasc,
             "nome": nome or nome_novo(rng, sexo)}
        pessoas[cpf] = p
        return p

    prox_matricula = 1000001
    def nova_matricula():
        nonlocal prox_matricula
        m = str(prox_matricula); prox_matricula += 1
        return m

    def vinculo(p, unidade, cargo, funcao):
        """v0.3: cria o ASSENTO (identidade + lotacao + funcao + cargo). A VIDA
        (situacao/classe/padrao/afastamento/ingresso) vem do ARQUETIPO, estampada
        depois por estampa_arquetipo() — o sorteio demografico do v0.2 morreu."""
        # exercicio: igual a lotacao, salvo % que exerce em outra unidade valida
        exerc = unidades[unidade]["cod"]
        if rng.random() < cfg["exercicio_difere_lotacao_pct"]:
            exerc = unidades[rng.choice(lotaveis)]["cod"]

        # funcao em transicao (raro) — data em DDMMYYYY, exercita o _data_iso do loader
        nova_f, d_nova = "", ""
        if funcao and rng.random() < cfg["nova_funcao_pct"]:
            nova_f = funcao
            d_nova = fmt_ddmmyyyy(d_ref - dt.timedelta(days=rng.randint(1, 90)))

        return {
            "matricula_funcional": nova_matricula(), "cpf": p["cpf"], "nome": p["nome"],
            "data_nascimento": p["nasc"].isoformat(), "cargo": cargo,
            "classe": "A", "padrao": "I",              # placeholder — arquetipo estampa
            "sigla_nivel_cargo": "NS", "funcao_comissionada": funcao or "",
            "nova_funcao": nova_f, "data_ingresso_nova_funcao": d_nova,
            "cod_unidade_lotacao": unidades[unidade]["cod"], "cod_unidade_exercicio": exerc,
            "origem_unidade": "SIAPE" if unidade in orfas else "SIORG",
            "situacao_funcional": "ATIVO",             # placeholder — arquetipo estampa
            "regime_juridico": weighted(cfg["regime"], rng),
            "data_exercicio_no_orgao": d_ref.isoformat(),   # placeholder
            "cod_afastamento_vigente": "", "data_referencia": d_ref.isoformat(),
            "cod_mecanica": "ingestao",
            "arquetipo": "", "traj_salt": "0",
        }

    # topo (hard-coded, spec Secao 1) — lotacao: cfg lotacao_dg_vice
    un_topo = cfg["lotacao_dg_vice"]
    dg_p = nova_pessoa(sexo="M", nome="Aurélio Leão"); usados.add("Aurélio Leão")
    vice_p = nova_pessoa(sexo="M", nome="João Equino"); usados.add("João Equino")
    dg = vinculo(dg_p, un_topo, "Analista", "CCE 1.18")
    vice = vinculo(vice_p, un_topo, "Analista", "CCE 1.18")
    dg["cod_afastamento_vigente"] = vice["cod_afastamento_vigente"] = ""
    servidores += [dg, vice]

    # unidades: chefia + FCEs + resto
    tecnico_ok = {n for n in lotaveis if unidades[n]["grupo"] in ("meio", "pequena")} | {"Oficina de Casulos"}
    for un in lotaveis:
        pos = list(posicoes.get(un, []))
        alvo = pops[un]
        chefia = pos.pop(0) if pos else None
        if chefia:
            # diretora da Camara de Cria: nome feminino (sabor, spec Secao 1)
            p = nova_pessoa(sexo="F") if un == "Câmara de Cria" else nova_pessoa()
            servidores.append(vinculo(p, un, "Analista", chefia))
        for f in pos:
            cargo = "Técnico" if (un in tecnico_ok and cfg["tecnico_pode_fce"] and rng.random() < 0.10) else "Analista"
            servidores.append(vinculo(nova_pessoa(), un, cargo, f))
        for _ in range(alvo - 1 - len(pos)):
            servidores.append(vinculo(nova_pessoa(), un, "Analista", None))  # cargo ajustado depois

    # ---- redistribui cargos efetivos nos SEM funcao (spec Secao 5) ----------
    sem_funcao = [s for s in servidores if not s["funcao_comissionada"]]
    n_agente = round(len(servidores) * cfg["pct_cargo"]["Agente"])
    n_tecnico_alvo = round(len(servidores) * cfg["pct_cargo"]["Tecnico"])
    n_tecnico_ja = sum(1 for s in servidores if s["cargo"] == "Técnico")
    rng.shuffle(sem_funcao)
    cods_tec_ok = {unidades[n]["cod"] for n in tecnico_ok}
    for s in sem_funcao:
        if n_agente > 0:
            s["cargo"] = "Agente"; n_agente -= 1
        elif n_tecnico_ja < n_tecnico_alvo and s["cod_unidade_lotacao"] in cods_tec_ok:
            s["cargo"] = "Técnico"; n_tecnico_ja += 1

    # =========================================================================
    # v0.3 — ESTAMPAGEM DE ARQUETIPOS (a vida vem do designer; o assento ficou)
    # =========================================================================
    CARGO_SEMENTE = {"Técnico": "Tecnico", "Analista": "Analista", "Agente": "Agente"}
    nasc_fixado = {}   # cpf -> date (Bruno: o nasc do 1o vinculo vale p/ pessoa)

    def estampa_arquetipo(s, rotulo, ingresso_base=None):
        """Roda o motor de trajetoria e grava o ESTADO do arquetipo no servidor.
        O salt garante reproducao identica no gerador de eventos."""
        arq, spec = traj.resolve(semente, rotulo)
        alvo_t = {"lotacao_final": s["cod_unidade_lotacao"],
                  "funcao_final": s["funcao_comissionada"] or None,
                  "forca_ativo": bool(s["funcao_comissionada"]),
                  "cargo": s["cargo"], "unidades": traj.UNIVERSO_UNIDADES,
                  "ingresso_base": ingresso_base}
        for salt in range(16):
            rv = traj.rng_vinculo(cfg["seed"], s["matricula_funcional"], salt)
            tr = traj.gera_trajetoria(rv, arq, spec, d_ref, regras, par, alvo_t)
            if tr:
                break
        else:
            sys.exit(f"arquetipo '{rotulo}' nao coube em 16 saltos (mat {s['matricula_funcional']})")
        est = tr["estado"]
        s["arquetipo"], s["traj_salt"] = rotulo, str(salt)
        s["classe"], s["padrao"] = est["classe"], est["padrao"]
        s["situacao_funcional"] = est["situacao_funcional"]
        s["cod_afastamento_vigente"] = est["cod_afastamento_vigente"] or ""
        s["data_exercicio_no_orgao"] = est["ingresso"].isoformat()
        if s["situacao_funcional"] != "ATIVO":       # nova_funcao so faz sentido ATIVO
            s["nova_funcao"] = ""; s["data_ingresso_nova_funcao"] = ""
        # nasc coerente com o ingresso (INATIVO exige >=50 na aposentadoria);
        # draws pos-motor no rng do vinculo: nao afetam a reproducao dos eventos
        if s["cpf"] in nasc_fixado:
            nasc = nasc_fixado[s["cpf"]]
        else:
            idade_ing = rv.randint(cfg["idade_ingresso"]["min"], cfg["idade_ingresso"]["max"])
            if s["situacao_funcional"] == "INATIVO":
                anos = (d_ref - est["ingresso"]).days // 365
                idade_ing = max(idade_ing, 51 - anos)
            nasc = dt.date(est["ingresso"].year - idade_ing,
                           est["ingresso"].month, min(est["ingresso"].day, 28))
            nasc_fixado[s["cpf"]] = nasc
            pessoas[s["cpf"]]["nasc"] = nasc
        s["data_nascimento"] = nasc.isoformat()
        return tr

    def moldes_elegiveis(cargo, tem_funcao):
        """Camada A por cargo do assento; assento com funcao prefere moldes cuja
        historia assume funcao; Agente NUNCA recebe molde com designacao (§5)."""
        A = [a for a in semente["camada_A"] if "vinculos" not in a]
        cand = [a for a in A if a.get("cargo", "Analista") == CARGO_SEMENTE[cargo]]
        if cargo == "Agente" or not cand:
            cand = [a for a in A if not traj.tem_designacao(a)]
        if tem_funcao:
            pref = [a for a in cand if traj.tem_designacao(a)]
            cand = pref or cand
        return cand

    # (a) DG/Vice — arquetipos institucionais fixos (semente ids 99/98)
    for s in servidores:
        if s["nome"] == "Aurélio Leão":
            estampa_arquetipo(s, "Aurélio Leão")
        elif s["nome"] == "João Equino":
            estampa_arquetipo(s, "João Equino")

    # (b) Camada A — estampa por PESO do designer (cargo do assento restringe)
    for s in servidores:
        if s["arquetipo"]:
            continue
        cand = moldes_elegiveis(s["cargo"], bool(s["funcao_comissionada"]))
        molde = rng.choices(cand, weights=[a["peso"] for a in cand], k=1)[0]
        estampa_arquetipo(s, molde["nome"])

    # (c) Camada B — PLANTADOS (contagem fixa, invariante ao N; casos-limite)
    fixos_nomes = {"Aurélio Leão", "João Equino"}
    plantaveis = [b for b in semente["camada_B"] if b["nome"] not in fixos_nomes]
    pool = [s for s in servidores
            if not s["funcao_comissionada"] and s["nome"] not in fixos_nomes]
    vitimas = iter(rng.sample(pool, sum(b["contagem"] for b in plantaveis)))
    for b in plantaveis:
        cargo_b = {v: k for k, v in CARGO_SEMENTE.items()}[b.get("cargo", "Analista")]
        for _ in range(b["contagem"]):
            s = next(vitimas)
            s["cargo"] = cargo_b
            nasc_fixado.pop(s["cpf"], None)      # re-deriva nasc p/ o arco completo
            estampa_arquetipo(s, b["nome"])

    # (d) acumulacao licita = arquetipo BRUNO (1 pessoa, 2 vinculos, 2 vidas)
    ja_unicos = {s["nome"] for s in servidores
                 if s["arquetipo"] in {b["nome"] for b in plantaveis} | fixos_nomes}
    candidatos = [s for s in servidores
                  if not s["funcao_comissionada"] and "#" not in s["arquetipo"]
                  and s["arquetipo"] not in {b["nome"] for b in plantaveis}
                  and s["nome"] not in fixos_nomes | ja_unicos]
    for s in rng.sample(candidatos, min(n_extra, len(candidatos))):
        nasc_fixado.pop(s["cpf"], None)
        tr_a = estampa_arquetipo(s, "Bruno Vespertílio#A")
        clone = dict(s)
        clone["matricula_funcional"] = nova_matricula()
        clone["funcao_comissionada"] = ""
        clone["nova_funcao"] = ""; clone["data_ingresso_nova_funcao"] = ""
        clone["cod_afastamento_vigente"] = ""   # afastamento nao viaja entre vinculos
        clone["cargo"] = "Analista"             # 2o concurso (spec B da semente)
        un2 = rng.choice(lotaveis)
        clone["cod_unidade_lotacao"] = clone["cod_unidade_exercicio"] = unidades[un2]["cod"]
        clone["origem_unidade"] = "SIAPE" if un2 in orfas else "SIORG"
        estampa_arquetipo(clone, "Bruno Vespertílio#B",
                          ingresso_base=tr_a["estado"]["ingresso"])
        servidores.append(clone)

    # ---- populacoes de acesso (spec Secao 7) --------------------------------
    acessos = []
    cod = lambda n: unidades[n]["cod"]
    def em(un, sufixos):
        return [s for s in servidores if s["cod_unidade_lotacao"] == cod(un)
                and any(s["funcao_comissionada"].endswith(p) for p in sufixos)]
    # Lente do RH: todos da Camara de Cria (default; alternativa restrita = A6)
    for s in servidores:
        if s["cod_unidade_lotacao"] == cod("Câmara de Cria"):
            acessos.append((s["matricula_funcional"], s["nome"], "lente_rh"))
    # Calculadora: divisao financeira da Cria (1x1.10 + 1x1.13 + diretora 1.15)
    #              + gestores 1.13+ dos Buscadores (2x1.13 + chefe CCE 1.15) = 6 nomeados
    fin = []
    fin += em("Câmara de Cria", ["1.15"])[:1]
    fin += em("Câmara de Cria", ["1.13"])[:1]
    fin += em("Câmara de Cria", ["1.10"])[:1]
    fin += em("Buscadores de Mantimentos", ["1.15", "1.13"])
    for s in fin:
        acessos.append((s["matricula_funcional"], s["nome"], "calculadora"))
    # Filme do Gestor: funcao >= 1.13 (regra fechada — spec Secao 7)
    NIVEIS_GESTOR = ("1.13", "1.15", "1.17", "1.18")
    for s in servidores:
        if any(s["funcao_comissionada"].endswith(n) for n in NIVEIS_GESTOR):
            acessos.append((s["matricula_funcional"], s["nome"], "filme_gestor"))

    # ---- saidas --------------------------------------------------------------
    cols = ["matricula_funcional","cpf","nome","data_nascimento","cargo","classe","padrao",
            "sigla_nivel_cargo","funcao_comissionada","nova_funcao","data_ingresso_nova_funcao",
            "cod_unidade_lotacao","cod_unidade_exercicio","origem_unidade","situacao_funcional",
            "regime_juridico","data_exercicio_no_orgao","cod_afastamento_vigente",
            "data_referencia","cod_mecanica",
            "arquetipo","traj_salt"]   # v0.3: contrato com o gerador de eventos
                                       # (o loader ignora colunas extras — nao vao ao banco)
    with open(outdir / "servidor.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols); w.writeheader(); w.writerows(servidores)

    with open(outdir / "pessoa.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["cpf","sexo","uf_nascimento","municipio_nascimento","data_nascimento"])
        cpfs_usados = {s["cpf"] for s in servidores}
        for cpf, p in pessoas.items():
            if cpf in cpfs_usados:
                w.writerow([cpf, p["sexo"], p["uf"], p["mun"], p["nasc"].isoformat()])

    with open(outdir / "acessos_paineis.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f); w.writerow(["matricula_funcional", "nome", "painel"]); w.writerows(acessos)

    with open(outdir / "seed_unidades_reino_animal.sql", "w", encoding="utf-8") as f:
        f.write("-- dom_unidade_eorg — massa Reino Animal (spec v0.3). ORFAS EXCLUIDAS (KR 2.1):\n")
        f.write("".join(f"--   orfa: {o} (cod {unidades[o]['cod']} NAO carregado de proposito)\n" for o in sorted(orfas)))
        f.write("INSERT INTO dom_unidade_eorg (cod_unidade, nome_unidade) VALUES\n")
        linhas = [f"    ({u['cod']}, '{n.replace(chr(39), chr(39)*2)}')"
                  for n, u in unidades.items() if n not in orfas]
        f.write(",\n".join(linhas) + "\nON CONFLICT (cod_unidade) DO NOTHING;\n")

    usadas = sorted({s["funcao_comissionada"] for s in servidores if s["funcao_comissionada"]})
    with open(outdir / "seed_funcao_reino_animal.sql", "w", encoding="utf-8") as f:
        f.write("-- dom_funcao — codigos CCE/FCE usados pela massa (spec v0.3 Secao 4)\n")
        f.write("INSERT INTO dom_funcao (cod, nome) VALUES\n")
        f.write(",\n".join(f"    ('{c}', '{NOMES_FUNCAO[c]}')" for c in usadas))
        f.write("\nON CONFLICT (cod) DO NOTHING;\n")

    # ADR-013: ESQUELETO do decreto animalizado -> dom_estrutura_decreto (2 vigencias).
    # Inclui unidades orfas de proposito (o E-Org exclui as orfas; a diferenca aparece
    # em vw_orfao_estrutura_decreto — o 2o espelho da KR 2.1).
    cols = ["numero_decreto", "data_vigencia", "cod_unidade", "nome_unidade",
            "cod_unidade_pai", "tipo_unidade", "cod_funcao", "denominacao",
            "trilha", "nivel_ordinal", "quantidade", "chefia"]
    with open(outdir / "seed_estrutura_decreto.sql", "w", encoding="utf-8") as f:
        f.write("-- dom_estrutura_decreto — ESQUELETO do decreto ANIMALIZADO (ADR-013).\n")
        f.write("-- Vigencias: 11.816/2023 (base, gera a massa) + 12.503/2025 (delta).\n")
        f.write("-- ORFAS INCLUIDAS de proposito (viram 'so_no_decreto' no 2o espelho).\n")
        f.write("INSERT INTO dom_estrutura_decreto (" + ", ".join(cols) + ") VALUES\n")
        linhas = ["    (" + ", ".join(_sql_lit(r[c]) for c in cols) + ")"
                  for r in linhas_estrutura_decreto(unidades)]
        f.write(",\n".join(linhas) + "\nON CONFLICT DO NOTHING;\n")

    return servidores, pessoas, acessos, unidades, orfas, fator, d_ref


def validar(servidores, pessoas, acessos, unidades, orfas, fator, cfg, d_ref, outdir):
    erros, checks = [], []
    def check(cond, msg):
        (checks if cond else erros).append(msg)

    mats = [s["matricula_funcional"] for s in servidores]
    check(len(mats) == len(set(mats)), f"matriculas unicas ({len(mats)})")
    check(all(re.fullmatch(r"[0-9]{7}", m) for m in mats), "matricula ^[0-9]{7}$")
    check(all(re.fullmatch(r"[0-9]{11}", s["cpf"]) for s in servidores), "cpf 11 digitos")
    check(all(not (s["cargo"] == "Agente" and s["funcao_comissionada"]) for s in servidores),
          "Agente NUNCA tem funcao")
    tec_ok_cods = {u["cod"] for n, u in unidades.items()
                   if u["grupo"] in ("meio", "pequena")} | {unidades["Oficina de Casulos"]["cod"]}
    check(all(s["cod_unidade_lotacao"] in tec_ok_cods for s in servidores if s["cargo"] == "Técnico"),
          "Tecnico so em meio/pequenas/Oficina")

    n = len(servidores)
    por_cargo = {c: sum(1 for s in servidores if s["cargo"] == c) for c in CARGOS}
    check(abs(por_cargo["Agente"] / n - cfg["pct_cargo"]["Agente"]) < 0.01,
          f"Agente ~{cfg['pct_cargo']['Agente']:.0%} ({por_cargo['Agente']/n:.1%})")

    cods_orfas = {unidades[o]["cod"] for o in orfas}
    n_orfaos = sum(1 for s in servidores if s["cod_unidade_lotacao"] in cods_orfas)
    check(n_orfaos > 0, f"orfaos estruturais carregados: {n_orfaos} em {len(orfas)} tocas")

    calc = [a for a in acessos if a[2] == "calculadora"]
    check(len(calc) == 6, f"populacao Calculadora = {len(calc)} (esperado 6)")

    cpfs = {}
    for s in servidores:
        cpfs.setdefault(s["cpf"], []).append(s["matricula_funcional"])
    acum = sum(1 for v in cpfs.values() if len(v) > 1)
    check(acum > 0, f"acumulacao licita: {acum} CPFs com 2 vinculos")

    dg = [s for s in servidores if s["nome"] == "Aurélio Leão"]
    check(len(dg) == 1 and dg[0]["funcao_comissionada"] == "CCE 1.18", "DG = Aurelio Leao CCE 1.18")

    # --- arquetipos (v0.3: a vida vem do designer) -----------------------------
    check(all(s.get("arquetipo") for s in servidores), "todo vinculo tem arquetipo")
    por_arq = {}
    for s in servidores:
        por_arq[s["arquetipo"]] = por_arq.get(s["arquetipo"], 0) + 1
    check(por_arq.get("Elias Elefante", 0) == 2, f"plantados: Elias x{por_arq.get('Elias Elefante', 0)} (esperado 2)")
    check(por_arq.get("Gerson Raposão", 0) == 2, f"plantados: Gerson x{por_arq.get('Gerson Raposão', 0)} (esperado 2)")
    check(por_arq.get("Vicente Cachorro-do-Mato", 0) == 1, f"plantados: Vicente x{por_arq.get('Vicente Cachorro-do-Mato', 0)} (esperado 1)")
    check(por_arq.get("Bruno Vespertílio#A", 0) == por_arq.get("Bruno Vespertílio#B", 0),
          "Bruno: pares #A/#B casados")

    # --- FKs de dominio (espelho do seed_dominios.sql v0.2) -------------------
    DOM_SITUACAO = {"ATIVO", "INATIVO", "CEDIDO", "DISPONIBILIDADE", "DESLIGADO"}
    DOM_AFAST = {"01", "03", "05", "06", "07", "10", "11", "12,13", "15", "17-20,35,43",
                 "21,39,45", "22,36", "24", "25", "29", "31", "40"}
    check(all(s["situacao_funcional"] in DOM_SITUACAO for s in servidores),
          "situacao_funcional dentro de dom_situacao_vinculo")
    check(all(not s["cod_afastamento_vigente"] or s["cod_afastamento_vigente"] in DOM_AFAST
              for s in servidores), "cod_afastamento_vigente dentro de dom_afastamento")
    check(all(s["cod_afastamento_vigente"] == "40" for s in servidores
              if s["situacao_funcional"] == "CEDIDO"), "CEDIDO => afastamento 40")
    check(all(s["situacao_funcional"] == "ATIVO" for s in servidores if s["funcao_comissionada"]),
          "quem tem funcao e ATIVO")
    afastados = sum(1 for s in servidores if s["cod_afastamento_vigente"])
    check(afastados > 0, f"afastados vigentes: {afastados} (alimenta vw_afastado_conta_exercicio)")

    # --- coerencia temporal (contrato com o gerador de eventos) ---------------
    ruins, futuros = 0, 0
    for s in servidores:
        d_ing = dt.date.fromisoformat(s["data_exercicio_no_orgao"])
        anos = (d_ref - d_ing).days / 365.25
        if ANOS_MIN_CLASSE[s["classe"]] > anos + 0.01:
            ruins += 1
        if d_ing > d_ref:
            futuros += 1
    check(ruins == 0, f"classe sem lastro de tempo de casa: {ruins} (esperado 0)")
    check(futuros == 0, f"ingresso no futuro: {futuros} (esperado 0)")

    por_funcao = {}
    for s in servidores:
        if s["funcao_comissionada"]:
            por_funcao[s["funcao_comissionada"]] = por_funcao.get(s["funcao_comissionada"], 0) + 1
    gestores = sum(v for k, v in por_funcao.items() if k.split()[-1] in ("1.13", "1.15", "1.17", "1.18"))
    por_situacao = {}
    for s in servidores:
        por_situacao[s["situacao_funcional"]] = por_situacao.get(s["situacao_funcional"], 0) + 1
    sx = {}
    for p in pessoas.values():
        sx[p["sexo"]] = sx.get(p["sexo"], 0) + 1
    df = sum(1 for p in pessoas.values() if p["uf"] == "DF")

    rel = [f"# Relatorio da massa Reino Animal — seed {cfg['seed']}, jitter aplicado {fator:.3f}",
           f"carimbo: massa v0.3 ARQUETIPO-PRIMEIRO | semente_trajetorias_v1.yaml | schema v0.11 | data_referencia {d_ref}",
           "",
           f"- vinculos: {n} | pessoas (CPF): {len(cpfs)} | acumulacao: {acum} CPFs",
           f"- cargos: {por_cargo}",
           f"- situacao (EMERGENTE dos arquetipos): {dict(sorted(por_situacao.items()))} | afastados vigentes: {afastados}",
           f"- arquetipos: {dict(sorted(por_arq.items(), key=lambda kv: -kv[1]))}",
           f"- sexo (pessoas): {dict(sorted(sx.items()))} | naturalidade DF: {100*df/len(pessoas):.0f}%",
           f"- comissionados: {sum(por_funcao.values())} | gestores (1.13+): {gestores}",
           f"- por funcao: {dict(sorted(por_funcao.items()))}",
           f"- orfas (fora do dom_unidade_eorg): {sorted(orfas)} | servidores orfaos: {n_orfaos}",
           f"- acessos: lente_rh={sum(1 for a in acessos if a[2]=='lente_rh')}, "
           f"calculadora={len(calc)}, filme_gestor={sum(1 for a in acessos if a[2]=='filme_gestor')}",
           "", "## Invariantes"]
    rel += [f"- OK: {c}" for c in checks] + [f"- **FALHA**: {e}" for e in erros]
    (outdir / "relatorio_massa.md").write_text("\n".join(rel), encoding="utf-8")
    return erros


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default=os.path.join(os.path.dirname(__file__), "config.yaml"))
    ap.add_argument("--outdir", default=os.path.join(os.path.dirname(__file__), "out"))
    args = ap.parse_args()
    cfg = yaml.safe_load(open(args.config, encoding="utf-8"))
    outdir = Path(args.outdir)
    servidores, pessoas, acessos, unidades, orfas, fator, d_ref = gerar(cfg, outdir)
    erros = validar(servidores, pessoas, acessos, unidades, orfas, fator, cfg, d_ref, outdir)
    print(f"gerados {len(servidores)} vinculos | erros de invariante: {len(erros)}")
    if erros:
        print("\n".join("FALHA: " + e for e in erros)); sys.exit(1)


if __name__ == "__main__":
    main()
