from atem.agrupamento import cid_pai, geojson_brasil, grupo_procedimento, regiao_da_uf, uf_do_especialista


def test_cid_pai():
    assert cid_pai("C508") == "C50" and cid_pai("c50.4") == "C50" and cid_pai("C61") == "C61"
    assert cid_pai(None) is None and cid_pai("") is None


def test_procedimentos_mesma_familia():
    a = grupo_procedimento("QUIMIOTERAPIA DO CARCINOMA DE MAMA EM ESTÁDIO I")
    b = grupo_procedimento("Quimioterapia do Carcinoma de Mama (prévia)")
    c = grupo_procedimento("QUIMIOTERAPIA DO CARCINOMA DE MAMA EM ESTÁDIO II E III")
    assert a == b
    assert grupo_procedimento(None) == "(não informado)"
    assert c.startswith("Quimioterapia")


def test_uf_e_regiao():
    assert uf_do_especialista("Roraima") == "RR" and uf_do_especialista("RJ") == "RJ"
    assert uf_do_especialista(None, "Secretaria de Saude do Estado do Ceara") == "CE"
    assert uf_do_especialista(None, "Hospital Regional - RJ") == "RJ"
    assert uf_do_especialista(None, "?") is None
    assert regiao_da_uf("CE") == "Nordeste" and regiao_da_uf(None) == "Não informada"


def test_geojson_tem_27_ufs():
    assert len(geojson_brasil()["features"]) == 27
