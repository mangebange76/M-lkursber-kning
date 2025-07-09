import streamlit as st
import pandas as pd
import yfinance as yf
import gspread
from google.oauth2 import service_account
from datetime import datetime

# Autentisering
scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
creds = service_account.Credentials.from_service_account_info(
    st.secrets["GOOGLE_CREDENTIALS"], scopes=scope
)
client = gspread.authorize(creds)

# Öppna Google Sheet
spreadsheet_url = st.secrets["SPREADSHEET_URL"]
sheet = client.open_by_url(spreadsheet_url)
worksheet = sheet.worksheet("Bolag")

# Läs in data från Google Sheet
headers = worksheet.row_values(1)
data = worksheet.get_all_records()
df = pd.DataFrame(data)
if df.empty:
    df = pd.DataFrame(columns=headers)

st.title("📈 Fundamental Värdering med P/S-modell")

st.subheader("➕ Lägg till eller uppdatera bolag")

with st.form("add_stock_form"):
    ticker_input = st.text_input("Ange Ticker (ex: AAPL, MSFT, NVDA)", "")
    omsättning_2027 = st.number_input("Ange förväntad omsättning 2027 (MUSD):", min_value=0.0, step=0.1)
    submitted = st.form_submit_button("Hämta & Uppdatera")

    if submitted and ticker_input:
        try:
            ticker = ticker_input.upper()
            stock = yf.Ticker(ticker)
            info = stock.info

            namn = info.get("shortName", "Okänt")
            kurs = round(info.get("currentPrice", 0), 2)
            omsättning_ttm = round(info.get("totalRevenue", 0) / 1e6, 2)
            oms_2025 = round(info.get("revenueForecastNextFiscalYear", 0) / 1e6, 2)
            oms_2026 = round(info.get("revenueForecastNext+1Year", 0) / 1e6, 2)

            updated = False
            for i, row in df.iterrows():
                if row["Ticker"] == ticker:
                    df.at[i, "Bolag"] = namn
                    df.at[i, "Aktuell kurs"] = kurs
                    df.at[i, "Omsättning TTM"] = omsättning_ttm
                    df.at[i, "Omsättning 2025"] = oms_2025
                    df.at[i, "Omsättning 2026"] = oms_2026
                    df.at[i, "Omsättning 2027"] = omsättning_2027
                    df.at[i, "Senast uppdaterad"] = datetime.now().strftime("%Y-%m-%d %H:%M")
                    updated = True
                    break

            if not updated:
                ny_rad = {
                    "Bolag": namn,
                    "Ticker": ticker,
                    "Aktuell kurs": kurs,
                    "Omsättning TTM": omsättning_ttm,
                    "Omsättning 2025": oms_2025,
                    "Omsättning 2026": oms_2026,
                    "Omsättning 2027": omsättning_2027,
                    "Senast uppdaterad": datetime.now().strftime("%Y-%m-%d %H:%M")
                }
                df = df.append(ny_rad, ignore_index=True)

            worksheet.clear()
            worksheet.append_row(df.columns.tolist())
            for row in df.values.tolist():
                worksheet.append_row(row)

            st.success(f"{ticker} uppdaterad.")
        except Exception as e:
            st.error(f"Något gick fel: {e}")

def beräkna_analys(df):
    df["Snitt P/S"] = None
    df["Målkurs 2025"] = None
    df["Målkurs 2026"] = None
    df["Målkurs 2027"] = None
    df["Undervärdering (%)"] = None

    for i, row in df.iterrows():
        try:
            ttm = row["Omsättning TTM"]
            kurs = row["Aktuell kurs"]
            ps_ttm = kurs / ttm if ttm else None

            snitt_ps = ps_ttm  # Här kan man lägga till historiska P/S om tillgängligt
            df.at[i, "Snitt P/S"] = round(snitt_ps, 2) if snitt_ps else None

            for år in [2025, 2026, 2027]:
                omsättning = row.get(f"Omsättning {år}")
                if pd.notna(snitt_ps) and pd.notna(omsättning) and omsättning > 0:
                    målkurs = snitt_ps * omsättning
                    df.at[i, f"Målkurs {år}"] = round(målkurs, 2)

            if pd.notna(df.at[i, "Målkurs 2025"]) and kurs > 0:
                undervärde = (df.at[i, "Målkurs 2025"] - kurs) / kurs * 100
                df.at[i, "Undervärdering (%)"] = round(undervärde, 2)
        except Exception as e:
            print(f"Fel vid beräkning för {row['Ticker']}: {e}")
    return df

def uppdatera_alla_bolag(df, worksheet):
    from datetime import datetime
    import yfinance as yf

    uppdaterad_df = df.copy()
    for index, row in df.iterrows():
        ticker = row["Ticker"]
        try:
            aktie = yf.Ticker(ticker)
            info = aktie.info

            nuvarande_kurs = round(info.get("currentPrice", 0), 2)
            ttm_sales = round(info.get("totalRevenue", 0) / info.get("sharesOutstanding", 1), 2) if info.get("totalRevenue") else None
            omsättning_2025 = info.get("revenueEstimate", {}).get("2025")  # Custom key
            omsättning_2026 = info.get("revenueEstimate", {}).get("2026")  # Custom key

            uppdaterad_df.at[index, "Aktuell kurs"] = nuvarande_kurs
            uppdaterad_df.at[index, "Omsättning TTM"] = ttm_sales
            uppdaterad_df.at[index, "Senast uppdaterad"] = datetime.now().strftime("%Y-%m-%d %H:%M")

            if omsättning_2025:
                uppdaterad_df.at[index, "Omsättning 2025"] = round(omsättning_2025 / info.get("sharesOutstanding", 1), 2)
            if omsättning_2026:
                uppdaterad_df.at[index, "Omsättning 2026"] = round(omsättning_2026 / info.get("sharesOutstanding", 1), 2)

        except Exception as e:
            st.warning(f"Kunde inte uppdatera {ticker}: {e}")

    # Skriv tillbaka uppdaterad data till Google Sheet
    worksheet.clear()
    worksheet.append_row(list(uppdaterad_df.columns))
    for _, row in uppdaterad_df.iterrows():
        worksheet.append_row([row[col] if pd.notna(row[col]) else "" for col in uppdaterad_df.columns])

    return uppdaterad_df

