import streamlit as st
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import yfinance as yf
import pandas as pd
import datetime
import json

st.set_page_config(page_title="Målkursanalys", layout="centered")

# Autentisera med Google Sheets
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds_dict = json.loads(st.secrets["GOOGLE_CREDENTIALS"])
creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
client = gspread.authorize(creds)

SPREADSHEET_URL = st.secrets["SPREADSHEET_URL"]
SHEET_NAME = "Data"
sheet = client.open_by_url(SPREADSHEET_URL)
worksheet = sheet.worksheet(SHEET_NAME)

# Rubriker som krävs
HEADERS = [
    "Ticker", "Namn", "Valuta", "Kurs", "Aktuell kurs", "P/S TTM", "P/E TTM",
    "Tillväxt 2025 (%)", "Tillväxt 2026 (%)", "Tillväxt 2027 (%)",
    "Omsättning TTM", "Målkurs 2025", "Målkurs 2026", "Målkurs 2027",
    "Senast uppdaterad"
]

# Säkerställ att rubriker finns
def ensure_headers():
    try:
        current = worksheet.row_values(1)
        if current != HEADERS:
            worksheet.delete_rows(1)
            worksheet.insert_row(HEADERS, 1)
    except Exception:
        worksheet.insert_row(HEADERS, 1)

ensure_headers()

# Funktion: Lägg till bolag
def add_company(ticker_input, tillv_2027):
    try:
        ticker = ticker_input.upper()
        data = yf.Ticker(ticker)
        info = data.info

        name = info.get("longName", "")
        currency = info.get("currency", "")
        current_price = round(float(info.get("currentPrice", 0)), 2)
        shares_out = info.get("sharesOutstanding", 1)
        revenue_ttm = info.get("totalRevenue", 0)

        # Hämta historiska kvartalsrapporter (omsättning & EPS)
        hist = data.quarterly_financials.T
        if hist.empty or "Total Revenue" not in hist.columns or "Basic EPS" not in data.quarterly_earnings.columns:
            st.error("Kunde inte hämta kvartalsdata för omsättning eller EPS.")
            return

        # TTM Revenue per kvartal = summera 4 senaste
        hist_rev = hist["Total Revenue"].dropna().astype(float)
        rev_ttm_list = [hist_rev[i:i+4].sum() for i in range(len(hist_rev)-3)]
        price_hist = data.history(period="1y", interval="3mo")["Close"].dropna().tolist()[-len(rev_ttm_list):]
        ps_list = [round(price / (rev / shares_out), 2) if rev > 0 else 0 for price, rev in zip(price_hist, rev_ttm_list)]
        avg_ps_ttm = round(sum(ps_list) / len(ps_list), 2) if ps_list else 0

        eps_q = data.quarterly_earnings["Earnings"].dropna().astype(float)
        eps_ttm_list = [eps_q[i:i+4].sum() for i in range(len(eps_q)-3)]
        pe_list = [round(price / eps, 2) if eps > 0 else 0 for price, eps in zip(price_hist, eps_ttm_list)]
        avg_pe_ttm = round(sum(pe_list) / len(pe_list), 2) if pe_list else 0

        # Hämta tillväxt
        forecast = info.get("earningsGrowth", 0)
        tillv_2025 = round(forecast * 100 if forecast else 20.0, 1)
        tillv_2026 = tillv_2025 * 0.88
        tillv_2027 = float(tillv_2027)

        # Målkursberäkningar
        oms_2025 = revenue_ttm * (1 + tillv_2025 / 100)
        oms_2026 = oms_2025 * (1 + tillv_2026 / 100)
        oms_2027 = oms_2026 * (1 + tillv_2027 / 100)

        kurs_2025 = round((oms_2025 / shares_out) * avg_ps_ttm, 2)
        kurs_2026 = round((oms_2026 / shares_out) * avg_ps_ttm, 2)
        kurs_2027 = round((oms_2027 / shares_out) * avg_ps_ttm, 2)

        row = [
            ticker, name, currency, current_price, current_price, avg_ps_ttm, avg_pe_ttm,
            round(tillv_2025, 1), round(tillv_2026, 1), round(tillv_2027, 1),
            revenue_ttm, kurs_2025, kurs_2026, kurs_2027,
            datetime.date.today().isoformat()
        ]

        worksheet.append_row(row)
        st.success(f"{ticker} har lagts till!")
    except Exception as e:
        st.error(f"Något gick fel: {e}")

# Ladda data från Google Sheet
def load_data():
    df = pd.DataFrame(worksheet.get_all_records())
    df["Undervärdering 2027 (%)"] = round((df["Målkurs 2027"] - df["Aktuell kurs"]) / df["Aktuell kurs"] * 100, 1)
    df = df.sort_values(by="Undervärdering 2027 (%)", ascending=False).reset_index(drop=True)
    return df

# UI – Inmatning av bolag
st.title("📈 Aktieanalys – Målkursberäkning")
st.subheader("Lägg till nytt bolag")
ticker_input = st.text_input("Ticker (t.ex. TTD eller NVDA)")
tillv_input = st.text_input("Förväntad tillväxt 2027 (%)", value="15")

if st.button("Lägg till bolag"):
    if ticker_input and tillv_input:
        add_company(ticker_input, tillv_input)
    else:
        st.warning("Fyll i både ticker och tillväxt för 2027.")

# Visa data – en i taget
df = load_data()
if not df.empty:
    index = st.number_input("Visa bolag #", min_value=1, max_value=len(df), value=1, step=1) - 1
    row = df.iloc[index]
    st.markdown(f"### {row['Namn']} ({row['Ticker']})")
    st.write(f"**Aktuell kurs:** {row['Aktuell kurs']:.2f} {row['Valuta']}")
    st.write(f"**P/S TTM:** {row['P/S TTM']}, **P/E TTM:** {row['P/E TTM']}")
    st.write(f"**Tillväxt:** 2025: {row['Tillväxt 2025 (%)']} %, 2026: {row['Tillväxt 2026 (%)']} %, 2027: {row['Tillväxt 2027 (%)']} %")
    st.write(f"**Målkurs 2025:** {row['Målkurs 2025']} {row['Valuta']}")
    st.write(f"**Målkurs 2026:** {row['Målkurs 2026']} {row['Valuta']}")
    st.write(f"**Målkurs 2027:** {row['Målkurs 2027']} {row['Valuta']}")
    st.write(f"**Undervärdering 2027:** {row['Undervärdering 2027 (%)']} %")
    st.caption(f"Senast uppdaterad: {row['Senast uppdaterad']}")
else:
    st.info("Inga bolag inlagda än.")
