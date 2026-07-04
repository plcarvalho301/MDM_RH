"""
Gerador descartavel — popula uma trajetoria de eventos pro Filme do Servidor.
Objetivo unico: ter volume o suficiente pra testar se o replay ordena por
data_evento corretamente (nao pela ordem de insercao). Por isso insere em
ordem EMBARALHADA de proposito.

Uso:
    python gera_filme_servidor.py                       # 30 eventos, matricula 5000001, 2005-2024
    python gera_filme_servidor.py --matricula 5000001 --cpf 10000000001 --n 30 --ano-ini 2005 --ano-fim 2024
"""
import argparse
import json
import random
from datetime import date, timedelta

import psycopg2


def carrega_env(path="loader/.env"):
    env = {}
    with open(path, encoding="utf-8") as f:
        for linha in f:
            linha = linha.strip()
            if not linha or linha.startswith("#") or "=" not in linha:
                continue
            k, v = linha.split("=", 1)
            env[k.strip()] = v.strip()
    return env


def data_aleatoria(rnd, ano_ini, ano_fim):
    ini = date(ano_ini, 1, 1)
    fim = date(ano_fim, 12, 31)
    delta_dias = (fim - ini).days
    return ini + timedelta(days=rnd.randint(0, delta_dias))


AFASTAMENTOS = ["01", "03", "07", "06", "15", "10", "05", "40", "24", "29"]

def gera_payload(rnd, tipo, dt):
    if tipo == "AFASTAMENTO":
        dias = rnd.randint(5, 90)
        return {
            "cod_afastamento": rnd.choice(AFASTAMENTOS),
            "data_inicio": dt.isoformat(),
            "data_fim": (dt + timedelta(days=dias)).isoformat(),
        }
    if tipo == "PROVIMENTO":
        return {"cargo": "EPPGG", "classe": rnd.choice(["A", "B", "C"]), "padrao": rnd.choice(["I", "II", "III"])}
    if tipo == "ALTERACAO_FUNCAO":
        return {"funcao_anterior": None, "funcao_nova": f"FCE 1.{rnd.randint(1,15):02d}"}
    if tipo == "CESSAO":
        return {"orgao_destino": f"ORGAO_{rnd.randint(1,20):03d}", "data_inicio": dt.isoformat()}
    if tipo == "REMOCAO":
        return {"unidade_origem": rnd.randint(1001, 1030), "unidade_destino": rnd.randint(1001, 1030)}
    if tipo == "RETORNO_VINCULO":
        return {"motivo_retorno": "fim_afastamento"}
    if tipo == "FECHAMENTO_FOLHA":
        return {"competencia": f"{dt.year}-{dt.month:02d}", "valor_liquido": round(rnd.uniform(4000, 12000), 2)}
    if tipo == "DESLIGAMENTO":
        return {"motivo": "exoneracao_a_pedido"}
    return {}


TIPOS = ["AFASTAMENTO", "ALTERACAO_FUNCAO", "CESSAO", "REMOCAO",
         "RETORNO_VINCULO", "FECHAMENTO_FOLHA"]


def gera_eventos(matricula, cpf, n, ano_ini, ano_fim, seed=42):
    rnd = random.Random(seed)
    eventos = []
    # 1o evento sempre PROVIMENTO no inicio da janela (admissao)
    eventos.append((data_aleatoria(rnd, ano_ini, ano_ini + 1), "PROVIMENTO"))
    for _ in range(n - 1):
        eventos.append((data_aleatoria(rnd, ano_ini, ano_fim), rnd.choice(TIPOS)))
    rnd.shuffle(eventos)  # ordem de INSERCAO embaralhada -- testa que o replay ordena por data, nao por insercao
    return [
        {
            "matricula_funcional": matricula, "cpf": cpf,
            "cod_tipo_evento": tipo, "data_evento": dt.isoformat(),
            "payload": gera_payload(rnd, tipo, dt),
            "cod_mecanica": "ingestao", "fonte": "API_SIAPE_OCORRENCIAS",
            "grau_confianca": "alto",
        }
        for dt, tipo in eventos
    ]


def carrega(matricula, cpf, n, ano_ini, ano_fim):
    env = carrega_env()
    conn = psycopg2.connect(
        host=env.get("PGHOST", "localhost"), port=env.get("PGPORT", "5432"),
        dbname=env.get("PGDATABASE", "mdm_rh"), user=env.get("PGUSER", "postgres"),
        password=env.get("PGPASSWORD", ""),
    )
    conn.autocommit = False
    eventos = gera_eventos(matricula, cpf, n, ano_ini, ano_fim)
    with conn.cursor() as cur:
        for ev in eventos:
            cur.execute(
                """
                INSERT INTO evento
                    (matricula_funcional, cpf, cod_tipo_evento, data_evento,
                     payload, cod_mecanica, fonte, grau_confianca)
                VALUES (%(matricula_funcional)s, %(cpf)s, %(cod_tipo_evento)s,
                        %(data_evento)s, %(payload)s::jsonb, %(cod_mecanica)s,
                        %(fonte)s, %(grau_confianca)s)
                """,
                {**ev, "payload": json.dumps(ev["payload"])},
            )
    conn.commit()
    conn.close()
    print(f"{len(eventos)} eventos inseridos para matricula {matricula}, "
          f"datas entre {ano_ini} e {ano_fim} (ordem de insercao embaralhada).")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--matricula", default="5000001")
    ap.add_argument("--cpf", default="10000000001")
    ap.add_argument("--n", type=int, default=30)
    ap.add_argument("--ano-ini", type=int, default=2005)
    ap.add_argument("--ano-fim", type=int, default=2024)
    args = ap.parse_args()
    carrega(args.matricula, args.cpf, args.n, args.ano_ini, args.ano_fim)
