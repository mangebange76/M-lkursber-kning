# 📊 Aktieanalys-app – P/S & P/E målkurs

Denna Streamlit-app låter dig analysera aktier baserat på TTM P/S och framtida omsättningstillväxt. Appen beräknar framtida målkurs för tre år (Y1–Y3) och sorterar bolag efter undervärdering.

## 🚀 Funktioner

- Lägg till eller uppdatera bolag (ticker, namn, kategori)
- Automatisk hämtning av:
  - Kurs, omsättning, EPS
  - TTM P/S och P/E
  - Tillväxt för Y1 & Y2 (från Yahoo Finance)
- Extrapolering av tillväxt för Y3
- Målkursberäkningar för tre år
- Undervärderingssortering och bolagsbläddring
- Data sparas i Google Sheets

## 🛠️ Installation

```bash
pip install -r requirements.txt
