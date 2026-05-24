# ============================================================
#  ROBÔ AGREGADO v1.6d — Cloud Edition
#  Versão com diagnóstico de erro para Streamlit Cloud
# ============================================================

import streamlit as st

# set_page_config DEVE ser o primeiro comando Streamlit
st.set_page_config(
    page_title="Robô Agregado | Luciano",
    page_icon="🦈", layout="wide",
    initial_sidebar_state="expanded",
)

try:
    import pandas as pd
    import numpy as np
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots
    from datetime import datetime, timezone, timedelta
    import requests
except Exception as _import_err:
    st.error(f"Erro ao importar biblioteca: {_import_err}")
    st.stop()

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;600;700&display=swap');
html,body,[class*="css"]{background:#0e1117;color:#e2e8f0;}
.stApp{background:#0e1117;}
[data-testid="stSidebar"]{background:#1a1f2e !important;}
.card{background:#1a1f2e;border:1px solid #2d3748;border-radius:10px;padding:14px 18px;margin-bottom:10px;}
.card-bull{border-left:3px solid #00d4aa;}
.card-bear{border-left:3px solid #ff4444;}
.card-neutro{border-left:3px solid #888;}
.badge{display:inline-block;padding:2px 9px;border-radius:20px;font-size:10px;font-weight:600;text-transform:uppercase;font-family:'JetBrains Mono',monospace;}
.badge-bull{background:#00d4aa18;color:#00d4aa;border:1px solid #00d4aa44;}
.badge-bear{background:#ff444418;color:#ff4444;border:1px solid #ff444444;}
.badge-neutro{background:#88888818;color:#888;border:1px solid #88888844;}
.stButton>button{background:#2d3748;border:1px solid #4a5568;color:#e2e8f0;border-radius:7px;}
.stButton>button:hover{border-color:#00d4aa;}
</style>
""", unsafe_allow_html=True)

# ─── HELPERS ─────────────────────────────────────────────────
def brt():
    return datetime.now(timezone(timedelta(hours=-3))).strftime("%d/%m/%Y %H:%M BRT")

def badge(txt, tipo="neutro"):
    return f'<span class="badge badge-{tipo}">{txt}</span>'

# ─── ESTADO ──────────────────────────────────────────────────
for k,v in [("resultado",None),("sym_analisado",""),("tf","1h")]:
    if k not in st.session_state: st.session_state[k] = v

# ─── FUNÇÕES DE DADOS ────────────────────────────────────────
@st.cache_data(ttl=60)
def get_ohlcv(symbol, tf="1h", limit=200):
    try:
        r = requests.get(
            "https://fapi.binance.com/fapi/v1/klines",
            params={"symbol":symbol,"interval":tf,"limit":limit}, timeout=10
        )
        if r.status_code == 200:
            df = pd.DataFrame(r.json(), columns=["ts","o","h","l","c","v","ct","qv","n","tbv","tqv","ig"])
            df["ts"] = pd.to_datetime(df["ts"], unit="ms")
            for col in ["o","h","l","c","v"]: df[col] = df[col].astype(float)
            df = df[["ts","o","h","l","c","v"]].rename(columns={"ts":"time","o":"open","h":"high","l":"low","c":"close","v":"volume"})
            df.set_index("time", inplace=True)
            return df
        # fallback spot
        r2 = requests.get(
            "https://api.binance.com/api/v3/klines",
            params={"symbol":symbol,"interval":tf,"limit":limit}, timeout=10
        )
        if r2.status_code == 200:
            df = pd.DataFrame(r2.json(), columns=["ts","o","h","l","c","v","ct","qv","n","tbv","tqv","ig"])
            df["ts"] = pd.to_datetime(df["ts"], unit="ms")
            for col in ["o","h","l","c","v"]: df[col] = df[col].astype(float)
            df = df[["ts","o","h","l","c","v"]].rename(columns={"ts":"time","o":"open","h":"high","l":"low","c":"close","v":"volume"})
            df.set_index("time", inplace=True)
            return df
    except: pass
    return pd.DataFrame()

@st.cache_data(ttl=30)
def get_price(symbol):
    for url in [
        f"https://fapi.binance.com/fapi/v1/ticker/price?symbol={symbol}",
        f"https://api.binance.com/api/v3/ticker/price?symbol={symbol}",
    ]:
        try:
            r = requests.get(url, timeout=5)
            if r.status_code == 200: return float(r.json()["price"])
        except: pass
    return 0.0

@st.cache_data(ttl=60)
def get_funding(symbol):
    try:
        r = requests.get(f"https://fapi.binance.com/fapi/v1/fundingRate",
                        params={"symbol":symbol,"limit":1}, timeout=5)
        if r.status_code == 200:
            data = r.json()
            if data: return float(data[-1]["fundingRate"]) * 100
    except: pass
    return 0.0

@st.cache_data(ttl=60)
def get_ls_ratio(symbol):
    try:
        r = requests.get("https://fapi.binance.com/futures/data/globalLongShortAccountRatio",
                        params={"symbol":symbol,"period":"1h","limit":1}, timeout=5)
        if r.status_code == 200:
            data = r.json()
            if data: return float(data[-1]["longShortRatio"]), float(data[-1]["longAccount"])*100, float(data[-1]["shortAccount"])*100
    except: pass
    return 1.0, 50.0, 50.0

def zscore_volume(df, length=55):
    vol = df["volume"]
    ema = vol.ewm(span=length, adjust=False).mean()
    std = vol.rolling(length, min_periods=2).std().fillna(1)
    return (vol - ema) / std.replace(0, 1)

def candle_colors(df):
    z = zscore_volume(df)
    cores = []
    for i in range(len(df)):
        zi = z.iloc[i]
        alta = df["close"].iloc[i] >= df["open"].iloc[i]
        if zi > 4.0:   c = "#ff3232" if alta else "#b400ff"
        elif zi > 2.5: c = "#ff8c00" if alta else "#ff50c8"
        elif zi > 1.0: c = "#ffd700"
        elif zi > -0.5: c = "#dcdcdc"
        else:          c = "#6495ed"
        cores.append(c)
    return cores, z

def calc_vwap(df, anchor=0):
    sub = df.iloc[anchor:].copy()
    sub["tp"] = (sub["high"] + sub["low"] + sub["close"]) / 3
    sub["tv"] = sub["tp"] * sub["volume"]
    return (sub["tv"].cumsum() / sub["volume"].cumsum()).rename("vwap")

def calc_vp(df, bins=25):
    if df.empty or len(df) < 5: return {}
    lo, hi = df["low"].min(), df["high"].max()
    faixas = np.linspace(lo, hi, bins+1)
    vols = np.zeros(bins)
    for _, row in df.iterrows():
        for i in range(bins):
            ol = max(row["low"], faixas[i])
            oh = min(row["high"], faixas[i+1])
            if oh > ol:
                frac = (oh-ol) / max(row["high"]-row["low"], 1e-10)
                vols[i] += row["volume"] * frac
    centros = [(faixas[i]+faixas[i+1])/2 for i in range(bins)]
    poc_idx = int(np.argmax(vols))
    poc = centros[poc_idx]
    vt = vols.sum(); va = vt*0.7
    va_idx = [poc_idx]; va_vol = vols[poc_idx]; lo_i, hi_i = poc_idx, poc_idx
    while va_vol < va and (lo_i>0 or hi_i<bins-1):
        al = vols[lo_i-1] if lo_i>0 else -1
        ah = vols[hi_i+1] if hi_i<bins-1 else -1
        if al>=ah and lo_i>0: lo_i-=1; va_vol+=vols[lo_i]; va_idx.append(lo_i)
        elif hi_i<bins-1: hi_i+=1; va_vol+=vols[hi_i]; va_idx.append(hi_i)
        else: break
    return {"poc":poc,"vah":centros[max(va_idx)],"val":centros[min(va_idx)],
            "faixas":centros,"volumes":vols.tolist(),"poc_idx":poc_idx}

def find_anchors(df, cores, z):
    if len(df) < 10: return len(df)//3, len(df)//2, 0
    cores_topo  = {"#b400ff","#ff50c8"}
    cores_fundo = {"#ff3232","#ff8c00"}
    preco_mid = (df["high"].max() + df["low"].min()) / 2
    bt, bf = 0, 0; it, ib = None, None
    for i,(c,zi) in enumerate(zip(cores, z)):
        pm = (df["high"].iloc[i]+df["low"].iloc[i])/2
        vol = df["volume"].iloc[i]
        if c in cores_topo and pm > preco_mid and vol > bt: bt=vol; it=i
        if c in cores_fundo and pm < preco_mid and vol > bf: bf=vol; ib=i
    # VP anchor: início do range (últimos 80 candles)
    q20 = df["low"].quantile(0.15); q80 = df["high"].quantile(0.85)
    ivp = 0
    for i in range(len(df)-1, max(0,len(df)-80), -1):
        p = df["close"].iloc[i]
        if p < q20 or p > q80: ivp = min(i+1, len(df)-1); break
    return (it if it is not None else len(df)//3,
            ib if ib is not None else len(df)//2,
            ivp)

def build_chart(sym, tf, height=560):
    df = get_ohlcv(sym, tf, 200)
    if df.empty: return go.Figure()

    cores, z = candle_colors(df)
    it, ib, ivp = find_anchors(df, cores, z)

    # VWAPs
    vwap_topo  = calc_vwap(df, it)
    vwap_fundo = calc_vwap(df, ib)

    # Volume Profile
    df_vp = df.iloc[ivp:]
    vp = calc_vp(df_vp, bins=28)

    fig = make_subplots(rows=2, cols=1, shared_xaxes=True,
                       row_heights=[0.78, 0.22], vertical_spacing=0.01)

    # Candles agrupados por cor
    grupos = {}
    for i,c in enumerate(cores):
        grupos.setdefault(c,[]).append(i)

    for c, idxs in grupos.items():
        sub = df.iloc[idxs]
        fig.add_trace(go.Candlestick(
            x=sub.index, open=sub["open"], high=sub["high"],
            low=sub["low"], close=sub["close"],
            increasing_line_color=c, decreasing_line_color=c,
            increasing_fillcolor=c, decreasing_fillcolor=c,
            showlegend=False, whiskerwidth=0.4,
        ), row=1, col=1)

    # VWAP Topo
    if not vwap_topo.empty:
        fig.add_trace(go.Scatter(x=vwap_topo.index, y=vwap_topo.values,
            mode="lines", line=dict(color="#e040fb", width=1.8, dash="dot"),
            name="VWAP↓", hovertemplate="VWAP Topo: $%{y:,.4f}<extra></extra>"),
            row=1, col=1)
        fig.add_trace(go.Scatter(x=[df.index[it]], y=[df["high"].iloc[it]*1.002],
            mode="markers", marker=dict(symbol="triangle-down", color="#e040fb", size=8),
            showlegend=False), row=1, col=1)

    # VWAP Fundo
    if not vwap_fundo.empty:
        fig.add_trace(go.Scatter(x=vwap_fundo.index, y=vwap_fundo.values,
            mode="lines", line=dict(color="#00e676", width=1.8, dash="dot"),
            name="VWAP↑", hovertemplate="VWAP Fundo: $%{y:,.4f}<extra></extra>"),
            row=1, col=1)
        fig.add_trace(go.Scatter(x=[df.index[ib]], y=[df["low"].iloc[ib]*0.998],
            mode="markers", marker=dict(symbol="triangle-up", color="#00e676", size=8),
            showlegend=False), row=1, col=1)

    # Volume Profile sobreposto
    if vp and ivp < len(df):
        faixas = vp["faixas"]; volumes = vp["volumes"]
        vm = max(volumes) if max(volumes) > 0 else 1
        x0 = df.index[ivp]
        try:
            dt = df.index[-1] - df.index[-2]
            n = len(df) - ivp
            x1 = x0 + dt * int(n * 0.28)
        except: x1 = df.index[min(ivp+20, len(df)-1)]
        h = (max(faixas)-min(faixas)) / max(len(faixas)-1,1) * 0.88
        for i,(f,v) in enumerate(zip(faixas,volumes)):
            frac = v/vm
            xe = x0 + (x1-x0)*frac
            is_poc = (i == vp["poc_idx"])
            in_va = vp["val"] <= f <= vp["vah"]
            cor = "#ffaa00" if is_poc else ("rgba(0,200,100,0.4)" if in_va else "rgba(60,100,180,0.22)")
            fig.add_shape(type="rect", x0=x0, x1=xe,
                y0=f-h/2, y1=f+h/2, fillcolor=cor, line=dict(width=0),
                opacity=0.9 if is_poc else 1.0, row=1, col=1)

        poc = vp["poc"]; vah = vp["vah"]; val = vp["val"]
        if poc: fig.add_hline(y=poc, line_color="#ffaa00", line_width=1.5,
            annotation_text=f"POC ${poc:,.2f}", annotation_position="right",
            annotation_font_color="#ffaa00", annotation_font_size=9, row=1, col=1)
        if vah: fig.add_hline(y=vah, line_color="#00d4aa", line_width=0.8, line_dash="dash",
            annotation_text=f"VAH ${vah:,.2f}", annotation_position="right",
            annotation_font_color="#00d4aa", annotation_font_size=8, row=1, col=1)
        if val: fig.add_hline(y=val, line_color="#ff4444", line_width=0.8, line_dash="dash",
            annotation_text=f"VAL ${val:,.2f}", annotation_position="right",
            annotation_font_color="#ff4444", annotation_font_size=8, row=1, col=1)

    # Volume colorido no painel
    fig.add_trace(go.Bar(x=df.index, y=df["volume"],
        marker_color=cores, opacity=0.8, name="Vol"), row=2, col=1)

    # MA volume
    vol_ma = df["volume"].ewm(span=55, adjust=False).mean()
    fig.add_trace(go.Scatter(x=df.index, y=vol_ma, mode="lines",
        line=dict(color="#ff8c00", width=1.2, dash="dot"), hoverinfo="skip"), row=2, col=1)

    fig.update_layout(
        paper_bgcolor="#0e1117", plot_bgcolor="#131820",
        font=dict(family="JetBrains Mono", color="#94a3b8", size=10),
        showlegend=False, height=height,
        margin=dict(l=0, r=130, t=10, b=10),
        xaxis_rangeslider_visible=False,
        dragmode="pan", hovermode="x unified",
        yaxis=dict(side="right", gridcolor="#1a2030", fixedrange=False),
        yaxis2=dict(side="right", gridcolor="#1a2030", fixedrange=False),
    )
    fig.update_xaxes(gridcolor="#1a2030", zeroline=False)

    # Legenda de cores
    legendas = [("Extra Alto Alta","#ff3232"),("Alto Alta","#ff8c00"),
                ("Médio","#ffd700"),("Normal","#dcdcdc"),
                ("Extra Alto Baixa","#b400ff"),("Alto Baixa","#ff50c8"),("Fraco","#6495ed")]
    for i,(l,c) in enumerate(legendas):
        fig.add_annotation(x=0.002, y=0.99-i*0.055, xref="paper", yref="paper",
            text=f"█ {l}", showarrow=False, font=dict(size=8, color=c),
            xanchor="left", yanchor="top")
    return fig

def analisar(symbol):
    preco = get_price(symbol)
    df1d  = get_ohlcv(symbol, "1d", 60)
    df1h  = get_ohlcv(symbol, "1h", 200)
    funding = get_funding(symbol)
    ratio, lp, sp = get_ls_ratio(symbol)

    # OBV
    obv_bias = "NEUTRO"
    if not df1h.empty and len(df1h) > 20:
        obv = [0]
        for i in range(1, len(df1h)):
            if df1h["close"].iloc[i] > df1h["close"].iloc[i-1]: obv.append(obv[-1]+df1h["volume"].iloc[i])
            elif df1h["close"].iloc[i] < df1h["close"].iloc[i-1]: obv.append(obv[-1]-df1h["volume"].iloc[i])
            else: obv.append(obv[-1])
        obv_s = pd.Series(obv)
        sl = (obv_s.iloc[-1]-obv_s.iloc[-20]) / (abs(obv_s.iloc[-20])+1)
        ps = (df1h["close"].iloc[-1]-df1h["close"].iloc[-20]) / df1h["close"].iloc[-20]
        if sl>0.01 and ps>0.01: obv_bias="ACUMULAÇÃO"
        elif sl<-0.01 and ps<-0.01: obv_bias="DISTRIBUIÇÃO"
        elif sl>0.01 and ps<-0.01: obv_bias="DIV. BULLISH"
        elif sl<-0.01 and ps>0.01: obv_bias="DIV. BEARISH"

    # VWAP
    vwap_bias = "NEUTRO"; vwap_val = 0; vwap_pct = 0
    if not df1h.empty and preco > 0:
        anchor = max(0, len(df1h)-5*24)
        vwap = calc_vwap(df1h, anchor)
        if not vwap.empty:
            vwap_val = vwap.iloc[-1]
            vwap_pct = (preco - vwap_val) / vwap_val * 100
            vwap_bias = "BULLISH" if vwap_pct>0.5 else ("BEARISH" if vwap_pct<-0.5 else "NEUTRO")

    # Estrutura
    est_bias = "NEUTRO"; est_str = "—"
    if not df1h.empty and len(df1h)>20:
        highs = df1h["high"]; lows = df1h["low"]
        def sw_top(n=5):
            tops=[]
            for i in range(n,len(highs)-n):
                if highs.iloc[i]==highs.iloc[i-n:i+n+1].max(): tops.append(i)
            return tops
        def sw_bot(n=5):
            bots=[]
            for i in range(n,len(lows)-n):
                if lows.iloc[i]==lows.iloc[i-n:i+n+1].min(): bots.append(i)
            return bots
        tops=sw_top(); bots=sw_bot()
        if len(tops)>=2 and len(bots)>=2:
            hh = highs.iloc[tops[-1]]>highs.iloc[tops[-2]]
            hl = lows.iloc[bots[-1]]>lows.iloc[bots[-2]]
            lh = highs.iloc[tops[-1]]<highs.iloc[tops[-2]]
            ll = lows.iloc[bots[-1]]<lows.iloc[bots[-2]]
            if hh and hl: est_bias="BULLISH"; est_str="HH / HL"
            elif lh and ll: est_bias="BEARISH"; est_str="LH / LL"
            else: est_str="CHoCH"

    # Score
    score = 50
    if est_bias=="BULLISH": score+=15
    elif est_bias=="BEARISH": score-=15
    if vwap_bias=="BULLISH": score+=10
    elif vwap_bias=="BEARISH": score-=10
    if "ACUMUL" in obv_bias: score+=10
    elif "DISTRIB" in obv_bias: score-=10
    elif "DIV. BULL" in obv_bias: score+=8
    if funding < -0.01: score+=8
    elif funding > 0.05: score-=8
    if ratio < 0.7: score+=8
    elif ratio > 1.5: score-=8
    score = max(0, min(100, score))

    bias = "BULLISH" if score>=60 else ("BEARISH" if score<=40 else "NEUTRO")

    return {
        "preco": preco, "bias": bias, "score": score,
        "est_bias": est_bias, "est_str": est_str,
        "vwap_bias": vwap_bias, "vwap_val": vwap_val, "vwap_pct": vwap_pct,
        "obv_bias": obv_bias,
        "funding": funding, "ls_ratio": ratio, "long_pct": lp, "short_pct": sp,
    }

# ─── SIDEBAR ─────────────────────────────────────────────────
with st.sidebar:
    st.markdown("""<div style="text-align:center;padding:14px 0 10px">
    <div style="font-size:34px">🦈</div>
    <div style="font-family:'JetBrains Mono';font-size:17px;font-weight:700;color:#00d4aa">ROBÔ AGREGADO</div>
    <div style="font-size:10px;color:#94a3b8;margin-top:3px">Metodologia Agregada — Luciano</div>
    </div><hr style="border-color:#2d3748;margin:6px 0 12px">""", unsafe_allow_html=True)

    sym_input = st.text_input("🎯 ATIVO", value="BTCUSDT", placeholder="Ex: BTCUSDT")
    symbol = sym_input.upper().strip()
    btn_analisar = st.button("⚡ ANALISAR AGORA", use_container_width=True)

    st.markdown("<hr style='border-color:#2d3748;margin:10px 0'>", unsafe_allow_html=True)
    st.markdown("**📋 WATCHLIST**")
    for w in ["BTCUSDT","ETHUSDT","SOLUSDT","HYPEUSDT","XAGUSD","BNBUSDT"]:
        if st.button(w, key=f"w_{w}", use_container_width=True):
            symbol = w; btn_analisar = True

    st.markdown("<hr style='border-color:#2d3748;margin:10px 0'>", unsafe_allow_html=True)
    margem = st.number_input("💰 Margem (USD)", value=200, min_value=50, max_value=10000, step=50)
    st.caption(f"🕐 {brt()}")

# ─── HEADER ──────────────────────────────────────────────────
st.markdown(f"""<div style="background:linear-gradient(135deg,#1a1f2e,#0e1117);border:1px solid #2d3748;
border-radius:12px;padding:18px 24px;margin-bottom:16px;display:flex;align-items:center;gap:14px;">
<div style="font-size:32px">🦈</div>
<div>
<div style="font-family:'JetBrains Mono';font-size:19px;font-weight:700;color:#00d4aa">ROBÔ AGREGADO v1.6</div>
<div style="color:#94a3b8;font-size:11px;margin-top:2px">SMC · Wyckoff · Tuk Tuk · VP Ancorado · VWAP Ancorado · OBV · Sentimento</div>
</div>
<div style="margin-left:auto;font-family:'JetBrains Mono';font-size:10px;color:#4a5568">{brt()}</div>
</div>""", unsafe_allow_html=True)

# ─── EXECUÇÃO ────────────────────────────────────────────────
if btn_analisar:
    with st.spinner(f"⚡ Analisando {symbol}..."):
        try:
            res = analisar(symbol)
            res["symbol"] = symbol
            st.session_state["resultado"] = res
            st.session_state["sym_analisado"] = symbol
        except Exception as e:
            st.error(f"Erro: {e}")

res = st.session_state.get("resultado")
sym = st.session_state.get("sym_analisado", "")

if res is None:
    st.markdown("""<div style="text-align:center;padding:80px;color:#4a5568">
    <div style="font-size:64px;margin-bottom:20px">🦈</div>
    <div style="font-size:20px;font-weight:700;color:#00d4aa;margin-bottom:8px">ROBÔ AGREGADO</div>
    <div style="font-size:14px;color:#94a3b8">Digite um ativo e clique em ANALISAR</div>
    </div>""", unsafe_allow_html=True)
    st.stop()

# ─── MÉTRICAS ────────────────────────────────────────────────
preco = res["preco"]; bias = res["bias"]; score = res["score"]
tipo_b = "bull" if bias=="BULLISH" else ("bear" if bias=="BEARISH" else "neutro")
cor_p = "#00d4aa" if bias=="BULLISH" else ("#ff4444" if bias=="BEARISH" else "#888")
sc_cor = "#00d4aa" if score>=60 else ("#ff4444" if score<=40 else "#ffaa00")

c1,c2,c3,c4,c5 = st.columns([1,1.5,1,1,1])

c1.markdown(f"""<div class="card" style="text-align:center;border-left:3px solid {sc_cor}">
<div style="font-size:9px;color:#94a3b8;text-transform:uppercase;letter-spacing:1px;margin-bottom:6px">SCORE</div>
<div style="font-family:'JetBrains Mono';font-size:28px;font-weight:700;color:{sc_cor}">{score}</div>
<div style="margin-top:6px">{badge(bias, tipo_b)}</div></div>""", unsafe_allow_html=True)

c2.markdown(f"""<div class="card card-{tipo_b}">
<div style="font-size:9px;color:#94a3b8;text-transform:uppercase;letter-spacing:1px;margin-bottom:6px">{sym}</div>
<div style="font-family:'JetBrains Mono';font-size:26px;font-weight:700;color:{cor_p}">${preco:,.4f}</div>
<div style="font-size:10px;color:#94a3b8;margin-top:4px">Preço atual</div></div>""", unsafe_allow_html=True)

est_t = "bull" if res["est_bias"]=="BULLISH" else ("bear" if res["est_bias"]=="BEARISH" else "neutro")
c3.markdown(f"""<div class="card">
<div style="font-size:9px;color:#94a3b8;text-transform:uppercase;letter-spacing:1px;margin-bottom:6px">ESTRUTURA</div>
<div style="font-family:'JetBrains Mono';font-size:14px;font-weight:700;color:#e2e8f0">{res["est_str"]}</div>
<div style="margin-top:6px">{badge(res["est_bias"], est_t)}</div></div>""", unsafe_allow_html=True)

vt = "bull" if res["vwap_bias"]=="BULLISH" else ("bear" if res["vwap_bias"]=="BEARISH" else "neutro")
c4.markdown(f"""<div class="card card-{vt}">
<div style="font-size:9px;color:#94a3b8;text-transform:uppercase;letter-spacing:1px;margin-bottom:6px">VWAP ANCORADO</div>
<div style="font-family:'JetBrains Mono';font-size:20px;font-weight:700;color:{'#00d4aa' if res['vwap_pct']>0 else '#ff4444'}">{res["vwap_pct"]:+.2f}%</div>
<div style="font-size:10px;color:#94a3b8;margin-top:4px">${res["vwap_val"]:,.2f}</div></div>""", unsafe_allow_html=True)

fund_cor = "#00d4aa" if res["funding"]<0 else ("#ff4444" if res["funding"]>0.03 else "#888")
c5.markdown(f"""<div class="card">
<div style="font-size:9px;color:#94a3b8;text-transform:uppercase;letter-spacing:1px;margin-bottom:6px">SENTIMENTO</div>
<div style="font-family:'JetBrains Mono';font-size:13px;font-weight:700;color:{fund_cor}">Fund: {res["funding"]:+.4f}%</div>
<div style="font-size:11px;color:#94a3b8;margin-top:4px">L/S: {res["ls_ratio"]:.2f} ({res["long_pct"]:.0f}%/{res["short_pct"]:.0f}%)</div>
<div style="font-size:10px;color:#94a3b8">OBV: {res["obv_bias"]}</div></div>""", unsafe_allow_html=True)

# ─── GRÁFICO ─────────────────────────────────────────────────
# TF selector
col_t, c1d,c4h,c1h,c30,c15,c5m,c_exp = st.columns([2.5,.55,.55,.55,.65,.65,.55,1.3])
col_t.markdown(f"<div style='font-size:16px;font-weight:700;padding-top:7px;font-family:JetBrains Mono;color:#e2e8f0'>📊 {sym} — {st.session_state['tf'].upper()}</div>", unsafe_allow_html=True)

for lbl,val,col in [("1D","1d",c1d),("4H","4h",c4h),("1H","1h",c1h),("30M","30m",c30),("15M","15m",c15),("5M","5m",c5m)]:
    if col.button(lbl, key=f"tf_{val}", use_container_width=True,
                  type="primary" if st.session_state["tf"]==val else "secondary"):
        st.session_state["tf"] = val; st.rerun()

expand = c_exp.button("⛶ Expandir", key="exp", use_container_width=True)

st.markdown("<div style='font-size:10px;color:#4a5568;text-align:right;margin-top:-4px;margin-bottom:2px;'>🖱️ Arrastar = pan | Scroll = zoom | Duplo clique = reset</div>", unsafe_allow_html=True)

with st.spinner("Carregando gráfico..."):
    fig = build_chart(sym, st.session_state["tf"], 540)
    st.plotly_chart(fig, use_container_width=True, config={
        "displayModeBar":True, "scrollZoom":True, "displaylogo":False,
        "modeBarButtonsToRemove":["select2d","lasso2d","toggleSpikelines"],
    })

# Modal expandido
if expand:
    fig2 = build_chart(sym, st.session_state["tf"], 720)
    fj = fig2.to_json()
    st.markdown(f"""
<div id="ov" style="display:flex;position:fixed;top:0;left:0;width:100vw;height:100vh;background:rgba(0,0,0,.85);z-index:9998;">
<div id="md" style="position:fixed;top:3vh;left:2vw;width:96vw;height:92vh;background:#0e1117;border:1px solid #2d3748;border-radius:14px;z-index:9999;display:flex;flex-direction:column;">
<div id="hd" style="display:flex;align-items:center;justify-content:space-between;padding:10px 16px;border-bottom:1px solid #2d3748;cursor:move;background:#131820;border-radius:14px 14px 0 0;user-select:none;">
<span style="font-family:'JetBrains Mono';font-size:14px;font-weight:700;color:#00d4aa">🦈 {sym} — {st.session_state["tf"].upper()}</span>
<button onclick="document.getElementById('ov').style.display='none'" style="background:none;border:none;color:#ff4444;font-size:22px;cursor:pointer;">✕</button>
</div>
<div style="flex:1;overflow:hidden;padding:4px;"><div id="pm" style="width:100%;height:100%;"></div></div>
<div id="rh" style="position:absolute;right:0;bottom:0;width:20px;height:20px;cursor:se-resize;background:linear-gradient(135deg,transparent 50%,#2d3748 50%);border-radius:0 0 14px 0;"></div>
</div></div>
<script src="https://cdn.plot.ly/plotly-2.27.0.min.js"></script>
<script>
(function(){{
var f={fj};
Plotly.newPlot('pm',f.data,f.layout,{{scrollZoom:true,displayModeBar:true,responsive:true,displaylogo:false}});
var md=document.getElementById('md'),hd=document.getElementById('hd'),rh=document.getElementById('rh');
var drag=false,sx,sy,ox,oy;
hd.addEventListener('mousedown',function(e){{drag=true;sx=e.clientX;sy=e.clientY;var r=md.getBoundingClientRect();ox=r.left;oy=r.top;document.addEventListener('mousemove',onD);document.addEventListener('mouseup',function(){{drag=false;document.removeEventListener('mousemove',onD);}});}});
function onD(e){{if(!drag)return;md.style.left=(ox+e.clientX-sx)+'px';md.style.top=(oy+e.clientY-sy)+'px';Plotly.Plots.resize(document.getElementById('pm'));}}
var rsz=false,rsx,rsy,rw,rh2;
rh.addEventListener('mousedown',function(e){{rsz=true;rsx=e.clientX;rsy=e.clientY;rw=md.offsetWidth;rh2=md.offsetHeight;document.addEventListener('mousemove',onR);document.addEventListener('mouseup',function(){{rsz=false;document.removeEventListener('mousemove',onR);}});e.stopPropagation();}});
function onR(e){{if(!rsz)return;md.style.width=Math.max(400,rw+e.clientX-rsx)+'px';md.style.height=Math.max(300,rh2+e.clientY-rsy)+'px';Plotly.Plots.resize(document.getElementById('pm'));}}
}})();
</script>""", unsafe_allow_html=True)

# ─── FOOTER ──────────────────────────────────────────────────
st.markdown(f"""<hr style="border-color:#2d3748;margin:20px 0 10px">
<div style="text-align:center;font-size:10px;color:#4a5568;font-family:'JetBrains Mono'">
🦈 Robô Agregado v1.6 | {brt()} | Binance
</div>""", unsafe_allow_html=True)
