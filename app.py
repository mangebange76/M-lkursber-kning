import streamlit as st
import pandas as pd
import yfinance as yf
import gspread
from datetime import datetime
from oauth2client.service_account import ServiceAccountCredentials

# --- Google Sheets-anslutning ---
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds = ServiceAccountCredentials.from_json_keyfile_dict(st.secrets["GOOGLE_CREDENTIALS"], scope)
client = gspread.authorize(creds)

SHEET_NAME = "Aktiedata"
SHEET = client.open(SHEET_NAME)
MAIN_SHEET = SHEET.worksheet("Bolag") if "Bolag" in [ws.title for ws in SHEET.worksheets()] else SHEET.add_worksheet(title="Bolag", rows="1000", cols="30")

# --- Initiera kolumner om arket är tomt ---
HEADERS = ["Ticker", "Namn", "Kategori", "Valuta", "Antal aktier", "Senast uppdaterad",
           "Tillväxt Y1", "Tillväxt Y2", "Tillväxt Y3",
           "Målkurs Y1", "Målkurs Y2", "Målkurs Y3",
           "Tidigare målkurs Y1", "Tidigare målkurs Y2", "Tidigare målkurs Y3",
           "Aktuell kurs", "P/S TTM", "P/E TTM"]
if not MAIN_SHEET.get_all_values():
    MAIN_SHEET.append_row(HEADERS)

# --- Hjälpfunktioner ---
def get_current_year():
    return datetime.today().year

def load_data():
    records = MAIN_SHEET.get_all_records()
    df = pd.DataFrame(records)
    return df

def save_data(row):
    df = load_data()
    if row["Ticker"] in df["Ticker"].values:
        index = df[df["Ticker"] == row["Ticker"]].index[0]
        MAIN_SHEET.delete_rows(index + 2)
    MAIN_SHEET.append_row(list(row.values()))

def get_growth_estimates(ticker_obj):
    try:
        cal = ticker_obj.calendar
        return_dates = cal.columns.tolist()
        y1 = float(ticker_obj.analysis.loc["Revenue Estimate"].iloc[0]["Growth"].strip('%')) / 100
        y2 = float(ticker_obj.analysis.loc["Revenue Estimate"].iloc[1]["Growth"].strip('%')) / 100
        y3 = (y1 + y2) / 2
        return round(y1, 3), round(y2, 3), round(y3, 3)
    except:
        return 0.15, 0.15, 0.15

def calculate_ttm(ticker_obj):
    hist = ticker_obj.history(period="1y")
    info = ticker_obj.info
    currency = info.get("currency", "USD")
    shares = info.get("sharesOutstanding", None)
    if shares is None or shares == 0:
        return None

    try:
        revenue_ttm = info["totalRevenue"]
        eps_ttm = info["trailingEps"]
        price_now = hist["Close"][-1]
        ps = round((price_now * shares) / revenue_ttm, 2) if revenue_ttm else None
        pe = round(price_now / eps_ttm, 2) if eps_ttm else None
        return round(price_now, 2), ps, pe, shares, currency
    except:
        return None

def calculate_price_targets(revenue_now, growths, ps_avg, shares):
    prices = []
    rev = revenue_now
    for g in growths:
        rev *= (1 + g)
        price = (rev / shares) * ps_avg
        prices.append(round(price, 2))
    return prices

# --- UI ---
st.set_page_config(page_title="Aktieanalys", layout="centered")
st.title("📈 Aktieanalys – Målkurs via P/S & tillväxt")

tab1, tab2 = st.tabs(["➕ Lägg till/uppdatera bolag", "📊 Analys"])

with tab1:
    with st.form("add_form"):
        ticker = st.text_input("Ticker (ex: NVDA)").upper().strip()
        namn = st.text_input("Bolagsnamn")
        kategori = st.text_input("Kategori/tagg (ex: AI, shipping...)")
        antal_aktier = st.number_input("Antal aktier (utestående)", min_value=1_000_000, step=100000)
        submitted = st.form_submit_button("Spara bolag")

        if submitted and ticker:
            try:
                t = yf.Ticker(ticker)
                kurs, ps, pe, aktier, valuta = calculate_ttm(t)
                y1, y2, y3 = get_growth_estimates(t)
                prices = calculate_price_targets(t.info["totalRevenue"], [y1, y2, y3], ps, aktier)

                df = load_data()
                tidigare = df[df["Ticker"] == ticker][["Målkurs Y1", "Målkurs Y2", "Målkurs Y3"]].values.tolist()
                tidigare = tidigare[0] if tidigare else ["", "", ""]

                row = {
                    "Ticker": ticker,
                    "Namn": namn,
                    "Kategori": kategori,
                    "Valuta": valuta,
                    "Antal aktier": aktier,
                    "Senast uppdaterad": datetime.today().strftime("%Y-%m-%d"),
                    "Tillväxt Y1": y1,
                    "Tillväxt Y2": y2,
                    "Tillväxt Y3": y3,
                    "Målkurs Y1": prices[0],
                    "Målkurs Y2": prices[1],
                    "Målkurs Y3": prices[2],
                    "Tidigare målkurs Y1": tidigare[0],
                    "Tidigare målkurs Y2": tidigare[1],
                    "Tidigare målkurs Y3": tidigare[2],
                    "Aktuell kurs": kurs,
                    "P/S TTM": ps,
                    "P/E TTM": pe
                }
                save_data(row)
                st.success(f"{ticker} sparades/uppdaterades.")
            except Exception as e:
                st.error(f"Fel: {e}")

with tab2:
    df = load_data()
    if df.empty:
        st.info("Inga bolag inlagda ännu.")
    else:
        sort_key = st.selectbox("Sortera på undervärdering enligt:", ["Målkurs Y1", "Målkurs Y2", "Målkurs Y3"])
        df["Undervärdering"] = (df[sort_key] - df["Aktuell kurs"]) / df["Aktuell kurs"]
        df = df.sort_values("Undervärdering", ascending=False).reset_index(drop=True)

        index = st.number_input("Visa bolag #", min_value=1, max_value=len(df), value=1) - 1
        row = df.iloc[index]

        st.subheader(f"{row['Namn']} ({row['Ticker']})")
        st.markdown(f"**Kategori:** {row['Kategori']}")
        st.markdown(f"**Aktuell kurs:** {row['Aktuell kurs']} {row['Valuta']}")
        st.markdown(f"**P/S TTM:** {row['P/S TTM']} &nbsp;&nbsp; **P/E TTM:** {row['P/E TTM']}")
        st.markdown("---")

        st.markdown("### 📈 Tillväxt och målkurs")
        for i, år in enumerate(["Y1", "Y2", "Y3"]):
            st.markdown(f"""
            **Tillväxt {år}:** {row[f'Tillväxt {år}']*100:.1f}%  
            **Målkurs {år}:** {row[f'Målkurs {år}']}  
            _Tidigare målkurs:_ {row[f'Tidigare målkurs {år}']}  
            """)

        st.markdown("---")
        st.markdown(f"**Senast uppdaterad:** {row['Senast uppdaterad']}")
