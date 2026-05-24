# ============================================================
#  ROBÔ AGREGADO — analise_engine.py
#  Motor de análise — aplica a Metodologia Agregada completa:
#  SMC, Wyckoff, Tuk Tuk, Volume Profile, VWAP, OBV, Sentimento
# ============================================================

import numpy as np
import pandas as pd
from utils.market_data import (
    buscar_ohlcv, calcular_vwap_ancorado, calcular_volume_profile,
    identificar_estrutura_mercado, sinal_obv, analisar_volume_contexto,
    detectar_swing_points, buscar_preco_atual,
)
from utils.sentiment import (
    buscar_funding_rate, buscar_open_interest,
    buscar_long_short_ratio, buscar_cvd,
    calcular_sentimento_geral,
)
from utils.config import (
    MARGEM_PADRAO_USD, ALAVANCAGEM_MAX, ALAVANCAGEM_35PCT,
    A1_RR, A2_RR, A3_RR, A1_REAL, A2_REAL, A3_REAL, TS_REAL,
    TRAILING_BTC, TRAILING_XAGUSD, TRAILING_DEFAULT,
    CONFLUENCIAS_MIN,
)


# ─── DETECTOR DE WYCKOFF / TUK TUK ──────────────────────────

def detectar_wyckoff(df: pd.DataFrame) -> dict:
    """
    Identifica a fase de Wyckoff e presença de Tuk Tuk.

    Tuk Tuk de Wyckoff (definição oficial Luciano):
    - Candles de baixa amplitude DENTRO do range
    - Volume CRESCENTE dentro do range (compressão)
    - Sinal = durante a compressão, NÃO no breakout
    """
    if len(df) < 20:
        return {"fase": "INDEFINIDA", "tuk_tuk": False, "spring": False, "upthrust": False}

    # Calcular amplitude dos últimos 20 candles
    df_rec = df.iloc[-20:].copy()
    df_rec["amplitude"] = df_rec["high"] - df_rec["low"]
    amplitude_media = df_rec["amplitude"].mean()

    # Últimos 5 candles para detectar compressão (Tuk Tuk)
    ultimos_5 = df_rec.iloc[-5:]
    amplitude_5 = ultimos_5["amplitude"].mean()
    vol_5 = ultimos_5["volume"].mean()
    vol_anterior = df_rec.iloc[-10:-5]["volume"].mean()

    tuk_tuk = (
        amplitude_5 < amplitude_media * 0.6 and   # candles menores
        vol_5 > vol_anterior * 1.1                 # volume crescendo
    )

    # Spring: rompimento abaixo do range + recuperação rápida
    range_low = df_rec["low"].quantile(0.1)
    range_high = df_rec["high"].quantile(0.9)
    ultimo_low = df.iloc[-1]["low"]
    ultimo_close = df.iloc[-1]["close"]
    penultimo_low = df.iloc[-2]["low"] if len(df) > 1 else ultimo_low

    spring = (
        penultimo_low < range_low * 0.995 and  # tocou abaixo do range
        ultimo_close > range_low               # fechou de volta dentro
    )

    # Upthrust: rompimento acima + recuo rápido
    ultimo_high = df.iloc[-1]["high"]
    penultimo_high = df.iloc[-2]["high"] if len(df) > 1 else ultimo_high

    upthrust = (
        penultimo_high > range_high * 1.005 and
        ultimo_close < range_high
    )

    # Volume geral: acumulação vs distribuição
    vol_subida = df_rec[df_rec["close"] > df_rec["open"]]["volume"].mean()
    vol_queda  = df_rec[df_rec["close"] < df_rec["open"]]["volume"].mean()
    if pd.isna(vol_subida): vol_subida = 0
    if pd.isna(vol_queda):  vol_queda  = 0

    # Fase
    preco_rel = (df.iloc[-1]["close"] - range_low) / max(range_high - range_low, 1)
    if tuk_tuk and preco_rel < 0.4:
        fase = "ACUMULAÇÃO (Tuk Tuk)"
    elif tuk_tuk and preco_rel > 0.6:
        fase = "DISTRIBUIÇÃO (Tuk Tuk)"
    elif spring:
        fase = "SPRING detectado"
    elif upthrust:
        fase = "UPTHRUST detectado"
    elif vol_subida > vol_queda * 1.3:
        fase = "MARKUP (acumulação)"
    elif vol_queda > vol_subida * 1.3:
        fase = "MARKDOWN (distribuição)"
    else:
        fase = "RANGE (lateralização)"

    return {
        "fase": fase,
        "tuk_tuk": tuk_tuk,
        "spring": spring,
        "upthrust": upthrust,
        "range_low": range_low,
        "range_high": range_high,
        "vol_subida": vol_subida,
        "vol_queda": vol_queda,
        "amplitude_compressao": amplitude_5 / max(amplitude_media, 1),
    }


