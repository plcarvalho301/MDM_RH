#!/usr/bin/env python3
# =============================================================================
# MDM-RH — Loader FOTO (conector custom da PoC)
# versao: v0.1
# ancora: 3_dag_ingestao.mermaid (v0.4) | 3_schema_mdm.sql (v0.5)
# -----------------------------------------------------------------------------
# Le servidor.csv (saida do gen_massa.py) e carrega em `servidor` via UPSERT
# (FOTO = sobrescreve por matricula_funcional). Segue o vocabulario do DAG:
#   valida     -> regras de negocio / formato. Falha => rejeito (nao trava a carga).
#   classifica -> nesta PoC e TRIVIAL: tudo que vem deste leitor e FOTO (nunca
#                 evento). Quando o leitor real (API/Extrator) entrar, classifica
#                 decide registro a registro — aqui so existe 1 caminho.
#   upsert     -> ON CONFLICT (matricula_funcional) DO UPDATE, como o schema manda.
#
# LEITOR AGNOSTICO A FONTE (ADR-006): este loader LE CSV. Trocar por leitor SOAP
#   da API SIAPE depois e outro arquivo — a metade valida/classifica/upsert daqui
#   e reaproveitavel (por isso esta separada em funcoes puras, testaveis sem DB).
#
# NULL HANDLING (ponto de falha nº1 identificado na entrega da massa):
#   O CSV grava campo ausente como "" (string vazia). Column NULLABLE do schema
#   precisa receber None/NULL, NAO ''. Ex.: cod_afastamento_vigente='' quebraria
#   a FK (nao existe afastamento de codigo vazio). Tratado em `_null_if_blank`.
#
# USO:
#   python carrega_foto.py --csv ../gerador/out/servidor.csv              # carga real
#   python carrega_foto.py --csv ../gerador/out/servidor.csv --dry-run    # so valida/classifica, sem DB
#
# CONEXAO: le de variaveis de ambiente (.env — ver .env.example neste dir):
#   PGHOST, PGPORT, PGDATABASE, PGUSER, PGPASSWORD
# DEP: psycopg2-binary (pip install psycopg2-binary --break-system-packages)
# =============================================================================
import csv, json, argparse, os, re, sys

# psycopg2 e opcional em --dry-run (permite testar valida/classifica sem DB/driver)
try:
    import psycopg2
    from psycopg2.extras import Json
except ImportError:
    psycopg2 = None

# --- colunas nullable vs not-null (espelha o CHECK/NOT NULL do schema v0.5) --
NULLABLE = {
    "classe", "padrao", "sigla_nivel_cargo", "funcao_comissionada", "nova_funcao",
    "data_ingresso_nova_funcao", "cod_unidade_exercicio", "regime_juridico",
    "cod_afastamento_vigente",
}
NOT_NULL = {
    "matricula_funcional", "cpf", "nome", "data_nascimento", "cargo",
    "cod_unidade_lotacao", "origem_unidade", "situacao_funcional",
    "data_referencia", "cod_mecanica",
}
RE_MATRICULA = re.compile(r"^[0-9]{7}$")
RE_CPF       = re.compile(r"^[0-9]{11}$")

COLS_SERVIDOR = [  # ordem = ordem do INSERT; espelha o CSV do gen_massa.py
    "matricula_funcional","cpf","nome","data_nascimento","cargo","classe","padrao",
    "sigla_nivel_cargo","funcao_comissionada","nova_funcao","data_ingresso_nova_funcao",
    "cod_unidade_lotacao","cod_unidade_exercicio","origem_unidade","situacao_funcional",
    "regime_juridico","data_exercicio_no_orgao","cod_afastamento_vigente",
    "data_referencia","cod_mecanica",
]

INT_COLS  = {"cod_unidade_lotacao", "cod_unidade_exercicio"}
DATE_COLS = {"data_nascimento","data_ingresso_nova_funcao","data_exercicio_no_orgao","data_referencia"}


def _null_if_blank(v):
    """CSV grava ausencia como ''. Coluna nullable precisa de None, nao ''."""
    return None if v == "" else v


def _data_iso(v):
    """A API real manda data como DDMMYYYY; o schema quer date. ISO passa direto."""
    if re.fullmatch(r"[0-9]{8}", v):
        return f"{v[4:]}-{v[2:4]}-{v[:2]}"
    return v


def valida(row: dict) -> tuple[bool, str]:
    """Regras de negocio / formato. Retorna (ok, motivo). Nao toca no banco."""
    for col in NOT_NULL:
        if not row.get(col):
            return False, f"campo_obrigatorio_ausente:{col}"
    if not RE_MATRICULA.match(row["matricula_funcional"]):
        return False, "matricula_malformada"
    if not RE_CPF.match(row["cpf"]):
        return False, "cpf_malformado"
    if row["cod_mecanica"] not in ("ingestao", "extracao"):
        return False, "cod_mecanica_invalida"
    try:
        int(row["cod_unidade_lotacao"])
    except (ValueError, TypeError):
        return False, "cod_unidade_lotacao_nao_numerico"
    return True, ""


