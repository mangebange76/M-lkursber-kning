import streamlit as st
import pandas as pd
import datetime
import yfinance as yf
import gspread
from google.oauth2 import service_account

# --- Autentisering ---
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds = service_account.Credentials.from_service_account_info(
    st.secrets["GOOGLE_CREDENTIALS"], scopes=scope
)
client = gspread.authorize(creds)

# --- Kalkylark och blad ---
SPREADSHEET_URL = st.secrets["SPREADSHEET_URL"]
SHEET_NAME = "Bolag"

sheet = client.open_by_url(SPREADSHEET_URL)
worksheet = sheet.worksheet(SHEET_NAME)
data = worksheet.get_all_records()
df = pd.DataFrame(data)

# --- Förväntade kolumner ---
EXPECTED_COLUMNS = [
    "Ticker", "Bolagsnamn", "Senaste uppdatering", "Aktuell kurs",
    "PS TTM", "PE TTM", "Tillväxt 2025", "Tillväxt 2026", "Tillväxt 2027",
    "Målkurs 2025", "Målkurs 2026", "Målkurs 2027",
    "PE 2026", "PE 2027", "PS 2026", "PS 2027"
]

# --- Kontrollera kolumner ---
if df.empty or list(df.columns) != EXPECTED_COLUMNS:
    worksheet.clear()
    worksheet.append_row(EXPECTED_COLUMNS)
    df = pd.DataFrame(columns=EXPECTED_COLUMNS)

# --- Inmatning ---
st.title("Aktieanalys – Målkursberäkning")

with st.form("add_ticker_form"):
    ticker_input = st.text_input("Ange ticker (t.ex. AAPL, MSFT)", "").strip().upper()
    submitted = st.form_submit_button("Lägg till eller uppdatera")

if submitted and ticker_input:
    try:
        ticker_obj = yf.Ticker(ticker_input)
        hist = ticker_obj.history(period="1d")
        info = ticker_obj.info
        current_price = round(hist["Close"].iloc[-1], 2)
        company_name = info.get("shortName", "")

        today = datetime.datetime.today().strftime("%Y-%m-%d")

        new_row = {
            "Ticker": ticker_input,
            "Bolagsnamn": company_name,
            "Senaste uppdatering": today,
            "Aktuell kurs": current_price,
            "PS TTM": "", "PE TTM": "",
            "Tillväxt 2025": "", "Tillväxt 2026": "", "Tillväxt 2027": "",
            "Målkurs 2025": "", "Målkurs 2026": "", "Målkurs 2027": "",
            "PE 2026": "", "PE 2027": "", "PS 2026": "", "PS 2027": ""
        }

        existing_idx = df.index[df["Ticker"] == ticker_input].tolist()

        if existing_idx:
            worksheet.delete_rows(existing_idx[0] + 2)  # +2 p.g.a. header + 0-index
            worksheet.insert_row(list(new_row.values()), existing_idx[0] + 2)
        else:
            worksheet.append_row(list(new_row.values()))

        st.success(f"{ticker_input} uppdaterades.")

    except Exception as e:
        st.error(f"Något gick fel: {e}")

# --- Visa nuvarande databas ---
st.subheader("Databas (senaste)")
st.dataframe(df)
