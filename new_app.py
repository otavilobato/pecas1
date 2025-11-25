import streamlit as st
import pandas as pd
import hashlib
import base64
import requests
from io import BytesIO
from datetime import datetime

# =========================
# FUNÇÕES AUXILIARES
# =========================

def hash_value(value: str) -> str:
    hashed = hashlib.sha256(value.encode()).digest()
    return base64.b64encode(hashed).decode()

def github_read_excel():
    token = st.secrets["github"]["token"]
    repo = st.secrets["github"]["repo"]
    file_path = st.secrets["github"]["file_path"]

    url = f"https://raw.githubusercontent.com/{repo}/main/{file_path}"
    headers = {"Authorization": f"token {token}"}

    r = requests.get(url, headers=headers)

    if r.status_code != 200:
        st.error("Erro ao carregar arquivo no GitHub.")
        return None

    return pd.read_excel(BytesIO(r.content))

def github_write_excel(df):
    token = st.secrets["github"]["token"]
    repo = st.secrets["github"]["repo"]
    file_path = st.secrets["github"]["file_path"]

    get_url = f"https://api.github.com/repos/{repo}/contents/{file_path}"

    get_r = requests.get(get_url, headers={"Authorization": f"token {token}"})
    sha = get_r.json().get("sha")

    excel_buffer = BytesIO()
    df.to_excel(excel_buffer, index=False)
    excel_b64 = base64.b64encode(excel_buffer.getvalue()).decode()

    data = {
        "message": "Atualização via Streamlit",
        "content": excel_b64,
        "sha": sha
    }

    put_r = requests.put(get_url, json=data, headers={"Authorization": f"token {token}"})

    return put_r.status_code in (200, 201)

# =========================
# TELA DE LOGIN
# =========================

def login_screen():
    st.title("🔐 Login")

    username = st.text_input("Usuário")
    password = st.text_input("Senha", type="password")

    if st.button("Entrar"):
        users = st.secrets["auth"]

        if username in users and users[username] == password:
            st.session_state["logged"] = True
            st.success("✔ Login bem-sucedido!")
            st.rerun()
        else:
            st.error("Usuário ou senha incorretos.")

# =========================
# TELA DE CADASTRO
# =========================

def cadastro_screen():

    st.title("📄 Cadastro de Peças")

    UF = st.selectbox("UF", ["AM", "PA", "RR", "RO", "AC", "AP"])
    FRU = st.text_input("FRU")
    SUB1 = st.text_input("SUB1")
    SUB2 = st.text_input("SUB2")
    SUB3 = st.text_input("SUB3")
    DESCRICAO = st.text_input("DESCRIÇÃO")
    MAQUINAS = st.text_input("MÁQUINAS")
    CLIENTE_ORIG = st.text_input("Cliente")
    SERIAL = st.text_input("Serial")
    DATA_FIM = st.date_input("Data Fim")
    SLA = st.text_input("SLA")

    CLIENTE_FINAL = f"{CLIENTE_ORIG}({SERIAL}_{DATA_FIM}_{SLA}){UF}"

    if st.button("Salvar"):

        df = github_read_excel()
        if df is None:
            return

        new_row = {
            "UF": hash_value(UF),
            "FRU": hash_value(FRU),
            "SUB1": hash_value(SUB1),
            "SUB2": hash_value(SUB2),
            "SUB3": hash_value(SUB3),
            "DESCRICAO": hash_value(DESCRICAO),
            "MAQUINAS": hash_value(MAQUINAS),
            "CLIENTE": hash_value(CLIENTE_FINAL),
            "DATA_FIM": hash_value(str(DATA_FIM)),
            "SLA": hash_value(SLA)
        }

        df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)

        if github_write_excel(df):
            st.success("✔ Registro salvo com sucesso!")
        else:
            st.error("Erro ao salvar no GitHub.")

# =========================
# GERENCIADOR PRINCIPAL
# =========================

if "logged" not in st.session_state:
    st.session_state["logged"] = False

if not st.session_state["logged"]:
    login_screen()
else:
    cadastro_screen()

