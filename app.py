import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from datetime import timedelta

# --- SAYFA AYARLARI ---
st.set_page_config(page_title="Pro Wave Hunter", layout="wide", page_icon="⚡")

# --- FOREX LİSTESİ ---
FOREX_PAIRS = [
    "EURUSD=X", "GBPUSD=X", "USDJPY=X", "USDCHF=X", "AUDUSD=X", "USDCAD=X", "NZDUSD=X",
    "EURGBP=X", "EURJPY=X", "EURCHF=X", "EURAUD=X", "EURNZD=X", "EURCAD=X",
    "GBPJPY=X", "GBPCHF=X", "GBPAUD=X", "GBPNZD=X", "GBPCAD=X",
    "AUDJPY=X", "CADJPY=X", "CHFJPY=X", "NZDJPY=X",
    "AUDCAD=X", "AUDCHF=X", "CADCHF=X", "NZDCAD=X", "NZDCHF=X",
    "XAUUSD=X" # Altın sevenler için ekledim
]

# --- YAN MENÜ ---
st.sidebar.header("⚡ Ayarlar")

selected_symbol = st.sidebar.selectbox("Parite Seçiniz", FOREX_PAIRS, index=0)

# Hassasiyet Ayarı (Manuel)
deviation_pct = st.sidebar.slider("ZigZag Hassasiyeti (%)", 0.1, 5.0, 1.2, step=0.1)
st.sidebar.caption(f"Değeri yukarıdaki önerilere göre değiştirebilirsin.")

if st.sidebar.button("🔄 VERİLERİ GÜNCELLE"):
    st.cache_data.clear()

# --- VERİ MOTORU ---
@st.cache_data
def get_data(sym, period="5y"): 
    try:
        df = yf.download(sym, period=period, interval="1d", progress=False, auto_adjust=False)
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        df.reset_index(inplace=True)
        
        for col in ['Date', 'index', 'Datetime']:
            if col in df.columns:
                df.rename(columns={col: 'Datetime'}, inplace=True)
                break
        
        if 'Close' not in df.columns and 'Adj Close' in df.columns:
             df.rename(columns={'Adj Close': 'Close'}, inplace=True)
             
        df['Datetime'] = pd.to_datetime(df['Datetime']).dt.tz_localize(None)
        return df
    except:
        return pd.DataFrame()

# --- OPTİMİZASYON HESAPLAYICI (YENİ) ---
def calculate_optimal_sensitivity(df, days):
    """
    Belirtilen gün sayısı (geçmiş) için ideal hassasiyeti önerir.
    Mantık: O dönemin günlük ortalama volatilitesinin 3 katı (Gürültü Filtresi).
    """
    if df.empty: return 0.0
    
    start_date = df['Datetime'].iloc[-1] - timedelta(days=days)
    period_df = df[df['Datetime'] >= start_date].copy()
    
    if period_df.empty: return 0.0
    
    # Günlük Yüzdesel Değişim (Mutlak)
    period_df['Daily_Change'] = period_df['Close'].pct_change().abs() * 100
    avg_volatility = period_df['Daily_Change'].mean()
    
    # Sinyal/Gürültü oranı için genelde 3x katsayısı kullanılır
    suggested = avg_volatility * 3.0
    return round(suggested, 2)

