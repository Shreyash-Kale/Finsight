"""
ML-based impulse risk classifier trained on Michigan behavioral study data (Study3).

Maps transaction features to the study's behavioral feature space, then classifies
impulse risk as Low / Medium / High using a Random Forest pipeline.
"""

import csv
import functools
from pathlib import Path

import numpy as np

# ---------------------------------------------------------------------------
# Category → purchase-intent proxy (1 = essential, 7 = fully discretionary)
# ---------------------------------------------------------------------------
CATEGORY_INTENT = {
    "Healthcare": 1, "Rent": 1, "Utilities": 1, "Insurance": 1,
    "Groceries": 2, "Transportation": 2, "Education": 2,
    "Food & Dining": 4, "Personal Care": 4, "Subscriptions": 3,
    "Shopping": 6, "Entertainment": 6, "Clothing": 6,
    "Travel": 6, "Gifts": 5, "Electronics": 6,
    "Other": 4,
}

# Fixed costs are always Low — these are non-negotiable recurring expenses
FIXED_COST_CATEGORIES = {"Rent", "Utilities", "Insurance"}

# Essential categories are Low unless they heavily strain the budget (>25%)
ESSENTIAL_CATEGORIES = {"Healthcare", "Groceries", "Education", "Transportation"}

DATA_PATH = Path(__file__).parent.parent / "data" / "Study3_Data_Public_Mar10.csv"


