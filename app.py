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
    "EURUSD=X", "GBPUSD=X", "USDJPY=X", "USDCHF=X", "AUDUSD=X", "USDCAD=X", "NZDUSD=X", # Majors
    "EURGBP=X", "EURJPY=X", "EURCHF=X", "EURAUD=X", "EURNZD=X", "EURCAD=X", # Euro Cross
    "GBPJPY=X", "GBPCHF=X", "GBPAUD=X", "GBPNZD=X", "GBPCAD=X", # GBP Cross
    "AUDJPY=X", "CADJPY=X", "CHFJPY=X", "NZDJPY=X", # Yen Cross
    "AUDCAD=X", "AUDCHF=X", "CADCHF=X", "NZDCAD=X", "NZDCHF=X" # Others
]

# --- YAN MENÜ ---
st.sidebar.header("⚡ Ayarlar")

# 4. Madde: Dropdown Menü
selected_symbol = st.sidebar.selectbox("Parite Seçiniz", FOREX_PAIRS, index=0)

# Hassasiyet Ayarı
deviation_pct = st.sidebar.slider("ZigZag Hassasiyeti (%)", 0.5, 5.0, 1.2, step=0.1)
st.sidebar.caption(f"ℹ️ Pivot oluşması için fiyatın ters yöne en az **%{deviation_pct}** gitmesi gerekir.")

# Güncelleme Butonu
if st.sidebar.button("🔄 VERİLERİ GÜNCELLE"):
    st.cache_data.clear()

# --- VERİ MOTORU ---
@st.cache_data
def get_data(sym, period="5y"): # 7. Madde için uzun veri çekiyoruz
    try:
        df = yf.download(sym, period=period, interval="1d", progress=False, auto_adjust=False)
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        df.reset_index(inplace=True)
        
        # Sütun İsimlerini Standartlaştır
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

# Veri Çek (5 Yıllık - Analiz için gerekli)
df = get_data(selected_symbol, "5y")

