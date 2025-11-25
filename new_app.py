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

def gerar_relatorio_screen():
    st.title("📄 Gerar Relatório de Peças Vencidas")

    df = github_read_excel()
    if df is None:
        return

    hoje = datetime.now().date()

    vencidos = df[df["DATA_FIM"].apply(lambda x: x < str(hoje))]

    if len(vencidos) == 0:
        st.info("Nenhuma peça vencida para gerar relatório.")
        return

    # Gera o conteúdo do TXT
    linhas = []
    for _, row in vencidos.iterrows():
        linha = f"{row['UF']} | {row['FRU']} | {row['CLIENTE']} | {row['DATA_FIM']}"
        linhas.append(linha)

    txt_content = "\n".join(linhas)

    st.download_button(
        "📥 Baixar Relatório TXT",
        txt_content,
        file_name="pecas_vencidas.txt",
        mime="text/plain"
    )
def logout():
    st.session_state["logged"] = False
    st.rerun()


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
def renovar_contrato_screen():
    st.title("🛠 Renovar Contrato")

    df = github_read_excel()
    if df is None:
        return

    # converter DATA_FIM criptografada → texto
    df["DATA_FIM_DEC"] = df["DATA_FIM"].apply(lambda x: x)

    hoje = datetime.now().date()
    vencidos = df[df["DATA_FIM_DEC"] < str(hoje)]

    st.subheader("Peças vencidas")
    st.dataframe(vencidos)

    if len(vencidos) == 0:
        st.info("Nenhuma peça vencida encontrada.")
        return

    # Selecionar qual linha editar
    idx = st.selectbox(
        "Selecione um registro para renovação",
        vencidos.index.tolist()
    )

    nova_data = st.date_input("Nova data de validade")

    if st.button("Salvar Renovação"):
        df.at[idx, "DATA_FIM"] = hash_value(str(nova_data))

        if github_write_excel(df):
            st.success("✔ Contrato renovado com sucesso!")
        else:
            st.error("Erro ao atualizar dados.")

# =========================
# TELA DE CADASTRO
# =========================

def cadastro_screen():

    st.title("📄 Cadastro de Peças (Criptografado)")

    UF = st.selectbox("UF", ["AM", "PA", "RR", "RO", "AC", "AP"])
    FRU = st.text_input("FRU (7 caracteres obrigatórios)")
    SUB1 = st.text_input("SUB1 (opcional, 7 caracteres)")
    SUB2 = st.text_input("SUB2 (opcional, 7 caracteres)")
    SUB3 = st.text_input("SUB3 (opcional, 7 caracteres)")
    DESCRICAO = st.text_input("DESCRIÇÃO")
    MAQUINAS = st.text_input("MÁQUINAS")
    CLIENTE_ORIG = st.text_input("Cliente")
    SERIAL = st.text_input("Serial")
    DATA_FIM = st.date_input("Data Fim")
    SLA = st.text_input("SLA")

    if st.button("Salvar"):

        # ==============================
        # CAIXA ALTA AUTOMÁTICA
        # ==============================
        FRU = FRU.upper()
        SUB1 = SUB1.upper()
        SUB2 = SUB2.upper()
        SUB3 = SUB3.upper()
        DESCRICAO = DESCRICAO.upper()
        MAQUINAS = MAQUINAS.upper()
        CLIENTE_ORIG = CLIENTE_ORIG.upper()
        SERIAL = SERIAL.upper()
        SLA = SLA.upper()

        CLIENTE_FINAL = f"{CLIENTE_ORIG}({SERIAL}_{DATA_FIM}_{SLA}){UF}"

        # ==============================
        # VALIDAÇÕES
        # ==============================

        # FRU obrigatório e 7 caracteres
        if len(FRU) != 7:
            st.error("❌ O campo FRU deve ter exatamente 7 caracteres.")
            return

        # SUB1/2/3 opcionais mas, se preenchidos, 7 chars
        for nome, valor in [("SUB1", SUB1), ("SUB2", SUB2), ("SUB3", SUB3)]:
            if valor != "" and len(valor) != 7:
                st.error(f"❌ O campo {nome} deve ter exatamente 7 caracteres quando preenchido.")
                return

        # Campos obrigatórios
        campos_obrigatorios = {
            "DESCRIÇÃO": DESCRICAO,
            "MÁQUINAS": MAQUINAS,
            "Cliente": CLIENTE_ORIG,
            "Serial": SERIAL,
            "SLA": SLA
        }

        for nome, valor in campos_obrigatorios.items():
            if valor == "":
                st.error(f"❌ O campo {nome} é obrigatório.")
                return

        # ==============================
        # CARREGAR EXCEL
        # ==============================

        df = github_read_excel()
        if df is None:
            return

        # ==============================
        # MONTAR REGISTRO
        # ==============================

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

        # ==============================
        # SALVAR NO GITHUB
        # ==============================

        if github_write_excel(df):
            st.success("✔ Registro salvo com sucesso!")
        else:
            st.error("❌ Erro ao salvar no GitHub.")

# =========================
# MENU LATERAL
# =========================

def sidebar_menu():
    menu = st.sidebar.radio(
        "📌 Navegação",
        ["Cadastro", "Renovar Contrato", "Gerar Relatório", "Sair"]
    )
    return menu

# =========================
# ÁREA LOGADA
# =========================

if "logged" not in st.session_state:
    st.session_state["logged"] = False

if not st.session_state["logged"]:
    login_screen()

else:
    opcao = sidebar_menu()

    if opcao == "Cadastro":
        cadastro_screen()

    elif opcao == "Renovar Contrato":
        renovar_contrato_screen()

    elif opcao == "Gerar Relatório":
        gerar_relatorio_screen()

    elif opcao == "Sair":
        logout()



