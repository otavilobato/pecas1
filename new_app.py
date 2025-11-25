# new_app.py
import streamlit as st
import pandas as pd
import base64
import requests
from io import BytesIO
from datetime import datetime, date

# --------------------------
# CONFIGURAÇÃO DA PÁGINA
# --------------------------
st.set_page_config(page_title="SALDO_PECAS - Sistema", layout="wide")

# --------------------------
# HELPERS / GITHUB I/O
# --------------------------
def github_read_excel():
    """Lê o arquivo Excel do GitHub (branch main). Retorna DataFrame ou None."""
    try:
        token = st.secrets["github"]["token"]
        repo = st.secrets["github"]["repo"]
        file_path = st.secrets["github"]["file_path"]
    except Exception:
        st.error("Chaves do GitHub ausentes em st.secrets['github']. Verifique seu secrets.toml.")
        return None

    url = f"https://raw.githubusercontent.com/{repo}/main/{file_path}"
    headers = {"Authorization": f"token {token}"}
    r = requests.get(url, headers=headers)
    if r.status_code != 200:
        st.error(f"Erro ao carregar arquivo no GitHub (status {r.status_code}). Verifique repo/token/file_path.")
        return None
    try:
        df = pd.read_excel(BytesIO(r.content))
    except Exception as e:
        # se o arquivo existir mas estiver vazio / inválido, retornamos DataFrame vazio
        st.warning(f"Atenção: não foi possível ler o Excel como esperado ({e}). Será usado DataFrame vazio.")
        df = pd.DataFrame()
    return df

def github_write_excel(df, commit_message="Atualização via Streamlit"):
    """Grava o DataFrame como Excel no GitHub (substitui o arquivo)."""
    try:
        token = st.secrets["github"]["token"]
        repo = st.secrets["github"]["repo"]
        file_path = st.secrets["github"]["file_path"]
    except Exception:
        st.error("Chaves do GitHub ausentes em st.secrets['github']. Verifique seu secrets.toml.")
        return False

    get_url = f"https://api.github.com/repos/{repo}/contents/{file_path}"
    get_r = requests.get(get_url, headers={"Authorization": f"token {token}"})
    if get_r.status_code not in (200,):
        st.error(f"Erro ao obter info do arquivo no GitHub (status {get_r.status_code}).")
        return False
    sha = get_r.json().get("sha")
    # converter df para excel bytes
    buf = BytesIO()
    try:
        df.to_excel(buf, index=False)
    except Exception as e:
        st.error(f"Erro ao gerar excel em memória: {e}")
        return False
    content_b64 = base64.b64encode(buf.getvalue()).decode()
    data = {"message": commit_message, "content": content_b64, "sha": sha}
    put_r = requests.put(get_url, json=data, headers={"Authorization": f"token {token}"})
    if put_r.status_code in (200, 201):
        return True
    else:
        st.error(f"Erro ao gravar arquivo no GitHub: {put_r.status_code} - {put_r.text}")
        return False

def parse_date_safe(val):
    """Converte valores em date, se possível. Retorna date ou None."""
    if pd.isna(val) or val is None:
        return None
    if isinstance(val, date):
        return val
    try:
        return pd.to_datetime(val).date()
    except Exception:
        return None

# --------------------------
# AUTENTICAÇÃO / LOGIN
# --------------------------
def login_screen():
    st.title("🔐 Login")
    st.write("Entre com seu usuário e senha.")
    username = st.text_input("Usuário", key="login_user")
    password = st.text_input("Senha", type="password", key="login_pass")
    if st.button("Entrar", key="login_btn"):
        users = st.secrets.get("auth", {})
        if username in users and users[username] == password:
            st.session_state["logged"] = True
            st.session_state["username"] = username
            st.success(f"Bem-vindo, {username}!")
            st.experimental_rerun()
        else:
            st.error("Usuário ou senha incorretos.")

def logout():
    st.session_state["logged"] = False
    st.session_state["username"] = None
    st.experimental_rerun()

