import streamlit as st
from pymongo import MongoClient
import pandas as pd
import datetime
from bson.decimal128 import Decimal128
from decimal import Decimal
from bson.objectid import ObjectId
from datetime import datetime, timedelta
from pytz import timezone as pytz_timezone

from streamlit_theme import st_theme
import openai
from openai import OpenAI
import json

from ai_logic import (
    analyze_transaction_impulse_risk,
    generate_theory_explanation,
    generate_cooling_recommendation,
    generate_nudge,
    generate_dashboard_insights
)

st.set_page_config(layout="wide")


def clean_for_ai(obj):
    """Recursively convert all MongoDB-specific objects to JSON-safe types."""
    if isinstance(obj, Decimal128):
        return float(obj.to_decimal())
    elif isinstance(obj, Decimal):
        return float(obj)
    elif isinstance(obj, datetime):
        return obj.isoformat()
    elif isinstance(obj, ObjectId):
        return str(obj)
    elif isinstance(obj, dict):
        return {k: clean_for_ai(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [clean_for_ai(i) for i in obj]
    else:
        return obj

def make_timestamp(selected_date=None, selected_time=None, *, auto=False):
    """Return a US/Eastern tz-aware datetime object.
    auto=True → current moment
    manual    → combine date/time pickers (default: today @ 00:00)
    """
    if auto:
        return datetime.now(est_timezone)

    selected_date = selected_date or datetime.today().date()
    selected_time = selected_time or datetime.min.time()
    naive_dt = datetime.combine(selected_date, selected_time)
    return est_timezone.localize(naive_dt)


def color_table(row, color):
    return [f'background-color: {color}'] * len(row)

def get_theme_colors():
    """Get appropriate colors based on current theme"""
    theme = st_theme()
    is_dark = theme.get("base") == "dark" if theme else False
    
    return {
        'completed': '#5dd96a' if not is_dark else '#193929',  # Light green / Dark green
        'cancelled': '#d95d5d' if not is_dark else '#5e1919',  # Light red / Dark red
        'onhold': '#d9a55d' if not is_dark else '#5e4219',     # Light yellow / Dark orange
    }

@st.cache_resource
def get_openai_client():
    client = OpenAI(api_key=st.secrets["openai"]["api_key"])
    return client

# MongoDB Setup
@st.cache_resource
def get_mongo_connection():
    # Connect to MongoDB using credentials from secrets.toml
    client = MongoClient(st.secrets["mongo"]["mongo_url"])
    db = client['finsight_db']  # Database name
    return db

db = get_mongo_connection()
user_data_collection = db['user_data']
txn_data_collection = db['txn_data']

def insert_user_data(data):
    try:
        user_data_collection.insert_one(data)
        return True
    except Exception as e:
        st.error(f"Error inserting data: {e}")
        return False
    
def insert_complete_txn_data(data):
    try:
        txn_data_collection.insert_one(data)
        return True
    except Exception as e:
        st.error(f"Error inserting data: {e}")
        return False

def check_email_exists(email):
    return user_data_collection.find_one({"email": email}) is not None

def verify_login(email,password):
    return user_data_collection.find_one({"email": email, "password": password})

def update_transaction_status(txn_id, new_status):
    """Update the status of a transaction in MongoDB"""
    try:
        result = txn_data_collection.update_one(
            {"_id": txn_id},
            {"$set": {"status": new_status}}
        )
        return result.modified_count > 0
    except Exception as e:
        st.error(f"Error updating transaction: {e}")
        return False

# Function to retrieve user's transaction history
def get_user_transactions(email):
    """Get all transaction data for a user"""
    try:
        # Find all transactions for this user
        transactions = list(txn_data_collection.find({"email": email}))
        
        # Process transactions for API consumption
        processed_txns = []
        for txn in transactions:
            processed_txns.append({
                "category": txn["category"],
                "amount": float(txn["amount"].to_decimal()),
                "description": txn["description"],
                "status": txn["status"],
                "date": txn["txn_datetime"].astimezone(est_timezone).strftime('%Y-%m-%d %I:%M %p EST')

            })
        
        return processed_txns
    except Exception as e:
        st.error(f"Error retrieving transactions: {str(e)}")
        return []

def test_openai_connection():
    """Test OpenAI API connection"""
    try:
        client = get_openai_client()
        response = client.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": "Hello, are you working?"}
            ],
            max_tokens=50
        )
        return True, response.choices[0].message.content
    except Exception as e:
        return False, str(e)

# 1. Transaction Feedback Function
# def generate_transaction_feedback(transaction):
#     """Generate feedback on a completed transaction"""
#     try:
#         # Get user's transaction history
#         user_history = get_user_transactions(st.session_state.email)

#         if hasattr(transaction['amount'], 'to_decimal'):
#             transaction_amount = float(transaction['amount'].to_decimal())
#         else:
#             transaction_amount = float(transaction['amount'])
        
