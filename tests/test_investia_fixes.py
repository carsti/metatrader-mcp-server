"""
Testes de regressão das quatro correções aplicadas para o InvestIA Trader.

Princípio que vale mais que a contagem de testes: nenhuma asserção sobre texto
de código-fonte para provar registro de ferramenta. `"@mcp.tool()" in fonte`
passa com o decorador comentado, dentro de docstring, ou aplicado ao wrapper
errado -- exatamente a classe de erro que o defeito #25 era. Quem responde é o
registry do FastMCP.

    pytest tests/test_investia_fixes.py -v
"""

import importlib
import inspect
import json
import pathlib
import re
import sys
from datetime import date, datetime, timedelta, timezone

import pytest

try:
    from tests.conftest import precisa_de_mt5_real, MT5_REAL_DISPONIVEL
except ImportError:  # pytest invocado com tests/ como rootdir
    from conftest import precisa_de_mt5_real, MT5_REAL_DISPONIVEL


# ---------------------------------------------------------------- utilidades
# Armadilha: account/__init__.py reexporta a FUNÇÃO get_account_type com o
# mesmo nome do MÓDULO. `import ...account.get_account_type as m` entrega a
# função, e monkeypatch.setattr(m, ...) estoura. Pegue o módulo em sys.modules.
importlib.import_module("metatrader_client.account.get_account_type")
_tipo = sys.modules["metatrader_client.account.get_account_type"]

importlib.import_module("metatrader_client.account.get_account_info")
_info = sys.modules["metatrader_client.account.get_account_info"]

importlib.import_module("metatrader_client.account.get_trade_statistics")
_stats = sys.modules["metatrader_client.account.get_trade_statistics"]

from metatrader_client.history import _time_window as tw  # noqa: E402

_RAIZ = pathlib.Path(__file__).resolve().parent.parent
_HISTORY = _RAIZ / "src" / "metatrader_client" / "history"


class _Conn:
    """Conexão falsa que sempre se diz conectada."""

    def is_connected(self):
        return True


def _patch_info(monkeypatch, trade_mode, **extra):
    dados = {"trade_mode": trade_mode}
    dados.update(extra)
    monkeypatch.setattr(_tipo, "get_account_info", lambda _c: dict(dados))
    return dados


def _agora():
    return datetime.now(timezone.utc).replace(tzinfo=None)


# ============================================================== DEFEITO 1
# ENUM_ACCOUNT_TRADE_MODE (MQL5): 0 = DEMO, 1 = CONTEST, 2 = REAL.

@pytest.mark.parametrize(
    "trade_mode,esperado", [(0, "demo"), (1, "contest"), (2, "real")]
)
def test_mapeamento_segue_o_enum_do_mql5(monkeypatch, trade_mode, esperado):
    _patch_info(monkeypatch, trade_mode)
    assert _tipo.get_account_type(_Conn()) == esperado


def test_conta_demo_nunca_mais_e_chamada_de_real(monkeypatch):
    """Regressão direta do issue #24: trade_mode 0 devolvia 'real'."""
    _patch_info(monkeypatch, 0)
    assert _tipo.get_account_type(_Conn()) == "demo"
    assert _tipo.get_account_type(_Conn()) != "real"


def test_tabela_de_modos_nao_tem_rotulo_duplicado():
    assert sorted(_tipo._TRADE_MODE.values()) == ["contest", "demo", "real"]


def test_modo_fora_do_enum_e_rotulado_como_desconhecido(monkeypatch):
    _patch_info(monkeypatch, 99)
    assert _tipo.get_account_type(_Conn()) == "unknown (99)"


@pytest.mark.parametrize(
    "trade_mode,bloqueia",
    [(0, False), (1, False), (2, True), (99, True), (-1, True), (None, True)],
)
def test_guarda_fail_closed_bloqueia_o_desconhecido(
    monkeypatch, trade_mode, bloqueia
):
    """
    Qualquer trade_mode fora de {0,1} bloqueia. É a permissão que exige prova,
    não o bloqueio.
    """
    _patch_info(monkeypatch, trade_mode)
    assert _tipo.blocks_live_trading(_Conn()) is bloqueia


def test_guarda_bloqueia_ate_com_trade_mode_nao_hasheavel(monkeypatch):
    """Um trade_mode impossível de classificar continua bloqueando."""
    _patch_info(monkeypatch, ["lixo"])
    assert _tipo.blocks_live_trading(_Conn()) is True


