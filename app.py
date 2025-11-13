import streamlit as st
import pandas as pd

# Configuração da página para celular
st.set_page_config(page_title="Visualizador Excel", layout="wide")

st.title("📊 Visualizador de Tabela Excel")

# Carregar arquivo Excel
try:
    df = pd.read_excel("dados.xlsx")
    st.success("Arquivo carregado com sucesso!")
except FileNotFoundError:
    st.error("Arquivo 'dados.xlsx' não encontrado. Suba o arquivo no repositório.")

# Mostrar tabela completa
st.subheader("Tabela Completa")
st.dataframe(df)

# Filtro simples
st.subheader("🔍 Filtrar por coluna")
colunas = df.columns.tolist()
coluna_escolhida = st.selectbox("Escolha a coluna para filtrar:", colunas)
valor_filtro = st.text_input("Digite o valor para buscar:")

if valor_filtro:
    resultado = df[df[coluna_escolhida].astype(str).str.contains(valor_filtro, case=False)]
    st.write(f"Resultados encontrados: {len(resultado)}")
    st.dataframe(resultado)
