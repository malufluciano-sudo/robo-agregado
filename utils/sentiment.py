# ============================================================
#  ROBÔ AGREGADO — sentiment.py
#  Funding Rate, OI, CVD, Long/Short Ratio
#  Fontes: Coinalyze API + Binance Futures
# ============================================================

import requests
import pandas as pd
import numpy as np
import streamlit as st
from utils.config import (
    COINALYZE_API_KEY, COINALYZE_BASE,
    BINANCE_FUTURES_BASE,
    FUNDING_BULLISH_MAX, FUNDING_BEARISH_MIN,
    LS_RATIO_BULLISH, LS_RATIO_BEARISH,
)


# ─── MAPEAMENTO SÍMBOLOS COINALYZE ───────────────────────────
# Coinalyze usa sufixo _PERP para perpetuais
def _coinalyze_symbol(symbol: str) -> str:
    s = symbol.upper().replace("USDT", "").replace(".P", "")
    return f"{s}USDT_PERP.A"  # aggregate across exchanges


@st.cache_data(ttl=60)
def buscar_funding_rate(symbol: str) -> dict:
    """
    Funding Rate (Open Interest Weighted) via Coinalyze.
    Fallback: Binance Futures (taxa única).
    """
    # Tenta Coinalyze primeiro
    try:
        sym = _coinalyze_symbol(symbol)
        url = f"{COINALYZE_BASE}/funding-rate-history"
        r = requests.get(url, params={
            "symbols": sym,
            "interval": "1hour",
            "limit": 1,
        }, headers={"api_key": COINALYZE_API_KEY}, timeout=8)
        if r.status_code == 200:
            data = r.json()
            if data and len(data) > 0 and "history" in data[0]:
                hist = data[0]["history"]
                if hist:
                    taxa = hist[-1].get("c", 0) or hist[-1].get("v", 0)
                    return _interpretar_funding(float(taxa), "Coinalyze OI-Weighted")
    except Exception:
        pass

    # Fallback: Binance
    try:
        r = requests.get(
            f"{BINANCE_FUTURES_BASE}/fapi/v1/fundingRate",
            params={"symbol": symbol.upper(), "limit": 1},
            timeout=8,
        )
        if r.status_code == 200:
            data = r.json()
            if data:
                taxa = float(data[-1].get("fundingRate", 0))
                return _interpretar_funding(taxa, "Binance")
    except Exception:
        pass

    return {"taxa": 0.0, "sinal": "NEUTRO", "descricao": "Sem dados de funding", "fonte": "—"}


def _interpretar_funding(taxa: float, fonte: str) -> dict:
    taxa_pct = taxa * 100
    if taxa_pct < FUNDING_BULLISH_MAX:
        sinal = "BULLISH"
        descricao = f"Funding {taxa_pct:.4f}% — vendedores pagando compradores (bullish)"
    elif taxa_pct > FUNDING_BEARISH_MIN:
        sinal = "EXTREMO BEARISH"
        descricao = f"Funding {taxa_pct:.4f}% — excesso de longs, risco de squeeze"
    elif taxa_pct > 0.02:
        sinal = "BEARISH"
        descricao = f"Funding {taxa_pct:.4f}% — leve pressão de longs"
    else:
        sinal = "NEUTRO"
        descricao = f"Funding {taxa_pct:.4f}% — equilíbrio"
    return {"taxa": taxa_pct, "sinal": sinal, "descricao": descricao, "fonte": fonte}


@st.cache_data(ttl=60)
def buscar_open_interest(symbol: str) -> dict:
    """
    Aggregated Open Interest via Coinalyze.
    Fallback: Binance Futures.
    """
    # Coinalyze
    try:
        sym = _coinalyze_symbol(symbol)
        url = f"{COINALYZE_BASE}/open-interest-history"
        r = requests.get(url, params={
            "symbols": sym,
            "interval": "1hour",
            "limit": 24,
        }, headers={"api_key": COINALYZE_API_KEY}, timeout=8)
        if r.status_code == 200:
            data = r.json()
            if data and "history" in data[0]:
                hist = data[0]["history"]
                if len(hist) >= 2:
                    oi_atual = float(hist[-1].get("c", 0) or hist[-1].get("v", 0))
                    oi_anterior = float(hist[0].get("c", 0) or hist[0].get("v", 0))
                    return _interpretar_oi(oi_atual, oi_anterior, "Coinalyze Aggregated")
    except Exception:
        pass

    # Fallback Binance
    try:
        r = requests.get(
            f"{BINANCE_FUTURES_BASE}/fapi/v1/openInterest",
            params={"symbol": symbol.upper()},
            timeout=8,
        )
        if r.status_code == 200:
            oi = float(r.json().get("openInterest", 0))
            return _interpretar_oi(oi, oi, "Binance")
    except Exception:
        pass

    return {"oi_atual": 0, "variacao_pct": 0, "sinal": "NEUTRO", "descricao": "Sem dados de OI", "fonte": "—"}


