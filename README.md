# Finsight

Finsight is an AI-assisted personal finance app built with Streamlit. It helps users log spending, flag potentially impulsive purchases, and get behavior-aware suggestions before or after transactions.

## What It Does

- Tracks transactions by status: `Completed`, `Hold`, `Cancelled`
- Shows budget usage, balance, and category trends
- Generates AI feedback for completed purchases
- Provides AI recommendations for pending purchases
- Uses short behavioral nudges and cooling-period suggestions

## Tech Stack

- Python
- Streamlit
- MongoDB (`pymongo`)
- OpenAI API + `instructor` for structured outputs

## Project Structure

- `app.py`: Streamlit entrypoint and page routing
- `ai/logic.py`: AI/risk logic (risk scoring, nudges, recommendations, insights)
- `services/`: App services (`auth_service.py`, `db_service.py`, `state_service.py`, `transaction_service.py`)
- `ui/pages/`: Page rendering modules (`auth_pages.py`, `dashboard.py`, `transaction_pages.py`)
- `ui/components/`: Shared UI components (`sidebar.py`)
- `config/settings.py`: Shared runtime configuration
- `requirements.txt`: Python dependencies
- `data/`: Study CSV files used as behavioral context references

## Architecture

The app follows a simple layered structure:

- `app.py` routes session page state to UI page modules and wires dependencies.
- `ui/pages/*` renders Streamlit screens.
- `ui/components/*` contains reusable UI pieces used across pages.
- `services/*` handles data access, authentication, session defaults, and transaction business logic.
- `ai/logic.py` contains all OpenAI + behavioral inference logic.
- `config/settings.py` stores shared runtime constants.

Module map:

```text
app.py
	-> ui/pages/auth_pages.py
	-> ui/pages/dashboard.py
	-> ui/pages/transaction_pages.py
	-> ui/components/sidebar.py
	-> services/auth_service.py
	-> services/db_service.py
	-> services/state_service.py
	-> services/transaction_service.py
	-> ai/logic.py
	-> config/settings.py
```

## Requirements

- Python 3.8+
- MongoDB instance (local or cloud)
- OpenAI API key

## Setup

1. Clone and enter the project:

```bash
git clone https://github.com/Shreyash-Kale/Finsight
cd finsight
```

2. Create and activate a virtual environment:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

3. Install dependencies:

```bash
pip install -r requirements.txt
```

4. Create Streamlit secrets at `.streamlit/secrets.toml`:

```toml
[openai]
api_key = "YOUR_OPENAI_API_KEY"

[mongo]
mongo_url = "YOUR_MONGODB_CONNECTION_STRING"
```

## Run

```bash
streamlit run app.py
```

Then open the local URL shown in your terminal (usually `http://localhost:8501`).

## Basic Usage

1. Register and log in.
2. Set monthly budget and income.
3. Log completed or pending transactions.
4. Review dashboard metrics and AI insights.
5. Update pending transactions to complete, hold, or cancel.

## Notes

- Passwords are hashed before storage.
- OpenAI and Mongo credentials are read from Streamlit secrets, not environment variables.