# ---------------------------------------------------------------------------
# Data loading & model training (cached for the process lifetime)
# ---------------------------------------------------------------------------
def _load_study3():
    """
    Return (X, y) arrays from Study3 CSV using the labeled rows only.
    Features: PRE_FeltUrge, PRE_PurchaseIntent, TimeElapsed_Hours, PRE_UrgeIntent_INDEX
    Note: ImpulseBuyngFreq is excluded — it directly encodes the target label.
    """
    X, y = [], []
    with open(DATA_PATH, newline="", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            label = row.get("ImpFreq_HighLow", "").strip()
            if label not in ("0", "1"):
                continue
            try:
                X.append([
                    float(row["PRE_FeltUrge"]),
                    float(row["PRE_PurchaseIntent"]),
                    float(row["TimeElapsed_Hours"]),
                    float(row["PRE_UrgeIntent_INDEX"]),
                ])
                y.append(int(label))
            except (ValueError, KeyError):
                continue
    return np.array(X), np.array(y)


@functools.lru_cache(maxsize=1)
def _get_model():
    """Train and cache a RandomForest pipeline (runs once per process)."""
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.pipeline import Pipeline
    from sklearn.preprocessing import StandardScaler

    X, y = _load_study3()
    pipeline = Pipeline([
        ("scaler", StandardScaler()),
        ("clf", RandomForestClassifier(
            n_estimators=150,
            class_weight="balanced",
            random_state=42,
        )),
    ])
    pipeline.fit(X, y)
    return pipeline


# ---------------------------------------------------------------------------
# Feature mapping: transaction → study feature space
# ---------------------------------------------------------------------------
def _extract_features(transaction: dict, user_profile: dict, user_history: list) -> list:
    """
    Map a Finsight transaction to Study3 feature space:
      [felt_urge, purchase_intent, time_elapsed_hrs, urge_intent_idx]
    """
    amount   = float(transaction.get("amount", 0))
    category = transaction.get("category", "Other")
    budget   = float(user_profile.get("monthly_budget") or 1)

    # Feature 1 – felt_urge proxy (1-7): higher spend relative to budget → more urge
    budget_ratio = amount / budget
    felt_urge = float(min(7.0, max(1.0, 1.0 + budget_ratio * 30)))

    # Feature 2 – purchase_intent proxy (1-7): discretionary categories score higher
    purchase_intent = float(CATEGORY_INTENT.get(category, 4))

    # Feature 3 – time_elapsed proxy (hours): late-night → impulsive (low elapsed)
    hour = _parse_hour(transaction.get("date", ""))
    if hour is None:
        time_elapsed = 12.0
    elif hour >= 22 or hour <= 3:
        time_elapsed = 1.0   # very impulsive window
    elif 6 <= hour <= 12:
        time_elapsed = 18.0  # planned morning purchase
    else:
        time_elapsed = 10.0

    # Feature 4 – composite urge-intent index
    urge_intent_idx = (felt_urge + purchase_intent) / 2.0

    return [felt_urge, purchase_intent, time_elapsed, urge_intent_idx]


def _parse_hour(date_str: str):
    """Return the hour (int) from an ISO datetime string, or None on failure."""
    if not date_str:
        return None
    try:
        from datetime import datetime
        # Handles both 'YYYY-MM-DDTHH:MM:SS...' and 'YYYY-MM-DD HH:MM AM/PM EST'
        for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %I:%M %p %Z", "%Y-%m-%d %I:%M %p"):
            try:
                return datetime.strptime(date_str[:25], fmt).hour
            except ValueError:
                continue
        # Last resort: grab the hour from the time portion
        parts = date_str.split()
        if len(parts) >= 2:
            return int(parts[1].split(":")[0])
    except Exception:
        pass
    return None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
def classify_impulse_risk(
    transaction: dict,
    user_profile: dict,
    user_history: list,
) -> dict:
    """
    Classify a transaction's impulse risk using the trained Random Forest.

    Returns a dict with:
      risk_level             – "Low" | "Medium" | "High"
      high_impulse_prob      – float 0-1
      time_pattern_risk      – 0-100
      category_risk          – 0-100
      frequency_risk         – 0-100
      amount_pattern_risk    – 0-100
      budget_risk            – 0-100
      explanation            – plain-text summary
    """
    model    = _get_model()
    features = _extract_features(transaction, user_profile, user_history)
    proba    = model.predict_proba(np.array([features]))[0]
    high_prob = float(proba[1])

    category = transaction.get("category", "Other")
    budget_ratio = float(transaction.get("amount", 0)) / float(user_profile.get("monthly_budget") or 1)

    # Fixed costs (rent, utilities, insurance) are never impulse purchases
    if category in FIXED_COST_CATEGORIES:
        risk_level = "Low"
    # Essential categories are Low unless they're unusually large (>25% of budget)
    elif category in ESSENTIAL_CATEGORIES and budget_ratio < 0.25:
        risk_level = "Low"
    elif high_prob < 0.50:
        risk_level = "Low"
    elif high_prob < 0.75:
        risk_level = "Medium"
    else:
        risk_level = "High"

    felt_urge, purchase_intent, time_elapsed, _ = features
    budget = float(user_profile.get("monthly_budget") or 1)
    amount = float(transaction.get("amount", 0))

    # Cancellation-rate risk computed separately (not a model feature)
    cancelled = sum(1 for t in user_history if t.get("status") == "Cancelled")
    cancelled_rate = cancelled / max(len(user_history), 1)

    time_risk   = round(min(100.0, (1.0 / max(time_elapsed, 0.1)) * 20), 1)
    cat_risk    = round((purchase_intent / 7.0) * 100, 1)
    freq_risk   = round(cancelled_rate * 100, 1)
    amount_risk = round(((felt_urge - 1) / 6.0) * 100, 1)
    budget_risk = round(min(100.0, (amount / budget) * 200), 1)

    explanation = (
        f"{risk_level} impulse risk (confidence {high_prob:.0%}). "
        f"Top drivers: category ({cat_risk:.0f}/100), "
        f"budget burden ({budget_risk:.0f}/100), "
        f"cancellation history ({freq_risk:.0f}/100)."
    )

    return {
        "risk_level":          risk_level,
        "high_impulse_prob":   round(high_prob, 3),
        "time_pattern_risk":   time_risk,
        "category_risk":       cat_risk,
        "frequency_risk":      freq_risk,
        "amount_pattern_risk": amount_risk,
        "budget_risk":         budget_risk,
        "explanation":         explanation,
    }
