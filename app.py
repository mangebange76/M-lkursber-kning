import streamlit as st
import pandas as pd
import yfinance as yf
import gspread
import json
from datetime import datetime
from oauth2client.service_account import ServiceAccountCredentials

# --- Google Sheets-anslutning ---
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds_dict = json.loads(st.secrets["GOOGLE_CREDENTIALS"])
creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
client = gspread.authorize(creds)

# --- Inställningar ---
SHEET_NAME = "Aktiedata"
RUBRIKER = ["Ticker", "Namn", "Kategori", "Valuta", "Antal aktier", "Senast uppdaterad",
            "Tillväxt Y1", "Tillväxt Y2", "Tillväxt Y3",
            "Målkurs Y1", "Målkurs Y2", "Målkurs Y3",
            "Tidigare målkurs Y1", "Tidigare målkurs Y2", "Tidigare målkurs Y3",
            "Aktuell kurs", "P/S TTM", "P/E TTM"]

# --- Öppna eller skapa worksheet ---
SHEET = client.open(SHEET_NAME)
if "Bolag" in [ws.title for ws in SHEET.worksheets()]:
    MAIN_SHEET = SHEET.worksheet("Bolag")
else:
    MAIN_SHEET = SHEET.add_worksheet(title="Bolag", rows="1000", cols="30")

# --- Kontrollera och skapa rubriker vid behov ---
def kontrollera_och_uppdatera_rubriker():
    befintliga = MAIN_SHEET.row_values(1)
    if befintliga != RUBRIKER:
        if befintliga:
            MAIN_SHEET.delete_rows(1)
        MAIN_SHEET.insert_row(RUBRIKER, index=1)

kontrollera_och_uppdatera_rubriker()

# --- Hjälpfunktioner ---
def load_data():
    records = MAIN_SHEET.get_all_records()
    return pd.DataFrame(records)

def save_data(row):
    df = load_data()
    if not df.empty and "Ticker" in df.columns and row["Ticker"] in df["Ticker"].values:
        index = df[df["Ticker"] == row["Ticker"]].index[0]
        MAIN_SHEET.delete_rows(index + 2)
    MAIN_SHEET.append_row(list(row.values()))

def get_growth_estimates(ticker_obj):
    try:
        df = ticker_obj.analysis
        g1 = df.iloc[0]["Growth"]
        g2 = df.iloc[1]["Growth"]
        if "%" in g1 and "%" in g2:
            y1 = float(g1.strip('%')) / 100
            y2 = float(g2.strip('%')) / 100
        else:
            raise ValueError
        y3 = (y1 + y2) / 2
        return round(y1, 3), round(y2, 3), round(y3, 3)
    except:
        return 0.15, 0.15, 0.15

def calculate_ttm(ticker_obj):
    try:
        hist = ticker_obj.history(period="5d")
        info = ticker_obj.info
        price_now = hist["Close"][-1]
        shares = info.get("sharesOutstanding", 0)
        revenue = info.get("totalRevenue", None)
        eps = info.get("trailingEps", None)
        currency = info.get("currency", "USD")
        if not revenue or not eps or eps == 0 or shares == 0:
            return None
        ps = round((price_now * shares) / revenue, 2)
        pe = round(price_now / eps, 2)
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
        kategori = st.text_input("Kategori/tagg (ex: AI, shipping...)")
        antal_aktier = st.number_input("Antal aktier (utestående)", min_value=1_000_000, step=100000)
        submitted = st.form_submit_button("Spara bolag")

        if submitted and ticker:
            try:
                t = yf.Ticker(ticker)
                namn = t.info.get("shortName", "Okänt bolag")
                resultat = calculate_ttm(t)
                if not resultat:
                    st.error("Kunde inte hämta nyckeltal (P/S, P/E eller kurs).")
                else:
                    kurs, ps, pe, aktier, valuta = resultat
                    y1, y2, y3 = get_growth_estimates(t)
                    prices = calculate_price_targets(t.info["totalRevenue"], [y1, y2, y3], ps, aktier)

                    df = load_data()
                    if not df.empty and "Ticker" in df.columns and ticker in df["Ticker"].values:
                        tidigare = df[df["Ticker"] == ticker][["Målkurs Y1", "Målkurs Y2", "Målkurs Y3"]].values.tolist()[0]
                    else:
                        tidigare = ["", "", ""]

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
                    st.success(f"{ticker} ({namn}) sparades/uppdaterades.")
            except Exception as e:
                st.error(f"Fel: {e}")

with tab2:
    df = load_data()
    if df.empty:
        st.info("Inga bolag inlagda ännu.")
    else:
        sort_key = st.selectbox("Sortera på undervärdering enligt:", ["Målkurs Y1", "Målkurs Y2", "Målkurs Y3"])
        df["Undervärdering"] = (df[sort_key].astype(float) - df["Aktuell kurs"].astype(float)) / df["Aktuell kurs"].astype(float)
        df = df.sort_values("Undervärdering", ascending=False).reset_index(drop=True)

        index = st.number_input("Visa bolag #", min_value=1, max_value=len(df), value=1) - 1
        row = df.iloc[index]

        st.subheader(f"{row['Namn']} ({row['Ticker']})")
        st.markdown(f"**Kategori:** {row['Kategori']}")
        st.markdown(f"**Aktuell kurs:** {float(row['Aktuell kurs']):,.2f} {row['Valuta']}")
        st.markdown(f"**P/S TTM:** {float(row['P/S TTM']):,.2f} &nbsp;&nbsp; **P/E TTM:** {float(row['P/E TTM']):,.2f}")
        st.markdown("---")

        st.markdown("### 📈 Tillväxt och målkurs")
        for i, år in enumerate(["Y1", "Y2", "Y3"]):
            st.markdown(f"""
            **Tillväxt {år}:** {float(row[f'Tillväxt {år}'])*100:.1f}%  
            **Målkurs {år}:** {float(row[f'Målkurs {år}']):,.2f}  
            _Tidigare målkurs:_ {row[f'Tidigare målkurs {år}']}  
            """)

        st.markdown("---")
        st.markdown(f"**Senast uppdaterad:** {row['Senast uppdaterad']}")
