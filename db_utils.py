import psycopg2
import pandas as pd
import streamlit as st
import os

# Verbindung zur Datenbank
DB_HOST = os.getenv("DB_HOST")
DB_PORT = os.getenv("DB_PORT", 5432)
DB_NAME = os.getenv("DB_NAME")
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")

def get_connection():
    return psycopg2.connect(
        host=DB_HOST,
        port=DB_PORT,
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD,
        sslmode="require"
    )

def get_stock_prices():
    conn = get_connection()
    df = pd.read_sql_query("SELECT * FROM stock_prices ORDER BY stock_name, period", conn)
    conn.close()
    return df


def get_all_surveys():
    conn = get_connection()
    df = pd.read_sql_query("SELECT * FROM survey", conn)
    conn.close()
    return df

def get_all_actions():
    conn = get_connection()
    df = pd.read_sql_query("SELECT * FROM actions", conn)
    conn.close()
    return df

def get_all_results():
    conn = get_connection()
    df = pd.read_sql_query("SELECT * FROM results", conn)
    conn.close()
    return df

def init_db():
    conn = get_connection()
    cursor = conn.cursor()


    cursor.execute('''CREATE TABLE IF NOT EXISTS survey (
                        user_id TEXT PRIMARY KEY,
                        age INTEGER,
                        experience INTEGER,
                        study TEXT,
                        gender TEXT,
                        ip_address TEXT,
                        user_group TEXT)''')

    cursor.execute('''CREATE TABLE IF NOT EXISTS actions (
                        id SERIAL PRIMARY KEY,
                        user_id TEXT,
                        period INTEGER,
                        action TEXT,
                        stock_name TEXT,
                        amount INTEGER,
                        price REAL)''')

    cursor.execute('''CREATE TABLE IF NOT EXISTS results (
                        user_id TEXT PRIMARY KEY,
                        total_value REAL)''')

    conn.commit()
    cursor.close()
    conn.close()

def save_survey(user_id, age, experience, study, gender, ip_address=None, user_group=None):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''INSERT INTO survey (user_id, age, experience, study, gender, ip_address, user_group)
                      VALUES (%s, %s, %s, %s, %s, %s, %s)
                      ON CONFLICT (user_id) DO UPDATE
                      SET age = EXCLUDED.age,
                          experience = EXCLUDED.experience,
                            study = EXCLUDED.study,
                            gender = EXCLUDED.gender,
                          ip_address = EXCLUDED.ip_address,
                            user_group = EXCLUDED.user_group''',
                   (user_id, age, experience, study, gender, ip_address, user_group))
    conn.commit()
    cursor.close()
    conn.close()

def save_action(action, user_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''INSERT INTO actions (user_id, period, action, stock_name, amount, price)
                      VALUES (%s, %s, %s, %s, %s, %s)''',
                   (user_id, action['Period'], action['Action'], action['Stock'], action['Amount'], action['Price']))
    conn.commit()
    cursor.close()
    conn.close()

def save_result(total_value, user_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''INSERT INTO results (user_id, total_value)
                      VALUES (%s, %s)
                      ON CONFLICT (user_id) DO UPDATE
                      SET total_value = EXCLUDED.total_value''',
                   (user_id, total_value))
    conn.commit()
    cursor.close()
    conn.close()

def get_user_count():
    conn = get_connection()
    with conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM survey")
        count = cur.fetchone()[0]
    conn.close()
    return count

def save_input(user_id, text):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS user_input (
            user_id TEXT,
            input_text TEXT,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    cursor.execute('''
        INSERT INTO user_input (user_id, input_text)
        VALUES (%s, %s)
    ''', (user_id, text))
    conn.commit()
    cursor.close()
    conn.close()

