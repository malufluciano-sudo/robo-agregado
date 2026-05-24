# ============================================================
#  ROBÔ AGREGADO — market_data.py
#  Busca OHLCV, calcula VWAP Ancorado, OBV, Volume Profile
# ============================================================

import requests
import pandas as pd
import numpy as np
from datetime import datetime, timedelta, timezone
import time
import streamlit as st
from utils.config import BINANCE_BASE, BINANCE_FUTURES_BASE


# ─── MAPEAMENTO DE TIMEFRAMES ────────────────────────────────
TF_MAP = {
    "1d": "1d", "1h": "1h", "15m": "15m", "5m": "5m",
    "4h": "4h", "30m": "30m",
}
TF_LIMIT = {
    "1d": 90, "4h": 120, "1h": 200, "30m": 200,
    "15m": 200, "5m": 200,
}


@st.cache_data(ttl=60)
def buscar_ohlcv(symbol: str, timeframe: str = "1h", limite: int = None) -> pd.DataFrame:
    """
    Busca candles OHLCV da Binance (spot ou futuros).
    Tenta futuros primeiro (USDT perp), fallback para spot.
    """
    tf = TF_MAP.get(timeframe, timeframe)
    lim = limite or TF_LIMIT.get(timeframe, 200)

    # Tenta futuros primeiro
    for base_url, label in [
        (BINANCE_FUTURES_BASE + "/fapi/v1/klines", "futures"),
        (BINANCE_BASE + "/api/v3/klines", "spot"),
    ]:
        try:
            resp = requests.get(base_url, params={
                "symbol": symbol.upper(),
                "interval": tf,
                "limit": lim,
            }, timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                if isinstance(data, list) and len(data) > 0:
                    df = pd.DataFrame(data, columns=[
                        "timestamp", "open", "high", "low", "close", "volume",
                        "close_time", "quote_vol", "trades", "taker_buy_base",
                        "taker_buy_quote", "ignore"
                    ])
                    df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
                    for col in ["open", "high", "low", "close", "volume"]:
                        df[col] = df[col].astype(float)
                    df = df[["timestamp", "open", "high", "low", "close", "volume"]].copy()
                    df.set_index("timestamp", inplace=True)
                    return df
        except Exception:
            continue
    return pd.DataFrame()


@st.cache_data(ttl=30)
def buscar_preco_atual(symbol: str) -> float:
    """Busca preço atual (24h ticker)."""
    # Tenta futuros
    for url in [
        f"{BINANCE_FUTURES_BASE}/fapi/v1/ticker/price?symbol={symbol.upper()}",
        f"{BINANCE_BASE}/api/v3/ticker/price?symbol={symbol.upper()}",
    ]:
        try:
            r = requests.get(url, timeout=5)
            if r.status_code == 200:
                return float(r.json()["price"])
        except Exception:
            continue
    return 0.0


def calcular_obv(df: pd.DataFrame) -> pd.Series:
    """
    Calcula OBV (On Balance Volume).
    Sinal: tendência crescente = acumulação, decrescente = distribuição.
    """
    if df.empty:
        return pd.Series(dtype=float)
    obv = [0]
    for i in range(1, len(df)):
        if df["close"].iloc[i] > df["close"].iloc[i - 1]:
            obv.append(obv[-1] + df["volume"].iloc[i])
        elif df["close"].iloc[i] < df["close"].iloc[i - 1]:
            obv.append(obv[-1] - df["volume"].iloc[i])
        else:
            obv.append(obv[-1])
    return pd.Series(obv, index=df.index, name="OBV")


def sinal_obv(df: pd.DataFrame, periodos: int = 20) -> dict:
    """
    Interpreta OBV segundo Wyckoff:
    - OBV em alta + preço em alta = acumulação confirmada
    - OBV em queda + preço em alta = distribuição (divergência bearish)
    - OBV em alta + preço em queda = Spring potencial (divergência bullish)
    """
    if df.empty or len(df) < periodos:
        return {"sinal": "NEUTRO", "descricao": "Dados insuficientes", "valor": 0}

    obv = calcular_obv(df)
    obv_recente = obv.iloc[-periodos:]
    preco_recente = df["close"].iloc[-periodos:]

    obv_slope = (obv_recente.iloc[-1] - obv_recente.iloc[0]) / (abs(obv_recente.iloc[0]) + 1)
    preco_slope = (preco_recente.iloc[-1] - preco_recente.iloc[0]) / preco_recente.iloc[0]

    if obv_slope > 0.01 and preco_slope > 0.01:
        return {"sinal": "ACUMULAÇÃO", "descricao": "OBV ↑ + Preço ↑ — Força compradora confirmada", "valor": obv.iloc[-1], "bias": "BULLISH"}
    elif obv_slope < -0.01 and preco_slope < -0.01:
        return {"sinal": "DISTRIBUIÇÃO", "descricao": "OBV ↓ + Preço ↓ — Pressão vendedora confirmada", "valor": obv.iloc[-1], "bias": "BEARISH"}
    elif obv_slope > 0.01 and preco_slope < -0.01:
        return {"sinal": "DIV. BULLISH", "descricao": "OBV ↑ mas Preço ↓ — Possível Spring/reversão", "valor": obv.iloc[-1], "bias": "BULLISH"}
    elif obv_slope < -0.01 and preco_slope > 0.01:
        return {"sinal": "DIV. BEARISH", "descricao": "OBV ↓ mas Preço ↑ — Possível Upthrust/exaustão", "valor": obv.iloc[-1], "bias": "BEARISH"}
    else:
        return {"sinal": "NEUTRO", "descricao": "OBV sem tendência clara — aguardar", "valor": obv.iloc[-1], "bias": "NEUTRO"}


def calcular_vwap_ancorado(df: pd.DataFrame, anchor_idx: int = 0) -> pd.Series:
    """
    VWAP Ancorado — ancora em anchor_idx (default: início do df = sessão/range).
    Fórmula: cumsum(típico × volume) / cumsum(volume)
    """
    if df.empty:
        return pd.Series(dtype=float)
    sub = df.iloc[anchor_idx:].copy()
    sub["tipico"] = (sub["high"] + sub["low"] + sub["close"]) / 3
    sub["tv"] = sub["tipico"] * sub["volume"]
    sub["cum_tv"] = sub["tv"].cumsum()
    sub["cum_vol"] = sub["volume"].cumsum()
    vwap = sub["cum_tv"] / sub["cum_vol"]
    return vwap.rename("VWAP")


def calcular_volume_profile(df: pd.DataFrame, bins: int = 30) -> dict:
    """
    Volume Profile Ancorado — distribuição de volume por faixa de preço.
    Retorna: POC, VAH, VAL, HVN, LVN e o histograma completo.
    """
    if df.empty or len(df) < 5:
        return {}

    preco_min = df["low"].min()
    preco_max = df["high"].max()
    faixas = np.linspace(preco_min, preco_max, bins + 1)
    vol_por_faixa = np.zeros(bins)

    for _, row in df.iterrows():
        for i in range(bins):
            overlap_low  = max(row["low"],  faixas[i])
            overlap_high = min(row["high"], faixas[i + 1])
            if overlap_high > overlap_low:
                frac = (overlap_high - overlap_low) / max(row["high"] - row["low"], 1e-10)
                vol_por_faixa[i] += row["volume"] * frac

    precos_centro = [(faixas[i] + faixas[i + 1]) / 2 for i in range(bins)]
    poc_idx  = int(np.argmax(vol_por_faixa))
    poc      = precos_centro[poc_idx]

    vol_total = vol_por_faixa.sum()
    va_threshold = vol_total * 0.70   # 70% do volume = Value Area

    # Value Area: expande ao redor do POC até cobrir 70%
    va_indices = [poc_idx]
    vol_va = vol_por_faixa[poc_idx]
    lo, hi = poc_idx, poc_idx
    while vol_va < va_threshold and (lo > 0 or hi < bins - 1):
        add_lo = vol_por_faixa[lo - 1] if lo > 0 else -1
        add_hi = vol_por_faixa[hi + 1] if hi < bins - 1 else -1
        if add_lo >= add_hi and lo > 0:
            lo -= 1; vol_va += vol_por_faixa[lo]; va_indices.append(lo)
        elif hi < bins - 1:
            hi += 1; vol_va += vol_por_faixa[hi]; va_indices.append(hi)
        else:
            break

    vah = precos_centro[max(va_indices)]
    val = precos_centro[min(va_indices)]

    # HVN e LVN
    vol_medio = np.mean(vol_por_faixa)
    hvn = [precos_centro[i] for i in range(bins) if vol_por_faixa[i] > vol_medio * 1.5]
    lvn = [precos_centro[i] for i in range(bins) if vol_por_faixa[i] < vol_medio * 0.5]

    return {
        "poc": poc,
        "vah": vah,
        "val": val,
        "hvn": hvn,
        "lvn": lvn,
        "faixas": precos_centro,
        "volumes": vol_por_faixa.tolist(),
        "poc_idx": poc_idx,
    }


def detectar_swing_points(df: pd.DataFrame, lookback: int = 5) -> dict:
    """
    Detecta HH, HL, LH, LL para estrutura SMC.
    Retorna listas de índices de topos e fundos.
    """
    if len(df) < lookback * 2 + 1:
        return {"topos": [], "fundos": []}

    topos, fundos = [], []
    for i in range(lookback, len(df) - lookback):
        janela_high = df["high"].iloc[i - lookback: i + lookback + 1]
        janela_low  = df["low"].iloc[i - lookback: i + lookback + 1]
        if df["high"].iloc[i] == janela_high.max():
            topos.append(i)
        if df["low"].iloc[i] == janela_low.min():
            fundos.append(i)
    return {"topos": topos, "fundos": fundos}


def identificar_estrutura_mercado(df: pd.DataFrame) -> dict:
    """
    Identifica CHoCH e BOS com base nos swing points.
    """
    if df.empty or len(df) < 20:
        return {"estrutura": "NEUTRO", "ultimo_evento": "—", "bias": "NEUTRO"}

    pts = detectar_swing_points(df)
    topos = pts["topos"]
    fundos = pts["fundos"]

    if len(topos) < 2 or len(fundos) < 2:
        return {"estrutura": "NEUTRO", "ultimo_evento": "Poucos swings", "bias": "NEUTRO"}

    # Compara últimos dois topos e dois fundos
    ultimo_topo1 = df["high"].iloc[topos[-1]]
    ultimo_topo2 = df["high"].iloc[topos[-2]]
    ultimo_fundo1 = df["low"].iloc[fundos[-1]]
    ultimo_fundo2 = df["low"].iloc[fundos[-2]]

    hh = ultimo_topo1 > ultimo_topo2
    hl = ultimo_fundo1 > ultimo_fundo2
    lh = ultimo_topo1 < ultimo_topo2
    ll = ultimo_fundo1 < ultimo_fundo2

    if hh and hl:
        return {"estrutura": "HH / HL", "ultimo_evento": "BOS Bullish", "bias": "BULLISH"}
    elif lh and ll:
        return {"estrutura": "LH / LL", "ultimo_evento": "BOS Bearish", "bias": "BEARISH"}
    elif hh and ll:
        return {"estrutura": "HH / LL", "ultimo_evento": "CHoCH — reversão possível", "bias": "NEUTRO"}
    elif lh and hl:
        return {"estrutura": "LH / HL", "ultimo_evento": "CHoCH — consolidação", "bias": "NEUTRO"}
    else:
        return {"estrutura": "NEUTRO", "ultimo_evento": "Range", "bias": "NEUTRO"}


def analisar_volume_contexto(df: pd.DataFrame, periodos: int = 20) -> dict:
    """
    Analisa contexto de volume:
    - Spike (> 2x média) = possível breakout ou reversão
    - Volume crescente em subida = acumulação
    - Volume crescente em queda = distribuição
    - Volume decrescente no topo = exaustão (sinal de inversão)
    """
    if df.empty or len(df) < periodos:
        return {"sinal": "NEUTRO", "descricao": "Dados insuficientes"}

    vol_medio = df["volume"].iloc[-periodos:].mean()
    vol_atual = df["volume"].iloc[-1]
    ultimo_close = df["close"].iloc[-1]
    penultimo_close = df["close"].iloc[-2]

    spike = vol_atual > vol_medio * 2.0
    tendencia_vol = df["volume"].iloc[-5:].mean() > df["volume"].iloc[-periodos:-5].mean()

    if spike:
        direcao = "alta" if ultimo_close > penultimo_close else "queda"
        return {
            "sinal": "SPIKE",
            "descricao": f"Volume {vol_atual/vol_medio:.1f}x acima da média — impulso de {direcao}",
            "spike": True,
            "ratio": vol_atual / vol_medio,
        }
    elif tendencia_vol:
        return {
            "sinal": "CRESCENTE",
            "descricao": "Volume em aumento — pressão acumulando",
            "spike": False,
            "ratio": vol_atual / vol_medio,
        }
    else:
        return {
            "sinal": "DECRESCENTE",
            "descricao": "Volume em queda — possível exaustão ou lateralização",
            "spike": False,
            "ratio": vol_atual / vol_medio,
        }
