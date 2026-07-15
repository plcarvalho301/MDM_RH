#!/usr/bin/env python3
# =============================================================================
# MDM-RH — Loader EVENTO (a "fiacao de persistencia" que faltava)
# versao: v0.1
# ancora: banco/3_schema_mdm.sql (evento particionado por id_carga, fn_particao_carga),
#         geradores/out/load_eventos.sql (padrao COPY que este loader generaliza),
#         carrega_foto.py (mesmo vocabulario: valida -> prepara -> persiste).
# -----------------------------------------------------------------------------
# Recebe eventos dos conectores B/C/D (AFASTAMENTO / FECHAMENTO_FOLHA /
# CONTRIBUICAO_PSS) e persiste em `evento` (INSERT-only, ADR-009). Para cada
# id_carga presente: fn_particao_carga(id) abre a particao LIST, entao INSERT em
# lote. ON CONFLICT (id_carga, id_evento) DO NOTHING => re-load idempotente (a
# serie e imutavel, nunca sobrescreve). Rejeito -> quarentena, nao aborta a carga.
#
# LEITOR AGNOSTICO A FONTE (ADR-006): recebe dicts de evento — do conector (em
# memoria, no runner de ingestao) ou de um CSV avulso (--eventos-csv). A metade
# valida/prepara e pura (testavel sem DB); so `carrega` toca no banco.
#
# USO (a partir da raiz do repo):
#   python -m pipeline.loaders.carrega_evento --eventos-csv geradores/out/eventos_conector.csv
#   python -m pipeline.loaders.carrega_evento --eventos-csv ... --dry-run   # so valida/prepara
# CONEXAO: PGHOST/PGPORT/PGDATABASE/PGUSER/PGPASSWORD (ver loaders/.env.example)
# =============================================================================
import argparse
import csv
import json
import os
import sys

# psycopg2 e opcional em --dry-run (permite validar/preparar sem DB/driver).
try:
    import psycopg2
    from psycopg2.extras import Json, execute_values
except ImportError:
    psycopg2 = None

COLS_EVENTO = ["id_evento", "id_carga", "matricula_funcional", "cpf", "cod_tipo_evento",
               "data_evento", "payload", "cod_mecanica", "fonte", "grau_confianca", "data_carga"]

OBRIGATORIOS = ("id_evento", "id_carga", "cod_tipo_evento", "data_evento", "fonte")


def valida(e: dict) -> tuple[bool, str]:
    """Regras minimas de formato. Retorna (ok, motivo). Nao toca no banco."""
    for col in OBRIGATORIOS:
        if not e.get(col):
            return False, f"campo_obrigatorio_ausente:{col}"
    pl = e.get("payload")
    if isinstance(pl, str) and pl:
        try:
            json.loads(pl)
        except ValueError:
            return False, "payload_json_invalido"
    return True, ""


def prepara_linha(e: dict) -> dict:
    """Projeta as 11 colunas e normaliza o payload p/ objeto Python (coluna jsonb)."""
    out = {c: e.get(c) for c in COLS_EVENTO}
    pl = e.get("payload")
    out["payload"] = json.loads(pl) if isinstance(pl, str) and pl else (pl or {})
    out["cpf"] = e.get("cpf") or ""
    return out


def carrega(eventos, dry_run: bool = False):
    rows_ok, rejeitos = [], []
    for e in eventos:
        ok, motivo = valida(e)
        if not ok:
            rejeitos.append((motivo, e))
            continue
        rows_ok.append(prepara_linha(e))

    cargas = sorted({r["id_carga"] for r in rows_ok})
    print(f"valida: {len(rows_ok)} ok / {len(rejeitos)} rejeitados | {len(cargas)} carga(s)")
    if rejeitos:
        from collections import Counter
        print(f"  motivos: {dict(Counter(m for m, _ in rejeitos))}")

    if dry_run:
        print("[--dry-run] nao conecta no banco. Amostra da 1a linha preparada:")
        if rows_ok:
            print(" ", json.dumps(rows_ok[0], default=str, ensure_ascii=False))
        return {"ok": len(rows_ok), "rejeitos": len(rejeitos), "cargas": cargas}

    if psycopg2 is None:
        sys.exit("psycopg2 nao instalado. pip install psycopg2-binary --break-system-packages")

    conn = psycopg2.connect(
        host=os.environ.get("PGHOST", "localhost"),
        port=os.environ.get("PGPORT", "5432"),
        dbname=os.environ.get("PGDATABASE", "mdm_rh"),
        user=os.environ.get("PGUSER", "mdm_rh"),
        password=os.environ.get("PGPASSWORD", ""),
    )
    conn.autocommit = False
    with conn.cursor() as cur:
        # 1) abre uma particao LIST por id_carga (idempotente — CREATE IF NOT EXISTS)
        for idc in cargas:
            cur.execute("SELECT fn_particao_carga(%s)", (idc,))
        # 2) INSERT-only em lote; ON CONFLICT nao sobrescreve (serie imutavel, ADR-009)
        sql = (f"INSERT INTO evento ({','.join(COLS_EVENTO)}) VALUES %s "
               f"ON CONFLICT (id_carga, id_evento) DO NOTHING")
        valores = [[Json(r[c]) if c == "payload" else r[c] for c in COLS_EVENTO]
                   for r in rows_ok]
        execute_values(cur, sql, valores)
        # 3) rejeitos -> quarentena (nao aborta a carga)
        for motivo, e in rejeitos:
            cur.execute(
                "INSERT INTO rejeito (fonte, cod_mecanica, motivo, registro_bruto) "
                "VALUES (%s, %s, %s, %s)",
                (e.get("fonte") or "WS_SIAPE", e.get("cod_mecanica") or "ingestao", motivo,
                 Json(e, dumps=lambda o: json.dumps(o, default=str))))
        conn.commit()
    conn.close()
    # rowcount pos-execute_values nao soma as paginas; reportamos os validos processados.
    print(f"carga: {len(rows_ok)} eventos validos processados (INSERT-only; conflitos de "
          f"re-load ignorados), {len(rejeitos)} rejeitados -> quarentena.")
    return {"ok": len(rows_ok), "rejeitos": len(rejeitos), "cargas": cargas}


def _le_csv(caminho):
    with open(caminho, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Loader EVENTO (persiste eventos dos conectores)")
    ap.add_argument("--eventos-csv", required=True, help="CSV de eventos (COLS_EVENTO) do conector")
    ap.add_argument("--dry-run", action="store_true", help="so valida/prepara, nao conecta no banco")
    a = ap.parse_args()
    carrega(_le_csv(a.eventos_csv), dry_run=a.dry_run)
