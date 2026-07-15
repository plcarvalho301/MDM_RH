#!/usr/bin/env python3
# =============================================================================
# MDM-RH — RUNNER de ingestao SIAPE (amarra conectores -> loaders num fluxo so)
# versao: v0.1
# ancora: docs/5_spec_pipeline_airflow_v0_1.md (topologia do DAG),
#         docs/3_depara_soap_conectores_v0_3.md (de-para das faces).
# -----------------------------------------------------------------------------
# extrai -> conecta A/B/C/D -> reconcilia FOTO -> persiste {servidor, evento} -> REFRESH.
# NAO reescreve nada: reusa parse_* (conector), carrega_foto/carrega_evento (loaders).
# Cada etapa e uma funcao chamavel — quando o Airflow entrar, o DAG so envolve estas
# funcoes em PythonOperators (o spec pede "nothing rewritten"). Rodar sem Airflow:
#   python -m pipeline.ingestao_siape --fonte xml [--data-ref 2026-07-13] [--dry-run]
#
# COBERTURA (v1): as faces que o SIAPE Consultas fornece — FOTO (consultaDadosFuncionais),
# AFASTAMENTO (§4.21), FECHAMENTO_FOLHA (§4.20), CONTRIBUICAO_PSS (§4.22). A serie
# historica de `vinculos` (PROVIMENTO/PROGRESSAO/...) vem do Extrator/PCA, fora daqui —
# logo o replay de `situacao_funcional` completo exige tambem essa fonte (ver §0 do de-para).
#
# CONEXAO: PGHOST/PGPORT/PGDATABASE/PGUSER/PGPASSWORD (loaders/.env).
# =============================================================================
import argparse
import os
import sys
import uuid
from datetime import date

from pipeline.conectores import conector_siape as con
from pipeline.loaders import carrega_foto, carrega_evento

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_PADRAO = os.path.join(RAIZ, "geradores", "out")

MVS = ["mv_filme_servidor", "mv_filme_gestor", "mv_calculadora_folha", "mv_calculadora_pss"]

# Colunas NOT NULL de `servidor` que o recorte SIAPE nao traz (reconciliacao FOTO).
# nome/data_nascimento agora VIAJAM no envelope (contrato FUNCIONAIS); aqui so os
# 3 constantes derivados + cod_afastamento_vigente (nullable, vem do evento AFASTAMENTO).
def reconcilia_foto(linha_siape: dict, data_ref: str) -> dict:
    row = dict(linha_siape)
    row["origem_unidade"] = "SIAPE"      # o feed e SIAPE
    row["cod_mecanica"] = "ingestao"     # ADR-014
    row["data_referencia"] = data_ref    # D-1 da carga
    row.setdefault("cod_afastamento_vigente", "")
    return row


def extrai(fonte: str, outdir: str) -> dict:
    """extrai: obtem os 4 envelopes. fonte=xml (teste, le do emissor) | api (go-live)."""
    if fonte != "xml":
        raise SystemExit(f"fonte={fonte!r}: so 'xml' na v1 (api = go-live: JWT/ICP-Brasil, paginacao)")
    def ler(nome):
        return open(os.path.join(outdir, nome), encoding="utf-8").read()
    return {
        "funcionais":  ler("siape_funcionais.xml"),
        "afastamento": ler("siape_afastamento.xml"),
        "financeiro":  ler("siape_financeiro.xml"),
        "pss":         ler("siape_pss.xml"),
    }


def _refresh_mvs():
    import psycopg2
    conn = psycopg2.connect(
        host=os.environ.get("PGHOST", "localhost"), port=os.environ.get("PGPORT", "5432"),
        dbname=os.environ.get("PGDATABASE", "mdm_rh"), user=os.environ.get("PGUSER", "mdm_rh"),
        password=os.environ.get("PGPASSWORD", ""))
    conn.autocommit = True
    with conn.cursor() as cur:
        for mv in MVS:
            cur.execute(f"REFRESH MATERIALIZED VIEW {mv}")  # v1: plano. CONCURRENTLY = upgrade D-1.
    conn.close()
    print(f"[refresh] {len(MVS)} MVs de exposicao atualizadas")


def ingesta(fonte="xml", outdir=OUT_PADRAO, data_ref=None, dry_run=False):
    data_ref = data_ref or date.today().isoformat()
    # 1 id_carga por execucao (ADR-009: retratacao por DETACH da carga inteira).
    # Deterministico por data => re-run mesmo dia e idempotente (ON CONFLICT no evento).
    id_carga = str(uuid.uuid5(uuid.NAMESPACE_URL, f"ingestao_siape:{data_ref}"))
    dc = con.DATA_CARGA_INGESTAO

    xmls = extrai(fonte, outdir)
    foto16, rej_a = con.parse_funcionais(xmls["funcionais"])
    afast,  rej_b = con.parse_afastamento(xmls["afastamento"], id_carga, dc)
    folha,  rej_c = con.parse_financeiro(xmls["financeiro"],  id_carga, dc)
    pss,    rej_d = con.parse_pss(xmls["pss"],                id_carga, dc)
    foto20 = [reconcilia_foto(r, data_ref) for r in foto16]

    print(f"[extrai/conecta] foto={len(foto16)} afast={len(afast)} folha={len(folha)} "
          f"pss={len(pss)} | rejeitos A/B/C/D={len(rej_a)}/{len(rej_b)}/{len(rej_c)}/{len(rej_d)} "
          f"| id_carga={id_carga[:8]} data_ref={data_ref}")

    print("[persiste_foto]");  carrega_foto.carrega_linhas(foto20, dry_run=dry_run)
    print("[persiste_evento]"); carrega_evento.carrega(afast + folha + pss, dry_run=dry_run)
    if not dry_run:
        _refresh_mvs()
    return {"id_carga": id_carga, "foto": len(foto16),
            "eventos": len(afast) + len(folha) + len(pss)}


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Runner de ingestao SIAPE (conectores -> banco)")
    ap.add_argument("--fonte", choices=("xml", "api"), default="xml")
    ap.add_argument("--outdir", default=OUT_PADRAO, help="dir dos siape_*.xml (fonte=xml)")
    ap.add_argument("--data-ref", default=None, help="data de referencia (D-1); default: hoje")
    ap.add_argument("--dry-run", action="store_true", help="conecta/valida/prepara, nao toca no banco")
    a = ap.parse_args()
    r = ingesta(fonte=a.fonte, outdir=a.outdir, data_ref=a.data_ref, dry_run=a.dry_run)
    print(f"== ingestao SIAPE: {r['foto']} FOTO + {r['eventos']} eventos, carga {r['id_carga'][:8]} ==")
