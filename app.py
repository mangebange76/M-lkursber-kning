import streamlit as st
import pandas as pd
import gspread
from google.oauth2 import service_account
from datetime import datetime
import yfinance as yf

# Autentisering
scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
creds = service_account.Credentials.from_service_account_info(
    st.secrets["GOOGLE_CREDENTIALS"], scopes=scope
)
client = gspread.authorize(creds)

# Öppna kalkylark och rätt blad
spreadsheet_url = st.secrets["SPREADSHEET_URL"]
sheet = client.open_by_url(spreadsheet_url)
worksheet = sheet.worksheet("Bolag")

# Förväntade rubriker
required_headers = ["Bolag", "Ticker", "Senast uppdaterad", "Aktuell kurs", "TTM Sales", "TTM EPS"]

# Läs existerande data
data = worksheet.get_all_records()
if not data or list(data[0].keys()) != required_headers:
    worksheet.clear()
    worksheet.append_row(required_headers)
    df = pd.DataFrame(columns=required_headers)
else:
    df = pd.DataFrame(data)

st.title("Fundamental aktievärdering")

# Formulär
with st.form("add_stock_form"):
    ticker_input = st.text_input("Ange Ticker (t.ex. AAPL, MSFT):", "")
    submitted = st.form_submit_button("Hämta & Lägg till/uppdatera")

    if submitted and ticker_input:
        try:
            ticker = ticker_input.upper()
            stock = yf.Ticker(ticker)
            info = stock.info

            current_price = round(info.get("currentPrice", 0), 2)
            ttm_sales = round(info.get("totalRevenue", 0) / 1e6, 2) if info.get("totalRevenue") else 0
            ttm_eps = round(info.get("trailingEps", 0), 2)
            name = info.get("shortName", "Okänt")
            now = datetime.now().strftime("%Y-%m-%d %H:%M")

            new_data = {
                "Bolag": name,
                "Ticker": ticker,
                "Senast uppdaterad": now,
                "Aktuell kurs": current_price,
                "TTM Sales": ttm_sales,
                "TTM EPS": ttm_eps
            }

            if ticker in df["Ticker"].values:
                row_idx = df[df["Ticker"] == ticker].index[0] + 2
                for i, key in enumerate(required_headers):
                    worksheet.update_cell(row_idx, i + 1, new_data[key])
                st.success(f"{ticker} uppdaterad.")
            else:
                worksheet.append_row([new_data[h] for h in required_headers])
                st.success(f"{ticker} tillagd.")
        except Exception as e:
            st.error(f"Något gick fel: {e}")

# Visa tabell
st.subheader("Aktiedata från Google Sheet")
st.dataframe(df)