# --------------------------
# TELAS DO APLICATIVO
# --------------------------
def cadastro_screen():
    st.header("📄 Cadastro de Peças")

    # Linha 1: FRU | SUB1 | SUB2 | SUB3
    col1, col2, col3, col4 = st.columns(4)
    FRU = col1.text_input("FRU (7 caracteres)*", key="fru").upper().strip()
    SUB1 = col2.text_input("SUB1 (opcional, 7 chars)", key="sub1").upper().strip()
    SUB2 = col3.text_input("SUB2 (opcional, 7 chars)", key="sub2").upper().strip()
    SUB3 = col4.text_input("SUB3 (opcional, 7 chars)", key="sub3").upper().strip()

    # Linha 2: CLIENTE | SERIAL
    col5, col6 = st.columns(2)
    CLIENTE_raw = col5.text_input("CLIENTE *", key="cliente").upper().strip()
    SERIAL = col6.text_input("SERIAL *", key="serial").upper().strip()

    # Linha 3: DATA_FIM | UF
    col7, col8 = st.columns(2)
    DATA_FIM = col7.date_input("DATA FIM *", key="datafim")
    UF = col8.text_input("UF *", key="uf").upper().strip()

    # Linha 4: DESCRICAO | MAQUINAS
    col9, col10 = st.columns(2)
    DESCRICAO = col9.text_input("DESCRIÇÃO *", key="descricao").upper().strip()
    MAQUINAS = col10.text_input("MÁQUINAS *", key="maquinas").upper().strip()

    # Linha 5: SLA
    SLA = st.text_input("SLA *", key="sla").upper().strip()

    # Montagem CLIENTE final
    CLIENTE_FINAL = ""
    if CLIENTE_raw and SERIAL and SLA and UF:
        CLIENTE_FINAL = f"{CLIENTE_raw}({SERIAL}_{DATA_FIM}_{SLA}){UF}"

    st.markdown("**Preview CLIENTE (como será gravado):**")
    st.code(CLIENTE_FINAL if CLIENTE_FINAL else "(preencha CLIENTE, SERIAL, SLA, UF)")

    # Validações
    erros = []
    if not FRU or len(FRU) != 7:
        erros.append("FRU é obrigatório e deve ter exatamente 7 caracteres.")
    for nome, val in [("SUB1", SUB1), ("SUB2", SUB2), ("SUB3", SUB3)]:
        if val and len(val) != 7:
            erros.append(f"{nome} quando preenchido deve ter exatamente 7 caracteres.")
    obrigatorios = {
        "CLIENTE": CLIENTE_raw,
        "SERIAL": SERIAL,
        "DATA_FIM": DATA_FIM,
        "UF": UF,
        "DESCRIÇÃO": DESCRICAO,
        "MÁQUINAS": MAQUINAS,
        "SLA": SLA
    }
    for k, v in obrigatorios.items():
        if v is None or (isinstance(v, str) and v.strip() == ""):
            erros.append(f"{k} é obrigatório.")

    if erros:
        st.error("⚠️ Corrija os itens antes de salvar:\n\n- " + "\n- ".join(erros))
        return

    if st.button("Salvar Registro", key="btn_salvar"):
        df = github_read_excel()
        if df is None:
            return

        # garantir colunas existentes, se o arquivo estiver vazio cria as colunas
        row = {
            "UF": UF,
            "FRU": FRU,
            "SUB1": SUB1,
            "SUB2": SUB2,
            "SUB3": SUB3,
            "DESCRICAO": DESCRICAO,
            "MAQUINAS": MAQUINAS,
            "CLIENTE": CLIENTE_FINAL,
            "DATA_FIM": str(DATA_FIM),
            "SLA": SLA,
            "Cadastrado_por": st.session_state.get("username", "")
        }

        try:
            if df.empty:
                df = pd.DataFrame([row])
            else:
                df = pd.concat([df, pd.DataFrame([row])], ignore_index=True)
        except Exception:
            df = pd.DataFrame([row])

        ok = github_write_excel(df, commit_message=f"Cadastro por {st.session_state.get('username','')}")
        if ok:
            st.success("✔ Registro salvo com sucesso.")
        else:
            st.error("❌ Erro ao salvar no GitHub.")