@pytest.mark.parametrize(
    "trade_mode,esperado",
    [(0, ("demo", False)), (1, ("contest", False)), (2, ("real", True))],
)
def test_classify_account_devolve_rotulo_e_guarda(
    monkeypatch, trade_mode, esperado
):
    _patch_info(monkeypatch, trade_mode)
    assert _tipo.classify_account(_Conn()) == esperado


def test_classify_account_faz_um_unico_round_trip(monkeypatch):
    """A razão de existir da função: um fato lido uma vez, não duas."""
    chamadas = []

    def _contando(_c):
        chamadas.append(1)
        return {"trade_mode": 0}

    monkeypatch.setattr(_tipo, "get_account_info", _contando)
    _tipo.classify_account(_Conn())
    assert len(chamadas) == 1


def test_nome_is_real_account_nao_voltou():
    """
    Sob semântica fail-closed um nome positivo produz afirmação falsa quando o
    modo é desconhecido. Se ele reaparecer, este teste quebra.
    """
    import metatrader_client.account as pacote

    assert not hasattr(_tipo, "is_real_account")
    assert not hasattr(pacote, "is_real_account")


def test_guardas_estao_exportadas_no_pacote():
    import metatrader_client.account as pacote

    assert pacote.blocks_live_trading is _tipo.blocks_live_trading
    assert pacote.classify_account is _tipo.classify_account
    assert pacote.classify_trade_mode is _tipo.classify_trade_mode
    assert "blocks_live_trading" in pacote.__all__
    assert "classify_account" in pacote.__all__
    assert "classify_trade_mode" in pacote.__all__


def test_docstring_do_trade_mode_segue_o_enum():
    doc = _info.get_account_info.__doc__
    assert "0-demo, 1-contest, 2-real" in doc
    assert "0-real" not in doc


@pytest.mark.parametrize(
    "trade_mode,esperado",
    [(0, ("demo", False)), (1, ("contest", False)), (2, ("real", True)),
     (99, ("unknown (99)", True))],
)
def test_classify_trade_mode_e_pura(trade_mode, esperado):
    """Classifica sem tocar no terminal -- é o que permite o round-trip único."""
    assert _tipo.classify_trade_mode(trade_mode) == esperado


def test_get_trade_statistics_faz_um_unico_round_trip(monkeypatch):
    """
    Antes eram dois: get_account_info na própria função mais o de dentro de
    get_account_type. Trocar por classify_account não teria resolvido -- ele
    também lê. Só a classificação pura corta a segunda leitura.
    """
    conta = {
        "trade_mode": 0, "balance": 1.0, "equity": 1.0, "profit": 0.0,
        "margin_level": 0.0, "margin_free": 1.0, "leverage": 100,
        "currency": "BRL",
    }
    chamadas = []

    def _contando(_c):
        chamadas.append(1)
        return dict(conta)

    monkeypatch.setattr(_stats, "get_account_info", _contando)
    monkeypatch.setattr(_tipo, "get_account_info", _contando)
    assert _stats.get_trade_statistics(_Conn())["account_type"] == "demo"
    assert len(chamadas) == 1


def test_rotulo_corrigido_chega_ao_consumidor_real(monkeypatch):
    """
    get_trade_statistics alimenta a ferramenta MCP get_account_info -- era por
    ele que o rótulo errado chegava ao cliente.
    """
    conta = {
        "trade_mode": 0, "balance": 1.0, "equity": 1.0, "profit": 0.0,
        "margin_level": 0.0, "margin_free": 1.0, "leverage": 100,
        "currency": "BRL",
    }
    monkeypatch.setattr(_stats, "get_account_info", lambda _c: dict(conta))
    monkeypatch.setattr(_tipo, "get_account_info", lambda _c: dict(conta))
    assert _stats.get_trade_statistics(_Conn())["account_type"] == "demo"


# ============================================================== DEFEITO 2
# mt5.history_*_get() leem datetime naive como hora do SERVIDOR (UTC).

def test_utc_now_naive_e_naive_e_carrega_utc():
    agora = tw.utc_now_naive()
    assert agora.tzinfo is None
    assert abs((agora - _agora()).total_seconds()) < 5


def test_default_inferior_alcanca_trinta_dias_atras():
    inicio, _ = tw.normalize_window()
    assert timedelta(days=29) < (_agora() - inicio) < timedelta(days=31)


def test_default_superior_tem_folga_a_frente_do_utc():
    """
    Causa-raiz do issue #26. Em Cataguases (UTC-3) contra servidor em UTC+2/+3,
    terminar a janela no relógio local descarta de 3 a 6 horas de atividade --
    o negócio de fechamento existe mas cai fora, e a posição fechada continua
    aparecendo como aberta.
    """
    _, fim = tw.normalize_window()
    agora = _agora()
    assert fim > agora
    assert fim - agora >= timedelta(hours=6)


