#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Validador do replay-de-intervalo (ADR-008) contra o Postgres REAL.

Substitui a leitura por-evento dos smoke tests da sessao 2026-07-04: AFASTAMENTO
e CESSAO nao transitam situacao_funcional por transicao — sao INTERVALOS
[data_inicio, data_fim] do payload, resolvidos contra a data de referencia:
  (a) CEDIDO / afastado-vigente derivam de data_inicio <= ref <= data_fim
      (data_fim nula = em aberto; a intercorrencia EXPIRA por data, nao por
      evento de retorno);
  (b) coalescencia por chave (cod_tipo_evento, data_inicio) — o par
      aberto+fechamento do 2o registro colapsa e a data_carga mais recente vence;
  (c) fim de cessao devolve a origem SEM evento — o intervalo expira sozinho.

A REFERENCIA da logica e a funcao replay() do gerador_eventos.py (provada la
com --valida antes de tocar o banco). Este modulo reimplementa a MESMA logica
lendo da tabela `evento` particionada e compara com a FOTO projetada pelo
gerador (foto_projetada.csv). Se os dois baterem, a premissa ADR-008 esta
provada TAMBEM na volta do banco — encanamento completo: CSV -> \\copy ->
particao por carga -> replay -> FOTO.

Contrato NUCLEO (o mesmo do --valida do gerador): situacao_funcional.
Checks ESTENDIDOS (alem da referencia, todos reconstruiveis dos eventos):
  - cod_afastamento_vigente  (1o intervalo de AFASTAMENTO contendo a ref)
  - funcao_comissionada      (ultimo ALTERACAO_FUNCAO: designacao|dispensa)
  - classe/padrao            (ultimo PROGRESSAO a partir de A/I)
Lotacao NAO e reconstruivel (PROVIMENTO nao carrega unidade no payload;
ALTERACAO_FUNCAO com muda_unidade troca lotacao sem evento) — fica fora.

O mapa motivo->situacao NAO e hardcoded: vem de dom_motivo_deslig
(situacao_resultante), que e DADO de dominio — schema v0.8 / seed v0.2 §12.

Uso:
    python valida_replay_intervalo.py                 # so carga_base (default)
    python valida_replay_intervalo.py --incluir-lixo  # base + carga_lixo:
        o lixo (duplicatas bem-formadas) PASSA LIMPO pelo replay — e a tese
        da ADR-009: a superficie de deteccao e o manifesto/painel, nao a
        validacao; por isso a retirada e por CARGA (detach), nunca por linha.
    python valida_replay_intervalo.py --nucleo-so     # so situacao_funcional
    python valida_replay_intervalo.py --corte-futuro  # data_evento <= ref

ATENCAO --corte-futuro: o replay de REFERENCIA nao filtra fato futuro, e a
massa v1 (seed 20260705) depende disso — 21 segundos-vinculos do arquetipo
Bruno Vespertilio tem PROVIMENTO DEPOIS da data_base (2027..2030) e mesmo
assim entram ATIVOS na foto. Com o corte ligado, esses 21 caem do universo
(achado de qualidade do gerador v1, nao do encanamento — candidato a clamp
do inicia_apos_anos no gerador v1.1).

