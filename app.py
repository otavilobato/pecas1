import streamlit as st
import pandas as pd
import hashlib
from datetime import datetime, timedelta
import io
import requests
import base64
import os

# =========================
# CONFIGURAÇÃO
# =========================
EXCEL_URL = "https://github.com/otavilobato/pecas1/raw/refs/heads/main/SALDO_PECAS.xlsx"
EXCEL_API = "https://api.github.com/repos/otavilobato/pecas1/contents/SALDO_PECAS.xlsx"

USUARIOS = {
    "olobato": hashlib.sha256("9410".encode()).hexdigest(),
    "gladeira": hashlib.sha256("0002".encode()).hexdigest()
}

# =========================
# FUNÇÕES AUXILIARES
# =========================
@st.cache_data(ttl=60)
def carregar_dados():
    github_token = st.secrets.get("GITHUB_TOKEN", os.getenv("GITHUB_TOKEN"))
    headers = {}
    if github_token:
        headers["Authorization"] = f"token {github_token}"
    try:
        r = requests.get(EXCEL_URL, headers=headers)
        if r.status_code == 200:
            df = pd.read_excel(io.BytesIO(r.content), sheet_name="PRINCIPAL")
            return df
        else:
            st.error(f"❌ Falha ao carregar planilha (código {r.status_code}).")
            return pd.DataFrame()
    except Exception as e:
        st.error(f"Erro ao tentar carregar: {e}")
        return pd.DataFrame()

def salvar_dados(df):
    try:
        github_token = st.secrets.get("GITHUB_TOKEN", os.getenv("GITHUB_TOKEN"))
        if not github_token:
            st.error("❌ Token do GitHub não configurado.")
            return None
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, sheet_name="PRINCIPAL", index=False)
        content = output.getvalue()
        encoded_content = base64.b64encode(content).decode("utf-8")
        headers = {"Authorization": f"token {github_token}"}
        resp_get = requests.get(EXCEL_API, headers=headers)
        sha = resp_get.json().get("sha") if resp_get.status_code == 200 else None
        commit_message = f"Atualização automática via Streamlit ({datetime.now().strftime('%d/%m/%Y %H:%M')})"
        data = {"message": commit_message, "content": encoded_content, "sha": sha}
        resp_put = requests.put(EXCEL_API, headers=headers, json=data)
        if resp_put.status_code in (200, 201):
            st.success("✅ Alterações salvas no GitHub com sucesso!")
        else:
            st.error(f"Erro ao salvar no GitHub: {resp_put.status_code}")
            st.text(resp_put.text)
    except Exception as e:
        st.error(f"Erro ao tentar salvar: {e}")
        return None

def parse_data_possivel(valor):
    if isinstance(valor, datetime):
        return valor
    if pd.isna(valor):
        return None
    try:
        if isinstance(valor, (int, float)):
            return datetime.fromordinal(datetime(1900, 1, 1).toordinal() + int(valor) - 2)
        for fmt in ("%d/%m/%Y", "%d/%m/%y", "%Y-%m-%d"):
            try:
                return datetime.strptime(str(valor).strip(), fmt)
            except ValueError:
                continue
        return None
    except:
        return None

# =========================
# LOGIN
# =========================
def tentar_login():
    usuario = st.session_state.get("usuario_input", "")
    senha = st.session_state.get("senha_input", "")
    if not usuario or not senha:
        return
    senha_hash = hashlib.sha256(senha.encode()).hexdigest()
    if usuario in USUARIOS and USUARIOS[usuario] == senha_hash:
        st.session_state["usuario"] = usuario
        st.success("Login realizado com sucesso!")
    else:
        st.error("Usuário ou senha incorretos.")

def login_page():
    st.title("🔐 Login")
    st.text_input("Usuário", key="usuario_input")
    st.text_input("Senha", type="password", key="senha_input", on_change=tentar_login)
    st.button("Entrar", on_click=tentar_login)

# =========================
# CADASTRO DE PEÇAS
# =========================
def pagina_cadastro():
    st.subheader("🧩 Cadastro de Peças")
    df = carregar_dados()

    uf = st.selectbox("UF", ["", "AM","BA","CE","DF","GO","MA","MG","PA","PE","RJ","TO"])
    fru = st.text_input("FRU (7 caracteres)")
    sub1 = st.text_input("SUB1")
    sub2 = st.text_input("SUB2")
    sub3 = st.text_input("SUB3")
    descricao = st.text_input("Descrição")
    maquinas = st.text_input("Máquinas")
    cliente = st.text_input("Clientes")
    serial = st.text_input("Serial")
    data_contrato = st.date_input("Data do Contrato")
    sla = st.text_input("SLA")

    if st.button("💾 Salvar Peça"):
        if not uf or not fru or not serial or not data_contrato:
            st.error("Campos UF, FRU, SERIAL e Data são obrigatórios.")
        elif len(fru) != 7:
            st.error("FRU deve ter 7 caracteres.")
        else:
            nova_linha = {
                "UF": uf.upper(),
                "FRU": fru.upper(),
                "SUB1": sub1.upper(),
                "SUB2": sub2.upper(),
                "SUB3": sub3.upper(),
                "DESCRICAO": descricao.upper(),
                "MAQUINAS": maquinas.upper(),
                "CLIENTE": f"{cliente.upper()} - ({serial.upper()} {data_contrato.strftime('%d/%m/%y')}_{sla.upper()}) - {uf.upper()}",
                "DATA_FIM": data_contrato.strftime("%d/%m/%y"),
                "SLA": sla.upper(),
                "DATA_VERIFICACAO": datetime.now().strftime("%d/%m/%y"),
                "STATUS": "DENTRO"
            }
            df = pd.concat([df, pd.DataFrame([nova_linha])], ignore_index=True)
            salvar_dados(df)

