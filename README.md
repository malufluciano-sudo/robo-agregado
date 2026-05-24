# 🦈 ROBÔ AGREGADO v1.0
## Metodologia Exclusiva — Luciano

Dashboard de análise técnica completa baseado na **Metodologia Agregada**:
SMC · Wyckoff · Tuk Tuk · Volume Profile Ancorado · VWAP Ancorado · OBV · Sentimento de Mercado

---

## 🚀 COMO RODAR (Windows)

### Opção 1 — Duplo clique (mais fácil)
```
Duplo clique em START.bat
```

### Opção 2 — Terminal
```cmd
pip install -r requirements.txt
python -m streamlit run app.py
```

Acesse: **http://localhost:8501**

---

## 📊 O QUE O ROBÔ FAZ

### Análise Top-Down Automática (1D → 1H → 15M)
- Estrutura de mercado: HH/HL, LH/LL, CHoCH, BOS
- Wyckoff: Acumulação, Markup, Distribuição, Markdown
- Tuk Tuk de Wyckoff: detecção de compressão (baixa amplitude + volume crescente)
- Spring e Upthrust automáticos

### SMC (Smart Money Concepts)
- Order Blocks Bullish e Bearish (regra IL + FVG obrigatória)
- Internal Liquidity mapeada
- IDM (Inducement)

### Volume Profile Ancorado
- POC, VAH, VAL calculados por faixa de preço real
- HVN e LVN identificados
- Gráfico horizontal de distribuição de volume

### VWAP Ancorado
- Ancora automática na semana atual
- Posição do preço vs VWAP em %
- Bias derivado do desequilíbrio

### OBV (On Balance Volume)
- Cálculo em 1D e 1H
- Identificação de acumulação vs distribuição
- Divergências bullish/bearish vs preço

### Sentimento de Mercado
| Indicador | Fonte |
|-----------|-------|
| Funding Rate (OI-Weighted) | Coinalyze + Binance |
| Aggregated Open Interest | Coinalyze + Binance |
| Long/Short Ratio (Accounts) | Binance Futures |
| CVD Aggregated | Binance Futures Taker |

### Gestão de Risco (Inegociável)
- Stop: técnico (POC, VWAP, OB, range)
- A1 = 1:1 → realizar 25% + trailing stop
- A2 = 2:1 → realizar 50%
- A3 = 3:1 → realizar 80%
- Trailing Stop: 10% restante
- Cenários de P&L automáticos

### Checklist Universal Wyckoff (10 critérios)
Verifica automaticamente antes de propor qualquer trade.

---

## 🗂️ ESTRUTURA DOS ARQUIVOS

```
RoboAgregado/
├── app.py                    ← Dashboard principal (Streamlit)
├── requirements.txt          ← Dependências Python
├── START.bat                 ← Inicializador Windows
├── README.md
└── utils/
    ├── config.py             ← Configurações e constantes
    ├── market_data.py        ← OHLCV, VWAP, OBV, Volume Profile
    ├── sentiment.py          ← Funding, OI, L/S, CVD
    └── analise_engine.py     ← Motor da Metodologia Agregada
```

---

## ⚙️ CONFIGURAÇÕES

Edite `utils/config.py` para ajustar:
- `MARGEM_PADRAO_USD` — margem padrão (default $200)
- `ALAVANCAGEM_MAX` — alavancagem máxima permitida
- `CONFLUENCIAS_MIN` — mínimo para gerar trade (default 3)
- `COINALYZE_API_KEY` — sua chave Coinalyze

---

## 📡 FONTES DE DADOS

- **Preço / OHLCV:** Binance Futures (fallback: Binance Spot)
- **Sentimento:** Coinalyze API (OI-Weighted Funding, Aggregated OI)
- **L/S Ratio:** Binance Futures
- **CVD:** Binance Futures Taker Volume

Dados públicos — não requer API key para preço.
Coinalyze key incluída por padrão.

---

## ⚠️ DISCLAIMER

Este robô é uma **ferramenta de análise**, não de execução automática.
Todas as decisões de trade são de responsabilidade exclusiva do trader.
