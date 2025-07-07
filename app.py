import streamlit as st
import pandas as pd
import gspread
from google.oauth2 import service_account
from datetime import datetime
from yfinance import Ticker

# Autentisering via secrets.toml
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds = service_account.Credentials.from_service_account_info(
    st.secrets["GOOGLE_CREDENTIALS"], scopes=scope
)
client = gspread.authorize(creds)

# Öppna kalkylarket och bladet
SPREADSHEET_NAME = "Aktiedata"
SHEET_NAME = "Bolag"
sheet = client.open(SPREADSHEET_NAME)
worksheet = sheet.worksheet(SHEET_NAME)

# Förväntade kolumner
expected_columns = [
    "Ticker", "Namn", "Valuta", "Kategori", "Senast uppdaterad", "Aktuell kurs",
    "P/S TTM", "P/E TTM", "Tillväxt Y1", "Tillväxt Y2", "Tillväxt Y3",
    "Målkurs Y1", "Målkurs Y2", "Målkurs Y3"
]

# Kontrollera om kolumnerna finns – annars skapa dem
try:
    df = pd.DataFrame(worksheet.get_all_records())
except Exception:
    df = pd.DataFrame()

if df.empty or any(col not in df.columns for col in expected_columns):
    worksheet.clear()
    worksheet.append_row(expected_columns)
    df = pd.DataFrame(columns=expected_columns)

# Funktion: hämta data från Yahoo Finance
def fetch_data(ticker_str):
    try:
        ticker = Ticker(ticker_str)
        info = ticker.info

        name = info.get("longName", "Okänt")
        currency = info.get("currency", "USD")
        price = round(info.get("currentPrice", 0), 2)
        ps = round(info.get("priceToSalesTrailing12Months", 0), 2)
        pe = round(info.get("trailingPE", 0), 2)

        # Här kan mer sofistikerad tillväxtanalys byggas in
        growth1, growth2, growth3 = 0.25, 0.22, 0.20

        # Målkursberäkning
        mk1 = round(price * (1 + growth1), 2)
        mk2 = round(mk1 * (1 + growth2), 2)
        mk3 = round(mk2 * (1 + growth3), 2)

        return {
            "Ticker": ticker_str.upper(),
            "Namn": name,
            "Valuta": currency,
            "Kategori": "Ej angiven",
            "Senast uppdaterad": datetime.today().strftime("%Y-%m-%d"),
            "Aktuell kurs": price,
            "P/S TTM": ps,
            "P/E TTM": pe,
            "Tillväxt Y1": f"{growth1*100:.1f}%",
            "Tillväxt Y2": f"{growth2*100:.1f}%",
            "Tillväxt Y3": f"{growth3*100:.1f}%",
            "Målkurs Y1": mk1,
            "Målkurs Y2": mk2,
            "Målkurs Y3": mk3
        }
    except Exception as e:
        st.error(f"Något gick fel: {e}")
        return None

# UI – Lägg till nytt bolag
st.title("📈 Aktieanalys: Tillväxt & Målkurs")

ticker_input = st.text_input("Ange ticker (t.ex. TTD eller AAPL)")
if st.button("Hämta & Lägg till"):
    if ticker_input:
        data = fetch_data(ticker_input)
        if data:
            df = pd.DataFrame(worksheet.get_all_records())
            if data["Ticker"] in df["Ticker"].values:
                st.warning("Bolaget finns redan.")
            else:
                worksheet.append_row([data[col] for col in expected_columns])
                st.success(f"{data['Namn']} har lagts till.")
    else:
        st.warning("Du måste ange en ticker.")

# Visa alla bolag
df = pd.DataFrame(worksheet.get_all_records())
if df.empty:
    st.warning("❌ Inga bolag inlagda än.")
else:
    selected_index = st.number_input("Bläddra mellan bolag", min_value=0, max_value=len(df)-1, step=1)
    row = df.iloc[selected_index]

    st.header(f"{row['Namn']} ({row['Ticker']})")
    st.write(f"**Kategori:** {row['Kategori']}")
    st.write(f"**Aktuell kurs:** {row['Aktuell kurs']} {row['Valuta']}")
    st.write(f"P/S TTM: {row['P/S TTM']}  P/E TTM: {row['P/E TTM']}")

    st.markdown("---")
    st.subheader("📉 Tillväxt och målkurs")
    st.write(f"**Tillväxt Y1:** {row['Tillväxt Y1']}  **Målkurs Y1:** {row['Målkurs Y1']}")
    st.write(f"**Tillväxt Y2:** {row['Tillväxt Y2']}  **Målkurs Y2:** {row['Målkurs Y2']}")
    st.write(f"**Tillväxt Y3:** {row['Tillväxt Y3']}  **Målkurs Y3:** {row['Målkurs Y3']}")
