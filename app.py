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
# No secrets.toml você deve ter as seções:
# [token] GITHUB_TOKEN = "..."
# [auth] ... users ...
# [permissoes] ... mapping ...

RAW_USERS = st.secrets["auth"]
USUARIOS = {u: hashlib.sha256(RAW_USERS[u].encode()).hexdigest() for u in RAW_USERS}

RAW_PERMISSOES = st.secrets["permissoes"]
PERMISSOES = {
    user: (["ALL"] if RAW_PERMISSOES[user] == "ALL" else RAW_PERMISSOES[user].split(","))
    for user in RAW_PERMISSOES
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
    return (
        st.secrets.get("token", {}).get("GITHUB_TOKEN")
        if isinstance(st.secrets.get("token"), dict)
        else st.secrets.get("token", {}).get("GITHUB_TOKEN")
        if isinstance(st.secrets.get("token"), dict)
        else st.secrets.get("GITHUB_TOKEN")
        or os.getenv("GITHUB_TOKEN")
        or st.secrets.get("GITHUB_TOKEN")
    )

def _get_headers():
    token = get_github_token()
    return {"Authorization": f"token {token}"} if token else {}

@st.cache_data(ttl=60)
def carregar_planilha_principal():
    headers = _get_headers()
    try:
        r = requests.get(EXCEL_RAW_URL, headers=headers)
        if r.status_code == 200:
            return pd.read_excel(io.BytesIO(r.content), sheet_name="PRINCIPAL")
        else:
            st.error(f"❌ Falha ao carregar planilha (código {r.status_code}).")
            return pd.DataFrame()
    except Exception as e:
        st.error(f"Erro ao tentar carregar planilha: {e}")
        return pd.DataFrame()

def salvar_planilha_principal(df):
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
@st.cache_data(ttl=20)
def carregar_logs():
    headers = _get_headers()
    try:
        r = requests.get(LOGS_RAW_URL, headers=headers)
        if r.status_code == 200:
            df = pd.read_csv(io.BytesIO(r.content))
            return df
        else:
            cols = ["data_hora","usuario","acao","detalhes","antes","depois"]
            return pd.DataFrame(columns=cols)
    except Exception:
        cols = ["data_hora","usuario","acao","detalhes","antes","depois"]
        return pd.DataFrame(columns=cols)

def salvar_logs(df_log):
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
            return True
        else:
            st.error(f"Erro ao salvar logs no GitHub: {resp_put.status_code}")
            st.text(resp_put.text)
            return False
    except Exception as e:
        st.error(f"Erro ao tentar salvar logs: {e}")
        return False

def registrar_log(usuario, acao, detalhes="", antes=None, depois=None, salvar_remote=True):
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
                except:
                    pass

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
# FILTRAGEM POR USUÁRIO
# =========================
def filtrar_por_usuario(df, usuario):
    ufs = ufs_do_usuario(usuario)
    if "ALL" in ufs:
        return df
    if "UF" not in df.columns:
        return df.iloc[0:0]
    return df[df["UF"].isin(ufs)]

# =========================
# PÁGINA: CADASTRO
# =========================
def pagina_cadastro():
    usuario = st.session_state["usuario"]
    ufs_user = ufs_do_usuario(usuario)

    st.subheader("🧩 Cadastro de Peças")

    df = carregar_planilha_principal()

    if "ALL" in ufs_user:
        lista_uf = ["AM","BA","CE","DF","GO","MA","MG","PA","PE","RJ","TO"]
    else:
        lista_uf = ufs_user

    uf = st.selectbox("UF", lista_uf)
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
            return

        if len(fru) != 7:
            st.error("FRU deve ter 7 caracteres.")
            return

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

        registrar_log(usuario, "CADASTRO", f"FRU {fru.upper()}", antes=None, depois=nova_linha)

        df = pd.concat([df, pd.DataFrame([nova_linha])], ignore_index=True)
        ok = salvar_planilha_principal(df)

        if ok:
            st.success("Peça cadastrada com sucesso!")
        else:
            st.error("Houve um erro ao salvar. Tente novamente.")

# =========================
# PÁGINA: RENOVAÇÃO
# =========================
def pagina_renovacao():
    usuario = st.session_state["usuario"]

    st.subheader("🔄 Renovação de Contrato")

    df_full = carregar_planilha_principal()
    df = filtrar_por_usuario(df_full, usuario)

    if df.empty:
        st.info("Nenhuma peça cadastrada para sua região.")
        return

    hoje = datetime.today()

    df["DATA_FIM_DT"] = df["DATA_FIM"].apply(parse_data_possivel)

    vencidas = df[df["DATA_FIM_DT"].notna() & (df["DATA_FIM_DT"].dt.date < hoje.date())]

    if vencidas.empty:
        st.info("Nenhum contrato vencido.")
        return

    vencidas_mostrar = vencidas.drop(columns=["DATA_FIM_DT", "STATUS", "DATA_VERIFICACAO"], errors='ignore')
    st.dataframe(vencidas_mostrar)

    indices_relativos = list(vencidas.index)

    idx_pos = st.number_input(
        "Selecione posição (número da linha mostrada acima)",
        min_value=0,
        max_value=len(indices_relativos)-1,
        step=1
    )

    nova_data = st.date_input("Nova Data")
    novo_sla = st.text_input("Novo SLA (opcional)")

    if st.button("Atualizar Contrato"):
        try:
            idx_abs = indices_relativos[int(idx_pos)]

            antes = df_full.loc[idx_abs].to_dict()

            df_full.loc[idx_abs, "DATA_FIM"] = nova_data.strftime("%d/%m/%y")
            df_full.loc[idx_abs, "STATUS"] = "DENTRO"

            if novo_sla:
                df_full.loc[idx_abs, "SLA"] = novo_sla.upper()

            depois = df_full.loc[idx_abs].to_dict()

            registrar_log(usuario, "RENOVACAO", f"Linha {idx_abs}", antes=antes, depois=depois)

            ok = salvar_planilha_principal(df_full)
            if ok:
                st.success("Contrato atualizado com sucesso!")
            else:
                st.error("Erro ao salvar atualização.")
        except Exception as e:
            st.error(f"Erro ao atualizar: {e}")

    if st.button("❌ Excluir Contrato"):
        try:
            idx_abs = indices_relativos[int(idx_pos)]
            antes = df_full.loc[idx_abs].to_dict()

            df_full = df_full.drop(idx_abs).reset_index(drop=True)

            registrar_log(usuario, "EXCLUSAO", f"Linha {idx_abs}", antes=antes, depois=None)

            ok = salvar_planilha_principal(df_full)
            if ok:
                st.success("Contrato excluído com sucesso!")
            else:
                st.error("Erro ao salvar exclusão.")
        except Exception as e:
            st.error(f"Erro ao excluir: {e}")

# =========================
# PÁGINA: VISUALIZAR TUDO
# =========================
def pagina_visualizar_tudo():
    usuario = st.session_state["usuario"]

    st.subheader("📋 Todos os registros (sua UF)")

    df = filtrar_por_usuario(carregar_planilha_principal(), usuario)

    if df.empty:
        st.info("Nenhum registro encontrado para sua UF.")
        return

    df_mostrar = df.drop(columns=["STATUS","DATA_VERIFICACAO"], errors='ignore')
    st.dataframe(df_mostrar)

    formato = st.radio("Formato para download", ["CSV","TXT"])

    if formato == "CSV":
        if st.button("⬇️ Exportar CSV (registros visíveis)"):
            registrar_log(usuario, "EXPORTACAO", f"Exportou CSV ({len(df_mostrar)} linhas)")
            st.download_button("Download CSV", df_mostrar.to_csv(index=False).encode("utf-8"), "dados.csv")
    else:
        if st.button("⬇️ Exportar TXT (registros visíveis)"):
            registrar_log(usuario, "EXPORTACAO", f"Exportou TXT ({len(df_mostrar)} linhas)")
            st.download_button("Download TXT", df_mostrar.to_csv(index=False, sep="\t").encode("utf-8"), "dados.txt")

# =========================
# PÁGINA: RELATÓRIO (VENCIDAS)
# =========================
def pagina_relatorio():
    usuario = st.session_state["usuario"]

    st.subheader("📄 Relatório de Peças Vencidas (sua UF)")

    df = filtrar_por_usuario(carregar_planilha_principal(), usuario)

    if df.empty:
        st.info("Nenhum registro encontrado para sua UF.")
        return

    hoje = datetime.today()

    df["DATA_FIM_DT"] = df["DATA_FIM"].apply(parse_data_possivel)

    vencidas = df[df["DATA_FIM_DT"].notna() & (df["DATA_FIM_DT"].dt.date < hoje.date())]

    if vencidas.empty:
        st.info("Nenhum contrato vencido.")
        return

    vencidas_mostrar = vencidas.drop(columns=["STATUS","DATA_VERIFICACAO","DATA_FIM_DT"], errors='ignore')
    st.dataframe(vencidas_mostrar)

    if st.button("⬇️ Baixar Relatório CSV (vencidas)"):
        registrar_log(usuario, "EXPORTACAO_RELATORIO_VENCIDAS", f"Exportou relatório vencidas ({len(vencidas_mostrar)} linhas)")
        st.download_button("Download CSV", vencidas_mostrar.to_csv(index=False).encode("utf-8"), "relatorio_vencidas.csv")

# =========================
# PÁGINA: LOGS (APENAS ADMIN)
# =========================
def pagina_logs():
    usuario = st.session_state["usuario"]

    if not is_admin(usuario):
        st.error("⛔ Acesso restrito aos administradores.")
        return

    st.subheader("📜 Logs do Sistema (detalhado)")

    df_log = carregar_logs()

    if df_log.empty:
        st.info("Nenhum log disponível.")
        return

    try:
        df_show = df_log.sort_values("data_hora", ascending=False)
    except:
        df_show = df_log

    st.dataframe(df_show)

    if st.button("⬇️ Exportar Logs (CSV)"):
        registrar_log(usuario, "EXPORTAR_LOGS", f"Exportou logs ({len(df_log)} linhas)")
        st.download_button("Download Logs CSV", df_log.to_csv(index=False).encode("utf-8"), "logs.csv")

# =========================
# MENU PRINCIPAL
# =========================
def main_page():
    usuario = st.session_state["usuario"]

    st.sidebar.title(f"👋 Olá, {usuario}")

    opcoes = ["Cadastro", "Renovação", "Relatório", "Visualizar Tudo"]
    if is_admin(usuario):
        opcoes.append("Logs")
    opcoes.append("Sair")

    escolha = st.sidebar.radio("Menu", opcoes)

    if escolha == "Cadastro":
        pagina_cadastro()
    elif escolha == "Renovação":
        pagina_renovacao()
    elif escolha == "Relatório":
        pagina_relatorio()
    elif escolha == "Visualizar Tudo":
        pagina_visualizar_tudo()
    elif escolha == "Logs":
        pagina_logs()
    elif escolha == "Sair":
        registrar_log(usuario, "LOGOUT", "Usuário saiu")
        st.session_state.clear()
        st.info("Você saiu. Atualize a página para entrar novamente.")

# =========================
# EXECUÇÃO DO APP
# =========================
st.set_page_config(page_title="Controle de Peças", layout="centered")

if "usuario" not in st.session_state:
    login_page()
else:
    main_page()
