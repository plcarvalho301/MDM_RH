# -*- coding: utf-8 -*-
# =============================================================================
# MDM-RH — EMISSOR SIAPE (Card 3) — serializa a massa no envelope SOAP das APIs
# Ancoras: siape_envelope.py (contrato), 3_depara_soap_conectores_v0_2.md,
#          6_spec_conectores_siape_v0_2.md, ADR-009 (semantica da carga_lixo).
# -----------------------------------------------------------------------------
# O lado PRODUTOR do contrato. Dubla a SERPRO no teste (a/b): projeta a FOTO como
# consultaDadosFuncionais e re-serializa os eventos AFASTAMENTO como §4.21. Em
# go-live e a API real que produz — este emissor sai do loop, so o conector fica.
# Enganchado em gerador_eventos.py via `--formato siape` (camada de serializacao).
#
# Assimetria das fatias (handoff): Emissor A le a FOTO (servidor.csv, projecao),
# Emissor B le os eventos AFASTAMENTO da carga_base e os re-serializa.
# =============================================================================
import json
from xml.sax.saxutils import escape

from pipeline.contrato import siape_envelope as env


def _tag(nome, valor):
    """<nome>valor</nome>, ou <nome/> se vazio (tag vazia != ausente)."""
    if valor is None or valor == "":
        return f"<{nome}/>"
    return f"<{nome}>{escape(str(valor))}</{nome}>"


# ── A. consultaDadosFuncionais (FOTO) ────────────────────────────────────────
def _dados_funcionais(row):
    """Uma linha FOTO -> um <DadosFuncionais> (14 mapeadas + pareadas + descarte)."""
    p = []
    for col, tag, kind in env.FUNCIONAIS:
        v = (row.get(col) or "")
        if kind == "date":
            v = env.iso_para_ddmmyyyy(v)
        elif kind == "uorg":
            v = env.uorg_emite(v)
        elif kind == "sit":
            cod, nome = env.SIT_TO_COD.get(v, ("", ""))
            p.append(_tag("codSitFuncional", cod))
            p.append(_tag("nomeSitFuncional", nome))
            continue
        p.append(_tag(tag, v))
    # Pareadas codX/nomeX que a FOTO nao consome (emitidas p/ fidelidade):
    p.append(_tag("codCargo", "480026"))
    p.append(_tag("nomeClasse", row.get("classe") or ""))
    p.append(_tag("codFuncao", "1" if (row.get("funcao_comissionada") or "") else ""))
    p.append(_tag("codNovaFuncao", ""))
    # Descarte representativo (financeiro / datado->evento / operacional) — o
    # conector precisa ter o que descartar (~69 tags reais, so 14 consumidas):
    mat = row.get("matricula_funcional") or ""
    p.append(_tag("valeTransporte", "N"))
    p.append(_tag("percentualTS", "0"))
    p.append(_tag("codOcorrPSS", "00"))
    p.append(_tag("dataOcorrExclusao", ""))
    p.append(_tag("dataOcorrAposentadoria", ""))
    p.append(_tag("dataOcorrIngressoOrgao",
                  env.iso_para_ddmmyyyy(row.get("data_exercicio_no_orgao") or "")))
    p.append(_tag("identUnica", f"{mat}X"))
    p.append(_tag("codUpag", "000010"))
    p.append(_tag("codJornada", "40"))
    p.append(_tag("emailServidor", "servidor@reinoanimal.gov.br"))
    p.append(_tag("nomeChefeUorg", ""))
    p.append(_tag("cpfChefiaImediata", "00000000000"))
    p.append(_tag("pontuacaoDesempenho", "0"))
    return "      <DadosFuncionais>" + "".join(p) + "</DadosFuncionais>"


def emite_funcionais(foto_rows):
    """FOTO (lista de dict) -> XML: 1 consultaDadosFuncionaisResponse por CPF,
    DadosFuncionais repetido por vinculo (N/CPF — arquetipo #B = 2o vinculo).
    Envolto num <lote> (container de teste) para transportar N respostas num
    arquivo; o conector parseia POR envelope (unidade real = 1 resposta = 1 CPF)."""
    por_cpf = {}
    for r in foto_rows:
        por_cpf.setdefault(r["cpf"], []).append(r)
    out = ["<lote>"]
    for cpf, vincs in por_cpf.items():
        out.append(f'  <soap:Envelope xmlns:soap="{env.NS_SOAP}"><soap:Body>')
        out.append(f'    <ns1:consultaDadosFuncionaisResponse xmlns:ns1="{env.NS_WRAP}">')
        out.append(f'     <out><dadosFuncionais xmlns="{env.NS_TIPO}">')
        for r in vincs:
            out.append(_dados_funcionais(r))
        out.append("     </dadosFuncionais></out>")
        out.append("    </ns1:consultaDadosFuncionaisResponse>")
        out.append("  </soap:Body></soap:Envelope>")
    out.append("</lote>")
    return "\n".join(out)


