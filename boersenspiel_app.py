import random
import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import string
import requests
from dotenv import load_dotenv
import os 
from db_utils import init_db, save_action, save_result, save_survey
from db_utils import get_all_surveys, get_all_actions, get_all_results, get_stock_prices

init_db()

def get_ip():
    try:
        return requests.get('https://api.ipify.org').text
    except:
        return "unavailable"


def generate_user_id(length=6):
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=length))


# --- Data Classes ---
class Stock:
    def __init__(self, name, price_history):
        self.name = name
        self.price_history = price_history
        self.price = price_history[-1] if price_history else 0

    def update_price(self, period):
        if period <= len(self.price_history):
            self.price = self.price_history[period - 1]
            return self.price
        return self.price

    def price_change(self):
        if len(self.price_history) < 2:
            return 0.0
        return round(((self.price - self.price_history[-2]) / self.price_history[-2]) * 100, 2)

class Player:
    def __init__(self, capital):
        self.capital = capital
        self.portfolio = {}
        self.actions = []
        self.performance = []

    def track_performance(self, stocks):
        total = self.total_value(stocks)
        self.performance.append(total)

    def buy(self, stock: Stock, amount: int, period: int):
        cost = stock.price * amount
        if self.capital >= cost:
            self.capital -= cost
            if stock.name in self.portfolio:
                self.portfolio[stock.name]["amount"] += amount
                self.portfolio[stock.name]["buy_price"] = (
                    (self.portfolio[stock.name]["buy_price"] + stock.price) / 2
                )
            else:
                self.portfolio[stock.name] = {"amount": amount, "buy_price": stock.price}
            self.actions.append(
                {"Period": period, "Action": "Buy", "Stock": stock.name, "Amount": amount, "Price": stock.price}
            )
            save_action(self.actions[-1], st.session_state.user_id)
            return f"Bought {amount} of {stock.name} at {stock.price:.2f}€"
        else:
            return "Not enough capital."

    def sell(self, stock: Stock, amount: int, period: int):
        if stock.name in self.portfolio and self.portfolio[stock.name]["amount"] >= amount:
            self.capital += stock.price * amount
            self.portfolio[stock.name]["amount"] -= amount
            if self.portfolio[stock.name]["amount"] == 0:
                del self.portfolio[stock.name]
            self.actions.append(
                {"Period": period, "Action": "Sell", "Stock": stock.name, "Amount": amount, "Price": stock.price}
            )
            save_action(self.actions[-1], st.session_state.user_id)
            return f"Sold {amount} of {stock.name} at {stock.price:.2f}€"
        else:
            return "Not enough stock to sell."

    def total_value(self, stocks: list):
        value = self.capital
        for name, data in self.portfolio.items():
            stock = next((s for s in stocks if s.name == name), None)
            if stock:
                value += data["amount"] * stock.price
        return round(value, 2)


# --- Initialization ---
def initialize_stocks():
    df = get_stock_prices()
    stocks = []
    for stock_name in df["stock_name"].unique():
        stock_prices = df[df["stock_name"] == stock_name].sort_values("period")["price"].tolist()
        stocks.append(Stock(stock_name, stock_prices))
    return stocks

