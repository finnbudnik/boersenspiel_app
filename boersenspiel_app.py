import random
import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import string
import requests
import uuid
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

def generate_user_id(length=8):
    return uuid.uuid4().hex[:length].upper()


# Data Classes
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

    def price_change(self, current_period=None):
        if current_period is None or current_period <= 1:
            return 0.0
        if current_period > len(self.price_history):
            current_period = len(self.price_history)
        
        try:
            current_price = self.price_history[current_period - 1]
            previous_price = self.price_history[current_period - 2]
            if previous_price == 0:
                return 0.0
            return round(((current_price - previous_price) / previous_price) * 100, 2)
        except IndexError:
            return 0.0


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
            return "Not enough cash."

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


# Initialization
def initialize_stocks():
    df = get_stock_prices()
    stocks = []
    for stock_name in df["stock_name"].unique():
        stock_prices = df[df["stock_name"] == stock_name].sort_values("period")["price"].tolist()
        stocks.append(Stock(stock_name, stock_prices))
    return stocks

# Pages
def landing_page():
    from db_utils import get_user_count  # Neue Hilfsfunktion (s. unten)
    user_count = get_user_count()

    st.title("Stock Market Simulation Game")

    st.markdown("**Welcome!**")

    st.markdown("In this simulation, you'll manage a portfolio of five fictional stocks over 15 periods, starting from " \
    "period 6. At the beginning of each period, you may execute an unlimited number of trades - completely free of transaction " \
    "fees and taxes. You'll be randomly provided with a combination of cash and/or gifted stocks, totalling 1000€ in value.")

    st.markdown("**You have the chance to get a percentage of your gains payed out.** For this reason only, please insert your E-Mail adress down below.")

    st.markdown("Stock prices are updated each time you click the **\"Next Period\"** Button. Your objective is to make smart " \
    "buy and sell decisions to maximize your total portfolio value by period 15, based on past price movements. Each of the " \
    "five stocks has a distinct probability of increasing in value: 40%, 45%, 50%, 55%, or 60%. This means two stocks are more likely " \
    "to rise, two are more likely to fall and one is neutral - but which is which remains unknown. In each period, prices can " \
    "rise by up to 6%, or fall by up to 5%, resulting in overall market growth. ")

    st.markdown("**Please note:** Your data is securely stored and used strictly for academic purposes. By clicking the **\"Start Simulation\"** " \
    "button, you agree to your data being retained for 90 days and used for research and analysis. Your E-Mail is used only for contact")

    st.markdown("Thank you for your participation - and enjoy the game! Please start by completing the survey and start the " \
    "game by pressing the \"Start simulation\" button. then switch to the simulation via the navigation bar.")

    st.subheader("Survey")
    age = st.slider("How old are you?", 18, 70, 30)
    gender = st.radio("What is your gender?", ["Male", "Female", "Diverse", "Other"])
    study = st.radio("What is your field of study?", 
                     ["Economics or Law (incl. WiWi, VWL, BWL, WIng, WInf, ...)",
                     "Engineering, Computer Science or similar ", "Natural Science", "Social science or Humanities" ,"Other"])
    experience = st.slider("On a scale of 1 (Beginner) to 10 (Expert) what is your experience with trading?", 1, 10, 5)
    mail = st.text_input("Please insert your E-Mail", "Your E-Mail")

    if st.button("Start Simulation", key="start_button_landing"):
        user_id = generate_user_id()
        is_alt_group = (user_count + 1) % 2 == 0  # Jeder zweite Spieler ist in der alternativen Gruppe

        # Save user info to session state
        st.session_state.user_id = user_id
        st.session_state.age = age
        st.session_state.experience = experience
        st.session_state.study = study
        st.session_state.gender = gender
        st.session_state.mail = mail
        st.session_state.is_playing = True
        st.session_state.period = 6
        st.session_state.logs = []
        st.session_state.survey_completed = True
        st.session_state.page = "Simulation"  

        stocks = initialize_stocks()
        st.session_state.stocks = stocks

        random.shuffle(stocks)
        st.session_state.stocks = stocks

        player = Player(capital=1000 if not is_alt_group else 500)
        st.session_state.player = player

        # Treatment-Group
        if is_alt_group:
            lunaris = next((s for s in stocks if s.name == "Lunaris Ventures"), None)
            assert lunaris is not None, "Lunaris Ventures wurde nicht in stocks gefunden!"
            amount = 9.174311927
            buy_price = round(lunaris.price_history[4], 2) 
            player.portfolio["Lunaris Ventures"] = {"amount": amount, "buy_price": buy_price}


        ip = get_ip()
        save_survey(user_id, age, experience, study, gender, mail, ip_address=ip, user_group="treatment" if is_alt_group else "control")

        for period in range(1, 6):
            for stock in stocks:
                stock.update_price(period)
            player.track_performance(stocks)

        st.rerun()


