"""
Full AI implementation integrating:
- Instructor-powered OpenAI completions
- Michigan dataset insights
- Risk scoring + behavioral theory explanation
- Cooling period + nudge generation
"""

import json
import functools
import importlib
from typing import Any
import streamlit as st

instructor = importlib.import_module("instructor") if importlib.util.find_spec("instructor") else None
from openai import OpenAI
from pydantic import BaseModel
from config.settings import OPENAI_CHAT_MODEL

# ------------------------------------------------------------------------
# Embedded behavioral insights from CSVs (pre-extracted)
# ------------------------------------------------------------------------

HUMAN_TONE_RULES = """
Speak in warm, everyday language (second‑person “you”).
✅ Mention the behavioral idea in plain English (e.g., “research shows a short pause helps”)
🚫 Do NOT cite specific study numbers, academic jargon, or dataset names.
Keep it under 60 words.
"""


BEHAVIORAL_INSIGHTS = """
Key findings from three behavioral studies:

1. Study 3 (cooling delays):
   - Average cooling effect = 0.022
   - High-frequency impulse buyers: 0.020
   - Low-frequency impulse buyers: 0.023
   ➤ Delaying purchases can lower urge, especially for low-frequency buyers.

2. Study 4 (10-minute Amazon pause):
   - Users added only 0.35 impulse items after delay.
   ➤ Even short pauses discourage spontaneous spending.

3. Study 5 (reflection vs distraction):
   - Reflection reduced buying urge by 0.49 points.
   - Distraction reduced urge by 0.60 points.
   ➤ Distraction appears slightly more effective.

Use this research to support your advice to users considering or completing a purchase.
"""

# ------------------------------------------------------------------------
# Singleton OpenAI client setup with instructor mode
# ------------------------------------------------------------------------
@functools.lru_cache(maxsize=1)
def get_clients() -> tuple[OpenAI, Any]:
    if instructor is None:
        raise RuntimeError(
            "Missing dependency 'instructor'. Install requirements with: pip install -r requirements.txt"
        )

    try:
        api_key = st.secrets["openai"]["api_key"]
    except Exception as exc:
        raise RuntimeError(
            "Missing Streamlit secret [openai].api_key. Add it in .streamlit/secrets.toml."
        ) from exc

    if not api_key:
        raise RuntimeError("Empty Streamlit secret [openai].api_key.")
    client = OpenAI(api_key=api_key)
    instruct_client = instructor.from_openai(client, mode=instructor.Mode.TOOLS)
    return client, instruct_client

# ------------------------------------------------------------------------
# Pydantic Models
# ------------------------------------------------------------------------
class ImpulseRiskFactors(BaseModel):
    time_pattern_risk: float
    category_risk: float
    frequency_risk: float
    amount_pattern_risk: float
    budget_risk: float
    total_risk_score: float
    risk_level: str
    explanation: str

class TheoryBasedExplanation(BaseModel):
    primary_theory: str
    theory_explanation: str
    personal_insight: str
    behavioral_tip: str

class CoolingPeriodRecommendation(BaseModel):
    recommended_hours: int
    custom_strategy: str
    implementation_tip: str

# ------------------------------------------------------------------------
# AI Core Functions with Embedded Study Insights
# ------------------------------------------------------------------------
def analyze_transaction_impulse_risk(transaction, user_history, user_profile):
    _, instruct = get_clients()
 

    system_prompt = f"""
    {BEHAVIORAL_INSIGHTS}

    You are a behavioral economics advisor helping users assess impulse risk in purchases.

    Before assigning any score, consider how essential the spending category is.
    Healthcare, Rent, and Utilities are usually essential — treat them as lower impulse-risk unless user history shows erratic patterns.

    Evaluate this transaction based on:
    - Time and frequency
    - Spending category (with importance weight)
    - Budget burden and emotional context

    Return individual risk scores, a total score, a risk level (Low/Med/High), and a brief explanation in 2 sentences.
    """

    return instruct.chat.completions.create(
        model=OPENAI_CHAT_MODEL,
        response_model=ImpulseRiskFactors,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": json.dumps({"transaction": transaction, "user_profile": user_profile, "history": user_history})}
        ]
    )