def beräkna_målkurser(df):
    df = df.copy()

    for år in ["2025", "2026", "2027"]:
        kol_omsättning = f"Omsättning {år}"
        kol_målkurs = f"Målkurs {år}"
        kol_p_s = "P/S TTM"

        if kol_omsättning not in df.columns:
            df[kol_omsättning] = None

        df[kol_målkurs] = None
        for i, row in df.iterrows():
            try:
                if (
                    pd.notna(row.get(kol_omsättning))
                    and pd.notna(row.get(kol_p_s))
                    and row.get(kol_p_s) != 0
                ):
                    df.at[i, kol_målkurs] = round(row[kol_p_s] * row[kol_omsättning], 2)
            except Exception:
                df.at[i, kol_målkurs] = None

    return df


def filtrera_och_sortera(df, sortera_efter="2025"):
    kolumn = f"Målkurs {sortera_efter}"
    df_filtered = df.copy()
    df_filtered = df_filtered[
        (df_filtered["Aktuell kurs"].notna()) & (df_filtered[kolumn].notna())
    ]
    df_filtered["Undervärdering (%)"] = (
        (df_filtered[kolumn] - df_filtered["Aktuell kurs"])
        / df_filtered["Aktuell kurs"]
        * 100
    ).round(2)
    df_filtered = df_filtered.sort_values(by="Undervärdering (%)", ascending=False)

    return df_filtered.reset_index(drop=True)

# ===== VÄRDERINGSVY =====
st.header("📊 Värderingsvy")

df = uppdatera_aktuell_kurs(df)
df = beräkna_målkurser(df)

sorteringsval = st.radio(
    "Sortera undervärdering efter målkurs för år:",
    ["2025", "2026", "2027"],
    horizontal=True,
)

df_filtered = filtrera_och_sortera(df, sortera_efter=sorteringsval)

if not df_filtered.empty:
    if "index" not in st.session_state:
        st.session_state.index = 0

    max_index = len(df_filtered) - 1

    col1, col2, col3 = st.columns(3)
    with col1:
        if st.button("⬅️ Föregående") and st.session_state.index > 0:
            st.session_state.index -= 1
    with col3:
        if st.button("Nästa ➡️") and st.session_state.index < max_index:
            st.session_state.index += 1

    bolagsrad = df_filtered.iloc[st.session_state.index]
    st.subheader(f"{bolagsrad['Bolag']} ({bolagsrad['Ticker']})")

    st.markdown(f"""
    **Aktuell kurs**: {bolagsrad['Aktuell kurs']} USD  
    **P/S TTM**: {bolagsrad['P/S TTM']}  
    **Omsättning 2025**: {bolagsrad.get('Omsättning 2025', '–')}  
    **Målkurs 2025**: {bolagsrad.get('Målkurs 2025', '–')}  
    **Målkurs 2026**: {bolagsrad.get('Målkurs 2026', '–')}  
    **Målkurs 2027**: {bolagsrad.get('Målkurs 2027', '–')}  
    **Undervärdering enligt {sorteringsval}**: {bolagsrad['Undervärdering (%)']} %
    """)

else:
    st.info("Ingen data att visa. Lägg till bolag eller fyll i omsättningar.")

# ===== PORTFÖLJ & KÖPREKOMMENDATION =====
st.header("💼 Portfölj & Köprekommendation")

with st.form("portfolio_form"):
    st.subheader("Ange dina innehav")
    tickers_innehav = st.multiselect("Vilka tickers äger du?", df["Ticker"].unique())
    kapital = st.number_input("Tillgängligt kapital (kr):", min_value=0, value=1000, step=100)
    submit_köp = st.form_submit_button("Beräkna köprekommendation")

    if submit_köp:
        df = beräkna_målkurser(df)
        undervärderade = df[df["Ticker"].isin(tickers_innehav)].copy()
        undervärderade["Skillnad"] = undervärderade["Målkurs 2025"] - undervärderade["Aktuell kurs"]
        undervärderade = undervärderade.sort_values(by="Skillnad", ascending=False)

        st.subheader("📈 Rekommendation:")
        if not undervärderade.empty:
            bästa = undervärderade.iloc[0]
            pris = bästa["Aktuell kurs"]
            if pris <= kapital:
                st.success(f"Köp **{bästa['Ticker']}** ({bästa['Bolag']}) för {pris} USD.")
            else:
                st.warning(f"**{bästa['Ticker']}** är mest attraktiv, men kräver {pris} USD – du behöver mer kapital.")
        else:
            st.info("Inget innehav matchar kriterierna eller saknar data.")

# ===== MAIN =====
def main():
    pass  # Allt körs redan i filens toppnivå ovan

if __name__ == "__main__":
    main()
