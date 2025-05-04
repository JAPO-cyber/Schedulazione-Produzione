import streamlit as st
from utils.auth import check_login
from lib.style import apply_custom_style

# 📌 Stato sessione
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
if "role" not in st.session_state:
    st.session_state.role = None

# Determinazione del titolo della pagina (alias)
page_title = "Login" if not st.session_state.logged_in else "Schedulatore di produzione"
st.set_page_config(page_title=page_title, layout="wide")

# ✅ Applica stile grafico centralizzato
apply_custom_style()

# 🔐 Login
if not st.session_state.logged_in:
    st.markdown("## 🔐 Login")
    username = st.text_input("Username").strip()
    password = st.text_input("Password", type="password").strip()

    if st.button("Login"):
        success, role = check_login(username, password)
        if success:
            st.session_state.logged_in = True
            st.session_state.role = role
            # Naviga direttamente alla pagina di caricamento dati
            st.switch_page("1_Caricamento_Dati")

# 🔓 Logout + Ruolo nella sidebar
if st.session_state.logged_in:
    with st.sidebar:
        st.markdown(f"👤 **Ruolo attuale:** `{st.session_state.role}`")
        if st.button("🔓 Logout"):
            st.session_state.logged_in = False
            st.session_state.role = None
            # Ricarica la pagina per ripristinare lo stato di login
            st.rerun()

