# -----------------------------------------------------------------------------
# Payloads descartaveis p/ smoke test do pipeline de EVENTO (cod_mecanica=ingestao).
# NAO e gen_massa.py v2 (trajetoria) — e anterior a ele. Objetivo unico: provar
# que classifica/valida separam evento bom de evento torto, com AFASTAMENTO
# como tipo de teste (fonte historica completa, sem pendencia dupla-face).
#
# Cobertura (7 bifurcacoes fechadas na sessao):
#   1. limpo, data_fim nula (aberto)              -> carrega em evento
#   2. limpo, data_fim preenchida                 -> carrega em evento
#   3. cod_afastamento fora de dom_afastamento     -> rejeito (fk_afastamento_inexistente)
#   4. matricula_funcional fora do regex 7 digitos -> rejeito (matricula_malformada)
#   5. cpf fora do regex 11 digitos                -> rejeito (cpf_malformado)
#   6. data_evento ausente                         -> rejeito (data_ausente)
#   7. duplicata exata de chave candidata           -> observar comportamento (sem UNIQUE hoje)
#
# + 1 caso fora das 7, exercitando o check de lote fechado nesta sessao (ADR-007
#   candidata): matricula sintaticamente valida mas inexistente em `servidor`.
#   Nao e CHECK/FK do schema — e a regra de negocio que o loader aplica em valida.
# -----------------------------------------------------------------------------

PAYLOADS_AFASTAMENTO = [
    # 1. limpo, aberto (sem data_fim)
    {
        "caso": "limpo_aberto",
        "matricula_funcional": "1000001",
        "cpf": "11111111111",
        "cod_tipo_evento": "AFASTAMENTO",
        "data_evento": "2024-03-01",
        "cod_mecanica": "ingestao",
        "fonte": "API_SIAPE_CONSULTAS",
        "grau_confianca": "alto",
        "payload": {
            "cod_afastamento": "01",       # Acidente/Doenca do Trabalho — existe no seed
            "data_inicio": "2024-03-01",
            "data_fim": None,
        },
    },
    # 2. limpo, fechado (com data_fim)
    {
        "caso": "limpo_fechado",
        "matricula_funcional": "1000002",
        "cpf": "22222222222",
        "cod_tipo_evento": "AFASTAMENTO",
        "data_evento": "2023-06-10",
        "cod_mecanica": "ingestao",
        "fonte": "API_SIAPE_CONSULTAS",
        "grau_confianca": "alto",
        "payload": {
            "cod_afastamento": "15",       # Gozo de Ferias ou Recesso
            "data_inicio": "2023-06-10",
            "data_fim": "2023-07-09",
        },
    },
    # 3. cod_afastamento inexistente em dom_afastamento -> FK falha
    {
        "caso": "fk_afastamento_inexistente",
        "matricula_funcional": "1000003",
        "cpf": "33333333333",
        "cod_tipo_evento": "AFASTAMENTO",
        "data_evento": "2024-01-15",
        "cod_mecanica": "ingestao",
        "fonte": "API_SIAPE_CONSULTAS",
        "grau_confianca": "alto",
        "payload": {
            "cod_afastamento": "99",       # nao existe no seed (so ha 17 codigos validos)
            "data_inicio": "2024-01-15",
            "data_fim": None,
        },
    },
    # 4. matricula malformada (nao bate ^[0-9]{7}$)
    {
        "caso": "matricula_malformada",
        "matricula_funcional": "ABC123",
        "cpf": "44444444444",
        "cod_tipo_evento": "AFASTAMENTO",
        "data_evento": "2024-02-20",
        "cod_mecanica": "ingestao",
        "fonte": "API_SIAPE_CONSULTAS",
        "grau_confianca": "alto",
        "payload": {
            "cod_afastamento": "01",
            "data_inicio": "2024-02-20",
            "data_fim": None,
        },
    },
    # 5. cpf malformado (nao bate ^[0-9]{11}$)
    {
        "caso": "cpf_malformado",
        "matricula_funcional": "1000005",
        "cpf": "123",
        "cod_tipo_evento": "AFASTAMENTO",
        "data_evento": "2024-02-21",
        "cod_mecanica": "ingestao",
        "fonte": "API_SIAPE_CONSULTAS",
        "grau_confianca": "alto",
        "payload": {
            "cod_afastamento": "01",
            "data_inicio": "2024-02-21",
            "data_fim": None,
        },
    },
    # 6. data_evento ausente
    {
        "caso": "data_ausente",
        "matricula_funcional": "1000006",
        "cpf": "66666666666",
        "cod_tipo_evento": "AFASTAMENTO",
        "data_evento": None,
        "cod_mecanica": "ingestao",
        "fonte": "API_SIAPE_CONSULTAS",
        "grau_confianca": "alto",
        "payload": {
            "cod_afastamento": "01",
            "data_inicio": "2024-02-22",
            "data_fim": None,
        },
    },
    # 7a. primeira ocorrencia da chave candidata (matricula, cod_afastamento, data_inicio)
    {
        "caso": "duplicata_chave_1a",
        "matricula_funcional": "1000007",
        "cpf": "77777777777",
        "cod_tipo_evento": "AFASTAMENTO",
        "data_evento": "2024-04-01",
        "cod_mecanica": "ingestao",
        "fonte": "API_SIAPE_CONSULTAS",
        "grau_confianca": "alto",
        "payload": {
            "cod_afastamento": "03",       # Acidente/Doenca nao relacionada ao trabalho
            "data_inicio": "2024-04-01",
            "data_fim": None,
        },
    },
    # 7b. segunda ocorrencia, mesma chave candidata — nao ha UNIQUE hoje, entra as duas
    {
        "caso": "duplicata_chave_2a",
        "matricula_funcional": "1000007",
        "cpf": "77777777777",
        "cod_tipo_evento": "AFASTAMENTO",
        "data_evento": "2024-04-01",
        "cod_mecanica": "ingestao",
        "fonte": "API_SIAPE_CONSULTAS",
        "grau_confianca": "alto",
        "payload": {
            "cod_afastamento": "03",
            "data_inicio": "2024-04-01",
            "data_fim": None,
        },
    },
    # 8. matricula sintaticamente valida, mas SEM linha correspondente em `servidor`.
    #    Nao e CHECK/FK do schema. Exercita o check em lote (ADR-007 candidata):
    #    toda matricula que carrega evento deveria ter linha carregavel em servidor
    #    (API ou fonte da verdade pre-projeto disponivel em csv de propriedade do RH).
    #    Aqui, de proposito, a matricula NAO foi carregada em servidor -> deve cair
    #    em rejeito por "matricula_orfa_servidor", nao por CHECK/FK do banco.
    {
        "caso": "matricula_orfa_servidor",
        "matricula_funcional": "9999999",
        "cpf": "88888888888",
        "cod_tipo_evento": "AFASTAMENTO",
        "data_evento": "2024-05-01",
        "cod_mecanica": "ingestao",
        "fonte": "API_SIAPE_CONSULTAS",
        "grau_confianca": "alto",
        "payload": {
            "cod_afastamento": "01",
            "data_inicio": "2024-05-01",
            "data_fim": None,
        },
    },
]
