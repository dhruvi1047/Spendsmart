from pathlib import Path
from datetime import date, timedelta
import sqlite3
import csv
import io

import pandas as pd
import plotly.express as px
import streamlit as st

APP_DIR = Path(__file__).resolve().parent
DB_PATH = APP_DIR / "spendsmart.db"
CATEGORIES = ["Food", "Transport", "Stationery", "Printing", "College", "Shopping", "Entertainment", "Other"]
ICONS = {
    "Food": "🍔", "Transport": "🚌", "Stationery": "📚", "Printing": "🖨️",
    "College": "🎓", "Shopping": "🛍️", "Entertainment": "🎧", "Other": "✦"
}

st.set_page_config(page_title="SpendSmart", page_icon="💸", layout="wide")

st.markdown("""
<style>
    .block-container {padding-top: 2rem; padding-bottom: 3rem; max-width: 1400px;}
    [data-testid="stMetric"] {background: #f5f8f4; border: 1px solid #e2ebe1; padding: 14px 16px; border-radius: 14px;}
    [data-testid="stMetricLabel"] {color: #607568;}
    div.stButton > button[kind="primary"] {background: #244c43; border-color: #244c43;}
    .small-note {color: #6b7c71; font-size: .9rem;}
</style>
""", unsafe_allow_html=True)


