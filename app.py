import streamlit as st
import pandas as pd
import hashlib
from datetime import datetime
import io
import requests
import base64
import os

# =========================
# CONFIGURAÇÃO
# =========================
# Substitua pelos seus dados reais
REPO = "otavilobato/pecas1"
ARQUIVO = "SALDO_PECAS.xlsx"

EXCEL_URL = f"https://github.com/{REPO}/raw/refs/heads/main/{ARQUIVO}"
EXCEL_API = f"https://api.github.com/repos/{REPO}/contents/{ARQUIVO}"
EXCEL_ARQUIVO = ARQUIVO

USUARIOS = {
    "olobato": hashlib.sha256("9410".encode()).hexdigest(),
    "gladeira": hashlib.sha256("0002".encode()).hexdigest()
}

# =========================
# FUNÇÕES AUXILIARES
# =========================
@st.cache_data(ttl=60)
def carregar_dados():
    """
    Carrega a planilha Excel do GitHub.
    Funciona para repositórios públicos e privados (usando token).
    """
    github_token = st.secrets.get("GITHUB_TOKEN", os.getenv("GITHUB_TOKEN"))
    headers = {}
    if github_token:
        headers["Authorization"] = f"token {github_token}"

    try:
        r = requests.get(EXCEL_URL, headers=headers)
        if r.status_code == 200:
            return pd.read_excel(io.BytesIO(r.content), sheet_name="PRINCIPAL")
        else:
            st.error(f"❌ Não foi possível carregar a planilha ({r.status_code}).")
            st.text(r.text)
            return pd.DataFrame()
    except Exception as e:
        st.error(f"Erro ao tentar carregar: {e}")
        return pd.DataFrame()

def salvar_dados(df):
    """
    Salva os dados de volta no GitHub, usando o token de acesso pessoal.
    """
    try:
        github_token = st.secrets.get("GITHUB_TOKEN", os.getenv("GITHUB_TOKEN"))
        if not github_token:
            st.error("❌ Token do GitHub não configurado. Adicione em Secrets ou variável de ambiente.")
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
    for fmt in ("%d/%m/%Y", "%d/%m/%y"):
        try:
            return datetime.strptime(str(valor), fmt)
        except:
            continue
    return None

# =========================
# LOGIN
# =========================
def login_page():
    st.title("🔐 Login")
    usuario = st.text_input("Usuário")
    senha = st.text_input("Senha", type="password")
    if st.button("Entrar"):
        senha_hash = hashlib.sha256(senha.encode()).hexdigest()
        if usuario in USUARIOS and USUARIOS[usuario] == senha_hash:
            st.session_state["usuario"] = usuario
            st.success("Login realizado com sucesso!")
            st.rerun()
        else:
            st.error("Usuário ou senha incorretos.")

# =========================
# CADASTRO DE PEÇAS
# =========================
def pagina_cadastro():
    st.subheader("🧩 Cadastro de Peças")
    df = carregar_dados()
    if df.empty:
        st.warning("⚠️ A planilha está vazia ou não foi carregada.")
        return

    uf = st.selectbox("UF", ["", "AM","BA","CE","DF","GO","MA","MG","PA","PE","RJ","TO"])
    fru = st.text_input("FRU (7 caracteres)")
    sub1 = st.text_input("SUB1")
    sub2 = st.text_input("SUB2")
    sub3 = st.text_input("SUB3")
    descricao = st.text_input("Descrição")
    maquinas = st.text_input("Máquinas")
    clientes = st.text_input("Clientes")
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
                "UF": uf,
                "FRU": fru,
                "SUB1": sub1,
                "SUB2": sub2,
                "SUB3": sub3,
                "DESCRICAO": descricao,
                "MAQUINAS": maquinas,
                "CLIENTES": f"{clientes} - ({serial} {data_contrato.strftime('%d/%m/%y')}_{sla}) - {uf}",
                "DATA_FIM": data_contrato.strftime("%d/%m/%y"),
                "SLA": sla,
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

    vencidas = []
    for _, row in df.iterrows():
        data_fim = parse_data_possivel(row.get("DATA_FIM"))
        if data_fim and data_fim.date() < hoje.date():
            vencidas.append(row)

    if not vencidas:
        st.info("Nenhum contrato vencido.")
        return

    df_vencidas = pd.DataFrame(vencidas)
    st.dataframe(df_vencidas)

    linha = st.number_input("Linha a renovar (número da tabela acima)", min_value=0, step=1)
    nova_data = st.date_input("Nova Data")
    novo_sla = st.text_input("Novo SLA (opcional)")

    if st.button("Atualizar Contrato"):
        try:
            idx = int(linha)
            df.loc[idx, "DATA_FIM"] = nova_data.strftime("%d/%m/%y")
            df.loc[idx, "STATUS"] = "DENTRO"
            if novo_sla:
                df.loc[idx, "SLA"] = novo_sla
            salvar_dados(df)
        except Exception as e:
            st.error(f"Erro: {e}")

# =========================
# RELATÓRIO
# =========================
def pagina_relatorio():
    st.subheader("📄 Relatório de Peças Vencidas")

    df = carregar_dados()
    hoje = datetime.today()

    # Verifica se a planilha foi carregada
    if df.empty:
        st.warning("⚠️ Não foi possível carregar dados.")
        return

    # Garante que a coluna exista
    if "DATA_FIM" not in df.columns:
        st.error("❌ A coluna 'DATA_FIM' não existe na planilha.")
        return

    # Função segura para verificar se a data é vencida
    def vencida(x):
        data = parse_data_possivel(x)
        if data is None:
            return False
        return data.date() < hoje.date()

    try:
        vencidas = df[df["DATA_FIM"].apply(vencida)]
        if vencidas.empty:
            st.info("Nenhum contrato vencido encontrado.")
        else:
            st.dataframe(vencidas)
            st.download_button(
                "⬇️ Baixar Relatório",
                vencidas.to_csv(index=False).encode("utf-8"),
                "relatorio_vencidas.csv",
                "text/csv",
            )
    except Exception as e:
        st.error(f"Erro ao gerar relatório: {e}")

# =========================
# MENU PRINCIPAL
# =========================
def main_page():
    st.sidebar.title(f"👋 Olá, {st.session_state['usuario']}")
    escolha = st.sidebar.radio("Menu", ["Cadastro", "Renovação", "Relatório", "Sair"])
    if escolha == "Cadastro":
        pagina_cadastro()
    elif escolha == "Renovação":
        pagina_renovacao()
    elif escolha == "Relatório":
        pagina_relatorio()
    elif escolha == "Sair":
        st.session_state.clear()
        st.rerun()

# =========================
# APP
# =========================
st.set_page_config(page_title="Controle de Peças", layout="centered")

if "usuario" not in st.session_state:
    login_page()
else:
    main_page()
