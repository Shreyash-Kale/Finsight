import streamlit as st
from bson.decimal128 import Decimal128
from decimal import Decimal


def render_user_sidebar(user_data_collection) -> None:
    with st.sidebar:
        st.title(f"Hello, {st.session_state.name}!")

        if st.button("Edit Monthly Budget"):
            st.session_state.show_budget_edit = not st.session_state.show_budget_edit
            if st.session_state.show_budget_edit:
                st.session_state.show_income_edit = False
            st.rerun()

        if st.session_state.show_budget_edit:
            with st.container():
                col1, col2 = st.columns([3, 1])
                with col1:
                    new_budget = st.number_input(
                        "New Monthly Budget ($)",
                        min_value=0.0,
                        value=float(st.session_state.monthly_budget),
                        step=10.0,
                        format="%.2f",
                    )
                with col2:
                    if st.button("", key="budget_done", icon="☑️"):
                        user_data_collection.update_one(
                            {"email": st.session_state.email},
                            {"$set": {"monthly_budget": Decimal128(Decimal(str(new_budget)))}}
                        )
                        st.session_state.monthly_budget = float(new_budget)
                        st.session_state.show_budget_edit = False
                        st.session_state.page = "dashboard"
                        st.rerun()

        if st.button("Edit Monthly Income"):
            st.session_state.show_income_edit = not st.session_state.show_income_edit
            if st.session_state.show_income_edit:
                st.session_state.show_budget_edit = False
            st.rerun()

        if st.session_state.show_income_edit:
            with st.container():
                col1, col2 = st.columns([3, 1])
                with col1:
                    new_income = st.number_input(
                        "New Monthly Income ($)",
                        min_value=0.0,
                        value=float(st.session_state.monthly_income),
                        step=10.0,
                        format="%.2f",
                    )
                with col2:
                    if st.button("", key="income_done", icon="☑️"):
                        user_data_collection.update_one(
                            {"email": st.session_state.email},
                            {"$set": {"monthly_income": Decimal128(Decimal(str(new_income)))}}
                        )
                        st.session_state.monthly_income = float(new_income)
                        st.session_state.show_income_edit = False
                        st.session_state.page = "dashboard"
                        st.rerun()

        if st.button("Logout"):
            st.session_state.user_logged_in = False
            st.session_state.name = ""
            st.session_state.page = "welcome"
            st.rerun()