def test_janela_default_cobre_negocio_carimbado_em_utc_mais_3():
    inicio, fim = tw.normalize_window()
    negocio_no_servidor = _agora() + timedelta(hours=3)
    assert inicio <= negocio_no_servidor <= fim


def test_pedir_os_deals_de_hoje_contem_o_agora():
    """
    O ramo que uma correção parcial deixa passar: strptime('%Y-%m-%d') dá
    meia-noite naive, o MT5 lê como UTC, e "os deals de hoje" volta vazio.
    """
    hoje = _agora().strftime("%Y-%m-%d")
    inicio, fim = tw.normalize_window(hoje, hoje)
    assert inicio <= _agora() <= fim


def test_dia_explicito_cobre_todo_o_intervalo_de_offset_de_servidor():
    hoje = _agora().date()
    inicio, fim = tw.normalize_window(hoje, hoje)
    assert inicio <= datetime.combine(hoje, datetime.min.time())
    assert fim >= datetime.combine(hoje, datetime.max.time())


def test_string_com_offset_menos_03_vira_utc():
    inicio, _ = tw.normalize_window("2026-08-08T10:00:00-03:00", "2026-08-09T00:00")
    assert inicio == datetime(2026, 8, 8, 13, 0)


def test_datetime_aware_vira_naive_utc():
    aware = datetime(2026, 8, 8, 10, 0, tzinfo=timezone(timedelta(hours=-3)))
    inicio, _ = tw.normalize_window(aware, datetime(2026, 8, 9))
    assert inicio == datetime(2026, 8, 8, 13, 0)
    assert inicio.tzinfo is None


def test_ambos_os_limites_saem_sempre_naive():
    inicio, fim = tw.normalize_window("2026-08-08T10:00:00+02:00", None)
    assert inicio.tzinfo is None and fim.tzinfo is None


@pytest.mark.parametrize(
    "entrada,esperado",
    [
        ("2026-08-08 14:30", datetime(2026, 8, 8, 14, 30)),
        ("2026-08-08T14:30:15", datetime(2026, 8, 8, 14, 30, 15)),
        ("2026/08/08 14:30", datetime(2026, 8, 8, 14, 30)),
        ("08/08/2026 14:30", datetime(2026, 8, 8, 14, 30)),
    ],
)
def test_formatos_de_datetime_aceitos(entrada, esperado):
    inicio, _ = tw.normalize_window(entrada, "2026-09-01T00:00")
    assert inicio == esperado


@pytest.mark.parametrize("entrada", ["2026-08-08", "2026/08/08", "08/08/2026"])
def test_formatos_de_data_pura_aceitos(entrada):
    inicio, _ = tw.normalize_window(entrada, "2026-09-01T00:00")
    assert inicio == datetime(2026, 8, 7, 0, 0)  # início do dia menos a folga


def test_objeto_date_e_aceito():
    inicio, _ = tw.normalize_window(date(2026, 8, 8), datetime(2026, 9, 1))
    assert inicio == datetime(2026, 8, 7, 0, 0)


def test_limites_invertidos_sao_trocados():
    inicio, fim = tw.normalize_window("2026-08-10T00:00", "2026-08-01T00:00")
    assert inicio == datetime(2026, 8, 1)
    assert fim == datetime(2026, 8, 10)
    assert inicio < fim


@pytest.mark.parametrize("ruim", ["ontem", "", "2026-13-45", 12345, object()])
def test_data_ilegivel_levanta_valueerror(ruim):
    """Nunca silencie: janela errada é pior que falha alta."""
    with pytest.raises(ValueError, match=r"^Unrecognised date"):
        tw.normalize_window(ruim, None)


def test_default_lookback_e_configuravel():
    inicio, _ = tw.normalize_window(default_lookback=timedelta(days=7))
    assert timedelta(days=6) < (_agora() - inicio) < timedelta(days=8)


def test_nenhum_datetime_now_ingenuo_em_history():
    """Varredura: `datetime.now()` sem tz não pode voltar ao pacote."""
    ofensores = []
    for arq in _HISTORY.glob("*.py"):
        if arq.name == "_time_window.py":
            continue
        for n, linha in enumerate(arq.read_text(encoding="utf-8").splitlines(), 1):
            if re.search(r"datetime\.now\(\s*\)", linha):
                ofensores.append(f"{arq.name}:{n}")
    assert not ofensores, f"datetime.now() ingênuo em: {ofensores}"