# =========================
# RENOVAÇÃO DE CONTRATO
# =========================
def pagina_renovacao():
    st.subheader("🔄 Renovação de Contrato")
    df = carregar_dados()
    hoje = datetime.today()
    proximos_7dias = hoje + timedelta(days=7)

    df["DATA_FIM_DT"] = df["DATA_FIM"].apply(parse_data_possivel)
    vencidas = df[df["DATA_FIM_DT"].notna() & (df["DATA_FIM_DT"].dt.date < hoje.date())]

    if vencidas.empty:
        st.info("Nenhum contrato vencido.")
        return

    vencidas_mostrar = vencidas.drop(columns=["DATA_FIM_DT", "STATUS", "DATA_VERIFICACAO"], errors='ignore')
    st.dataframe(vencidas_mostrar)

    linha = st.number_input(
        "Linha a renovar ou excluir (número da tabela acima)",
        min_value=0,
        max_value=len(df)-1,
        step=1
    )
    nova_data = st.date_input("Nova Data")
    novo_sla = st.text_input("Novo SLA (opcional)")

    col1, col2 = st.columns(2)
    with col1:
        if st.button("Atualizar Contrato"):
            try:
                idx = int(linha)
                df.loc[idx, "DATA_FIM"] = nova_data.strftime("%d/%m/%y")
                df.loc[idx, "STATUS"] = "DENTRO"
                if novo_sla:
                    df.loc[idx, "SLA"] = novo_sla.upper()
                salvar_dados(df)
                st.success("Contrato atualizado com sucesso!")
            except Exception as e:
                st.error(f"Erro ao atualizar: {e}")
    with col2:
        if st.button("❌ Excluir Contrato"):
            try:
                idx = int(linha)
                df = df.drop(idx).reset_index(drop=True)
                salvar_dados(df)
                st.success("Contrato excluído com sucesso!")
            except Exception as e:
                st.error(f"Erro ao excluir: {e}")

# =========================
# VISUALIZAR TODOS
# =========================
def pagina_visualizar_tudo():
    st.subheader("📋 Todos os registros")
    df = carregar_dados()
    if df.empty:
        st.info("Nenhum registro encontrado.")
        return

    hoje = datetime.today()
    proximos_7dias = hoje + timedelta(days=7)
    df["DATA_FIM_DT"] = df["DATA_FIM"].apply(parse_data_possivel)

    df_mostrar = df.drop(columns=["DATA_FIM_DT", "STATUS", "DATA_VERIFICACAO"], errors='ignore')
    st.dataframe(df_mostrar)

    formato = st.radio("Escolha o formato do relatório", ["CSV", "TXT"])
    if formato == "CSV":
        st.download_button(
            "⬇️ Baixar Relatório CSV",
            df_mostrar.to_csv(index=False).encode("utf-8"),
            "relatorio.csv",
            "text/csv"
        )
    else:
        st.download_button(
            "⬇️ Baixar Relatório TXT",
            df_mostrar.to_csv(index=False, sep="\t").encode("utf-8"),
            "relatorio.txt",
            "text/plain"
        )

# =========================
# RELATÓRIO
# =========================
def pagina_relatorio():
    st.subheader("📄 Relatório de Peças Vencidas")
    df = carregar_dados()
    hoje = datetime.today()
    df["DATA_FIM_DT"] = df["DATA_FIM"].apply(parse_data_possivel)
    vencidas = df[df["DATA_FIM_DT"].notna() & (df["DATA_FIM_DT"].dt.date < hoje.date())]

    if vencidas.empty:
        st.info("Nenhum contrato vencido.")
        return

    vencidas_mostrar = vencidas.drop(columns=["DATA_FIM_DT", "STATUS", "DATA_VERIFICACAO"], errors='ignore')
    st.dataframe(vencidas_mostrar)

    formato_relatorio = st.selectbox("Formato do relatório", ["CSV", "TXT"])
    if st.button("⬇️ Baixar Relatório"):
        if formato_relatorio == "CSV":
            st.download_button(
                "⬇️ Baixar CSV",
                vencidas_mostrar.to_csv(index=False).encode("utf-8"),
                "relatorio.csv",
                "text/csv"
            )
        else:
            st.download_button(
                "⬇️ Baixar TXT",
                vencidas_mostrar.to_csv(index=False, sep="\t").encode("utf-8"),
                "relatorio.txt",
                "text/plain"
            )

# =========================
# MENU PRINCIPAL
# =========================
def main_page():
    st.sidebar.title(f"👋 Olá, {st.session_state['usuario']}")
    escolha = st.sidebar.radio("Menu", ["Cadastro", "Renovação", "Relatório", "Visualizar Tudo", "Sair"])

    if escolha == "Cadastro":
        pagina_cadastro()
    elif escolha == "Renovação":
        pagina_renovacao()
    elif escolha == "Relatório":
        pagina_relatorio()
    elif escolha == "Visualizar Tudo":
        pagina_visualizar_tudo()
    elif escolha == "Sair":
        st.session_state.clear()
        st.info("Você saiu. Atualize a página para fazer login novamente.")

# =========================
# APP
# =========================
st.set_page_config(page_title="Controle de Peças", layout="centered")

if "usuario" not in st.session_state:
    login_page()
else:
    main_page()
