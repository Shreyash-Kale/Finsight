import streamlit as st
from bson.decimal128 import Decimal128
from decimal import Decimal


def render_welcome_page():
    st.title("Finsight")
    st.write("AI assisted budget tracking")

    if st.button("Login"):
        st.session_state.page = "login"
        st.rerun()

    if st.button("Register"):
        st.session_state.page = "register"
        st.rerun()


def render_register_page(*, insert_user_data, check_email_exists, hash_password):
    st.title("Register")

    name = st.text_input("Name")
    email = st.text_input("Email")
    password = st.text_input("Password", type="password")
    budget = st.number_input("Monthly Budget", min_value=0.0, step=10.0, format="%.2f")
    income = st.number_input("Monthly Income", min_value=0.0, step=10.0, format="%.2f")

    col1, col2 = st.columns(2)

    with col1:
        if st.button("Back"):
            st.session_state.page = "welcome"
            st.rerun()

    with col2:
        if st.button("Register"):
            if not name.strip() or not email.strip() or not password.strip():
                st.error("Name, email, and password are required.")
                return

            normalized_email = email.strip().lower()
            normalized_name = name.strip()

            data = {
                "email": normalized_email,
                "password": hash_password(password),
                "name": normalized_name,
                "monthly_budget": Decimal128(Decimal(str(budget))),
                "monthly_income": Decimal128(Decimal(str(income))),
            }

            if check_email_exists(data["email"]):
                st.error("Error: This Prolific ID has already been used.")
            else:
                if insert_user_data(data):
                    st.success("Data saved successfully!")
                else:
                    st.error("Error: Failed to save data. Please try again.")

            st.success("Registration successful! Please log in.")
            st.session_state.page = "welcome"
            st.rerun()


def render_login_page(*, verify_login):
    st.title("Login")

    email = st.text_input("Email")
    password = st.text_input("Password", type="password")

    if st.button("Login", key="login_button"):
        normalized_email = email.strip().lower()
        login = verify_login(normalized_email, password)
        if login:
            st.session_state.user_logged_in = True
            st.session_state.email = normalized_email
            st.session_state.name = login["name"]
            st.session_state.monthly_budget = float(login["monthly_budget"].to_decimal())
            st.session_state.monthly_income = float(login["monthly_income"].to_decimal())
            st.session_state.page = "dashboard"
            st.rerun()
        else:
            st.error("Error: Incorrect Email/Password")

    if st.button("Back"):
        st.session_state.page = "welcome"
        st.rerun()