if not df.empty and 'Close' in df.columns:
    
    # ZigZag Hesapla
    waves_df, pivots_df = calculate_waves(df, deviation=deviation_pct/100)
    
    # --- 5. MADDE: VOLATİLİTE ENDEKSİ (EURUSD BAZLI) ---
    eur_df = get_data("EURUSD=X", "1y") # Baz veri
    if not eur_df.empty:
        w_eur, _ = calculate_waves(eur_df, deviation=deviation_pct/100)
        avg_eur_move = w_eur['Abs_Change'].mean()
        
        # Seçilen paritenin son 1 yılı
        last_1y_start = df['Datetime'].iloc[-1] - timedelta(days=365)
        w_curr_1y = waves_df[waves_df['Start_Date'] >= last_1y_start]
        avg_curr_move = w_curr_1y['Abs_Change'].mean()
        
        volatility_score = avg_curr_move / avg_eur_move if avg_eur_move > 0 else 1.0
        
        col_vol1, col_vol2 = st.columns([3, 1])
        with col_vol1:
            st.markdown(f"### 📊 Volatilite Skoru: **{volatility_score:.2f}x**")
            st.caption(f"(EURUSD = 1.00 baz alınmıştır. Bu parite EURUSD'den {volatility_score:.2f} kat daha hareketlidir.)")
            st.progress(min(volatility_score/3, 1.0)) # Bar göstergesi

    # --- 7. MADDE: TARİHSEL KIYASLAMA TABLOSU ---
    st.markdown("---")
    st.subheader("🕰️ Dönemsel Dalga Ortalamaları")
    
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
        
    st.table(pd.DataFrame(comparison_data).set_index('Dönem'))

    # --- 2. MADDE: GÜNCEL İSTATİSTİKLER ---
    # Son 1 yılı baz alarak genel istatistik verelim
    stats_waves = waves_df[waves_df['Start_Date'] >= (current_date - timedelta(days=365))]
    
    bull_stats = stats_waves[stats_waves['Direction'] == "YÜKSELİŞ"]
    bear_stats = stats_waves[stats_waves['Direction'] == "DÜŞÜŞ"]
    
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Ort. Yükseliş (1Y)", f"%{bull_stats['Abs_Change'].mean():.2f}")
    col2.metric("Yükseliş Adedi", f"{len(bull_stats)}")
    col3.metric("Ort. Düşüş (1Y)", f"%{bear_stats['Abs_Change'].mean():.2f}") # 2. Madde
    col4.metric("Düşüş Adedi", f"{len(bear_stats)}") # 2. Madde

    # --- 3. MADDE: PİVOT OLUŞTURAN DEĞİŞİM ---
    st.info(f"""
    ℹ️ **BİLGİ:** Seçtiğin %{deviation_pct} hassasiyetine göre;
    Bir tepenin "Tepe" olarak işaretlenmesi için fiyatın oradan **%{deviation_pct}** düşmesi beklendi.
    Bir dibin "Dip" olarak işaretlenmesi için fiyatın oradan **%{deviation_pct}** yükselmesi beklendi.
    """)

    # --- 7. MADDE EKİ: CANLI UYARI MEKANİZMASI ---
    # Son tamamlanmamış (current) dalgayı kontrol et
    current_price = df['Close'].iloc[-1]
    last_pivot = pivots_df.iloc[-2] # Current'dan önceki son kesinleşmiş pivot
    
    # Şu anki hareketin yüzdesi
    current_move_pct = abs((current_price - last_pivot['Price']) / last_pivot['Price']) * 100
    current_dir = "YÜKSELİŞ" if current_price > last_pivot['Price'] else "DÜŞÜŞ"
    
    # 5 Yıllık ortalama ile kıyasla
    long_term_waves = waves_df[waves_df['Direction'] == current_dir]
    long_term_avg = long_term_waves['Abs_Change'].mean()
    
    st.subheader(f"📡 Canlı Durum: {current_dir} Dalgası İçindeyiz")
    c1, c2 = st.columns([1, 3])
    c1.metric("Anlık Dalga Boyu", f"%{current_move_pct:.2f}")
    
    # Uyarı Mantığı
    if current_move_pct >= long_term_avg * 0.8:
        st.warning(f"⚠️ **DÖNÜŞ SİNYALİ:** Mevcut hareket (%{current_move_pct:.2f}), uzun vadeli ortalamaya (%{long_term_avg:.2f}) yaklaştı veya geçti. Dönüş ihtimali artıyor!")
    else:
        st.success(f"✅ **DEVAM:** Mevcut hareket (%{current_move_pct:.2f}), ortalamanın (%{long_term_avg:.2f}) henüz altında. Alanı var.")


    # --- 1. MADDE: GRAFİK (SARI ÇİZGİLER) ---
    fig = go.Figure()

    # Mumlar
    fig.add_trace(go.Candlestick(x=df['Datetime'], open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], name='Fiyat'))

    # SARI ZIGZAG
    fig.add_trace(go.Scatter(x=pivots_df['Date'], y=pivots_df['Price'], 
                             mode='lines+markers+text', 
                             name='Dalga Yapısı', 
                             line=dict(color='yellow', width=3), # 1. Madde: Sarı Renk
                             marker=dict(size=8, color='yellow'),
                             text=[f"{p['Price']:.4f}" for p in pivots_df.to_dict('records')],
                             textposition="top center"))

    fig.update_layout(title=f"{selected_symbol} ZigZag Analizi (Son 5 Yıldan Görünüm)", 
                      template="plotly_dark", height=700,
                      xaxis_rangeslider_visible=False) # Alt slider'ı gizle
    st.plotly_chart(fig, use_container_width=True)

else:
    st.error("Veri bekleniyor... (Piyasa kapalı olabilir veya sembol hatalı)")
