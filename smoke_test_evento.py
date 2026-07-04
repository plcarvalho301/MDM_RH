"""
Smoke test descartavel — pipeline de EVENTO (cod_mecanica=ingestao).

NAO e o gerador de trajetoria (v2). E anterior a ele: prova que o encanamento
classifica/valida sabe separar evento bom de evento torto, usando AFASTAMENTO
como tipo de teste.

Mesma vara de pescar do carrega_foto.py (v1, PoC FOTO): deixa o Postgres fazer
o trabalho pesado de CHECK/FK simples (regex de matricula/cpf, FK de
cod_afastamento) e captura a excecao pra rotear em `rejeito`. So o que o
schema NAO cobre — existencia de matricula em `servidor` — e checado em
Python, em lote, antes do INSERT (ADR-007 candidata, ainda nao formalizada
em 1_adr_mdm.md; so o comportamento entra hoje).

Uso:
    python smoke_test_evento.py --dry-run   # nao escreve nada, so mostra decisao
    python smoke_test_evento.py             # escreve em evento/rejeito de verdade

Le credenciais de .env (mesmo padrao do carrega_foto.py da PoC FOTO).
"""

import argparse
import json
import os
import sys
from datetime import date

import psycopg2
import psycopg2.extras

from payloads_afastamento_smoke import PAYLOADS_AFASTAMENTO


def carrega_env(path=".env"):
    """Le .env simples (KEY=VALUE por linha), sem dependencia de python-dotenv."""
    env = {}
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            for linha in f:
                linha = linha.strip()
                if not linha or linha.startswith("#") or "=" not in linha:
                    continue
                k, v = linha.split("=", 1)
                env[k.strip()] = v.strip()
    # env real do sistema tem prioridade sobre o arquivo
    for k in ("PGHOST", "PGPORT", "PGDATABASE", "PGUSER", "PGPASSWORD"):
        if os.environ.get(k):
            env[k] = os.environ[k]
    return env


def conecta(env):
    return psycopg2.connect(
        host=env.get("PGHOST", "localhost"),
        port=env.get("PGPORT", "5432"),
        dbname=env.get("PGDATABASE", "mdm_rh"),
        user=env.get("PGUSER", "postgres"),
        password=env.get("PGPASSWORD", ""),
    )


def busca_matriculas_existentes(conn, matriculas):
    """
    Check em lote (ADR-007 candidata): quais das matriculas do batch ja tem
    linha em `servidor`. UMA query por batch, nao uma por evento — e o ponto
    fechado na sessao sobre custo computacional.
    """
    if not matriculas:
        return set()
    with conn.cursor() as cur:
        cur.execute(
            "SELECT matricula_funcional FROM servidor WHERE matricula_funcional = ANY(%s)",
            (list(matriculas),),
        )
        return {row[0] for row in cur.fetchall()}


def classifica(payload):
    """
    classifica: decide sub_dominio + cod_tipo_evento a partir do que ja esta
    em dom_tipo_evento/dom_afastamento. Nesta massa descartavel, todo item ja
    vem com cod_tipo_evento=AFASTAMENTO — classifica aqui e so o passthrough
    formal, deixando explicito onde o passo vive no pipeline real.
    """
    return payload.get("cod_tipo_evento")


def valida_sintaxe_local(payload):
    """
    Validacoes que o PROPRIO SCHEMA ja cobre via CHECK/FK — checadas aqui so
    para dar um motivo de rejeicao mais legivel do que a mensagem crua do
    psycopg2 quando possivel. A fonte da verdade da rejeicao ainda e a
    excecao do Postgres, capturada em carrega_evento(); isto e so uma
    pre-triagem best-effort.
    """
    motivos = []
    matricula = payload.get("matricula_funcional") or ""
    cpf = payload.get("cpf") or ""
    if not (len(matricula) == 7 and matricula.isdigit()):
        motivos.append("matricula_malformada")
    if not (len(cpf) == 11 and cpf.isdigit()):
        motivos.append("cpf_malformado")
    if not payload.get("data_evento"):
        motivos.append("data_ausente")
    return motivos


def envelope_evento(payload):
    return {
        "matricula_funcional": payload["matricula_funcional"],
        "cpf": payload["cpf"],
        "cod_tipo_evento": payload["cod_tipo_evento"],
        "data_evento": payload["data_evento"],
        "payload": json.dumps(payload["payload"]),
        "cod_mecanica": payload["cod_mecanica"],
        "fonte": payload["fonte"],
        "grau_confianca": payload["grau_confianca"],
    }