# --- Pages ---
def landing_page():
    from db_utils import get_user_count  # Neue Hilfsfunktion (s. unten)
    user_count = get_user_count()

    st.title("📊 Welcome to the Stock Market Simulation Game")

    st.write(
        "In this simulation, you'll manage a portfolio of 5 fictional stocks over 15 periods. "
        "Each period represents a market update where stock prices change. Your goal is to make smart "
        "buy/sell decisions to maximize your total portfolio value."
    )

    st.subheader("👤 Quick Survey")
    age = st.slider("How old are you?", 10, 100, 25)
    experience = st.radio(
        "What is your experience with trading?",
        ["None", "Beginner", "Intermediate", "Expert"]
    )

    if st.button("Start Simulation", key="start_button_landing"):
        user_id = generate_user_id()
        is_alt_group = (user_count + 1) % 2 == 0  # Jeder zweite Spieler ist in der alternativen Gruppe

        random.seed(42)

        # Save user info to session state
        st.session_state.user_id = user_id
        st.session_state.age = age
        st.session_state.experience = experience
        st.session_state.is_playing = True
        st.session_state.period = 6
        st.session_state.logs = []
        st.session_state.survey_completed = True
        st.session_state.page = "Simulation"  # Direct redirect

        # Nur EINMAL stocks initialisieren
        stocks = initialize_stocks()
        st.session_state.stocks = stocks

        # Spieler initialisieren
        player = Player(capital=1000 if not is_alt_group else 500)

        # Alternative Gruppe bekommt Lunaris-Aktien
        if is_alt_group:
            lunaris = next((s for s in stocks if s.name == "Lunaris Ventures"), None)
            assert lunaris is not None, "Lunaris Ventures wurde nicht in stocks gefunden!"
            amount = 10
            player.portfolio["Lunaris Ventures"] = {"amount": amount, "buy_price": lunaris.price}

        st.session_state.player = player

        ip = get_ip()
        save_survey(user_id, age, experience, ip_address=ip, user_group="treatment" if is_alt_group else "control")

        # Initiale Kursverläufe für Perioden 1–5 berechnen
        for period in range(1, 6):
            for stock in st.session_state.stocks:
                stock.update_price(period)
            st.session_state.player.track_performance(st.session_state.stocks)

        st.rerun()


