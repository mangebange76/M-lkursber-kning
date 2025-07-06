import streamlit as st
import yfinance as yf
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime

# Konfiguration
st.set_page_config(page_title="Målkursberäkning", layout="centered")

# Google Sheets inställningar
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds = ServiceAccountCredentials.from_json_keyfile_dict(st.secrets["GOOGLE_CREDENTIALS"], scope)
client = gspread.authorize(creds)
SPREADSHEET_URL = st.secrets["SPREADSHEET_URL"]
SHEET_NAME = "Bolag"
SHEET = client.open_by_url(SPREADSHEET_URL).worksheet(SHEET_NAME)

# Kolumner som krävs
HEADERS = [
    "Ticker", "Namn", "Valuta", "Kurs", "Aktuell kurs", "P/S TTM", "P/E TTM",
    "Tillväxt 2025 (%)", "Tillväxt 2026 (%)", "Tillväxt 2027 (%)",
    "Omsättning TTM", "Målkurs 2025", "Målkurs 2026", "Målkurs 2027",
    "Senast uppdaterad"
]

# Kontrollera och skapa rubriker om de saknas eller är fel
def ensure_headers():
    existing = SHEET.row_values(1)
    if existing != HEADERS:
        SHEET.resize(rows=1)
        SHEET.insert_row(HEADERS, 1)

# Läser in datan från kalkylarket
def load_data():
    ensure_headers()
    records = SHEET.get_all_records()
    return pd.DataFrame(records)

# Spara nytt bolag eller uppdatera existerande
def save_to_sheet(data):
    df = load_data()
    tickers = df["Ticker"].tolist()
    if data["Ticker"] in tickers:
        index = tickers.index(data["Ticker"]) + 2
        SHEET.delete_row(index)
    row = [data.get(col, "") for col in HEADERS]
    SHEET.append_row(row)

# Konvertera decimal från t.ex. 74,41 till 74.41
def parse_decimal(val):
    try:
        if isinstance(val, str):
            val = val.replace(",", ".")
        return round(float(val), 2)
    except:
        return None

# Hämtar bolagsdata och gör beräkningar
def analyze_ticker(ticker, growth_2027=None):
    try:
        ticker = ticker.upper()
        stock = yf.Ticker(ticker)
        info = stock.info

        name = info.get("longName", ticker)
        currency = info.get("currency", "USD")
        current_price = float(info.get("currentPrice", 0))
        shares_outstanding = float(info.get("sharesOutstanding", 0))
        history = stock.quarterly_financials
        revenue_quarters = history.loc["Total Revenue"].dropna()
        if len(revenue_quarters) < 4:
            return None

        revenue_ttm = revenue_quarters[:4].sum()
        ps_ttm = round((current_price * shares_outstanding) / revenue_ttm, 2)

        earnings_history = stock.quarterly_earnings
        eps_quarters = earnings_history["Earnings"].dropna()
        eps_ttm = eps_quarters[:4].sum() if len(eps_quarters) >= 4 else None
        pe_ttm = round(current_price / eps_ttm, 2) if eps_ttm and eps_ttm != 0 else None

        growth_2025 = info.get("revenueGrowth", 0.15)
        growth_2026 = growth_2025 * 0.9
        growth_2027 = growth_2027 if growth_2027 is not None else round(growth_2026 * 0.9, 2)

        revenue_2025 = revenue_ttm * (1 + growth_2025)
        revenue_2026 = revenue_2025 * (1 + growth_2026)
        revenue_2027 = revenue_2026 * (1 + growth_2027)

        avg_ps = ps_ttm
        shares = shares_outstanding

        def calc_target(revenue):
            return round((revenue / shares) * avg_ps, 2)

        target_2025 = calc_target(revenue_2025)
        target_2026 = calc_target(revenue_2026)
        target_2027 = calc_target(revenue_2027)

        return {
            "Ticker": ticker,
            "Namn": name,
            "Valuta": currency,
            "Kurs": round(current_price, 2),
            "Aktuell kurs": round(current_price, 2),
            "P/S TTM": ps_ttm,
            "P/E TTM": pe_ttm if pe_ttm else "",
            "Tillväxt 2025 (%)": round(growth_2025 * 100, 2),
            "Tillväxt 2026 (%)": round(growth_2026 * 100, 2),
            "Tillväxt 2027 (%)": round(growth_2027 * 100, 2),
            "Omsättning TTM": int(revenue_ttm),
            "Målkurs 2025": target_2025,
            "Målkurs 2026": target_2026,
            "Målkurs 2027": target_2027,
            "Senast uppdaterad": datetime.now().strftime("%Y-%m-%d")
        }
    except Exception as e:
        st.error(f"Något gick fel: {e}")
        return None

# --- Gränssnitt ---
st.title("📊 Målkursberäkning med tillväxt och multipel")

with st.form("new_ticker_form"):
    st.subheader("Lägg till eller uppdatera bolag")
    new_ticker = st.text_input("Ange ticker (t.ex. TTD)", max_chars=10)
    custom_growth_2027 = st.number_input("Manuell tillväxt 2027 (%)", min_value=0.0, max_value=200.0, value=20.0)
    submitted = st.form_submit_button("Analysera och spara")
    if submitted and new_ticker:
        data = analyze_ticker(new_ticker, custom_growth_2027 / 100)
        if data:
            save_to_sheet(data)
            st.success(f"{data['Namn']} sparad!")

# Visa sorterade bolag
df = load_data()
if df.empty:
    st.warning("❌ Inga bolag inlagda än.")
else:
    sort_key = st.selectbox("Sortera efter:", ["Målkurs 2025", "Målkurs 2026", "Målkurs 2027"])
    df["Undervärdering"] = (df[sort_key] - df["Aktuell kurs"]) / df["Aktuell kurs"]
    df = df.sort_values(by="Undervärdering", ascending=False).reset_index(drop=True)

    if "page" not in st.session_state:
        st.session_state.page = 0

    total = len(df)
    current = st.session_state.page
    company = df.iloc[current]

    st.markdown(f"### {company['Namn']} ({company['Ticker']})")
    st.write(f"**Kategori:** _(ej ifyllt)_")
    st.write(f"**Aktuell kurs:** {company['Aktuell kurs']} {company['Valuta']}")
    st.write(f"**P/S TTM:** {company['P/S TTM']}  **P/E TTM:** {company['P/E TTM']}")

    st.markdown("### 📈 Tillväxt och målkurs")
    for y in ["2025", "2026", "2027"]:
        st.write(f"**Tillväxt Y{y[-1]}:** {company[f'Tillväxt {y} (%)']}%")
        st.write(f"**Målkurs Y{y[-1]}:** {company[f'Målkurs {y}']}")
        st.caption("Tidigare målkurs: _(ej spårad än)_")

    col1, col2 = st.columns(2)
    if col1.button("⬅️ Föregående") and current > 0:
        st.session_state.page -= 1
    if col2.button("➡️ Nästa") and current < total - 1:
        st.session_state.page += 1