#         # Create the prompt
#         prompt = f"""
#         You are a financial advisor assistant helping a user track their spending habits. 
#         The user has just added this expense:
#         - Category: {transaction['category']}
#         - Amount: ${transaction_amount}
#         - Description: {transaction['description']}
#         - Date: {transaction['txn_datetime'].astimezone(est_timezone).strftime('%Y-%m-%d %H:%M:%S')}
        
#         User's monthly budget: ${st.session_state.monthly_budget:.2f}
#         User's previous transactions: {json.dumps(user_history[-15:] if len(user_history) > 10 else user_history)}
        
#         Provide a brief, insightful analysis of this expense considering:
#         1. How it fits within their monthly budget
#         2. Patterns compared to previous spending in this category
#         3. One actionable tip to help them manage this type of expense better
        
#         Keep your response under 100 words and focus on being helpful, not judgmental.
#         """
        
#         # Call OpenAI API
#         client = get_openai_client()
#         response = client.chat.completions.create(
#             model="gpt-4",
#             messages=[
#                 {"role": "system", "content": "You are a helpful financial assistant."},
#                 {"role": "user", "content": prompt}
#             ],
#             max_tokens=150,
#             temperature=0.7
#         )
        
#         return response.choices[0].message.content
#     except Exception as e:
#         return f"AI analysis unavailable at the moment. Error: {str(e)}"

def generate_transaction_feedback(transaction):
    try:
        user_history = get_user_transactions(st.session_state.email)
        user_profile = {
            "monthly_budget": st.session_state.monthly_budget,
            "monthly_income": st.session_state.monthly_income
        }

        safe_transaction = clean_for_ai(transaction)
        risk = analyze_transaction_impulse_risk(safe_transaction, user_history, user_profile)
        tip = generate_theory_explanation(safe_transaction, risk)
        nudge = generate_nudge(user_profile, safe_transaction["category"], safe_transaction["amount"], risk.risk_level)

        if risk.risk_level.lower() == "low":
            return (
                f"You spent ${safe_transaction['amount']} on {safe_transaction['category']}."
                f" This seems reasonable based on your habits and budget. Keep it up!"
            )
        elif risk.risk_level.lower() == "medium":
            return (
                f"You just spent ${safe_transaction['amount']} on {safe_transaction['category']}."
                f" This isn't unusually high, but it might be worth pausing next time. "
                f"Try this: {tip.behavioral_tip}. "
                f"{nudge}"
            )
        else:  # High impulse
            return (
                f"You spent ${safe_transaction['amount']} on {safe_transaction['category']}, "
                f"which seems impulsive given your recent patterns. "
                f"{tip.theory_explanation} Try this next time: {tip.behavioral_tip} "
                f"({tip.primary_theory}). {nudge}"
            )

    except Exception as e:
        return f"⚠️ AI analysis failed: {str(e)}"



# 2. Transaction Recommendation Function
# def generate_transaction_recommendation(pending_txn):
#     """Generate recommendation for a pending transaction"""
#     try:
#         # Get user's transaction history
#         user_history = get_user_transactions(st.session_state.email)

#         if hasattr(pending_txn['amount'], 'to_decimal'):
#             pending_transaction_amount = float(pending_txn['amount'].to_decimal())
#         else:
#             pending_transaction_amount = float(pending_txn['amount'])
        
#         # Calculate remaining budget
#         completed_expenses = sum(float(txn["amount"]) for txn in user_history if txn["status"] == "Completed")
#         remaining_budget = st.session_state.monthly_budget - completed_expenses
        
#         # Create the prompt
#         prompt = f"""
#         You are a financial advisor assistant helping a user decide whether to complete, postpone, or cancel a pending expense.
        
#         Pending expense details:
#         - Category: {pending_txn['category']}
#         - Amount: ${pending_transaction_amount}
#         - Description: {pending_txn['description']}
        
#         User's financial situation:
#         - Monthly budget: ${st.session_state.monthly_budget:.2f}
#         - Remaining budget: ${remaining_budget:.2f}
#         - Monthly income: ${st.session_state.monthly_income:.2f}
        
#         Transaction history summary:
#         {json.dumps(user_history[-15:] if len(user_history) > 5 else user_history)}
        
#         Based on this information, recommend whether the user should COMPLETE, POSTPONE, or CANCEL this transaction.
#         Explain your reasoning in 2-3 sentences and be direct with your recommendation.
#         """
        
#         # Call OpenAI API
#         client = get_openai_client()
#         response = client.chat.completions.create(
#             model="gpt-4",
#             messages=[
#                 {"role": "system", "content": "You are a helpful financial assistant."},
#                 {"role": "user", "content": prompt}
#             ],
#             max_tokens=150,
#             temperature=0.7
#         )
        
