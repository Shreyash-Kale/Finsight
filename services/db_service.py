import streamlit as st
from openai import OpenAI
from pymongo import MongoClient, ASCENDING, DESCENDING


def get_required_secret(section: str, key: str) -> str:
    try:
        value = st.secrets[section][key]
    except Exception as exc:
        raise RuntimeError(
            f"Missing Streamlit secret [{section}].{key}. Add it in .streamlit/secrets.toml."
        ) from exc

    if not value:
        raise RuntimeError(f"Empty Streamlit secret [{section}].{key}.")

    return value


@st.cache_resource
def get_openai_client() -> OpenAI:
    return OpenAI(api_key=get_required_secret("openai", "api_key"))


@st.cache_resource
def get_mongo_connection():
    client = MongoClient(get_required_secret("mongo", "mongo_url"))
    db = client["finsight_db"]

    user_collection = db["user_data"]
    txn_collection = db["txn_data"]

    # Indexes improve common dashboard and auth query patterns.
    user_collection.create_index([("email", ASCENDING)], name="idx_user_email")
    txn_collection.create_index(
        [("email", ASCENDING), ("status", ASCENDING), ("txn_datetime", DESCENDING)],
        name="idx_txn_email_status_datetime",
    )
    txn_collection.create_index(
        [("email", ASCENDING), ("txn_datetime", DESCENDING)],
        name="idx_txn_email_datetime",
    )

    return db
