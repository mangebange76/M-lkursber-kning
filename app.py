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

# === Del 4 ===

try:
    st.header("📊 Värderingsvy")

    sorteringsår = st.selectbox("Sortera undervärdering baserat på:", [2025, 2026, 2027])

    # Visa bolag sorterat efter undervärdering (baserat på vald år)
    if not df.empty:
        sorteringskolumn = f"Undervärdering {sorteringsår}"
        if sorteringskolumn in df.columns:
            visningsindex = st.session_state.get("visningsindex", 0)
            df_sorted = df.sort_values(by=sorteringskolumn, ascending=False).reset_index(drop=True)

            if visningsindex >= len(df_sorted):
                visningsindex = 0

            bolag_data = df_sorted.loc[visningsindex]
            st.write(f"**{bolag_data['Bolag']} ({bolag_data['Ticker']})**")
            st.metric("Aktuell kurs", f"${bolag_data['Aktuell kurs']:.2f}")
            st.metric("Snitt P/S", f"{bolag_data['Snitt P/S 4Q']:.2f}")
            st.metric(f"Målkurs {sorteringsår}", f"${bolag_data[f'Målkurs {sorteringsår}']:.2f}")

            # Navigering
            col1, col2 = st.columns(2)
            with col1:
                if st.button("⬅️ Föregående"):
                    st.session_state.visningsindex = (visningsindex - 1) % len(df_sorted)
            with col2:
                if st.button("➡️ Nästa"):
                    st.session_state.visningsindex = (visningsindex + 1) % len(df_sorted)

except Exception as e:
    st.error(f"Fel i värderingsvyn: {e}")

# === Del 5 ===

st.header("💰 Investeringsförslag")

tillgängligt_kapital = st.number_input("Ange tillgängligt kapital (SEK)", min_value=0, step=100, value=1000)

if "Senast föreslaget bolag" not in st.session_state:
    st.session_state["Senast föreslaget bolag"] = None

# Få fram bästa undervärderade bolag
try:
    if not df.empty and "Undervärdering 2025" in df.columns:
        df_invest = df[df["Aktuell kurs"] > 0].copy()
        df_invest = df_invest.sort_values(by="Undervärdering 2025", ascending=False)

        for _, row in df_invest.iterrows():
            bolag = row["Bolag"]
            ticker = row["Ticker"]
            kurs = row["Aktuell kurs"]

            if kurs <= tillgängligt_kapital:
                st.success(f"💡 Köpförslag: **{bolag} ({ticker})** – aktuell kurs: ${kurs:.2f}")
                st.session_state["Senast föreslaget bolag"] = ticker
                break
        else:
            dyraste = df_invest.iloc[0]
            st.warning(
                f"Inget bolag kan köpas för {tillgängligt_kapital} SEK.\n"
                f"Förslag: **{dyraste['Bolag']} ({dyraste['Ticker']})** kostar ${dyraste['Aktuell kurs']:.2f}. "
                f"Du behöver mer kapital."
            )

except Exception as e:
    st.error(f"Fel i investeringsförslag: {e}")

# === Del 6: main() och appstart ===

def main():
    st.set_page_config(page_title="Aktievärdering", layout="wide")

    st.markdown(
        """
        <style>
        section[data-testid="stSidebar"] {
            background-color: #f0f2f6;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    st.sidebar.title("📁 Meny")
    view = st.sidebar.radio("Välj vy", ["📄 Bolagsdata", "📊 Värderingsvy", "💰 Investeringsförslag"])

    if view == "📄 Bolagsdata":
        st.experimental_rerun()  # Detta låter användaren välja vy och få rätt vy att visas (kan tas bort om statisk app)
    elif view == "📊 Värderingsvy":
        pass  # Hanteras i Del 4
    elif view == "💰 Investeringsförslag":
        pass  # Hanteras i Del 5


# === Starta appen ===
if __name__ == "__main__":
    main()
