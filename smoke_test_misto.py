"""
Smoke test descartavel — encanamento MISTO (FOTO + EVENTO no mesmo lote).

Anterior ao gen_massa v2 (trajetoria); prova que o pipeline classifica
DE VERDADE por linha (nao mais o passthrough trivial de carrega_foto.py/v1
nem de smoke_test_evento.py, que so sabiam um tipo por leitor). Aqui o
mesmo lote traz FOTO e EVENTO misturados e cada registro vai pro destino
certo (servidor via UPSERT, evento via INSERT).

Cenarios pedidos:
  a) FOTO e EVENTO no mesmo lote — o evento referencia a matricula que o
     PROPRIO registro FOTO do lote acabou de criar (prova a ordem: a
     checagem de matricula-orfa enxerga o que o lote ja upsertou, nao so
     o que ja estava no banco antes de rodar).
  b) evento para matricula que nao existe em lugar nenhum (nem lote, nem
     banco) -> rejeito por matricula_orfa_servidor.
  c) evento para matricula que JA existe de verdade em servidor (uma das
     1200 da massa FOTO), mas com o payload JSON quebrado (nao fecha
     sintaxe) -> Postgres recusa o cast ::jsonb -> erro_postgres. Motivo
     diferente do (b): aqui a matricula existe, quem quebra e o dado.

Uso:
    python smoke_test_misto.py --dry-run
    python smoke_test_misto.py

Reaproveita valida_sintaxe_local/busca_matriculas_existentes/insere_rejeito
de smoke_test_evento.py (mesma vara de pescar, nao duplica regra).
"""

import argparse
import json
import sys

import psycopg2

from smoke_test_evento import (
    carrega_env,
    conecta,
    busca_matriculas_existentes,
    valida_sintaxe_local,
    insere_rejeito,
)

COLS_SERVIDOR = [
    "matricula_funcional", "cpf", "nome", "data_nascimento", "cargo", "classe",
    "padrao", "sigla_nivel_cargo", "funcao_comissionada", "nova_funcao",
    "data_ingresso_nova_funcao", "cod_unidade_lotacao", "cod_unidade_exercicio",
    "origem_unidade", "situacao_funcional", "regime_juridico",
    "data_exercicio_no_orgao", "cod_afastamento_vigente", "data_referencia",
    "cod_mecanica",
]

LOTE_MISTO = [
    # a) FOTO nova no lote — cria o servidor que o proximo registro referencia
    {
        "caso": "a_foto_no_lote",
        "tipo_registro": "FOTO",
        "matricula_funcional": "5000001", "cpf": "10000000001",
        "nome": "Servidor Misto A", "data_nascimento": "1985-05-10",
        "cargo": "EPPGG", "classe": "B", "padrao": "III", "sigla_nivel_cargo": "NS",
        "funcao_comissionada": None, "nova_funcao": None,
        "data_ingresso_nova_funcao": None,
        "cod_unidade_lotacao": 1001, "cod_unidade_exercicio": 1001,
        "origem_unidade": "SIORG", "situacao_funcional": "ATIVO",
        "regime_juridico": "RJU", "data_exercicio_no_orgao": "2015-02-01",
        "cod_afastamento_vigente": None,
        "data_referencia": "2026-07-03", "cod_mecanica": "ingestao",
    },
    # a) EVENTO no MESMO lote, mesma matricula do registro FOTO acima
    {
        "caso": "a_evento_no_lote",
        "tipo_registro": "EVENTO",
        "matricula_funcional": "5000001", "cpf": "10000000001",
        "cod_tipo_evento": "AFASTAMENTO", "data_evento": "2026-06-01",
        "cod_mecanica": "ingestao", "fonte": "API_SIAPE_CONSULTAS",
        "grau_confianca": "alto",
        "payload": {"cod_afastamento": "15", "data_inicio": "2026-06-01", "data_fim": None},
    },
    # b) EVENTO para matricula que nao existe nem no lote, nem no banco
    {
        "caso": "b_evento_servidor_inexistente",
        "tipo_registro": "EVENTO",
        "matricula_funcional": "5009999", "cpf": "10000009999",
        "cod_tipo_evento": "AFASTAMENTO", "data_evento": "2026-05-15",
        "cod_mecanica": "ingestao", "fonte": "API_SIAPE_CONSULTAS",
        "grau_confianca": "alto",
        "payload": {"cod_afastamento": "01", "data_inicio": "2026-05-15", "data_fim": None},
    },
    # c) EVENTO para matricula REAL (ja carregada na massa FOTO), payload JSON quebrado
    {
        "caso": "c_evento_payload_quebrado",
        "tipo_registro": "EVENTO",
        "matricula_funcional": "1010905", "cpf": "11786190254",
        "cod_tipo_evento": "AFASTAMENTO", "data_evento": "2026-04-10",
        "cod_mecanica": "ingestao", "fonte": "API_SIAPE_CONSULTAS",
        "grau_confianca": "alto",
        # de proposito: JSON invalido (chave sem fechar), Postgres recusa o cast ::jsonb
        "payload_bruto": '{"cod_afastamento": "01", "data_inicio": "2026-04-10", "data_fim": ',
    },
]


