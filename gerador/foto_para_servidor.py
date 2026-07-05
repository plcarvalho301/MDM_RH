#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Ponte foto_projetada.csv -> servidor.csv (carga da FOTO a partir dos EVENTOS).

CONTEXTO / DIVIDA TECNICA CONHECIDA: nesta PoC os eventos foram gerados
trajetoria-primeiro (gerador_eventos.py) e a FOTO saiu como PROJECAO deles
(foto_projetada.csv). O natural seria o inverso — gerar eventos a partir de uma
FOTO de servidores ativos. Fica para corrigir depois; por ora esta ponte
materializa a `servidor` a partir da foto projetada para destravar o Power BI,
mantendo as matriculas EM SINCRONIA com os eventos ja carregados no banco.

O foto_projetada.csv nao tem as colunas NOT NULL `data_nascimento` e
`origem_unidade` (o gerador de eventos nunca precisou delas). Esta ponte as
COMPLETA de forma FICTICIA e DETERMINISTICA (funcao da matricula — reproduzivel,
sem RNG global), sem inventar nada que o replay ja prova: cargo, classe, padrao,
funcao, lotacao, situacao e afastamento vigente vem VERBATIM da foto projetada.

Saida: servidor.csv com as 20 colunas que loader/carrega_foto.py espera.
Uso:   python foto_para_servidor.py [--foto foto_projetada.csv] [--out servidor.csv]
"""

import argparse
import csv
import hashlib
from datetime import date, timedelta

# colunas que o loader espera, na ordem do INSERT (carrega_foto.COLS_SERVIDOR)
COLS = [
    "matricula_funcional", "cpf", "nome", "data_nascimento", "cargo", "classe",
    "padrao", "sigla_nivel_cargo", "funcao_comissionada", "nova_funcao",
    "data_ingresso_nova_funcao", "cod_unidade_lotacao", "cod_unidade_exercicio",
    "origem_unidade", "situacao_funcional", "regime_juridico",
    "data_exercicio_no_orgao", "cod_afastamento_vigente", "data_referencia",
    "cod_mecanica",
]


def _det(matricula, salt, lo, hi):
    """Inteiro deterministico em [lo, hi] a partir da matricula (sem RNG global)."""
    h = hashlib.sha256(f"{salt}:{matricula}".encode()).hexdigest()
    return lo + int(h, 16) % (hi - lo + 1)


def data_nascimento_ficticia(matricula, data_ref):
    """
    Idade plausivel de servidor: 25..70 anos na data de referencia.
    Ficticia e deterministica; nao ha data de nascimento reconstruivel dos
    eventos (PROVIMENTO nao carrega idade), entao e um preenchimento honesto,
    marcado como tal.
    """
    idade = _det(matricula, "idade", 25, 70)
    dias = _det(matricula, "dia", 0, 364)
    return data_ref.replace(year=data_ref.year - idade) - timedelta(days=dias)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--foto", default="foto_projetada.csv")
    ap.add_argument("--out", default="servidor.csv")
    a = ap.parse_args()

    with open(a.foto, encoding="utf-8", newline="") as f:
        linhas = list(csv.DictReader(f))

    with open(a.out, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=COLS)
        w.writeheader()
        for r in linhas:
            mat = r["matricula_funcional"]
            data_ref = date.fromisoformat(r["data_referencia"])
            w.writerow({
                # --- verbatim da foto projetada (o que o replay prova) ---
                "matricula_funcional": mat,
                "cpf": r["cpf"],
                "nome": r["nome"],
                "cargo": r["cargo"],
                "classe": r["classe"],
                "padrao": r["padrao"],
                "funcao_comissionada": r["funcao_comissionada"],   # '' = None no loader
                "cod_unidade_lotacao": r["cod_unidade_lotacao"],
                "situacao_funcional": r["situacao_funcional"],
                "cod_afastamento_vigente": r["cod_afastamento_vigente"],
                "data_referencia": r["data_referencia"],
                # --- completado ficticio deterministico (NOT NULL que faltavam) ---
                "data_nascimento": data_nascimento_ficticia(mat, data_ref).isoformat(),
                "origem_unidade": "ORGAO_PROPRIO",
                # --- constantes coerentes com a massa (RJU; extracao) ---
                "regime_juridico": "RJU",
                "cod_mecanica": "extracao",
                # --- exercicio = lotacao por default (sem cessao de exercicio na foto) ---
                "cod_unidade_exercicio": r["cod_unidade_lotacao"],
                # --- nullable sem fonte na foto: vazio (loader converte '' -> None) ---
                "sigla_nivel_cargo": "",
                "nova_funcao": "",
                "data_ingresso_nova_funcao": "",
                "data_exercicio_no_orgao": "",
            })
    print(f"gerado {a.out}: {len(linhas)} linhas (data_nascimento/origem_unidade FICTICIOS)")


if __name__ == "__main__":
    main()