#         return response.choices[0].message.content
#     except Exception as e:
#         return f"AI recommendation unavailable at the moment. Error: {str(e)}"

def generate_transaction_recommendation(pending_txn):
    try:
        user_history = get_user_transactions(st.session_state.email)
        user_profile = {
            "monthly_budget": st.session_state.monthly_budget,
            "monthly_income": st.session_state.monthly_income
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
        elif risk.risk_level.lower() == "medium":
            return (
                f"This expense seems okay, but there’s a chance it’s a bit impulsive. "
                f"You might benefit from a short pause before finalizing. "
                f"Try {cooling.custom_strategy.lower()}. "
                f"Also, {tip.behavioral_tip} ({tip.primary_theory}). "
                f"{nudge}"
            )
        else:  # High
            return (
                f"Whoa — this ${pending_txn['amount']} expense for {pending_txn['category']} "
                f"raises a red flag. You've made similar high-risk decisions recently. "
                f"Take a break for at least {cooling.recommended_hours} hours. During that time, "
                f"{cooling.implementation_tip}. "
                f"{tip.theory_explanation} ({tip.primary_theory}) "
                f"Think it through before you hit 'Complete'. {nudge}"
            )

    except Exception as e:
        return f"⚠️ AI recommendation failed: {str(e)}"





# 3. Financial Insights Function
def generate_financial_insights():
    """Generate comprehensive financial insights for dashboard"""
    try:
        # Get user's transaction history
        user_history = get_user_transactions(st.session_state.email)
        
        # Check if user has enough transactions
        if len(user_history) < 10:
            return "Log more transactions to get AI insights..."
        
        # Calculate insights
        total_spent = sum(float(txn["amount"]) for txn in user_history if txn["status"] == "Completed")
        categories = {}
        for txn in user_history:
            if txn["status"] == "Completed":
                cat = txn["category"]
                if cat in categories:
                    categories[cat] += float(txn["amount"])
                else:
                    categories[cat] = float(txn["amount"])
        
        # Find top spending categories
        top_categories = sorted(categories.items(), key=lambda x: x[1], reverse=True)[:3]
        
        # Create the prompt
        prompt = f"""
        You are a financial advisor assistant providing insights on a user's spending habits.
        
        User's financial summary:
        - Monthly budget: ${st.session_state.monthly_budget:.2f}
        - Monthly income: ${st.session_state.monthly_income:.2f}
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
        
        # Call OpenAI API
        client = get_openai_client()
        response = client.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "You are a helpful financial assistant."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=300,
            temperature=0.7
        )
        
        return response.choices[0].message.content
    except Exception as e:
        return f"AI insights unavailable at the moment. Error: {str(e)}"



est_timezone = pytz_timezone('US/Eastern')


def main():
    # Initialize session state variables
    if 'page' not in st.session_state:
        st.session_state.page = 'welcome'
    if 'user_logged_in' not in st.session_state:
        st.session_state.user_logged_in = False
    if 'email' not in st.session_state:
        st.session_state.email = ''
    if 'name' not in st.session_state:
        st.session_state.name = ''
    if 'expenses' not in st.session_state:
        st.session_state.expenses = pd.DataFrame(columns=['date', 'category', 'amount', 'description'])
    if 'income' not in st.session_state:
        st.session_state.income = pd.DataFrame(columns=['date', 'source', 'amount', 'description'])
    if 'monthly_budget' not in st.session_state:
        st.session_state.monthly_budget = 0.00
    if 'monthly_income' not in st.session_state:
        st.session_state.monthly_income = 0.00
    if 'show_budget_edit' not in st.session_state:
        st.session_state.show_budget_edit = False
    if 'show_income_edit' not in st.session_state:
        st.session_state.show_income_edit = False
    
    if 'openai_tested' not in st.session_state:
        success, message = test_openai_connection()
        if not success:
            st.error(f"OpenAI connection failed: {message}")
        st.session_state.openai_tested = True


    # Navigation sidebar (only show when logged in)
    if st.session_state.user_logged_in:
        with st.sidebar:
            st.title(f"Hello, {st.session_state.name}!")
            
            # Edit Monthly Budget section
            if st.button('Edit Monthly Budget'):
                # Make dropdowns mutually exclusive
                st.session_state.show_budget_edit = not st.session_state.show_budget_edit
                if st.session_state.show_budget_edit:
                    st.session_state.show_income_edit = False
                st.rerun()
            
            if st.session_state.show_budget_edit:
                with st.container():
                    col1, col2 = st.columns([3, 1])
                    with col1:
                        new_budget = st.number_input('New Monthly Budget ($)', 
                                                  min_value=0.0, 
                                                  value=float(st.session_state.monthly_budget),
                                                  step=10.0,
                                                  format="%.2f")
                    with col2:
                        if st.button('', key='budget_done',icon='☑️'):
                            user_data_collection.update_one(
                                {"email": st.session_state.email},
                                {"$set": {
                                    "monthly_budget": Decimal128(Decimal(str(new_budget)))
                                }}
                            )
                            st.session_state.monthly_budget = float(new_budget)
                            st.session_state.show_budget_edit = False
                            st.session_state.page = 'dashboard'
                            st.rerun()
            
            # Edit Monthly Income section
            if st.button('Edit Monthly Income'):
                # Make dropdowns mutually exclusive
                st.session_state.show_income_edit = not st.session_state.show_income_edit
                if st.session_state.show_income_edit:
                    st.session_state.show_budget_edit = False
                st.rerun()
            
            if st.session_state.show_income_edit:
                with st.container():
                    col1, col2 = st.columns([3, 1])
                    with col1:
                        new_income = st.number_input('New Monthly Income ($)', 
                                                  min_value=0.0, 
                                                  value=float(st.session_state.monthly_income),
                                                  step=10.0,
                                                  format="%.2f")
                    with col2:
                        if st.button('', key='budget_done',icon='☑️'):
                            user_data_collection.update_one(
                                {"email": st.session_state.email},
                                {"$set": {
                                    "monthly_income": Decimal128(Decimal(str(new_income)))
                                }}
                            )
                            st.session_state.monthly_income = float(new_income)
                            st.session_state.show_income_edit = False
                            st.session_state.page = 'dashboard'
                            st.rerun()
                
            if st.button('Logout'):
                st.session_state.user_logged_in = False
                st.session_state.name = ''
                st.session_state.page = 'welcome'
                st.rerun()

    # Render appropriate page based on session state
    if st.session_state.page == 'welcome':
        render_welcome_page()
    elif st.session_state.page == 'register':
        render_register_page()
    elif st.session_state.page == 'login':
        render_login_page()
    elif st.session_state.page == 'dashboard':
        render_dashboard()
    elif st.session_state.page == 'add_complete_expense':
        render_add_complete_expense_page()
    elif st.session_state.page == 'add_income':
        render_add_income_page()
    elif st.session_state.page == 'transactions':
        render_transactions_page()
    elif st.session_state.page == 'add_pending_expense':
        render_add_pending_expense_page()


def render_welcome_page():
    st.title('Finsight')
    st.write('AI assisted budget tracking')

    
    if st.button('Login'):
        st.session_state.page = 'login'
        st.rerun()

    if st.button('Register'):
        st.session_state.page = 'register'
        st.rerun()

def render_register_page():
    st.title('Register')
    
    name = st.text_input('Name')
    email = st.text_input('Email')
    password = st.text_input('Password', type='password')
    budget = st.text_input('Monthly Budget')
    income = st.text_input('Monthly Income')
    
    col1, col2 = st.columns(2)

    with col1:
        if st.button('Back'):
            st.session_state.page = 'welcome'
            st.rerun()
    
    with col2:
        if st.button('Register'):
            # In a real app, we would save this data
            data = {
                'email': email,
                'password': password,
                'name': name,
                'monthly_budget': Decimal128(Decimal(str(budget))),
                'monthly_income': Decimal128(Decimal(str(income)))
            }
            # Check if Prolific ID already exists
            if check_email_exists(data['email']):
                st.error("Error: This Prolific ID has already been used.")
            else:
                # Insert data into the database
                if insert_user_data(data):
                    st.success("Data saved successfully!")
                else:
                    st.error("Error: Failed to save data. Please try again.")
            st.success('Registration successful! Please log in.')
            st.session_state.page = 'welcome'
            st.rerun()

def render_login_page():
    st.title('Login')
    
    email = st.text_input('Email')
    password = st.text_input('Password', type='password')
    
    if st.button('Login', key='login_button'):
        # In a real app, we would verify credentials
        login = verify_login(email,password)
        if login:
            st.session_state.user_logged_in = True
            st.session_state.email = email
            st.session_state.name = login['name']
            st.session_state.monthly_budget = float(login['monthly_budget'].to_decimal())
            st.session_state.monthly_income = float(login['monthly_income'].to_decimal())
            st.session_state.page = 'dashboard'
            st.rerun()
        else:
            st.error("Error: Incorrect Email/Password")

    if st.button('Back'):
        st.session_state.page = 'welcome'
        st.rerun()
    


def render_dashboard():


    colors = get_theme_colors()
    st.title('Finsight Dashboard')
    st.subheader(f'Welcome back, {st.session_state.name}!')
    
    # Summary metrics
    col1, col2, col3, col4, col5 = st.columns(5)
    

    with col1:
        st.metric(label="Monthly Budget", value=f"${st.session_state.monthly_budget:.2f}")
    
    with col2:
        st.metric(label="Monthly Income", value=f"${st.session_state.monthly_income:.2f}")

    with col3:
        # Aggregate total expenses directly from MongoDB
        pipeline = [
            {"$match": {"email": st.session_state.email, "status": "Completed"}},
            {"$group": {"_id": None, "totalAmount": {"$sum": "$amount"}}}
        ]

        result = txn_data_collection.aggregate(pipeline)

        # Extract the total amount from the aggregation result
        try:
            total_expenses = next(result)["totalAmount"]
            # If amount is Decimal128, convert to float for display
            if hasattr(total_expenses, "to_decimal"):
                total_expenses = float(total_expenses.to_decimal())
            else:
                total_expenses = float(total_expenses)
        except StopIteration:
            total_expenses = 0.0

        # Use total_expenses in your dashboard display
        st.metric(label="Total Expenses", value=f"${total_expenses:.2f}")
    
    with col4:
        # Aggregate total expenses directly from MongoDB
        pipeline = [
            {"$match": {"email": st.session_state.email, "status": "Cancelled"}},
            {"$group": {"_id": None, "totalAmount": {"$sum": "$amount"}}}
        ]

        c_result = txn_data_collection.aggregate(pipeline)

        try:
            cancelled_expenses = next(c_result)["totalAmount"]
            # If amount is Decimal128, convert to float for display
            if hasattr(cancelled_expenses, "to_decimal"):
                cancelled_expenses = float(cancelled_expenses.to_decimal())
            else:
                cancelled_expenses = float(cancelled_expenses)
        except StopIteration:
            cancelled_expenses = 0.0

        st.metric(label="Expenses Cancelled", value=f"${cancelled_expenses:.2f}")
        
    with col5:
        # Aggregate total expenses directly from MongoDB
        pipeline = [
            {"$match": {"email": st.session_state.email, "status": "Hold"}},
            {"$group": {"_id": None, "totalAmount": {"$sum": "$amount"}}}
        ]

        h_result = txn_data_collection.aggregate(pipeline)

        try:
            onhold_expenses = next(h_result)["totalAmount"]
            # If amount is Decimal128, convert to float for display
            if hasattr(onhold_expenses, "to_decimal"):
                onhold_expenses = float(onhold_expenses.to_decimal())
            else:
                onhold_expenses = float(onhold_expenses)
        except StopIteration:
            onhold_expenses = 0.0

        st.metric(label="Expenses on Hold", value=f"${onhold_expenses:.2f}")
    
    # Balance calculation
    balance = float(st.session_state.monthly_budget) - total_expenses
    if balance >= 0:
        st.success(f"Current Balance: ${balance:.2f}")
    else:
        st.error(f"Current Balance: -${abs(balance):.2f}")
    
    # Budget progress
    try:
        monthly_budget = float(st.session_state.monthly_budget)
        if monthly_budget > 0:
            budget_usage = (total_expenses / monthly_budget) * 100
            progress_value = float(min(budget_usage/100, 1.0))
        else:
            progress_value = 0.0
    except TypeError:
        st.error("Invalid budget value")
        progress_value = 0.0

    st.subheader("Budget Usage")
    st.progress(progress_value)
    st.write(f"{progress_value*100:.1f}% of monthly budget used")

    insights_container = st.container()
    with insights_container:
        # Check if insights already exist in session state
        if 'financial_insights' not in st.session_state:
            # Generate structured dashboard insights with AI
            user_history = get_user_transactions(st.session_state.email)
            user_profile = {
                "monthly_budget": st.session_state.monthly_budget,
                "monthly_income": st.session_state.monthly_income
            }
            st.session_state.financial_insights = generate_dashboard_insights(user_profile, user_history)

            
        # Display insights from session state
        if st.session_state.financial_insights:
            st.subheader("AI Financial Insights")
            st.markdown(st.session_state.financial_insights)

            
            # Optional: Add a refresh button for insights
            if st.button("Refresh Insights"):
                user_history = get_user_transactions(st.session_state.email)
                user_profile = {
                    "monthly_budget": st.session_state.monthly_budget,
                    "monthly_income": st.session_state.monthly_income
                }
                st.session_state.financial_insights = generate_dashboard_insights(user_profile, user_history)
                st.rerun()

    
    # Quick actions
    st.subheader('Quick Actions')
    
    col1, col2 = st.columns(2)

    with col1:
        if st.button('Log a completed transaction'):
            st.session_state.page = 'add_complete_expense'
            st.rerun()

    with col2:
        if st.button('Log Pending Transaction'):
            st.session_state.page = 'add_pending_expense'
            st.session_state.pending_expense_phase = 'details'  # Initialize phase
            st.rerun()
    
    # with col2:
    #     if st.button('Add New Income'):
    #         st.session_state.page = 'add_income'
    #         st.rerun()
    
    completed_section = st.container()
    
    with completed_section:
        st.subheader("Completed Transactions")
        
        try:
            # Query MongoDB for completed transactions
            completed_txns = list(txn_data_collection.find({
                'email': st.session_state.email,
                'status': 'Completed'
            }).sort('txn_datetime', -1))
            
            # Create dataframe
            txn_list = []
            for txn in completed_txns:
                txn_list.append({
                    'txn_datetime': txn['txn_datetime'].astimezone(est_timezone).strftime('%Y-%m-%d %I:%M %p EST')
,
                    'category': txn['category'],
                    'amount': float(txn['amount'].to_decimal()),
                    'description': txn['description'],
                    '_id': str(txn['_id'])
                })
            
            txn_df = pd.DataFrame(txn_list)
            
            if not txn_df.empty:
                # Display dataframe with custom formatting
                styled_df = txn_df.style.apply(lambda x: [f'background-color: {colors["completed"]}']*len(x), axis=1)
                st.dataframe(
                    styled_df,
                    column_config={
                        "txn_datetime": "Date/Time (EST)",
                        "category": "Category",
                        "amount": st.column_config.NumberColumn(
                            "Amount", format="$%.2f",
                        ),
                        "description": "Description",
                        "_id": None
                    },
                    hide_index=True,
                    use_container_width=True
                )
                
                # Pagination logic
                def change_completed_page(direction):
                    if direction == "next":
                        st.session_state.completed_page += 1
                    else:
                        st.session_state.completed_page -= 1
                
                completed_items_per_page = 4
                if 'completed_page' not in st.session_state:
                    st.session_state.completed_page = 0
                    
                total_completed_pages = max(1, len(completed_txns) // completed_items_per_page + 
                                        (1 if len(completed_txns) % completed_items_per_page > 0 else 0))
                
                with st.expander("### Cancel Completed Transactions"):
                    col1, col2, col3 = st.columns([1, 3, 1])
                    with col1:
                        if st.session_state.completed_page > 0:
                            st.button("◀ Previous", on_click=change_completed_page, 
                                    args=("prev",), key="prev_completed")
                    with col3:
                        if st.session_state.completed_page < total_completed_pages - 1:
                            st.button("Next ▶", on_click=change_completed_page, 
                                    args=("next",), key="next_completed")
                    with col2:
                        st.write(f"Page {st.session_state.completed_page + 1} of {total_completed_pages}")
                    
                    # Show transactions for current page
                    start_c_idx = st.session_state.completed_page * completed_items_per_page
                    end_c_idx = min(start_c_idx + completed_items_per_page, len(completed_txns))
                    
                    for i in range(start_c_idx, end_c_idx):
                        txn = completed_txns[i]
                        cols = st.columns([4, 1])
                        with cols[0]:
                            st.write(f"{txn['description'][:20]}{'...' if len(txn['description']) > 20 else ''} - **{txn['category']}** - ${float(txn['amount'].to_decimal()):.2f} ({txn['txn_datetime'].astimezone(est_timezone).strftime('%Y-%m-%d %I:%M %p EST')})")
                        
                        with cols[1]:
                            def cancel_transaction(txn_id):
                                txn_data_collection.update_one(
                                    {'_id': txn_id},
                                    {'$set': {'status': 'Cancelled'}}
                                )
                                st.success("Transaction marked as cancelled!")
                                
                            st.button(f"Cancel", key=f"cancel_{txn['_id']}", 
                                    on_click=cancel_transaction, args=(txn['_id'],))
            else:
                st.info("No completed transactions")
                
        except Exception as e:
            st.error(f"Error loading transactions: {str(e)}")


    st.subheader("Cancelled Transactions")
    
    try:
        # Query MongoDB for completed transactions
        cancelled_txns = txn_data_collection.find({
            'email': st.session_state.email,
            'status': 'Cancelled'
        }).sort('txn_datetime', -1)

        # Convert MongoDB cursor to DataFrame
        c_txn_list = []
        for txn in cancelled_txns:
            c_txn_list.append({
                'txn_datetime': txn['txn_datetime'].astimezone(est_timezone).strftime('%Y-%m-%d %I:%M %p EST')
,
                'category': txn['category'],
                'amount': float(txn['amount'].to_decimal()),
                'description': txn['description']
            })
            
        c_txn_df = pd.DataFrame(c_txn_list)

        if not c_txn_df.empty:
            # Display dataframe with custom formatting
            styled_c_df = c_txn_df.style.apply(lambda x: [f'background-color: {colors["cancelled"]}']*len(x), axis=1)
            st.dataframe(
                styled_c_df,
                column_config={
                    "txn_datetime": "Date/Time (EST)",
                    "category": "Category",
                    "amount": st.column_config.NumberColumn(
                        "Amount",
                        format="$%.2f",
                    ),
                    "description": "Description"
                },
                hide_index=True,
                use_container_width=True
            )
        else:
            st.info("No cancelled transactions")
            
    except Exception as e:
        st.error(f"Error loading transactions: {str(e)}")
    
    onhold_section = st.container()
    with onhold_section:
        st.subheader("On Hold Transactions")
        
        try:
            # Query MongoDB for onhold transactions
            onhold_txns = list(txn_data_collection.find({
                'email': st.session_state.email,
                'status': 'Hold'
            }).sort('txn_datetime', -1))
            
            # Create dataframe
            h_txn_list = []
            for txn in onhold_txns:
                h_txn_list.append({
                    'txn_datetime': txn['txn_datetime'].astimezone(est_timezone).strftime('%Y-%m-%d %I:%M %p EST')
,
                    'category': txn['category'],
                    'amount': float(txn['amount'].to_decimal()),
                    'description': txn['description'],
                    '_id': str(txn['_id'])
                })
            
            h_txn_df = pd.DataFrame(h_txn_list)
            
            if not h_txn_df.empty:
                # Display dataframe
                styled_h_df = h_txn_df.style.apply(lambda x: [f'background-color: {colors["onhold"]}']*len(x), axis=1)
                st.dataframe(
                    styled_h_df,
                    column_config={
                        "txn_datetime": "Date/Time (EST)",
                        "category": "Category",
                        "amount": st.column_config.NumberColumn(
                            "Amount", format="$%.2f",
                        ),
                        "description": "Description",
                        "_id": None
                    },
                    hide_index=True,
                    use_container_width=True
                )
                
                # Pagination with callbacks
                def change_onhold_page(direction):
                    if direction == "next":
                        st.session_state.onhold_page += 1
                    else:
                        st.session_state.onhold_page -= 1
                
                items_per_page = 4
                if 'onhold_page' not in st.session_state:
                    st.session_state.onhold_page = 0
                    
                total_pages = max(1, len(onhold_txns) // items_per_page + 
                            (1 if len(onhold_txns) % items_per_page > 0 else 0))
                
                # Pagination UI
                with st.expander("### Update Transactions On Hold"):
                    col1, col2, col3 = st.columns([1, 3, 1])
                    with col1:
                        if st.session_state.onhold_page > 0:
                            st.button("◀ Previous", on_click=change_onhold_page, 
                                    args=("prev",), key="prev_onhold")
                    with col3:
                        if st.session_state.onhold_page < total_pages - 1:
                            st.button("Next ▶", on_click=change_onhold_page, 
                                    args=("next",), key="next_onhold")
                    with col2:
                        st.write(f"Page {st.session_state.onhold_page + 1} of {total_pages}")
                    
                    # Show transactions for current page
                    start_idx = st.session_state.onhold_page * items_per_page
                    end_idx = min(start_idx + items_per_page, len(onhold_txns))
                    
                    for i in range(start_idx, end_idx):
                        txn = onhold_txns[i]
                        cols = st.columns([4, 1, 1])
                        with cols[0]:
                            st.write(f"{txn['description'][:20]}{'...' if len(txn['description']) > 20 else ''} - **{txn['category']}** - ${float(txn['amount'].to_decimal()):.2f} ({txn['txn_datetime'].astimezone(est_timezone).strftime('%Y-%m-%d %I:%M %p EST')})")
                        
                        with cols[1]:
                            def complete_transaction(txn_id):
                                txn_data_collection.update_one(
                                    {'_id': txn_id},
                                    {'$set': {'status': 'Completed'}}
                                )
                                st.success("Transaction marked as completed!")
                                
                            st.button(f"Complete", key=f"complete_{txn['_id']}", 
                                    on_click=complete_transaction, args=(txn['_id'],))
                        
                        with cols[2]:
                            def cancel_transaction(txn_id):
                                txn_data_collection.update_one(
                                    {'_id': txn_id},
                                    {'$set': {'status': 'Cancelled'}}
                                )
                                st.success("Transaction marked as cancelled!")
                                
                            st.button(f"Cancel", key=f"cancel_h_{txn['_id']}", 
                                    on_click=cancel_transaction, args=(txn['_id'],))
            else:
                st.info("No transactions on hold")
                
        except Exception as e:
            st.error(f"Error loading transactions: {str(e)}")


    
    

def render_add_complete_expense_page():
    st.title('Add Expense')

    category = st.selectbox('Category', [
        'Food', 'Entertainment', 'Shopping', 'Travel', 'Utilities', 
        'Health', 'Groceries', 'Gifts', 'Education'
    ])
    amount = st.number_input('Amount ($)', min_value=0.0, step=0.01)
    description = st.text_input('Description')
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

    if st.button('Add Expense'):
        if not description.strip():
            description_error = True
        else:
            ts = make_timestamp(ui_date, ui_time, auto=False)
            complete_data = {
                'email': st.session_state.email,
                'txn_datetime': ts,
                'category': category,
                'amount': Decimal128(Decimal(str(amount))),
                'description': description,
                'status': 'Completed'
            }
            if insert_complete_txn_data(complete_data):
                safe_txn = clean_for_ai(complete_data)
                feedback = generate_transaction_feedback(safe_txn)
                st.success(f'Expense added successfully!\n\n**AI Feedback**: {feedback}')
            else:
                st.error("Error: Failed to save data. Please try again.")

    if description_error:
        st.warning("Please provide a description for this expense.")

    if st.button('Back to Dashboard'):
        st.session_state.page = 'dashboard'
        st.rerun()

    

def render_add_income_page():
    st.title('Add Income')
    
    date = st.date_input('Date', datetime.datetime.now())
    source = st.selectbox('Source', options=[
        'Salary', 'Freelance', 'Investments', 'Gift', 'Other'
    ])
    amount = st.number_input('Amount ($)', min_value=0.0, step=0.01)
    description = st.text_input('Description (optional)')

    col1, col2 = st.columns(2)
    with col1:
        ui_date = st.date_input("Transaction date", value=datetime.today())
    with col2:
        ui_time_str = st.text_input("Time (HH:MM)", value="12:00")
        try:
            ui_time = datetime.strptime(ui_time_str, "%H:%M").time()
        except ValueError:
            st.warning("Please enter a valid time in HH:MM format (24-hour).")
            return  # prevent processing until valid


    if st.button('Add Expense'):
        ts = make_timestamp(ui_date, ui_time, auto=False)
        st.session_state.pending_expense = {
            'category': category,
            'amount': amount,
            'description': description,
            'txn_datetime': ts
        }
        st.session_state.pending_expense_phase = 'status'
        st.rerun()


def render_transactions_page():
    st.title('Transactions')
    
    # Tabs for expenses and income
    tab1, tab2 = st.tabs(["Expenses", "Income"])
    
    with tab1:
        st.subheader('Your Expenses')
        if not st.session_state.expenses.empty:
            st.dataframe(st.session_state.expenses.sort_values('date', ascending=False))
        else:
            st.info('No expenses recorded yet.')
    
    with tab2:
        st.subheader('Your Income')
        if not st.session_state.income.empty:
            st.dataframe(st.session_state.income.sort_values('date', ascending=False))
        else:
            st.info('No income recorded yet.')
    
    if st.button('Back to Dashboard'):
        st.session_state.page = 'dashboard'
        st.rerun()

def render_add_pending_expense_page():
    st.title('Add Pending Expense')

    if 'pending_expense_phase' not in st.session_state:
        st.session_state.pending_expense_phase = 'details'

    # Phase 1: Collect expense details
    if st.session_state.pending_expense_phase == 'details':
        category = st.selectbox('Category', options=[
            'Food', 'Transport', 'Entertainment', 'Utilities', 
            'Rent', 'Shopping', 'Healthcare', 'Education', 'Other'
        ])
        amount = st.number_input('Amount ($)', min_value=0.00, step=0.1, format="%.2f")
        description = st.text_input('Description')
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

        if st.button('Add Expense'):
            if not description.strip():
                description_error = True
            else:
                txn_time = make_timestamp(ui_date, ui_time)
                st.session_state.pending_expense = {
                    'category': category,
                    'amount': amount,
                    'description': description,
                    'txn_datetime': txn_time
                }
                st.session_state.pending_expense_phase = 'status'
                st.rerun()

        if description_error:
            st.warning("Please provide a description for this expense.")

        if st.button('Back to Dashboard'):
            st.session_state.page = 'dashboard'
            st.rerun()

    # Phase 2: Select transaction status
    elif st.session_state.pending_expense_phase == 'status':
        safe_txn = clean_for_ai(st.session_state.pending_expense)
        recommendation = generate_transaction_recommendation(safe_txn)

        st.info(f"**AI Recommendation**: {recommendation}")
        st.write("Would you like to Cancel, Postpone, or Complete?")

        st.write(f"Category: {st.session_state.pending_expense['category']}")
        st.write(f"Amount: ${st.session_state.pending_expense['amount']:.2f}")
        st.write(f"Description: {st.session_state.pending_expense['description']}")

        for status in ['Cancelled', 'Hold', 'Completed']:
            if st.button(status):
                pending_data = {
                    'email': st.session_state.email,
                    'txn_datetime': st.session_state.pending_expense['txn_datetime'],
                    'category': st.session_state.pending_expense['category'],
                    'amount': Decimal128(Decimal(str(st.session_state.pending_expense['amount']))),
                    'description': st.session_state.pending_expense['description'],
                    'status': status
                }
                if insert_complete_txn_data(pending_data):
                    st.success(f'Expense marked as {status.lower()} and recorded!')
                    st.session_state.pending_expense_phase = 'details'
                    st.session_state.page = 'dashboard'
                    st.rerun()
                else:
                    st.error("Error: Failed to save data. Please try again.")

        if st.button('Back to Details'):
            st.session_state.pending_expense_phase = 'details'
            st.rerun()


if __name__ == '__main__':
    main()