# ── B. consultaDadosAfastamentoHistorico §4.21 (EVENTO) ──────────────────────
def emite_afastamento(afast_events):
    """Eventos AFASTAMENTO (dicts com matricula_funcional, cpf, payload) ->
    XML §4.21: 1 consultaDadosAfastamentoHistoricoResponse por CPF,
    ArrayOfArrayDadosAfastamento (1 ArrayDadosAfastamento por vinculo, serie datada).
    Mapa (de-para §B.2): cod_afastamento->codOcorrencia, data_inicio->dataIni
    (ISO->DDMMYYYY), data_fim->dataFim (vazio=aberto), matricula->grMatricula."""
    por_cpf = {}
    for e in afast_events:
        pl = e["payload"] if isinstance(e["payload"], dict) else json.loads(e["payload"])
        por_cpf.setdefault(e["cpf"], {}).setdefault(e["matricula_funcional"], []).append(pl)
    out = ["<lote>"]
    for cpf, vincs in por_cpf.items():
        out.append(f'  <soap:Envelope xmlns:soap="{env.NS_SOAP}"><soap:Body>')
        out.append(f'    <ns1:consultaDadosAfastamentoHistoricoResponse xmlns:ns1="{env.NS_WRAP}">')
        out.append(f'     <out><ArrayOfArrayDadosAfastamento xmlns="{env.NS_TIPO}">')
        for mat, series in vincs.items():
            out.append("      <ArrayDadosAfastamento>")
            for pl in series:
                dados = (
                    _tag("grMatricula", mat)
                    + _tag("codOcorrencia", pl.get("cod_afastamento") or "")
                    + _tag("descOcorrencia", "")   # descarta: nome vem do dominio
                    + _tag("dataIni", env.iso_para_ddmmyyyy(pl.get("data_inicio") or ""))
                    + _tag("dataFim", env.iso_para_ddmmyyyy(pl.get("data_fim") or ""))
                )
                out.append(f"        <DadosAfastamento>{dados}</DadosAfastamento>")
            out.append("      </ArrayDadosAfastamento>")
        out.append("     </ArrayOfArrayDadosAfastamento></out>")
        out.append("    </ns1:consultaDadosAfastamentoHistoricoResponse>")
        out.append("  </soap:Body></soap:Envelope>")
    out.append("</lote>")
    return "\n".join(out)


# ── Injecao de defeito (Card 3) — reusa semantica da carga_lixo (ADR-009) ─────
# Um por vez, flag explicita (nao cocktail). Transporta o defeito material p/ o
# envelope; o conector deve degradar com graca (rejeito->quarentena, loga, nao aborta).
def aplica_defeito_funcionais(xml_texto, tipo):
    """Corrompe UMA ocorrencia do XML funcionais conforme o catalogo (de-para §C)."""
    if tipo == "data_malformada":
        return _primeiro(xml_texto, "dataExercicioNoOrgao", "00000000")
    if tipo == "tag_ausente":
        return _remove_primeiro(xml_texto, "codSitFuncional")   # ausente != vazia
    if tipo == "cpf_mascarado":
        return _primeiro(xml_texto, "cpf", "123.456.789-01")
    if tipo == "alfanum_coagido":
        return _primeiro(xml_texto, "codPadrao", "2")           # esperado 'II'
    raise ValueError(f"defeito desconhecido: {tipo} (catalogo: {env.DEFEITOS})")


def _primeiro(xml_texto, tag, novo):
    ini = xml_texto.find(f"<{tag}>")
    if ini < 0:
        ini = xml_texto.find(f"<{tag}/>")
        if ini < 0:
            return xml_texto
        fim = xml_texto.find(">", ini) + 1
        return xml_texto[:ini] + f"<{tag}>{novo}</{tag}>" + xml_texto[fim:]
    fim = xml_texto.find(f"</{tag}>", ini) + len(f"</{tag}>")
    return xml_texto[:ini] + f"<{tag}>{novo}</{tag}>" + xml_texto[fim:]


def _remove_primeiro(xml_texto, tag):
    ini = xml_texto.find(f"<{tag}>")
    if ini < 0:
        return xml_texto.replace(f"<{tag}/>", "", 1)
    fim = xml_texto.find(f"</{tag}>", ini) + len(f"</{tag}>")
    return xml_texto[:ini] + xml_texto[fim:]
