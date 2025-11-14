# app.py
import streamlit as st
import pandas as pd
import hashlib
from datetime import datetime, timedelta
import io
import requests
import base64
import os
import json
import time  # <- adicionado

# =========================
# CONFIGURAÇÃO - GitHub / Arquivos
# =========================
REPO_RAW_BASE = "https://raw.githubusercontent.com/otavilobato/pecas1/main"
REPO_API_BASE = "https://api.github.com/repos/otavilobato/pecas1/contents"
EXCEL_RAW_URL = f"{REPO_RAW_BASE}/SALDO_PECAS.xlsx"
EXCEL_API_URL = f"{REPO_API_BASE}/SALDO_PECAS.xlsx"
LOGS_RAW_URL = f"{REPO_RAW_BASE}/logs.csv"
LOGS_API_URL = f"{REPO_API_BASE}/logs.csv"

# =========================
# CREDENCIAIS / USUÁRIOS (via secrets)
# =========================
RAW_USERS = st.secrets["auth"]
USUARIOS = {u: hashlib.sha256(RAW_USERS[u].encode()).hexdigest() for u in RAW_USERS}
RAW_PERMISSOES = st.secrets["permissoes"]
PERMISSOES = {
    user: (["ALL"] if RAW_PERMISSOES[user] == "ALL" else RAW_PERMISSOES[user].split(",")) for user in RAW_PERMISSOES
}

def ufs_do_usuario(usuario):
    return PERMISSOES.get(usuario, [])

def is_admin(usuario):
    ufs = ufs_do_usuario(usuario)
    return "ALL" in ufs

# =========================
# UTILITÁRIOS: datas e parsing
# =========================
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
# FUNÇÕES GERAIS DE I/O COM GITHUB
# =========================
def get_github_token():
    return st.secrets.get("token", {}).get("GITHUB_TOKEN") or os.getenv("GITHUB_TOKEN")

def _get_headers():
    token = get_github_token()
    return {"Authorization": f"token {token}"} if token else {}

def carregar_planilha_principal():
    """ Carrega sempre a planilha PRINCIPAL atualizada, sem cache """
    headers = _get_headers()
    url = f"{EXCEL_RAW_URL}?nocache={int(time.time())}"  # força versão atual
    try:
        r = requests.get(url, headers=headers)
        if r.status_code == 200:
            return pd.read_excel(io.BytesIO(r.content), sheet_name="PRINCIPAL")
        else:
            st.error(f"❌ Falha ao carregar planilha (código {r.status_code}).")
            return pd.DataFrame()
    except Exception as e:
        st.error(f"Erro ao tentar carregar planilha: {e}")
        return pd.DataFrame()

def salvar_planilha_principal(df):
    """ Faz upload do Excel para o repositório (substitui SALDO_PECAS.xlsx). """
    try:
        token = get_github_token()
        if not token:
            st.error("❌ Token do GitHub não configurado.")
            return False
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, sheet_name="PRINCIPAL", index=False)
        content = output.getvalue()
        encoded_content = base64.b64encode(content).decode("utf-8")
        headers = {"Authorization": f"token {token}"}
        resp_get = requests.get(EXCEL_API_URL, headers=headers)
        sha = resp_get.json().get("sha") if resp_get.status_code == 200 else None
        commit_message = f"Atualização automática SALDO_PECAS ({datetime.now().strftime('%d/%m/%Y %H:%M')})"
        data = {"message": commit_message, "content": encoded_content}
        if sha:
            data["sha"] = sha
        resp_put = requests.put(EXCEL_API_URL, headers=headers, json=data)
        if resp_put.status_code in (200, 201):
            st.cache_data.clear()  # <- limpa cache para refletir dados atualizados
            return True
        else:
            st.error(f"Erro ao salvar planilha no GitHub: {resp_put.status_code}")
            st.text(resp_put.text)
            return False
    except Exception as e:
        st.error(f"Erro ao tentar salvar planilha: {e}")
        return False