def renovar_contrato_screen():
    st.header("🛠 Renovar Contrato - Peças Vencidas")

    df = github_read_excel()
    if df is None:
        return

    if "DATA_FIM" not in df.columns:
        st.info("Arquivo não contém coluna DATA_FIM.")
        return

    df["_DATA_FIM_parsed"] = df["DATA_FIM"].apply(parse_date_safe)
    hoje = date.today()
    vencidos = df[df["_DATA_FIM_parsed"].apply(lambda d: d is not None and d < hoje)].copy()

    if vencidos.empty:
        st.info("Nenhuma peça vencida encontrada.")
        return

    st.subheader(f"Peças vencidas ({len(vencidos)})")
    st.dataframe(vencidos.drop(columns=["_DATA_FIM_parsed"], errors="ignore"))

    escolha = st.selectbox("Selecione índice (linha) para renovar", options=vencidos.index.tolist(), key="sel_renovar")
    registro = df.loc[escolha]
    st.markdown("**Registro selecionado:**")
    st.write(registro.drop(labels=["_DATA_FIM_parsed"], errors="ignore"))

    nova_data = st.date_input("Nova DATA_FIM", value=hoje, key=f"nova_data_{escolha}")

    if st.button("Salvar Renovação", key=f"btn_renovar_{escolha}"):
        df.at[escolha, "DATA_FIM"] = str(nova_data)
        ok = github_write_excel(df, commit_message=f"Renovação por {st.session_state.get('username','')}")
        if ok:
            st.success("✔ Renovação salva com sucesso.")
        else:
            st.error("❌ Erro ao salvar renovação.")

def gerar_relatorio_screen():
    st.header("📄 Gerar Relatório de Peças Vencidas (TXT)")

    df = github_read_excel()
    if df is None:
        return

    if "DATA_FIM" not in df.columns:
        st.info("Arquivo não contém coluna DATA_FIM.")
        return

    df["_DATA_FIM_parsed"] = df["DATA_FIM"].apply(parse_date_safe)
    hoje = date.today()
    vencidos = df[df["_DATA_FIM_parsed"].apply(lambda d: d is not None and d < hoje)].copy()

    if vencidos.empty:
        st.info("Nenhuma peça vencida para gerar relatório.")
        return

    linhas = []
    for i, row in vencidos.iterrows():
        linhas.append(f"{i} | {row.get('UF','')} | {row.get('FRU','')} | {row.get('CLIENTE','')} | {row.get('DATA_FIM','')}")

    txt = "\n".join(linhas)
    st.text_area("Preview do relatório", txt, height=200)
    st.download_button("📥 Baixar relatório (pecas_vencidas.txt)", txt, file_name="pecas_vencidas.txt", mime="text/plain")

# --------------------------
# SIDEBAR / NAVEGAÇÃO
# --------------------------
def sidebar_menu():
    st.sidebar.markdown(f"**Usuário:** {st.session_state.get('username','')}")
    return st.sidebar.radio("📌 Navegação", ["Cadastro", "Renovar Contrato", "Gerar Relatório", "Sair"])

# --------------------------
# MAIN
# --------------------------
def main():
    if "logged" not in st.session_state:
        st.session_state["logged"] = False
        st.session_state["username"] = None

    if not st.session_state["logged"]:
        login_screen()
        return

    opcao = sidebar_menu()

    if opcao == "Cadastro":
        cadastro_screen()
    elif opcao == "Renovar Contrato":
        renovar_contrato_screen()
    elif opcao == "Gerar Relatório":
        gerar_relatorio_screen()
    elif opcao == "Sair":
        if st.button("Confirmar logout"):
            logout()

if __name__ == "__main__":
    main()
