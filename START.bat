# ============================================================
#  ROBÔ AGREGADO — app.py  v1.4
#  Gráfico estilo TradingView + Sentimento estilo Coinglass
#  Trader: Luciano | BRT (UTC-3)
# ============================================================

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime, timezone, timedelta

from utils.config import *
from utils.market_data import (
    buscar_ohlcv, calcular_vwap_ancorado,
    calcular_volume_profile, calcular_obv, buscar_preco_atual,
)
from utils.sentiment import (
    buscar_funding_rate, buscar_open_interest,
    buscar_long_short_ratio, buscar_cvd,
    calcular_sentimento_geral,
    buscar_funding_historico, buscar_oi_historico,
    buscar_ls_historico, buscar_liquidacoes_historico,
)
from utils.analise_engine import analisar_ativo_completo

# ─── PÁGINA ──────────────────────────────────────────────────
st.set_page_config(
    page_title="Robô Agregado | Luciano",
    page_icon="🦈", layout="wide",
    initial_sidebar_state="expanded",
)

# ─── CSS ─────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;600;700&family=Inter:wght@300;400;500;600&display=swap');
html,body,[class*="css"]{font-family:'Inter',sans-serif;background:#0e1117;color:#e2e8f0;}
.stApp{background:#0e1117;}
[data-testid="stSidebar"]{background:#1a1f2e !important;border-right:1px solid #2d3748;}
.metric-card{background:#1a1f2e;border:1px solid #2d3748;border-radius:10px;padding:14px 18px;margin-bottom:10px;}
.metric-card-bullish{border-left:3px solid #00d4aa;}
.metric-card-bearish{border-left:3px solid #ff4444;}
.metric-card-neutro{border-left:3px solid #888;}
.metric-card-alerta{border-left:3px solid #ffaa00;}
.badge{display:inline-block;padding:2px 9px;border-radius:20px;font-size:10px;font-weight:600;
       letter-spacing:.5px;text-transform:uppercase;font-family:'JetBrains Mono',monospace;}
.badge-bullish{background:#00d4aa18;color:#00d4aa;border:1px solid #00d4aa44;}
.badge-bearish{background:#ff444418;color:#ff4444;border:1px solid #ff444444;}
.badge-neutro{background:#88888818;color:#888;border:1px solid #88888844;}
.badge-alerta{background:#ffaa0018;color:#ffaa00;border:1px solid #ffaa0044;}
.big-number{font-family:'JetBrains Mono',monospace;font-size:26px;font-weight:700;line-height:1;}
.trade-card{background:#1a1f2e;border:1px solid #2d3748;border-radius:12px;padding:18px;
            font-family:'JetBrains Mono',monospace;font-size:13px;}
.conf-item{display:flex;align-items:center;gap:10px;padding:7px 0;
           border-bottom:1px solid #1e2530;font-size:13px;}
.stButton>button{background:#2d3748;border:1px solid #4a5568;color:#e2e8f0;
                 border-radius:7px;font-weight:500;transition:all .15s;}
.stButton>button:hover{background:#3d4a5f;border-color:#00d4aa;}
div[data-testid="stMetricValue"]{font-family:'JetBrains Mono',monospace;}
/* TF buttons strip */
.tf-strip div[data-testid="stHorizontalBlock"] .stButton>button{
    padding:3px 0;font-size:11px;font-family:'JetBrains Mono',monospace;font-weight:700;border-radius:5px;}
</style>
""", unsafe_allow_html=True)

# ─── HELPERS ─────────────────────────────────────────────────
def brt():
    return datetime.now(timezone(timedelta(hours=-3))).strftime("%d/%m/%Y %H:%M BRT")

def cor_bias(b):
    return {"BULLISH": COR_BULLISH, "BEARISH": COR_BEARISH}.get(b, COR_NEUTRO)

def badge(txt, tipo="neutro"):
    return f'<span class="badge badge-{tipo}">{txt}</span>'

def ts_to_dt(ts_ms):
    return datetime.utcfromtimestamp(ts_ms / 1000)


# ─── ESTADO ──────────────────────────────────────────────────
for k, v in [("tf_ativo","1h"),("analise_resultado",None),("symbol_analisado","")]:
    if k not in st.session_state: st.session_state[k] = v


# ─── SIDEBAR ─────────────────────────────────────────────────
with st.sidebar:
    st.markdown("""
    <div style="text-align:center;padding:14px 0 10px">
      <div style="font-size:34px">🦈</div>
      <div style="font-family:'JetBrains Mono';font-size:17px;font-weight:700;color:#00d4aa">ROBÔ AGREGADO</div>
      <div style="font-size:10px;color:#94a3b8;margin-top:3px">Metodologia Agregada — Luciano</div>
    </div><hr style="border-color:#2d3748;margin:6px 0 12px">
    """, unsafe_allow_html=True)

    ativo_input = st.text_input("🎯 ATIVO", value="BTCUSDT", placeholder="Ex: BTCUSDT, XAGUSD")
    symbol = ativo_input.upper().strip()
    analisar = st.button("⚡ ANALISAR AGORA", use_container_width=True)

    st.markdown("<hr style='border-color:#2d3748;margin:10px 0'>", unsafe_allow_html=True)
    st.markdown("**📋 WATCHLIST**")
    for w in ["BTCUSDT","ETHUSDT","SOLUSDT","HYPEUSDT","XAGUSD","BNBUSDT"]:
        if st.button(w, key=f"wl_{w}", use_container_width=True):
            symbol = w; analisar = True

    st.markdown("<hr style='border-color:#2d3748;margin:10px 0'>", unsafe_allow_html=True)
    margem_cfg   = st.number_input("💰 Margem (USD)", value=200, min_value=50, max_value=10000, step=50)
    auto_refresh = st.toggle("🔄 Auto-refresh 30s", value=False)
    if auto_refresh:
        st.markdown('<script>setTimeout(()=>window.location.reload(),30000)</script>', unsafe_allow_html=True)
    st.caption(f"🕐 {brt()}")


# ─── HEADER ──────────────────────────────────────────────────
st.markdown(f"""
<div style="background:linear-gradient(135deg,#1a1f2e,#0e1117);border:1px solid #2d3748;
     border-radius:12px;padding:18px 24px;margin-bottom:16px;display:flex;align-items:center;gap:14px;">
  <div style="font-size:32px">🦈</div>
  <div>
    <div style="font-family:'JetBrains Mono';font-size:19px;font-weight:700;color:#00d4aa">ROBÔ AGREGADO v1.4</div>
    <div style="color:#94a3b8;font-size:11px;margin-top:2px">SMC · Wyckoff · Tuk Tuk · VP Ancorado · VWAP Ancorado · OBV · Sentimento Coinglass</div>
  </div>
  <div style="margin-left:auto;font-family:'JetBrains Mono';font-size:10px;color:#4a5568">{brt()}</div>
</div>
""", unsafe_allow_html=True)


# ─── ANÁLISE ─────────────────────────────────────────────────
if analisar or (st.session_state["symbol_analisado"] != symbol and symbol):
    with st.spinner(f"⚡ Analisando {symbol} — Metodologia Agregada..."):
        res = analisar_ativo_completo(symbol)
        res["margem_cfg"] = margem_cfg
        st.session_state["analise_resultado"] = res
        st.session_state["symbol_analisado"]  = symbol

res = st.session_state.get("analise_resultado")
if res is None:
    st.markdown("""<div style="text-align:center;padding:80px;color:#4a5568">
    <div style="font-size:48px;margin-bottom:16px">📊</div>
    <div style="font-size:18px;color:#94a3b8">Selecione um ativo e clique em ANALISAR</div>
    </div>""", unsafe_allow_html=True)
    st.stop()
if res.get("erro"): st.error(f"⚠️ {res['erro']}"); st.stop()

# Dados
preco       = res["preco_atual"]
bias        = res["bias"]
score       = res["score"]
pb          = res.get("pontos_bull",0)
pbe         = res.get("pontos_bear",0)
conf        = res.get("confluencias",0)
dados       = res.get("dados",{})
trade       = res.get("trade")
detalhes    = res.get("detalhes",[])
sym         = res["symbol"]
cor_p       = cor_bias(bias)
tipo_b      = "bullish" if bias=="BULLISH" else ("bearish" if bias=="BEARISH" else "neutro")


# ════════════════════════════════════════════════════════════
#  MÉTRICAS RESUMO
# ════════════════════════════════════════════════════════════
c1,c2,c3,c4,c5 = st.columns([1,1.5,1,1,1])
sc_cor = COR_BULLISH if score>=66 else (COR_BEARISH if score<=33 else COR_ALERTA)

c1.markdown(f"""<div class="metric-card" style="text-align:center;border-left:3px solid {sc_cor}">
<div style="font-size:9px;color:#94a3b8;text-transform:uppercase;letter-spacing:1px;margin-bottom:6px">SCORE</div>
<div class="big-number" style="color:{sc_cor}">{score}</div>
<div style="font-size:9px;color:#555;margin-top:2px">/100</div>
<div style="margin-top:6px">{badge(bias,tipo_b)}</div></div>""", unsafe_allow_html=True)

c2.markdown(f"""<div class="metric-card metric-card-{tipo_b}">
<div style="font-size:9px;color:#94a3b8;text-transform:uppercase;letter-spacing:1px;margin-bottom:6px">{sym}</div>
<div class="big-number" style="color:{cor_p}">${preco:,.4f}</div>
<div style="font-size:10px;color:#94a3b8;margin-top:4px">Preço atual</div></div>""", unsafe_allow_html=True)

est1d = dados.get("estrutura",{}).get("1d",{})
c3.markdown(f"""<div class="metric-card">
<div style="font-size:9px;color:#94a3b8;text-transform:uppercase;letter-spacing:1px;margin-bottom:6px">CONFLUÊNCIAS</div>
<div style="display:flex;gap:6px;align-items:baseline">
<span class="big-number" style="color:{COR_BULLISH}">{pb}</span>
<span style="color:#555">vs</span>
<span class="big-number" style="color:{COR_BEARISH}">{pbe}</span></div>
<div style="font-size:10px;color:#94a3b8;margin-top:4px">{est1d.get('estrutura','—')}</div></div>""", unsafe_allow_html=True)

vd = dados.get("vwap",{}); vp_ = vd.get("pct",0)
vt = "bullish" if vp_>0 else ("bearish" if vp_<0 else "neutro")
c4.markdown(f"""<div class="metric-card metric-card-{vt}">
<div style="font-size:9px;color:#94a3b8;text-transform:uppercase;letter-spacing:1px;margin-bottom:6px">VWAP ANCORADO</div>
<div class="big-number" style="font-size:20px;color:{cor_bias(vd.get('bias','NEUTRO'))}">{vp_:+.2f}%</div>
<div style="font-size:10px;color:#94a3b8;margin-top:4px">${vd.get('valor',0):,.2f}</div>
<div style="margin-top:4px">{badge(vd.get('bias','NEUTRO'),vt)}</div></div>""", unsafe_allow_html=True)

sg = dados.get("sentimento",{}).get("geral",{})
ss = sg.get("score",50); sc2=sg.get("cor","#888"); sl=sg.get("label","NEUTRO")
st2 = "bullish" if ss>=60 else ("bearish" if ss<=40 else "neutro")
c5.markdown(f"""<div class="metric-card metric-card-{st2}">
<div style="font-size:9px;color:#94a3b8;text-transform:uppercase;letter-spacing:1px;margin-bottom:6px">SENTIMENTO</div>
<div class="big-number" style="color:{sc2}">{ss}</div>
<div style="font-size:9px;color:#555;margin-top:2px">/100</div>
<div style="margin-top:6px">{badge(sl,st2)}</div></div>""", unsafe_allow_html=True)


# ════════════════════════════════════════════════════════════
#  FUNÇÃO: CORES DE CANDLE POR VOLUME (Pine Script rule)
# ════════════════════════════════════════════════════════════
def colorir_candles_por_volume(df: pd.DataFrame) -> list:
    """
    Regra do indicador NoobSharks (Luciano):
    Volume > 2.0x média  = SPIKE
    Volume > 1.5x média  = ALTO
    Volume > 1.0x média  = MÉDIO
    Volume <= 1.0x média = BAIXO

    Candle de alta:
      SPIKE → amarelo   (#f5c518)
      ALTO  → laranja   (#ff8c00)
      MÉDIO → verde     (#00d4aa)
      BAIXO → azul claro (#4a9eff)  ← fraco / não entrar

    Candle de baixa:
      SPIKE → roxo      (#9b59b6)
      ALTO  → vermelho  (#ff2244)
      MÉDIO → laranja   (#ff6600)
      BAIXO → branco/cinza (#aaaaaa) ← fraco / não entrar
    """
    vol_media = df["volume"].rolling(20, min_periods=1).mean()
    cores = []
    for i in range(len(df)):
        v    = df["volume"].iloc[i]
        vm   = vol_media.iloc[i]
        alta = df["close"].iloc[i] >= df["open"].iloc[i]
        ratio = v / vm if vm > 0 else 1.0
        if alta:
            if ratio >= 2.0:   cores.append("#f5c518")   # spike alta = amarelo
            elif ratio >= 1.5: cores.append("#ff8c00")   # alto alta  = laranja
            elif ratio >= 1.0: cores.append("#00d4aa")   # médio alta = verde
            else:              cores.append("#4a9eff")   # baixo alta = azul (fraco)
        else:
            if ratio >= 2.0:   cores.append("#9b59b6")   # spike baixa = roxo
            elif ratio >= 1.5: cores.append("#ff2244")   # alto baixa  = vermelho
            elif ratio >= 1.0: cores.append("#ff6600")   # médio baixa = laranja
            else:              cores.append("#aaaaaa")   # baixo baixa = cinza (fraco)
    return cores


# ════════════════════════════════════════════════════════════
#  FUNÇÃO: ÂNCORA AUTOMÁTICA (Metodologia Agregada)
# ════════════════════════════════════════════════════════════
def identificar_ancora_metodologia(df: pd.DataFrame, wyckoff: dict) -> int:
    """
    Identifica o ponto de âncora para VWAP e Volume Profile
    baseado na Metodologia Agregada:

    1. Se há range lateral identificado → ancora no início do range
    2. Se há Spring/Upthrust → ancora no candle de maior volume do range
    3. Fallback → candle de maior volume nos últimos 50 candles
    """
    if df.empty or len(df) < 10:
        return 0

    range_low  = wyckoff.get("range_low",  0)
    range_high = wyckoff.get("range_high", 0)

    # Se temos range definido, encontrar início do range
    if range_low > 0 and range_high > 0:
        range_amplitude = range_high - range_low
        # Varrer de trás para frente para achar onde o range começou
        for i in range(len(df)-1, max(0, len(df)-80), -1):
            preco_c = df["close"].iloc[i]
            # Fora do range = antes do range começar
            if preco_c < range_low - range_amplitude*0.05 or \
               preco_c > range_high + range_amplitude*0.05:
                ancora = min(i + 1, len(df)-1)
                # Refinar: dentro do range, candle de maior volume
                df_range = df.iloc[ancora:]
                if not df_range.empty:
                    ancora_vol = df_range["volume"].idxmax()
                    ancora_pos = df.index.get_loc(ancora_vol)
                    return ancora_pos
                return ancora
        # Chegou ao início sem sair do range → usa início dos dados
        ancora_vol = df.iloc[-50:]["volume"].idxmax()
        return df.index.get_loc(ancora_vol)
    else:
        # Sem range identificado → candle de maior volume nos últimos 50
        sub = df.iloc[-50:]
        ancora_vol = sub["volume"].idxmax()
        return df.index.get_loc(ancora_vol)


# ════════════════════════════════════════════════════════════
#  FUNÇÃO: GRÁFICO PRINCIPAL (estilo TradingView)
# ════════════════════════════════════════════════════════════
def build_chart_tv(symbol, timeframe, analise, height=600):
    df = buscar_ohlcv(symbol, timeframe, 150)
    if df.empty:
        fig = go.Figure()
        fig.update_layout(paper_bgcolor="#0e1117", plot_bgcolor="#0e1117", height=height)
        return fig

    dados_a  = analise.get("dados", {})
    wyck_1h  = dados_a.get("wyckoff", {}).get("1h", {})

    # ── Âncora automática (Metodologia Agregada) ─────────────
    ancora_idx = identificar_ancora_metodologia(df, wyck_1h)
    ancora_ts  = df.index[ancora_idx]

    # ── VWAP Ancorado no ponto metodológico ──────────────────
    vwap_serie = calcular_vwap_ancorado(df, ancora_idx)

    # ── Volume Profile Ancorado no range ─────────────────────
    df_range = df.iloc[ancora_idx:]
    vp = calcular_volume_profile(df_range, bins=35)

    # ── Cores dos candles por volume (regra Pine Script) ─────
    cores_candle = colorir_candles_por_volume(df)

    # ── Subplots: candle (grande) + volume colorido ───────────
    fig = make_subplots(
        rows=2, cols=1, shared_xaxes=True,
        row_heights=[0.80, 0.20],
        vertical_spacing=0.01,
    )

    # ── Candlestick com cores por volume ─────────────────────
    # Plotar grupo por grupo de cor para manter cores individuais
    for i in range(len(df)):
        cor = cores_candle[i]
        row = df.iloc[i]
        fig.add_trace(go.Candlestick(
            x=[df.index[i]],
            open=[row["open"]], high=[row["high"]],
            low=[row["low"]],   close=[row["close"]],
            increasing_line_color=cor, decreasing_line_color=cor,
            increasing_fillcolor=cor,  decreasing_fillcolor=cor,
            showlegend=False, name="",
            whiskerwidth=0.4,
        ), row=1, col=1)

    # ── VWAP Ancorado ────────────────────────────────────────
    if not vwap_serie.empty:
        fig.add_trace(go.Scatter(
            x=vwap_serie.index, y=vwap_serie.values,
            mode="lines", name=f"VWAP (âncora: {ancora_ts.strftime('%d/%m %H:%M') if hasattr(ancora_ts,'strftime') else ''})",
            line=dict(color="#c084fc", width=2),
            hovertemplate="VWAP: $%{y:,.4f}<extra></extra>",
        ), row=1, col=1)

        # Marker do ponto de âncora
        fig.add_trace(go.Scatter(
            x=[ancora_ts], y=[df["low"].iloc[ancora_idx] * 0.998],
            mode="markers+text",
            marker=dict(symbol="triangle-up", color="#c084fc", size=10),
            text=["⚓"], textposition="bottom center",
            textfont=dict(size=10, color="#c084fc"),
            name="Âncora VWAP", showlegend=False,
            hovertemplate=f"Âncora VWAP<extra></extra>",
        ), row=1, col=1)

    # ── Volume Profile — barras horizontais sobre o gráfico ──
    if vp and "faixas" in vp and "volumes" in vp:
        faixas  = vp["faixas"]
        volumes = vp["volumes"]
        vol_max = max(volumes) if max(volumes) > 0 else 1

        # Largura do VP = 15% da janela temporal (direita do gráfico)
        try:
            dt_candle  = df.index[-1] - df.index[-2]
            x_vp_start = df.index[-1]
            x_vp_end   = df.index[-1] + dt_candle * 18  # 18 candles de largura máx
        except Exception:
            x_vp_start = x_vp_end = df.index[-1]

        altura_faixa = (max(faixas) - min(faixas)) / max(len(faixas)-1, 1) * 0.85

        for i, (f, v) in enumerate(zip(faixas, volumes)):
            frac = v / vol_max
            x_end = x_vp_start + (x_vp_end - x_vp_start) * frac

            is_poc = (i == vp.get("poc_idx", -1))
            in_va  = vp.get("val", 0) <= f <= vp.get("vah", 0)

            if is_poc:
                cor_vp = "#ffaa00"; opac = 0.95
            elif in_va:
                cor_vp = "rgba(0,180,100,0.55)"; opac = 1
            else:
                cor_vp = "rgba(60,100,160,0.35)"; opac = 1

            fig.add_shape(
                type="rect",
                x0=x_vp_start, x1=x_end,
                y0=f - altura_faixa/2, y1=f + altura_faixa/2,
                fillcolor=cor_vp if is_poc else cor_vp,
                line=dict(width=0),
                opacity=opac,
                row=1, col=1,
            )

        # Linhas POC / VAH / VAL
        poc_v = vp.get("poc", 0); vah_v = vp.get("vah", 0); val_v = vp.get("val", 0)
        if poc_v > 0:
            fig.add_hline(y=poc_v, line_color="#ffaa00", line_width=1.8,
                         annotation_text=f"POC ${poc_v:,.2f}",
                         annotation_position="right",
                         annotation_font_color="#ffaa00", annotation_font_size=10,
                         row=1, col=1)
        if vah_v > 0:
            fig.add_hline(y=vah_v, line_color="#00d4aa", line_width=1, line_dash="dash",
                         annotation_text=f"VAH ${vah_v:,.2f}",
                         annotation_position="right",
                         annotation_font_color="#00d4aa", annotation_font_size=9,
                         row=1, col=1)
        if val_v > 0:
            fig.add_hline(y=val_v, line_color="#ff4444", line_width=1, line_dash="dash",
                         annotation_text=f"VAL ${val_v:,.2f}",
                         annotation_position="right",
                         annotation_font_color="#ff4444", annotation_font_size=9,
                         row=1, col=1)

    # ── Order Blocks ─────────────────────────────────────────
    obs = dados_a.get("order_blocks", {})
    for ob in obs.get("bull", [])[-2:]:
        fig.add_hrect(y0=ob["nivel_baixo"], y1=ob["nivel_alto"],
                     fillcolor="rgba(0,212,170,0.07)", line_color="#00d4aa",
                     line_width=0.8, row=1, col=1,
                     annotation_text="OB↑", annotation_font_color="#00d4aa",
                     annotation_font_size=9)
    for ob in obs.get("bear", [])[-2:]:
        fig.add_hrect(y0=ob["nivel_baixo"], y1=ob["nivel_alto"],
                     fillcolor="rgba(255,68,68,0.07)", line_color="#ff4444",
                     line_width=0.8, row=1, col=1,
                     annotation_text="OB↓", annotation_font_color="#ff4444",
                     annotation_font_size=9)

    # ── Níveis do Trade ──────────────────────────────────────
    t = analise.get("trade")
    if t:
        ct = COR_BULLISH if t["bias"]=="BULLISH" else COR_BEARISH
        for preco_n, cor_n, dash_n, lbl in [
            (t["entrada"], ct,       "dash", f"ENT ${t['entrada']:,.4f}"),
            (t["stop"],    "#ff4444","dot",  f"STP ${t['stop']:,.4f}"),
            (t["a1"],      "#88cc88","dash", f"A1 ${t['a1']:,.4f}"),
            (t["a2"],      "#55aa55","dash", f"A2 ${t['a2']:,.4f}"),
            (t["a3"],      "#00d4aa","dash", f"A3 ${t['a3']:,.4f}"),
        ]:
            fig.add_hline(y=preco_n, line_color=cor_n, line_width=1.2,
                         line_dash=dash_n, annotation_text=lbl,
                         annotation_position="left",
                         annotation_font_color=cor_n, annotation_font_size=9,
                         row=1, col=1)

    # ── Volume colorido (painel inferior) ────────────────────
    fig.add_trace(go.Bar(
        x=df.index, y=df["volume"],
        marker_color=cores_candle, opacity=0.85, name="Volume",
        hovertemplate="%{y:,.0f}<extra></extra>",
    ), row=2, col=1)

    # Linha de média de volume
    vol_ma = df["volume"].rolling(20).mean()
    fig.add_trace(go.Scatter(
        x=df.index, y=vol_ma, mode="lines", name="Vol MA20",
        line=dict(color="#ffaa00", width=1.2, dash="dot"),
        hoverinfo="skip",
    ), row=2, col=1)

    # ── Layout estilo TradingView ────────────────────────────
    fig.update_layout(
        paper_bgcolor="#0e1117",
        plot_bgcolor="#131820",
        font=dict(family="JetBrains Mono", color="#94a3b8", size=10),
        showlegend=False,
        margin=dict(l=0, r=140, t=10, b=10),
        xaxis_rangeslider_visible=False,
        height=height,
        dragmode="pan",
        hovermode="x unified",
        # Eixo Y direito clicável/arrastável
        yaxis=dict(
            side="right",
            showgrid=True, gridcolor="#1a2030",
            tickfont=dict(size=10),
            fixedrange=False,  # permite scroll vertical no eixo Y
        ),
        yaxis2=dict(
            side="right",
            showgrid=True, gridcolor="#1a2030",
            tickfont=dict(size=9),
            fixedrange=False,
        ),
    )
    fig.update_xaxes(gridcolor="#1a2030", showgrid=True, zeroline=False,
                     tickfont=dict(size=9))
    fig.update_yaxes(gridcolor="#1a2030", zeroline=False)

    # Legenda de cores dos candles (canto superior esquerdo)
    legenda_cores = [
        ("█ Spike Alta",  "#f5c518"), ("█ Alto Alta",   "#ff8c00"),
        ("█ Médio Alta",  "#00d4aa"), ("█ Baixo Alta",  "#4a9eff"),
        ("█ Spike Baixa", "#9b59b6"), ("█ Alto Baixa",  "#ff2244"),
        ("█ Médio Baixa", "#ff6600"), ("█ Baixo Baixa", "#aaaaaa"),
    ]
    for i, (lbl, cor) in enumerate(legenda_cores):
        fig.add_annotation(
            x=0.002, y=0.99 - i*0.045,
            xref="paper", yref="paper",
            text=lbl, showarrow=False,
            font=dict(size=8, color=cor),
            xanchor="left", yanchor="top",
        )

    return fig


# ════════════════════════════════════════════════════════════
#  FUNÇÃO: PAINEL DE SENTIMENTO ESTILO COINGLASS
# ════════════════════════════════════════════════════════════
def build_sentiment_panel(symbol, analise, height=520):
    """
    4 painéis empilhados com eixo X compartilhado:
    1. Funding Rate (barras, verde=negativo/bullish, vermelho=positivo/bearish)
    2. Open Interest (linha + área)
    3. CVD Aggregated (linha acumulada + barras de delta)
    4. Long/Short Ratio (linha + zona de referência)
    """
    # Buscar históricos
    fund_hist = buscar_funding_historico(symbol, 72)
    oi_hist   = buscar_oi_historico(symbol, 72)
    ls_hist   = buscar_ls_historico(symbol, 72)
    liq_hist  = buscar_liquidacoes_historico(symbol, 72)

    # Converter timestamps
    def to_dt(lst, key="t"):
        return [ts_to_dt(d[key]) for d in lst] if lst else []

    fig = make_subplots(
        rows=4, cols=1,
        shared_xaxes=True,
        row_heights=[0.28, 0.24, 0.24, 0.24],
        vertical_spacing=0.025,
        subplot_titles=(
            "Funding Rate OI-Weighted (%)",
            "Aggregated Open Interest",
            "Aggregated Spot CVD",
            "Long/Short Ratio (Accounts)",
        ),
    )

    # ── 1. Funding Rate ──────────────────────────────────────
    if fund_hist:
        x_f = to_dt(fund_hist)
        y_f = [d["v"] for d in fund_hist]
        cores_f = ["#00d4aa" if v <= 0 else "#ff4444" for v in y_f]
        fig.add_trace(go.Bar(
            x=x_f, y=y_f, marker_color=cores_f,
            name="Funding", opacity=0.85,
            hovertemplate="Funding: %{y:.4f}%<extra></extra>",
        ), row=1, col=1)
        fig.add_hline(y=0, line_color="#444", line_width=0.8, row=1, col=1)
        # Zonas de referência
        fig.add_hrect(y0=0.05,  y1=0.2,  fillcolor="rgba(255,68,68,0.08)",  line_width=0, row=1, col=1)
        fig.add_hrect(y0=-0.2, y1=-0.01, fillcolor="rgba(0,212,170,0.08)", line_width=0, row=1, col=1)
        # Último valor
        fig.add_annotation(
            x=x_f[-1], y=y_f[-1],
            text=f" {y_f[-1]:+.4f}%",
            showarrow=False, xanchor="left",
            font=dict(size=10, color="#00d4aa" if y_f[-1]<=0 else "#ff4444"),
            row=1, col=1,
        )
    else:
        # Sem dados — mostrar valor atual
        fd = analise.get("dados",{}).get("sentimento",{}).get("funding",{})
        taxa = fd.get("taxa",0)
        cor_f = "#00d4aa" if taxa<=0 else "#ff4444"
        fig.add_trace(go.Bar(
            x=[datetime.utcnow()], y=[taxa],
            marker_color=[cor_f], name="Funding",
            hovertemplate=f"Funding: {taxa:+.4f}%<extra></extra>",
        ), row=1, col=1)

    # ── 2. Open Interest ────────────────────────────────────
    if oi_hist:
        x_oi = to_dt(oi_hist)
        y_oi = [d["v"] for d in oi_hist]
        # Linha principal
        fig.add_trace(go.Scatter(
            x=x_oi, y=y_oi, mode="lines",
            line=dict(color="#f7931a", width=1.8),
            fill="tozeroy", fillcolor="rgba(247,147,26,0.08)",
            name="OI", hovertemplate="OI: %{y:,.0f}<extra></extra>",
        ), row=2, col=1)
        # Delta de OI (variação barra a barra)
        delta_oi = [0] + [y_oi[i]-y_oi[i-1] for i in range(1,len(y_oi))]
        cores_oi = ["#00d4aa" if d>=0 else "#ff4444" for d in delta_oi]
        fig.add_trace(go.Bar(
            x=x_oi, y=delta_oi, marker_color=cores_oi, opacity=0.5,
            name="ΔOI", hovertemplate="ΔOI: %{y:,.0f}<extra></extra>",
            yaxis="y5",
        ), row=2, col=1)
    else:
        oi_d = analise.get("dados",{}).get("sentimento",{}).get("oi",{})
        fig.add_annotation(
            text=f"OI: {oi_d.get('variacao_pct',0):+.1f}%  {oi_d.get('sinal','—')}",
            xref="paper", yref="paper", x=0.5, y=0.6,
            showarrow=False, font=dict(size=12, color="#f7931a"),
            row=2, col=1,
        )

    # ── 3. CVD ───────────────────────────────────────────────
    cvd_h = analise.get("dados",{}).get("sentimento",{}).get("cvd",{}).get("historico",[])
    if cvd_h:
        x_cvd = list(range(len(cvd_h)))
        # Usar timestamps do OI se disponível, senão índice
        if oi_hist and len(oi_hist) >= len(cvd_h):
            x_cvd = to_dt(oi_hist[-len(cvd_h):])
        elif liq_hist and len(liq_hist) >= len(cvd_h):
            x_cvd = to_dt(liq_hist[-len(cvd_h):])

        # CVD acumulado como linha
        fig.add_trace(go.Scatter(
            x=x_cvd, y=cvd_h, mode="lines",
            line=dict(color="#00d4aa" if cvd_h[-1]>=0 else "#ff4444", width=2),
            fill="tozeroy",
            fillcolor="rgba(0,212,170,0.06)" if cvd_h[-1]>=0 else "rgba(255,68,68,0.06)",
            name="CVD", hovertemplate="CVD: %{y:,.0f}<extra></extra>",
        ), row=3, col=1)
        fig.add_hline(y=0, line_color="#444", line_width=0.8, row=3, col=1)

        # Linha de tendência CVD
        if len(cvd_h) > 6:
            xn = list(range(len(cvd_h)))
            z  = np.polyfit(xn, cvd_h, 1)
            p  = np.poly1d(z)
            cor_tr = "#00d4aa" if z[0]>0 else "#ff4444"
            fig.add_trace(go.Scatter(
                x=x_cvd, y=[p(i) for i in xn],
                mode="lines", line=dict(color=cor_tr, width=1, dash="dot"),
                name="Tendência CVD", hoverinfo="skip",
            ), row=3, col=1)

    # ── 4. Long/Short Ratio ──────────────────────────────────
    if ls_hist:
        x_ls   = to_dt(ls_hist)
        y_long = [d["long"]  for d in ls_hist]
        y_short= [d["short"] for d in ls_hist]
        y_ratio= [d["ratio"] for d in ls_hist]

        # Área empilhada long/short
        fig.add_trace(go.Scatter(
            x=x_ls, y=y_long, mode="lines",
            line=dict(color="#00d4aa", width=0),
            fill="tozeroy", fillcolor="rgba(0,212,170,0.25)",
            name="Long %", stackgroup="ls",
            hovertemplate="Long: %{y:.1f}%<extra></extra>",
        ), row=4, col=1)
        fig.add_trace(go.Scatter(
            x=x_ls, y=y_short, mode="lines",
            line=dict(color="#ff4444", width=0),
            fill="tonexty", fillcolor="rgba(255,68,68,0.25)",
            name="Short %", stackgroup="ls",
            hovertemplate="Short: %{y:.1f}%<extra></extra>",
        ), row=4, col=1)

        # Linha ratio
        fig.add_trace(go.Scatter(
            x=x_ls, y=y_ratio, mode="lines",
            line=dict(color="#ffaa00", width=1.5),
            name="Ratio", yaxis="y8",
            hovertemplate="Ratio: %{y:.2f}<extra></extra>",
        ), row=4, col=1)

        # Zonas de referência
        fig.add_hline(y=50, line_color="#444", line_width=0.8, line_dash="dot", row=4, col=1)
        # Último valor
        ultimo_ls = ls_hist[-1]
        cor_ls = "#00d4aa" if ultimo_ls["ratio"]<0.7 else ("#ff4444" if ultimo_ls["ratio"]>1.5 else "#ffaa00")
        fig.add_annotation(
            x=x_ls[-1], y=ultimo_ls["long"],
            text=f" L/S {ultimo_ls['ratio']:.2f}",
            showarrow=False, xanchor="left",
            font=dict(size=10, color=cor_ls),
            row=4, col=1,
        )
    else:
        ls_d = analise.get("dados",{}).get("sentimento",{}).get("ls_ratio",{})
        lp   = ls_d.get("long_pct",50); sp=ls_d.get("short_pct",50)
        fig.add_trace(go.Bar(
            x=["Long","Short"], y=[lp,sp],
            marker_color=[COR_BULLISH, COR_BEARISH],
            text=[f"{lp:.1f}%",f"{sp:.1f}%"], textposition="outside",
        ), row=4, col=1)

    # ── Layout ───────────────────────────────────────────────
    fig.update_layout(
        paper_bgcolor="#0e1117", plot_bgcolor="#131820",
        font=dict(family="JetBrains Mono", color="#94a3b8", size=9),
        showlegend=False, height=height,
        margin=dict(l=0, r=10, t=30, b=10),
        hovermode="x unified",
        barmode="overlay",
    )
    for i in range(1, 5):
        fig.update_xaxes(gridcolor="#1a2030", row=i, col=1, showgrid=True, zeroline=False)
        fig.update_yaxes(gridcolor="#1a2030", row=i, col=1, showgrid=True, zeroline=False,
                        side="right", tickfont=dict(size=8))
    fig.update_annotations(font_size=10, font_color="#94a3b8")

    return fig


# ════════════════════════════════════════════════════════════
#  BLOCO GRÁFICO — TF SELECTOR + GRÁFICO + MODAL
# ════════════════════════════════════════════════════════════
st.markdown('<div class="tf-strip">', unsafe_allow_html=True)
col_tit, c1d, c4h, c1h, c30, c15, c5m, c_exp = st.columns([2.5,.55,.55,.55,.65,.65,.55,1.3])

col_tit.markdown(
    f"<div style='font-size:16px;font-weight:700;padding-top:7px;font-family:JetBrains Mono;"
    f"color:#e2e8f0'>📊 {sym} — {st.session_state['tf_ativo'].upper()}</div>",
    unsafe_allow_html=True)

for lbl, val, col in [("1D","1d",c1d),("4H","4h",c4h),("1H","1h",c1h),
                       ("30M","30m",c30),("15M","15m",c15),("5M","5m",c5m)]:
    ativo_tf = st.session_state["tf_ativo"] == val
    if col.button(lbl, key=f"tf_{val}", use_container_width=True,
                  type="primary" if ativo_tf else "secondary"):
        st.session_state["tf_ativo"] = val
        st.rerun()

expand_click = c_exp.button("⛶ Expandir", key="exp", use_container_width=True)
st.markdown('</div>', unsafe_allow_html=True)

# Dica de uso
st.markdown(
    "<div style='font-size:10px;color:#4a5568;text-align:right;margin-top:-4px;margin-bottom:2px;'>"
    "🖱️ Arrastar = pan &nbsp;|&nbsp; Scroll = zoom &nbsp;|&nbsp; "
    "Scroll no eixo Y = comprimir/expandir candles &nbsp;|&nbsp; 2× clique = reset</div>",
    unsafe_allow_html=True)

# Gráfico inline
fig_inline = build_chart_tv(sym, st.session_state["tf_ativo"], res, height=560)
chart_cfg = {
    "displayModeBar": True,
    "modeBarButtonsToRemove": ["select2d","lasso2d","toggleSpikelines","autoScale2d"],
    "displaylogo": False,
    "scrollZoom": True,
    "toImageButtonOptions": {"format":"png","filename":f"{sym}_chart","scale":2},
}
st.plotly_chart(fig_inline, use_container_width=True, config=chart_cfg)

# Modal flutuante expandido
if expand_click:
    fig_modal = build_chart_tv(sym, st.session_state["tf_ativo"], res, height=720)
    fig_json  = fig_modal.to_json()
    st.markdown(f"""
<div id="chartOverlay" style="display:flex;position:fixed;top:0;left:0;width:100vw;height:100vh;
     background:rgba(0,0,0,.8);z-index:9998;align-items:flex-start;">
  <div id="chartModal" style="position:fixed;top:4vh;left:3vw;width:94vw;height:90vh;
       background:#0e1117;border:1px solid #2d3748;border-radius:14px;z-index:9999;
       display:flex;flex-direction:column;box-shadow:0 24px 80px rgba(0,0,0,.9);">
    <div id="chartHdr" style="display:flex;align-items:center;justify-content:space-between;
         padding:10px 16px;border-bottom:1px solid #2d3748;cursor:move;background:#131820;
         border-radius:14px 14px 0 0;user-select:none;">
      <span style="font-family:'JetBrains Mono';font-size:14px;font-weight:700;color:#00d4aa;">
        🦈 {sym} — {st.session_state['tf_ativo'].upper()} | Expandido
      </span>
      <div style="display:flex;gap:16px;align-items:center;">
        <span style="font-size:10px;color:#4a5568;">Arraste para mover · Canto inferior direito para redimensionar</span>
        <button onclick="document.getElementById('chartOverlay').style.display='none'"
                style="background:none;border:none;color:#ff4444;font-size:22px;cursor:pointer;padding:0 6px;">✕</button>
      </div>
    </div>
    <div style="flex:1;overflow:hidden;padding:4px;">
      <div id="plotlyModal" style="width:100%;height:100%;"></div>
    </div>
    <div id="resizeHandle" style="position:absolute;right:0;bottom:0;width:20px;height:20px;
         cursor:se-resize;background:linear-gradient(135deg,transparent 50%,#2d3748 50%);
         border-radius:0 0 14px 0;"></div>
  </div>
</div>
<script src="https://cdn.plot.ly/plotly-2.27.0.min.js"></script>
<script>
(function(){{
  var fig = {fig_json};
  Plotly.newPlot('plotlyModal', fig.data, fig.layout, {{
    scrollZoom:true, displayModeBar:true, responsive:true,
    modeBarButtonsToRemove:['select2d','lasso2d','toggleSpikelines'],
    displaylogo:false
  }});
  var modal=document.getElementById('chartModal'),
      hdr=document.getElementById('chartHdr'),
      rh=document.getElementById('resizeHandle');
  var drag=false,sx,sy,ox,oy;
  hdr.addEventListener('mousedown',function(e){{
    drag=true;sx=e.clientX;sy=e.clientY;
    var r=modal.getBoundingClientRect();ox=r.left;oy=r.top;
    document.addEventListener('mousemove',onDrag);
    document.addEventListener('mouseup',function(){{drag=false;document.removeEventListener('mousemove',onDrag);}});
  }});
  function onDrag(e){{
    if(!drag)return;
    modal.style.left=(ox+e.clientX-sx)+'px';
    modal.style.top=(oy+e.clientY-sy)+'px';
    Plotly.Plots.resize(document.getElementById('plotlyModal'));
  }}
  var rsz=false,rsx,rsy,rw,rh2;
  rh.addEventListener('mousedown',function(e){{
    rsz=true;rsx=e.clientX;rsy=e.clientY;rw=modal.offsetWidth;rh2=modal.offsetHeight;
    document.addEventListener('mousemove',onResize);
    document.addEventListener('mouseup',function(){{rsz=false;document.removeEventListener('mousemove',onResize);}});
    e.stopPropagation();
  }});
  function onResize(e){{
    if(!rsz)return;
    modal.style.width=Math.max(400,rw+e.clientX-rsx)+'px';
    modal.style.height=Math.max(300,rh2+e.clientY-rsy)+'px';
    Plotly.Plots.resize(document.getElementById('plotlyModal'));
  }}
}})();
</script>""", unsafe_allow_html=True)


# ════════════════════════════════════════════════════════════
#  PAINEL DE SENTIMENTO ESTILO COINGLASS
# ════════════════════════════════════════════════════════════
st.markdown("---")
st.markdown("### 📡 SENTIMENTO DE MERCADO — Estilo Coinglass")

fig_sent = build_sentiment_panel(sym, res, height=520)
st.plotly_chart(fig_sent, use_container_width=True, config={
    "displayModeBar": True,
    "displaylogo": False,
    "scrollZoom": True,
    "modeBarButtonsToRemove": ["select2d","lasso2d"],
})


# ════════════════════════════════════════════════════════════
#  TOP-DOWN
# ════════════════════════════════════════════════════════════
st.markdown("---")
st.markdown("### 🔭 ANÁLISE TOP-DOWN — 1D → 1H → 15M")
estrutura = dados.get("estrutura",{}); wyckoff=dados.get("wyckoff",{}); obv_d=dados.get("obv",{})

def tf_card(lbl, est, wyk, obv_i):
    bx=est.get("bias","NEUTRO"); t="bullish" if bx=="BULLISH" else ("bearish" if bx=="BEARISH" else "neutro")
    wf=wyk.get("fase","—") if wyk else "—"
    tuk="🔵 TUK TUK " if(wyk and wyk.get("tuk_tuk"))else ""
    spr="🟢 SPRING "  if(wyk and wyk.get("spring")) else ""
    upt="🔴 UPTHRUST" if(wyk and wyk.get("upthrust"))else ""
    os_=obv_i.get("sinal","—") if obv_i else "—"
    ob_=obv_i.get("bias","NEUTRO") if obv_i else "NEUTRO"
    ot_="bullish" if ob_=="BULLISH" else("bearish" if ob_=="BEARISH" else "neutro")
    return f"""<div class="metric-card metric-card-{t}">
<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:10px">
<span style="font-family:'JetBrains Mono';font-weight:700;font-size:16px;color:{cor_bias(bx)}">{lbl}</span>
{badge(bx,t)}</div>
<div style="font-size:12px;color:#94a3b8;margin-bottom:4px"><b style="color:#e2e8f0">Estrutura:</b> {est.get('estrutura','—')}</div>
<div style="font-size:12px;color:#94a3b8;margin-bottom:4px"><b style="color:#e2e8f0">Evento:</b> {est.get('ultimo_evento','—')}</div>
<div style="font-size:12px;color:#94a3b8;margin-bottom:4px"><b style="color:#e2e8f0">Wyckoff:</b> {wf}</div>
<div style="font-size:12px;color:#94a3b8;margin-bottom:6px"><b style="color:#e2e8f0">OBV:</b> {os_} {badge(ob_,ot_)}</div>
<div>{tuk}{spr}{upt}</div></div>"""

c1d_,c1h_,c15_ = st.columns(3)
c1d_.markdown(tf_card("1D",estrutura.get("1d",{}),wyckoff.get("1h",{}),obv_d.get("1d",{})),unsafe_allow_html=True)
c1h_.markdown(tf_card("1H",estrutura.get("1h",{}),wyckoff.get("1h",{}),obv_d.get("1h",{})),unsafe_allow_html=True)
c15_.markdown(tf_card("15M",estrutura.get("15m",{}),wyckoff.get("15m",{}),obv_d.get("1h",{})),unsafe_allow_html=True)


# ════════════════════════════════════════════════════════════
#  CONFLUÊNCIAS
# ════════════════════════════════════════════════════════════
st.markdown("---")
cbull,cbear=st.columns(2)
cbull.markdown(f"<div style='display:flex;align-items:center;gap:8px;margin-bottom:10px'><span style='font-size:18px'>🟢</span><span style='font-weight:700;font-size:15px;color:{COR_BULLISH}'>CONFLUÊNCIAS LONG ({pb}/9)</span></div>",unsafe_allow_html=True)
cbear.markdown(f"<div style='display:flex;align-items:center;gap:8px;margin-bottom:10px'><span style='font-size:18px'>🔴</span><span style='font-weight:700;font-size:15px;color:{COR_BEARISH}'>CONFLUÊNCIAS SHORT ({pbe}/9)</span></div>",unsafe_allow_html=True)
for item in (detalhes if bias=="BULLISH" else []):
    cbull.markdown(f"<div class='conf-item'><span style='color:{COR_BULLISH}'>✓</span><span style='font-size:13px;color:#e2e8f0'>{item}</span></div>",unsafe_allow_html=True)
if not detalhes or bias!="BULLISH":
    cbull.markdown("<div style='color:#4a5568;font-size:13px;padding:6px 0'>Sem confluências bullish suficientes</div>",unsafe_allow_html=True)
for item in (detalhes if bias=="BEARISH" else []):
    cbear.markdown(f"<div class='conf-item'><span style='color:{COR_BEARISH}'>✓</span><span style='font-size:13px;color:#e2e8f0'>{item}</span></div>",unsafe_allow_html=True)
if not detalhes or bias!="BEARISH":
    cbear.markdown("<div style='color:#4a5568;font-size:13px;padding:6px 0'>Sem confluências bearish suficientes</div>",unsafe_allow_html=True)


# ════════════════════════════════════════════════════════════
#  TRADE SETUP
# ════════════════════════════════════════════════════════════
st.markdown("---")
st.markdown("### 🎯 SETUP DE TRADE — Metodologia Agregada")

if trade is None:
    st.markdown(f"""<div class="metric-card metric-card-neutro" style="padding:20px;max-width:580px">
<div style="font-size:24px;margin-bottom:10px">⚠️</div>
<div style="font-size:15px;font-weight:600;color:#ffaa00;margin-bottom:6px">Trade não gerado</div>
<div style="font-size:13px;color:#94a3b8">
Confluências insuficientes ({conf}/9 — mínimo {CONFLUENCIAS_MIN}) ou R/R inválido para {sym}.
</div></div>""", unsafe_allow_html=True)
else:
    tc=COR_BULLISH if trade["bias"]=="BULLISH" else COR_BEARISH
    tt="bullish" if trade["bias"]=="BULLISH" else "bearish"
    em="🟢" if trade["bias"]=="BULLISH" else "🔴"
    pd_="  ⏳ PENDING" if trade.get("entrada_distante") else ""
    c=trade["cenarios"]
    ct_,cg_,cc_=st.columns([1.5,1,1.5])
    ct_.markdown(f"""<div class="trade-card" style="border-left:3px solid {tc}">
<div style="font-size:16px;font-weight:700;color:{tc};margin-bottom:14px">{em} {sym} {trade['bias']}{pd_}</div>
<div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;font-size:13px;">
<div><div style="color:#94a3b8;font-size:10px;text-transform:uppercase">ENTRADA</div>
<div style="color:#e2e8f0;font-weight:700">${trade['entrada']:,.4f}</div></div>
<div><div style="color:#94a3b8;font-size:10px;text-transform:uppercase">STOP</div>
<div style="color:{COR_BEARISH};font-weight:700">${trade['stop']:,.4f}</div></div>
<div><div style="color:#94a3b8;font-size:10px;text-transform:uppercase">A1 (1:1)</div>
<div style="color:#88cc88;font-weight:700">${trade['a1']:,.4f}</div></div>
<div><div style="color:#94a3b8;font-size:10px;text-transform:uppercase">A2 (2:1)</div>
<div style="color:#66bb66;font-weight:700">${trade['a2']:,.4f}</div></div>
<div style="grid-column:span 2"><div style="color:#94a3b8;font-size:10px;text-transform:uppercase">A3 (3:1)</div>
<div style="color:{COR_BULLISH};font-weight:700;font-size:14px">${trade['a3']:,.4f}</div></div>
</div><hr style="border-color:#2d3748;margin:10px 0">
<div style="font-size:11px;color:#94a3b8">Stop: <span style="color:#e2e8f0">{trade['stop_pct']:.2f}%</span> | Trailing: <span style="color:#e2e8f0">{trade['trailing_pct']:.1f}%</span></div>
</div>""", unsafe_allow_html=True)

    cg_.markdown(f"""<div class="metric-card">
<div style="font-size:10px;color:#94a3b8;text-transform:uppercase;letter-spacing:1px;margin-bottom:10px">GESTÃO DE RISCO</div>
<div style="font-size:12px;line-height:2;color:#e2e8f0;font-family:'JetBrains Mono'">
<div>Margem: <b>${trade['margem']:.0f}</b></div>
<div>Notional: <b>${trade['notional']:,.0f}</b></div>
<div>Qtd: <b>{trade['quantidade']:.4f}</b></div>
<hr style="border-color:#2d3748;margin:6px 0">
<div>Alav. Max: <b style="color:{COR_ALERTA}">{trade['alavancagem_max']}x</b></div>
<div>Alav. 35%: <b style="color:{COR_BULLISH}">{trade['alavancagem_35']}x</b></div>
<div>Stop %: <b style="color:{COR_BEARISH}">{trade['stop_pct']:.2f}%</b></div>
</div></div>""", unsafe_allow_html=True)

    cc_.markdown(f"""<div class="metric-card">
<div style="font-size:10px;color:#94a3b8;text-transform:uppercase;letter-spacing:1px;margin-bottom:10px">CENÁRIOS P&L</div>
<div style="font-size:12px;font-family:'JetBrains Mono';line-height:2">
<div style="display:flex;justify-content:space-between"><span style="color:#ff4444">🛑 STOP</span><span style="color:#ff4444">${c['stop']['perda']:.2f} ({c['stop']['pct']:.1f}%)</span></div>
<div style="display:flex;justify-content:space-between"><span style="color:#88cc88">🎯 A1 25%</span><span style="color:#88cc88">+${c['a1']['ganho']:.2f} (+{c['a1']['pct']:.1f}%)</span></div>
<div style="display:flex;justify-content:space-between"><span style="color:#66bb66">🎯 A2 50%</span><span style="color:#66bb66">+${c['a2']['ganho']:.2f} (+{c['a2']['pct']:.1f}%)</span></div>
<div style="display:flex;justify-content:space-between"><span style="color:{COR_BULLISH}">🏆 A3 80%</span><span style="color:{COR_BULLISH}">+${c['a3']['ganho']:.2f} (+{c['a3']['pct']:.1f}%)</span></div>
<div style="display:flex;justify-content:space-between"><span style="color:#a78bfa">🔄 TS 10%</span><span style="color:#a78bfa">+${c['ts']['ganho']:.2f} (+{c['ts']['pct']:.1f}%)</span></div>
<hr style="border-color:#2d3748;margin:6px 0">
<div style="display:flex;justify-content:space-between;font-weight:700">
<span style="color:{COR_BULLISH}">WIN TOTAL</span><span style="color:{COR_BULLISH}">+${c['win_total']:.2f} (+{c['win_pct']:.1f}%)</span></div>
</div></div>""", unsafe_allow_html=True)

    st.markdown(f"""<div class="metric-card metric-card-alerta" style="margin-top:10px">
<div style="font-size:10px;color:#94a3b8;text-transform:uppercase;letter-spacing:1px;margin-bottom:5px">🤖 COMANDO BOT</div>
<div style="font-family:'JetBrains Mono';font-size:12px;color:#ffaa00;word-break:break-all">{trade.get('comando_bot','—')}</div>
</div>""", unsafe_allow_html=True)


# ════════════════════════════════════════════════════════════
#  ORDER BLOCKS + CHECKLIST
# ════════════════════════════════════════════════════════════
st.markdown("---")
st.markdown("### 🧱 ORDER BLOCKS + ✅ CHECKLIST")
obs_d=dados.get("order_blocks",{}); obs_bull=obs_d.get("bull",[]); obs_bear=obs_d.get("bear",[])
wyck_1h=dados.get("wyckoff",{}).get("1h",{}); vol_ctx=dados.get("volume",{})

co1,co2,co3=st.columns([1,1,1.2])
co1.markdown(f"**🟢 OB Bull ({len(obs_bull)})**")
for ob in reversed(obs_bull):
    v="✅" if ob.get("fvg") else "⚠️"
    co1.markdown(f"""<div class="metric-card metric-card-bullish" style="padding:8px 12px;margin-bottom:5px">
<div style="font-family:'JetBrains Mono';font-size:11px">
Alta: <b style="color:{COR_BULLISH}">${ob['nivel_alto']:,.4f}</b> &nbsp; Baixa: <b>${ob['nivel_baixo']:,.4f}</b></div>
<div style="font-size:10px;color:#94a3b8">{v} {'Válido' if ob.get('fvg') else 'Parcial (sem FVG)'}</div></div>""",unsafe_allow_html=True)

co2.markdown(f"**🔴 OB Bear ({len(obs_bear)})**")
for ob in reversed(obs_bear):
    v="✅" if ob.get("fvg") else "⚠️"
    co2.markdown(f"""<div class="metric-card metric-card-bearish" style="padding:8px 12px;margin-bottom:5px">
<div style="font-family:'JetBrains Mono';font-size:11px">
Alta: <b style="color:{COR_BEARISH}">${ob['nivel_alto']:,.4f}</b> &nbsp; Baixa: <b>${ob['nivel_baixo']:,.4f}</b></div>
<div style="font-size:10px;color:#94a3b8">{v} {'Válido' if ob.get('fvg') else 'Parcial (sem FVG)'}</div></div>""",unsafe_allow_html=True)

co3.markdown("**✅ Checklist Wyckoff**")
checklist=[
    ("Range lateral?",          "RANGE" in wyck_1h.get("fase","") or wyck_1h.get("tuk_tuk",False)),
    ("S/R definidos?",          wyck_1h.get("range_low",0)>0),
    ("OBV definido?",           obv_d.get("1h",{}).get("bias","NEUTRO")!="NEUTRO"),
    ("Spring / Upthrust?",      wyck_1h.get("spring",False) or wyck_1h.get("upthrust",False)),
    ("Tuk Tuk COMPLETO?",       wyck_1h.get("tuk_tuk",False)),
    ("OB válido (IL+FVG)?",     any(o.get("fvg") for o in obs_bull+obs_bear)),
    ("VWAP confirma?",          dados.get("vwap",{}).get("bias","NEUTRO")==bias),
    ("Volume confirma?",        vol_ctx.get("sinal") in ["SPIKE","CRESCENTE"]),
    ("Sentimento alinhado?",    (ss>=65 and bias=="BULLISH")or(ss<=35 and bias=="BEARISH")),
    ("R/R ≥ 1:1?",             trade is not None),
]
for item,ok in checklist:
    co3.markdown(f"<div style='display:flex;align-items:center;gap:8px;padding:5px 0;border-bottom:1px solid #1e2530;font-size:12px'>"
                 f"<span>{'✅' if ok else '❌'}</span><span style='color:{'#e2e8f0' if ok else '#94a3b8'}'>{item}</span></div>",
                 unsafe_allow_html=True)
ok_t=sum(1 for _,ok in checklist if ok)
ck_t="bullish" if ok_t>=7 else("alerta" if ok_t>=4 else "bearish")
co3.markdown(f"""<div class="metric-card metric-card-{ck_t}" style="margin-top:10px;text-align:center;padding:10px">
<span style="font-family:'JetBrains Mono';font-size:13px;font-weight:700">
{ok_t}/{len(checklist)} — {'✅ VÁLIDO' if ok_t>=7 else('⚠️ PARCIAL' if ok_t>=4 else '❌ INVÁLIDO')}</span></div>""",unsafe_allow_html=True)


# ─── FOOTER ──────────────────────────────────────────────────
st.markdown(f"""<hr style="border-color:#2d3748;margin:20px 0 10px">
<div style="text-align:center;font-size:10px;color:#4a5568;font-family:'JetBrains Mono'">
🦈 Robô Agregado v1.4 — Metodologia Exclusiva Luciano | {brt()} | Binance · Coinalyze
</div>""", unsafe_allow_html=True)
