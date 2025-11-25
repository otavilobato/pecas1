def cadastro_screen():
    st.header("📄 Cadastro de Peças")

    # ---------- LINHA 1 ----------
    col1, col2, col3, col4 = st.columns(4)

    FRU = col1.text_input("FRU (7 caracteres)*").upper().strip()
    SUB1 = col2.text_input("SUB1 (opcional, 7 chars)").upper().strip()
    SUB2 = col3.text_input("SUB2 (opcional, 7 chars)").upper().strip()
    SUB3 = col4.text_input("SUB3 (opcional, 7 chars)").upper().strip()

    # ---------- LINHA 2 ----------
    col5, col6 = st.columns(2)

    CLIENTE_raw = col5.text_input("CLIENTE *").upper().strip()
    SERIAL = col6.text_input("SERIAL *").upper().strip()

    # ---------- LINHA 3 ----------
    col7, col8 = st.columns(2)

    DATA_FIM = col7.date_input("DATA FIM *", format="YYYY/MM/DD")
    UF = col8.text_input("UF *").upper().strip()

    # ---------- LINHA 4 ----------
    col9, col10 = st.columns(2)

    DESCRICAO = col9.text_input("DESCRIÇÃO *").upper().strip()
    MAQUINAS = col10.text_input("MÁQUINAS *").upper().strip()

    # ---------- LINHA 5 ----------
    SLA = st.text_input("SLA *").upper().strip()

    # ---------- MONTAGEM DO CLIENTE FINAL ----------
    CLIENTE_FINAL = ""
    if CLIENTE_raw and SERIAL and SLA:
        CLIENTE_FINAL = f"{CLIENTE_raw}({SERIAL}_{DATA_FIM}_{SLA}){UF}"

    st.markdown("### Preview CLIENTE:")
    st.code(CLIENTE_FINAL if CLIENTE_FINAL else "(preencha CLIENTE, SERIAL, SLA e UF)")

    # ---------- VALIDAÇÕES ----------
    erros = []

    if FRU == "" or len(FRU) != 7:
        erros.append("FRU é obrigatório e deve ter 7 caracteres.")

    for nome, campo in [("SUB1", SUB1), ("SUB2", SUB2), ("SUB3", SUB3)]:
        if campo and len(campo) != 7:
            erros.append(f"{nome} deve ter exatamente 7 caracteres quando preenchido.")

    obrigatorios = [
        ("CLIENTE", CLIENTE_raw),
        ("SERIAL", SERIAL),
        ("UF", UF),
        ("DESCRIÇÃO", DESCRICAO),
        ("MÁQUINAS", MAQUINAS),
        ("SLA", SLA),
    ]

    for nome, valor in obrigatorios:
        if not valor:
            erros.append(f"{nome} é obrigatório.")

    if erros:
        st.error("⚠️ Corrija os itens antes de salvar:\n\n- " + "\n- ".join(erros))
        return

    # ---------- BOTÃO SALVAR ----------
    if st.button("Salvar Registro"):
        df = github_read_excel()
        if df is None:
            return

        nova_linha = {
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

        # adicionar linha
        df = pd.concat([df, pd.DataFrame([nova_linha])], ignore_index=True)

        ok = github_write_excel(df, commit_message="Cadastro Streamlit")
        if ok:
            st.success("✔ Registro salvo com sucesso!")
        else:
            st.error("❌ Erro ao salvar o registro no GitHub.")
