import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go

# --- SAYFA AYARLARI ---
st.set_page_config(page_title="Wave Hunter AI", layout="wide", page_icon="🌊")

# --- YAN MENÜ ---
st.sidebar.header("🌊 Dalga Analizörü")
symbol = st.sidebar.text_input("Parite", value="EURUSD=X")
period = st.sidebar.selectbox("Veri Geçmişi", ["1y", "2y", "5y", "max"], index=0) # Varsayılan 1 Yıl (Senin analizine uygun)
deviation_pct = st.sidebar.slider("ZigZag Hassasiyeti (%)", 0.5, 5.0, 1.2, step=0.1) 
st.sidebar.info("Senin %2.64 analizini yakalamak için hassasiyeti **1.0 - 1.5** arasında dene.")

# --- VERİ MOTORU ---
@st.cache_data
def get_data(sym, per):
    try:
        df = yf.download(sym, period=per, interval="1d", progress=False, auto_adjust=False)
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        df.reset_index(inplace=True)
        
        # Sütun İsimlerini Standartlaştır
        for col in ['Date', 'index', 'Datetime']:
            if col in df.columns:
                df.rename(columns={col: 'Datetime'}, inplace=True)
                break
        
        # Kapanış Fiyatı
        if 'Close' not in df.columns and 'Adj Close' in df.columns:
             df.rename(columns={'Adj Close': 'Close'}, inplace=True)
             
        # Tarih formatı
        df['Datetime'] = pd.to_datetime(df['Datetime']).dt.tz_localize(None)
        return df
    except:
        return pd.DataFrame()

# --- ZIGZAG ALGORİTMASI ---
def calculate_waves(df, deviation=0.015):
    """
    Senin gözle yaptığın 'Tepe-Dip' sayımını yapan matematiksel fonksiyon.
    """
    df = df.copy()
    last_pivot_price = df['Close'].iloc[0]
    last_pivot_date = df['Datetime'].iloc[0]
    trend = 0 # 1: Up, -1: Down
    
    pivots = [{'Date': last_pivot_date, 'Price': last_pivot_price, 'Type': 'Start'}]
    
    for i in range(1, len(df)):
        curr_price = df['Close'].iloc[i]
        curr_date = df['Datetime'].iloc[i]
        change_pct = (curr_price - last_pivot_price) / last_pivot_price
        
        if trend == 0:
            if change_pct > deviation: trend = 1; last_pivot_price = curr_price
            elif change_pct < -deviation: trend = -1; last_pivot_price = curr_price
        
        elif trend == 1: # Yükselişteyiz
            if curr_price > last_pivot_price:
                last_pivot_price = curr_price # Yeni tepe
            elif change_pct < -deviation:
                # Düşüş başladı -> Önceki Tepeyi Kaydet
                # (Basitlik için tepe tarihini yaklaşık alıyoruz, senin görselindeki gibi uç noktaları birleştirir)
                pivots.append({'Date': df.iloc[i-1]['Datetime'], 'Price': last_pivot_price, 'Type': 'High'})
                trend = -1
                last_pivot_price = curr_price
                
        elif trend == -1: # Düşüşteyiz
            if curr_price < last_pivot_price:
                last_pivot_price = curr_price # Yeni dip
            elif change_pct > deviation:
                # Yükseliş başladı -> Önceki Dibi Kaydet
                pivots.append({'Date': df.iloc[i-1]['Datetime'], 'Price': last_pivot_price, 'Type': 'Low'})
                trend = 1
                last_pivot_price = curr_price
                
    # Son fiyatı ekle
    pivots.append({'Date': df['Datetime'].iloc[-1], 'Price': df['Close'].iloc[-1], 'Type': 'Current'})
    
    # Bacakları (Legs) Oluştur
    waves = []
    for i in range(1, len(pivots)):
        start = pivots[i-1]
        end = pivots[i]
        pct_change = ((end['Price'] - start['Price']) / start['Price']) * 100
        direction = "YÜKSELİŞ" if pct_change > 0 else "DÜŞÜŞ"
        
        waves.append({
            'Start_Date': start['Date'],
            'End_Date': end['Date'],
            'Change_Pct': pct_change,
            'Abs_Change': abs(pct_change),
            'Direction': direction,
            'Start_Price': start['Price'],
            'End_Price': end['Price']
        })
        
    return pd.DataFrame(waves), pd.DataFrame(pivots)