def game_page():

    if not st.session_state.get('survey_completed', False):
        st.warning("Please complete the survey first.")
        return
    
    # Robust initialisieren: sicherstellen, dass Preise zu aktuellem Periodenstand passen
    current_period = st.session_state.period
    for stock in st.session_state.stocks:
        stock.update_price(current_period - 1)
    
    # Reload
    if 'stocks' in st.session_state and 'period' in st.session_state:
        for stock in st.session_state.stocks:
            stock.update_price(st.session_state.period)


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
        elif st.session_state.get("total_value") is None:
            player = st.session_state.player
            total = player.total_value(st.session_state.stocks)
            st.session_state.total_value = total
            save_result(total, st.session_state.user_id)
            st.session_state.page = "Final"
            st.rerun()

    st.markdown("### Recent Price Updates")

    # Vorperiode bestimmen
    previous_period = max(1, st.session_state.period - 1)

    for stock in st.session_state.stocks:
        try:
            prev_price = stock.price_history[previous_period - 1]
            change = stock.price_change(previous_period)
        except IndexError:
            prev_price = 0.0
            change = 0.0
        color = "green" if change >= 0 else "red"
        st.markdown(
            f"- **{stock.name}**: {prev_price:.2f}€ "
            f"(<span style='color:{color}'>{change:+.2f}%</span>)",
            unsafe_allow_html=True
        )


    # Ensure all stock prices are updated to the current period
    for stock in st.session_state.stocks:
        stock.update_price(st.session_state.period - 1)

    st.markdown(f"**💰 Cash:** {player.capital:.2f}€")

    st.markdown("### Trade Stocks")
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
            f"{round(data['buy_price'], 2):.2f}€",
            f"{round(stock_obj.price, 2):.2f}€",
            f"{round(value, 2):.2f}€",  # Value darf ruhig Zahl bleiben für Summe
            f"{round(change, 2)}%",
            f"{round(gain_loss, 2):.2f}€"
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

        total_with_capital = total_market_value + player.capital
        total_gain = round(total_market_value - total_invested, 2)
        total_change = round(((total_with_capital / 1000 - 1) * 100), 2) if total_invested else 0.0

        # Capital
        portfolio_df.loc[len(portfolio_df.index)] = ["Cash", "", "", "", f"{round(player.capital, 2):.2f}€", "", ""]


        # Total
        portfolio_df.loc[len(portfolio_df.index)] = [
            "Total", "", "", "", f"{round(total_with_capital, 2):.2f}€", f"{total_change}%", f"{round(total_with_capital - 1000, 2):.2f}€"
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


    # Stock charts
    st.markdown("### 📉 Stock Price Trends")

    selected_stock_chart = st.selectbox("Select a stock to view its price trend", [stock.name for stock in st.session_state.stocks])

    selected_stock_obj = next((s for s in st.session_state.stocks if s.name == selected_stock_chart), None)
    if selected_stock_obj:
        current_period = st.session_state.period

        # Zeige nur vergangene Perioden (bis einschließlich current_period - 1)
        past_periods = list(range(1, current_period))
        prices = selected_stock_obj.price_history[:current_period - 1]

        fig, ax = plt.subplots(figsize=(6, 3))
        ax.plot(past_periods, prices, marker="o", color="blue")
        ax.set_title(f"{selected_stock_obj.name} Price Over Time")
        ax.set_xlabel("Period")
        ax.set_ylabel("Price (€)")
        ax.set_xticks(past_periods)
        ax.grid(True)
        st.pyplot(fig)


    if st.session_state.period == 15:
        st.success("🎉 Game Over!")
        total = player.total_value(st.session_state.stocks)
        save_result(total, st.session_state.user_id)
        st.session_state.total_value = total
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

    st.markdown("### 📝 Actions History")
    if player.actions:
        st.dataframe(pd.DataFrame(player.actions))

def final_page():
    st.title("Game over!")
    st.success("Your result was successfully safed.")

    st.subheader("Your Final Result:")
    
    if "total_value" in st.session_state:
        st.metric(label="Total Value", value=f"{st.session_state.total_value:,.2f}€")
    else:
        st.warning("Total value not found. Please make sure you completed the simulation.")

    st.write("Thank you for participating! We really appreciate your time and effort. If you inserted your E-Mail in the beginning" \
    " you have the chance of receivieng a percentage of your gains payed out. Please be aware, that the emission may take some time, you will "
    "be contacted via E-Mail. Emission is only" \
    " possible, if a valid E-mail adress is inserted in the survey. We reserve " \
    "the right to cap the payout and withhold if necessary. Multiple payouts are not possible, only the first completed " \
    "game will be taken into account.")


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


# Run App
page = st.session_state.get("page", "Landing Page")

if page == "Landing Page":
    landing_page()
elif page == "Simulation":
    game_page()
elif page == "Final":
    final_page()
elif page == "Admin":
    admin_page()