# --- ZIGZAG HESAPLAMA ---
def calculate_waves(df, deviation=0.015):
    df = df.copy()
    last_pivot_price = df['Close'].iloc[0]
    last_pivot_date = df['Datetime'].iloc[0]
    trend = 0 
    pivots = [{'Date': last_pivot_date, 'Price': last_pivot_price, 'Type': 'Start'}]
    
    for i in range(1, len(df)):
        curr_price = df['Close'].iloc[i]
        change_pct = (curr_price - last_pivot_price) / last_pivot_price
        
        if trend == 0:
            if change_pct > deviation: trend = 1; last_pivot_price = curr_price
            elif change_pct < -deviation: trend = -1; last_pivot_price = curr_price
        
        elif trend == 1: # Yükseliş
            if curr_price > last_pivot_price:
                last_pivot_price = curr_price
            elif change_pct < -deviation:
                pivots.append({'Date': df.iloc[i-1]['Datetime'], 'Price': last_pivot_price, 'Type': 'High'})
                trend = -1
                last_pivot_price = curr_price
                
        elif trend == -1: # Düşüş
            if curr_price < last_pivot_price:
                last_pivot_price = curr_price
            elif change_pct > deviation:
                pivots.append({'Date': df.iloc[i-1]['Datetime'], 'Price': last_pivot_price, 'Type': 'Low'})
                trend = 1
                last_pivot_price = curr_price
                
    pivots.append({'Date': df['Datetime'].iloc[-1], 'Price': df['Close'].iloc[-1], 'Type': 'Current'})
    
    waves = []
    for i in range(1, len(pivots)):
        start, end = pivots[i-1], pivots[i]
        pct = ((end['Price'] - start['Price']) / start['Price']) * 100
        waves.append({
            'Start_Date': start['Date'],
            'Change_Pct': pct,
            'Abs_Change': abs(pct),
            'Direction': "YÜKSELİŞ" if pct > 0 else "DÜŞÜŞ"
        })
    
    return pd.DataFrame(waves), pd.DataFrame(pivots)

# --- ANA EKRAN ---
st.title(f"⚡ {selected_symbol} Analiz Terminali")

# Veri Çek
df = get_data(selected_symbol, "5y")

