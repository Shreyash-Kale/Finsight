from datetime import datetime
from decimal import Decimal

import pandas as pd
import streamlit as st
from bson.decimal128 import Decimal128


def render_add_complete_expense_page(
    *,
    est_timezone,
    make_timestamp,
    insert_complete_txn_data,
    clean_for_ai,
    generate_transaction_feedback,
):
    st.title("Add Expense")

    category = st.selectbox(
        "Category",
        [
            "Food",
            "Entertainment",
            "Shopping",
            "Travel",
            "Utilities",
            "Health",
            "Groceries",
            "Gifts",
            "Education",
        ],
    )
    amount = st.number_input("Amount ($)", min_value=0.0, step=0.01)
    description = st.text_input("Description")
    description_error = False

    col1, col2 = st.columns(2)
    with col1:
        ui_date = st.date_input("Transaction date", value=datetime.today())
    with col2:
        now_est = datetime.now(est_timezone).strftime("%H:%M")
        ui_time_str = st.text_input("Time (HH:MM)", value=now_est)
        try:
            ui_time = datetime.strptime(ui_time_str, "%H:%M").time()
        except ValueError:
            st.warning("Please enter a valid time in HH:MM format (24-hour).")
            return

    if st.button("Add Expense"):
        if not description.strip():
            description_error = True
        else:
            ts = make_timestamp(ui_date, ui_time, auto=False)
            complete_data = {
                "email": st.session_state.email,
                "txn_datetime": ts,
                "category": category,
                "amount": Decimal128(Decimal(str(amount))),
                "description": description,
                "status": "Completed",
            }
            if insert_complete_txn_data(complete_data):
                safe_txn = clean_for_ai(complete_data)
                feedback = generate_transaction_feedback(safe_txn)
                st.success(f"Expense added successfully!\n\n**AI Feedback**: {feedback}")
            else:
                st.error("Error: Failed to save data. Please try again.")

    if description_error:
        st.warning("Please provide a description for this expense.")

    if st.button("Back to Dashboard"):
        st.session_state.page = "dashboard"
        st.rerun()


def render_add_income_page(*, est_timezone, make_timestamp):
    st.title("Add Income")

    source = st.selectbox(
        "Source",
        options=["Salary", "Freelance", "Investments", "Gift", "Other"],
    )
    amount = st.number_input("Amount ($)", min_value=0.0, step=0.01)
    description = st.text_input("Description (optional)")

    col1, col2 = st.columns(2)
    with col1:
        ui_date = st.date_input("Transaction date", value=datetime.today())
    with col2:
        now_est = datetime.now(est_timezone).strftime("%H:%M")
        ui_time_str = st.text_input("Time (HH:MM)", value=now_est)
        try:
            ui_time = datetime.strptime(ui_time_str, "%H:%M").time()
        except ValueError:
            st.warning("Please enter a valid time in HH:MM format (24-hour).")
            return

    if st.button("Add Income"):
        ts = make_timestamp(ui_date, ui_time, auto=False)
        new_income = {
            "date": ts,
            "source": source,
            "amount": amount,
            "description": description,
        }
        st.session_state.income = pd.concat(
            [st.session_state.income, pd.DataFrame([new_income])],
            ignore_index=True,
        )
        st.success("Income added successfully.")


def render_transactions_page():
    st.title("Transactions")

    tab1, tab2 = st.tabs(["Expenses", "Income"])

    with tab1:
        st.subheader("Your Expenses")
        if not st.session_state.expenses.empty:
            st.dataframe(st.session_state.expenses.sort_values("date", ascending=False))
        else:
            st.info("No expenses recorded yet.")

    with tab2:
        st.subheader("Your Income")
        if not st.session_state.income.empty:
            st.dataframe(st.session_state.income.sort_values("date", ascending=False))
        else:
            st.info("No income recorded yet.")

    if st.button("Back to Dashboard"):
        st.session_state.page = "dashboard"
        st.rerun()


def render_add_pending_expense_page(
    *,
    make_timestamp,
    clean_for_ai,
    generate_transaction_recommendation,
    insert_complete_txn_data,
):
    st.title("Add Pending Expense")

    if "pending_expense_phase" not in st.session_state:
        st.session_state.pending_expense_phase = "details"

    if st.session_state.pending_expense_phase == "details":
        category = st.selectbox(
            "Category",
            options=[
                "Food",
                "Transport",
                "Entertainment",
                "Utilities",
                "Rent",
                "Shopping",
                "Healthcare",
                "Education",
                "Other",
            ],
        )
        amount = st.number_input("Amount ($)", min_value=0.00, step=0.1, format="%.2f")
        description = st.text_input("Description")
        description_error = False

        col1, col2 = st.columns(2)
        with col1:
            ui_date = st.date_input("Transaction date", value=datetime.today())
        with col2:
            ui_time_str = st.text_input("Time (HH:MM)", value="12:00")
            try:
                ui_time = datetime.strptime(ui_time_str, "%H:%M").time()
            except ValueError:
                st.warning("Please enter a valid time in HH:MM format (24-hour).")
                return

        if st.button("Add Expense"):
            if not description.strip():
                description_error = True
            else:
                txn_time = make_timestamp(ui_date, ui_time)
                st.session_state.pending_expense = {
                    "category": category,
                    "amount": amount,
                    "description": description,
                    "txn_datetime": txn_time,
                }
                st.session_state.pending_expense_phase = "status"
                st.rerun()

        if description_error:
            st.warning("Please provide a description for this expense.")

        if st.button("Back to Dashboard"):
            st.session_state.page = "dashboard"
            st.rerun()

    elif st.session_state.pending_expense_phase == "status":
        safe_txn = clean_for_ai(st.session_state.pending_expense)
        recommendation = generate_transaction_recommendation(safe_txn)

        st.info(f"**AI Recommendation**: {recommendation}")
        st.write("Would you like to Cancel, Postpone, or Complete?")

        st.write(f"Category: {st.session_state.pending_expense['category']}")
        st.write(f"Amount: ${st.session_state.pending_expense['amount']:.2f}")
        st.write(f"Description: {st.session_state.pending_expense['description']}")

        for status in ["Cancelled", "Hold", "Completed"]:
            if st.button(status):
                pending_data = {
                    "email": st.session_state.email,
                    "txn_datetime": st.session_state.pending_expense["txn_datetime"],
                    "category": st.session_state.pending_expense["category"],
                    "amount": Decimal128(Decimal(str(st.session_state.pending_expense["amount"]))),
                    "description": st.session_state.pending_expense["description"],
                    "status": status,
                }
                if insert_complete_txn_data(pending_data):
                    st.success(f"Expense marked as {status.lower()} and recorded!")
                    st.session_state.pending_expense_phase = "details"
                    st.session_state.page = "dashboard"
                    st.rerun()
                else:
                    st.error("Error: Failed to save data. Please try again.")

        if st.button("Back to Details"):
            st.session_state.pending_expense_phase = "details"
            st.rerun()
