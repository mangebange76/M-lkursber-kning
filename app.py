# ----------------------- Del 1 -----------------------

import streamlit as st
import pandas as pd
import gspread
from google.oauth2 import service_account
from datetime import datetime
import yfinance as yf

st.set_page_config(page_title="Aktievärdering", layout="centered")

# Autentisering
scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
creds = service_account.Credentials.from_service_account_info(
    st.secrets["GOOGLE_CREDENTIALS"], scopes=scope
)
client = gspread.authorize(creds)

# Hämta Google Sheet
spreadsheet_url = st.secrets["SPREADSHEET_URL"]
sheet = client.open_by_url(spreadsheet_url)
worksheet = sheet.worksheet("Bolag")

# Obligatoriska kolumner
required_headers = [
    "Bolag", "Ticker", "Senast uppdaterad", "Aktuell kurs", "TTM Sales", "TTM EPS",
    "Antal aktier", "Omsättning 2023", "Omsättning 2024", "Omsättning 2025", "Omsättning 2026",
    "P/S snitt", "Tillväxt 2024", "Tillväxt 2025", "Tillväxt 2026"
]

# Hämta data från arket
rows = worksheet.get_all_records()
if not rows or list(rows[0].keys()) != required_headers:
    worksheet.clear()
    worksheet.append_row(required_headers)
    df = pd.DataFrame(columns=required_headers)
else:
    df = pd.DataFrame(rows)

# ----------------------- Del 2 -----------------------

st.title("📈 Fundamental aktievärdering")