if not df.empty and 'Close' in df.columns:
    
    # --- 1. ÖNERİLEN HASSASİYET KUTULARI (YENİ) ---
    opt_3m = calculate_optimal_sensitivity(df, 90)
    opt_1y = calculate_optimal_sensitivity(df, 365)
    opt_2y = calculate_optimal_sensitivity(df, 730)
    
    st.subheader("🎯 Önerilen Hassasiyet Ayarları")
    c_opt1, c_opt2, c_opt3, c_opt4 = st.columns(4)
    
    c_opt1.info(f"**Son 3 Ayın** Karakteri:\n# %{opt_3m}")
    c_opt2.info(f"**Son 1 Yılın** Karakteri:\n# %{opt_1y}")
    c_opt3.info(f"**Son 2 Yılın** Karakteri:\n# %{opt_2y}")
    c_opt4.markdown("👈 *Sol menüdeki slider'ı bu değerlerden birine ayarlayabilirsin.*")

    # ZigZag Hesapla (Kullanıcının Seçtiği Değerle)
    waves_df, pivots_df = calculate_waves(df, deviation=deviation_pct/100)
    
    # --- VOLATİLİTE ENDEKSİ ---
    eur_df = get_data("EURUSD=X", "1y")
    if not eur_df.empty:
        w_eur, _ = calculate_waves(eur_df, deviation=deviation_pct/100)
        avg_eur_move = w_eur['Abs_Change'].mean() if not w_eur.empty else 1.0
        
        last_1y_start = df['Datetime'].iloc[-1] - timedelta(days=365)
        w_curr_1y = waves_df[waves_df['Start_Date'] >= last_1y_start]
        avg_curr_move = w_curr_1y['Abs_Change'].mean() if not w_curr_1y.empty else 1.0
        
        volatility_score = avg_curr_move / avg_eur_move if avg_eur_move > 0 else 1.0
        
        st.markdown(f"**Volatilite Skoru:** `{volatility_score:.2f}x` (Baz: EURUSD)")

    # --- TARİHSEL TABLO ---
    st.markdown("---")
    
    periods = {'Son 1 Yıl': 365, 'Son 2 Yıl': 730, 'Son 5 Yıl': 1825}
    comparison_data = []
    current_date = df['Datetime'].iloc[-1]
    
    for label, days in periods.items():
        start_date = current_date - timedelta(days=days)
        period_waves = waves_df[waves_df['Start_Date'] >= start_date]
        
        bulls = period_waves[period_waves['Direction'] == "YÜKSELİŞ"]['Abs_Change'].mean()
        bears = period_waves[period_waves['Direction'] == "DÜŞÜŞ"]['Abs_Change'].mean()
        
        comparison_data.append({
            'Dönem': label,
            'Ort. Yükseliş': f"%{bulls:.2f}" if not pd.isna(bulls) else "-",
            'Ort. Düşüş': f"%{bears:.2f}" if not pd.isna(bears) else "-",
            'Dalga Sayısı': len(period_waves)
        })
        
    col_table, col_metrics = st.columns([2, 1])
    with col_table:
        st.subheader("🕰️ Dönemsel Ortalamalar")
        st.table(pd.DataFrame(comparison_data).set_index('Dönem'))
    
    with col_metrics:
        # Son 1 Yıl Detayı
        stats_waves = waves_df[waves_df['Start_Date'] >= (current_date - timedelta(days=365))]
        bull_stats = stats_waves[stats_waves['Direction'] == "YÜKSELİŞ"]
        bear_stats = stats_waves[stats_waves['Direction'] == "DÜŞÜŞ"]
        
        st.subheader("📊 Son 1 Yıl Detayı")
        st.metric("Yükseliş Adedi", f"{len(bull_stats)}")
        st.metric("Düşüş Adedi", f"{len(bear_stats)}")

    # --- CANLI DURUM & GRAFİK ---
    
    # Uyarı Sistemi
    current_price = df['Close'].iloc[-1]
    last_pivot = pivots_df.iloc[-2]
    current_move_pct = abs((current_price - last_pivot['Price']) / last_pivot['Price']) * 100
    current_dir = "YÜKSELİŞ" if current_price > last_pivot['Price'] else "DÜŞÜŞ"
    long_term_waves = waves_df[waves_df['Direction'] == current_dir]
    long_term_avg = long_term_waves['Abs_Change'].mean() if not long_term_waves.empty else 0.1
    
    st.markdown("---")
    st.subheader(f"📡 Canlı Durum: {current_dir} Dalgası")
    
    alert_col1, alert_col2 = st.columns([1, 3])
    alert_col1.metric("Anlık Hareket", f"%{current_move_pct:.2f}")
    
    if current_move_pct >= long_term_avg * 0.8:
        alert_col2.warning(f"⚠️ **DÖNÜŞ BÖLGESİ:** Hareket (%{current_move_pct:.2f}), uzun vadeli ortalamaya (%{long_term_avg:.2f}) yaklaştı.")
    else:
        alert_col2.success(f"✅ **ALANI VAR:** Hareket (%{current_move_pct:.2f}), ortalamanın (%{long_term_avg:.2f}) altında ilerliyor.")

    # GRAFİK
    fig = go.Figure()
    fig.add_trace(go.Candlestick(x=df['Datetime'], open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], name='Fiyat'))

    # SARI ZIGZAG (Daha Şeffaf ve İnce)
    fig.add_trace(go.Scatter(x=pivots_df['Date'], y=pivots_df['Price'], 
                             mode='lines+markers', # Text'i kaldırdım kalabalık olmasın diye
                             name='Trend Yapısı', 
                             # RGBA(Red, Green, Blue, Alpha) -> 0.6 Alpha ile %60 Görünürlük (Şeffaf)
                             line=dict(color='rgba(255, 215, 0, 0.65)', width=2), 
                             marker=dict(size=5, color='rgba(255, 215, 0, 0.8)')))

    fig.update_layout(title=f"{selected_symbol} Yapısal Analiz", 
                      template="plotly_dark", height=700,
                      xaxis_rangeslider_visible=False)
    st.plotly_chart(fig, use_container_width=True)
    
    st.info(f"ℹ️ Pivot Teyit Eşiği: **%{deviation_pct}** (Seçili Ayar)")

else:
    st.error("Veri bekleniyor... (Piyasa kapalı olabilir veya sembol hatalı)")