def connect():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with connect() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS expenses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                note TEXT NOT NULL,
                category TEXT NOT NULL,
                amount REAL NOT NULL CHECK(amount > 0),
                expense_date TEXT NOT NULL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS budgets (
                period TEXT PRIMARY KEY,
                amount REAL NOT NULL CHECK(amount > 0)
            )
        """)
        count = conn.execute("SELECT COUNT(*) FROM expenses").fetchone()[0]
        if count == 0:
            samples = [
                ("Lunch at canteen", "Food", 85, -1),
                ("Bus pass", "Transport", 300, -2),
                ("Lab record", "Stationery", 120, -3),
                ("Project printouts", "Printing", 65, -4),
                ("College event contribution", "College", 150, -5),
                ("Evening snacks", "Food", 55, -6),
                ("Auto fare", "Transport", 90, -7),
                ("Notebook", "Stationery", 75, -8),
                ("Coffee with friends", "Food", 110, -9),
                ("Photocopies", "Printing", 35, -10),
                ("Movie ticket", "Entertainment", 180, -12),
                ("College supplies", "College", 210, -14),
                ("Birthday gift", "Shopping", 250, -16),
                ("Lunch", "Food", 95, -18),
                ("Bus fare", "Transport", 40, -20),
                ("Pens and markers", "Stationery", 90, -21),
                ("Snacks", "Food", 60, -23),
                ("Assignment print", "Printing", 45, -25),
                ("Mobile recharge", "Other", 199, -27),
                ("College canteen", "Food", 70, -29),
            ]
            today = date.today()
            conn.executemany(
                "INSERT INTO expenses(note, category, amount, expense_date) VALUES (?, ?, ?, ?)",
                [(n, c, a, (today + timedelta(days=offset)).isoformat()) for n, c, a, offset in samples]
            )
        conn.execute("INSERT OR IGNORE INTO budgets(period, amount) VALUES ('monthly', 5000)")
        conn.execute("INSERT OR IGNORE INTO budgets(period, amount) VALUES ('weekly', 1500)")


def get_expenses():
    with connect() as conn:
        rows = conn.execute(
            "SELECT id, note, category, amount, expense_date FROM expenses ORDER BY expense_date DESC, id DESC"
        ).fetchall()
    return pd.DataFrame([dict(r) for r in rows], columns=["id", "note", "category", "amount", "expense_date"])


def get_budget(period):
    with connect() as conn:
        row = conn.execute("SELECT amount FROM budgets WHERE period = ?", (period,)).fetchone()
    return float(row["amount"]) if row else 0.0


def set_budget(period, amount):
    with connect() as conn:
        conn.execute(
            "INSERT INTO budgets(period, amount) VALUES (?, ?) "
            "ON CONFLICT(period) DO UPDATE SET amount=excluded.amount",
            (period, float(amount))
        )


def money(value):
    return f"₹{float(value):,.2f}".rstrip("0").rstrip(".")


def week_start(today):
    return today - timedelta(days=today.weekday())


def add_expense(note, category, amount, expense_date):
    with connect() as conn:
        conn.execute(
            "INSERT INTO expenses(note, category, amount, expense_date) VALUES (?, ?, ?, ?)",
            (note.strip() or f"{category} expense", category, float(amount), expense_date.isoformat())
        )


def delete_expense(expense_id):
    with connect() as conn:
        conn.execute("DELETE FROM expenses WHERE id = ?", (int(expense_id),))


init_db()
df = get_expenses()
today = date.today()
month_start = today.replace(day=1).isoformat()
week_begin = week_start(today).isoformat()
today_iso = today.isoformat()

st.sidebar.markdown("# 💸 SpendSmart")
st.sidebar.caption("STUDENT FINANCE • PROJECT STUDIO")
page = st.sidebar.radio(
    "WORKSPACE",
    ["Dashboard", "Add expense", "Expense history", "Budget planner", "Insights & savings"],
    label_visibility="collapsed"
)
st.sidebar.divider()
st.sidebar.caption("Small steps add up. Track everyday spending and make your student budget work smarter.")
st.sidebar.caption("Sample data is included so you can test the prototype immediately.")

st.title({
    "Dashboard": "Your money, in focus",
    "Add expense": "Add a new expense",
    "Expense history": "Expense history",
    "Budget planner": "Plan your budget",
    "Insights & savings": "Insights & savings",
}[page])
st.caption(f"Today • {today.strftime('%A, %d %B %Y')}")

# Prepare date-window data
if not df.empty:
    df["expense_date"] = pd.to_datetime(df["expense_date"]).dt.date
    month_df = df[df["expense_date"].apply(lambda d: d.strftime("%Y-%m")) == today.strftime("%Y-%m")]
    week_df = df[(df["expense_date"] >= week_start(today)) & (df["expense_date"] <= today)]
    day_df = df[df["expense_date"] == today]
else:
    month_df = week_df = day_df = df.copy()

monthly_spent = float(month_df["amount"].sum()) if not month_df.empty else 0
weekly_spent = float(week_df["amount"].sum()) if not week_df.empty else 0
daily_spent = float(day_df["amount"].sum()) if not day_df.empty else 0
monthly_budget = get_budget("monthly")
weekly_budget = get_budget("weekly")

if page == "Dashboard":
    remaining = monthly_budget - monthly_spent
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Spent today", money(daily_spent))
    c2.metric("Spent this week", money(weekly_spent))
    c3.metric("Spent this month", money(monthly_spent))
    c4.metric("Monthly balance", money(remaining), delta="Within budget" if remaining >= 0 else "Over budget", delta_color="normal" if remaining >= 0 else "inverse")

    st.subheader("Monthly budget overview")
    pct = monthly_spent / monthly_budget if monthly_budget else 0
    st.progress(min(pct, 1.0), text=f"{money(monthly_spent)} spent of {money(monthly_budget)} ({pct:.0%})" if monthly_budget else "Set a monthly budget to track progress.")
    if monthly_budget and pct >= 1:
        st.error("Monthly budget exceeded. Review non-essential spending.")
    elif monthly_budget and pct >= .8:
        st.warning("You have used 80% or more of your monthly budget.")

    left, right = st.columns([1.25, 1])
    with left:
        st.subheader("Spending by category")
        if not month_df.empty:
            cat = month_df.groupby("category", as_index=False)["amount"].sum().sort_values("amount", ascending=False)
            fig = px.pie(cat, names="category", values="amount", hole=.58, title="This month's expenses")
            fig.update_layout(margin=dict(t=45, b=10, l=5, r=5), legend_title_text="")
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No expenses recorded this month yet.")
    with right:
        st.subheader("Budget snapshot")
        st.metric("Weekly budget", money(weekly_budget))
        st.metric("Spent this week", money(weekly_spent))
        st.metric("Weekly balance", money(weekly_budget - weekly_spent))
        st.caption("The week runs Monday to Sunday.")

    st.subheader("Recent transactions")
    if not df.empty:
        recent = df.head(7).copy()
        recent["expense_date"] = recent["expense_date"].astype(str)
        recent["amount"] = recent["amount"].map(money)
        st.dataframe(recent[["expense_date", "note", "category", "amount"]].rename(
            columns={"expense_date": "Date", "note": "Expense", "category": "Category", "amount": "Amount"}
        ), use_container_width=True, hide_index=True)
    else:
        st.info("No transactions yet. Add your first expense.")

elif page == "Add expense":
    st.write("Enter the amount, date, category and a short note.")
    with st.form("add_expense_form", clear_on_submit=True):
        col1, col2 = st.columns(2)
        with col1:
            amount = st.number_input("Amount (₹)", min_value=1.0, step=10.0, value=100.0)
            expense_date = st.date_input("Date", value=today, max_value=date(2100, 12, 31))
        with col2:
            category = st.selectbox("Category", CATEGORIES, format_func=lambda x: f"{ICONS[x]} {x}")
            note = st.text_input("Short note", max_chars=70, placeholder="e.g. Lunch with friends")
        submitted = st.form_submit_button("Save expense", type="primary", use_container_width=True)
        if submitted:
            add_expense(note, category, amount, expense_date)
            st.success("Expense saved successfully.")
            st.rerun()

elif page == "Expense history":
    st.write("Search, filter, delete and export your records.")
    col1, col2, col3 = st.columns([1.2, 1, 1])
    with col1:
        query = st.text_input("Search notes")
    with col2:
        chosen_category = st.selectbox("Category", ["All"] + CATEGORIES)
    with col3:
        period = st.selectbox("Date range", ["All time", "This month", "This week"])
    filtered = df.copy()
    if query:
        filtered = filtered[filtered["note"].str.contains(query, case=False, na=False) |
                            filtered["category"].str.contains(query, case=False, na=False)]
    if chosen_category != "All":
        filtered = filtered[filtered["category"] == chosen_category]
    if period == "This month":
        filtered = filtered[filtered["expense_date"].apply(lambda d: d.strftime("%Y-%m")) == today.strftime("%Y-%m")]
    elif period == "This week":
        filtered = filtered[(filtered["expense_date"] >= week_start(today)) & (filtered["expense_date"] <= today)]
    st.metric("Matching expenses", len(filtered), help="Number of records after applying filters.")
    if filtered.empty:
        st.info("No expenses match these filters.")
    else:
        display = filtered.copy()
        display["expense_date"] = display["expense_date"].astype(str)
        display["amount"] = display["amount"].map(money)
        st.dataframe(display[["id", "expense_date", "note", "category", "amount"]].rename(
            columns={"id": "ID", "expense_date": "Date", "note": "Expense", "category": "Category", "amount": "Amount"}
        ), use_container_width=True, hide_index=True)
        csv_df = filtered[["expense_date", "amount", "category", "note"]].copy()
        csv_df["expense_date"] = csv_df["expense_date"].astype(str)
        csv_bytes = csv_df.to_csv(index=False).encode("utf-8-sig")
        st.download_button("⬇ Download CSV", data=csv_bytes, file_name="spendsmart-expenses.csv", mime="text/csv")
        ids = filtered["id"].astype(int).tolist()
        selected_id = st.selectbox("Select an expense ID to delete", ids)
        if st.button("Delete selected expense", type="secondary"):
            delete_expense(selected_id)
            st.success(f"Expense #{selected_id} deleted.")
            st.rerun()

elif page == "Budget planner":
    st.write("Set weekly and monthly spending limits. The remaining amount updates automatically.")
    col1, col2 = st.columns(2)
    with col1:
        with st.form("monthly_budget_form"):
            st.subheader("Monthly budget")
            new_monthly = st.number_input("Monthly limit (₹)", min_value=1.0, step=100.0, value=float(monthly_budget or 5000))
            if st.form_submit_button("Save monthly budget", type="primary"):
                set_budget("monthly", new_monthly)
                st.success("Monthly budget updated.")
                st.rerun()
    with col2:
        with st.form("weekly_budget_form"):
            st.subheader("Weekly budget")
            new_weekly = st.number_input("Weekly limit (₹)", min_value=1.0, step=100.0, value=float(weekly_budget or 1500))
            if st.form_submit_button("Save weekly budget", type="primary"):
                set_budget("weekly", new_weekly)
                st.success("Weekly budget updated.")
                st.rerun()
    st.divider()
    a, b = st.columns(2)
    with a:
        st.metric("Monthly remaining", money(monthly_budget - monthly_spent))
        if monthly_budget and monthly_spent >= monthly_budget * .8:
            st.warning("Monthly spending has reached at least 80% of the limit.")
    with b:
        st.metric("Weekly remaining", money(weekly_budget - weekly_spent))
        if weekly_budget and weekly_spent >= weekly_budget * .8:
            st.warning("Weekly spending has reached at least 80% of the limit.")

elif page == "Insights & savings":
    st.subheader("Category breakdown")
    if not month_df.empty:
        cat = month_df.groupby("category", as_index=False)["amount"].sum().sort_values("amount", ascending=False)
        fig = px.bar(cat, x="category", y="amount", color="category", title="Monthly spending by category")
        fig.update_layout(showlegend=False, xaxis_title="", yaxis_title="Amount (₹)", margin=dict(t=45, b=10))
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("Add expenses to see category insights.")

    st.divider()
    st.subheader("What-if savings calculator")
    if not month_df.empty:
        spent_by_category = month_df.groupby("category")["amount"].sum().to_dict()
    else:
        spent_by_category = {}
    chosen = st.selectbox("Choose a category", CATEGORIES)
    reduction = st.slider("Reduce spending by", min_value=5, max_value=50, value=10, step=5)
    category_spend = float(spent_by_category.get(chosen, 0))
    savings = category_spend * reduction / 100
    a, b = st.columns(2)
    a.metric("Potential monthly savings", money(savings))
    b.metric("Current category spending", money(category_spend))
    st.caption(f"If you reduce {chosen.lower()} spending by {reduction}%, you could save {money(savings)} this month.")

    st.divider()
    st.subheader("Export records")
    all_csv = df.copy()
    if not all_csv.empty:
        all_csv["expense_date"] = all_csv["expense_date"].astype(str)
    st.download_button(
        "⬇ Download all expenses (CSV)",
        data=all_csv.to_csv(index=False).encode("utf-8-sig"),
        file_name="spendsmart-all-expenses.csv",
        mime="text/csv",
        use_container_width=False
    )

st.divider()
st.caption("SpendSmart • Project Studio prototype | Manual expense tracking only — no bank or UPI connection.")
