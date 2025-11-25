# app.py
import streamlit as st
import pandas as pd
from io import BytesIO
import base64, os
from github import Github
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.backends import default_backend
from cryptography.fernet import Fernet


# ======== Configurações da criptografia ========
KDF_ITERATIONS = 200_000
SALT_SIZE = 16


# ----- Deriva chave (igual web e local) -----
def derive_key_from_password(password: str, salt: bytes) -> bytes:
    password_bytes = password.encode('utf-8')
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=KDF_ITERATIONS,
        backend=default_backend()
    )
    key = kdf.derive(password_bytes)
    return base64.urlsafe_b64encode(key)


# ----- Converte DF → Excel -----
def dataframe_to_excel_bytes(df: pd.DataFrame) -> bytes:
    bio = BytesIO()
    with pd.ExcelWriter(bio, engine='openpyxl') as w:
        df.to_excel(w, index=False)
    return bio.getvalue()


# ----- Converte Excel → DF -----
def excel_bytes_to_dataframe(b: bytes) -> pd.DataFrame:
    bio = BytesIO(b)
    return pd.read_excel(bio)


# ----- Criptografa bytes -----
def encrypt_bytes_with_password(plain_bytes: bytes, password: str) -> bytes:
    salt = os.urandom(SALT_SIZE)
    key = derive_key_from_password(password, salt)
    f = Fernet(key)
    token = f.encrypt(plain_bytes)
    return salt + token


# ----- Descriptografa bytes -----
def decrypt_bytes_with_password(enc_bytes: bytes, password: str) -> bytes:
    salt = enc_bytes[:SALT_SIZE]
    token = enc_bytes[SALT_SIZE:]
    key = derive_key_from_password(password, salt)
    f = Fernet(key)
    return f.decrypt(token)


# ======== GitHub Helpers ========
def get_file_from_github(g, owner, repo_name, path):
    repo = g.get_repo(f"{owner}/{repo_name}")
    try:
        return repo.get_contents(path)
    except Exception:
        return None


def read_raw_file_bytes_from_github(g, owner, repo_name, path):
    contents = get_file_from_github(g, owner, repo_name, path)
    if contents is None:
        return None
    return base64.b64decode(contents.content)


def commit_file_to_github(g, owner, repo_name, path, data_bytes, message="update encrypted sheet"):
    repo = g.get_repo(f"{owner}/{repo_name}")
    contents = get_file_from_github(g, owner, repo_name, path)
    encoded = base64.b64encode(data_bytes).decode('utf-8')

    if contents is None:
        repo.create_file(path, message, encoded, branch="main")
    else:
        repo.update_file(path, message, encoded, contents.sha, branch="main")


# ============================================================
#                       STREAMLIT APP
# ============================================================

st.title("Cadastro seguro — dados criptografados no GitHub")


# -------- Config do secrets --------
GITHUB_TOKEN = st.secrets["github_token"]
GITHUB_OWNER = st.secrets["github_owner"]
GITHUB_REPO = st.secrets["github_repo"]
ENC_PATH = st.secrets["enc_filename"]  # ex.: "dados_enc/dados.enc"
MASTER_PASSWORD = st.secrets["master_password"]

g = Github(GITHUB_TOKEN)

# --------- Formulário ---------
with st.form("cadastro"):
    nome = st.text_input("Nome")
    email = st.text_input("Email")
    valor = st.number_input("Valor", value=0)
    enviar = st.form_submit_button("Salvar")


# ============================================================
#                   PROCESSAMENTO DO ENVIO
# ============================================================

if enviar:
    st.info("Processando...")

    # cria registro
    nova_linha = {"Nome": nome, "Email": email, "Valor": valor}

    # lê arquivo criptografado existente (se houver)
    arquivo_bruto = read_raw_file_bytes_from_github(
        g, GITHUB_OWNER, GITHUB_REPO, ENC_PATH
    )

    if arquivo_bruto is None:
        df = pd.DataFrame([nova_linha])
    else:
        try:
            xlsx_bytes = decrypt_bytes_with_password(arquivo_bruto, MASTER_PASSWORD)
            df_old = excel_bytes_to_dataframe(xlsx_bytes)
            df = pd.concat([df_old, pd.DataFrame([nova_linha])], ignore_index=True)

        except Exception:
            st.error("Erro ao descriptografar arquivo existente no GitHub.")
            st.stop()

    # recria Excel
    xlsx_bytes = dataframe_to_excel_bytes(df)

    # re-encripta
    enc_bytes = encrypt_bytes_with_password(xlsx_bytes, MASTER_PASSWORD)

    # salva no GitHub
    try:
        commit_file_to_github(
            g, GITHUB_OWNER, GITHUB_REPO, ENC_PATH,
            enc_bytes,
            message=f"Atualização criptografada - {nome}"
        )

        st.success("✔ Dados salvos com segurança no GitHub (criptografados).")

    except Exception as e:
        st.error(f"Erro ao salvar no GitHub: {e}")