def detectar_order_blocks(df: pd.DataFrame) -> list:
    """
    Detecta Order Blocks válidos segundo regra Luciano:
    1. OB = último candle de alta antes de queda impulsiva (bearish OB)
             último candle de baixa antes de subida impulsiva (bullish OB)
    2. OBRIGATÓRIO: candle seguinte ao OB deve conter FVG
    3. Zona = CORPO do candle OB apenas
    """
    obs = []
    if len(df) < 10:
        return obs

    for i in range(5, len(df) - 3):
        candle     = df.iloc[i]
        proximo    = df.iloc[i + 1]
        posterior  = df.iloc[i + 2] if i + 2 < len(df) else None

        # FVG no candle seguinte?
        if posterior is not None:
            fvg_bull = proximo["low"] > candle["high"]   # gap entre fechamento e próximo
            fvg_bear = proximo["high"] < candle["low"]
        else:
            fvg_bull = fvg_bear = False

        # OB Bullish: candle de baixa + próximo candle com FVG bullish
        if (candle["close"] < candle["open"] and    # candle de baixa
            proximo["close"] > proximo["open"] and  # próximo é de alta
            (fvg_bull or proximo["high"] > candle["high"] * 1.002)):  # movimento impulsivo
            obs.append({
                "tipo": "BULLISH",
                "nivel_alto": candle["open"],
                "nivel_baixo": candle["close"],
                "idx": i,
                "timestamp": df.index[i] if hasattr(df.index[i], 'strftime') else str(df.index[i]),
                "fvg": fvg_bull,
                "valido": True,
            })

        # OB Bearish: candle de alta + próximo candle com FVG bearish
        if (candle["close"] > candle["open"] and
            proximo["close"] < proximo["open"] and
            (fvg_bear or proximo["low"] < candle["low"] * 0.998)):
            obs.append({
                "tipo": "BEARISH",
                "nivel_alto": candle["close"],
                "nivel_baixo": candle["open"],
                "idx": i,
                "timestamp": df.index[i] if hasattr(df.index[i], 'strftime') else str(df.index[i]),
                "fvg": fvg_bear,
                "valido": True,
            })

    # Retorna os 3 mais recentes de cada tipo
    bull_obs = [o for o in obs if o["tipo"] == "BULLISH"][-3:]
    bear_obs = [o for o in obs if o["tipo"] == "BEARISH"][-3:]
    return bull_obs + bear_obs


# ─── MOTOR PRINCIPAL DE ANÁLISE ──────────────────────────────

