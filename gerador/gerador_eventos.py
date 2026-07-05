#!/usr/bin/env python3
# =============================================================================
# MDM-RH — GERADOR DE EVENTOS (massa Reino Animal) — v1
# Data: 2026-07-05
# Âncoras: semente_trajetorias_v1.yaml | 3_catalogo_eventos_v1.yaml (v1.1)
#          3_schema_mdm.sql (v0.8) | ADR-008 | ADR-009 | 3_massa_reino_animal_v0_3.md
#
# ARQUITETURA (trajetória-primeiro): a máquina de estados anda PRA FRENTE gerando
# eventos; a FOTO é o ESTADO FINAL PROJETADO na data_base — nunca gerada à parte.
# --valida re-reproduz cada vínculo com a lógica de INTERVALO (ADR-008) e compara
# com a FOTO projetada: é o mini-smoke da premissa de replay embutido no gerador.
#
# SAÍDAS (--out DIR), prontas para COPY (schema v0.8):
#   eventos_<carga>.csv     colunas = envelope do evento (id_carga incluso)
#   foto_projetada.csv      estado final por vínculo (subconjunto da FOTO)
#   cargas.json             id_carga → {rotulo, contagem} (insumo do fn_particao_carga)
#   load_eventos.sql        abre partições + \copy por carga
# CARGAS (ADR-009 exercitada desde o nascimento):
#   carga_base  = eventos de trajetória      carga_folha = FECHAMENTO_FOLHA
#   carga_lixo  = fixture de RETRATAÇÃO OPERACIONAL (duplicatas/erro material
#                 deliberados; --sem-lixo desliga). NÃO confundir com reversão
#                 de domínio (Gerson/Vicente), que é evento legítimo na base.
#
# LIMITES DECLARADOS (v1; próximo incremento = gerador de DESVIOS/bifurcações):
#   - Não reconcilia o quadro de 226 chefias (massa §4): funções vêm do arquétipo.
#   - Lotações sorteadas nas 43 unidades; órfão estrutural (KR 2.1) segue com a
#     massa FOTO/loader, não daqui.
#   - Rubricas de folha mínimas (1 rubrica sintética) — volume é o teste, não o shape.
# =============================================================================
import argparse, csv, hashlib, json, os, random, sys, uuid
from datetime import date, datetime, timedelta, timezone

import yaml

# ── Constantes de domínio (schema v0.8 / seed v0.2 / massa v0.3) ─────────────
GRADE = [(c, p) for c in ["A", "B", "C", "ESPECIAL"] for p in ["I", "II", "III", "IV", "V"]]
MOTIVO_DESLIG = {  # cod → situacao_resultante (dom_motivo_deslig)
    "07": "DESLIGADO", "08": "DESLIGADO", "09": "DESLIGADO", "25": "DESLIGADO",
    "38": "INATIVO", "39": "INATIVO",
    "DEMI_OFICIO": "DESLIGADO", "CASS_APOSENT": "DESLIGADO", "ANUL_PROVIMENTO": "DESLIGADO",
}
AFAST_PAUSA_FOLHA = {"05"}          # LSV: sem remuneração → folha pausa
AFAST_SUSPENDE_PROGRESSAO = {"05"}  # conta_efetivo_exercicio = nao
UNIDADES = list(range(100001, 100044))          # massa §2: 43 unidades, 100001–100043
NOMES = ["Marina", "Aluízio", "Tereza", "Ubirajara", "Cléa", "Firmino", "Zilda", "Otávio",
         "Iara", "Nelson", "Dora", "Ismael", "Rute", "Valdir", "Neide", "Plínio", "Sônia",
         "Edgar", "Lúcia", "Ramiro", "Cátia", "Josué", "Vânia", "Heraldo", "Selma", "Túlio"]
