#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# =============================================================================
# MDM-RH — CONECTOR SIAPE (Card 6) — consome o envelope SOAP das APIs SIAPE
# Ancoras: siape_envelope.py (contrato), 6_spec_conectores_siape_v0_2.md,
#          3_depara_soap_conectores_v0_2.md, ADR-014 (carimbo), ADR-009 (quarentena).
# -----------------------------------------------------------------------------
# O lado CONSUMIDOR do contrato. Dois conectores, um por face (eixos ortogonais
# FOTO x EVENTO):
#   A. consultaDadosFuncionais  -> colunas FOTO  (saida == servidor.csv de entrada)
#   B. consultaDadosAfastamento -> eventos AFASTAMENTO (carimbo ADR-014)
#
# O MESMO conector serve o teste (a/b, XML do emissor, offline) e o go-live (c/d,
# retorno real da SERPRO) — a API so troca a ORIGEM do XML, nao o parser. Por isso
# o parse e agnostico a namespace (casa por local-name): resiste ao prefixo que a
# SERPRO escolher. Sem validacao de token no loop (auth registrada p/ conector real).
#
# Degradacao graciosa (ADR-009): linha defeituosa vai p/ quarentena (rejeito),
# loga, NAO aborta a carga — mesmo destino do 'valida' no DAG de ingestao.
#
# Uso (a partir da raiz do repo):
#   py -3 -m pipeline.conectores.conector_siape funcionais  [--xml ...] [--out ...]
#   py -3 -m pipeline.conectores.conector_siape afastamento [--xml ...] [--out ...]
# =============================================================================
import argparse
import csv
import json
import os
import sys
import uuid
import xml.etree.ElementTree as ET

from pipeline.contrato import siape_envelope as env

# Carga de ingestao (deterministica p/ reprodutibilidade — o id_carga real vem do DAG).
ID_CARGA_INGESTAO = str(uuid.uuid5(uuid.NAMESPACE_URL, "WS_SIAPE:consultaDadosAfastamentoHistorico"))
DATA_CARGA_INGESTAO = "2026-07-07T09:00:00+00:00"

COLS_EVENTO = ["id_evento", "id_carga", "matricula_funcional", "cpf", "cod_tipo_evento",
               "data_evento", "payload", "cod_mecanica", "fonte", "grau_confianca", "data_carga"]


class LinhaRejeitada(Exception):
    """Defeito material: linha vai p/ quarentena (rejeito), nao aborta a carga."""
    def __init__(self, motivo, dados=None):
        super().__init__(motivo)
        self.motivo, self.dados = motivo, dados


# ── Primitivas de leitura (agnosticas a namespace) ───────────────────────────
def _local(tag):
    return tag.split("}", 1)[-1]


def _filhos_texto(elem):
    """{local_name: texto} + conjunto de tags presentes (distingue ausente x vazia)."""
    d, presentes = {}, set()
    for c in elem:
        ln = _local(c.tag)
        presentes.add(ln)
        d[ln] = (c.text or "")
    return d, presentes


def _envelopes(xml_texto):
    raiz = ET.fromstring(xml_texto)
    if _local(raiz.tag) == "Envelope":
        yield raiz
        return
    for env_el in raiz:
        if _local(env_el.tag) == "Envelope":
            yield env_el


def _itera(envelope, nome_registro):
    """Cada <nome_registro> do envelope (DadosFuncionais/DadosAfastamento),
    independente da profundidade/prefixo do wrapper."""
    for el in envelope.iter():
        if _local(el.tag) == nome_registro:
            yield el


def _cpf_envelope(envelope):
    """CPF da resposta: consultaDadosAfastamento/Financeiros e listaContribuicoesPSS
    sao consultas POR-CPF (1 resposta = 1 CPF). O CPF nao vem no payload do evento
    (a chave e a matricula), so na resposta — o conector o carimba em cada evento
    (evento.cpf e denormalizado p/ agregacao, ck_ev_cpf exige 11 digitos). So digitos."""
    for el in envelope.iter():
        if _local(el.tag) == "cpf":
            return "".join(ch for ch in (el.text or "") if ch.isdigit())
    return ""


