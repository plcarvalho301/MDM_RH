#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# =============================================================================
# MDM-RH — GERADOR DE EVENTOS (foto-primeiro) — v2
# Data: 2026-07-05
# Ancoras: gen_massa.py (FOTO canonica) | 3_catalogo_eventos_v1.yaml (v1.1)
#          3_schema_mdm.sql (v0.9) | ADR-008 | ADR-009
#
# INVERSAO (v1 -> v2): o v1 era trajetoria-primeiro (inventava a propria gente e
# PROJETAVA a foto). Errado: gerava um universo paralelo ao do gen_massa. O v2
# CONSOME a FOTO canonica (gen_massa/out/servidor.csv) e emite eventos que
# ATERRISSAM no estado fotografado de cada vinculo — mesma gente, mesma matricula.
#
# CONTRATO com a foto (o replay/MV re-deriva ISTO da serie de eventos):
#   - situacao_funcional  (base PROVIMENTO/DESLIGAMENTO + intervalos vigentes)
#   - cod_afastamento_vigente, funcao_comissionada, classe, padrao
# A situacao NAO e evento: deriva de intervalos na data_ref (regras em REGRAS_SIT,
# decisao #5 — convencao do gen_massa: CEDIDO<=>cessao+afast 40; DISPONIBILIDADE
# <=>afast 31; ATIVO+cod=afastado vigente ATIVO).
#
# CONTRATO de payload (v0.9 le estas chaves via ->> nas MVs de Filme):
#   AFASTAMENTO {cod_afastamento,data_inicio,data_fim}; CESSAO {orgao_cessionario,
#   data_inicio,onus,data_fim}; DESLIGAMENTO {cod_motivo_deslig,data_desligamento};
#   PROVIMENTO {cargo_inicial,regime_juridico}; PROGRESSAO {classe/padrao _origem/
#   _destino,tipo_progressao}; ALTERACAO_FUNCAO {cod_funcao,nome_funcao,
#   tipo_movimento}; FECHAMENTO_FOLHA {mes_competencia,mes_pagamento,tipo_fechamento,
#   rubricas}.  NAO renomear chaves sem mexer nas MVs.
#
# ESCOPO v2 (decisao #2 = hibrido): TODOS os 1300 vinculos ganham a trajetoria
# MECANICA que aterrissa no estado (bulk). Os ~14 casos-teste nominais (Gerson 2
# desligamentos, Vicente anulacao, etc.) ganham trajetoria RICA na PROXIMA FASE —
# a foto (snapshot) nao carrega a forma da trajetoria, entao exige marcador do
# gen_massa; fica para o proximo incremento. Aqui o desligado/inativo recebe um
# motivo plausivel unico.
#
# SAIDAS (--out DIR), formato = envelope do evento (schema v0.9). Destino ARQUIVO;
#   --carrega-banco (decisao #6) fara o destino=banco via loader depois.
#   eventos_<carga>.csv | cargas.json | load_eventos.sql
# CARGAS: carga_base (trajetoria) | carga_folha (FECHAMENTO_FOLHA) | carga_lixo
#   (fixture ADR-009, --sem-lixo desliga).
#
# Uso: python gerador_eventos.py --foto ../gerador/out/servidor.csv [--config config.yaml]
# Dep: PyYAML (so p/ ler a seed do config)
# =============================================================================
import argparse, csv, json, os, random, sys, uuid
from datetime import date, datetime, timedelta, timezone

import yaml

# ── Constantes de dominio (schema v0.9 / seed v0.2) ──────────────────────────
GRADE = [(c, p) for c in ["A", "B", "C", "ESPECIAL"] for p in ["I", "II", "III", "IV", "V"]]
MOTIVO_DESLIG = {  # cod -> situacao_resultante (dom_motivo_deslig)
    "07": "DESLIGADO", "08": "DESLIGADO", "09": "DESLIGADO", "25": "DESLIGADO",
    "38": "INATIVO", "39": "INATIVO",
    "DEMI_OFICIO": "DESLIGADO", "CASS_APOSENT": "DESLIGADO", "ANUL_PROVIMENTO": "DESLIGADO",
}
# motivo default por situacao-alvo do desligamento (casos-teste ganham motivo
# especifico na proxima fase; aqui o generico honesto):
DESLIG_DEFAULT = {"DESLIGADO": "07", "INATIVO": "38"}
AFAST_PAUSA_FOLHA = {"05"}          # LSV: sem remuneracao -> folha pausa

