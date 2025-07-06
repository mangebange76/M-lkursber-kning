import streamlit as st
import pandas as pd
import yfinance as yf
import gspread
import json
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime

st.set_page_config(page_title="Målkursanalys", layout="centered")

# Funktioner
def format_svenskt(v):
    return f"{v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

def convert_number(value):
    try:
        return float(str(value).replace(",", "."))
    except:
        return None

# Google Sheets setup
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds_dict = json.loads(st.secrets["GOOGLE_CREDENTIALS"])
creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
client = gspread.authorize(creds)

# Öppna kalkylarket
SPREADSHEET_URL = st.secrets["SPREADSHEET_URL"]
SHEET_NAME = "Bolag"
sheet = client.open_by_url(SPREADSHEET_URL).worksheet(SHEET_NAME)

# Rubriker vi förväntar oss
EXPECTED_HEADERS = [
    "Ticker", "Namn", "Valuta", "Kurs", "Aktuell kurs", "P/S TTM", "P/E TTM",
    "Tillväxt 2025 (%)", "Tillväxt 2026 (%)", "Tillväxt 2027 (%)",
    "Omsättning TTM", "Målkurs 2025", "Målkurs 2026", "Målkurs 2027", "Senast uppdaterad"
]

# Kontrollera rubriker utan att rubba datan
def check_and_create_headers(sheet):
    headers = sheet.row_values(1)
    if headers != EXPECTED_HEADERS:
        sheet.update('A1', [EXPECTED_HEADERS])
    return sheet

sheet = check_and_create_headers(sheet)

# Ladda data från ark
def load_data():
    rows = sheet.get_all_records()
    df = pd.DataFrame(rows)
    return df

df = load_data()

# Visa fel om data saknas
if df.empty:
    st.warning("❌ Inga bolag inlagda än.")
    st.stop()

# Konvertera numeriska kolumner
num_cols = [col for col in df.columns if "kurs" in col.lower() or "ttm" in col.lower() or "tillväxt" in col.lower() or "målkurs" in col.lower()]
for col in num_cols:
    df[col] = df[col].apply(convert_number)

# Sortera efter undervärdering (målkurs 2027 jämfört med aktuell kurs)
df["Undervärdering (%)"] = ((df["Målkurs 2027"] - df["Aktuell kurs"]) / df["Aktuell kurs"]) * 100
df = df.sort_values(by="Undervärdering (%)", ascending=False).reset_index(drop=True)

# Bläddringsfunktion
if "bolags_index" not in st.session_state:
    st.session_state.bolags_index = 0

def visa_bolag(index):
    if index < 0 or index >= len(df):
        return

    row = df.iloc[index]

    st.subheader(f"📌 {row['Namn']} ({row['Ticker']})")
    st.markdown(f"**Aktuell kurs:** {format_svenskt(row['Aktuell kurs'])} {row['Valuta']}")
    st.markdown(f"**P/S TTM:** {format_svenskt(row['P/S TTM'])}")
    st.markdown(f"**P/E TTM:** {format_svenskt(row['P/E TTM'])}")
    st.markdown(f"**Tillväxt:** 2025: {row['Tillväxt 2025 (%)']}% · 2026: {row['Tillväxt 2026 (%)']}% · 2027: {row['Tillväxt 2027 (%)']}%")
    st.markdown(f"**Målkursar:** 2025: {format_svenskt(row['Målkurs 2025'])}, 2026: {format_svenskt(row['Målkurs 2026'])}, 2027: {format_svenskt(row['Målkurs 2027'])}")
    st.markdown(f"**Undervärdering 2027:** {format_svenskt(row['Undervärdering (%)'])}%")
    st.markdown(f"**Senast uppdaterad:** {row['Senast uppdaterad']}")

# Bläddringsknappar
col1, col2 = st.columns(2)
with col1:
    if st.button("⬅️ Föregående") and st.session_state.bolags_index > 0:
        st.session_state.bolags_index -= 1
with col2:
    if st.button("➡️ Nästa") and st.session_state.bolags_index < len(df) - 1:
        st.session_state.bolags_index += 1

visa_bolag(st.session_state.bolags_index)