BICHOS = ["Lobato-Cerva", "Tuiuiú", "Jaguatirica", "Ariranha", "Tamanduá", "Seriema",
          "Cutia", "Boto-Rosa", "Urutau", "Guará", "Paca", "Mutum", "Irara", "Sagui",
          "Curió", "Anta", "Quero-Quero", "Teiú", "Graxaim", "Sabiá", "Capivara", "Arara"]


def cpf_valido(rng):
    d = [rng.randrange(10) for _ in range(9)]
    for n in (10, 11):
        s = sum(v * w for v, w in zip(d, range(n, 1, -1)))
        d.append((s * 10 % 11) % 10)
    return "".join(map(str, d))


def add_meses(d, m):
    y, mo = d.year + (d.month - 1 + m) // 12, (d.month - 1 + m) % 12 + 1
    from calendar import monthrange
    return date(y, mo, min(d.day, monthrange(y, mo)[1]))


def rint(rng, par):  # [min,max] → int
    return rng.randint(par[0], par[1])


# ── Emissão ──────────────────────────────────────────────────────────────────
class Emissor:
    """Acumula eventos por carga; carimba data_carga com deslocamento controlável
    (o desempate da coalescência ADR-008 é data_carga — o fechamento vem DEPOIS)."""
    COLS = ["id_evento", "id_carga", "matricula_funcional", "cpf", "cod_tipo_evento",
            "data_evento", "payload", "cod_mecanica", "fonte", "grau_confianca", "data_carga"]

    def __init__(self, rng):
        self.rng, self.cargas = rng, {}
        self.t0 = datetime(2026, 7, 5, 3, 0, tzinfo=timezone.utc)

    def carga(self, rotulo):
        cid = str(uuid.UUID(int=self.rng.getrandbits(128), version=4))
        self.cargas[rotulo] = {"id_carga": cid, "linhas": []}
        return cid

    def emite(self, rotulo, mat, cpf, tipo, data_ev, payload, atraso_h=0,
              fonte="GERADOR_REINO_ANIMAL", grau="alto"):
        c = self.cargas[rotulo]
        c["linhas"].append([str(uuid.UUID(int=self.rng.getrandbits(128), version=4)),
                            c["id_carga"], mat, cpf, tipo, data_ev.isoformat(),
                            json.dumps(payload, ensure_ascii=False), "extracao",
                            fonte, grau,
                            (self.t0 + timedelta(hours=atraso_h)).isoformat()])


