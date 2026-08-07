import yfinance as yf

# CCAU.L.csv  EXSA.DE.csv  GOLD.csv  IPXJ.L.csv  IQQJ.DE.csv  SXR8.DE.csv  XMME.DE.csv

# Yahoo Finance Ticker
ticker = "CCAU.L.DE"

# Zeitraum festlegen
start_date = "2026-06-10"
end_date = "2026-08-05"

# Kursdaten herunterladen
data = yf.download(
    ticker,
    start=start_date,
    end=end_date,
    interval="1d",
    auto_adjust=False
)

# Daten anzeigen
print(data.head())
print(data.tail())

# Als CSV speichern
data.to_csv("emerging.csv")

print("Kursdaten wurden erfolgreich als SXR8_DE_kursdaten.csv gespeichert.")