def insere_evento(conn, env):
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO evento
                (matricula_funcional, cpf, cod_tipo_evento, data_evento,
                 payload, cod_mecanica, fonte, grau_confianca)
            VALUES (%(matricula_funcional)s, %(cpf)s, %(cod_tipo_evento)s,
                    %(data_evento)s, %(payload)s::jsonb, %(cod_mecanica)s,
                    %(fonte)s, %(grau_confianca)s)
            """,
            env,
        )


def insere_rejeito(conn, fonte, cod_mecanica, motivo, registro_bruto):
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO rejeito (fonte, cod_mecanica, motivo, registro_bruto)
            VALUES (%s, %s, %s, %s::jsonb)
            """,
            (fonte, cod_mecanica, motivo, json.dumps(registro_bruto, default=str)),
        )


def roda(dry_run=False):
    env = carrega_env()

    resultado = {"carregados": [], "rejeitados": []}

    if dry_run:
        conn = None
        matriculas_existentes = set()  # dry-run nao consulta banco
        print("[dry-run] sem conexao ao banco; check de matricula orfa sera pulado.\n")
    else:
        conn = conecta(env)
        conn.autocommit = False
        matriculas_batch = {p["matricula_funcional"] for p in PAYLOADS_AFASTAMENTO}
        matriculas_existentes = busca_matriculas_existentes(conn, matriculas_batch)

    for item in PAYLOADS_AFASTAMENTO:
        caso = item["caso"]

        # 1. classifica
        tipo = classifica(item)

        # 2. valida (pre-triagem local, best-effort — nao substitui a excecao do banco)
        motivos_locais = valida_sintaxe_local(item)

        # 2b. check de matricula orfa (ADR-007 candidata) — so faz sentido com banco de verdade
        if not dry_run and item["matricula_funcional"] not in matriculas_existentes:
            if "matricula_malformada" not in motivos_locais:
                motivos_locais.append("matricula_orfa_servidor")

        if motivos_locais and not dry_run:
            insere_rejeito(
                conn,
                fonte=item["fonte"],
                cod_mecanica=item["cod_mecanica"],
                motivo=";".join(motivos_locais),
                registro_bruto=item,
            )
            conn.commit()
            resultado["rejeitados"].append((caso, ";".join(motivos_locais)))
            print(f"[REJEITO/pre-triagem] {caso}: {motivos_locais}")
            continue
        elif motivos_locais and dry_run:
            resultado["rejeitados"].append((caso, ";".join(motivos_locais)))
            print(f"[REJEITO/pre-triagem, dry-run] {caso}: {motivos_locais}")
            continue

        # 3. carrega — deixa o Postgres aplicar CHECK/FK reais (cpf, matricula, fk tipo/afastamento)
        env_evento = envelope_evento(item)

        if dry_run:
            print(f"[carregaria] {caso}: {env_evento['matricula_funcional']} / "
                  f"{env_evento['cod_tipo_evento']} / {env_evento['data_evento']}")
            resultado["carregados"].append(caso)
            continue

        try:
            insere_evento(conn, env_evento)
            conn.commit()
            resultado["carregados"].append(caso)
            print(f"[EVENTO] {caso}: carregado")
        except psycopg2.Error as e:
            conn.rollback()
            motivo_pg = str(e).strip().splitlines()[0]
            insere_rejeito(
                conn,
                fonte=item["fonte"],
                cod_mecanica=item["cod_mecanica"],
                motivo=f"erro_postgres:{motivo_pg}",
                registro_bruto=item,
            )
            conn.commit()
            resultado["rejeitados"].append((caso, motivo_pg))
            print(f"[REJEITO/postgres] {caso}: {motivo_pg}")

    if conn:
        conn.close()

    print("\n--- resumo ---")
    print(f"carregados: {len(resultado['carregados'])}")
    print(f"rejeitados: {len(resultado['rejeitados'])}")
    for caso, motivo in resultado["rejeitados"]:
        print(f"  - {caso}: {motivo}")

    return resultado


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Smoke test do pipeline de EVENTO (AFASTAMENTO).")
    parser.add_argument("--dry-run", action="store_true", help="Nao escreve no banco; so mostra decisao.")
    args = parser.parse_args()

    try:
        roda(dry_run=args.dry_run)
    except psycopg2.OperationalError as e:
        print(f"Erro de conexao ao Postgres: {e}", file=sys.stderr)
        print("Confirme .env (PGHOST/PGPORT/PGDATABASE/PGUSER/PGPASSWORD) e se o schema/seed ja rodaram.", file=sys.stderr)
        sys.exit(1)
