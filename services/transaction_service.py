import json
from datetime import datetime

import streamlit as st
from bson.decimal128 import Decimal128
from bson.objectid import ObjectId
from decimal import Decimal

from ai.logic import (
    analyze_transaction_impulse_risk,
    generate_theory_explanation,
    generate_cooling_recommendation,
    generate_nudge,
)


def clean_for_ai(obj):
    """Recursively convert MongoDB/Python objects to JSON-safe types."""
    if isinstance(obj, Decimal128):
        return float(obj.to_decimal())
    if isinstance(obj, Decimal):
        return float(obj)
    if isinstance(obj, datetime):
        return obj.isoformat()
    if isinstance(obj, ObjectId):
        return str(obj)
    if isinstance(obj, dict):
        return {k: clean_for_ai(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [clean_for_ai(i) for i in obj]
    return obj


def make_timestamp(est_timezone, selected_date=None, selected_time=None, *, auto=False):
    """Return a timezone-aware datetime in the configured timezone."""
    if auto:
        return datetime.now(est_timezone)

    selected_date = selected_date or datetime.today().date()
    selected_time = selected_time or datetime.min.time()
    naive_dt = datetime.combine(selected_date, selected_time)
    return est_timezone.localize(naive_dt)


def insert_complete_txn_data(txn_data_collection, data):
    try:
        txn_data_collection.insert_one(data)
        return True
    except Exception as e:
        st.error(f"Error inserting data: {e}")
        return False


def update_transaction_status(txn_data_collection, txn_id, new_status):
    try:
        result = txn_data_collection.update_one(
            {"_id": txn_id},
            {"$set": {"status": new_status}},
        )
        return result.modified_count > 0
    except Exception as e:
        st.error(f"Error updating transaction: {e}")
        return False


def get_user_transactions(txn_data_collection, email, est_timezone):
    try:
        transactions = list(txn_data_collection.find({"email": email}))
        processed_txns = []
        for txn in transactions:
            processed_txns.append(
                {
                    "category": txn["category"],
                    "amount": float(txn["amount"].to_decimal()),
                    "description": txn["description"],
                    "status": txn["status"],
                    "date": txn["txn_datetime"]
                    .astimezone(est_timezone)
                    .strftime("%Y-%m-%d %I:%M %p EST"),
                }
            )
        return processed_txns
    except Exception as e:
        st.error(f"Error retrieving transactions: {str(e)}")
        return []


def generate_transaction_feedback(transaction, *, email, monthly_budget, monthly_income, txn_data_collection, est_timezone):
    try:
        user_history = get_user_transactions(txn_data_collection, email, est_timezone)
        user_profile = {
            "monthly_budget": monthly_budget,
            "monthly_income": monthly_income,
        }

        safe_transaction = clean_for_ai(transaction)
        risk = analyze_transaction_impulse_risk(safe_transaction, user_history, user_profile)
        tip = generate_theory_explanation(safe_transaction, risk)
        nudge = generate_nudge(
            user_profile,
            safe_transaction["category"],
            safe_transaction["amount"],
            risk.risk_level,
        )

        if risk.risk_level.lower() == "low":
            return (
                f"You spent ${safe_transaction['amount']} on {safe_transaction['category']}."
                f" This seems reasonable based on your habits and budget. Keep it up!"
            )
        if risk.risk_level.lower() == "medium":
            return (
                f"You just spent ${safe_transaction['amount']} on {safe_transaction['category']}."
                f" This isn't unusually high, but it might be worth pausing next time. "
                f"Try this: {tip.behavioral_tip}. "
                f"{nudge}"
            )

        return (
            f"You spent ${safe_transaction['amount']} on {safe_transaction['category']}, "
            f"which seems impulsive given your recent patterns. "
            f"{tip.theory_explanation} Try this next time: {tip.behavioral_tip} "
            f"({tip.primary_theory}). {nudge}"
        )

    except Exception as e:
        return f"⚠️ AI analysis failed: {str(e)}"


def generate_transaction_recommendation(pending_txn, *, email, monthly_budget, monthly_income, txn_data_collection, est_timezone):
    try:
        user_history = get_user_transactions(txn_data_collection, email, est_timezone)
        user_profile = {
            "monthly_budget": monthly_budget,
            "monthly_income": monthly_income,
        }

        risk = analyze_transaction_impulse_risk(pending_txn, user_history, user_profile)
        cooling = generate_cooling_recommendation(user_profile, user_history)
        tip = generate_theory_explanation(pending_txn, risk)
        nudge = generate_nudge(user_profile, pending_txn["category"], pending_txn["amount"], risk.risk_level)

        if risk.risk_level.lower() == "low":
            return (
                f"This purchase of ${pending_txn['amount']} for {pending_txn['category']} "
                f"looks aligned with your usual habits. You're doing well! "
                f"Just keep an eye on your budget balance."
            )
        if risk.risk_level.lower() == "medium":
            return (
                f"This expense seems okay, but there's a chance it's a bit impulsive. "
                f"You might benefit from a short pause before finalizing. "
                f"Try {cooling.custom_strategy.lower()}. "
                f"Also, {tip.behavioral_tip} ({tip.primary_theory}). "
                f"{nudge}"
            )

        return (
            f"Whoa - this ${pending_txn['amount']} expense for {pending_txn['category']} "
            f"raises a red flag. You've made similar high-risk decisions recently. "
            f"Take a break for at least {cooling.recommended_hours} hours. During that time, "
            f"{cooling.implementation_tip}. "
            f"{tip.theory_explanation} ({tip.primary_theory}) "
            f"Think it through before you hit 'Complete'. {nudge}"
        )

    except Exception as e:
        return f"⚠️ AI recommendation failed: {str(e)}"


def generate_financial_insights(
    *,
    email,
    monthly_budget,
    monthly_income,
    txn_data_collection,
    est_timezone,
    get_openai_client,
    openai_model,
):
    try:
        user_history = get_user_transactions(txn_data_collection, email, est_timezone)

        if len(user_history) < 10:
            return "Log more transactions to get AI insights..."

        total_spent = sum(float(txn["amount"]) for txn in user_history if txn["status"] == "Completed")
        categories = {}
        for txn in user_history:
            if txn["status"] == "Completed":
                cat = txn["category"]
                categories[cat] = categories.get(cat, 0.0) + float(txn["amount"])

        top_categories = sorted(categories.items(), key=lambda x: x[1], reverse=True)[:3]

        prompt = f"""
        You are a financial advisor assistant providing insights on a user's spending habits.

        User's financial summary:
        - Monthly budget: ${monthly_budget:.2f}
        - Monthly income: ${monthly_income:.2f}
        - Total spent: ${total_spent:.2f}
        - Top spending categories: {top_categories}

        Transaction history:
        {json.dumps(clean_for_ai(user_history))}

        Please provide the following insights:
        1. A summary of their spending profile (where money is going)
        2. Identification of potential areas of overspending
        3. 2-3 actionable tips to improve their financial situation

        Keep your response to 150-200 words, be specific, and focus on practical advice.
        """

        client = get_openai_client()
        response = client.chat.completions.create(
            model=openai_model,
            messages=[
                {"role": "system", "content": "You are a helpful financial assistant."},
                {"role": "user", "content": prompt},
            ],
            max_tokens=300,
            temperature=0.7,
        )

        return response.choices[0].message.content
    except Exception as e:
        return f"AI insights unavailable at the moment. Error: {str(e)}"
