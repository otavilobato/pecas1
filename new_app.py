# app.py
import streamlit as st
import pandas as pd
import base64
import requests
from io import BytesIO
from datetime import datetime, date

# --------------------------
# Config / Helpers
# --------------------------

def github_read_excel():
    """Lê o arquivo Excel do GitHub (branch main)."""
    token = st.secrets["github"]["token"]
    repo = st.secrets["github"]["repo"]
    file_path = st.secrets["github"]["file_path"]
    url = f"https://raw.githubusercontent.com/{repo}/main/{file_path}"
    headers = {"Authorization": f"token {token}"}
    r = requests.get(url, headers=headers)
    if r.status_code != 200:
        st.error(f"Erro ao carregar arquivo no GitHub (status {r.status_code}). Verifique secrets e o arquivo.")
        return None
    try:
        df = pd.read_excel(BytesIO(r.content))
    except Exception as e:
        st.error(f"Erro ao ler excel: {e}")
        return None
    return df

def github_write_excel(df, commit_message="Atualização via Streamlit"):
    """Grava o DataFrame como Excel no GitHub (substitui o arquivo)."""
    token = st.secrets["github"]["token"]
    repo = st.secrets["github"]["repo"]
    file_path = st.secrets["github"]["file_path"]
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
    """Tenta converter val (str / datetime / date) para date; se falhar retorna None."""
    if pd.isna(val):
        return None
    if isinstance(val, date):
        return val
    try:
        return pd.to_datetime(val).date()
    except Exception:
        return None

# --------------------------
# Telas / Funcionalidades
# --------------------------

def login_screen():
    st.title("🔐 Login")
    st.write("Faça login para acessar o sistema.")
    username = st.text_input("Usuário", key="login_user")
    password = st.text_input("Senha", type="password", key="login_pass")
    if st.button("Entrar", key="login_button"):
        users = st.secrets["auth"]
        if username in users and users[username] == password:
            st.session_state["logged"] = True
            st.session_state["username"] = username
            st.success(f"Bem-vindo, {username}!")
            st.experimental_rerun()
        else:
            st.error("Usuário ou senha inválidos.")

def logout():
    st.session_state["logged"] = False
    st.session_state["username"] = None
    st.experimental_rerun()

def sidebar_menu():
    return st.sidebar.radio("📌 Navegação", ["Cadastro", "Renovar Contrato", "Gerar Relatório", "Sair"])

def cadastro_screen():
    st.header("📄 Cadastro de Peças")

    # FRU + SUB1 + SUB2 + SUB3 na mesma linha
    col_fru, col_s1, col_s2, col_s3 = st.columns(4)
    FRU = col_fru.text_input("FRU (7 caracteres)*", key="in_fru").upper().strip()
    SUB1 = col_s1.text_input("SUB1 (opcional, 7 chars)", key="in_sub1").upper().strip()
    SUB2 = col_s2.text_input("SUB2 (opcional, 7 chars)", key="in_sub2").upper().strip()
    SUB3 = col_s3.text_input("SUB3 (opcional, 7 chars)", key="in_sub3").upper().strip()

    # Demais campos de 2 em 2
    col_a, col_b = st.columns(2)
    CLIENTE_raw = col_a.text_input("CLIENTE *", key="in_cliente").upper().strip()
    SERIAL = col_b.text_input("SERIAL *", key="in_serial").upper().strip()

    col_c, col_d = st.columns(2)
    DATA_FIM = col_c.date_input("DATA FIM *", key="in_datafim")
    UF = col_d.text_input("UF *", key="in_uf").upper().strip()

    col_e, col_f = st.columns(2)
    DESCRICAO = col_e.text_input("DESCRIÇÃO *", key="in_desc").upper().strip()
    MAQUINAS = col_f.text_input("MÁQUINAS *", key="in_maquinas").upper().strip()

    # SLA e outro (SLA e pode ser numérico)
    col_g, col_h = st.columns(2)
    SLA = col_g.text_input("SLA *", key="in_sla").upper().strip()
    # espaço para futuro campo
    # outro_campo = col_h.text_input("Outro (opcional)")

    st.write("")  # espaço

    # pré-montagem do CLIENTE final conforme regra
    CLIENTE_FINAL = f"{CLIENTE_raw}({SERIAL}_{DATA_FIM}_{SLA}){UF}"

    st.markdown("**Preview CLIENTE (será salvo assim):**")
    st.code(CLIENTE_FINAL)

    # validações
    erros = []
    if FRU == "" or len(FRU) != 7:
        erros.append("FRU é obrigatório e deve ter exatamente 7 caracteres.")
    for nome, val in [("SUB1", SUB1), ("SUB2", SUB2), ("SUB3", SUB3)]:
        if val != "" and len(val) != 7:
            erros.append(f"{nome} quando preenchido deve ter exatamente 7 caracteres.")
    # campos obrigatórios
    obrigatorios = {"CLIENTE": CLIENTE_raw, "SERIAL": SERIAL, "DATA_FIM": DATA_FIM, "UF": UF, "DESCRIÇÃO": DESCRICAO, "MÁQUINAS": MAQUINAS, "SLA": SLA}
    for k,v in obrigatorios.items():
        if v == "" or v is None:
            erros.append(f"{k} é obrigatório.")

    if erros:
        st.error("⚠️ Corrija os itens abaixo antes de salvar:\n\n- " + "\n- ".join(erros))
    else:
        if st.button("Salvar Registro", key="btn_salvar"):
            # carregar planilha do github
            df = github_read_excel()
            if df is None:
                return

            # preparar linha (salva em texto, CAIXA ALTA)
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

            # acrescenta e salva
            try:
                df = pd.concat([df, pd.DataFrame([row])], ignore_index=True)
            except Exception:
                # se o arquivo estiver vazio ou sem colunas, cria novo DF com as colunas
                df = pd.DataFrame([row])

            ok = github_write_excel(df, commit_message=f"Cadastro por {st.session_state.get('username','')}")
            if ok:
                st.success("✔ Registro salvo com sucesso.")
            else:
                st.error("❌ Erro ao salvar o registro no GitHub.")