def analisar_ativo_completo(symbol: str) -> dict:
    """
    Executa a Metodologia Agregada completa em um ativo.
    Retorna score, bias, confluências, setup e níveis de trade.
    """
    resultado = {
        "symbol": symbol,
        "preco_atual": 0.0,
        "bias": "NEUTRO",
        "score": 0,
        "confluencias": 0,
        "dados": {},
        "trade": None,
        "erro": None,
    }

    try:
        # ── Preço atual ───────────────────────────────────────
        preco = buscar_preco_atual(symbol)
        resultado["preco_atual"] = preco

        # ── Top-Down: 1D → 1H → 15M ──────────────────────────
        df_1d  = buscar_ohlcv(symbol, "1d",  90)
        df_1h  = buscar_ohlcv(symbol, "1h",  200)
        df_15m = buscar_ohlcv(symbol, "15m", 200)

        if df_1d.empty or df_1h.empty:
            resultado["erro"] = "Sem dados OHLCV disponíveis"
            return resultado

        # ── Estrutura de mercado ──────────────────────────────
        est_1d  = identificar_estrutura_mercado(df_1d)
        est_1h  = identificar_estrutura_mercado(df_1h)
        est_15m = identificar_estrutura_mercado(df_15m) if not df_15m.empty else {"bias": "NEUTRO"}

        # ── Wyckoff + Tuk Tuk ─────────────────────────────────
        wyckoff_1h = detectar_wyckoff(df_1h)
        wyckoff_15m = detectar_wyckoff(df_15m) if not df_15m.empty else {"fase": "—", "tuk_tuk": False}

        # ── Volume Profile Ancorado (último mês no 1D) ────────
        vp_1d = calcular_volume_profile(df_1d, bins=30)
        vp_1h = calcular_volume_profile(df_1h.iloc[-100:], bins=25)

        # ── VWAP Ancorado ─────────────────────────────────────
        # Ancora no início da semana (últimos 5 dias no 1H)
        anchor_semanal = max(0, len(df_1h) - 5 * 24)
        vwap_semanal = calcular_vwap_ancorado(df_1h, anchor_semanal)
        vwap_atual = vwap_semanal.iloc[-1] if not vwap_semanal.empty else 0

        # Posição do preço vs VWAP
        if preco > 0 and vwap_atual > 0:
            pct_vs_vwap = (preco - vwap_atual) / vwap_atual * 100
            if pct_vs_vwap > 0.5:
                vwap_bias = "BULLISH"
                vwap_desc = f"Preço {pct_vs_vwap:.2f}% acima da VWAP semanal"
            elif pct_vs_vwap < -0.5:
                vwap_bias = "BEARISH"
                vwap_desc = f"Preço {abs(pct_vs_vwap):.2f}% abaixo da VWAP semanal"
            else:
                vwap_bias = "NEUTRO"
                vwap_desc = f"Preço na VWAP semanal ({pct_vs_vwap:+.2f}%)"
        else:
            vwap_bias = "NEUTRO"; vwap_desc = "VWAP indisponível"; pct_vs_vwap = 0

        # ── OBV ───────────────────────────────────────────────
        obv_1d = sinal_obv(df_1d, 20)
        obv_1h = sinal_obv(df_1h, 30)

        # ── Volume contexto ───────────────────────────────────
        vol_ctx = analisar_volume_contexto(df_1h, 20)

        # ── Order Blocks ──────────────────────────────────────
        obs_1h = detectar_order_blocks(df_1h)
        obs_bull = [o for o in obs_1h if o["tipo"] == "BULLISH"]
        obs_bear = [o for o in obs_1h if o["tipo"] == "BEARISH"]

        # ── Sentimento ────────────────────────────────────────
        funding = buscar_funding_rate(symbol)
        oi      = buscar_open_interest(symbol)
        ls      = buscar_long_short_ratio(symbol)
        cvd     = buscar_cvd(symbol)
        sentimento = calcular_sentimento_geral(funding, oi, ls, cvd)

        # ── SCORE DE CONFLUÊNCIAS ─────────────────────────────
        # Cada item vale 1 ponto (0-9 possíveis)
        pontos_bull = 0
        pontos_bear = 0
        detalhes_bull = []
        detalhes_bear = []

        # 1. Estrutura 1D
        if est_1d["bias"] == "BULLISH":
            pontos_bull += 1; detalhes_bull.append("Estrutura 1D bullish (HH/HL)")
        elif est_1d["bias"] == "BEARISH":
            pontos_bear += 1; detalhes_bear.append("Estrutura 1D bearish (LH/LL)")

        # 2. Estrutura 1H
        if est_1h["bias"] == "BULLISH":
            pontos_bull += 1; detalhes_bull.append("Estrutura 1H bullish (BOS)")
        elif est_1h["bias"] == "BEARISH":
            pontos_bear += 1; detalhes_bear.append("Estrutura 1H bearish (BOS)")

        # 3. Wyckoff / Tuk Tuk
        if "ACUMULAÇÃO" in wyckoff_1h["fase"] or wyckoff_1h["spring"]:
            pontos_bull += 1; detalhes_bull.append(f"Wyckoff: {wyckoff_1h['fase']}")
        elif "DISTRIBUIÇÃO" in wyckoff_1h["fase"] or wyckoff_1h["upthrust"]:
            pontos_bear += 1; detalhes_bear.append(f"Wyckoff: {wyckoff_1h['fase']}")

        # 4. OBV 1D
        if obv_1d.get("bias") == "BULLISH":
            pontos_bull += 1; detalhes_bull.append(f"OBV 1D: {obv_1d['sinal']}")
        elif obv_1d.get("bias") == "BEARISH":
            pontos_bear += 1; detalhes_bear.append(f"OBV 1D: {obv_1d['sinal']}")

        # 5. VWAP
        if vwap_bias == "BULLISH":
            pontos_bull += 1; detalhes_bull.append(vwap_desc)
        elif vwap_bias == "BEARISH":
            pontos_bear += 1; detalhes_bear.append(vwap_desc)

        # 6. POC (Volume Profile)
        poc = vp_1h.get("poc", 0)
        if poc > 0 and preco > 0:
            if preco > poc * 1.002:
                pontos_bull += 1; detalhes_bull.append(f"Preço acima do POC (${poc:,.2f})")
            elif preco < poc * 0.998:
                pontos_bear += 1; detalhes_bear.append(f"Preço abaixo do POC (${poc:,.2f})")

        # 7. Sentimento
        s_score = sentimento["score"]
        if s_score >= 65:
            pontos_bull += 1; detalhes_bull.append(f"Sentimento bullish (score {s_score})")
        elif s_score <= 35:
            pontos_bear += 1; detalhes_bear.append(f"Sentimento bearish (score {s_score})")

        # 8. Funding contrarian
        f_taxa = funding.get("taxa", 0)
        if f_taxa < -0.01:
            pontos_bull += 1; detalhes_bull.append(f"Funding negativo ({f_taxa:.4f}%) — bullish")
        elif f_taxa > 0.05:
            pontos_bear += 1; detalhes_bear.append(f"Funding extremo ({f_taxa:.4f}%) — bearish")

        # 9. CVD
        if cvd.get("bias") == "BULLISH":
            pontos_bull += 1; detalhes_bull.append(f"CVD: {cvd['sinal']}")
        elif cvd.get("bias") == "BEARISH":
            pontos_bear += 1; detalhes_bear.append(f"CVD: {cvd['sinal']}")

        # ── Bias final ────────────────────────────────────────
        if pontos_bull >= CONFLUENCIAS_MIN and pontos_bull > pontos_bear:
            bias_final = "BULLISH"
            confluencias = pontos_bull
            detalhes = detalhes_bull
        elif pontos_bear >= CONFLUENCIAS_MIN and pontos_bear > pontos_bull:
            bias_final = "BEARISH"
            confluencias = pontos_bear
            detalhes = detalhes_bear
        else:
            bias_final = "NEUTRO"
            confluencias = max(pontos_bull, pontos_bear)
            detalhes = []

        score = int((confluencias / 9) * 100)

        # ── Calcular trade (se confluências suficientes) ──────
        trade = None
        if confluencias >= CONFLUENCIAS_MIN and preco > 0:
            trade = calcular_trade(
                symbol=symbol,
                preco=preco,
                bias=bias_final,
                vp_1h=vp_1h,
                vwap=vwap_atual,
                wyckoff=wyckoff_1h,
                obs_bull=obs_bull,
                obs_bear=obs_bear,
            )

        # ── Montar resultado final ────────────────────────────
        resultado.update({
            "bias": bias_final,
            "score": score,
            "confluencias": confluencias,
            "pontos_bull": pontos_bull,
            "pontos_bear": pontos_bear,
            "detalhes": detalhes,
            "trade": trade,
            "dados": {
                "estrutura": {"1d": est_1d, "1h": est_1h, "15m": est_15m},
                "wyckoff": {"1h": wyckoff_1h, "15m": wyckoff_15m},
                "obv": {"1d": obv_1d, "1h": obv_1h},
                "vwap": {"valor": vwap_atual, "bias": vwap_bias, "descricao": vwap_desc, "pct": pct_vs_vwap},
                "volume_profile": {"1d": vp_1d, "1h": vp_1h},
                "volume": vol_ctx,
                "sentimento": {
                    "funding": funding,
                    "oi": oi,
                    "ls_ratio": ls,
                    "cvd": cvd,
                    "geral": sentimento,
                },
                "order_blocks": {"bull": obs_bull, "bear": obs_bear},
            },
        })

    except Exception as e:
        resultado["erro"] = str(e)

    return resultado


