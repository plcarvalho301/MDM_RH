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
# Uso (a partir da raiz do repo): py -3 -m pipeline.tests.valida_roundtrip_siape [--foto ...] [--eventos-base ...] [--sem-db]
# =============================================================================
import argparse
import csv
import json
import os
import sys
from datetime import date

RAIZ = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from pipeline.contrato import siape_envelope as siape
from geradores import emissor_siape as emissor
from geradores import gerador_eventos as gen
from pipeline.conectores import conector_siape as con


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

    # assert1 — §4.21 e SNAPSHOT historico: o emissor coalesce o par abre/fecha (ADR-008)
    # por chave (mat,cod,data_inicio), vencendo a data_carga mais recente. Comparamos contra
    # esse snapshot, nao contra o event-stream interno (open+close).
    snap = {}
    for e in afast:
        pl = e["payload"] if isinstance(e["payload"], dict) else json.loads(e["payload"])
        k = (str(e["matricula_funcional"]), pl.get("cod_afastamento") or "", pl.get("data_inicio") or "")
        dc = e.get("data_carga") or ""
        if k not in snap or dc >= snap[k][0]:
            snap[k] = (dc, e)
    orig = sorted(_chave_afast(e) for _dc, e in snap.values())
    novo = sorted(_chave_afast(e) for e in afast_linha)
    id_ok = (orig == novo)
    print(f"[b.1] identidade (§4.21 snapshot): {len(afast)} no stream -> {len(snap)} ocorrencias, "
          f"{len(afast_linha)} reconstruidas, {len(rejeitos)} rejeitos -> {'OK' if id_ok else 'FALHA'}")
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


# ── (c/d) compensacao: FECHAMENTO_FOLHA §4.20 e CONTRIBUICAO_PSS §4.22 ────────
def _pl(e):
    return e["payload"] if isinstance(e["payload"], dict) else json.loads(e["payload"])


def _norm_rubricas(rs):
    campos = ("cod_rubrica", "nome_rubrica", "valor_rubrica", "indicador_rd", "numero_seq")
    return sorted(tuple((k, r.get(k)) for k in campos) for r in rs)


def roundtrip_c(folha_events):
    """(c) FECHAMENTO_FOLHA -> emissor C -> XML §4.20 -> conector C -> eventos'.
    Compara (matricula, mes_competencia) -> tipo_fechamento + rubricas. mes_pagamento
    NAO viaja no envelope (decisao TL) — fora da comparacao."""
    xml = emissor.emite_financeiro(folha_events)
    novo, rejeitos = con.parse_financeiro(xml)
    orig = {(str(e["matricula_funcional"]), _pl(e).get("mes_competencia")): e for e in folha_events}
    got = {(str(e["matricula_funcional"]), _pl(e).get("mes_competencia")): e for e in novo}
    div = len(set(orig) ^ set(got))
    for k in set(orig) & set(got):
        p0, p1 = _pl(orig[k]), _pl(got[k])
        if p0.get("tipo_fechamento") != p1.get("tipo_fechamento"):
            div += 1
        if _norm_rubricas(p0.get("rubricas", [])) != _norm_rubricas(p1.get("rubricas", [])):
            div += 1
            if div <= 8:
                print(f"  [c] DIVERGE {k} rubricas: {p0.get('rubricas')} != {p1.get('rubricas')}")
    ok = (div == 0 and not rejeitos)
    print(f"[c] round-trip FECHAMENTO_FOLHA: {len(folha_events)} eventos, {div} divergencias, "
          f"{len(rejeitos)} rejeitos -> {'OK' if ok else 'FALHA'}")
    return ok


def roundtrip_d(pss_events):
    """(d) CONTRIBUICAO_PSS -> emissor D -> XML §4.22 -> conector D -> eventos'."""
    xml = emissor.emite_pss(pss_events)
    novo, rejeitos = con.parse_pss(xml)
    chave = lambda e: (str(e["matricula_funcional"]), _pl(e).get("ano_contribuicao"), _pl(e).get("mes_contribuicao"))
    orig = {chave(e): e for e in pss_events}
    got = {chave(e): e for e in novo}
    campos = ("gr_matricula", "ano_contribuicao", "mes_contribuicao", "indice_reajuste",
              "pss_apurado", "pss_informado", "remuneracao_pss", "remuneracao_pss_ajustada")
    div = len(set(orig) ^ set(got))
    for k in set(orig) & set(got):
        p0, p1 = _pl(orig[k]), _pl(got[k])
        for c in campos:
            if p0.get(c) != p1.get(c):
                div += 1
                if div <= 8:
                    print(f"  [d] DIVERGE {k} [{c}]: {p0.get(c)!r} != {p1.get(c)!r}")
    ok = (div == 0 and not rejeitos)
    print(f"[d] round-trip CONTRIBUICAO_PSS: {len(pss_events)} eventos, {div} divergencias, "
          f"{len(rejeitos)} rejeitos -> {'OK' if ok else 'FALHA'}")
    return ok


