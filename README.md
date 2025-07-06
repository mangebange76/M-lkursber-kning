# 📈 Aktieanalys – Målkursberäkning

En Streamlit-app för att:
- Hämta finansiell data från Yahoo Finance
- Beräkna P/S och P/E TTM
- Estimera framtida målkurs för 2025–2027
- Spara och uppdatera bolag i Google Sheets

## ✅ Funktioner
- Automatisk kontroll och skapande av rubriker i kalkylark
- Automatisk analys från ticker
- Tillväxtjusterad målkurs
- Sortering och bläddring mellan bolag

## 🚀 Så kör du appen
1. Lägg in din `secrets.toml` i Streamlit Cloud med `GOOGLE_CREDENTIALS` och `SPREADSHEET_URL`
2. Dela ditt Google Sheet offentligt med redigeringsrättigheter
3. Starta appen i Streamlit

## 🔒 Säkerhet
Nycklarna hanteras via `st.secrets` – inga känsliga uppgifter ska ligga direkt i koden.
