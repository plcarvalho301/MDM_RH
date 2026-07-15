# -*- coding: utf-8 -*-
# =============================================================================
# MDM-RH — CONTRATO DE ENVELOPE SIAPE (Cards 3 + 6) — o de-para executavel
# Ancoras: 3_depara_soap_conectores_v0_2.md (§A funcionais, §B afastamento §4.21),
#          6_spec_conectores_siape_v0_2.md, ADR-014 (proveniencia do afastamento).
# -----------------------------------------------------------------------------
# Este modulo E o CONTRATO DE FRONTEIRA — e SO isso: o vocabulario que os DOIS
# lados compartilham (namespaces, formato de valor, mapa tag<->coluna, carimbo,
# catalogo de defeitos). Nao emite nem parseia nada.
#   - Card 3 (emissor)  -> geradores/emissor_siape.py          produz o envelope daqui.
#   - Card 6 (conector) -> pipeline/conectores/conector_siape.py consome o envelope daqui.
# Um so lugar define o shape; se o contrato muda, muda aqui e os dois lados seguem.
# So stdlib: importavel offline, sem DB, sem API viva (o ponto dos cards a/b).
# =============================================================================
from datetime import date

# ── Namespaces (de-para §A.2 — response real §3.2 lida) ──────────────────────
NS_SOAP = "http://schemas.xmlsoap.org/soap/envelope/"
NS_WRAP = "http://servico.wssiapenet"        # ns1: wrapper *Response
NS_TIPO = "http://tipo.servico.wssiapenet"   # xmlns default do corpo dados*

# ── Carimbo de ingestao do evento AFASTAMENTO (ADR-014) ──────────────────────
CARIMBO_AFASTAMENTO = {
    "fonte": "WS_SIAPE:consultaDadosAfastamentoHistorico",
    "cod_mecanica": "ingestao",   # ← API; != 'extracao' do gerador (ADR-006, ortogonal)
    "grau_confianca": "alto",
}

# ── Situacao: bijecao estado-derivado <-> (codSitFuncional, nomeSitFuncional) ─
# A FOTO guarda o ESTADO derivado (ATIVO/CEDIDO/...); o SIAPE fala codSitFuncional.
# Bijecao controlada dos dois lados => round-trip exato. Fidelidade ao codigo real
# da SERPRO e refinamento de go-live (o conector inverte por codSitFuncional).
SIT_TO_COD = {
    "ATIVO":           ("01", "ATIVO PERMANENTE"),
    "CEDIDO":          ("40", "CEDIDO"),
    "DISPONIBILIDADE": ("31", "EM DISPONIBILIDADE"),
    "INATIVO":         ("02", "APOSENTADO"),
    "DESLIGADO":       ("99", "EXCLUIDO"),
    "TRANSFERIDO":     ("50", "TRANSFERIDO"),
}
COD_TO_SIT = {cod: sit for sit, (cod, _nome) in SIT_TO_COD.items()}


# ── Formatadores de valor (partilhados: emissor usa ida, conector usa volta) ─
def iso_para_ddmmyyyy(s):
    """'2000-07-05' -> '05072000'. Vazio permanece vazio (tag vazia = NULL)."""
    s = (s or "").strip()
    if not s:
        return ""
    a, m, d = s.split("-")
    return f"{d}{m}{a}"


def ddmmyyyy_para_iso(s):
    """'05072000' -> '2000-07-05'. Vazio permanece vazio. Valida calendario
    (rejeita 00000000, 30/02, etc.) — e o gancho da degradacao graciosa."""
    s = (s or "").strip()
    if not s:
        return ""
    if len(s) != 8 or not s.isdigit():
        raise ValueError(f"data DDMMYYYY mal-formada: {s!r}")
    dd, mm, aaaa = int(s[0:2]), int(s[2:4]), int(s[4:])
    try:
        date(aaaa, mm, dd)
    except ValueError:
        raise ValueError(f"data DDMMYYYY fora do calendario: {s!r}")
    return f"{s[4:]}-{s[2:4]}-{s[0:2]}"


def uorg_emite(v):
    """FOTO '100010' -> '000100010' (zeros a esquerda, largura 9 — de-para §A.2)."""
    v = (v or "").strip()
    return v.zfill(9) if v else ""


def uorg_le(v):
    """'000100010' -> '100010' (strip dos zeros; conector int()). Vazio -> ''."""
    v = (v or "").strip()
    if not v:
        return ""
    return str(int(v))


