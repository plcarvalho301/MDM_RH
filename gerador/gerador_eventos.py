#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# =============================================================================
# MDM-RH — GERADOR DE EVENTOS (Reino Animal) — v3 (arquetipo-primeiro)
# Ancoras: trajetorias.py (motor unico) | semente_trajetorias_v1.yaml |
#          gen_massa.py v0.3 | 3_catalogo_eventos_v1.yaml v1.1 | ADR-008/009
# -----------------------------------------------------------------------------
# v3: o gerador NAO tem maquina de estados propria — ele RE-RODA, por vinculo, a
# MESMA trajetoria de arquetipo que o gen_massa estampou (rng identico via
# seed:matricula:traj_salt) e emite os eventos dela. O estado projetado pelo
# motor TEM que bater com a linha do servidor.csv (assert duro); o --valida
# fecha o laco reconstruindo tudo por replay-de-intervalo (ADR-008).
#
# Fluxo: gen_massa (foto+arquetipo) -> ESTE (eventos) -> loaders -> replay = foto.
#
# CARGAS (ADR-009 exercitada desde o nascimento):
#   carga_base  = trajetorias | carga_folha = FECHAMENTO_FOLHA (volume)
#   carga_lixo  = fixture de RETRATACAO OPERACIONAL (30 duplicatas, --sem-lixo desliga)
#
# Uso: python gerador_eventos.py [--foto gerador/out/servidor.csv] [--out gerador/out] --valida
# =============================================================================
import argparse, csv, json, os, random, sys, uuid
from datetime import date, datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import trajetorias as traj
from trajetorias import add_meses

import yaml


# ── Emissao ──────────────────────────────────────────────────────────────────
class Emissor:
    """Acumula eventos por carga; carimba data_carga com deslocamento controlavel
    (o desempate da coalescencia ADR-008 e data_carga — o fechamento vem DEPOIS)."""
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


# ── Folha mensal (carga propria — destacavel, ADR-009) ───────────────────────
def gera_folha(rng, em, mat, cpf, fol, data_ref):
    n = 0
    d = date(fol["ingresso"].year, fol["ingresso"].month, 1)
    fim = fol["fim_folha"] or data_ref          # DESLIGADO para; INATIVO segue (proventos)
    while d <= fim:
        if not any(p0 <= d <= p1 for p0, p1 in fol["pausas"]):
            comp = f"{d.year}{d.month:02d}"
            em.emite("carga_folha", mat, cpf, "FECHAMENTO_FOLHA", add_meses(d, 1),
                     {"mes_competencia": comp, "mes_pagamento": comp, "tipo_fechamento": "normal",
                      "rubricas": [{"cod_rubrica": 1, "nome_rubrica": "VENCIMENTO BASICO",
                                    "valor_rubrica": round(rng.uniform(8000, 24000), 2),
                                    "indicador_rd": "R", "numero_seq": 1}]})
            n += 1
        d = add_meses(d, 1)
    return n


# ── Replay de validacao (ADR-008; reconstroi TUDO so dos eventos) ────────────
def replay(eventos, data_ref, regras):
    evs = sorted(eventos, key=lambda e: (e["data_evento"], e["data_carga"], e["id_evento"]))
    sit = None
    aberto = {}                       # (tipo, data_inicio) -> payload (coalescencia)
    funcao = None
    grau = 0
    for e in evs:
        t = e["cod_tipo_evento"]
        pl = json.loads(e["payload"])
        if t == "PROVIMENTO":
            sit = "ATIVO"
        elif t == "DESLIGAMENTO":
            sit = regras["motivo_sit"][pl["cod_motivo_deslig"]]
        elif t == "RETORNO_VINCULO":
            sit = "ATIVO"
        elif t in ("CESSAO", "AFASTAMENTO"):
            aberto[(t, pl["data_inicio"])] = pl
        elif t == "ALTERACAO_FUNCAO":
            funcao = pl.get("cod_funcao") if pl.get("tipo_movimento") == "designacao" else None
        elif t == "PROGRESSAO":
            alvo = (pl.get("classe_destino"), pl.get("padrao_destino"))
            if alvo in traj.GRADE:
                grau = traj.GRADE.index(alvo)

    ic = {"CESSAO": [], "AFASTAMENTO": []}
    for (t, ini), pl in aberto.items():
        fim = pl.get("data_fim")
        ic[t].append((date.fromisoformat(ini),
                      date.fromisoformat(fim) if fim else date.max,
                      pl.get("cod_afastamento")))
    cedido = any(a <= data_ref <= b for a, b, _ in ic["CESSAO"])
    af_vig = next((c for a, b, c in sorted(ic["AFASTAMENTO"], key=lambda x: (x[0], x[1], x[2] or ""))
                   if a <= data_ref <= b), None)
    if sit == "ATIVO":
        if cedido:
            sit = "CEDIDO"
        elif af_vig and regras["afast_deriva"].get(af_vig) == "DISPONIBILIDADE":
            sit = "DISPONIBILIDADE"
    if sit not in ("ATIVO", "CEDIDO"):
        funcao = None
    if sit not in ("ATIVO", "CEDIDO", "DISPONIBILIDADE"):
        af_vig = None
    classe, padrao = traj.GRADE[grau]
    return {"situacao_funcional": sit, "cod_afastamento_vigente": af_vig,
            "funcao_comissionada": funcao, "classe": classe, "padrao": padrao}