def generate_theory_explanation(transaction_data, risk_assessment):
    _, instruct = get_clients()

    system_prompt = f"""
{BEHAVIORAL_INSIGHTS}

{HUMAN_TONE_RULES}

A user is deciding whether to complete this {risk_assessment.risk_level}‑risk purchase.
Give a short rationale (1–2 sentences) and one practical micro‑habit or tip.
"""

    return instruct.chat.completions.create(
        model=OPENAI_CHAT_MODEL,
        response_model=TheoryBasedExplanation,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": json.dumps({
                "transaction": transaction_data,
                "assessment": risk_assessment.model_dump()
            })}
        ]
    )

def generate_cooling_recommendation(user_profile, transaction_history):
    _, instruct = get_clients()
    cancelled = sum(1 for t in transaction_history if t.get("status") == "Cancelled")
    cancelled_rate = cancelled / max(len(transaction_history), 1)
    impulse_freq = min(round(cancelled_rate * 5) + 2, 5)

    prompt = f"""
{BEHAVIORAL_INSIGHTS}

User profile:
- Est. impulse frequency: {impulse_freq}/5
- Cancelled txns: {cancelled_rate:.2f}

Suggest:
1. Recommended cooling hours
2. A custom strategy
3. A small action tip
"""
    return instruct.chat.completions.create(
        model=OPENAI_CHAT_MODEL,
        response_model=CoolingPeriodRecommendation,
        messages=[{"role": "system", "content": prompt}]
    )

def generate_nudge(user_profile, category, amount, risk_level):
    client, _ = get_clients()
    prompt = f"""
{BEHAVIORAL_INSIGHTS}

Write a short nudge (<160 characters) for someone about to spend ${amount} on {category}.
- Risk: {risk_level}
- Budget: ${user_profile['monthly_budget']}
Tone: supportive, simple, 5th-grade level.
"""
    res = client.chat.completions.create(
        model=OPENAI_CHAT_MODEL,
        messages=[{"role": "system", "content": prompt}]
    )
    return res.choices[0].message.content.strip()


# ------------------------------------------------------------------------
# Financial Insights for Dashboard – Enhanced Format
# ------------------------------------------------------------------------
def generate_dashboard_insights(user_profile: dict, user_history: list) -> str:
    client, _ = get_clients()

    def safe_convert(obj):
        if isinstance(obj, set):
            return list(obj)
        if isinstance(obj, dict):
            return {k: safe_convert(v) for k, v in obj.items()}
        if isinstance(obj, list):
            return [safe_convert(i) for i in obj]
        return obj

    friendly_prompt = """
    You are a kind, practical financial coach.
    The user wants to understand their current spending pattern and how to improve without feeling judged.

    Based on the user's profile and transaction history, generate a friendly summary with these three parts:

    📊 Spending Summary:
    Say where their money is going this month. Mention top 2–3 categories, relative budget use, and tone it positively.

    ⚠️ Red Flags:
    Gently call out anything risky — overspending, sudden spikes, category imbalance, etc. Be direct but not shaming.

    ✅ Try These Next:
    Suggest 2 or 3 specific, encouraging, behavior-based micro tips. Use ideas like:
    - wait-time pauses before big buys
    - planning a shopping day once per week
    - setting soft limits on non-essential categories
    - reminding themselves of their goal (e.g., saving for trip)

    Avoid bullet points. Keep total response to ~150 words.
    Use plain, human language — like a supportive message from a thoughtful friend.
    You can draw on behavioral studies from Michigan research when relevant.
    """

    cleaned_data = safe_convert({
        "user_profile": user_profile,
        "transaction_history": user_history
    })

    response = client.chat.completions.create(
        model=OPENAI_CHAT_MODEL,
        messages=[
            {"role": "system", "content": friendly_prompt},
            {"role": "user", "content": json.dumps(cleaned_data)}
        ]
    )

    return response.choices[0].message.content.strip()


