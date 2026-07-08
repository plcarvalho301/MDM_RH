#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# =============================================================================
# MDM-RH — MOTOR DE TRAJETORIAS (Reino Animal) — v1
# Ancoras: semente_trajetorias_v1.yaml (14 arquetipos do designer, normalizados)
#          | 3_catalogo_eventos_v1.yaml v1.1 | ADR-008 | handoff do designer v0.2
# -----------------------------------------------------------------------------
# O MOTOR UNICO da vida funcional. E usado pelos DOIS geradores:
#   gen_massa.py        -> roda a trajetoria p/ derivar o ESTADO do servidor na
#                          data_ref (situacao, classe/padrao, afastamento) — o
#                          arquetipo dirige a VIDA; o assento (lotacao/funcao)
#                          vem do quadro estrutural e e passado como ALVO.
#   gerador_eventos.py  -> re-roda a MESMA trajetoria (mesmo rng por vinculo) e
#                          emite os EVENTOS; o estado projetado tem que bater
#                          com o que o gen_massa escreveu (assert + --valida).
#
# REPRODUTIBILIDADE: rng por vinculo = Random(f"{seed}:{matricula}:{salt}").
#   Ambos os lados consomem EXATAMENTE os mesmos draws (mesma sequencia de
#   codigo); o salt vive na coluna traj_salt do servidor.csv (o gen_massa
#   incrementa quando um arco nao coube ou nao satisfez o alvo).
#
# COSTURA arquetipo x assento (a reconciliacao FOTO x EVENTO fina):
#   - lotacao: a trajetoria COMECA no assento; se a historia mudou de unidade
#     (REMOCAO/muda_unidade), uma REMOCAO corretiva devolve ao assento no fim.
#   - funcao: a historia corre; no fim, se o assento tem funcao != vigente,
#     emite-se a designacao do assento (ultima vence no replay); se o assento
#     NAO tem funcao e a historia terminou com uma, emite-se a dispensa.
#   - forca_ativo (assento com funcao): trunca o arco em EM-CURSO (u<=0.88) e
#     pula marcos DESLIGAMENTO/CESSAO — quem tem funcao e ATIVO (invariante).
#
# REGRAS DE MODELO NAO VIVEM AQUI (decisao #5): motivo->situacao, afastamento->
#   {deriva_situacao, pausa_folha, suspende_progressao} vem do banco (regras).
#
# CESSAO espelho: cada CESSAO emite TAMBEM o AFASTAMENTO 40 do mesmo intervalo
#   (v0.9: "CESSAO aparece 2x de proposito" — e a convencao CEDIDO<=>40 da foto).
# DISPONIBILIDADE: regra de negocio (Pedro, 2026-07-05): so existiu para poucos
#   ativos entre 1991 e 2000 — injetada nos elegiveis (ATIVO sem funcao, ingresso
#   <= 1995) como AFASTAMENTO 31 em aberto iniciado naquela janela.
# =============================================================================
import os
import random
from datetime import date

GRADE = [(c, p) for c in ["A", "B", "C", "ESPECIAL"] for p in ["I", "II", "III", "IV", "V"]]
UNIVERSO_UNIDADES = list(range(100001, 100044))   # massa §2: 43 unidades (constante
# nos DOIS lados do encanamento — destino de REMOCAO historica; o assento final
# e sempre o alvo, entao intermediarios em qualquer unidade sao apenas historia)


# ── util ─────────────────────────────────────────────────────────────────────
def add_meses(d, m):
    from calendar import monthrange
    y, mo = d.year + (d.month - 1 + m) // 12, (d.month - 1 + m) % 12 + 1
    return date(y, mo, min(d.day, monthrange(y, mo)[1]))


def d28(d):
    return date(d.year, d.month, min(d.day, 28))


def rint(rng, par):
    return rng.randint(par[0], par[1])


def rng_vinculo(seed, matricula, salt=0):
    """Um RNG por vinculo — a MESMA trajetoria dos dois lados do encanamento."""
    return random.Random(f"{seed}:{matricula}:{salt}")


