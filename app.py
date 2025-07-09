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

# Google Sheets
SPREADSHEET_URL = st.secrets["SPREADSHEET_URL"]
SHEET_NAME = "Bolag"
sheet = client.open_by_url(SPREADSHEET_URL)
worksheet = sheet.worksheet(SHEET_NAME)

# Kolumnrubriker
HEADERS = [
    "Bolag", "Ticker", "Senast uppdaterad", "Aktuell kurs",
    "P/S Q1", "P/S Q2", "P/S Q3", "P/S Q4", "Snitt P/S",
    "Omsättning 2023", "Omsättning 2024", "Omsättning 2025", "Omsättning 2026", "Omsättning 2027",
    "Tillväxt 2024", "Tillväxt 2025", "Tillväxt 2026", "Tillväxt 2027",
    "Målkurs 2025", "Målkurs 2026", "Målkurs 2027"
]

# Läs in data
def load_data():
    data = worksheet.get_all_records()
    if not data or list(data[0].keys()) != HEADERS:
        worksheet.clear()
        worksheet.append_row(HEADERS)
        return pd.DataFrame(columns=HEADERS)
    else:
        return pd.DataFrame(data)

df = load_data()

st.title("📊 Fundamental aktievärdering med P/S-modell")

# Formulär för nytt bolag
with st.form("add_stock_form"):
    st.subheader("Lägg till/uppdatera bolag")
    ticker_input = st.text_input("Ange Ticker (t.ex. AAPL, MSFT):", "")
    oms_2027_input = st.number_input("Ange förväntad omsättning 2027 (i miljoner USD):", min_value=0.0, value=0.0)
    submit = st.form_submit_button("📥 Hämta & Uppdatera bolag")

    if submit and ticker_input:
        try:
            ticker = ticker_input.upper()
            stock = yf.Ticker(ticker)
            info = stock.info

            name = info.get("shortName", "Okänt")
            kurs = round(info.get("currentPrice", 0), 2)
            oms_2023 = round(info.get("totalRevenue", 0) / 1e6, 2)
            hist_quarters = stock.quarterly_financials
            hist_prices = stock.history(period="1y", interval="3mo")

            # Beräkna P/S per kvartal (om data finns)
            ps_q = []
            for i in range(4):
                try:
                    rev = hist_quarters.iloc[:, i].sum() / 1e6
                    close_price = hist_prices["Close"].iloc[-(i + 1)]
                    ps_val = round(close_price / (rev / info.get("sharesOutstanding", 1e9)), 2)
                    ps_q.append(ps_val)
                except:
                    ps_q.append(0)

            snitt_ps = round(sum([v for v in ps_q if v > 0]) / max(1, len([v for v in ps_q if v > 0])), 2)

            # Omsättning prognos (Yahoo-analystat)
            oms_2024 = round(info.get("revenueEstimate", {}).get("2024", 0) / 1e6, 2) if isinstance(info.get("revenueEstimate", {}), dict) else 0
            oms_2025 = round(info.get("revenueEstimate", {}).get("2025", 0) / 1e6, 2) if isinstance(info.get("revenueEstimate", {}), dict) else 0
            oms_2026 = 0  # Hämtas ev i Del 3, annars 0

            # Tillväxt
            tillv_2025 = round(((oms_2025 - oms_2024) / oms_2024) * 100, 2) if oms_2024 > 0 else 0
            tillv_2026 = round(((oms_2026 - oms_2025) / oms_2025) * 100, 2) if oms_2025 > 0 else 0
            tillv_2027 = round(((oms_2027_input - oms_2026) / oms_2026) * 100, 2) if oms_2026 > 0 else 0

            # Målkurs
            def kalkylera_malkurs(oms, ps): return round(oms * ps / info.get("sharesOutstanding", 1e9), 2)

            malkurs_2025 = kalkylera_malkurs(oms_2025, snitt_ps)
            malkurs_2026 = kalkylera_malkurs(oms_2026, snitt_ps)
            malkurs_2027 = kalkylera_malkurs(oms_2027_input, snitt_ps)

            today = datetime.now().strftime("%Y-%m-%d %H:%M")

            ny_rad = {
                "Bolag": name,
                "Ticker": ticker,
                "Senast uppdaterad": today,
                "Aktuell kurs": kurs,
                "P/S Snitt": snitt_ps,
                "Omsättning 2023": oms_2023,
                "Omsättning 2024": oms_2024,
                "Omsättning 2025": oms_2025,
                "Omsättning 2026": oms_2026,
                "Omsättning 2027": oms_2027_input,
                "Tillväxt 2025 (%)": tillv_2025,
                "Tillväxt 2026 (%)": tillv_2026,
                "Tillväxt 2027 (%)": tillv_2027,
                "Målkurs 2025": malkurs_2025,
                "Målkurs 2026": malkurs_2026,
                "Målkurs 2027": malkurs_2027,
            }

            if ticker in df["Ticker"].values:
                idx = df[df["Ticker"] == ticker].index[0]
                df.loc[idx] = ny_rad
                st.success(f"{ticker} uppdaterad i databasen.")
            else:
                df = pd.concat([df, pd.DataFrame([ny_rad])], ignore_index=True)
                st.success(f"{ticker} tillagd i databasen.")

            # Uppdatera Google Sheet
            worksheet.clear()
            worksheet.append_row(list(ny_rad.keys()))
            worksheet.append_rows(df.values.tolist())