# ── Trajetória de UM vínculo ─────────────────────────────────────────────────
def gera_vinculo(rng, em, arq, spec, mat, cpf, nome, data_base):
    """Anda a máquina de estados pra frente. Retorna a FOTO projetada + intervalos
    (p/ folha e validação)."""
    dur = rint(rng, spec.get("carreira_anos", arq.get("carreira_anos", [15, 25])))
    atraso_ing = rint(rng, spec.get("inicia_apos_anos", [0, 0])) * 12
    # Camada A e TRUNCAVEL: a carreira pode estar EM CURSO (u<1) — marcos alem de
    # data_base simplesmente ainda nao aconteceram. Camada B (plantados) exige o
    # arco completo (u=1): o caso-limite so existe se a historia termina.
    u = rng.uniform(0.25, 1.15) if arq.get("truncavel", True) else 1.0
    ingresso = add_meses(add_meses(data_base, -int(dur * 12 * min(u, 1.15))), atraso_ing)
    ingresso = date(ingresso.year, ingresso.month, min(ingresso.day, 28))

    cursor = ingresso
    lot = rng.choice(UNIDADES)
    st = {"situacao": "ATIVO", "funcao": None, "lotacao": lot, "classe": "A", "padrao": "I",
          "cessoes": [], "afastamentos": [], "fim_folha": None, "grau": 0}
    em.emite(arq["rotulo_carga"], mat, cpf, "PROVIMENTO", ingresso,
             {"cargo_inicial": spec.get("cargo", arq.get("cargo", "Analista")),
              "regime_juridico": "RJU"})

    encerrado_em = None
    truncou = False

    def desliga(motivo, dt):
        nonlocal encerrado_em
        em.emite(arq["rotulo_carga"], mat, cpf, "DESLIGAMENTO", dt,
                 {"cod_motivo_deslig": motivo, "data_desligamento": dt.isoformat()})
        st["situacao"] = MOTIVO_DESLIG[motivo]
        if st["situacao"] == "DESLIGADO":
            st["fim_folha"] = dt          # DESLIGADO para a folha; INATIVO segue (proventos)
        encerrado_em = dt if st["situacao"] == "DESLIGADO" else encerrado_em

    for m in spec.get("marcos", arq.get("marcos", [])):
        if truncou:
            break
        n_rep = m.get("repeticao", 1)
        if n_rep is None or "rep_range" in m:
            n_rep = rint(rng, m.get("rep_range", [2, 4]))          # contrato: null = aberto
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
            if cursor > data_base:
                if arq.get("truncavel", True):
                    truncou = True; break   # carreira EM CURSO: marco ainda nao aconteceu
                return None                  # plantado completa o arco — re-sorteia

            t = m["tipo"]

            if t == "REMOCAO":
                dest = rng.choice([u for u in UNIDADES if u != st["lotacao"]])
                em.emite(arq["rotulo_carga"], mat, cpf, t, cursor,
                         {"cod_unidade_origem": st["lotacao"], "cod_unidade_destino": dest})
                st["lotacao"] = dest

            elif t == "ALTERACAO_FUNCAO":
                mov = m["movimento"]
                fun = m.get("funcao") if mov == "designacao" else None
                em.emite(arq["rotulo_carga"], mat, cpf, t, cursor,
                         {"cod_funcao": fun, "nome_funcao": fun, "tipo_movimento": mov})
                st["funcao"] = fun
                if m.get("muda_unidade"):
                    st["lotacao"] = rng.choice([u for u in UNIDADES if u != st["lotacao"]])

            elif t in ("AFASTAMENTO", "CESSAO"):
                renov = rint(rng, m["renovacoes"]) if "renovacoes" in m else 1
                ini = cursor
                for _r in range(renov):                      # renovação = N eventos (ADR-008)
                    dm = rint(rng, m.get("duracao_meses", [6, 12]))
                    fim = add_meses(ini, dm)
                    if t == "AFASTAMENTO":
                        chave = {"cod_afastamento": m["motivo"], "data_inicio": ini.isoformat()}
                        pl_fechado = dict(chave, data_fim=fim.isoformat())
                    else:
                        chave = {"orgao_cessionario": m.get("orgao"), "data_inicio": ini.isoformat(),
                                 "onus": "com_onus"}
                        pl_fechado = dict(chave, data_fim=fim.isoformat())
                    dois = m.get("forca_dois_registros") or rng.random() < arq["frac_dois"]
                    if dois:                                  # par aberto+fechamento → coalescência
                        em.emite(arq["rotulo_carga"], mat, cpf, t, ini, dict(chave, data_fim=None))
                        em.emite(arq["rotulo_carga"], mat, cpf, t, ini, pl_fechado, atraso_h=6)
                    else:
                        em.emite(arq["rotulo_carga"], mat, cpf, t, ini, pl_fechado)
                    (st["afastamentos"] if t == "AFASTAMENTO" else st["cessoes"]).append(
                        (ini, fim, m.get("motivo")))
                    ini = fim
                cursor = ini if not m.get("durante_cessao") else cursor
                if t == "CESSAO" and m.get("durante_cessao") is None:
                    pass  # situação CEDIDO é derivada por intervalo no replay

            elif t == "RETORNO_VINCULO":
                em.emite(arq["rotulo_carga"], mat, cpf, t, cursor, {"tipo_retorno": m["retorno"]})
                st["situacao"] = "ATIVO"

            elif t == "DESLIGAMENTO":
                if m.get("durante_cessao") and st["cessoes"]:
                    cursor = min(cursor, add_meses(st["cessoes"][-1][1], -1))
                desliga(m["motivo"], min(cursor, data_base))

    # PROGRESSAO por regra (portaria mensal; grade EPPGG; para no teto/desligamento)
    prog = spec.get("progressao", arq.get("progressao", {"modo": "minimo_legal"}))
    limite = encerrado_em or data_base
    k, grau = 0, 0
    interst = arq["intersticio"]
    alvo = prog.get("repeticao")
    dt = add_meses(ingresso, interst)
    while dt <= limite and grau < len(GRADE) - 1:
        if any(a[0] <= dt <= a[1] and a[2] in AFAST_SUSPENDE_PROGRESSAO
               for a in st["afastamentos"]):
            dt = add_meses(dt, interst); continue
        if alvo is not None and prog["modo"] != "ate_teto" and k >= alvo:
            break
        grau += 1; k += 1
        co, po = GRADE[grau - 1]; cd, pd = GRADE[grau]
        em.emite(arq["rotulo_carga"], mat, cpf, "PROGRESSAO", date(dt.year, dt.month, 1),
                 {"classe_origem": co, "padrao_origem": po,
                  "classe_destino": cd, "padrao_destino": pd, "tipo_progressao": "progressao"})
        dt = add_meses(dt, interst)
    st["classe"], st["padrao"] = GRADE[grau]

    # FOTO projetada em data_base (intervalos resolvidos)
    sit = st["situacao"]
    if sit == "ATIVO" and any(c[0] <= data_base <= c[1] for c in st["cessoes"]):
        sit = "CEDIDO"
    af_vig = next((a[2] for a in st["afastamentos"] if a[0] <= data_base <= a[1]), None)
    foto = {"matricula_funcional": mat, "cpf": cpf, "nome": nome,
            "cargo": spec.get("cargo", arq.get("cargo", "Analista")),
            "classe": st["classe"], "padrao": st["padrao"],
            "funcao_comissionada": st["funcao"] if sit in ("ATIVO", "CEDIDO") else None,
            "cod_unidade_lotacao": st["lotacao"], "situacao_funcional": sit,
            "cod_afastamento_vigente": af_vig if sit in ("ATIVO", "CEDIDO") else None,
            "data_referencia": data_base.isoformat(), "arquetipo": arq["nome"]}
    folha = {"ingresso": ingresso, "fim_folha": st["fim_folha"],
             "pausas": [(a[0], a[1]) for a in st["afastamentos"] if a[2] in AFAST_PAUSA_FOLHA]}
    return foto, folha