def renovar_contrato_screen():
    st.header("🛠 Renovar Contrato - Peças Vencidas")

    df = github_read_excel()
    if df is None:
        return

    # garantir coluna DATA_FIM existe
    if "DATA_FIM" not in df.columns:
        st.info("O arquivo não contém coluna DATA_FIM.")
        return

    # parse de datas
    df["_DATA_FIM_parsed"] = df["DATA_FIM"].apply(parse_date_safe)
    hoje = date.today()
    vencidos = df[df["_DATA_FIM_parsed"].apply(lambda d: d is not None and d < hoje)].copy()

    if vencidos.empty:
        st.info("Nenhuma peça vencida encontrada.")
        return

    st.subheader(f"Peças vencidas ({len(vencidos)})")
    # mostrar tabela resumida
    st.dataframe(vencidos.drop(columns=["_DATA_FIM_parsed"]))

    # selecionar índice (usar index real do df)
    escolha = st.selectbox("Selecione índice (linha) para renovar", options=vencidos.index.tolist())
    registro = df.loc[escolha]

    st.markdown("**Registro selecionado:**")
    st.write(registro.drop(labels=["_DATA_FIM_parsed"], errors="ignore"))

    nova_data = st.date_input("Nova DATA_FIM", value=hoje, key=f"nova_data_{escolha}")

    if st.button("Salvar Renovação", key=f"btn_renovar_{escolha}"):
        df.at[escolha, "DATA_FIM"] = str(nova_data)
        ok = github_write_excel(df, commit_message=f"Renovação DATA_FIM por {st.session_state.get('username','')}")
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
        st.info("O arquivo não contém coluna DATA_FIM.")
        return

    df["_DATA_FIM_parsed"] = df["DATA_FIM"].apply(parse_date_safe)
    hoje = date.today()
    vencidos = df[df["_DATA_FIM_parsed"].apply(lambda d: d is not None and d < hoje)].copy()

    if vencidos.empty:
        st.info("Nenhuma peça vencida para gerar relatório.")
        return

    # construir linhas do relatório (personalize o formato)
    linhas = []
    for i, row in vencidos.iterrows():
        linhas.append(f"{i} | {row.get('UF','')} | {row.get('FRU','')} | {row.get('CLIENTE','')} | {row.get('DATA_FIM','')}")

    txt = "\n".join(linhas)
    st.text_area("Preview do relatório", txt, height=200)

    st.download_button("📥 Baixar relatório (pecas_vencidas.txt)", txt, file_name="pecas_vencidas.txt", mime="text/plain")

# --------------------------
# Main
# --------------------------

def main():
    st.set_page_config(page_title="SALDO_PECAS - Sistema", layout="wide")
    if "logged" not in st.session_state:
        st.session_state["logged"] = False
        st.session_state["username"] = None

    if not st.session_state["logged"]:
        login_screen()
        return

    # área lateral com usuário e menu
    st.sidebar.markdown(f"**Usuário:** {st.session_state.get('username','')}")
    opcao = sidebar_menu()

    if opcao == "Cadastro":
        cadastro_screen()
    elif opcao == "Renovar Contrato":
        renovar_contrato_screen()
    elif opcao == "Gerar Relatório":
        gerar_relatorio_screen()
    elif opcao == "Sair":
        if st.sidebar.button("Confirmar logout"):
            logout()

if __name__ == "__main__":
    main()