def _interpretar_oi(oi_atual: float, oi_anterior: float, fonte: str) -> dict:
    variacao = ((oi_atual - oi_anterior) / max(oi_anterior, 1)) * 100
    if variacao > 5:
        sinal = "CRESCENTE"
        descricao = f"OI +{variacao:.1f}% em 24h — novas posições entrando (confirma movimento)"
    elif variacao < -5:
        sinal = "CAINDO"
        descricao = f"OI {variacao:.1f}% em 24h — fechamento de posições (exaustão ou squeeze)"
    else:
        sinal = "ESTÁVEL"
        descricao = f"OI {variacao:+.1f}% em 24h — mercado lateral/consolidando"
    return {
        "oi_atual": oi_atual,
        "variacao_pct": variacao,
        "sinal": sinal,
        "descricao": descricao,
        "fonte": fonte,
    }


@st.cache_data(ttl=60)
def buscar_long_short_ratio(symbol: str) -> dict:
    """
    Long/Short Ratio (Accounts) via Binance Futures.
    Complemento: Coinalyze se disponível.
    """
    try:
        r = requests.get(
            f"{BINANCE_FUTURES_BASE}/futures/data/globalLongShortAccountRatio",
            params={"symbol": symbol.upper(), "period": "1h", "limit": 1},
            timeout=8,
        )
        if r.status_code == 200:
            data = r.json()
            if data:
                ratio = float(data[-1].get("longShortRatio", 1.0))
                long_pct = float(data[-1].get("longAccount", 0.5)) * 100
                short_pct = float(data[-1].get("shortAccount", 0.5)) * 100
                return _interpretar_ls(ratio, long_pct, short_pct)
    except Exception:
        pass

    return {
        "ratio": 1.0, "long_pct": 50.0, "short_pct": 50.0,
        "sinal": "NEUTRO", "descricao": "Sem dados L/S", "fonte": "—"
    }


def _interpretar_ls(ratio: float, long_pct: float, short_pct: float) -> dict:
    if ratio > LS_RATIO_BULLISH:
        sinal = "COMPRADO DEMAIS"
        descricao = f"L/S {ratio:.2f} — {long_pct:.1f}% long. Risco de short squeeze reverso"
        bias = "BEARISH"   # contrarian: excesso de longs = topo próximo
    elif ratio < LS_RATIO_BEARISH:
        sinal = "VENDIDO DEMAIS"
        descricao = f"L/S {ratio:.2f} — {short_pct:.1f}% short. Potencial short squeeze bullish"
        bias = "BULLISH"   # contrarian: excesso de shorts = fundo próximo
    else:
        sinal = "EQUILIBRADO"
        descricao = f"L/S {ratio:.2f} — {long_pct:.1f}% long / {short_pct:.1f}% short"
        bias = "NEUTRO"
    return {
        "ratio": ratio,
        "long_pct": long_pct,
        "short_pct": short_pct,
        "sinal": sinal,
        "descricao": descricao,
        "bias": bias,
        "fonte": "Binance",
    }


@st.cache_data(ttl=120)
def buscar_cvd(symbol: str) -> dict:
    """
    Aggregated Spot Cumulative Volume Delta (CVD).
    Aproximação via Binance: taker_buy_base vs total volume nos candles.
    CVD = cumsum(buy_volume - sell_volume)
    """
    try:
        r = requests.get(
            f"{BINANCE_FUTURES_BASE}/fapi/v1/klines",
            params={"symbol": symbol.upper(), "interval": "1h", "limit": 48},
            timeout=10,
        )
        if r.status_code == 200:
            data = r.json()
            cvd_vals = []
            for candle in data:
                vol_total = float(candle[5])
                buy_vol   = float(candle[9])   # taker buy base volume
                sell_vol  = vol_total - buy_vol
                cvd_vals.append(buy_vol - sell_vol)

            cvd_cum = pd.Series(cvd_vals).cumsum()
            cvd_atual  = cvd_cum.iloc[-1]
            cvd_inicio = cvd_cum.iloc[0]
            tendencia  = cvd_cum.iloc[-12:].mean() - cvd_cum.iloc[-24:-12].mean()

            if tendencia > 0 and cvd_atual > 0:
                sinal = "PRESSÃO COMPRADORA"
                descricao = "CVD acumulado positivo — smart money comprando"
                bias = "BULLISH"
            elif tendencia < 0 and cvd_atual < 0:
                sinal = "PRESSÃO VENDEDORA"
                descricao = "CVD acumulado negativo — smart money vendendo"
                bias = "BEARISH"
            elif tendencia > 0 and cvd_atual < 0:
                sinal = "RECUPERAÇÃO CVD"
                descricao = "CVD virando para cima — possível reversão bullish"
                bias = "BULLISH"
            else:
                sinal = "NEUTRO"
                descricao = "CVD sem tendência clara"
                bias = "NEUTRO"

            return {
                "cvd_atual": cvd_atual,
                "tendencia": tendencia,
                "sinal": sinal,
                "descricao": descricao,
                "bias": bias,
                "historico": cvd_cum.tolist()[-24:],
                "fonte": "Binance Futures Taker",
            }
    except Exception:
        pass

    return {
        "cvd_atual": 0, "tendencia": 0,
        "sinal": "NEUTRO", "descricao": "Sem dados CVD", "bias": "NEUTRO",
        "historico": [], "fonte": "—"
    }