# ── Conector A: consultaDadosFuncionais -> FOTO ──────────────────────────────
def _le_dados_funcionais(elem):
    """<DadosFuncionais> -> linha FOTO (14 colunas). Degradacao graciosa: tag
    obrigatoria ausente / data mal-formada / cpf invalido -> LinhaRejeitada."""
    d, presentes = _filhos_texto(elem)
    for tag in env.TAGS_OBRIGATORIAS:
        if tag not in presentes:
            raise LinhaRejeitada(f"tag obrigatoria ausente: {tag}", d)
    row = {}
    for col, tag, kind in env.FUNCIONAIS:
        if kind == "sit":
            cod = (d.get("codSitFuncional") or "").strip()
            if cod and cod not in env.COD_TO_SIT:
                raise LinhaRejeitada(f"codSitFuncional desconhecido: {cod!r}", d)
            row[col] = env.COD_TO_SIT.get(cod, "") if cod else ""
            continue
        if kind == "cpf":
            # contrato: so digitos. Normaliza mascara (123.456.789-01 -> 12345678901);
            # se nao restarem 11 digitos, rejeita (degradacao graciosa).
            dig = "".join(ch for ch in (d.get(tag, "") or "") if ch.isdigit())
            if len(dig) != 11:
                raise LinhaRejeitada(f"cpf invalido (contrato: 11 digitos): {d.get(tag)!r}", d)
            row[col] = dig
            continue
        v = d.get(tag, "")
        try:
            if kind == "date":
                v = env.ddmmyyyy_para_iso(v)
            elif kind == "uorg":
                v = env.uorg_le(v)
            else:
                v = (v or "").strip()
        except ValueError as e:
            raise LinhaRejeitada(str(e), d)
        row[col] = v
    if not (row["matricula_funcional"] or "").isdigit():
        raise LinhaRejeitada(f"matricula nao-numerica: {row['matricula_funcional']!r}", d)
    return row


def parse_funcionais(xml_texto):
    """Conector A: XML consultaDadosFuncionais -> (linhas_foto, rejeitos)."""
    linhas, rejeitos = [], []
    for envelope in _envelopes(xml_texto):
        for elem in _itera(envelope, "DadosFuncionais"):
            try:
                linhas.append(_le_dados_funcionais(elem))
            except LinhaRejeitada as r:
                rejeitos.append({"motivo": r.motivo, "dados": r.dados})
    return linhas, rejeitos


# ── Conector B: consultaDadosAfastamentoHistorico §4.21 -> evento AFASTAMENTO ─
def _uuid_evento(mat, cod, data_inicio):
    """id_evento deterministico (uuid5) — reprodutivel entre execucoes."""
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"afastamento:{mat}|{cod}|{data_inicio}"))


def parse_afastamento(xml_texto, id_carga=ID_CARGA_INGESTAO, data_carga=DATA_CARGA_INGESTAO):
    """Conector B: XML §4.21 -> (eventos AFASTAMENTO, rejeitos). Carimbo ADR-014.
    Alimenta a tabela evento pelo mesmo pipeline (valida->classifica->particao)."""
    eventos, rejeitos = [], []
    for envelope in _envelopes(xml_texto):
        cpf_env = _cpf_envelope(envelope)
        for elem in _itera(envelope, "DadosAfastamento"):
            d, _presentes = _filhos_texto(elem)
            mat = (d.get("grMatricula") or "").strip()
            cod = (d.get("codOcorrencia") or "").strip()
            try:
                if not mat.isdigit():
                    raise LinhaRejeitada(f"grMatricula nao-numerica: {mat!r}", d)
                if len(cpf_env) != 11:
                    raise LinhaRejeitada(f"cpf da resposta invalido: {cpf_env!r}", d)
                ini = env.ddmmyyyy_para_iso(d.get("dataIni", ""))
                fim = env.ddmmyyyy_para_iso(d.get("dataFim", ""))
                if not ini:
                    raise LinhaRejeitada("dataIni ausente/vazia (obrigatoria)", d)
            except ValueError as e:
                rejeitos.append({"motivo": str(e), "dados": d})
                continue
            except LinhaRejeitada as r:
                rejeitos.append({"motivo": r.motivo, "dados": r.dados})
                continue
            # data_fim vazia = intervalo aberto -> null no payload (NAO ""): a MV
            # mv_filme_servidor faz (payload->>'data_fim')::date, e ''::date explode; null::date ok.
            payload = {"cod_afastamento": cod, "data_inicio": ini, "data_fim": fim or None}
            eventos.append({
                "id_evento": _uuid_evento(mat, cod, ini),
                "id_carga": id_carga,
                "matricula_funcional": mat,
                "cpf": cpf_env,  # do envelope (resposta por-CPF); chave da serie e a matricula
                "cod_tipo_evento": "AFASTAMENTO",
                "data_evento": ini,
                "payload": json.dumps(payload, ensure_ascii=False),
                "cod_mecanica": env.CARIMBO_AFASTAMENTO["cod_mecanica"],
                "fonte": env.CARIMBO_AFASTAMENTO["fonte"],
                "grau_confianca": env.CARIMBO_AFASTAMENTO["grau_confianca"],
                "data_carga": data_carga,
            })
    return eventos, rejeitos