# Regras de derivacao de situacao a partir de intervalos (decisao #5 — vira dado).
# situacao NAO e evento: deriva da base (PROVIMENTO=ATIVO / DESLIGAMENTO=motivo) +
# o intervalo vigente na data_ref. Convencao da foto canonica (gen_massa):
AFAST_CEDIDO = "40"          # CEDIDO tem afast 40 espelho + evento CESSAO
AFAST_DISPONIBILIDADE = "31"  # DISPONIBILIDADE deriva de afast 31 vigente
ORGAOS_CESSIONARIOS = ["Chancelaria dos Albatrozes", "Banco Central dos Castores",
                       "Tribunal das Corujas", "Instituto dos Cervos"]


# ── Helpers de data ──────────────────────────────────────────────────────────
def add_meses(d, m):
    from calendar import monthrange
    y, mo = d.year + (d.month - 1 + m) // 12, (d.month - 1 + m) % 12 + 1
    return date(y, mo, min(d.day, monthrange(y, mo)[1]))


def d28(d):  # normaliza p/ <= dia 28 (mesma disciplina do gen_massa)
    return date(d.year, d.month, min(d.day, 28))


def parse_data(v):
    """ISO passa direto; a API real (e o gen_massa) manda DDMMYYYY — mesmo
    tratamento do _data_iso do loader."""
    import re
    if re.fullmatch(r"[0-9]{8}", v):
        return date(int(v[4:]), int(v[2:4]), int(v[:2]))
    return date.fromisoformat(v)


# ── Emissao ──────────────────────────────────────────────────────────────────
class Emissor:
    """Acumula eventos por carga; carimba data_carga com deslocamento controlavel
    (o desempate da coalescencia ADR-008 e data_carga — o fechamento vem DEPOIS)."""
    COLS = ["id_evento", "id_carga", "matricula_funcional", "cpf", "cod_tipo_evento",
            "data_evento", "payload", "cod_mecanica", "fonte", "grau_confianca", "data_carga"]

    def __init__(self, rng):
        self.rng, self.cargas = rng, {}
        self.t0 = datetime(2026, 7, 5, 3, 0, tzinfo=timezone.utc)

    def carga(self, rotulo):
        cid = str(uuid.UUID(int=self.rng.getrandbits(128), version=4))
        self.cargas[rotulo] = {"id_carga": cid, "linhas": []}
        return cid

    def emite(self, rotulo, mat, cpf, tipo, data_ev, payload, atraso_h=0,
              fonte="GERADOR_REINO_ANIMAL", grau="alto"):
        c = self.cargas[rotulo]
        c["linhas"].append([str(uuid.UUID(int=self.rng.getrandbits(128), version=4)),
                            c["id_carga"], mat, cpf, tipo, data_ev.isoformat(),
                            json.dumps(payload, ensure_ascii=False), "extracao",
                            fonte, grau,
                            (self.t0 + timedelta(hours=atraso_h)).isoformat()])