def classifica(row: dict) -> str:
    """
    Decide a natureza do registro. NESTA PoC: sempre 'FOTO' (leitor de massa so
    produz estado vigente). Assinatura mantida igual ao pipeline real para que,
    quando o leitor SOAP/Extrator entrar, o classifica passe a de fato decidir
    registro a registro (ADR-006) sem precisar mudar quem chama esta funcao.
    """
    return "FOTO"


def prepara_linha(row: dict) -> dict:
    """Aplica null-handling e tipagem antes do INSERT."""
    out = {}
    for col in COLS_SERVIDOR:
        v = row.get(col, "")
        if col in NULLABLE:
            v = _null_if_blank(v)
        if v is not None and col in INT_COLS:
            v = int(v)
        if v is not None and col in DATE_COLS:
            v = _data_iso(v)
        out[col] = v
    return out


def carrega(csv_path: str, dry_run: bool = False):
    rows_ok, rows_rejeito = [], []
    with open(csv_path, encoding="utf-8") as f:
        for raw in csv.DictReader(f):
            ok, motivo = valida(raw)
            if not ok:
                rows_rejeito.append((motivo, raw))
                continue
            natureza = classifica(raw)
            assert natureza == "FOTO"  # unico caminho nesta PoC; guard explicito
            rows_ok.append(prepara_linha(raw))

    print(f"valida:     {len(rows_ok)} ok / {len(rows_rejeito)} rejeitados")
    if rows_rejeito:
        from collections import Counter
        motivos = Counter(m for m, _ in rows_rejeito)
        print(f"  motivos: {dict(motivos)}")

    if dry_run:
        print("[--dry-run] nao conecta no banco. Amostra da 1a linha preparada:")
        if rows_ok:
            print(" ", json.dumps(rows_ok[0], default=str, ensure_ascii=False))
        return

    if psycopg2 is None:
        sys.exit("psycopg2 nao instalado. pip install psycopg2-binary --break-system-packages")

    conn = psycopg2.connect(
        host=os.environ.get("PGHOST", "localhost"),
        port=os.environ.get("PGPORT", "5432"),
        dbname=os.environ.get("PGDATABASE", "mdm_rh"),
        user=os.environ.get("PGUSER", "mdm_rh"),
        password=os.environ.get("PGPASSWORD", ""),
    )
    conn.autocommit = False

    placeholders = ",".join(["%s"] * len(COLS_SERVIDOR))
    col_list = ",".join(COLS_SERVIDOR)
    update_set = ",".join(f"{c}=EXCLUDED.{c}" for c in COLS_SERVIDOR if c != "matricula_funcional")
    sql_upsert = f"""
        INSERT INTO servidor ({col_list}) VALUES ({placeholders})
        ON CONFLICT (matricula_funcional) DO UPDATE SET {update_set}
    """
    sql_rejeito = """
        INSERT INTO rejeito (fonte, cod_mecanica, motivo, registro_bruto)
        VALUES (%s, %s, %s, %s)
    """

    inseridos, falhas_upsert = 0, 0
    with conn.cursor() as cur:
        for linha in rows_ok:
            vals = [linha[c] for c in COLS_SERVIDOR]
            try:
                cur.execute(sql_upsert, vals)
                inseridos += 1
            except Exception as e:
                conn.rollback()
                cur.execute(sql_rejeito, (
                    "massa_ficticia", linha.get("cod_mecanica", "ingestao"),
                    f"falha_upsert:{type(e).__name__}", Json(linha, dumps=lambda o: json.dumps(o, default=str)),
                ))
                conn.commit()
                falhas_upsert += 1
                continue
        conn.commit()

        for motivo, raw in rows_rejeito:
            cur.execute(sql_rejeito, (
                "massa_ficticia", raw.get("cod_mecanica", "ingestao"), motivo,
                Json(raw, dumps=lambda o: json.dumps(o, default=str)),
            ))
        conn.commit()

    conn.close()
    print(f"carga: {inseridos} upserts ok, {falhas_upsert} falharam no upsert "
          f"(foram p/ rejeito), {len(rows_rejeito)} ja rejeitados na validacao.")
    print(f"total em rejeito nesta rodada: {falhas_upsert + len(rows_rejeito)}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", required=True, help="caminho do servidor.csv")
    ap.add_argument("--dry-run", action="store_true", help="so valida/classifica, nao conecta no banco")
    args = ap.parse_args()
    carrega(args.csv, dry_run=args.dry_run)
