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
# FORMULÁRIO DE CADASTRO
# =========================
elif menu == "Cadastro":
    st.header("Cadastro de Peças")

    col_fru, col_s1, col_s2, col_s3 = st.columns(4)

    fru = col_fru.text_input("FRU (7 caracteres)*").upper()
    sub1 = col_s1.text_input("SUB 1 (7 caracteres - opcional)").upper()
    sub2 = col_s2.text_input("SUB 2 (7 caracteres - opcional)").upper()
    sub3 = col_s3.text_input("SUB 3 (7 caracteres - opcional)").upper()

    col_a, col_b = st.columns(2)
    cliente_base = col_a.text_input("CLIENTE *").upper()
    serial = col_b.text_input("SERIAL *").upper()

    col_c, col_d = st.columns(2)
    data_fim_sla = col_c.date_input("DATA FIM SLA *")
    uf = col_d.text_input("UF *").upper()

    # Montagem automática do campo CLIENTE FINAL  
    cliente = f"{cliente_base}(SERIAL_{serial}_{data_fim_sla}){uf}"

    st.write("Cliente gerado automaticamente:")
    st.code(cliente)

    # Validações
    erros = []

    if fru.strip() == "" or len(fru) != 7:
        erros.append("FRU deve ter exatamente 7 caracteres.")

    for nome, campo in [("SUB 1", sub1), ("SUB 2", sub2), ("SUB 3", sub3)]:
        if campo.strip() != "" and len(campo) != 7:
            erros.append(f"{nome} deve ter exatamente 7 caracteres quando preenchido.")

    if cliente_base.strip() == "":
        erros.append("CLIENTE é obrigatório.")
    if serial.strip() == "":
        erros.append("SERIAL é obrigatório.")
    if uf.strip() == "":
        erros.append("UF é obrigatório.")

    if erros:
        st.error("⚠ Erros encontrados:\n" + "\n".join(erros))
    else:
        if st.button("Cadastrar"):
            nova_linha = {
                "FRU": fru,
                "SUB1": sub1,
                "SUB2": sub2,
                "SUB3": sub3,
                "CLIENTE": cliente,
                "SERIAL": serial,
                "DATA_FIM_SLA": str(data_fim_sla),
                "UF": uf
            }

            df_saldo = df_saldo.append(nova_linha, ignore_index=True)

            st.success("Peça cadastrada com sucesso!")

            # Salvar no GitHub
            save_to_github(df_saldo)

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