Le credenciais de loader/.env (env real do sistema tem prioridade).
"""

import argparse
import csv
import json
import os
import sys
from datetime import date

import psycopg2
import psycopg2.extras


# ── conexao (mesma vara de pescar dos smoke tests / carrega_foto) ────────────
def carrega_env(path=os.path.join("loader", ".env")):
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


# ── replay de intervalo (porta fiel do replay() do gerador_eventos.py) ───────
def replay(eventos, data_ref, motivo_situacao):
    """
    Reconstroi o estado de UMA matricula em data_ref pela logica de INTERVALO
    + coalescencia. `eventos` ja vem ordenado por (data_evento, data_carga,
    id_evento) — a atribuicao de dict faz o registro de MAIOR data_carga
    vencer na chave de coalescencia (o fechamento vem depois do aberto).
    """
    sit = None
    aberto = {}                       # (tipo, data_inicio) -> payload
    funcao, classe, padrao = None, "A", "I"
    for e in eventos:
        t, pl = e["cod_tipo_evento"], e["payload"]
        if t == "PROVIMENTO":
            sit = "ATIVO"
        elif t == "DESLIGAMENTO":
            sit = motivo_situacao[pl["cod_motivo_deslig"]]
        elif t == "RETORNO_VINCULO":
            sit = "ATIVO"
        elif t in ("CESSAO", "AFASTAMENTO"):
            aberto[(t, pl["data_inicio"])] = pl     # coalescencia: ultimo vence
        elif t == "ALTERACAO_FUNCAO":
            funcao = pl.get("cod_funcao") if pl.get("tipo_movimento") == "designacao" else None
        elif t == "PROGRESSAO":
            classe = pl.get("classe_destino") or classe
            padrao = pl.get("padrao_destino") or padrao
        # REMOCAO / FECHAMENTO_FOLHA: ignorados de proposito (nao mudam estado)

    intervalos = {"CESSAO": [], "AFASTAMENTO": []}
    for (t, ini), pl in aberto.items():
        fim = pl.get("data_fim")
        intervalos[t].append((date.fromisoformat(ini),
                              date.fromisoformat(fim) if fim else date.max,
                              pl.get("cod_afastamento")))

    # afastamento vigente: 1o intervalo (por data_inicio) que contem a ref
    afast = next((cod for a, b, cod in sorted(intervalos["AFASTAMENTO"])
                  if a <= data_ref <= b), None)

    # situacao derivada (decisao #5, convencao da foto canonica): sobre base ATIVO,
    # cessao vigente -> CEDIDO; afast 31 vigente -> DISPONIBILIDADE. Precedencia:
    # cessao antes de disponibilidade.
    if sit == "ATIVO":
        if any(a <= data_ref <= b for a, b, _ in intervalos["CESSAO"]):
            sit = "CEDIDO"           # derivado, nunca evento; expira sozinho
        elif afast == "31":
            sit = "DISPONIBILIDADE"
    if sit not in ("ATIVO", "CEDIDO", "DISPONIBILIDADE"):
        afast, funcao = None, None    # mesmo corte da projecao do gerador
    return {"situacao_funcional": sit, "cod_afastamento_vigente": afast,
            "funcao_comissionada": funcao, "classe": classe, "padrao": padrao}


# ── leitura do banco ─────────────────────────────────────────────────────────
def busca_eventos(conn, ids_carga, data_ref, corte_futuro=False):
    """
    Puxa os eventos das cargas pedidas ja na ordem do replay. Por fidelidade
    a referencia NAO se corta fato futuro por default (ver ATENCAO no topo);
    FECHAMENTO_FOLHA fica fora por ser aditivo (nao transita estado).
    """
    por_mat = {}
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(
            """
            SELECT matricula_funcional, cod_tipo_evento, payload
              FROM evento
             WHERE id_carga = ANY(%s::uuid[])
               AND cod_tipo_evento <> 'FECHAMENTO_FOLHA'
               AND (NOT %s OR data_evento <= %s)
             ORDER BY matricula_funcional, data_evento, data_carga, id_evento
            """,
            (ids_carga, corte_futuro, data_ref),
        )
        for row in cur:
            por_mat.setdefault(row["matricula_funcional"], []).append(row)
    return por_mat


def carrega_motivos(conn):
    """dom_motivo_deslig.situacao_resultante — o mapa e DADO, nao codigo."""
    with conn.cursor() as cur:
        cur.execute("SELECT cod_motivo_deslig, situacao_resultante FROM dom_motivo_deslig")
        return dict(cur.fetchall())


# ── comparacao com a FOTO projetada ──────────────────────────────────────────
CAMPOS_NUCLEO = ["situacao_funcional"]
CAMPOS_EXTRA = ["cod_afastamento_vigente", "funcao_comissionada", "classe", "padrao"]


def main():
    ap = argparse.ArgumentParser(description="Replay ADR-008 contra o Postgres real")
    ap.add_argument("--cargas", default=os.path.join("gerador", "out", "cargas.json"))
    ap.add_argument("--foto", default=os.path.join("gerador", "out", "servidor.csv"))
    ap.add_argument("--data-ref", default=None, help="default: data_base do cargas.json")
    ap.add_argument("--incluir-lixo", action="store_true",
                    help="replaya base+lixo (prova ADR-009: lixo passa limpo)")
    ap.add_argument("--nucleo-so", action="store_true",
                    help="compara so situacao_funcional (contrato da referencia)")
    ap.add_argument("--corte-futuro", action="store_true",
                    help="filtra data_evento <= ref (a referencia NAO corta; ver docstring)")
    a = ap.parse_args()

    manifesto = json.load(open(a.cargas, encoding="utf-8"))
    data_ref = date.fromisoformat(a.data_ref or manifesto["data_base"])
    ids = [manifesto["cargas"]["carga_base"]["id_carga"]]
    if a.incluir_lixo:
        ids.append(manifesto["cargas"]["carga_lixo"]["id_carga"])

    with open(a.foto, encoding="utf-8", newline="") as f:
        foto = {r["matricula_funcional"]: r for r in csv.DictReader(f)}

    conn = conecta(carrega_env())
    try:
        motivos = carrega_motivos(conn)
        por_mat = busca_eventos(conn, ids, data_ref, a.corte_futuro)
    finally:
        conn.close()

    # o universo de matriculas do banco tem de ser EXATAMENTE o da foto
    so_banco = sorted(set(por_mat) - set(foto))
    so_foto = sorted(set(foto) - set(por_mat))
    for m in so_banco[:5]:
        print(f"[DIVERGE/universo] {m}: no banco, fora da foto")
    for m in so_foto[:5]:
        print(f"[DIVERGE/universo] {m}: na foto, sem eventos no banco")

    campos = CAMPOS_NUCLEO if a.nucleo_so else CAMPOS_NUCLEO + CAMPOS_EXTRA
    div_nucleo, div_extra, mostradas = 0, 0, 0
    for mat in sorted(set(foto) & set(por_mat)):
        r = replay(por_mat[mat], data_ref, motivos)
        for campo in campos:
            esperado = foto[mat][campo] or None      # celula vazia do CSV = None
            obtido = r[campo]
            if obtido != esperado:
                if campo in CAMPOS_NUCLEO:
                    div_nucleo += 1
                else:
                    div_extra += 1
                if mostradas < 10:
                    print(f"[DIVERGE/{campo}] {mat} ({foto[mat]['arquetipo']}): "
                          f"replay={obtido!r} foto={esperado!r}")
                    mostradas += 1

    universo = len(so_banco) + len(so_foto)
    rotulo = "base+lixo" if a.incluir_lixo else "carga_base"
    print(f"[valida-pg] replay-de-intervalo ({rotulo}, ref={data_ref}) vs FOTO projetada: "
          f"{len(foto)} vinculos | nucleo: {div_nucleo} divergencias"
          + ("" if a.nucleo_so else f" | estendido: {div_extra}")
          + f" | universo: {universo}")
    sys.exit(1 if (div_nucleo or div_extra or universo) else 0)


if __name__ == "__main__":
    try:
        main()
    except psycopg2.OperationalError as e:
        print(f"Sem conexao com o Postgres ({e}).\nConfira loader/.env e se o schema v0.8 + cargas foram aplicados.")
        sys.exit(1)