# === VISNING & NAVIGATION ===

st.header("📊 Värderingsvy")

if not df.empty:
    val_år = st.selectbox("Välj år att sortera efter undervärdering:", [2025, 2026, 2027])
    malkurs_kolumn = f"Målkurs {val_år}"

    if malkurs_kolumn in df.columns:
        df["Undervärdering"] = round((df[malkurs_kolumn] - df["Aktuell kurs"]) / df["Aktuell kurs"] * 100, 2)
        visnings_df = df.sort_values(by="Undervärdering", ascending=False).reset_index(drop=True)

        if "visnings_index" not in st.session_state:
            st.session_state.visnings_index = 0

        bolag = visnings_df.iloc[st.session_state.visnings_index]

        st.subheader(f"{bolag['Bolag']} ({bolag['Ticker']})")
        st.write(f"Aktuell kurs: {bolag['Aktuell kurs']} USD")
        st.write(f"P/S Snitt: {bolag['P/S Snitt']}")
        st.write(f"Tillväxt 2025: {bolag['Tillväxt 2025 (%)']}%")
        st.write(f"Tillväxt 2026: {bolag['Tillväxt 2026 (%)']}%")
        st.write(f"Tillväxt 2027: {bolag['Tillväxt 2027 (%)']}%")

        st.write(f"Målkurs 2025: {bolag['Målkurs 2025']} USD")
        st.write(f"Målkurs 2026: {bolag['Målkurs 2026']} USD")
        st.write(f"Målkurs 2027: {bolag['Målkurs 2027']} USD")

        st.write(f"Undervärdering {val_år}: {bolag['Undervärdering']} %")

        col1, col2 = st.columns([1, 1])
        with col1:
            if st.button("⬅️ Föregående") and st.session_state.visnings_index > 0:
                st.session_state.visnings_index -= 1
        with col2:
            if st.button("➡️ Nästa") and st.session_state.visnings_index < len(visnings_df) - 1:
                st.session_state.visnings_index += 1
    else:
        st.warning(f"Kolumnen '{malkurs_kolumn}' saknas i datan.")
else:
    st.info("Inga bolag inlagda ännu.")

# === INVESTERINGSREKOMMENDATION ===

st.header("💰 Investeringsförslag")

if not df.empty:
    kapital = st.number_input("Ange tillgängligt kapital (SEK):", min_value=0, value=1000, step=100)

    # Valfri årssats att grunda målkurs på
    invest_år = st.selectbox("Beräkna på målkurs för:", [2025, 2026, 2027])
    malkurs_kolumn = f"Målkurs {invest_år}"

    if malkurs_kolumn in df.columns:
        df["Uppvärderingspotential"] = df[malkurs_kolumn] / df["Aktuell kurs"]

        bäst = df[df["Uppvärderingspotential"] > 1].sort_values(by="Uppvärderingspotential", ascending=False)
        if not bäst.empty:
            kandidat = bäst.iloc[0]
            kurs = kandidat["Aktuell kurs"]
            ticker = kandidat["Ticker"]
            bolag = kandidat["Bolag"]
            målkurs = kandidat[malkurs_kolumn]
            p_s = kandidat["P/S Snitt"]

            st.subheader("📈 Bästa köpkandidat just nu")
            st.write(f"**{bolag} ({ticker})**")
            st.write(f"Aktuell kurs: {kurs} USD")
            st.write(f"Målkurs {invest_år}: {målkurs} USD")
            st.write(f"Uppvärderingspotential: {round((målkurs / kurs - 1) * 100, 2)}%")

            pris_i_sek = kurs * 10.5  # Grovväxling
            if kapital >= pris_i_sek:
                antal = int(kapital // pris_i_sek)
                st.success(f"📌 Köp {antal} st aktier i **{ticker}** ({round(antal * pris_i_sek)} kr)")
            else:
                st.warning(f"💸 Aktiekursen ({round(pris_i_sek)} kr) överstiger ditt kapital ({kapital} kr).")
                st.info(f"Behöver minst **{round(pris_i_sek - kapital)} kr** till för att köpa 1 aktie i {ticker}.")
        else:
            st.info("Inget bolag har uppvärderingspotential just nu.")
    else:
        st.warning(f"Saknar kolumn: {malkurs_kolumn}")
else:
    st.info("Ingen data att analysera.")