# ── Aterrissagem: eventos de UM vinculo que terminam no estado fotografado ───
def gera_eventos_vinculo(rng, em, row, data_ref, frac_dois):
    """Recebe uma linha da FOTO canonica e emite a serie de eventos que aterrissa
    nela. Retorna o insumo da folha (ingresso, fim_folha, pausas)."""
    mat, cpf = row["matricula_funcional"], row["cpf"]
    sit_alvo = row["situacao_funcional"]
    ingresso = d28(date.fromisoformat(row["data_exercicio_no_orgao"]))
    regime = row.get("regime_juridico") or "RJU"

    # 1) PROVIMENTO no ingresso
    em.emite("carga_base", mat, cpf, "PROVIMENTO", ingresso,
             {"cargo_inicial": row["cargo"], "regime_juridico": regime})

    # 2) DESLIGAMENTO (se aplicavel) fixa a fronteira temporal da carreira
    fim_folha = None
    encerrado_em = None
    if sit_alvo in ("DESLIGADO", "INATIVO"):
        # desligamento entre o ingresso e a data_ref (nunca no futuro)
        span = max((data_ref - ingresso).days, 30)
        dt_des = d28(ingresso + timedelta(days=rng.randint(span // 2, span)))
        dt_des = min(dt_des, data_ref)
        motivo = DESLIG_DEFAULT[sit_alvo]
        em.emite("carga_base", mat, cpf, "DESLIGAMENTO", dt_des,
                 {"cod_motivo_deslig": motivo, "data_desligamento": dt_des.isoformat()})
        encerrado_em = dt_des
        if sit_alvo == "DESLIGADO":
            fim_folha = dt_des            # DESLIGADO para a folha; INATIVO segue (proventos)

    limite = encerrado_em or data_ref

    # 3) PROGRESSAO: da grade (A,I) ate (classe, padrao) da foto. A ULTIMA
    #    progressao aterrissa no destino — datas so precisam caber antes do limite.
    alvo = (row["classe"] or "A", row["padrao"] or "I")
    n = GRADE.index(alvo) if alvo in GRADE else 0
    if n > 0:
        janela = max((limite - ingresso).days - 30, n)   # dias uteis p/ espalhar
        passo = max(janela // (n + 1), 1)
        d = ingresso
        for g in range(n):
            d = d28(min(d + timedelta(days=passo + rng.randint(-15, 15)), limite))
            co, po = GRADE[g]
            cd, pd = GRADE[g + 1]
            em.emite("carga_base", mat, cpf, "PROGRESSAO", date(d.year, d.month, 1),
                     {"classe_origem": co, "padrao_origem": po,
                      "classe_destino": cd, "padrao_destino": pd,
                      "tipo_progressao": "progressao"})

    # 4) ALTERACAO_FUNCAO: aterrissa na funcao_comissionada vigente (se houver e
    #    ativo/cedido). A ULTIMA designacao vence no replay.
    fun = row.get("funcao_comissionada") or None
    if fun and sit_alvo in ("ATIVO", "CEDIDO"):
        di = row.get("data_ingresso_nova_funcao")
        d_fun = d28(parse_data(di)) if di else d28(
            ingresso + timedelta(days=max((limite - ingresso).days // 2, 1)))
        d_fun = max(min(d_fun, limite), ingresso)
        em.emite("carga_base", mat, cpf, "ALTERACAO_FUNCAO", d_fun,
                 {"cod_funcao": fun, "nome_funcao": fun, "tipo_movimento": "designacao"})

    # 5) Intercorrencias vigentes que ATERRISSAM situacao + cod_afastamento_vigente
    pausas = []
    cod_af = (row.get("cod_afastamento_vigente") or "").strip()

    def emite_afast(cod, ini, fim):
        """AFASTAMENTO vigente: aberto (data_fim=None) ou par aberto+fechamento
        (coalescencia ADR-008; fim > data_ref mantem vigente)."""
        chave = {"cod_afastamento": cod, "data_inicio": ini.isoformat()}
        if rng.random() < frac_dois:               # par: exercita intervalo_vigente (v0.9)
            em.emite("carga_base", mat, cpf, "AFASTAMENTO", ini, dict(chave, data_fim=None))
            em.emite("carga_base", mat, cpf, "AFASTAMENTO", ini,
                     dict(chave, data_fim=fim.isoformat()), atraso_h=6)
        else:
            em.emite("carga_base", mat, cpf, "AFASTAMENTO", ini, dict(chave, data_fim=None))
        if cod in AFAST_PAUSA_FOLHA:
            pausas.append((ini, fim))

    if sit_alvo in ("ATIVO", "CEDIDO", "DISPONIBILIDADE") and cod_af:
        ini_af = d28(add_meses(data_ref, -rng.randint(1, 18)))
        ini_af = max(ini_af, ingresso)
        fim_af = d28(add_meses(data_ref, rng.randint(2, 24)))   # ainda vigente na ref
        if sit_alvo == "CEDIDO":
            # CESSAO (deriva CEDIDO) + AFASTAMENTO 40 espelho (v0.9: "aparece 2x")
            ini_ces = ini_af
            ch = {"orgao_cessionario": rng.choice(ORGAOS_CESSIONARIOS),
                  "data_inicio": ini_ces.isoformat(), "onus": "com_onus"}
            if rng.random() < frac_dois:
                em.emite("carga_base", mat, cpf, "CESSAO", ini_ces, dict(ch, data_fim=None))
                em.emite("carga_base", mat, cpf, "CESSAO", ini_ces,
                         dict(ch, data_fim=fim_af.isoformat()), atraso_h=6)
            else:
                em.emite("carga_base", mat, cpf, "CESSAO", ini_ces, dict(ch, data_fim=None))
            emite_afast(AFAST_CEDIDO, ini_af, fim_af)
        else:
            emite_afast(cod_af, ini_af, fim_af)     # ATIVO+cod ou DISPONIBILIDADE (31)

    return {"ingresso": ingresso, "fim_folha": fim_folha, "pausas": pausas}


# ── Folha mensal (carga propria — destacavel, ADR-009) ───────────────────────
def gera_folha(rng, em, mat, cpf, fol, data_ref):
    n = 0
    d = date(fol["ingresso"].year, fol["ingresso"].month, 1)
    fim = fol["fim_folha"] or data_ref
    while d <= fim:
        if not any(p0 <= d <= p1 for p0, p1 in fol["pausas"]):
            comp = f"{d.year}{d.month:02d}"
            em.emite("carga_folha", mat, cpf, "FECHAMENTO_FOLHA", add_meses(d, 1),
                     {"mes_competencia": comp, "mes_pagamento": comp, "tipo_fechamento": "normal",
                      "rubricas": [{"cod_rubrica": 1, "nome_rubrica": "VENCIMENTO BASICO",
                                    "valor_rubrica": round(rng.uniform(8000, 24000), 2),
                                    "indicador_rd": "R", "numero_seq": 1}]})
            n += 1
        d = add_meses(d, 1)
    return n


# ── Replay de validacao (ADR-008; 5 situacoes) ───────────────────────────────
def replay(eventos, data_ref):
    """Reconstroi o estado por INTERVALO + coalescencia. Retorna o dict que a foto
    canonica declara (situacao/afast/funcao/classe/padrao)."""
    evs = sorted(eventos, key=lambda e: (e["data_evento"], e["data_carga"], e["id_evento"]))
    sit = None
    aberto = {}                       # (tipo, data_inicio) -> payload (coalescencia)
    funcao, classe, padrao = None, "A", "I"
    for e in evs:
        t = e["cod_tipo_evento"]
        pl = e["payload"] if isinstance(e["payload"], dict) else json.loads(e["payload"])
        if t == "PROVIMENTO":
            sit = "ATIVO"
        elif t == "DESLIGAMENTO":
            sit = MOTIVO_DESLIG[pl["cod_motivo_deslig"]]
        elif t == "RETORNO_VINCULO":
            sit = "ATIVO"
        elif t in ("CESSAO", "AFASTAMENTO"):
            aberto[(t, pl["data_inicio"])] = pl
        elif t == "ALTERACAO_FUNCAO":
            funcao = pl.get("cod_funcao") if pl.get("tipo_movimento") == "designacao" else None
        elif t == "PROGRESSAO":
            classe, padrao = pl.get("classe_destino") or classe, pl.get("padrao_destino") or padrao

    ic = {"CESSAO": [], "AFASTAMENTO": []}
    for (t, ini), pl in aberto.items():
        fim = pl.get("data_fim")
        ic[t].append((date.fromisoformat(ini), date.fromisoformat(fim) if fim else date.max,
                      pl.get("cod_afastamento")))
    cedido = any(a <= data_ref <= b for a, b, _ in ic["CESSAO"])
    af_vig = next((cod for a, b, cod in sorted(ic["AFASTAMENTO"]) if a <= data_ref <= b), None)
    if sit == "ATIVO":
        if cedido:
            sit = "CEDIDO"
        elif af_vig == AFAST_DISPONIBILIDADE:
            sit = "DISPONIBILIDADE"
    if sit not in ("ATIVO", "CEDIDO", "DISPONIBILIDADE"):
        af_vig, funcao = None, None
    return {"situacao_funcional": sit, "cod_afastamento_vigente": af_vig,
            "funcao_comissionada": funcao, "classe": classe, "padrao": padrao}


# ── Main ─────────────────────────────────────────────────────────────────────
def main():
    aqui = os.path.dirname(__file__)
    ap = argparse.ArgumentParser(description="Gerador de eventos foto-primeiro (v2)")
    ap.add_argument("--foto", default=os.path.join(aqui, "out", "servidor.csv"),
                    help="FOTO canonica (saida do gen_massa)")
    ap.add_argument("--config", default=os.path.join(aqui, "config.yaml"),
                    help="dono da seed (decisao #4)")
    ap.add_argument("--out", default="saida")
    ap.add_argument("--sem-folha", action="store_true")
    ap.add_argument("--sem-lixo", action="store_true")
    ap.add_argument("--valida", action="store_true")
    a = ap.parse_args()

    os.makedirs(a.out, exist_ok=True)
    cfg = yaml.safe_load(open(a.config, encoding="utf-8"))
    seed = cfg["seed"]
    frac_dois = 0.25            # fracao de intercorrencias como par (ADR-008/v0.9)
    rng = random.Random(seed)

    with open(a.foto, encoding="utf-8", newline="") as f:
        foto = list(csv.DictReader(f))
    if not foto:
        sys.exit(f"FOTO vazia: {a.foto} — rode gen_massa antes.")
    data_ref = date.fromisoformat(foto[0]["data_referencia"])   # decisao #1: foto e dona

    em = Emissor(rng)
    for rot in ("carga_base", "carga_folha", "carga_lixo"):
        em.carga(rot)

    folhas = []
    for row in foto:
        fol = gera_eventos_vinculo(rng, em, row, data_ref, frac_dois)
        folhas.append((row["matricula_funcional"], row["cpf"], fol))

    n_folha = 0
    if not a.sem_folha:
        for mat, cpf, fol in folhas:
            n_folha += gera_folha(rng, em, mat, cpf, fol, data_ref)

    # Carga-lixo: fixture de RETRATACAO OPERACIONAL (defeito material deliberado).
    if not a.sem_lixo:
        amostra = rng.sample(em.cargas["carga_base"]["linhas"], k=min(30, len(foto)))
        for l in amostra:
            pl = json.loads(l[6])
            if "data_desligamento" in pl:
                pl["data_desligamento"] = "1900-01-01"     # bem-formado, errado
            em.emite("carga_lixo", l[2], l[3], l[4], date.fromisoformat(l[5]), pl,
                     atraso_h=48, fonte="CARGA_APOSENTADOS_DEFEITUOSA", grau="medio")

    # Validacao: replay-de-intervalo vs FOTO canonica (nucleo + estendido)
    if a.valida:
        por_mat = {}
        for l in em.cargas["carga_base"]["linhas"]:
            por_mat.setdefault(l[2], []).append(dict(zip(Emissor.COLS, l)))
        campos = ["situacao_funcional", "cod_afastamento_vigente", "funcao_comissionada",
                  "classe", "padrao"]
        div = 0
        for row in foto:
            r = replay(por_mat[row["matricula_funcional"]], data_ref)
            for c in campos:
                esp = row[c] or None
                if r[c] != esp:
                    div += 1
                    if div <= 8:
                        print(f"  DIVERGE {row['matricula_funcional']} [{c}]: "
                              f"replay={r[c]!r} foto={esp!r} (sit={row['situacao_funcional']})")
        print(f"[valida] replay-de-intervalo vs FOTO canonica: {len(foto)} vinculos, {div} divergencias")
        if div:
            sys.exit(1)

    # Escrita (formato = envelope; schema v0.9)
    manif = {}
    for rot, c in em.cargas.items():
        if not c["linhas"]:
            continue
        fn = os.path.join(a.out, f"eventos_{rot}.csv")
        with open(fn, "w", newline="", encoding="utf-8") as fh:
            w = csv.writer(fh); w.writerow(Emissor.COLS); w.writerows(c["linhas"])
        manif[rot] = {"id_carga": c["id_carga"], "eventos": len(c["linhas"]),
                      "arquivo": os.path.basename(fn)}
    json.dump({"seed": seed, "n_vinculos": len(foto), "data_base": data_ref.isoformat(),
               "cargas": manif}, open(os.path.join(a.out, "cargas.json"), "w"),
              indent=2, ensure_ascii=False)
    with open(os.path.join(a.out, "load_eventos.sql"), "w", encoding="utf-8") as fh:
        fh.write("-- carga da massa (schema v0.9): abre particao POR carga, depois COPY\n")
        fh.write("\\set ON_ERROR_STOP on\n")
        for rot, m in manif.items():
            fh.write(f"SELECT fn_particao_carga('{m['id_carga']}');\n")
            fh.write(f"\\copy evento ({','.join(Emissor.COLS)}) FROM '{m['arquivo']}' CSV HEADER\n")
        fh.write("-- depois: REFRESH MATERIALIZED VIEW CONCURRENTLY mv_filme_servidor; etc.\n")

    print(f"[ok] vinculos={len(foto)} eventos_base={manif.get('carga_base',{}).get('eventos',0)} "
          f"folha={n_folha} lixo={manif.get('carga_lixo',{}).get('eventos',0)} data_ref={data_ref}")


if __name__ == "__main__":
    main()
