#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# =============================================================================
# MDM-RH — GERADOR DE EVENTOS (Reino Animal) — v3 (arquetipo-primeiro)
# Ancoras: trajetorias.py (motor unico) | semente_trajetorias_v1.yaml |
#          gen_massa.py v0.3 | 3_catalogo_eventos_v1.yaml v1.2 | ADR-008/009/011
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
#   carga_pss   = CONTRIBUICAO_PSS (2a fonte da Calculadora, 4.22; --sem-pss desliga)
#   carga_lixo  = fixture de RETRATACAO OPERACIONAL (30 duplicatas, --sem-lixo desliga)
#
# Uso (a partir da raiz do repo): python -m geradores.gerador_eventos [--foto geradores/out/servidor.csv] [--out geradores/out] --valida
# =============================================================================
import argparse, csv, json, os, random, sys, uuid
from datetime import date, datetime, timedelta, timezone

from geradores import trajetorias as traj
from geradores.trajetorias import add_meses
from pipeline.contrato import siape_envelope as siape
from geradores import emissor_siape as emissor

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


# ── PSS mensal (carga propria — destacavel, ADR-009; espelha 4.22) ───────────
def gera_pss(rng, em, mat, cpf, fol, data_ref):
    """CONTRIBUICAO_PSS: uma por mes de vida funcional, do provimento a competencia
    atual — SEM piso temporal (fonte SIAPE, nao eSocial; handoff B.2.1). Pula os
    MESMOS meses sem remuneracao que a folha (pausas): sem folha => sem contribuicao.
    pss_apurado e int (aliquota RPPS 11% da base, arredondado); os arrays datados do
    4.22 (ferias/lpa/afastamentos/reclusao) ficam de fora da massa base — insumo de
    dias-liquidos, nao numero apurado (catalogo v1.2)."""
    n = 0
    d = date(fol["ingresso"].year, fol["ingresso"].month, 1)
    fim = fol["fim_folha"] or data_ref          # DESLIGADO para; INATIVO segue (proventos)
    while d <= fim:
        if not any(p0 <= d <= p1 for p0, p1 in fol["pausas"]):
            base = round(rng.uniform(8000, 24000), 2)
            apurado = int(round(base * 0.11))    # int: o payload/MV tipam pss_apurado como int
            em.emite("carga_pss", mat, cpf, "CONTRIBUICAO_PSS", add_meses(d, 1),
                     {"gr_matricula": int(mat),
                      "ano_contribuicao": d.year, "mes_contribuicao": d.month,
                      "indice_reajuste": 1,
                      "pss_apurado": apurado, "pss_informado": apurado,
                      "remuneracao_pss": base, "remuneracao_pss_ajustada": base})
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
    ap.add_argument("--sem-pss", action="store_true")
    ap.add_argument("--sem-lixo", action="store_true")
    ap.add_argument("--valida", action="store_true")
    ap.add_argument("--formato", choices=("loader", "siape"), default="loader",
                    help="loader=CSV interno+load_eventos.sql (default); siape=envelope SOAP das APIs SIAPE (Card 3)")
    ap.add_argument("--injeta-defeito", choices=siape.DEFEITOS, default=None,
                    help="corrompe UMA ocorrencia do envelope (so --formato siape) — prova degradacao graciosa do conector (ADR-009)")
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

    # Carga-PSS: 2a fonte da Calculadora (WS_SIAPE_CONSULTAS 4.22; handoff 2026-07-05).
    # Criada e emitida DEPOIS de base/folha/lixo DE PROPOSITO: o rng stream das tres
    # cargas ja carregadas fica intacto (mesmos id_carga/uuid), e o PSS entra puramente
    # aditivo — pode ser carregado sozinho, sem retocar as demais.
    n_pss = 0
    if not a.sem_pss:
        em.carga("carga_pss")
        rng_p = random.Random(f"{seed}:pss")
        for mat, cpf, fol in folhas:
            n_pss += gera_pss(rng_p, em, mat, cpf, fol, data_ref)

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

    # Escrita — camada de SERIALIZACAO (--formato). 'siape' = envelope SOAP das
    # APIs SIAPE (Card 3); assimetria das fatias: Emissor A projeta a FOTO
    # (servidor.csv), Emissor B re-serializa os eventos AFASTAMENTO da carga_base.
    if a.formato == "siape":
        xml_func = emissor.emite_funcionais(foto)
        afast = [dict(zip(Emissor.COLS, l)) for l in em.cargas["carga_base"]["linhas"]
                 if l[4] == "AFASTAMENTO"]
        xml_afast = emissor.emite_afastamento(afast)
        if a.injeta_defeito:
            xml_func = emissor.aplica_defeito_funcionais(xml_func, a.injeta_defeito)
        fpf = os.path.join(a.out, "siape_funcionais.xml")
        fpa = os.path.join(a.out, "siape_afastamento.xml")
        open(fpf, "w", encoding="utf-8").write(xml_func)
        open(fpa, "w", encoding="utf-8").write(xml_afast)
        defe = f" defeito={a.injeta_defeito}" if a.injeta_defeito else ""
        print(f"[siape] funcionais={len(foto)} vinculos -> {os.path.basename(fpf)} | "
              f"afastamento={len(afast)} eventos -> {os.path.basename(fpa)}{defe}")
        return

    # Escrita (formato = loader; schema v0.13)
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
    # As MVs de exposicao do schema v0.13 (Filme S/G + Calculadora folha/pss). O REFRESH
    # do build inicial e PLANO (popula de uma vez); o caminho D-1/Airflow usa CONCURRENTLY
    # (nao bloqueia o Power BI) — ver 3_schema_mdm.sql. mv_calculadora (unica) NAO existe
    # mais: virou duas por fronteira de payload (ADR-011).
    MVS_EXPOSICAO = ["mv_filme_servidor", "mv_filme_gestor",
                     "mv_calculadora_folha", "mv_calculadora_pss"]
    with open(os.path.join(a.out, "load_eventos.sql"), "w", encoding="utf-8") as fh:
        fh.write("-- carga da massa (schema v0.13): abre particao POR carga, COPY, e REFRESH das MVs\n")
        fh.write("\\set ON_ERROR_STOP on\n")
        for rot, m in manif.items():
            fh.write(f"SELECT fn_particao_carga('{m['id_carga']}');\n")
            fh.write(f"\\copy evento ({','.join(Emissor.COLS)}) FROM '{m['arquivo']}' CSV HEADER\n")
        fh.write("-- popula as MVs de exposicao (build inicial: REFRESH plano)\n")
        for mv in MVS_EXPOSICAO:
            fh.write(f"REFRESH MATERIALIZED VIEW {mv};\n")

    print(f"[ok] vinculos={len(foto)} eventos_base={manif.get('carga_base',{}).get('eventos',0)} "
          f"folha={n_folha} pss={n_pss} lixo={manif.get('carga_lixo',{}).get('eventos',0)} data_ref={data_ref}")


if __name__ == "__main__":
    main()
