import streamlit as st
import certifi
from openai import OpenAI
from pymongo import MongoClient, ASCENDING, DESCENDING
from urllib.parse import quote_plus, unquote_plus


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


def normalize_mongo_uri(uri: str) -> str:
    """Ensure MongoDB URI user/password are RFC 3986 escaped."""
    if "://" not in uri:
        return uri

    scheme, rest = uri.split("://", 1)
    if "@" not in rest:
        return uri

    userinfo, host_and_path = rest.rsplit("@", 1)
    if ":" not in userinfo:
        return uri

    username, password = userinfo.split(":", 1)
    encoded_username = quote_plus(unquote_plus(username))
    encoded_password = quote_plus(unquote_plus(password))
    return f"{scheme}://{encoded_username}:{encoded_password}@{host_and_path}"


@st.cache_resource
def get_openai_client() -> OpenAI:
    return OpenAI(api_key=get_required_secret("openai", "api_key"))


@st.cache_resource
def get_mongo_connection():
    raw_uri = get_required_secret("mongo", "mongo_url")
    client = MongoClient(
        normalize_mongo_uri(raw_uri),
        tlsCAFile=certifi.where(),
    )
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