with st.form("add_stock_form"):
    st.subheader("Lägg till eller uppdatera bolag")
    ticker_input = st.text_input("Ange Ticker (t.ex. AAPL, MSFT)", "")
    user_growth_2026 = st.number_input("Ange förväntad tillväxt % för 2026", min_value=-100.0, max_value=500.0, value=15.0, step=0.1)
    submitted = st.form_submit_button("📥 Hämta & Lägg till / Uppdatera")

    if submitted and ticker_input:
        try:
            ticker = ticker_input.upper()
            stock = yf.Ticker(ticker)
            info = stock.info

            name = info.get("shortName", "Okänt")
            current_price = round(info.get("currentPrice", 0), 2)
            total_sales = info.get("totalRevenue", None)
            ttm_sales = round(total_sales / 1e6, 2) if total_sales else 0
            ttm_eps = round(info.get("trailingEps", 0), 2)
            shares_outstanding = round(info.get("sharesOutstanding", 0), 2)
            now = datetime.now().strftime("%Y-%m-%d %H:%M")

            # Hämta historiska omsättningar och framtida tillväxt om tillgängligt
            rev_2023 = info.get("revenue2023", 0) or 0
            rev_2024 = info.get("revenue2024", 0) or 0
            rev_2025 = info.get("revenue2025", 0) or 0
            growth_2024 = info.get("growth2024", 0) or 0
            growth_2025 = info.get("growth2025", 0) or 0
            rev_2026 = rev_2025 * (1 + user_growth_2026 / 100) if rev_2025 else 0

            # Placeholder för P/S snitt – kan justeras i Del 3
            ps_snitt = round(current_price / (ttm_sales / shares_outstanding), 2) if ttm_sales and shares_outstanding else 0

            new_data = {
                "Bolag": name,
                "Ticker": ticker,
                "Senast uppdaterad": now,
                "Aktuell kurs": current_price,
                "TTM Sales": ttm_sales,
                "TTM EPS": ttm_eps,
                "Antal aktier": shares_outstanding,
                "Omsättning 2023": rev_2023,
                "Omsättning 2024": rev_2024,
                "Omsättning 2025": rev_2025,
                "Omsättning 2026": round(rev_2026, 2),
                "P/S snitt": ps_snitt,
                "Tillväxt 2024": growth_2024,
                "Tillväxt 2025": growth_2025,
                "Tillväxt 2026": user_growth_2026
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
            st.error(f"❌ Något gick fel: {e}")

# ----------------------- Del 3 -----------------------

# Visa tabell
st.subheader("📄 Aktiedata från Google Sheet")
st.dataframe(df)

# Beräkna målkurs för 2025, 2026, 2027 baserat på P/S snitt och omsättning
def calculate_valuations(row):
    try:
        ps = float(row.get("P/S snitt", 0))
        shares = float(row.get("Antal aktier", 0))

        rev_2025 = float(row.get("Omsättning 2025", 0))
        rev_2026 = float(row.get("Omsättning 2026", 0))

        target_now = ps * rev_2025 * 1e6 / shares if ps and rev_2025 and shares else 0
        target_2026 = ps * rev_2026 * 1e6 / shares if ps and rev_2026 and shares else 0

        # Använd tillväxt för 2026 för att skatta 2027
        growth_2026 = float(row.get("Tillväxt 2026", 0))
        rev_2027 = rev_2026 * (1 + growth_2026 / 100) if rev_2026 else 0
        target_2027 = ps * rev_2027 * 1e6 / shares if ps and rev_2027 and shares else 0

        return round(target_now, 2), round(target_2026, 2), round(target_2027, 2)
    except Exception:
        return 0, 0, 0

# Lägg till kolumner i df
df["Målkurs 2025"] = 0.0
df["Målkurs 2026"] = 0.0
df["Målkurs 2027"] = 0.0

for i, row in df.iterrows():
    m25, m26, m27 = calculate_valuations(row)
    df.at[i, "Målkurs 2025"] = m25
    df.at[i, "Målkurs 2026"] = m26
    df.at[i, "Målkurs 2027"] = m27

# ----------------------- Del 4 -----------------------

def visa_varderingsvy(df, vy_ar="2025"):
    st.header("📊 Värderingsvy")

    # Filtrera bort rader utan fullständig data
    df_filtered = df.dropna(subset=[
        "Bolag", "Ticker", "Aktuell kurs", f"Omsättning {vy_ar}", f"P/S snitt"
    ])

    if df_filtered.empty:
        st.info("Ingen komplett data för att visa värderingsvyn.")
        return

    # Beräkna nuvarande P/S
    df_filtered["P/S nu"] = df_filtered["Aktuell kurs"] / (df_filtered["Omsättning 2024"] / df_filtered["Antal aktier"])

    # Beräkna målkurs för valt år
    df_filtered["Målkurs"] = df_filtered[f"Omsättning {vy_ar}"] / df_filtered["Antal aktier"] * df_filtered["P/S snitt"]

    # Undervärdering = målkurs - aktuell kurs
    df_filtered["Undervärdering"] = df_filtered["Målkurs"] - df_filtered["Aktuell kurs"]

    # Sortera
    df_sorted = df_filtered.sort_values(by="Undervärdering", ascending=False).reset_index(drop=True)

    # Navigering
    st.session_state.setdefault("vy_index", 0)
    if st.button("⬅️ Föregående"):
        st.session_state["vy_index"] = max(0, st.session_state["vy_index"] - 1)
    if st.button("➡️ Nästa"):
        st.session_state["vy_index"] = min(len(df_sorted) - 1, st.session_state["vy_index"] + 1)

    # Visa bolag
    rad = df_sorted.iloc[st.session_state["vy_index"]]
    st.subheader(f"{rad['Bolag']} ({rad['Ticker']})")
    st.write(f"Aktuell kurs: {rad['Aktuell kurs']:.2f} USD")
    st.write(f"P/S snitt: {rad['P/S snitt']:.2f}")
    st.write(f"Omsättning {vy_ar}: {rad[f'Omsättning {vy_ar}']:.0f} MUSD")
    st.write(f"Målkurs {vy_ar}: {rad['Målkurs']:.2f} USD")
    st.write(f"Undervärdering: {rad['Undervärdering']:.2f} USD")

# ----------------------- Del 5 -----------------------

# Välj vilket år som ska styra undervärderingssorteringen
st.subheader("📈 Värderingssortering")
sort_year = st.selectbox("Sortera på undervärdering enligt år:", ["2025", "2026", "2027"])
sort_column = f"Målkurs {sort_year}"

# Filtrera bolag med kurs > 0 och målkurs > 0
df_filtered = df[(df["Aktuell kurs"] > 0) & (df[sort_column] > 0)].copy()
df_filtered["Undervärdering (%)"] = round((df_filtered[sort_column] - df_filtered["Aktuell kurs"]) / df_filtered["Aktuell kurs"] * 100, 2)
df_filtered = df_filtered.sort_values(by="Undervärdering (%)", ascending=False).reset_index(drop=True)

# Navigering mellan bolag
if "current_index" not in st.session_state:
    st.session_state.current_index = 0

if not df_filtered.empty:
    col1, col2 = st.columns(2)
    with col1:
        if st.button("⬅️ Föregående") and st.session_state.current_index > 0:
            st.session_state.current_index -= 1
    with col2:
        if st.button("➡️ Nästa") and st.session_state.current_index < len(df_filtered) - 1:
            st.session_state.current_index += 1

    bolag = df_filtered.iloc[st.session_state.current_index]

    st.header("📊 Värderingsvy")
    st.markdown(f"""
    **{bolag['Bolag']} ({bolag['Ticker']})**  
    📈 **Aktuell kurs:** {bolag['Aktuell kurs']:.2f} USD  
    🔢 **P/S-snitt:** {bolag['P/S snitt']:.2f}  
    📦 **Antal aktier:** {bolag['Antal aktier']:,}  
    🧾 **Omsättning 2025:** {bolag['Omsättning 2025']:.2f} MUSD  
    🔮 **Omsättning 2026:** {bolag['Omsättning 2026']:.2f} MUSD  
    📉 **Tillväxt 2026:** {bolag['Tillväxt 2026']} %  
    🎯 **Målkurs 2025:** {bolag['Målkurs 2025']:.2f} USD  
    🎯 **Målkurs 2026:** {bolag['Målkurs 2026']:.2f} USD  
    🎯 **Målkurs 2027:** {bolag['Målkurs 2027']:.2f} USD  
    🧮 **Undervärdering:** {bolag['Undervärdering (%)']:.2f} %
    """)
else:
    st.warning("Inga bolag med giltiga värden att visa.")

# ----------------------- Del 6 -----------------------

st.header("🧠 Investeringsförslag & Uppdatering")

# Ange tillgängligt kapital
kapital = st.number_input("Tillgängligt kapital (USD):", min_value=0.0, step=100.0)

# Generera investeringsförslag
if not df_filtered.empty:
    bästa = df_filtered.iloc[0]
    if bästa["Aktuell kurs"] <= kapital:
        antal = int(kapital // bästa["Aktuell kurs"])
        kostnad = antal * bästa["Aktuell kurs"]
        st.success(f"📌 Köpförslag: {antal} st {bästa['Ticker']} för totalt {kostnad:.2f} USD.")
    else:
        st.info(f"💡 Bästa val är {bästa['Ticker']} ({bästa['Bolag']}) men du behöver minst {bästa['Aktuell kurs']:.2f} USD.")

# Visa tabell för manuell inmatning av Omsättning 2027
st.subheader("📤 Lägg till Omsättning 2027 manuellt")
edited_df = st.data_editor(df[["Ticker", "Omsättning 2027"]], num_rows="dynamic")

if st.button("💾 Spara ändringar för Omsättning 2027"):
    for index, row in edited_df.iterrows():
        ticker = row["Ticker"]
        value = row["Omsättning 2027"]
        try:
            sheet_row = df[df["Ticker"] == ticker].index[0] + 2
            col_idx = df.columns.get_loc("Omsättning 2027") + 1
            worksheet.update_cell(sheet_row, col_idx, value)
        except Exception as e:
            st.error(f"Fel vid uppdatering för {ticker}: {e}")
    st.success("Omsättning 2027 uppdaterad!")

# Uppdatera all data-knapp
if st.button("🔄 Uppdatera alla bolag"):
    try:
        tickers = df["Ticker"].dropna().unique().tolist()
        for ticker in tickers:
            stock = yf.Ticker(ticker)
            info = stock.info
            hist = stock.history(period="1y")

            current_price = round(info.get("currentPrice", 0), 2)
            shares_out = info.get("sharesOutstanding", 0)

            oms_hist = []
            p_s_hist = []

            for q in hist.resample("Q").last().iterrows():
                kurs = q[1]["Close"]
                quarter_sales = info.get("totalRevenue", 0)  # Fallback
                p_s = (kurs * shares_out) / quarter_sales if quarter_sales else 0
                if p_s > 0:
                    p_s_hist.append(p_s)

            snitt_p_s = round(sum(p_s_hist[-4:]) / len(p_s_hist[-4:]), 2) if p_s_hist else 0
            oms_2025 = info.get("revenueEstimate", {}).get("2025", 0) / 1e6 if info.get("revenueEstimate") else 0
            oms_2026 = info.get("revenueEstimate", {}).get("2026", 0) / 1e6 if info.get("revenueEstimate") else 0

            tillväxt_2026 = round((oms_2026 - oms_2025) / oms_2025 * 100, 2) if oms_2025 > 0 else 0
            oms_2027 = df[df["Ticker"] == ticker]["Omsättning 2027"].values[0]

            målkurs_2025 = snitt_p_s * oms_2025 / (shares_out / 1e6) if shares_out else 0
            målkurs_2026 = snitt_p_s * oms_2026 / (shares_out / 1e6) if shares_out else 0
            målkurs_2027 = snitt_p_s * oms_2027 / (shares_out / 1e6) if shares_out else 0

            idx = df[df["Ticker"] == ticker].index[0] + 2
            update_map = {
                "Aktuell kurs": current_price,
                "P/S snitt": snitt_p_s,
                "Omsättning 2025": oms_2025,
                "Omsättning 2026": oms_2026,
                "Tillväxt 2026": tillväxt_2026,
                "Målkurs 2025": målkurs_2025,
                "Målkurs 2026": målkurs_2026,
                "Målkurs 2027": målkurs_2027
            }

            for col, val in update_map.items():
                col_idx = df.columns.get_loc(col) + 1
                worksheet.update_cell(idx, col_idx, round(val, 2))
        st.success("Alla bolag uppdaterade!")
    except Exception as e:
        st.error(f"Något gick fel: {e}")

# ----------------------- Del 7 -----------------------

def main():
    st.set_page_config(page_title="Aktievärdering & Investeringsförslag", layout="wide")
    # Kör hela appen
    pass  # Allt körs redan i huvudflödet (det finns ingen separat struktur att kapsla in)

if __name__ == "__main__":
    main()