def _eventos_demo():
    """Eventos sinteticos p/ o self-check offline (sem corpus/DB). Cobre: multi-competencia
    e multi-ano por matricula, suplementar, valor negativo (desconto)."""
    folha = [
        {"cpf": "11122233344", "matricula_funcional": "1234567", "cod_tipo_evento": "FECHAMENTO_FOLHA",
         "payload": {"mes_competencia": "202601", "mes_pagamento": "202601", "tipo_fechamento": "normal",
                     "rubricas": [{"cod_rubrica": 1, "nome_rubrica": "VENCIMENTO BASICO",
                                   "valor_rubrica": 12345.67, "indicador_rd": "R", "numero_seq": 1},
                                  {"cod_rubrica": 998, "nome_rubrica": "IRRF",
                                   "valor_rubrica": -1234.5, "indicador_rd": "D", "numero_seq": 2}]}},
        {"cpf": "11122233344", "matricula_funcional": "1234567", "cod_tipo_evento": "FECHAMENTO_FOLHA",
         "payload": {"mes_competencia": "202602", "mes_pagamento": "202603", "tipo_fechamento": "suplementar",
                     "rubricas": [{"cod_rubrica": 1, "nome_rubrica": "VENCIMENTO BASICO",
                                   "valor_rubrica": 500.0, "indicador_rd": "R", "numero_seq": 1}]}},
        {"cpf": "55566677788", "matricula_funcional": "7654321", "cod_tipo_evento": "FECHAMENTO_FOLHA",
         "payload": {"mes_competencia": "202601", "mes_pagamento": "202601", "tipo_fechamento": "normal",
                     "rubricas": [{"cod_rubrica": 1, "nome_rubrica": "VENCIMENTO BASICO",
                                   "valor_rubrica": 9000.0, "indicador_rd": "R", "numero_seq": 1}]}},
    ]
    pss = [
        {"cpf": "11122233344", "matricula_funcional": "1234567", "cod_tipo_evento": "CONTRIBUICAO_PSS",
         "payload": {"gr_matricula": 1234567, "ano_contribuicao": 2026, "mes_contribuicao": 1,
                     "indice_reajuste": 1, "pss_apurado": 1358, "pss_informado": 1358,
                     "remuneracao_pss": 12345.67, "remuneracao_pss_ajustada": 12345.67}},
        {"cpf": "11122233344", "matricula_funcional": "1234567", "cod_tipo_evento": "CONTRIBUICAO_PSS",
         "payload": {"gr_matricula": 1234567, "ano_contribuicao": 2025, "mes_contribuicao": 12,
                     "indice_reajuste": 1, "pss_apurado": 55, "pss_informado": 55,
                     "remuneracao_pss": 500.0, "remuneracao_pss_ajustada": 500.0}},
        {"cpf": "55566677788", "matricula_funcional": "7654321", "cod_tipo_evento": "CONTRIBUICAO_PSS",
         "payload": {"gr_matricula": 7654321, "ano_contribuicao": 2025, "mes_contribuicao": 12,
                     "indice_reajuste": 1, "pss_apurado": 990, "pss_informado": 990,
                     "remuneracao_pss": 9000.0, "remuneracao_pss_ajustada": 9000.0}},
    ]
    return folha, pss


def main():
    out = os.path.join(RAIZ, "geradores", "out")
    ap = argparse.ArgumentParser(description="Round-trip SIAPE (Cards 3+6, a/b/c/d) offline")
    ap.add_argument("--foto", default=os.path.join(out, "servidor.csv"))
    ap.add_argument("--eventos-base", default=os.path.join(out, "eventos_carga_base.csv"))
    ap.add_argument("--eventos-folha", default=os.path.join(out, "eventos_carga_folha.csv"))
    ap.add_argument("--eventos-pss", default=os.path.join(out, "eventos_carga_pss.csv"))
    ap.add_argument("--sem-db", action="store_true",
                    help="pula o juiz de replay (b.2); roda 100% offline sem Postgres")
    ap.add_argument("--demo", action="store_true",
                    help="round-trip sintetico de folha/PSS (c/d) — offline, sem corpus nem DB")
    a = ap.parse_args()

    if a.demo:
        folha, pss = _eventos_demo()
        print(f"== Round-trip SIAPE (demo compensacao) — {len(folha)} folha, {len(pss)} PSS ==")
        ok_c, ok_d = roundtrip_c(folha), roundtrip_d(pss)
        print(f"== RESULTADO demo: folha {'OK' if ok_c else 'FALHA'} | PSS {'OK' if ok_d else 'FALHA'} ==")
        sys.exit(0 if (ok_c and ok_d) else 1)

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
    ok_c = roundtrip_c(_le_csv(a.eventos_folha)) if os.path.exists(a.eventos_folha) else True
    ok_d = roundtrip_d(_le_csv(a.eventos_pss)) if os.path.exists(a.eventos_pss) else True
    print(f"== RESULTADO: A {'OK' if ok_a else 'FALHA'} | B {'OK' if ok_b else 'FALHA'} | "
          f"C {'OK' if ok_c else 'FALHA'} | D {'OK' if ok_d else 'FALHA'} ==")
    sys.exit(0 if (ok_a and ok_b and ok_c and ok_d) else 1)


if __name__ == "__main__":
    main()
