#!/usr/bin/env python3
# =============================================================================
# MDM-RH — Gerador de massa ficticia (FOTO)
# versao: v0.1
# -----------------------------------------------------------------------------
# Le config.yaml e gera massa de FOTO (tabela servidor). NAO gera eventos.
# Saidas em ./out/:
#   servidor.csv       -> FOTO (grao vinculo), pronto p/ COPY em `servidor`
#   pessoa.csv         -> cadastro (grao CPF): sexo, naturalidade. Tabela `cadastro`
#                         nao existe no schema v0.5; emitido a parte.
#   seed_unidades.sql  -> INSERT das UORGs ficticias VALIDAS em dom_unidade_eorg
#                         (as lotacoes orfas apontam p/ codigos FORA desta lista => KR 2.1)
#
# COERENCIA TEMPORAL (contrato com o futuro gerador de eventos):
#   nascimento -> ingresso -> tempo de casa -> classe/padrao possivel.
#   Interstício EPPGG: ~ 12-18 meses por padrao. 20 padroes => ~20 anos ao topo.
#   Regra pratica adotada: exige >= (anos_min_por_classe) de casa p/ cada classe.
#
# Uso: python gen_massa.py  [--config config.yaml]
# Dep: PyYAML  (pip install pyyaml --break-system-packages)
# =============================================================================
import csv, random, argparse, os, sys, datetime as dt
try:
    import yaml
except ImportError:
    sys.exit("Falta PyYAML: pip install pyyaml --break-system-packages")

# --- capitais brasileiras (naturalidade quando nao-DF) -----------------------
CAPITAIS = [
    ("AC","Rio Branco"),("AL","Maceio"),("AP","Macapa"),("AM","Manaus"),
    ("BA","Salvador"),("CE","Fortaleza"),("ES","Vitoria"),("GO","Goiania"),
    ("MA","Sao Luis"),("MT","Cuiaba"),("MS","Campo Grande"),("MG","Belo Horizonte"),
    ("PA","Belem"),("PB","Joao Pessoa"),("PR","Curitiba"),("PE","Recife"),
    ("PI","Teresina"),("RJ","Rio de Janeiro"),("RN","Natal"),("RS","Porto Alegre"),
    ("RO","Porto Velho"),("RR","Boa Vista"),("SC","Florianopolis"),("SP","Sao Paulo"),
    ("SE","Aracaju"),("TO","Palmas"),
]
CLASSES_ORD = ["A","B","C","ESPECIAL"]
PADROES = ["I","II","III","IV","V"]
# anos MINIMOS de casa p/ estar em cada classe (coerencia: nao dar ESPECIAL a novato)
ANOS_MIN_CLASSE = {"A":0, "B":5, "C":10, "ESPECIAL":15}

def weighted(d, rnd):
    """sorteia chave de dict {valor: peso}."""
    ks, ws = list(d.keys()), list(d.values())
    return rnd.choices(ks, weights=ws, k=1)[0]

def gera_cpf(rnd):
    return "".join(str(rnd.randint(0,9)) for _ in range(11))