# ── Coercao de tipo (regra de valor §4.1: e do conector, nao do de-para) ─────
def _coage(v, kind):
    v = (v or "").strip()
    if not v:
        return None
    if kind == "int":
        return int(v)
    if kind == "num":
        return float(v)
    return v


def _data_evento_comp(ano, mes):
    """Competencia (ano,mes) -> data_evento = 1o dia do mes seguinte (ISO), como o
    gerador emite (add_meses(competencia, 1)). O envelope carrega so a competencia."""
    a, m = int(ano), int(mes)
    a2, m2 = (a + 1, 1) if m == 12 else (a, m + 1)
    return f"{a2:04d}-{m2:02d}-01"


# ── Conector C: consultaDadosFinanceirosHistorico §4.20 -> FECHAMENTO_FOLHA ───
def parse_financeiro(xml_texto, id_carga=ID_CARGA_INGESTAO, data_carga=DATA_CARGA_INGESTAO):
    """Conector C: XML §4.20 -> (eventos FECHAMENTO_FOLHA, rejeitos). Carimbo CARIMBO_FOLHA.
    1 <ArrayDadosFinanceiros> = 1 (vinculo, competencia); rubricas aninhadas."""
    eventos, rejeitos = [], []
    for envelope in _envelopes(xml_texto):
        cpf_env = _cpf_envelope(envelope)
        for arr in _itera(envelope, "ArrayDadosFinanceiros"):
            d, _pres = _filhos_texto(arr)
            mat = (d.get("matricula") or "").strip()
            comp = (d.get("mesAnoPagamento") or "").strip()
            try:
                if not mat.isdigit():
                    raise LinhaRejeitada(f"matricula nao-numerica: {mat!r}", d)
                if len(cpf_env) != 11:
                    raise LinhaRejeitada(f"cpf da resposta invalido: {cpf_env!r}", d)
                if len(comp) != 6 or not comp.isdigit():
                    raise LinhaRejeitada(f"mesAnoPagamento mal-formado: {comp!r}", d)
                rubricas, tipo_fech = [], "normal"
                for rub in arr.iter():
                    if _local(rub.tag) != "DadosFinanceiros":
                        continue
                    rd, _ = _filhos_texto(rub)
                    rubricas.append({campo: _coage(rd.get(tag), kind)
                                     for campo, tag, kind in env.RUBRICA})
                    tipo_fech = env.MOVSUPL_LE.get((rd.get("indicadorMovSupl") or "").strip(), "normal")
            except LinhaRejeitada as r:
                rejeitos.append({"motivo": r.motivo, "dados": r.dados})
                continue
            payload = {"mes_competencia": comp, "tipo_fechamento": tipo_fech, "rubricas": rubricas}
            eventos.append({
                "id_evento": str(uuid.uuid5(uuid.NAMESPACE_URL, f"folha:{mat}|{comp}")),
                "id_carga": id_carga, "matricula_funcional": mat, "cpf": cpf_env,
                "cod_tipo_evento": "FECHAMENTO_FOLHA",
                "data_evento": _data_evento_comp(comp[:4], comp[4:]),
                "payload": json.dumps(payload, ensure_ascii=False),
                "cod_mecanica": env.CARIMBO_FOLHA["cod_mecanica"],
                "fonte": env.CARIMBO_FOLHA["fonte"],
                "grau_confianca": env.CARIMBO_FOLHA["grau_confianca"],
                "data_carga": data_carga,
            })
    return eventos, rejeitos


