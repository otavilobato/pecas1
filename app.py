import streamlit as st
import pandas as pd
import io
import requests
from datetime import datetime

# 🔧 URL da planilha hospedada no GitHub
GITHUB_FILE_URL = "https://github.com/otavilobato/pecas1/raw/refs/heads/main/SALDO_PECAS.xlsx"

# 🔑 Função para carregar token do GitHub com segurança
def get_github_token():
    try:
        return st.secrets["GITHUB_TOKEN"]
    except Exception:
        return None

# 📥 Função para carregar a planilha
def carregar_dados():
    try:
        r = requests.get(GITHUB_FILE_URL)
        if r.status_code == 200:
            try:
                df = pd.read_excel(io.BytesIO(r.content))
                if df.empty:
                    st.warning("⚠️ A planilha está vazia, será criado um modelo padrão.")
                    df = pd.DataFrame(columns=[
                        "UF","FRU","SUB1","SUB2","SUB3","DESCRICAO",
                        "MAQUINAS","CLIENTES","DATA_FIM","SLA",
                        "DATA_VERIFICACAO","STATUS"
                    ])
                return df
            except Exception as e:
                st.error(f"Erro ao ler planilha: {e}")
                return pd.DataFrame()
        else:
            st.error("❌ Não foi possível carregar a planilha do GitHub.")
            return pd.DataFrame()
    except Exception as e:
        st.error(f"Erro ao carregar planilha: {e}")
        return pd.DataFrame()

# 💾 Função para salvar os dados de volta no GitHub
def salvar_dados(df):
    github_token = get_github_token()
    if not github_token:
        st.error("❌ Token do GitHub não configurado. Adicione em Secrets ou variável de ambiente.")
        return

    try:
        # Gera o conteúdo Excel em memória
        output = io.BytesIO()
        df.to_excel(output, index=False)
        output.seek(0)

        # Faz upload via API do GitHub
        repo = "otavilobato/pecas1"
        path = "SALDO_PECAS.xlsx"
        url = f"https://api.github.com/repos/{repo}/contents/{path}"

        # Obtém hash SHA do arquivo existente (necessário para PUT)
        r_get = requests.get(url, headers={"Authorization": f"token {github_token}"})
        sha = r_get.json().get("sha")

        data = {
            "message": "Atualização automática via Streamlit",
            "content": output.getvalue().decode("latin1").encode("base64").decode(),
            "sha": sha
        }

        r_put = requests.put(url, headers={
            "Authorization": f"token {github_token}"
        }, json=data)

        if r_put.status_code in [200, 201]:
            st.success("✅ Planilha atualizada com sucesso no GitHub!")
        else:
            st.error(f"Erro ao salvar no GitHub: {r_put.text}")
    except Exception as e:
        st.error(f"Erro ao salvar dados: {e}")

# 🧾 Página de cadastro
def pagina_cadastro(df):
    st.header("📋 Cadastro de Peças / Contratos")

    uf = st.text_input("UF")
    fru = st.text_input("FRU")
    sub1 = st.text_input("SUB1")
    sub2 = st.text_input("SUB2")
    sub3 = st.text_input("SUB3")
    descricao = st.text_input("Descrição")
    maquinas = st.text_input("Máquinas")
    clientes = st.text_input("Clientes")
    data_contrato = st.date_input("Data Fim de Contrato")
    sla = st.text_input("SLA")
    data_verificacao = datetime.now().strftime("%d/%m/%y")
    status = st.selectbox("Status", ["ATIVO", "INATIVO", "VENCIDO"])

    if st.button("Salvar Registro"):
        novo = pd.DataFrame([{
            "UF": uf,
            "FRU": fru,
            "SUB1": sub1,
            "SUB2": sub2,
            "SUB3": sub3,
            "DESCRICAO": descricao,
            "MAQUINAS": maquinas,
            "CLIENTES": clientes,
            "DATA_FIM": data_contrato.strftime("%d/%m/%y"),
            "SLA": sla,
            "DATA_VERIFICACAO": data_verificacao,
            "STATUS": status
        }])

        df = pd.concat([df, novo], ignore_index=True)
        salvar_dados(df)

# 📊 Página de relatório
def pagina_relatorio(df):
    st.header("📈 Relatório de Contratos")

    if df.empty:
        st.warning("⚠️ Nenhum dado disponível para exibir.")
        return

    # Conversão de datas
    def parse_data_possivel(valor):
        try:
            return pd.to_datetime(valor, format="%d/%m/%y", errors="coerce")
        except:
            return None

    df["DATA_FIM"] = df["DATA_FIM"].apply(parse_data_possivel)
    hoje = datetime.now()

    vencidos = df[df["DATA_FIM"].notna() & (df["DATA_FIM"].dt.date < hoje.date())]
    ativos = df[df["STATUS"] == "ATIVO"]

    st.subheader("📅 Contratos Vencidos")
    st.dataframe(vencidos)

    st.subheader("🟢 Contratos Ativos")
    st.dataframe(ativos)

# 🧭 Função principal
def main():
    st.title("🔧 Sistema de Controle de Peças e Contratos")

    df = carregar_dados()

    menu = st.sidebar.radio("Navegação", ["Cadastro", "Relatório"])

    if menu == "Cadastro":
        pagina_cadastro(df)
    elif menu == "Relatório":
        pagina_relatorio(df)

# 🚀 Iniciar o app
if __name__ == "__main__":
    main()
