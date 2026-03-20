import streamlit as st
from pytz import timezone as pytz_timezone
from streamlit_theme import st_theme

from ai.logic import generate_dashboard_insights
from services.auth_service import hash_password, verify_login as verify_user_login
from services.db_service import get_mongo_connection
from services.state_service import initialize_session_state
from services.transaction_service import (
    clean_for_ai as clean_for_ai_impl,
    make_timestamp as make_timestamp_impl,
    insert_complete_txn_data as insert_complete_txn_data_impl,
    get_user_transactions as get_user_transactions_impl,
    generate_transaction_feedback as generate_transaction_feedback_impl,
    generate_transaction_recommendation as generate_transaction_recommendation_impl,
)
from ui.components.sidebar import render_user_sidebar
from ui.pages.auth_pages import (
    render_welcome_page as render_welcome_page_view,
    render_register_page as render_register_page_view,
    render_login_page as render_login_page_view,
)
from ui.pages.dashboard import render_dashboard_page
from ui.pages.transaction_pages import (
    render_add_complete_expense_page as render_add_complete_expense_page_view,
    render_add_income_page as render_add_income_page_view,
    render_transactions_page as render_transactions_page_view,
    render_add_pending_expense_page as render_add_pending_expense_page_view,
)

st.set_page_config(layout="wide")
est_timezone = pytz_timezone("US/Eastern")


try:
    db = get_mongo_connection()
except RuntimeError as exc:
    st.error(str(exc))
    st.stop()

user_data_collection = db["user_data"]
txn_data_collection = db["txn_data"]


def clean_for_ai(obj):
    return clean_for_ai_impl(obj)


def make_timestamp(selected_date=None, selected_time=None, *, auto=False):
    return make_timestamp_impl(est_timezone, selected_date, selected_time, auto=auto)


def get_theme_colors():
    theme = st_theme()
    is_dark = theme.get("base") == "dark" if theme else False
    return {
        "completed": "#5dd96a" if not is_dark else "#193929",
        "cancelled": "#d95d5d" if not is_dark else "#5e1919",
        "onhold": "#d9a55d" if not is_dark else "#5e4219",
    }


def insert_user_data(data):
    try:
        user_data_collection.insert_one(data)
        return True
    except Exception as e:
        st.error(f"Error inserting data: {e}")
        return False


def check_email_exists(email):
    return user_data_collection.find_one({"email": email}) is not None


def verify_login(email, password):
    return verify_user_login(user_data_collection, email, password)


def insert_complete_txn_data(data):
    return insert_complete_txn_data_impl(txn_data_collection, data)


def get_user_transactions(email):
    return get_user_transactions_impl(txn_data_collection, email, est_timezone)


def generate_transaction_feedback(transaction):
    return generate_transaction_feedback_impl(
        transaction,
        email=st.session_state.email,
        monthly_budget=st.session_state.monthly_budget,
        monthly_income=st.session_state.monthly_income,
        txn_data_collection=txn_data_collection,
        est_timezone=est_timezone,
    )


def generate_transaction_recommendation(pending_txn):
    return generate_transaction_recommendation_impl(
        pending_txn,
        email=st.session_state.email,
        monthly_budget=st.session_state.monthly_budget,
        monthly_income=st.session_state.monthly_income,
        txn_data_collection=txn_data_collection,
        est_timezone=est_timezone,
    )


def main():
    initialize_session_state()

    if st.session_state.user_logged_in:
        render_user_sidebar(user_data_collection)

    handlers = {
        "welcome": lambda: render_welcome_page_view(),
        "register": lambda: render_register_page_view(
            insert_user_data=insert_user_data,
            check_email_exists=check_email_exists,
            hash_password=hash_password,
        ),
        "login": lambda: render_login_page_view(verify_login=verify_login),
        "dashboard": lambda: render_dashboard_page(
            txn_data_collection=txn_data_collection,
            est_timezone=est_timezone,
            get_theme_colors=get_theme_colors,
            get_user_transactions=get_user_transactions,
            generate_dashboard_insights=generate_dashboard_insights,
        ),
        "add_complete_expense": lambda: render_add_complete_expense_page_view(
            est_timezone=est_timezone,
            make_timestamp=make_timestamp,
            insert_complete_txn_data=insert_complete_txn_data,
            clean_for_ai=clean_for_ai,
            generate_transaction_feedback=generate_transaction_feedback,
        ),
        "add_income": lambda: render_add_income_page_view(
            est_timezone=est_timezone,
            make_timestamp=make_timestamp,
        ),
        "transactions": lambda: render_transactions_page_view(),
        "add_pending_expense": lambda: render_add_pending_expense_page_view(
            make_timestamp=make_timestamp,
            clean_for_ai=clean_for_ai,
            generate_transaction_recommendation=generate_transaction_recommendation,
            insert_complete_txn_data=insert_complete_txn_data,
        ),
    }

    handlers.get(st.session_state.page, handlers["welcome"])()


if __name__ == "__main__":
    main()