# ── Conector D: listaContribuicoesPSS §4.22 -> CONTRIBUICAO_PSS ───────────────
def parse_pss(xml_texto, id_carga=ID_CARGA_INGESTAO, data_carga=DATA_CARGA_INGESTAO):
    """Conector D: XML §4.22 -> (eventos CONTRIBUICAO_PSS, rejeitos). Carimbo CARIMBO_PSS.
    Arvore ano->mes->contribuicao achatada; matricula de grMatricula (provisorio)."""
    eventos, rejeitos = [], []
    for envelope in _envelopes(xml_texto):
        cpf_env = _cpf_envelope(envelope)
        for arr in _itera(envelope, "ArrayContribuicoesPSS"):
            d0, _ = _filhos_texto(arr)
            mat = (d0.get("grMatricula") or "").strip()
            for anoel in arr.iter():
                if _local(anoel.tag) != "AnoContribuicoesPSS":
                    continue
                da, _ = _filhos_texto(anoel)
                ano = (da.get("ano") or "").strip()
                for mesel in anoel.iter():
                    if _local(mesel.tag) != "MesContribuicoesPSS":
                        continue
                    dm, _ = _filhos_texto(mesel)
                    mes = (dm.get("mes") or "").strip()
                    contrib = next((c for c in mesel if _local(c.tag) == "contribuicoesPSS"), None)
                    cd = _filhos_texto(contrib)[0] if contrib is not None else {}
                    try:
                        if not mat.isdigit():
                            raise LinhaRejeitada(f"grMatricula nao-numerica: {mat!r}", d0)
                        if len(cpf_env) != 11:
                            raise LinhaRejeitada(f"cpf da resposta invalido: {cpf_env!r}", d0)
                        if not (ano.isdigit() and mes.isdigit()):
                            raise LinhaRejeitada(f"ano/mes PSS mal-formado: {ano!r}/{mes!r}", dm)
                        payload = {"gr_matricula": int(mat),
                                   "ano_contribuicao": int(ano), "mes_contribuicao": int(mes)}
                        for campo, tag, kind in env.PSS:
                            payload[campo] = _coage(cd.get(tag), kind)
                    except LinhaRejeitada as r:
                        rejeitos.append({"motivo": r.motivo, "dados": r.dados})
                        continue
                    eventos.append({
                        "id_evento": str(uuid.uuid5(uuid.NAMESPACE_URL, f"pss:{mat}|{ano}{int(mes):02d}")),
                        "id_carga": id_carga, "matricula_funcional": mat, "cpf": cpf_env,
                        "cod_tipo_evento": "CONTRIBUICAO_PSS",
                        "data_evento": _data_evento_comp(ano, mes),
                        "payload": json.dumps(payload, ensure_ascii=False),
                        "cod_mecanica": env.CARIMBO_PSS["cod_mecanica"],
                        "fonte": env.CARIMBO_PSS["fonte"],
                        "grau_confianca": env.CARIMBO_PSS["grau_confianca"],
                        "data_carga": data_carga,
                    })
    return eventos, rejeitos


# ── I/O (CLI) ────────────────────────────────────────────────────────────────
def _grava_rejeitos(rejeitos, caminho):
    if not rejeitos:
        return
    with open(caminho, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["motivo", "dados"])
        for r in rejeitos:
            w.writerow([r["motivo"], json.dumps(r["dados"], ensure_ascii=False)])


def conecta_funcionais(xml_path, out_path):
    linhas, rejeitos = parse_funcionais(open(xml_path, encoding="utf-8").read())
    with open(out_path, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=env.COLS_FUNCIONAIS)
        w.writeheader()
        w.writerows(linhas)
    rej_path = os.path.splitext(out_path)[0] + "_rejeitos.csv"
    _grava_rejeitos(rejeitos, rej_path)
    print(f"[conector A] {len(linhas)} linhas FOTO -> {os.path.basename(out_path)} | "
          f"rejeitos={len(rejeitos)}" + (f" -> {os.path.basename(rej_path)}" if rejeitos else ""))
    return linhas, rejeitos


def conecta_afastamento(xml_path, out_path):
    eventos, rejeitos = parse_afastamento(open(xml_path, encoding="utf-8").read())
    with open(out_path, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=COLS_EVENTO)
        w.writeheader()
        w.writerows(eventos)
    rej_path = os.path.splitext(out_path)[0] + "_rejeitos.csv"
    _grava_rejeitos(rejeitos, rej_path)
    c = env.CARIMBO_AFASTAMENTO
    print(f"[conector B] {len(eventos)} eventos AFASTAMENTO -> {os.path.basename(out_path)} | "
          f"carimbo={c['fonte']}/{c['cod_mecanica']}/{c['grau_confianca']} | "
          f"rejeitos={len(rejeitos)}" + (f" -> {os.path.basename(rej_path)}" if rejeitos else ""))
    return eventos, rejeitos


def main():
    aqui = os.path.dirname(os.path.abspath(__file__))
    out = os.path.join(aqui, "..", "..", "geradores", "out")
    ap = argparse.ArgumentParser(description="Conector SIAPE (Card 6)")
    sub = ap.add_subparsers(dest="face", required=True)
    pa = sub.add_parser("funcionais", help="Conector A: consultaDadosFuncionais -> FOTO")
    pa.add_argument("--xml", default=os.path.join(out, "siape_funcionais.xml"))
    pa.add_argument("--out", default=os.path.join(out, "foto_conector.csv"))
    pb = sub.add_parser("afastamento", help="Conector B: consultaDadosAfastamentoHistorico -> evento")
    pb.add_argument("--xml", default=os.path.join(out, "siape_afastamento.xml"))
    pb.add_argument("--out", default=os.path.join(out, "eventos_conector.csv"))
    a = ap.parse_args()
    if a.face == "funcionais":
        conecta_funcionais(a.xml, a.out)
    else:
        conecta_afastamento(a.xml, a.out)


if __name__ == "__main__":
    main()
