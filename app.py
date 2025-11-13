import streamlit as st
import pandas as pd
from io import BytesIO
from datetime import datetime
import requests

# --- CONFIGURAÇÕES ---
GITHUB_RAW_URL = "https://github.com/otavilobato/pecas1/raw/refs/heads/main/SALDO_PECAS.xlsx"

# Função para carregar planilha
def carregar_planilha():
    try:
        response = requests.get(GITHUB_RAW_URL)
        if response.status_code == 200:
            return pd.read_excel(BytesIO(response.content))
        else:
            st.error("❌ Não foi possível carregar a planilha do GitHub.")
            return pd.DataFrame()
    except Exception as e:
        st.warning("⚠️ Erro ao tentar carregar a planilha: " + str(e))
        return pd.DataFrame()

# Função auxiliar para converter datas
def parse_data_possivel(valor):
    if isinstance(valor, datetime):
        return valor
    try:
        return pd.to_datetime(valor, errors='coerce')
    except:
        return None

# Página principal
def main_page():
    st.title("📦 Controle de Peças")
    df = carregar_planilha()

    # Se a planilha estiver vazia ou sem colunas válidas
    if df.empty or len(df.columns) == 0:
        st.info("🆕 Nenhum dado encontrado. Cadastre a primeira peça abaixo.")
        pagina_cadastro(df)
    else:
        menu = st.sidebar.radio("Escolha uma opção", ["Cadastro", "Relatório"])
        if menu == "Cadastro":
            pagina_cadastro(df)
        elif menu == "Relatório":
            pagina_relatorio(df)

# Página de cadastro
def pagina_cadastro(df):
    st.subheader("📝 Cadastrar nova peça")

    col1, col2 = st.columns(2)
    with col1:
        nome = st.text_input("Nome da peça")
        codigo = st.text_input("Código")
    with col2:
        data_inicio = st.date_input("Data Início", datetime.now())
        data_fim = st.date_input("Data Fim", datetime.now())

    if st.button("Salvar"):
        novo = pd.DataFrame([{
            "NOME": nome,
            "CÓDIGO": codigo,
            "DATA_INÍCIO": data_inicio,
            "DATA_FIM": data_fim
        }])

        if df.empty:
            df = novo
        else:
            df = pd.concat([df, novo], ignore_index=True)

        st.success("✅ Cadastro realizado com sucesso!")
        salvar_planilha(df)

# Página de relatório
def pagina_relatorio(df):
    st.subheader("📊 Relatório de Peças")

    if df.empty:
        st.info("Não há dados para exibir. Cadastre algo primeiro.")
        return

    hoje = datetime.now()

    # Verifica se coluna existe antes de usar
    if "DATA_FIM" not in df.columns:
        st.warning("A coluna 'DATA_FIM' não foi encontrada. Verifique a planilha.")
        return

    # Verifica vencidas
    df["DATA_FIM"] = df["DATA_FIM"].apply(parse_data_possivel)
    vencidas = df[df["DATA_FIM"].notna() & (df["DATA_FIM"].dt.date < hoje.date())]

    st.write("🔴 Peças vencidas:")
    st.dataframe(vencidas)

    st.write("📅 Todas as peças:")
    st.dataframe(df)

# Função para salvar (necessário configurar token no ambiente seguro)
def salvar_planilha(df):
    try:
        output = BytesIO()
        df.to_excel(output, index=False)
        output.seek(0)
        st.download_button("⬇️ Baixar cópia atualizada", data=output, file_name="SALDO_PECAS.xlsx")
        st.info("⚙️ Para salvar automaticamente no GitHub, configure um token pessoal no ambiente seguro do Streamlit Cloud.")
    except Exception as e:
        st.error(f"Erro ao salvar a planilha: {e}")

# --- EXECUÇÃO ---
if __name__ == "__main__":
    main_page()