def calcular_sentimento_geral(funding: dict, oi: dict, ls: dict, cvd: dict) -> dict:
    """
    Score de sentimento agregado (0-100):
    - 0-30: extremamente bearish
    - 31-50: bearish moderado
    - 51-70: neutro / indefinido
    - 71-85: bullish moderado
    - 86-100: extremamente bullish
    """
    score = 50  # começa neutro

    # Funding (peso 30%)
    f = funding.get("taxa", 0)
    if f < -0.01:   score += 15
    elif f < 0:     score += 8
    elif f > 0.05:  score -= 15
    elif f > 0.02:  score -= 8

    # OI (peso 20%)
    oi_sinal = oi.get("sinal", "ESTÁVEL")
    if oi_sinal == "CRESCENTE":   score += 5
    elif oi_sinal == "CAINDO":    score -= 5

    # L/S Ratio contrarian (peso 25%)
    ls_bias = ls.get("bias", "NEUTRO")
    if ls_bias == "BULLISH":   score += 12
    elif ls_bias == "BEARISH": score -= 12

    # CVD (peso 25%)
    cvd_bias = cvd.get("bias", "NEUTRO")
    if cvd_bias == "BULLISH":   score += 12
    elif cvd_bias == "BEARISH": score -= 12

    score = max(0, min(100, score))

    if score >= 75:
        label = "BULLISH"; cor = "#00d4aa"
    elif score >= 55:
        label = "LEVEMENTE BULLISH"; cor = "#7fdbba"
    elif score >= 45:
        label = "NEUTRO"; cor = "#888888"
    elif score >= 25:
        label = "LEVEMENTE BEARISH"; cor = "#ff8888"
    else:
        label = "BEARISH"; cor = "#ff4444"

    return {"score": score, "label": label, "cor": cor}


# ─── HISTÓRICOS PARA GRÁFICO ESTILO COINGLASS ────────────────

@st.cache_data(ttl=120)
def buscar_funding_historico(symbol: str, limit: int = 72) -> list:
    """Retorna lista de {t, v} com histórico de funding rate."""
    try:
        r = requests.get(
            f"{BINANCE_FUTURES_BASE}/fapi/v1/fundingRate",
            params={"symbol": symbol.upper(), "limit": limit},
            timeout=10,
        )
        if r.status_code == 200:
            return [{"t": int(d["fundingTime"]), "v": float(d["fundingRate"]) * 100}
                    for d in r.json()]
    except Exception:
        pass
    return []


@st.cache_data(ttl=120)
def buscar_oi_historico(symbol: str, limit: int = 72) -> list:
    """Retorna lista de {t, v} com histórico de Open Interest."""
    try:
        r = requests.get(
            f"{BINANCE_FUTURES_BASE}/futures/data/openInterestHist",
            params={"symbol": symbol.upper(), "period": "1h", "limit": limit},
            timeout=10,
        )
        if r.status_code == 200:
            return [{"t": int(d["timestamp"]), "v": float(d["sumOpenInterest"])}
                    for d in r.json()]
    except Exception:
        pass
    return []


@st.cache_data(ttl=120)
def buscar_ls_historico(symbol: str, limit: int = 72) -> list:
    """Retorna lista de {t, long, short, ratio} com histórico L/S."""
    try:
        r = requests.get(
            f"{BINANCE_FUTURES_BASE}/futures/data/globalLongShortAccountRatio",
            params={"symbol": symbol.upper(), "period": "1h", "limit": limit},
            timeout=10,
        )
        if r.status_code == 200:
            return [{"t": int(d["timestamp"]),
                     "long":  float(d.get("longAccount",  0.5)) * 100,
                     "short": float(d.get("shortAccount", 0.5)) * 100,
                     "ratio": float(d.get("longShortRatio", 1.0))}
                    for d in r.json()]
    except Exception:
        pass
    return []


@st.cache_data(ttl=120)
def buscar_liquidacoes_historico(symbol: str, limit: int = 72) -> list:
    """Retorna lista de {t, long_liq, short_liq} de liquidações agrupadas por hora."""
    # Binance não expõe histórico de liquidações via REST público —
    # aproximamos com o taker volume delta (diferença brusca = liquidações)
    try:
        r = requests.get(
            f"{BINANCE_FUTURES_BASE}/fapi/v1/klines",
            params={"symbol": symbol.upper(), "interval": "1h", "limit": limit},
            timeout=10,
        )
        if r.status_code == 200:
            result = []
            for k in r.json():
                t       = int(k[0])
                vol     = float(k[5])
                buy_vol = float(k[9])
                sell_vol = vol - buy_vol
                # Spike de sell_vol relativo = aproximação de long liquidation
                result.append({"t": t, "buy": buy_vol, "sell": sell_vol})
            return result
    except Exception:
        pass
    return []