def test_nenhum_strptime_em_history_fora_do_time_window():
    """O parse tem de acontecer num lugar só, senão o ramo explícito diverge."""
    ofensores = []
    for arq in _HISTORY.glob("*.py"):
        if arq.name == "_time_window.py":
            continue
        for n, linha in enumerate(arq.read_text(encoding="utf-8").splitlines(), 1):
            if "strptime" in linha:
                ofensores.append(f"{arq.name}:{n}")
    assert not ofensores, f"strptime fora do _time_window.py em: {ofensores}"


_MODULOS_HISTORICO = [
    ("metatrader_client.history.get_deals", "get_deals", "history_deals_get"),
    ("metatrader_client.history.get_orders", "get_orders", "history_orders_get"),
    ("metatrader_client.history.get_total_deals", "get_total_deals",
     "history_deals_total"),
    ("metatrader_client.history.get_total_orders", "get_total_orders",
     "history_orders_total"),
]


def _janela_capturada(monkeypatch, modulo, funcao, alvo, *args):
    """Espiona, via monkeypatch, o par (from, to) entregue ao MT5."""
    mod = importlib.import_module(modulo)
    capturado = {}

    def _spy(from_date, to_date, **kwargs):
        capturado["from"] = from_date
        capturado["to"] = to_date
        return () if "total" not in funcao else 0

    monkeypatch.setattr(mod.mt5, alvo, _spy)
    getattr(mod, funcao)(_Conn(), *args)
    return capturado


@pytest.mark.parametrize("modulo,funcao,alvo", _MODULOS_HISTORICO)
def test_modulo_de_historico_usa_janela_normalizada(
    monkeypatch, modulo, funcao, alvo
):
    cap = _janela_capturada(monkeypatch, modulo, funcao, alvo)
    agora = _agora()
    assert cap["to"] > agora
    assert cap["to"] - agora >= timedelta(hours=6)
    assert cap["from"].tzinfo is None and cap["to"].tzinfo is None
    assert cap["from"] <= agora + timedelta(hours=3) <= cap["to"]


@pytest.mark.parametrize(
    "modulo,funcao,alvo", _MODULOS_HISTORICO[:2]  # os que aceitam string
)
def test_ramo_de_data_explicita_tambem_normaliza(
    monkeypatch, modulo, funcao, alvo
):
    """A metade do issue #26 que uma correção parcial deixa passar."""
    hoje = _agora().strftime("%Y-%m-%d")
    cap = _janela_capturada(monkeypatch, modulo, funcao, alvo, hoje, hoje)
    assert cap["from"] <= _agora() <= cap["to"]


# ============================================================== DEFEITO 3

import metatrader_mcp.server as servidor  # noqa: E402

_FERRAMENTAS_ESPERADAS = 27


def _registry():
    """O registry real do FastMCP -- a única autoridade sobre o que existe."""
    gerente = servidor.mcp._tool_manager
    tools = getattr(gerente, "_tools", None)
    if tools is not None:
        return dict(tools)
    import anyio

    return {t.name: t for t in anyio.run(servidor.mcp.list_tools)}


def _impl(nome):
    """A implementação por trás da ferramenta registrada."""
    ferramenta = _registry()[nome]
    return getattr(ferramenta, "fn", None) or getattr(servidor, nome)


def test_get_candles_by_date_esta_registrada():
    """Estava definida sem @mcp.tool(): código morto, invisível ao cliente."""
    assert "get_candles_by_date" in _registry()


def test_get_symbol_info_esta_registrada():
    """Sem ela não há volume_min/volume_step: impossível dimensionar lote."""
    assert "get_symbol_info" in _registry()


def test_total_de_ferramentas_registradas():
    reg = _registry()
    assert len(reg) == _FERRAMENTAS_ESPERADAS, sorted(reg)


def test_ferramentas_antigas_nao_sumiram():
    antigas = {
        "get_account_info", "get_deals", "get_orders", "get_candles_latest",
        "get_symbol_price", "get_all_symbols", "get_symbols",
        "get_all_positions", "get_positions_by_symbol", "get_positions_by_id",
        "get_all_pending_orders", "get_pending_orders_by_symbol",
        "get_pending_orders_by_id", "place_market_order", "place_pending_order",
        "modify_position", "modify_pending_order", "close_position",
        "cancel_pending_order", "close_all_positions",
        "close_all_positions_by_symbol", "close_all_profitable_positions",
        "close_all_losing_positions", "cancel_all_pending_orders",
        "cancel_pending_orders_by_symbol",
    }
    assert antigas <= set(_registry())