# ── regras de modelo (dado, nao codigo — decisao #5) ─────────────────────────
def carrega_env(path=None):
    path = path or os.path.join(os.path.dirname(__file__), "..", "pipeline", "loaders", ".env")
    env = {}
    if os.path.exists(path):
        for linha in open(path, encoding="utf-8"):
            linha = linha.strip()
            if linha and not linha.startswith("#") and "=" in linha:
                k, v = linha.split("=", 1)
                env[k.strip()] = v.strip()
    for k in ("PGHOST", "PGPORT", "PGDATABASE", "PGUSER", "PGPASSWORD"):
        if os.environ.get(k):
            env[k] = os.environ[k]
    return env


def carrega_regras(env=None):
    """Le dom_motivo_deslig + dom_afastamento do banco. Os dominios tem que estar
    semeados ANTES dos geradores (pipeline: schema+seed_dominios primeiro)."""
    import psycopg2
    env = env or carrega_env()
    conn = psycopg2.connect(
        host=env.get("PGHOST", "localhost"), port=env.get("PGPORT", "5432"),
        dbname=env.get("PGDATABASE", "mdm_rh"), user=env.get("PGUSER", "postgres"),
        password=env.get("PGPASSWORD", ""))
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT cod_motivo_deslig, situacao_resultante FROM dom_motivo_deslig")
            motivo_sit = dict(cur.fetchall())
            cur.execute("SELECT cod_afastamento, deriva_situacao, pausa_folha,"
                        "       conta_efetivo_exercicio FROM dom_afastamento")
            deriva, pausa, suspende = {}, set(), set()
            for cod, der, pf, conta in cur.fetchall():
                if der:
                    deriva[cod] = der
                if pf:
                    pausa.add(cod)
                if conta == "nao":
                    suspende.add(cod)      # nao conta efetivo exercicio => progressao para
    finally:
        conn.close()
    if not motivo_sit or not deriva:
        raise SystemExit("dominios vazios no banco — rode schema + seed_dominios ANTES dos geradores.")
    return {"motivo_sit": motivo_sit, "afast_deriva": deriva,
            "afast_pausa": pausa, "afast_suspende": suspende}


# ── semente ──────────────────────────────────────────────────────────────────
def carrega_semente(path=None):
    import yaml
    path = path or os.path.join(os.path.dirname(__file__), "semente_trajetorias_v1.yaml")
    sem = yaml.safe_load(open(path, encoding="utf-8"))
    idx = {}
    for a in sem["camada_A"]:
        a["truncavel"] = True
        idx[a["nome"]] = a
    for b in sem["camada_B"]:
        b["truncavel"] = False       # plantado: o caso-limite exige o arco COMPLETO
        idx[b["nome"]] = b
    sem["_idx"] = idx
    return sem


def resolve(sem, rotulo):
    """'Bruno Vespertílio#B' -> (arquetipo, spec do vinculo B). Sem sufixo -> (arq, arq)."""
    nome, _, suf = rotulo.partition("#")
    arq = sem["_idx"][nome]
    if suf:
        spec = arq["vinculos"][0 if suf == "A" else 1]
    else:
        spec = arq
    return arq, spec


def tem_designacao(arq):
    """Molde cuja historia inclui assumir funcao (elegivel preferencial p/ assento
    com funcao; PROIBIDO para cargo Agente — massa §5)."""
    specs = arq.get("vinculos") or [arq]
    return any(m.get("movimento") == "designacao"
               for s in specs for m in s.get("marcos", []))