# ── Folha mensal (carga própria) ─────────────────────────────────────────────
def gera_folha(rng, em, mat, cpf, folha, data_base):
    n = 0
    d = date(folha["ingresso"].year, folha["ingresso"].month, 1)
    fim = folha["fim_folha"] or data_base
    while d <= fim:
        if not any(p0 <= d <= p1 for p0, p1 in folha["pausas"]):
            comp = f"{d.year}{d.month:02d}"
            em.emite("carga_folha", mat, cpf, "FECHAMENTO_FOLHA", add_meses(d, 1),
                     {"mes_competencia": comp, "mes_pagamento": comp, "tipo_fechamento": "normal",
                      "rubricas": [{"cod_rubrica": 1, "nome_rubrica": "VENCIMENTO BASICO",
                                    "valor_rubrica": round(rng.uniform(8000, 24000), 2),
                                    "indicador_rd": "R", "numero_seq": 1}]})
            n += 1
        d = add_meses(d, 1)
    return n


# ── Replay de validação (a premissa ADR-008, provada aqui mesmo) ─────────────
def replay(eventos, data_base):
    """Reconstrói situação em data_base pela lógica de INTERVALO + coalescência."""
    evs = sorted(eventos, key=lambda e: (e["data_evento"], e["data_carga"]))
    sit, intervalos = None, {"CESSAO": [], "AFASTAMENTO": []}
    aberto = {}
    for e in evs:
        t, pl = e["cod_tipo_evento"], json.loads(e["payload"])
        if t == "PROVIMENTO":
            sit = "ATIVO"
        elif t == "DESLIGAMENTO":
            sit = MOTIVO_DESLIG[pl["cod_motivo_deslig"]]
        elif t == "RETORNO_VINCULO":
            sit = "ATIVO"
        elif t in ("CESSAO", "AFASTAMENTO"):
            k = (t, pl["data_inicio"])                       # coalescência: mais recente vence
            aberto[k] = pl
    for (t, ini), pl in aberto.items():
        fim = pl.get("data_fim")
        intervalos[t].append((date.fromisoformat(ini),
                              date.fromisoformat(fim) if fim else date.max))
    if sit == "ATIVO" and any(a <= data_base <= b for a, b in intervalos["CESSAO"]):
        sit = "CEDIDO"
    return sit


