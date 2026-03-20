import pandas as pd
import streamlit as st


def initialize_session_state() -> None:
    defaults = {
        "page": "welcome",
        "user_logged_in": False,
        "email": "",
        "name": "",
        "monthly_budget": 0.00,
        "monthly_income": 0.00,
        "show_budget_edit": False,
        "show_income_edit": False,
        "openai_tested": True,
    }

    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value

    if "expenses" not in st.session_state:
        st.session_state.expenses = pd.DataFrame(
            columns=["date", "category", "amount", "description"]
        )

    if "income" not in st.session_state:
        st.session_state.income = pd.DataFrame(
            columns=["date", "source", "amount", "description"]
        )
