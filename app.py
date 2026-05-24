# -*- coding: utf-8 -*-
import streamlit as st

st.set_page_config(page_title="Robo Agregado", page_icon="📊", layout="wide")

st.title("🦈 Robô Agregado v1.6")
st.success("App carregado com sucesso!")
st.write("Digite um ativo na barra lateral para começar.")

with st.sidebar:
    symbol = st.text_input("Ativo", value="BTCUSDT")
    if st.button("Analisar"):
        with st.spinner("Buscando preço..."):
            try:
                import requests
                r = requests.get(f"https://fapi.binance.com/fapi/v1/ticker/price?symbol={symbol}", timeout=5)
                if r.status_code == 200:
                    preco = float(r.json()["price"])
                    st.metric(symbol, f"${preco:,.2f}")
                else:
                    st.error("Ativo não encontrado nos futuros. Tentando spot...")
                    r2 = requests.get(f"https://api.binance.com/api/v3/ticker/price?symbol={symbol}", timeout=5)
                    if r2.status_code == 200:
                        preco = float(r2.json()["price"])
                        st.metric(symbol, f"${preco:,.2f}")
            except Exception as e:
                st.error(f"Erro: {e}")
