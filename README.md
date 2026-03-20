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

- `HCAI.py`: Main Streamlit app (UI, auth flow, dashboard, transaction workflows)
- `ai_logic.py`: AI/risk logic (risk scoring, nudges, recommendations, insights)
- `requirements.txt`: Python dependencies
- `data/`: Study CSV files used as behavioral context references

## Requirements

- Python 3.8+
- MongoDB instance (local or cloud)
- OpenAI API key

## Setup

1. Clone and enter the project:

```bash
git clone https://github.com/adph/finsight
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
streamlit run HCAI.py
```

Then open the local URL shown in your terminal (usually `http://localhost:8501`).

## Basic Usage

1. Register and log in.
2. Set monthly budget and income.
3. Log completed or pending transactions.
4. Review dashboard metrics and AI insights.
5. Update pending transactions to complete, hold, or cancel.

## Notes

- Current implementation stores user passwords directly in MongoDB; this should be replaced with hashed passwords before production use.
- OpenAI and Mongo credentials are read from Streamlit secrets, not environment variables.