# ─── CALCULADORA DE TRADE ────────────────────────────────────

def calcular_trade(symbol, preco, bias, vp_1h, vwap, wyckoff, obs_bull, obs_bear) -> dict:
    """
    Calcula níveis de entrada, stop, A1/A2/A3 e gestão de risco.
    Regra inegociável: A1=1R, A2=2R, A3=3R. NUNCA ajustar por nível técnico.
    """
    poc  = vp_1h.get("poc", 0)
    vah  = vp_1h.get("vah", 0)
    val  = vp_1h.get("val", 0)

    if bias == "BULLISH":
        # Entrada: próximo suporte (POC, VAL, ou VWAP)
        candidatos_entrada = [x for x in [poc, val, vwap] if x > 0 and x <= preco * 1.005]
        if candidatos_entrada:
            entrada = max(candidatos_entrada) * 0.998  # ligeiramente abaixo
        else:
            entrada = preco   # entrada a mercado

        # Stop: abaixo do nível técnico mais forte abaixo da entrada
        candidatos_stop = [x for x in [val * 0.99, vwap * 0.99, wyckoff.get("range_low", 0)]
                          if x > 0 and x < entrada]
        stop = min(candidatos_stop) * 0.995 if candidatos_stop else entrada * 0.975

        # OB bull mais próximo como suporte adicional
        if obs_bull:
            ob_mais_perto = min(obs_bull, key=lambda o: abs(o["nivel_alto"] - entrada))
            stop = min(stop, ob_mais_perto["nivel_baixo"] * 0.995)

    else:  # BEARISH
        candidatos_entrada = [x for x in [poc, vah, vwap] if x > 0 and x >= preco * 0.995]
        if candidatos_entrada:
            entrada = min(candidatos_entrada) * 1.002
        else:
            entrada = preco

        candidatos_stop = [x for x in [vah * 1.01, vwap * 1.01, wyckoff.get("range_high", 0)]
                          if x > 0 and x > entrada]
        stop = max(candidatos_stop) * 1.005 if candidatos_stop else entrada * 1.025

        if obs_bear:
            ob_mais_perto = min(obs_bear, key=lambda o: abs(o["nivel_baixo"] - entrada))
            stop = max(stop, ob_mais_perto["nivel_alto"] * 1.005)

    if entrada <= 0 or stop <= 0:
        return None

    # Risco unitário
    risco = abs(entrada - stop)
    if risco < entrada * 0.001:  # risco < 0.1% — inválido
        return None

    # ─ Alvos pela fórmula INEGOCIÁVEL (entrada ± N × risco) ─
    if bias == "BULLISH":
        a1 = entrada + risco * A1_RR
        a2 = entrada + risco * A2_RR
        a3 = entrada + risco * A3_RR
    else:
        a1 = entrada - risco * A1_RR
        a2 = entrada - risco * A2_RR
        a3 = entrada - risco * A3_RR

    # ─ R/R check ─────────────────────────────────────────────
    rr = abs(a1 - entrada) / risco
    if rr < 0.95:   # R/R < 1:1
        return None

    # ─ Gestão de risco (cálculos obrigatórios) ───────────────
    stop_pct = abs(risco / entrada) * 100
    alavancagem_max_real = min(ALAVANCAGEM_MAX, int(5 / stop_pct * 100) if stop_pct > 0 else ALAVANCAGEM_MAX)
    alavancagem_35 = max(1, int(alavancagem_max_real * 0.35))
    margem = MARGEM_PADRAO_USD
    notional = margem * alavancagem_35
    quantidade = notional / entrada if entrada > 0 else 0

    # Trailing stop
    if "BTC" in symbol.upper():
        trailing = TRAILING_BTC
    elif "XAG" in symbol.upper():
        trailing = TRAILING_XAGUSD
    else:
        trailing = TRAILING_DEFAULT

    # Cenários de P&L
    risco_unit = quantidade * risco  # risco total em USD

    def cenario(alvo, pct_real):
        ganho_bruto = quantidade * abs(alvo - entrada) * pct_real
        return {
            "alvo": alvo,
            "ganho": ganho_bruto,
            "pct_margem": (ganho_bruto / margem) * 100,
        }

    c_a1 = cenario(a1, A1_REAL)
    c_a2 = cenario(a2, A2_REAL - A1_REAL)
    c_a3 = cenario(a3, A3_REAL - A2_REAL)
    c_ts = cenario(a3, TS_REAL)

    win_total = c_a1["ganho"] + c_a2["ganho"] + c_a3["ganho"] + c_ts["ganho"]
    stop_loss = risco_unit * 1.0  # 100% da posição

    return {
        "bias": bias,
        "entrada": round(entrada, 6),
        "stop": round(stop, 6),
        "a1": round(a1, 6),
        "a2": round(a2, 6),
        "a3": round(a3, 6),
        "risco_unit": round(risco, 6),
        "stop_pct": round(stop_pct, 3),
        "alavancagem_max": alavancagem_max_real,
        "alavancagem_35": alavancagem_35,
        "margem": margem,
        "notional": round(notional, 2),
        "quantidade": round(quantidade, 6),
        "trailing_pct": trailing * 100,
        "cenarios": {
            "stop":  {"perda": -round(stop_loss, 2), "pct": -round((stop_loss / margem) * 100, 1)},
            "a1":    {"ganho": round(c_a1["ganho"], 2), "pct": round(c_a1["pct_margem"], 1)},
            "a2":    {"ganho": round(c_a2["ganho"], 2), "pct": round(c_a2["pct_margem"], 1)},
            "a3":    {"ganho": round(c_a3["ganho"], 2), "pct": round(c_a3["pct_margem"], 1)},
            "ts":    {"ganho": round(c_ts["ganho"], 2), "pct": round(c_ts["pct_margem"], 1)},
            "win_total": round(win_total, 2),
            "win_pct":   round((win_total / margem) * 100, 1),
        },
        "entrada_distante": abs(entrada - buscar_preco_atual(symbol)) / max(buscar_preco_atual(symbol), 1) > 0.015,
        "comando_bot": f"/trade {symbol} {bias} {entrada:.4f} {stop:.4f} {a1:.4f} {a2:.4f} {a3:.4f} 1H 15M",
    }
