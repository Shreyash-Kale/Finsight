import pandas as pd
import streamlit as st


def render_dashboard_page(
    *,
    txn_data_collection,
    est_timezone,
    get_theme_colors,
    get_user_transactions,
    generate_dashboard_insights,
):
    colors = get_theme_colors()
    st.title("Finsight Dashboard")
    st.subheader(f"Welcome back, {st.session_state.name}!")

    col1, col2, col3, col4, col5 = st.columns(5)

    with col1:
        st.metric(label="Monthly Budget", value=f"${st.session_state.monthly_budget:.2f}")

    with col2:
        st.metric(label="Monthly Income", value=f"${st.session_state.monthly_income:.2f}")

    with col3:
        pipeline = [
            {"$match": {"email": st.session_state.email, "status": "Completed"}},
            {"$group": {"_id": None, "totalAmount": {"$sum": "$amount"}}},
        ]

        result = txn_data_collection.aggregate(pipeline)

        try:
            total_expenses = next(result)["totalAmount"]
            if hasattr(total_expenses, "to_decimal"):
                total_expenses = float(total_expenses.to_decimal())
            else:
                total_expenses = float(total_expenses)
        except StopIteration:
            total_expenses = 0.0

        st.metric(label="Total Expenses", value=f"${total_expenses:.2f}")

    with col4:
        pipeline = [
            {"$match": {"email": st.session_state.email, "status": "Cancelled"}},
            {"$group": {"_id": None, "totalAmount": {"$sum": "$amount"}}},
        ]

        c_result = txn_data_collection.aggregate(pipeline)

        try:
            cancelled_expenses = next(c_result)["totalAmount"]
            if hasattr(cancelled_expenses, "to_decimal"):
                cancelled_expenses = float(cancelled_expenses.to_decimal())
            else:
                cancelled_expenses = float(cancelled_expenses)
        except StopIteration:
            cancelled_expenses = 0.0

        st.metric(label="Expenses Cancelled", value=f"${cancelled_expenses:.2f}")

    with col5:
        pipeline = [
            {"$match": {"email": st.session_state.email, "status": "Hold"}},
            {"$group": {"_id": None, "totalAmount": {"$sum": "$amount"}}},
        ]

        h_result = txn_data_collection.aggregate(pipeline)

        try:
            onhold_expenses = next(h_result)["totalAmount"]
            if hasattr(onhold_expenses, "to_decimal"):
                onhold_expenses = float(onhold_expenses.to_decimal())
            else:
                onhold_expenses = float(onhold_expenses)
        except StopIteration:
            onhold_expenses = 0.0

        st.metric(label="Expenses on Hold", value=f"${onhold_expenses:.2f}")

    balance = float(st.session_state.monthly_budget) - total_expenses
    if balance >= 0:
        st.success(f"Current Balance: ${balance:.2f}")
    else:
        st.error(f"Current Balance: -${abs(balance):.2f}")

    try:
        monthly_budget = float(st.session_state.monthly_budget)
        if monthly_budget > 0:
            budget_usage = (total_expenses / monthly_budget) * 100
            progress_value = float(min(budget_usage / 100, 1.0))
        else:
            progress_value = 0.0
    except TypeError:
        st.error("Invalid budget value")
        progress_value = 0.0

    st.subheader("Budget Usage")
    st.progress(progress_value)
    st.write(f"{progress_value * 100:.1f}% of monthly budget used")

    insights_container = st.container()
    with insights_container:
        if "financial_insights" not in st.session_state:
            user_history = get_user_transactions(st.session_state.email)
            user_profile = {
                "monthly_budget": st.session_state.monthly_budget,
                "monthly_income": st.session_state.monthly_income,
            }
            st.session_state.financial_insights = generate_dashboard_insights(user_profile, user_history)

        if st.session_state.financial_insights:
            st.subheader("AI Financial Insights")
            st.markdown(st.session_state.financial_insights)

            if st.button("Refresh Insights"):
                user_history = get_user_transactions(st.session_state.email)
                user_profile = {
                    "monthly_budget": st.session_state.monthly_budget,
                    "monthly_income": st.session_state.monthly_income,
                }
                st.session_state.financial_insights = generate_dashboard_insights(user_profile, user_history)
                st.rerun()

    st.subheader("Quick Actions")

    col1, col2 = st.columns(2)

    with col1:
        if st.button("Log a completed transaction"):
            st.session_state.page = "add_complete_expense"
            st.rerun()

    with col2:
        if st.button("Log Pending Transaction"):
            st.session_state.page = "add_pending_expense"
            st.session_state.pending_expense_phase = "details"
            st.rerun()

    completed_section = st.container()

    with completed_section:
        st.subheader("Completed Transactions")

        try:
            completed_txns = list(
                txn_data_collection.find(
                    {
                        "email": st.session_state.email,
                        "status": "Completed",
                    }
                ).sort("txn_datetime", -1)
            )

            txn_list = []
            for txn in completed_txns:
                txn_list.append(
                    {
                        "txn_datetime": txn["txn_datetime"].astimezone(est_timezone).strftime("%Y-%m-%d %I:%M %p EST"),
                        "category": txn["category"],
                        "amount": float(txn["amount"].to_decimal()),
                        "description": txn["description"],
                        "_id": str(txn["_id"]),
                    }
                )

            txn_df = pd.DataFrame(txn_list)

            if not txn_df.empty:
                styled_df = txn_df.style.apply(
                    lambda x: [f'background-color: {colors["completed"]}'] * len(x),
                    axis=1,
                )
                st.dataframe(
                    styled_df,
                    column_config={
                        "txn_datetime": "Date/Time (EST)",
                        "category": "Category",
                        "amount": st.column_config.NumberColumn("Amount", format="$%.2f"),
                        "description": "Description",
                        "_id": None,
                    },
                    hide_index=True,
                    use_container_width=True,
                )

                def change_completed_page(direction):
                    if direction == "next":
                        st.session_state.completed_page += 1
                    else:
                        st.session_state.completed_page -= 1

                completed_items_per_page = 4
                if "completed_page" not in st.session_state:
                    st.session_state.completed_page = 0

                total_completed_pages = max(
                    1,
                    len(completed_txns) // completed_items_per_page
                    + (1 if len(completed_txns) % completed_items_per_page > 0 else 0),
                )

                with st.expander("### Cancel Completed Transactions"):
                    col1, col2, col3 = st.columns([1, 3, 1])
                    with col1:
                        if st.session_state.completed_page > 0:
                            st.button(
                                "< Previous",
                                on_click=change_completed_page,
                                args=("prev",),
                                key="prev_completed",
                            )
                    with col3:
                        if st.session_state.completed_page < total_completed_pages - 1:
                            st.button(
                                "Next >",
                                on_click=change_completed_page,
                                args=("next",),
                                key="next_completed",
                            )
                    with col2:
                        st.write(f"Page {st.session_state.completed_page + 1} of {total_completed_pages}")

                    start_c_idx = st.session_state.completed_page * completed_items_per_page
                    end_c_idx = min(start_c_idx + completed_items_per_page, len(completed_txns))

                    for i in range(start_c_idx, end_c_idx):
                        txn = completed_txns[i]
                        cols = st.columns([4, 1])
                        with cols[0]:
                            st.write(
                                f"{txn['description'][:20]}{'...' if len(txn['description']) > 20 else ''}"
                                f" - **{txn['category']}** - ${float(txn['amount'].to_decimal()):.2f}"
                                f" ({txn['txn_datetime'].astimezone(est_timezone).strftime('%Y-%m-%d %I:%M %p EST')})"
                            )

                        with cols[1]:

                            def cancel_transaction(txn_id):
                                txn_data_collection.update_one(
                                    {"_id": txn_id},
                                    {"$set": {"status": "Cancelled"}},
                                )
                                st.success("Transaction marked as cancelled!")

                            st.button(
                                "Cancel",
                                key=f"cancel_{txn['_id']}",
                                on_click=cancel_transaction,
                                args=(txn["_id"],),
                            )
            else:
                st.info("No completed transactions")

        except Exception as e:
            st.error(f"Error loading transactions: {str(e)}")

    st.subheader("Cancelled Transactions")

    try:
        cancelled_txns = txn_data_collection.find(
            {
                "email": st.session_state.email,
                "status": "Cancelled",
            }
        ).sort("txn_datetime", -1)

        c_txn_list = []
        for txn in cancelled_txns:
            c_txn_list.append(
                {
                    "txn_datetime": txn["txn_datetime"].astimezone(est_timezone).strftime("%Y-%m-%d %I:%M %p EST"),
                    "category": txn["category"],
                    "amount": float(txn["amount"].to_decimal()),
                    "description": txn["description"],
                }
            )

        c_txn_df = pd.DataFrame(c_txn_list)

        if not c_txn_df.empty:
            styled_c_df = c_txn_df.style.apply(
                lambda x: [f'background-color: {colors["cancelled"]}'] * len(x),
                axis=1,
            )
            st.dataframe(
                styled_c_df,
                column_config={
                    "txn_datetime": "Date/Time (EST)",
                    "category": "Category",
                    "amount": st.column_config.NumberColumn("Amount", format="$%.2f"),
                    "description": "Description",
                },
                hide_index=True,
                use_container_width=True,
            )
        else:
            st.info("No cancelled transactions")

    except Exception as e:
        st.error(f"Error loading transactions: {str(e)}")

    onhold_section = st.container()
    with onhold_section:
        st.subheader("On Hold Transactions")

        try:
            onhold_txns = list(
                txn_data_collection.find(
                    {
                        "email": st.session_state.email,
                        "status": "Hold",
                    }
                ).sort("txn_datetime", -1)
            )

            h_txn_list = []
            for txn in onhold_txns:
                h_txn_list.append(
                    {
                        "txn_datetime": txn["txn_datetime"].astimezone(est_timezone).strftime("%Y-%m-%d %I:%M %p EST"),
                        "category": txn["category"],
                        "amount": float(txn["amount"].to_decimal()),
                        "description": txn["description"],
                        "_id": str(txn["_id"]),
                    }
                )

            h_txn_df = pd.DataFrame(h_txn_list)

            if not h_txn_df.empty:
                styled_h_df = h_txn_df.style.apply(
                    lambda x: [f'background-color: {colors["onhold"]}'] * len(x),
                    axis=1,
                )
                st.dataframe(
                    styled_h_df,
                    column_config={
                        "txn_datetime": "Date/Time (EST)",
                        "category": "Category",
                        "amount": st.column_config.NumberColumn("Amount", format="$%.2f"),
                        "description": "Description",
                        "_id": None,
                    },
                    hide_index=True,
                    use_container_width=True,
                )

                def change_onhold_page(direction):
                    if direction == "next":
                        st.session_state.onhold_page += 1
                    else:
                        st.session_state.onhold_page -= 1

                items_per_page = 4
                if "onhold_page" not in st.session_state:
                    st.session_state.onhold_page = 0

                total_pages = max(
                    1,
                    len(onhold_txns) // items_per_page + (1 if len(onhold_txns) % items_per_page > 0 else 0),
                )

                with st.expander("### Update Transactions On Hold"):
                    col1, col2, col3 = st.columns([1, 3, 1])
                    with col1:
                        if st.session_state.onhold_page > 0:
                            st.button(
                                "< Previous",
                                on_click=change_onhold_page,
                                args=("prev",),
                                key="prev_onhold",
                            )
                    with col3:
                        if st.session_state.onhold_page < total_pages - 1:
                            st.button(
                                "Next >",
                                on_click=change_onhold_page,
                                args=("next",),
                                key="next_onhold",
                            )
                    with col2:
                        st.write(f"Page {st.session_state.onhold_page + 1} of {total_pages}")

                    start_idx = st.session_state.onhold_page * items_per_page
                    end_idx = min(start_idx + items_per_page, len(onhold_txns))

                    for i in range(start_idx, end_idx):
                        txn = onhold_txns[i]
                        cols = st.columns([4, 1, 1])
                        with cols[0]:
                            st.write(
                                f"{txn['description'][:20]}{'...' if len(txn['description']) > 20 else ''}"
                                f" - **{txn['category']}** - ${float(txn['amount'].to_decimal()):.2f}"
                                f" ({txn['txn_datetime'].astimezone(est_timezone).strftime('%Y-%m-%d %I:%M %p EST')})"
                            )

                        with cols[1]:

                            def complete_transaction(txn_id):
                                txn_data_collection.update_one(
                                    {"_id": txn_id},
                                    {"$set": {"status": "Completed"}},
                                )
                                st.success("Transaction marked as completed!")

                            st.button(
                                "Complete",
                                key=f"complete_{txn['_id']}",
                                on_click=complete_transaction,
                                args=(txn["_id"],),
                            )

                        with cols[2]:

                            def cancel_transaction(txn_id):
                                txn_data_collection.update_one(
                                    {"_id": txn_id},
                                    {"$set": {"status": "Cancelled"}},
                                )
                                st.success("Transaction marked as cancelled!")

                            st.button(
                                "Cancel",
                                key=f"cancel_h_{txn['_id']}",
                                on_click=cancel_transaction,
                                args=(txn["_id"],),
                            )
            else:
                st.info("No transactions on hold")

        except Exception as e:
            st.error(f"Error loading transactions: {str(e)}")
