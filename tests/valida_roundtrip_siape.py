#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# =============================================================================
# MDM-RH — VALIDA ROUND-TRIP SIAPE (Cards 3 + 6, cenarios a/b) — sem API viva
# Ancoras: siape_envelope.py, gerador_eventos.replay (juiz ADR-008),
#          6_spec_conectores_siape_v0_2.md §"Teste de contrato".
# -----------------------------------------------------------------------------
# (a) FOTO   -> emissor A -> XML Funcionais -> conector A -> foto'
#     assert foto' == servidor.csv    (round-trip puro, recorte SIAPE das 13 colunas)
# (b) EVENTO -> emissor B -> XML §4.21 -> conector B -> eventos'
#     assert1 identidade de evento   (matricula,cod,ini,fim) preservada  [offline, sem DB]
#     assert2 replay(rest+eventos') == FOTO em cod_afastamento_vigente/situacao [juiz ADR-008]
#
# Os cenarios c/d (SERPRO real) usam o MESMO conector — fora deste teste (go-live).
# Uso: py -3 tests/valida_roundtrip_siape.py [--foto ...] [--eventos-base ...] [--sem-db]
# =============================================================================
import argparse
import csv
import json
import os
import sys
from datetime import date

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(RAIZ, "gerador"))
sys.path.insert(0, os.path.join(RAIZ, "conector"))
import siape_envelope as siape
import emissor_siape as emissor
import gerador_eventos as gen
import conector_siape as con


def _le_csv(caminho):
    with open(caminho, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def roundtrip_a(foto):
    """(a) foto' == servidor.csv no recorte SIAPE das 13 colunas."""
    xml = emissor.emite_funcionais(foto)
    linhas, rejeitos = con.parse_funcionais(xml)
    por_mat = {l["matricula_funcional"]: l for l in linhas}
    div = 0
    if len(linhas) != len(foto):
        print(f"  [A] CONTAGEM: emitidos {len(foto)} vinculos, parseados {len(linhas)}")
        div += abs(len(linhas) - len(foto))
    for row in foto:
        got = por_mat.get(row["matricula_funcional"])
        if got is None:
            div += 1
            print(f"  [A] AUSENTE matricula {row['matricula_funcional']}")
            continue
        for c in siape.COLS_FUNCIONAIS:
            esp = (row.get(c) or "")
            obt = (got.get(c) or "")
            if obt != esp:
                div += 1
                if div <= 8:
                    print(f"  [A] DIVERGE {row['matricula_funcional']} [{c}]: "
                          f"foto'={obt!r} servidor={esp!r}")
    ok = (div == 0 and not rejeitos)
    print(f"[a] round-trip Funcionais: {len(foto)} vinculos, {div} divergencias, "
          f"{len(rejeitos)} rejeitos -> {'OK' if ok else 'FALHA'}")
    return ok


def _chave_afast(e):
    pl = e["payload"] if isinstance(e["payload"], dict) else json.loads(e["payload"])
    return (str(e["matricula_funcional"]), pl.get("cod_afastamento") or "",
            pl.get("data_inicio") or "", pl.get("data_fim") or "")


def roundtrip_b(foto, eventos_base, regras):
    """(b) emissor B -> conector B; identidade de evento + replay vs FOTO."""
    afast = [e for e in eventos_base if e["cod_tipo_evento"] == "AFASTAMENTO"]
    resto = [e for e in eventos_base if e["cod_tipo_evento"] != "AFASTAMENTO"]

    xml = emissor.emite_afastamento(afast)
    afast_linha, rejeitos = con.parse_afastamento(
        xml, con.ID_CARGA_INGESTAO, con.DATA_CARGA_INGESTAO)

    # assert1 — identidade de evento (offline, sem DB): mesmos (mat,cod,ini,fim)
    orig = sorted(_chave_afast(e) for e in afast)
    novo = sorted(_chave_afast(e) for e in afast_linha)
    id_ok = (orig == novo)
    print(f"[b.1] identidade de evento: {len(afast)} afastamentos, "
          f"{len(afast_linha)} reconstruidos, {len(rejeitos)} rejeitos -> "
          f"{'OK' if id_ok else 'FALHA'}")
    if not id_ok:
        so_orig = set(orig) - set(novo)
        so_novo = set(novo) - set(orig)
        for k in list(so_orig)[:4]:
            print(f"  [b.1] perdido: {k}")
        for k in list(so_novo)[:4]:
            print(f"  [b.1] surgido: {k}")

    if regras is None:
        print("[b.2] replay vs FOTO: PULADO (--sem-db) — identidade de evento ja provou o envelope")
        return id_ok

    # assert2 — juiz ADR-008: rest + eventos' reconstroi cod_afastamento_vigente
    data_ref = date.fromisoformat(foto[0]["data_referencia"])
    por_mat = {}
    for e in resto + afast_linha:
        por_mat.setdefault(str(e["matricula_funcional"]), []).append(e)
    div = 0
    for row in foto:
        mat = row["matricula_funcional"]
        r = gen.replay(por_mat.get(mat, []), data_ref, regras)
        for c in ("cod_afastamento_vigente", "situacao_funcional"):
            if r[c] != (row[c] or None):
                div += 1
                if div <= 8:
                    print(f"  [b.2] DIVERGE {mat} ({row.get('arquetipo','')}) [{c}]: "
                          f"replay={r[c]!r} foto={row[c] or None!r}")
    r2_ok = (div == 0)
    print(f"[b.2] replay(rest+eventos') vs FOTO: {len(foto)} vinculos, {div} divergencias "
          f"-> {'OK' if r2_ok else 'FALHA'}")
    return id_ok and r2_ok


def main():
    out = os.path.join(RAIZ, "gerador", "out")
    ap = argparse.ArgumentParser(description="Round-trip SIAPE (Cards 3+6, a/b) offline")
    ap.add_argument("--foto", default=os.path.join(out, "servidor.csv"))
    ap.add_argument("--eventos-base", default=os.path.join(out, "eventos_carga_base.csv"))
    ap.add_argument("--sem-db", action="store_true",
                    help="pula o juiz de replay (b.2); roda 100% offline sem Postgres")
    a = ap.parse_args()

    foto = _le_csv(a.foto)
    eventos_base = _le_csv(a.eventos_base)
    regras = None
    if not a.sem_db:
        try:
            regras = gen.traj.carrega_regras()
        except Exception as e:
            print(f"[aviso] regras do DB indisponiveis ({type(e).__name__}: {str(e)[:80]}) — "
                  f"caindo para --sem-db (so identidade de evento em b)")
    print(f"== Round-trip SIAPE — {len(foto)} vinculos, {len(eventos_base)} eventos base ==")
    ok_a = roundtrip_a(foto)
    ok_b = roundtrip_b(foto, eventos_base, regras)
    print(f"== RESULTADO: fatia A {'OK' if ok_a else 'FALHA'} | fatia B {'OK' if ok_b else 'FALHA'} ==")
    sys.exit(0 if (ok_a and ok_b) else 1)


if __name__ == "__main__":
    main()