# ── Mapa FUNCIONAIS: coluna FOTO <-> tag primaria (de-para §A.2) ──────────────
# (coluna_foto, tag_primaria, transforma). 'transforma' liga emissao<->parse:
#   str  = passthrough      | date = ISO<->DDMMYYYY
#   uorg = zeros<->int      | sit  = estado<->(codSitFuncional,nomeSitFuncional)
#   cpf  = passthrough<->normaliza (contrato: so digitos)
# So estas 14 colunas SAO consumidas pela FOTO; codX/nomeX pareados e as ~55 tags
# de descarte saem no XML (fidelidade) mas o conector as ignora.
FUNCIONAIS = [
    ("matricula_funcional",       "matriculaSiape",         "str"),
    ("cpf",                       "cpf",                    "cpf"),
    # nome/data_nascimento: o consultaDadosFuncionais real traz (a API tem ~69 tags,
    # so 14 eram consumidas); entram aqui p/ preencher as colunas NOT NULL de `servidor`
    # que o recorte antigo nao cobria (reconciliacao FOTO). Propaga a emissor+conector.
    ("nome",                      "nomeServidor",           "str"),
    ("data_nascimento",           "dataNascimento",         "date"),
    ("cargo",                     "nomeCargo",              "str"),
    ("classe",                    "codClasse",              "str"),
    ("padrao",                    "codPadrao",              "str"),
    ("sigla_nivel_cargo",         "siglaNivelCargo",        "str"),
    ("funcao_comissionada",       "nomeFuncao",             "str"),
    ("nova_funcao",               "nomeNovaFuncao",         "str"),
    # A FOTO ja grava data_ingresso_nova_funcao no formato-fio DDMMYYYY (ao contrario
    # de data_exercicio_no_orgao, que e ISO) — logo passthrough, nao re-converte.
    ("data_ingresso_nova_funcao", "dataIngressoNovaFuncao", "str"),
    ("cod_unidade_lotacao",       "codUorgLotacao",         "uorg"),
    ("cod_unidade_exercicio",     "codUorgExercicio",       "uorg"),
    ("situacao_funcional",        "codSitFuncional",        "sit"),
    ("regime_juridico",           "siglaRegimeJuridico",    "str"),
    ("data_exercicio_no_orgao",   "dataExercicioNoOrgao",   "date"),
]
# Colunas comparadas no round-trip A (foto' == servidor.csv, recorte SIAPE):
COLS_FUNCIONAIS = [c for c, _t, _k in FUNCIONAIS]
# Tags estruturais: ausencia = defeito (rejeito), != vazia (NULL legitimo).
TAGS_OBRIGATORIAS = {"matriculaSiape", "codSitFuncional"}

# ── Mapa AFASTAMENTO §4.21 (de-para §B.2): payload evento <-> tag ─────────────
# (campo_payload, tag). matricula vem de grMatricula (fora do payload, e chave).
AFASTAMENTO = [
    ("cod_afastamento", "codOcorrencia"),
    ("data_inicio",     "dataIni"),   # ISO<->DDMMYYYY
    ("data_fim",        "dataFim"),   # vazio = aberto (vigente)
]

# ── Carimbos de ingestao FECHAMENTO_FOLHA (§4.20) e CONTRIBUICAO_PSS (§4.22) ──
# Faces compensacao. Mesma logica do CARIMBO_AFASTAMENTO (ADR-014): a proveniencia
# viaja no envelope do evento como rastro; fonte = a operacao SOAP de origem.
CARIMBO_FOLHA = {
    "fonte": "WS_SIAPE:consultaDadosFinanceirosHistorico",
    "cod_mecanica": "ingestao",
    "grau_confianca": "alto",
}
CARIMBO_PSS = {
    "fonte": "WS_SIAPE:listaContribuicoesPSS",
    "cod_mecanica": "ingestao",
    "grau_confianca": "alto",
}

# ── Mapa FECHAMENTO_FOLHA §4.20 (de-para v0.3 §2): rubrica <-> tag ────────────
# DadosFinanceiros (uma por rubrica). Todas as tags-folha sao xsd:string no WSDL —
# a COERCAO de tipo e do conector (regra de valor §4.1), o de-para so registra o
# alvo (kind: int|num|str). So as 5 que o gerador popula; pz/pe/dataAnoMesRubrica
# entram quando a fonte real trouxer (YAGNI ate la). Wrapper ArrayDadosFinanceiros:
# matricula, mesAnoPagamento (= mes_competencia, decisao TL 2026-07-14),
# dadosFinanceiros[]. codigoOrgao descarta (pend. pos-live).
RUBRICA = [
    ("cod_rubrica",   "codRubrica",   "int"),
    ("nome_rubrica",  "nomeRubrica",  "str"),
    ("valor_rubrica", "valorRubrica", "num"),
    ("indicador_rd",  "indicadorRD",  "str"),
    ("numero_seq",    "numeroSeq",    "int"),
]
# tipo_fechamento <-> indicadorMovSupl (por-rubrica, esperado homogeneo — decisao
# TL §5.3). Codigos provisorios, emissor<->conector consistentes.
# ponytail: de-para provisorio de indicadorMovSupl; confirmar codigo real no go-live.
MOVSUPL_EMITE = {"normal": "N", "suplementar": "S"}
MOVSUPL_LE = {v: k for k, v in MOVSUPL_EMITE.items()}

# ── Mapa CONTRIBUICAO_PSS §4.22 (de-para v0.3 §3): escalar <-> tag ────────────
# ContribuicoesPSS (folha da arvore ano->mes->contribuicao). ano/mes sao NIVEIS da
# arvore (achatados p/ ano_contribuicao/mes_contribuicao — decisao TL §5.4). Os 3
# campos novos (percentualRemunerado/remuneracaoConsiderada/remuneracaoInformada)
# descartam (decisao TL §5.5). matricula NAO tem tag no shape PSS do WSDL — carrego
# grMatricula no nivel ArrayContribuicoesPSS.
# ponytail: linkage de matricula provisorio (WSDL PSS nao traz matricula); confirmar live.
PSS = [
    ("pss_apurado",              "pssApurado",             "int"),
    ("pss_informado",            "pssInformado",           "int"),
    ("remuneracao_pss",          "remuneracaoPss",         "num"),
    ("remuneracao_pss_ajustada", "remuneracaoPssAjustada", "num"),
    ("indice_reajuste",          "indiceReajuste",         "int"),
]

# ── Catalogo de defeitos (Card 3 injeta, Card 6 degrada) — de-para §C ─────────
DEFEITOS = ("data_malformada", "tag_ausente", "cpf_mascarado", "alfanum_coagido")