# =========================
# LOGS: carregar / salvar / registrar
# =========================
def carregar_logs():
    """ Tenta baixar logs.csv do repo (raw). Se não existir, retorna DataFrame vazio """
    headers = _get_headers()
    try:
        url = f"{LOGS_RAW_URL}?nocache={int(time.time())}"  # evita cache
        r = requests.get(url, headers=headers)
        if r.status_code == 200:
            df = pd.read_csv(io.BytesIO(r.content))
            return df
        else:
            cols = ["data_hora","usuario","acao","detalhes","antes","depois"]
            return pd.DataFrame(columns=cols)
    except:
        cols = ["data_hora","usuario","acao","detalhes","antes","depois"]
        return pd.DataFrame(columns=cols)

def salvar_logs(df_log):
    """ Sobe logs.csv para o repositório via API. """
    try:
        token = get_github_token()
        if not token:
            st.error("❌ Token do GitHub não configurado para salvar logs.")
            return False
        csv_bytes = df_log.to_csv(index=False).encode("utf-8")
        encoded = base64.b64encode(csv_bytes).decode("utf-8")
        headers = {"Authorization": f"token {token}"}
        resp_get = requests.get(LOGS_API_URL, headers=headers)
        sha = resp_get.json().get("sha") if resp_get.status_code == 200 else None
        commit_message = f"Atualização automática logs ({datetime.now().strftime('%d/%m/%Y %H:%M')})"
        data = {"message": commit_message, "content": encoded}
        if sha:
            data["sha"] = sha
        resp_put = requests.put(LOGS_API_URL, headers=headers, json=data)
        if resp_put.status_code in (200, 201):
            st.cache_data.clear()  # limpa cache
            return True
        else:
            st.error(f"Erro ao salvar logs no GitHub: {resp_put.status_code}")
            st.text(resp_put.text)
            return False
    except Exception as e:
        st.error(f"Erro ao tentar salvar logs: {e}")
        return False

def registrar_log(usuario, acao, detalhes="", antes=None, depois=None, salvar_remote=True):
    """ Registra um log detalhado """
    try:
        df_log = carregar_logs()
        nova = {
            "data_hora": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "usuario": usuario,
            "acao": acao,
            "detalhes": detalhes,
            "antes": json.dumps(antes, ensure_ascii=False) if antes is not None else "",
            "depois": json.dumps(depois, ensure_ascii=False) if depois is not None else ""
        }
        df_log = pd.concat([df_log, pd.DataFrame([nova])], ignore_index=True)
        if salvar_remote:
            ok = salvar_logs(df_log)
            if not ok:
                try:
                    df_log.to_csv("logs_local.csv", index=False)
                except: pass
        return True
    except Exception as e:
        print("Erro registrar_log:", e)
        return False

# =========================
# AUTENTICAÇÃO / LOGIN
# =========================
def tentar_login():
    usuario = st.session_state.get("usuario_input", "").strip()
    senha = st.session_state.get("senha_input", "").strip()
    if not usuario or not senha:
        return
    senha_hash = hashlib.sha256(senha.encode()).hexdigest()
    if usuario in USUARIOS and USUARIOS[usuario] == senha_hash:
        st.session_state["usuario"] = usuario
        st.success("Login realizado com sucesso!")
        registrar_log(usuario, "LOGIN", "Login bem-sucedido")
    else:
        st.error("Usuário ou senha incorretos.")
        registrar_log(usuario, "LOGIN_FAIL", "Tentativa de login falhou", antes={"usuario": usuario})

def login_page():
    st.title("🔐 Login")
    st.text_input("Usuário", key="usuario_input")
    st.text_input("Senha", type="password", key="senha_input", on_change=tentar_login)
    st.button("Entrar", on_click=tentar_login)

# =========================
# As demais funções (cadastro, renovação, visualizar tudo, logs, relatório, main_page)
# permanecem iguais, pois não precisamos alterar nada nelas
# apenas assegure que todas chamem carregar_planilha_principal() ao invés de cache
# =========================

# =========================
# EXECUÇÃO DO APP
# =========================
st.set_page_config(page_title="Controle de Peças", layout="centered")
if "usuario" not in st.session_state:
    login_page()
else:
    # Limpa cache sempre que entra na página principal
    st.cache_data.clear()
    main_page()