def game_page():
    if not st.session_state.get('survey_completed', False):
        st.warning("Please complete the survey first.")
        return

    st.title("📈 Stock Market Simulation Game")
    player = st.session_state.player

    col1, col2 = st.columns([2, 2])
    with col1:
        st.subheader(f"Period {st.session_state.period} of 15")
    with col2:
        if st.session_state.period < 15:
            if st.button("➡️ Next Period"):
                random.seed(st.session_state.period)

                for stock in st.session_state.stocks:
                    stock.update_price(st.session_state.period)
                st.session_state.player.track_performance(st.session_state.stocks)
                st.session_state.period += 1
                st.rerun()
        else:
            st.success("🎉 Game Over!")
            st.markdown(f"**📈 Total Value:** {player.total_value(st.session_state.stocks):.2f}€")

    st.markdown("### 🏦 Stock Prices")
    for stock in st.session_state.stocks:
        change = stock.price_change()
        color = "green" if change >= 0 else "red"
        st.markdown(
            f"- **{stock.name}**: {stock.price:.2f}€ "
            f"(<span style='color:{color}'>{change:+.2f}%</span>)",
            unsafe_allow_html=True
        )


    st.markdown(f"**💰 Capital:** {player.capital:.2f}€")

    st.markdown("### 💼 Trade Stocks")
    action = st.selectbox("Choose Action", ["Buy", "Sell"])
    selected_stock = st.selectbox("Choose Stock", [s.name for s in st.session_state.stocks])
    amount = st.number_input("Amount", min_value=1, value=1)

    if st.button("Execute"):
        stock_obj = next(s for s in st.session_state.stocks if s.name == selected_stock)
        if action == "Buy":
            result = player.buy(stock_obj, amount, st.session_state.period)
        else:
            result = player.sell(stock_obj, amount, st.session_state.period)
        st.success(result)

    st.markdown("### 📊 Portfolio Overview")
    portfolio_data = []
    for stock_name, data in player.portfolio.items():
        stock_obj = next(s for s in st.session_state.stocks if s.name == stock_name)
        value = data["amount"] * stock_obj.price
        change = ((stock_obj.price - data["buy_price"]) / data["buy_price"]) * 100 if data["buy_price"] != 0 else 0
        gain_loss = round((stock_obj.price - data["buy_price"]) * data["amount"], 2)
        portfolio_data.append([
            stock_name,
            data["amount"],
            round(data["buy_price"], 2),
            round(stock_obj.price, 2),
            round(value, 2),
            f"{round(change, 2)}%",
            round(gain_loss)
        ])


    portfolio_df = pd.DataFrame(
        portfolio_data,
        columns=["Stock", "Amount", "Buy Price", "Current Price", "Value (€)", "Change", "Gain/Loss (€)"]
    )

    total_value = player.total_value(st.session_state.stocks)
    if not portfolio_df.empty:
        # Gesamtberechnung für Total-Zeile
        total_invested = sum(data["amount"] * data["buy_price"] for data in player.portfolio.values())
        total_market_value = sum(
            data["amount"] * next((s for s in st.session_state.stocks if s.name == name), None).price
            for name, data in player.portfolio.items()
        )

        # Jetzt wird das Kapital zum Gesamtwert addiert:
        total_with_capital = total_market_value + player.capital
        total_gain = round(total_market_value - total_invested, 2)
        total_change = round(((total_market_value / total_invested - 1) * 100), 2) if total_invested else 0.0

        # Zeile: Capital
        portfolio_df.loc[len(portfolio_df.index)] = ["Capital", "", "", "", round(player.capital, 2), "", ""]

        # Zeile: Total (inkl. Kapital)
        portfolio_df.loc[len(portfolio_df.index)] = [
            "Total", "", "", "", round(total_with_capital, 2), f"{total_change}%", total_gain
        ]


        def highlight_changes(val):
            try:
                if isinstance(val, str) and "%" in val:
                    val = float(val.strip('%'))
                elif isinstance(val, (int, float)):
                    val = float(val)
                color = 'green' if val > 0 else 'red' if val < 0 else 'black'
                return f'color: {color}'
            except:
                return ""

        styled_df = portfolio_df.style.applymap(highlight_changes, subset=["Change", "Gain/Loss (€)"])
        st.dataframe(styled_df, use_container_width=True)


    st.markdown("### 📝 Actions History")
    if player.actions:
        st.dataframe(pd.DataFrame(player.actions))

    # Stock charts
    st.markdown("### 📉 Stock Price Trends")

    selected_stock_chart = st.selectbox("Select a stock to view its price trend", [stock.name for stock in st.session_state.stocks])

    selected_stock_obj = next((s for s in st.session_state.stocks if s.name == selected_stock_chart), None)
    if selected_stock_obj:
        # Nur tatsächliche Perioden anzeigen (ohne Startwert)
        periods = list(range(1, len(selected_stock_obj.price_history) + 1))
        prices = selected_stock_obj.price_history


        
        fig, ax = plt.subplots(figsize=(6, 3))
        ax.plot(periods, prices, marker="o", color="blue")
        ax.set_title(f"{selected_stock_obj.name} Price Over Time")
        ax.set_xlabel("Period")
        ax.set_ylabel("Price (€)")
        ax.set_xticks(periods)
        ax.grid(True)
        st.pyplot(fig)


    if st.session_state.period == 15:
        st.success("🎉 Game Over!")
        total = player.total_value(st.session_state.stocks)
        save_result(total, st.session_state.user_id)
        st.markdown(f"**📈 Total Value:** {total:.2f}€")


    st.markdown("### 📈 Portfolio Performance Over Time")

    if st.session_state.player.performance:
        periods = list(range(1, len(st.session_state.player.performance) + 1))  # Start bei 1
        fig, ax = plt.subplots(figsize=(6, 3))
        ax.plot(periods, st.session_state.player.performance, marker="o", color="green")
        ax.set_title("Portfolio Value Over Time")
        ax.set_xlabel("Period")
        ax.set_ylabel("Total Value (€)")
        ax.set_xticks(periods)  # Beschriftung der X-Achse mit 1, 2, 3, ...
        ax.grid(True)
        st.pyplot(fig)

def admin_page():
    st.title("🔐 Admin Dashboard")
    with st.expander("🔑 Show admin panel"):
        admin_access = st.text_input("Enter admin password:", type="password")

    if admin_access == "letmein":
        st.success("Access granted!")
        from db_utils import get_all_surveys, get_all_actions, get_all_results

        st.dataframe(get_all_surveys())
        st.dataframe(get_all_actions())
        st.dataframe(get_all_results())

    elif admin_access:
        st.error("❌ Incorrect password")
    else:
        st.info("Please enter password to access admin dashboard.")


# --- Run App ---
st.sidebar.title("📋 Navigation")
page = st.sidebar.radio("Go to", ["Landing Page", "Simulation", "Admin"])

if page == "Landing Page":
    landing_page()
elif page == "Simulation":
    game_page()
elif page == "Admin":
    admin_page()