def fmt(d):  # date -> DDMMYYYY (formato da API real; parser trata como string)
    return d.strftime("%d%m%Y")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default=os.path.join(os.path.dirname(__file__),"config.yaml"))
    ap.add_argument("--outdir", default=os.path.join(os.path.dirname(__file__),"out"))
    args = ap.parse_args()
    cfg = yaml.safe_load(open(args.config, encoding="utf-8"))
    rnd = random.Random(cfg.get("seed_aleatorio"))
    os.makedirs(args.outdir, exist_ok=True)

    # data de referencia (D-1)
    if cfg["data_referencia"] == "ontem":
        d_ref = dt.date.today() - dt.timedelta(days=1)
    else:
        d_ref = dt.date.fromisoformat(cfg["data_referencia"])

    # --- UORGs validas (E-Org ficticio) --------------------------------------
    n_uorg = cfg["n_uorgs"]
    uorgs_validas = list(range(1001, 1001 + n_uorg))   # codigos 1001..
    # pool de codigos ORFAOS (fora do E-Org) p/ lotacoes orfas
    uorgs_orfas = list(range(9001, 9051))

    n = cfg["n_servidores"]
    # quantos CPFs distintos (multivinculo reduz nº de pessoas p/ mesmo nº de vinculos)
    mv = cfg["multivinculo_pct"]

    servidores = []   # linhas de FOTO (vinculo)
    pessoas = {}      # cpf -> dados de pessoa (grao CPF)
    matriculas = set()
    def nova_matricula():
        while True:
            m = f"{rnd.randint(1000000,9999999)}"
            if m not in matriculas:
                matriculas.add(m); return m

    i = 0
    while len(servidores) < n:
        i += 1
        # decide se este e um CPF novo ou reaproveita p/ multivinculo
        reuse = pessoas and rnd.random() < mv
        if reuse:
            cpf = rnd.choice(list(pessoas.keys()))
            p = pessoas[cpf]
        else:
            cpf = gera_cpf(rnd)
            sexo = weighted(cfg["sexo"], rnd)
            # naturalidade
            if rnd.random() < cfg["geografia"]["DF_Brasilia"]:
                uf, mun = "DF", "Brasilia"
            else:
                uf, mun = rnd.choice(CAPITAIS)
            idade = rnd.randint(cfg["idade"]["min"], cfg["idade"]["max"])
            nasc = dt.date(d_ref.year - idade, rnd.randint(1,12), rnd.randint(1,28))
            nome = f"Servidor {'M' if sexo=='M' else 'F'} {len(pessoas)+1:04d}"
            p = dict(cpf=cpf, sexo=sexo, uf=uf, mun=mun, nasc=nasc, idade=idade, nome=nome)
            pessoas[cpf] = p

        # --- ingresso coerente com idade ------------------------------------
        idade_ing = rnd.randint(cfg["idade_ingresso"]["min"], cfg["idade_ingresso"]["max"])
        idade_ing = min(idade_ing, p["idade"])              # nao pode ingressar antes de nascer, obvio
        ano_ing = p["nasc"].year + idade_ing
        d_ingresso = dt.date(ano_ing, rnd.randint(1,12), rnd.randint(1,28))
        if d_ingresso > d_ref:                              # clampa ao D-1 (nao ingressa no futuro)
            d_ingresso = d_ref - dt.timedelta(days=rnd.randint(30,365))
        anos_casa = (d_ref - d_ingresso).days / 365.25

        # --- classe coerente com tempo de casa ------------------------------
        # sorteia por peso, mas rebaixa se nao tiver tempo p/ a classe sorteada
        classe = weighted(cfg["classe_peso"], rnd)
        while ANOS_MIN_CLASSE[classe] > anos_casa and classe != "A":
            classe = CLASSES_ORD[CLASSES_ORD.index(classe)-1]   # desce um degrau
        # --- padrao coerente: ~1 padrao a cada 1.2 anos DENTRO da classe -----
        # anos "gastos" ate entrar na classe atual ja foram no degrau anterior;
        # o excedente sobre o minimo da classe define ate onde subiu o padrao.
        excedente = anos_casa - ANOS_MIN_CLASSE[classe]
        max_padrao_idx = min(4, max(0, int(excedente / 1.2)))   # 0..4 -> I..V
        padrao = PADROES[rnd.randint(0, max_padrao_idx)]

        # --- situacao (aposentado exige idade/tempo) ------------------------
        situacao = weighted(cfg["situacao"], rnd)
        if situacao == "INATIVO" and (p["idade"] < 50 or anos_casa < 10):
            situacao = "ATIVO"     # sem lastro p/ aposentadoria => ativo

        regime = weighted(cfg["regime"], rnd)

        # --- lotacao (com orfaos de proposito) ------------------------------
        if rnd.random() < cfg["orfao_estrutural_pct"]:
            lot = rnd.choice(uorgs_orfas); origem = "SIAPE"   # orfao: nao resolve no E-Org
        else:
            lot = rnd.choice(uorgs_validas); origem = "SIORG"
        exerc = lot
        if rnd.random() < cfg["exercicio_difere_lotacao_pct"]:
            exerc = rnd.choice(uorgs_validas)

        # --- funcao comissionada (CCE/FCE) ----------------------------------
        funcao = ""
        if rnd.random() < cfg["funcao_comissionada_pct"]:
            trilha = weighted(cfg["funcao_trilha_peso"], rnd)
            nivel = rnd.randint(cfg["funcao_nivel"]["min"], cfg["funcao_nivel"]["max"])
            # cat 4 e so FCE e so ate nivel 13; cat 3 ate 16; cat 2 ate 17; cat1 ate 18
            teto = {"1":18,"2":17,"3":16,"4":13}[trilha]
            nivel = min(nivel, teto)
            tipo = "FCE" if (trilha=="4" or rnd.random()<0.7) else "CCE"  # efetivo: mais FCE
            funcao = f"{tipo} {trilha}.{nivel:02d}"

        nova_funcao = ""
        d_nova = ""
        if funcao and rnd.random() < cfg["nova_funcao_pct"]:
            nova_funcao = funcao  # simplificacao: transicao p/ mesma faixa
            d_nova = fmt(d_ref - dt.timedelta(days=rnd.randint(1,90)))

        # --- afastamento vigente --------------------------------------------
        afast = ""
        if rnd.random() < cfg["afastado_vigente_pct"]:
            afast = rnd.choice(["01","03","07","15","10","05","40","31","24","29"])

        servidores.append(dict(
            matricula_funcional=nova_matricula(), cpf=cpf, nome=p["nome"],
            data_nascimento=p["nasc"].isoformat(),
            cargo=cfg["cargo_fixo"], classe=classe, padrao=padrao,
            sigla_nivel_cargo=cfg["nivel_cargo_fixo"],
            funcao_comissionada=funcao, nova_funcao=nova_funcao,
            data_ingresso_nova_funcao=d_nova,
            cod_unidade_lotacao=lot, cod_unidade_exercicio=exerc, origem_unidade=origem,
            situacao_funcional=situacao, regime_juridico=regime,
            data_exercicio_no_orgao=d_ingresso.isoformat(),
            cod_afastamento_vigente=afast,
            data_referencia=d_ref.isoformat(), cod_mecanica="ingestao",
        ))

    # --- escreve saidas ------------------------------------------------------
    cols = list(servidores[0].keys())
    with open(os.path.join(args.outdir,"servidor.csv"),"w",newline="",encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols); w.writeheader(); w.writerows(servidores)

    with open(os.path.join(args.outdir,"pessoa.csv"),"w",newline="",encoding="utf-8") as f:
        w = csv.writer(f); w.writerow(["cpf","sexo","uf_nascimento","municipio_nascimento","data_nascimento"])
        for cpf,p in pessoas.items():
            w.writerow([cpf,p["sexo"],p["uf"],p["mun"],p["nasc"].isoformat()])

    with open(os.path.join(args.outdir,"seed_unidades.sql"),"w",encoding="utf-8") as f:
        f.write("-- UORGs ficticias VALIDAS (E-Org). Lotacoes orfas apontam FORA desta lista (KR 2.1).\n")
        f.write("INSERT INTO dom_unidade_eorg (cod_unidade, nome_unidade) VALUES\n")
        linhas = [f"    ({c}, 'Unidade Ficticia {c}')" for c in uorgs_validas]
        f.write(",\n".join(linhas) + "\nON CONFLICT (cod_unidade) DO NOTHING;\n")

    # --- relatorio -----------------------------------------------------------
    from collections import Counter
    print(f"Gerados: {len(servidores)} vinculos / {len(pessoas)} pessoas (CPFs distintos)")
    print(f"  multivinculo real: {len(servidores)-len(pessoas)} vinculos extras "
          f"({100*(len(servidores)-len(pessoas))/len(servidores):.1f}%)")
    sx = Counter(p['sexo'] for p in pessoas.values())
    print(f"  sexo: {dict(sx)}  ({100*sx['M']/len(pessoas):.0f}% M)")
    df = sum(1 for p in pessoas.values() if p['uf']=='DF')
    print(f"  naturalidade DF: {100*df/len(pessoas):.0f}%")
    orf = sum(1 for s in servidores if s['cod_unidade_lotacao']>=9001)
    print(f"  orfao estrutural: {orf} ({100*orf/len(servidores):.1f}%)")
    fc = sum(1 for s in servidores if s['funcao_comissionada'])
    print(f"  com funcao FCE/CCE: {fc} ({100*fc/len(servidores):.1f}%)")
    cl = Counter(s['classe'] for s in servidores)
    print(f"  classe: {dict(cl)}")
    si = Counter(s['situacao_funcional'] for s in servidores)
    print(f"  situacao: {dict(si)}")
    # sanity de coerencia: algum ESPECIAL com pouco tempo de casa? ingresso futuro?
    ruins = 0; futuros = 0
    for s in servidores:
        d_ing = dt.date.fromisoformat(s['data_exercicio_no_orgao'])
        anos = (d_ref - d_ing).days / 365.25
        if s['classe']=='ESPECIAL' and anos < ANOS_MIN_CLASSE['ESPECIAL']:
            ruins += 1
        if d_ing > d_ref:
            futuros += 1
    print(f"  [coerencia] ESPECIAL com < {ANOS_MIN_CLASSE['ESPECIAL']} anos de casa: {ruins} (esperado 0)")
    print(f"  [coerencia] ingresso no futuro: {futuros} (esperado 0)")

if __name__ == "__main__":
    main()