# ── Main ─────────────────────────────────────────────────────────────────────
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--semente",
                    default=os.path.join(os.path.dirname(__file__), "semente_trajetorias_v1.yaml"))
    ap.add_argument("--n-vinculos", type=int, default=1300)
    ap.add_argument("--seed", type=int, required=True)
    ap.add_argument("--out", default="saida")
    ap.add_argument("--sem-folha", action="store_true")
    ap.add_argument("--sem-lixo", action="store_true")
    ap.add_argument("--valida", action="store_true")
    a = ap.parse_args()

    os.makedirs(a.out, exist_ok=True)
    rng = random.Random(a.seed)
    cfg = yaml.safe_load(open(a.semente))
    par = cfg["parametros_default"]
    data_base = par["data_base"] if isinstance(par["data_base"], date) else date.fromisoformat(str(par["data_base"]))

    em = Emissor(rng)
    for rot in ("carga_base", "carga_folha", "carga_lixo"):
        em.carga(rot)

    # Volumetria: pesos da Camada A incidem sobre PESSOAS; Bruno adiciona vínculo extra.
    fixos_B = sum(b["contagem"] for b in cfg["camada_B"])
    pessoas_A = round((a.n_vinculos - fixos_B) / (1 + cfg["camada_A"][ [x["id"] for x in cfg["camada_A"]].index(6) ]["peso"] * 1))
    # (aprox: só Bruno tem 2º vínculo; pessoas ≈ alvo/(1+peso_bruno))
    pesos = [x["peso"] for x in cfg["camada_A"]]
    tot = sum(pesos); pesos = [p / tot for p in pesos]

    matr_seq = iter(range(1000001, 9999999))
    fotos, folhas, todos_ev_idx = [], [], {}

    def um(arq_def, forcar_nome=None):
        base = {"nome": arq_def["nome"], "rotulo_carga": "carga_base",
                "intersticio": par["intersticio_meses"],
                "frac_dois": par["frac_fechamento_dois_registros"], **arq_def}
        specs = arq_def.get("vinculos") or [arq_def]
        cpf = cpf_valido(rng)
        nome = forcar_nome or f"{rng.choice(NOMES)} {rng.choice(BICHOS)}"
        feitos = []
        for spec in specs:
            for _tent in range(8):
                mat = f"{next(matr_seq):07d}"
                marca = len(em.cargas["carga_base"]["linhas"])
                r = gera_vinculo(rng, em, base, spec, mat, cpf, nome, data_base)
                if r:
                    feitos.append((mat, cpf, *r)); break
                del em.cargas["carga_base"]["linhas"][marca:]   # não coube: descarta e re-sorteia
        return feitos

    # Camada B primeiro (contagem fixa, por cima)
    for b in cfg["camada_B"]:
        b["truncavel"] = False
        for _ in range(b["contagem"]):
            for mat, cpf, foto, fol in um(b, forcar_nome=(b.get("fixo") or {}).get("nome_completo")):
                if b.get("fixo"):
                    foto["funcao_comissionada"] = b["fixo"]["funcao"]
                fotos.append(foto); folhas.append((mat, cpf, fol))

    # Camada A até bater o alvo de vínculos
    while len(fotos) < a.n_vinculos:
        arq = rng.choices(cfg["camada_A"], weights=pesos, k=1)[0]
        for mat, cpf, foto, fol in um(arq):
            fotos.append(foto); folhas.append((mat, cpf, fol))

    # Folha (carga própria — destacável de propósito, ADR-009)
    n_folha = 0
    if not a.sem_folha:
        for mat, cpf, fol in folhas:
            n_folha += gera_folha(rng, em, mat, cpf, fol, data_base)

    # Carga-lixo: fixture de RETRATAÇÃO OPERACIONAL (defeito de dado deliberado).
    if not a.sem_lixo:
        amostra = rng.sample(em.cargas["carga_base"]["linhas"], k=min(30, len(fotos)))
        for l in amostra:
            pl = json.loads(l[6])
            if "data_desligamento" in pl:
                pl["data_desligamento"] = "1900-01-01"        # erro material: bem-formado, errado
            em.emite("carga_lixo", l[2], l[3], l[4], date.fromisoformat(l[5]), pl,
                     atraso_h=48, fonte="CARGA_APOSENTADOS_DEFEITUOSA", grau="medio")

    # Validação: replay-de-intervalo vs FOTO projetada (só carga_base conta)
    if a.valida:
        por_mat = {}
        for l in em.cargas["carga_base"]["linhas"]:
            por_mat.setdefault(l[2], []).append(
                dict(zip(Emissor.COLS, l)))
        div = 0
        for f in fotos:
            r = replay(por_mat[f["matricula_funcional"]], data_base)
            if r != f["situacao_funcional"]:
                div += 1
                if div <= 5:
                    print(f"  DIVERGE {f['matricula_funcional']} ({f['arquetipo']}): replay={r} foto={f['situacao_funcional']}")
        print(f"[valida] replay-de-intervalo vs FOTO projetada: {len(fotos)} vinculos, {div} divergencias")
        if div:
            sys.exit(1)

    # Escrita
    manif = {}
    for rot, c in em.cargas.items():
        if not c["linhas"]:
            continue
        fn = f"{a.out}/eventos_{rot}.csv"
        with open(fn, "w", newline="") as fh:
            w = csv.writer(fh); w.writerow(Emissor.COLS); w.writerows(c["linhas"])
        manif[rot] = {"id_carga": c["id_carga"], "eventos": len(c["linhas"]), "arquivo": fn}
    with open(f"{a.out}/foto_projetada.csv", "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(fotos[0].keys())); w.writeheader(); w.writerows(fotos)
    json.dump({"seed": a.seed, "n_vinculos": len(fotos), "data_base": data_base.isoformat(),
               "cargas": manif}, open(f"{a.out}/cargas.json", "w"), indent=2, ensure_ascii=False)
    with open(f"{a.out}/load_eventos.sql", "w") as fh:
        fh.write("-- carga da massa (schema v0.8): abre particao POR carga, depois COPY\n\\set ON_ERROR_STOP on\n")
        for rot, m in manif.items():
            fh.write(f"SELECT fn_particao_carga('{m['id_carga']}');\n")
            fh.write(f"\\copy evento ({','.join(Emissor.COLS)}) FROM '{m['arquivo'].split('/')[-1]}' CSV HEADER\n")
        fh.write("-- depois: REFRESH MATERIALIZED VIEW CONCURRENTLY mv_filme_servidor; etc.\n")

    arq_ct = {}
    for f in fotos:
        arq_ct[f["arquetipo"]] = arq_ct.get(f["arquetipo"], 0) + 1
    print(f"[ok] vinculos={len(fotos)} pessoas~={len({f['cpf'] for f in fotos})} "
          f"eventos_base={manif.get('carga_base',{}).get('eventos',0)} folha={n_folha} "
          f"lixo={manif.get('carga_lixo',{}).get('eventos',0)}")
    for k in sorted(arq_ct, key=arq_ct.get, reverse=True):
        print(f"   {k:26s} {arq_ct[k]:5d}")


if __name__ == "__main__":
    main()
