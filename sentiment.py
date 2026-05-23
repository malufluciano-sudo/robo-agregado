# ============================================================
#  ROBÔ AGREGADO — config.py
#  Configurações centrais da Metodologia Agregada de Luciano
# ============================================================

import os

# ─── COINALYZE ───────────────────────────────────────────────
# API key: lê do Streamlit Secrets (cloud) ou .env (local)
try:
    import streamlit as st
    COINALYZE_API_KEY = st.secrets.get("COINALYZE_KEY", os.getenv("COINALYZE_KEY", "376762b9-d136-4457-a192-9cd0a7865d43"))
except Exception:
    COINALYZE_API_KEY = os.getenv("COINALYZE_KEY", "376762b9-d136-4457-a192-9cd0a7865d43")
COINALYZE_BASE    = "https://api.coinalyze.net/v1"

# ─── BINANCE (dados públicos, sem autenticação) ───────────────
BINANCE_BASE = "https://api.binance.com"
BINANCE_FUTURES_BASE = "https://fapi.binance.com"

# ─── WATCHLIST PADRÃO ─────────────────────────────────────────
WATCHLIST_DEFAULT = [
    "BTCUSDT", "ETHUSDT", "SOLUSDT", "HYPEUSDT",
    "LINKUSDT", "BNBUSDT", "XRPUSDT",
]

# ─── GESTÃO DE RISCO ─────────────────────────────────────────
MARGEM_PADRAO_USD   = 200.0
ALAVANCAGEM_MAX     = 20
ALAVANCAGEM_35PCT   = 7     # 35% da alavancagem máxima
RR_MINIMO           = 1.0
CONFLUENCIAS_MIN    = 3

# Targets e realizações (Metodologia Agregada)
A1_RR   = 1.0;  A1_REAL = 0.25   # realizar 25% no A1
A2_RR   = 2.0;  A2_REAL = 0.50   # realizar 50% no A2
A3_RR   = 3.0;  A3_REAL = 0.80   # realizar 80% no A3
TS_REAL = 0.10                    # 10% restante no trailing stop

# Trailing stop por ativo
TRAILING_BTC  = 0.022   # 2.2%
TRAILING_XAGUSD = 0.025
TRAILING_DEFAULT = 0.030

# ─── TIMEFRAMES TOP-DOWN ─────────────────────────────────────
TF_TOPDOWN = ["1d", "1h", "15m", "5m"]
TF_LABELS  = {"1d": "1D", "1h": "1H", "15m": "15M", "5m": "5M"}

# ─── SENTIMENTO — THRESHOLDS ─────────────────────────────────
FUNDING_BULLISH_MAX  = -0.01   # funding negativo = bullish
FUNDING_BEARISH_MIN  =  0.05   # funding > 0.05% = extremo bearish
LS_RATIO_BULLISH     =  1.5    # long/short > 1.5 = muito comprado
LS_RATIO_BEARISH     =  0.7    # long/short < 0.7 = muito vendido

# ─── OBV / VOLUME ─────────────────────────────────────────────
OBV_TREND_PERIODOS = 20  # média de OBV para tendência
VOLUME_SPIKE_MULT  = 2.0 # volume > 2x média = spike

# ─── CORES (tema dark trading) ────────────────────────────────
COR_BULLISH  = "#00d4aa"
COR_BEARISH  = "#ff4444"
COR_NEUTRO   = "#888888"
COR_ALERTA   = "#ffaa00"
COR_BG       = "#0e1117"
COR_CARD     = "#1a1f2e"
COR_BORDER   = "#2d3748"
COR_TEXTO    = "#e2e8f0"
COR_SUBTEXTO = "#94a3b8"
