#!/usr/bin/env python3
"""
beta_gen_foto.py — encanamento MINIMO do beta (eixo FOTO).
Gera N fotos fake VALIDAS contra as constraints de `servidor` e insere.
NAO e o gen_massa.py do projeto (que nao esta neste corpus) — e o teste
funcional isolado do fluxo FOTO -> servidor -> vw_foto -> (Power BI).

Criterio de sucesso (o que voce pediu): inserir N fotos e ver linha em vw_foto.
Se entrar 20 e vw_foto devolver 0, o encanamento esta quebrado — este script
falha alto nesse caso, nao silencioso.

Depende so de: psycopg2-binary, .env (DATABASE_URL ou PG* vars).
"""
import os
import sys
import random
import argparse
import psycopg2

# --- valores validos extraidos do seed_dominios.sql (FKs reais do schema) ---
SITUACAO   = ["ATIVO", "ATIVO", "ATIVO", "CEDIDO", "DISPONIBILIDADE"]  # peso p/ ATIVO
REGIME     = ["RJU", "RJU", "CLT"]
AFASTAMENTO = ["01", "03", "07", "06", "15", "10", "05", "40", "24", "29"]
CARGO      = ["EPPGG"]
CLASSE     = ["A", "B", "C", "ESPECIAL"]
PADRAO     = ["I", "II", "III", "IV", "V"]
NIVEL      = ["NS", "NI", "NA"]
# unidades: mix de validas (existem em dom_unidade_eorg se seed popular) e orfas
# nota: lotacao NAO tem FK de proposito (orfao = KR 2.1), entao qualquer int passa.
UORG       = [1, 2, 3, 10, 20, 999_001, 999_002]  # 999_xxx = candidatos a orfao


def rand_cpf():
    return "".join(str(random.randint(0, 9)) for _ in range(11))


def rand_matricula(used):
    while True:
        m = "".join(str(random.randint(0, 9)) for _ in range(7))
        if m not in used:
            used.add(m)
            return m


def rand_date(y0, y1):
    y = random.randint(y0, y1)
    mo = random.randint(1, 12)
    d = random.randint(1, 28)
    return f"{y:04d}-{mo:02d}-{d:02d}"


def gen_one(used):
    afastado = random.random() < 0.15  # ~15% afastados p/ o booleano ter os dois valores
    return {
        "matricula_funcional": rand_matricula(used),
        "cpf": rand_cpf(),
        "nome": f"Servidor Fake {random.randint(1000,9999)}",
        "data_nascimento": rand_date(1960, 1998),
        "cargo": random.choice(CARGO),
        "classe": random.choice(CLASSE),
        "padrao": random.choice(PADRAO),
        "sigla_nivel_cargo": random.choice(NIVEL),
        "funcao_comissionada": None if random.random() < 0.6 else f"FCE-{random.randint(1,4)}{random.randint(1,18):02d}",
        "nova_funcao": None,
        "data_ingresso_nova_funcao": None,
        "cod_unidade_lotacao": random.choice(UORG),
        "cod_unidade_exercicio": random.choice(UORG),
        "origem_unidade": random.choice(["SIAPE", "SIORG"]),
        "situacao_funcional": random.choice(SITUACAO),
        "regime_juridico": random.choice(REGIME),
        "data_exercicio_no_orgao": rand_date(2000, 2024),
        "cod_afastamento_vigente": random.choice(AFASTAMENTO) if afastado else None,
        "data_referencia": rand_date(2026, 2026),
        "cod_mecanica": "ingestao",
    }


INSERT = """
INSERT INTO servidor (
    matricula_funcional, cpf, nome, data_nascimento,
    cargo, classe, padrao, sigla_nivel_cargo,
    funcao_comissionada, nova_funcao, data_ingresso_nova_funcao,
    cod_unidade_lotacao, cod_unidade_exercicio, origem_unidade,
    situacao_funcional, regime_juridico, data_exercicio_no_orgao,
    cod_afastamento_vigente, data_referencia, cod_mecanica
) VALUES (
    %(matricula_funcional)s, %(cpf)s, %(nome)s, %(data_nascimento)s,
    %(cargo)s, %(classe)s, %(padrao)s, %(sigla_nivel_cargo)s,
    %(funcao_comissionada)s, %(nova_funcao)s, %(data_ingresso_nova_funcao)s,
    %(cod_unidade_lotacao)s, %(cod_unidade_exercicio)s, %(origem_unidade)s,
    %(situacao_funcional)s, %(regime_juridico)s, %(data_exercicio_no_orgao)s,
    %(cod_afastamento_vigente)s, %(data_referencia)s, %(cod_mecanica)s
)
ON CONFLICT (matricula_funcional) DO UPDATE SET
    situacao_funcional = EXCLUDED.situacao_funcional,
    cod_afastamento_vigente = EXCLUDED.cod_afastamento_vigente,
    data_referencia = EXCLUDED.data_referencia;
"""


def conn_from_env():
    url = os.environ.get("DATABASE_URL")
    if url:
        return psycopg2.connect(url)
    return psycopg2.connect(
        host=os.environ.get("PGHOST", "localhost"),
        port=os.environ.get("PGPORT", "5432"),
        dbname=os.environ.get("PGDATABASE", "mdm"),
        user=os.environ.get("PGUSER", "postgres"),
        password=os.environ.get("PGPASSWORD", ""),
    )


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("-n", type=int, default=20, help="quantas fotos gerar (default 20)")
    ap.add_argument("--dry-run", action="store_true", help="gera e imprime, nao insere")
    args = ap.parse_args()

    used = set()
    rows = [gen_one(used) for _ in range(args.n)]

    if args.dry_run:
        for r in rows[:3]:
            print(r)
        print(f"... [{args.n} fotos geradas, dry-run — nada inserido]")
        return

    conn = conn_from_env()
    conn.autocommit = False
    cur = conn.cursor()
    for r in rows:
        cur.execute(INSERT, r)
    conn.commit()

    # verificacao de ponta-a-ponta: a view de exposicao enxerga o que entrou?
    cur.execute("SELECT count(*) FROM servidor;")
    n_serv = cur.fetchone()[0]
    cur.execute("SELECT count(*) FROM vw_foto;")
    n_view = cur.fetchone()[0]
    cur.execute("SELECT count(*) FROM vw_foto WHERE afastado;")
    n_afast = cur.fetchone()[0]
    cur.close()
    conn.close()

    print(f"servidor: {n_serv} linhas | vw_foto: {n_view} linhas | afastados: {n_afast}")
    if n_view == 0:
        print("FALHA: vw_foto vazia apos inserir fotos — encanamento quebrado.", file=sys.stderr)
        sys.exit(1)
    if n_view != n_serv:
        print(f"AVISO: vw_foto ({n_view}) != servidor ({n_serv}) — a view filtra algo inesperado.", file=sys.stderr)
        sys.exit(2)
    print("OK: FOTO -> servidor -> vw_foto fecha. Aponte o Power BI em vw_foto / vw_lente.")


if __name__ == "__main__":
    main()