# --- ANA EKRAN ---
st.title(f"🌊 {symbol} Dalga Sayım Analizi")
df = get_data(symbol, period)

if not df.empty and 'Close' in df.columns:
    
    # Analizi Yap
    waves_df, pivots_df = calculate_waves(df, deviation=deviation_pct/100)
    
    # --- 1. SENİN ANALİZİNİ DOĞRULAMA KUTUSU ---
    st.subheader("📊 Dalga İstatistikleri")
    
    col1, col2, col3, col4 = st.columns(4)
    
    # Yükselişleri Filtrele
    bull_waves = waves_df[waves_df['Direction'] == "YÜKSELİŞ"]
    bear_waves = waves_df[waves_df['Direction'] == "DÜŞÜŞ"]
    
    # Senin Rakamların (Karşılaştırma için)
    avg_bull = bull_waves['Abs_Change'].mean() if not bull_waves.empty else 0
    count_bull = len(bull_waves)
    
    col1.metric("Toplam Yükseliş Sayısı", f"{count_bull} Adet", help="Senin 7 sayınla uyuşuyor mu?")
    col2.metric("Ortalama Yükseliş", f"%{avg_bull:.2f}", help="Senin %2.64 rakamınla uyuşuyor mu?")
    col3.metric("Maksimum Yükseliş", f"%{bull_waves['Abs_Change'].max():.2f}" if not bull_waves.empty else "0")
    col4.metric("Ortalama Düşüş", f"%{bear_waves['Abs_Change'].mean():.2f}" if not bear_waves.empty else "0")

    # --- 2. GÖRSEL KANIT (GRAFİK) ---
    fig = go.Figure()

    # Mumlar
    fig.add_trace(go.Candlestick(x=df['Datetime'], open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], name='Fiyat'))

    # ZigZag Çizgisi (Senin Çizimin)
    fig.add_trace(go.Scatter(x=pivots_df['Date'], y=pivots_df['Price'], mode='lines+markers+text', 
                             name='Dalga Yapısı', line=dict(color='blue', width=2),
                             text=[f"{p['Price']:.4f}" for p in pivots_df.to_dict('records')],
                             textposition="top center"))

    fig.update_layout(title="Otomatik Dalga Sayımı", template="plotly_dark", height=600)
    st.plotly_chart(fig, use_container_width=True)

    # --- 3. DETAYLI LİSTE (Senin Excel Tablon Gibi) ---
    st.subheader("📋 Tespit Edilen Dalgalar")
    if not waves_df.empty:
        # Tabloyu düzenle
        display_df = waves_df[['Start_Date', 'End_Date', 'Direction', 'Change_Pct']].copy()
        display_df['Change_Pct'] = display_df['Change_Pct'].map('{:+.2f}%'.format)
        display_df['Start_Date'] = display_df['Start_Date'].dt.date
        display_df['End_Date'] = display_df['End_Date'].dt.date
        
        st.dataframe(display_df, use_container_width=True)
        
    # --- YORUM VE STRATEJİ ---
    st.info(f"""
    💡 **STRATEJİ NOTU:**
    Bu paritede ({symbol}) yükselişler ortalama **%{avg_bull:.2f}** civarında tükeniyor.
    Eğer bir yükseliş dalgası **%{avg_bull:.2f}** seviyesine ulaştıysa, **Kâr Al (Take Profit)** veya **Short İşlem** düşünmek mantıklı olabilir.
    """)

else:
    st.error("Veri bekleniyor...")
