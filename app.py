import streamlit as st
import pandas as pd
import gspread
import json
from oauth2client.service_account import ServiceAccountCredentials
import yfinance as yf
from datetime import datetime

st.set_page_config(page_title="Målkursanalys", layout="centered")

# Funktion för att formatera svenska tal
def format_svenskt(v):
    return f"{v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

# Google Sheets setup
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds_dict = json.loads(st.secrets["GOOGLE_CREDENTIALS"])
creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
client = gspread.authorize(creds)

SHEET_NAME = "Bolag"
WORKSHEET = client.open_by_url(st.secrets["SPREADSHEET_URL"]).worksheet(SHEET_NAME)

# Förväntade rubriker
HEADERS = [
    "Ticker", "Namn", "Kategori", "Valuta", "Aktuell kurs", "P/S TTM", "P/E TTM",
    "Tillväxt Y1", "Tillväxt Y2", "Tillväxt Y3",
    "Målkurs Y1", "Målkurs Y2", "Målkurs Y3",
    "Senast uppdaterad"
]

# Kontrollera och skapa rubriker om de saknas
def säkerställ_rubriker():
    if WORKSHEET.row_count < 1 or WORKSHEET.row_values(1) != HEADERS:
        WORKSHEET.clear()
        WORKSHEET.append_row(HEADERS)

# Läs data från arket
def load_data():
    säkerställ_rubriker()
    rows = WORKSHEET.get_all_records()
    return pd.DataFrame(rows)

# Spara ny rad till arket
def spara_rad(data):
    df = load_data()
    df = df[df["Ticker"] != data["Ticker"]]  # ta bort ev. gammal rad
    updated = df.to_dict("records")
    updated.append(data)
    WORKSHEET.clear()
    WORKSHEET.append_row(HEADERS)
    for rad in updated:
        WORKSHEET.append_row([rad.get(h, "") for h in HEADERS])

# Beräkna målkurs utifrån tillväxt och P/S
def beräkna_målkurs(omsättning, tillväxt, ps, antal_aktier):
    if omsättning == 0 or antal_aktier == 0:
        return 0
    framtida_omsättning = omsättning * (1 + tillväxt)
    return (framtida_omsättning / antal_aktier) * ps

# Formatsträngar till float (svenska decimaltal)
def safe_float(v):
    try:
        return float(str(v).replace(",", "."))
    except:
        return 0.0

# Input
st.title("📈 Målkursanalys")
ticker_input = st.text_input("Ange ticker (t.ex. AAPL)", "").upper()

if ticker_input:
    try:
        with st.spinner("Hämtar data..."):
            aktie = yf.Ticker(ticker_input)
            info = aktie.info
            namn = info.get("longName", "")
            valuta = info.get("currency", "")
            antal_aktier = info.get("sharesOutstanding", 0)
            kategori = info.get("sector", "Okänd")

            kurs = aktie.history(period="1d")["Close"][-1] if not aktie.history(period="1d").empty else 0
            omsättning = info.get("totalRevenue", 0)

            # Dummy-tillväxt (ersätt med riktig logik senare)
            tillväxt1 = 0.15
            tillväxt2 = 0.15
            tillväxt3 = 0.15

            ps_ttm = info.get("priceToSalesTrailing12Months", 0)
            pe_ttm = info.get("trailingPE", 0)

            mål1 = beräkna_målkurs(omsättning, tillväxt1, ps_ttm, antal_aktier)
            mål2 = beräkna_målkurs(omsättning * (1 + tillväxt1), tillväxt2, ps_ttm, antal_aktier)
            mål3 = beräkna_målkurs(omsättning * (1 + tillväxt1) * (1 + tillväxt2), tillväxt3, ps_ttm, antal_aktier)

            nu = datetime.now().strftime("%Y-%m-%d %H:%M")

            data = {
                "Ticker": ticker_input,
                "Namn": namn,
                "Kategori": kategori,
                "Valuta": valuta,
                "Aktuell kurs": round(kurs, 2),
                "P/S TTM": round(ps_ttm, 2),
                "P/E TTM": round(pe_ttm, 2),
                "Tillväxt Y1": round(tillväxt1, 4),
                "Tillväxt Y2": round(tillväxt2, 4),
                "Tillväxt Y3": round(tillväxt3, 4),
                "Målkurs Y1": round(mål1, 2),
                "Målkurs Y2": round(mål2, 2),
                "Målkurs Y3": round(mål3, 2),
                "Senast uppdaterad": nu
            }

            spara_rad(data)
            st.success("✅ Data uppdaterad!")

    except Exception as e:
        st.error(f"Något gick fel: {e}")

# Visa bolag i databasen
df = load_data()
if not df.empty:
    df["Undervärdering Y1"] = (df["Målkurs Y1"].apply(safe_float) - df["Aktuell kurs"].apply(safe_float)) / df["Aktuell kurs"].apply(safe_float)
    df = df.sort_values("Undervärdering Y1", ascending=False).reset_index(drop=True)

    index = st.number_input("Visa bolag:", min_value=0, max_value=len(df)-1, step=1)

    row = df.iloc[index]

    st.header(f"{row['Namn']} ({row['Ticker']})")
    st.markdown(f"**Kategori:** {row['Kategori']}")
    st.markdown(f"**Aktuell kurs:** {format_svenskt(safe_float(row['Aktuell kurs']))} {row['Valuta']}")
    st.markdown(f"**P/S TTM:** {format_svenskt(safe_float(row['P/S TTM']))} &nbsp;&nbsp; **P/E TTM:** {format_svenskt(safe_float(row['P/E TTM']))}")

    st.subheader("📈 Tillväxt och målkurs")
    for i in range(1, 4):
        st.markdown(f"**Tillväxt Y{i}:** {str(round(safe_float(row[f'Tillväxt Y{i}'])*100,1)).replace('.', ',')}%")
        st.markdown(f"**Målkurs Y{i}:** {format_svenskt(safe_float(row[f'Målkurs Y{i}']))}")
        tidigare = df[df["Ticker"] == row["Ticker"]][f"Målkurs Y{i}"].values.tolist()
        if tidigare:
            st.markdown(f"*Tidigare målkurs:* {format_svenskt(safe_float(tidigare[0]))}")
        else:
            st.markdown("*Tidigare målkurs:* –")

    st.caption(f"Senast uppdaterad: {row['Senast uppdaterad']}")