# ── o motor ──────────────────────────────────────────────────────────────────
def gera_trajetoria(rng, arq, spec, data_ref, regras, par, alvo):
    """
    Anda a maquina de estados do arquetipo e devolve:
      {"eventos": [(tipo, data, payload, atraso_h)], "estado": {...}, "folha": {...}}
    ou None se o arco de um plantado (nao-truncavel) nao coube ate data_ref —
    o chamador re-sorteia com salt+1.
    alvo = {"lotacao_final": int|None, "funcao_final": str|None, "forca_ativo": bool,
            "unidades": [int], "ingresso_base": date|None (Bruno #B: ingresso do #A)}
    """
    ev = []

    def emite(tipo, d, payload, atraso_h=0):
        ev.append((tipo, d, payload, atraso_h))

    def intervalo(tipo, chave, fim, dois, d_ev):
        """ADR-008: registro unico fechado, ou par aberto+fechamento (data_carga
        do fechamento vem 6h depois — coalescencia por chave)."""
        if dois:
            emite(tipo, d_ev, dict(chave, data_fim=None))
            emite(tipo, d_ev, dict(chave, data_fim=fim.isoformat()), atraso_h=6)
        else:
            emite(tipo, d_ev, dict(chave, data_fim=fim.isoformat()))

    truncavel = arq.get("truncavel", True)
    forca_ativo = bool(alvo.get("forca_ativo"))
    frac_dois = par["frac_fechamento_dois_registros"]
    unidades = alvo["unidades"]

    # ingresso: posicao no arco (u<1 = carreira EM CURSO — a foto de orgao vivo)
    dur = rint(rng, spec.get("carreira_anos", arq.get("carreira_anos", [15, 25])))
    u = rng.uniform(0.25, 1.15) if truncavel else 1.0
    if forca_ativo and truncavel:
        u = 0.25 + (u - 0.25) * (0.88 - 0.25) / 0.90   # remapeia p/ [0.25,0.88]: EM CURSO
    atraso_anos = rint(rng, spec["inicia_apos_anos"]) if "inicia_apos_anos" in spec else 0
    if atraso_anos and alvo.get("ingresso_base"):
        # 2o vinculo (Bruno): nasce DEPOIS do 1o, mas SEMPRE antes da foto
        ingresso = d28(min(add_meses(alvo["ingresso_base"], atraso_anos * 12),
                           add_meses(data_ref, -18)))
    else:
        ingresso = d28(add_meses(data_ref, -int(dur * 12 * min(u, 1.15))))

    st = {"situacao": "ATIVO", "funcao": None,
          "lotacao": alvo.get("lotacao_final") or rng.choice(unidades),
          "cessoes": [], "afastamentos": [], "fim_folha": None}
    emite("PROVIMENTO", ingresso,
          {"cargo_inicial": alvo.get("cargo") or spec.get("cargo", arq.get("cargo", "Analista")),
           "regime_juridico": "RJU"})

    cursor, encerrado_em, truncou = ingresso, None, False
    ult = ingresso                    # data do ultimo evento emitido (p/ costura)

    def desliga(motivo, dt_):
        nonlocal encerrado_em, ult
        emite("DESLIGAMENTO", dt_,
              {"cod_motivo_deslig": motivo, "data_desligamento": dt_.isoformat()})
        st["situacao"] = regras["motivo_sit"][motivo]
        if st["situacao"] == "DESLIGADO":
            st["fim_folha"] = st["fim_folha"] or dt_
            encerrado_em = encerrado_em or dt_
        ult = max(ult, dt_)

    for m in spec.get("marcos", arq.get("marcos", [])):
        if truncou:
            break
        n_rep = m.get("repeticao", 1)
        if n_rep is None or "rep_range" in m:
            n_rep = rint(rng, m.get("rep_range", [2, 4]))     # contrato: null = aberto
        for _ in range(max(1, n_rep)):
            if m.get("marco") == "fim_carreira":
                cursor = add_meses(ingresso, dur * 12)
            elif m.get("marco") == "fim_carreira_parcial":
                cursor = add_meses(ingresso, int(dur * 12 * 0.75))
            elif m.get("marco") == "nono_ano":
                cursor = add_meses(ingresso, 9 * 12)
            else:
                cursor = add_meses(cursor, rint(rng, m.get("offset_meses", [6, 24])))
            if m.get("apos_fim_cessao") and st["cessoes"]:
                cursor = max(cursor, add_meses(st["cessoes"][-1][1], 1))
            if cursor > data_ref:
                if truncavel:
                    truncou = True; break     # carreira EM CURSO: marco ainda nao veio
                return None                    # plantado exige o arco completo — re-sorteia

            t = m["tipo"]
            if forca_ativo and t in ("DESLIGAMENTO", "CESSAO"):
                continue                       # assento com funcao => ATIVO na foto

            if t == "REMOCAO":
                dest = rng.choice([x for x in unidades if x != st["lotacao"]])
                emite(t, cursor, {"cod_unidade_origem": st["lotacao"],
                                  "cod_unidade_destino": dest})
                st["lotacao"] = dest
                ult = max(ult, cursor)

            elif t == "ALTERACAO_FUNCAO":
                mov = m["movimento"]
                fun = m.get("funcao") if mov == "designacao" else None
                emite(t, cursor, {"cod_funcao": fun, "nome_funcao": fun, "tipo_movimento": mov})
                st["funcao"] = fun
                if m.get("muda_unidade"):
                    st["lotacao"] = rng.choice([x for x in unidades if x != st["lotacao"]])
                ult = max(ult, cursor)

            elif t in ("AFASTAMENTO", "CESSAO"):
                renov = rint(rng, m["renovacoes"]) if "renovacoes" in m else 1
                ini = cursor
                for _r in range(renov):                 # renovacao = N eventos (ADR-008)
                    dm = rint(rng, m.get("duracao_meses", [6, 12]))
                    fim = add_meses(ini, dm)
                    dois = m.get("forca_dois_registros") or rng.random() < frac_dois
                    if t == "AFASTAMENTO":
                        intervalo(t, {"cod_afastamento": m["motivo"],
                                      "data_inicio": ini.isoformat()}, fim, dois, ini)
                        st["afastamentos"].append((ini, fim, m["motivo"]))
                    else:
                        intervalo(t, {"orgao_cessionario": m.get("orgao"),
                                      "data_inicio": ini.isoformat(),
                                      "onus": "com_onus"}, fim, dois, ini)
                        # espelho SIAPE (v0.9: cessao aparece 2x; CEDIDO <=> afast 40)
                        intervalo("AFASTAMENTO", {"cod_afastamento": "40",
                                                  "data_inicio": ini.isoformat()}, fim, dois, ini)
                        st["cessoes"].append((ini, fim, None))
                        st["afastamentos"].append((ini, fim, "40"))
                    ini = fim
                ult = max(ult, cursor)
                cursor = ini if not m.get("durante_cessao") else cursor

            elif t == "RETORNO_VINCULO":
                emite(t, cursor, {"tipo_retorno": m["retorno"]})
                st["situacao"] = "ATIVO"
                ult = max(ult, cursor)

            elif t == "DESLIGAMENTO":
                if m.get("durante_cessao") and st["cessoes"]:
                    cursor = min(cursor, add_meses(st["cessoes"][-1][1], -1))
                desliga(m["motivo"], min(cursor, data_ref))

    # PROGRESSAO por regra (portaria mensal; grade EPPGG; para no teto/DESLIGADO;
    # suspende sob afastamento que NAO conta efetivo exercicio — regra do banco)
    prog = spec.get("progressao", arq.get("progressao", {"modo": "minimo_legal"}))
    limite = encerrado_em or data_ref
    grau, k = 0, 0
    interst = par["intersticio_meses"]
    alvo_rep = prog.get("repeticao")
    dt_ = add_meses(ingresso, interst)
    while dt_ <= limite and grau < len(GRADE) - 1:
        if any(a <= dt_ <= b and c in regras["afast_suspende"]
               for a, b, c in st["afastamentos"]):
            dt_ = add_meses(dt_, interst); continue
        if alvo_rep is not None and prog.get("modo") != "ate_teto" and k >= alvo_rep:
            break
        grau += 1; k += 1
        co, po = GRADE[grau - 1]; cd, pd = GRADE[grau]
        d_pr = date(dt_.year, dt_.month, 1)
        emite("PROGRESSAO", d_pr, {"classe_origem": co, "padrao_origem": po,
                                   "classe_destino": cd, "padrao_destino": pd,
                                   "tipo_progressao": "progressao"})
        ult = max(ult, d_pr)
        dt_ = add_meses(dt_, interst)

    def data_costura(teto):
        """Data p/ evento de costura: depois de tudo que ja aconteceu, antes do teto."""
        base = min(ult, teto)
        folga = (teto - base).days
        if folga <= 2:
            return d28(teto)
        return d28(base + __import__("datetime").timedelta(days=rng.randint(1, folga)))

    # costura FUNCAO: o assento vence (ultima designacao ganha no replay).
    # atraso_h=3: se a data empatar com um marco da historia, a data_carga
    # desempata — a costura e o fato que chega por ULTIMO (mesmo principio do
    # fechamento ADR-008, que usa +6h).
    ffinal = alvo.get("funcao_final")
    if st["situacao"] == "ATIVO":
        if ffinal and st["funcao"] != ffinal:
            d_f = data_costura(data_ref)
            emite("ALTERACAO_FUNCAO", d_f,
                  {"cod_funcao": ffinal, "nome_funcao": ffinal, "tipo_movimento": "designacao"},
                  atraso_h=3)
            st["funcao"] = ffinal
            ult = max(ult, d_f)
        elif not ffinal and st["funcao"]:
            d_f = data_costura(data_ref)
            mov = "dispensa_pedido" if rng.random() < 0.5 else "dispensa_oficio"
            emite("ALTERACAO_FUNCAO", d_f,
                  {"cod_funcao": None, "nome_funcao": None, "tipo_movimento": mov},
                  atraso_h=3)
            st["funcao"] = None
            ult = max(ult, d_f)

    # DISPONIBILIDADE (regra 1991-2000; elegivel: ATIVO, sem funcao, casa antiga,
    # sem cessao/afastamento cobrindo a data_ref)
    pct_disp = par.get("disponibilidade_pct") or 0
    if (pct_disp and st["situacao"] == "ATIVO" and not st["funcao"]
            and ingresso.year <= 1995
            and not any(a <= data_ref <= b for a, b, _ in st["cessoes"])
            and not any(a <= data_ref <= b for a, b, _ in st["afastamentos"])
            and rng.random() < pct_disp):
        ano = rng.randint(max(1991, ingresso.year + 1), 2000)
        ini = date(ano, rng.randint(1, 12), rng.randint(1, 28))
        emite("AFASTAMENTO", ini, {"cod_afastamento": "31",
                                   "data_inicio": ini.isoformat(), "data_fim": None})
        st["afastamentos"].append((ini, date.max, "31"))

    # costura LOTACAO: a historia termina no assento (REMOCAO corretiva se mudou)
    lfinal = alvo.get("lotacao_final")
    if lfinal and st["lotacao"] != lfinal:
        d_r = data_costura(limite)
        emite("REMOCAO", d_r, {"cod_unidade_origem": st["lotacao"],
                               "cod_unidade_destino": lfinal})
        st["lotacao"] = lfinal

    # ── projecao do estado em data_ref (o contrato com a FOTO) ────────────────
    sit = st["situacao"]
    if sit == "ATIVO" and any(a <= data_ref <= b for a, b, _ in st["cessoes"]):
        sit = "CEDIDO"
    af_vig = next((c for a, b, c in sorted(st["afastamentos"], key=lambda x: (x[0], x[1], x[2] or ""))
                   if a <= data_ref <= b), None)
    if sit == "ATIVO" and af_vig and regras["afast_deriva"].get(af_vig) == "DISPONIBILIDADE":
        sit = "DISPONIBILIDADE"
    funcao = st["funcao"] if sit in ("ATIVO", "CEDIDO") else None
    af_vig = af_vig if sit in ("ATIVO", "CEDIDO", "DISPONIBILIDADE") else None
    classe, padrao = GRADE[grau]

    estado = {"situacao_funcional": sit, "classe": classe, "padrao": padrao,
              "funcao_comissionada": funcao, "cod_afastamento_vigente": af_vig,
              "lotacao": st["lotacao"], "ingresso": ingresso}
    folha = {"ingresso": ingresso, "fim_folha": st["fim_folha"],
             "pausas": [(a, b) for a, b, c in st["afastamentos"]
                        if c in regras["afast_pausa"]]}
    return {"eventos": ev, "estado": estado, "folha": folha}