def test_toda_funcao_de_ferramenta_do_modulo_esta_no_registry():
    """
    Guarda contra a classe do defeito #25: função declarada com ctx: Context e
    esquecida sem decorador. Por introspecção, não por texto.
    """
    registry = _registry()
    orfas = []
    for nome, obj in inspect.getmembers(servidor, inspect.isfunction):
        if obj.__module__ != servidor.__name__:
            continue
        params = inspect.signature(obj).parameters
        if "ctx" not in params:
            continue
        if nome not in registry:
            orfas.append(nome)
    assert not orfas, f"funções com ctx: Context fora do registry: {orfas}"


def test_get_candles_by_date_usa_optional_str():
    sig = inspect.signature(_impl("get_candles_by_date"))
    from typing import Optional

    assert sig.parameters["from_date"].annotation == Optional[str]
    assert sig.parameters["to_date"].annotation == Optional[str]


class _MercadoFalso:
    def __init__(self, info):
        self._info = info

    def get_symbol_info(self, symbol_name):
        return self._info


class _ClienteFalso:
    def __init__(self, info):
        self.market = _MercadoFalso(info)


def test_get_symbol_info_devolve_json_parseavel(monkeypatch):
    """str(info) obrigaria o modelo do outro lado a parsear repr no olho."""
    especificacao = {
        "name": "PETR4", "volume_min": 100.0, "volume_step": 100.0,
        "digits": 2, "point": 0.01, "trade_stops_level": 0,
        "trade_contract_size": 1.0, "currency_base": "BRL",
    }
    monkeypatch.setattr(
        servidor, "get_client", lambda ctx: _ClienteFalso(especificacao)
    )
    saida = _impl("get_symbol_info")(None, "PETR4")
    assert isinstance(saida, str)
    assert json.loads(saida)["volume_step"] == 100.0


def test_get_symbol_info_serializa_campo_exotico(monkeypatch):
    """default=str: introspecção pode trazer campo não serializável."""
    monkeypatch.setattr(
        servidor,
        "get_client",
        lambda ctx: _ClienteFalso({"name": "PETR4", "expiration": datetime(2026, 8, 8)}),
    )
    assert json.loads(_impl("get_symbol_info")(None, "PETR4"))["expiration"]


def test_get_symbol_info_ergue_erro_para_simbolo_inexistente(monkeypatch):
    monkeypatch.setattr(servidor, "get_client", lambda ctx: _ClienteFalso({}))
    with pytest.raises(ValueError, match="Market Watch"):
        _impl("get_symbol_info")(None, "NAOEXISTE")


# ============================================================== DEFEITO 4

def test_stub_e_distinguivel_do_mt5_real(mt5_stub):
    assert getattr(mt5_stub, "__investia_stub__", False) is not MT5_REAL_DISPONIVEL


def test_stub_falha_alto_em_atributo_nao_modelado(mt5_stub):
    if MT5_REAL_DISPONIVEL:
        pytest.skip("rodando contra o MetaTrader5 real")
    with pytest.raises(AttributeError, match="precisa_de_mt5_real"):
        mt5_stub.uma_funcao_que_nao_existe


def test_constantes_do_stub_em_faixas_disjuntas(mt5_stub):
    """
    Se ORDER_TYPE_BUY, TRADE_ACTION_DEAL e POSITION_TYPE_BUY valessem todos 0,
    um teste de mapeamento passaria por coincidência numérica.
    """
    if MT5_REAL_DISPONIVEL:
        pytest.skip("faixas artificiais valem só para o stub")
    valores = [
        mt5_stub.ORDER_TYPE_BUY, mt5_stub.TRADE_ACTION_DEAL,
        mt5_stub.ORDER_TIME_GTC, mt5_stub.ORDER_FILLING_FOK,
        mt5_stub.POSITION_TYPE_BUY, mt5_stub.DEAL_TYPE_BUY,
    ]
    assert len(set(valores)) == len(valores)


def test_timeframes_do_stub_usam_valores_reais_do_mql5(mt5_stub):
    assert mt5_stub.TIMEFRAME_H1 == 16385
    assert mt5_stub.TIMEFRAME_D1 == 16408
    assert mt5_stub.TIMEFRAME_W1 == 32769
    assert mt5_stub.TIMEFRAME_MN1 == 49153


def test_retcode_done_usa_o_valor_real(mt5_stub):
    assert mt5_stub.TRADE_RETCODE_DONE == 10009


@precisa_de_mt5_real
def test_marcador_de_terminal_real_existe_e_pula_honestamente():
    """Pular é honesto; rodar contra stub e reportar verde não é."""
    import MetaTrader5 as mt5

    assert not getattr(mt5, "__investia_stub__", False)