def classifica_registro(row):
    """classifica DE VERDADE: decide pelo formato da linha, nao por leitor fixo."""
    return row["tipo_registro"]


def upsert_foto(conn, row):
    vals = [row[c] for c in COLS_SERVIDOR]
    placeholders = ",".join(["%s"] * len(COLS_SERVIDOR))
    col_list = ",".join(COLS_SERVIDOR)
    update_set = ",".join(f"{c}=EXCLUDED.{c}" for c in COLS_SERVIDOR if c != "matricula_funcional")
    with conn.cursor() as cur:
        cur.execute(
            f"""
            INSERT INTO servidor ({col_list}) VALUES ({placeholders})
            ON CONFLICT (matricula_funcional) DO UPDATE SET {update_set}
            """,
            vals,
        )


def insere_evento_raw(conn, matricula, cpf, cod_tipo_evento, data_evento,
                       payload_texto, cod_mecanica, fonte, grau_confianca):
    """Mesmo INSERT do smoke_test_evento.py, mas aceita payload como TEXTO cru
    (nao json.dumps de dict) — e o que deixa o caso (c) quebrar no cast ::jsonb."""
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO evento
                (matricula_funcional, cpf, cod_tipo_evento, data_evento,
                 payload, cod_mecanica, fonte, grau_confianca)
            VALUES (%s, %s, %s, %s, %s::jsonb, %s, %s, %s)
            """,
            (matricula, cpf, cod_tipo_evento, data_evento, payload_texto,
             cod_mecanica, fonte, grau_confianca),
        )


def roda(dry_run=False):
    env = carrega_env()
    resultado = {"foto": [], "evento": [], "rejeitados": []}

    conn = None if dry_run else conecta(env)
    if conn:
        conn.autocommit = False

    matriculas_no_lote = set()
    matriculas_no_banco = set()
    if not dry_run:
        candidatas = {r["matricula_funcional"] for r in LOTE_MISTO
                      if classifica_registro(r) == "EVENTO"}
        matriculas_no_banco = busca_matriculas_existentes(conn, candidatas)

    for row in LOTE_MISTO:
        caso = row["caso"]
        tipo = classifica_registro(row)

        if tipo == "FOTO":
            print(f"[classifica] {caso}: FOTO -> upsert em servidor")
            if dry_run:
                print(f"  [upsertaria] {row['matricula_funcional']}")
            else:
                upsert_foto(conn, row)
                conn.commit()
            matriculas_no_lote.add(row["matricula_funcional"])
            resultado["foto"].append(caso)
            continue

        # tipo == EVENTO
        print(f"[classifica] {caso}: EVENTO -> valida/insere")
        motivos = valida_sintaxe_local(row)

        existe = row["matricula_funcional"] in matriculas_no_lote or \
                 row["matricula_funcional"] in matriculas_no_banco
        if not dry_run and not existe and "matricula_malformada" not in motivos:
            motivos.append("matricula_orfa_servidor")

        if motivos:
            msg = f"[REJEITO/pre-triagem{' dry-run' if dry_run else ''}] {caso}: {motivos}"
            print(msg)
            resultado["rejeitados"].append((caso, ";".join(motivos)))
            if not dry_run:
                insere_rejeito(conn, row["fonte"], row["cod_mecanica"],
                                ";".join(motivos), row)
                conn.commit()
            continue

        payload_texto = row.get("payload_bruto")
        if payload_texto is None:
            payload_texto = json.dumps(row["payload"])

        if dry_run:
            print(f"  [carregaria] {row['matricula_funcional']} / {row['cod_tipo_evento']}")
            resultado["evento"].append(caso)
            continue

        try:
            insere_evento_raw(
                conn, row["matricula_funcional"], row["cpf"], row["cod_tipo_evento"],
                row["data_evento"], payload_texto, row["cod_mecanica"],
                row["fonte"], row["grau_confianca"],
            )
            conn.commit()
            resultado["evento"].append(caso)
            print(f"  [EVENTO] {caso}: carregado")
        except psycopg2.Error as e:
            conn.rollback()
            motivo_pg = str(e).strip().splitlines()[0]
            insere_rejeito(conn, row["fonte"], row["cod_mecanica"],
                            f"erro_postgres:{motivo_pg}", row)
            conn.commit()
            resultado["rejeitados"].append((caso, motivo_pg))
            print(f"  [REJEITO/postgres] {caso}: {motivo_pg}")

    if conn:
        conn.close()

    print("\n--- resumo ---")
    print(f"foto (upsert):    {len(resultado['foto'])}")
    print(f"evento (insert):  {len(resultado['evento'])}")
    print(f"rejeitados:       {len(resultado['rejeitados'])}")
    for caso, motivo in resultado["rejeitados"]:
        print(f"  - {caso}: {motivo}")

    return resultado


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Smoke test do encanamento MISTO (FOTO + EVENTO).")
    parser.add_argument("--dry-run", action="store_true", help="Nao escreve no banco; so mostra decisao.")
    args = parser.parse_args()

    try:
        roda(dry_run=args.dry_run)
    except psycopg2.OperationalError as e:
        print(f"Erro de conexao ao Postgres: {e}", file=sys.stderr)
        sys.exit(1)