# ── Main ─────────────────────────────────────────────────────────────────────
CAMPOS = ["situacao_funcional", "cod_afastamento_vigente", "funcao_comissionada",
          "classe", "padrao"]


def main():
    aqui = os.path.dirname(os.path.abspath(__file__))
    ap = argparse.ArgumentParser(description="Gerador de eventos v3 (arquetipo-primeiro)")
    ap.add_argument("--foto", default=os.path.join(aqui, "out", "servidor.csv"))
    ap.add_argument("--config", default=os.path.join(aqui, "config.yaml"))
    ap.add_argument("--semente", default=os.path.join(aqui, "semente_trajetorias_v1.yaml"))
    ap.add_argument("--out", default=os.path.join(aqui, "out"))
    ap.add_argument("--sem-folha", action="store_true")
    ap.add_argument("--sem-lixo", action="store_true")
    ap.add_argument("--valida", action="store_true")
    a = ap.parse_args()

    os.makedirs(a.out, exist_ok=True)
    cfg = yaml.safe_load(open(a.config, encoding="utf-8"))
    seed = cfg["seed"]
    semente = traj.carrega_semente(a.semente)
    regras = traj.carrega_regras()
    par = {**semente["parametros_default"],
           "disponibilidade_pct": cfg.get("disponibilidade_pct", 0)}

    with open(a.foto, encoding="utf-8", newline="") as f:
        foto = list(csv.DictReader(f))
    if not foto or "arquetipo" not in foto[0]:
        sys.exit(f"FOTO sem coluna arquetipo: {a.foto} — rode gen_massa v0.3 antes.")
    data_ref = date.fromisoformat(foto[0]["data_referencia"])

    # ingresso do vinculo #A por cpf (o #B do Bruno nasce depois dele)
    ingresso_a = {r["cpf"]: date.fromisoformat(r["data_exercicio_no_orgao"])
                  for r in foto if r["arquetipo"].endswith("#A")}

    em = Emissor(random.Random(seed))
    for rot in ("carga_base", "carga_folha", "carga_lixo"):
        em.carga(rot)

    folhas, divergencias = [], 0
    for row in foto:
        mat, cpf, rotulo = row["matricula_funcional"], row["cpf"], row["arquetipo"]
        arq, spec = traj.resolve(semente, rotulo)
        alvo = {"lotacao_final": int(row["cod_unidade_lotacao"]),
                "funcao_final": row["funcao_comissionada"] or None,
                "forca_ativo": bool(row["funcao_comissionada"]),
                "cargo": row["cargo"], "unidades": traj.UNIVERSO_UNIDADES,
                "ingresso_base": ingresso_a.get(cpf) if rotulo.endswith("#B") else None}
        rv = traj.rng_vinculo(seed, mat, int(row.get("traj_salt") or 0))
        tr = traj.gera_trajetoria(rv, arq, spec, data_ref, regras, par, alvo)
        if tr is None:
            sys.exit(f"trajetoria nao reproduziu (mat {mat}, {rotulo}) — foto e eventos dessincronizados?")
        # o estado do motor TEM que ser o estado da foto (mesmo rng => mesma vida)
        est = tr["estado"]
        for c in CAMPOS:
            esperado = row[c] or None
            obtido = est[c]
            if obtido != esperado:
                divergencias += 1
                if divergencias <= 8:
                    print(f"  DESSINCRONIA {mat} ({rotulo}) [{c}]: motor={obtido!r} foto={esperado!r}")
        for tipo, d, pl, atr in tr["eventos"]:
            em.emite("carga_base", mat, cpf, tipo, d, pl, atraso_h=atr)
        folhas.append((mat, cpf, tr["folha"]))
    if divergencias:
        sys.exit(f"[FALHA] {divergencias} dessincronias motor x foto — nada foi escrito.")

    n_folha = 0
    if not a.sem_folha:
        rng_f = random.Random(f"{seed}:folha")
        for mat, cpf, fol in folhas:
            n_folha += gera_folha(rng_f, em, mat, cpf, fol, data_ref)

    # Carga-lixo: fixture de RETRATACAO OPERACIONAL (defeito material deliberado)
    if not a.sem_lixo:
        rng_l = random.Random(f"{seed}:lixo")
        amostra = rng_l.sample(em.cargas["carga_base"]["linhas"], k=min(30, len(foto)))
        for l in amostra:
            pl = json.loads(l[6])
            if "data_desligamento" in pl:
                pl["data_desligamento"] = "1900-01-01"     # bem-formado, errado
            em.emite("carga_lixo", l[2], l[3], l[4], date.fromisoformat(l[5]), pl,
                     atraso_h=48, fonte="CARGA_APOSENTADOS_DEFEITUOSA", grau="medio")

    # Validacao: replay-de-intervalo (SO dos eventos) vs FOTO — o juiz final
    if a.valida:
        por_mat = {}
        for l in em.cargas["carga_base"]["linhas"]:
            por_mat.setdefault(l[2], []).append(dict(zip(Emissor.COLS, l)))
        div = 0
        for row in foto:
            r = replay(por_mat[row["matricula_funcional"]], data_ref, regras)
            for c in CAMPOS:
                if r[c] != (row[c] or None):
                    div += 1
                    if div <= 8:
                        print(f"  DIVERGE {row['matricula_funcional']} ({row['arquetipo']}) "
                              f"[{c}]: replay={r[c]!r} foto={row[c] or None!r}")
        print(f"[valida] replay-de-intervalo vs FOTO canonica: {len(foto)} vinculos, {div} divergencias")
        if div:
            sys.exit(1)

    # Escrita (formato = envelope; schema v0.11)
    manif = {}
    for rot, c in em.cargas.items():
        if not c["linhas"]:
            continue
        fn = os.path.join(a.out, f"eventos_{rot}.csv")
        with open(fn, "w", newline="", encoding="utf-8") as fh:
            w = csv.writer(fh); w.writerow(Emissor.COLS); w.writerows(c["linhas"])
        manif[rot] = {"id_carga": c["id_carga"], "eventos": len(c["linhas"]),
                      "arquivo": os.path.basename(fn)}
    json.dump({"seed": seed, "n_vinculos": len(foto), "data_base": data_ref.isoformat(),
               "cargas": manif}, open(os.path.join(a.out, "cargas.json"), "w"),
              indent=2, ensure_ascii=False)
    with open(os.path.join(a.out, "load_eventos.sql"), "w", encoding="utf-8") as fh:
        fh.write("-- carga da massa (schema v0.11): abre particao POR carga, depois COPY\n")
        fh.write("\\set ON_ERROR_STOP on\n")
        for rot, m in manif.items():
            fh.write(f"SELECT fn_particao_carga('{m['id_carga']}');\n")
            fh.write(f"\\copy evento ({','.join(Emissor.COLS)}) FROM '{m['arquivo']}' CSV HEADER\n")
        fh.write("-- depois: REFRESH MATERIALIZED VIEW CONCURRENTLY mv_filme_servidor; etc.\n")

    print(f"[ok] vinculos={len(foto)} eventos_base={manif.get('carga_base',{}).get('eventos',0)} "
          f"folha={n_folha} lixo={manif.get('carga_lixo',{}).get('eventos',0)} data_ref={data_ref}")


if __name__ == "__main__":
    main()
