import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from scipy.stats import pearsonr
from datetime import timedelta

# --- SAYFA AYARLARI ---
st.set_page_config(page_title="Champion Pattern AI", layout="wide", page_icon="🧠")

# --- YAN MENÜ ---
st.sidebar.title("🧠 Pattern Hunter AI")
symbol = st.sidebar.text_input("Parite (Yahoo Kodu)", value="EURUSD=X")
interval = st.sidebar.selectbox("Zaman Dilimi", ["1d", "1h"], index=0)
lookback_years = st.sidebar.slider("Kaç Yıllık Geçmiş Taransın?", 1, 15, 10)

st.sidebar.markdown("---")
st.sidebar.header("Referans Dönemi Seç")
# Varsayılan: Son 1 ay
default_start = pd.Timestamp.now() - timedelta(days=30)
default_end = pd.Timestamp.now()
ref_start = st.sidebar.date_input("Başlangıç", default_start)
ref_end = st.sidebar.date_input("Bitiş", default_end)

# --- FONKSİYONLAR ---
@st.cache_data
def get_data(sym, inter, years):
    # Veri derinliği hesapla
    period = f"{years}y" if years < 10 else "max"
    try:
        df = yf.download(sym, interval=inter, period=period, progress=False)
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.droplevel(0)
        df.reset_index(inplace=True)
        return df
    except:
        return pd.DataFrame()

def find_similar_patterns(df, start_date, end_date, top_n=3):
    # 1. Referans Datayı Kesip Alalım
    mask = (df['Datetime'] >= pd.to_datetime(start_date)) & (df['Datetime'] <= pd.to_datetime(end_date))
    ref_df = df.loc[mask].copy()
    
    if len(ref_df) < 5:
        return None, "Seçilen tarih aralığı çok kısa (En az 5 mum gerekli)."
    
    # 2. Normalizasyon
    ref_norm = (ref_df['Close'] - ref_df['Close'].iloc[0]) / ref_df['Close'].iloc[0]
    ref_len = len(ref_norm)
    results = []
    
    # 3. Geçmişi Tara
    search_space = df[df['Datetime'] < pd.to_datetime(start_date)].copy()
    progress_bar = st.progress(0)
    total_steps = len(search_space) - ref_len
    closes = search_space['Close'].values
    ref_values = ref_norm.values
    step = 5 
    
    for i in range(0, len(closes) - ref_len, step):
        candidate_closes = closes[i : i + ref_len]
        cand_norm = (candidate_closes - candidate_closes[0]) / candidate_closes[0]
        
        # Pearson Korelasyonu
        if len(ref_values) == len(cand_norm):
            corr, _ = pearsonr(ref_values, cand_norm)
            if not np.isnan(corr):
                results.append({
                    'Date': search_space.iloc[i]['Datetime'],
                    'Score': corr * 100,
                    'Norm_Data': cand_norm,
                    'Next_Move': (closes[i+ref_len+10] - closes[i+ref_len]) / closes[i+ref_len] * 100 if i+ref_len+10 < len(closes) else 0
                })
        if i % 1000 == 0:
            progress_bar.progress(min(i / total_steps, 1.0))
            
    progress_bar.empty()
    
    if not results: return None, "Eşleşme bulunamadı."
    
    results_df = pd.DataFrame(results)
    results_df = results_df.sort_values(by='Score', ascending=False).head(top_n)
    return ref_df, results_df

# --- ANA EKRAN ---
st.title("🧠 Champion AI: Tarih Tekerrür Analizi")
df = get_data(symbol, interval, lookback_years)

if not df.empty:
    st.info(f"Analiz edilen veri derinliği: {len(df)} mum ({lookback_years} Yıl)")
    if st.button("🔍 BENZERLİKLERİ TARA"):
        with st.spinner("Yapay zeka geçmiş verileri tarıyor..."):
            ref_data, matches = find_similar_patterns(df, ref_start, ref_end)
            
            if matches is not None and not isinstance(matches, str):
                # GRAFİK
                fig = go.Figure()
                ref_norm_plot = (ref_data['Close'] - ref_data['Close'].iloc[0]) / ref_data['Close'].iloc[0] * 100
                x_axis = np.arange(len(ref_norm_plot))
                fig.add_trace(go.Scatter(x=x_axis, y=ref_norm_plot, mode='lines+markers', name="GÜNCEL (Referans)", line=dict(color='blue', width=4)))
                
                colors = ['green', 'orange', 'red']
                i = 0
                for index, row in matches.iterrows():
                    fig.add_trace(go.Scatter(x=x_axis, y=row['Norm_Data']*100, mode='lines', 
                        name=f"#{i+1}: {row['Date'].strftime('%Y-%m-%d')} (Benzerlik: %{row['Score']:.1f})",
                        line=dict(color=colors[i], width=2, dash='dot')))
                    i += 1
                
                fig.update_layout(title="Formasyon Kıyaslaması", xaxis_title="Süre (Mum)", template="plotly_dark", height=500)
                st.plotly_chart(fig, use_container_width=True)
                
                # DETAYLAR
                st.subheader("📊 Bulunan Benzerliklerin Detayı")
                cols = st.columns(3)
                for idx, (index, row) in enumerate(matches.iterrows()):
                    with cols[idx]:
                        move_color = "green" if row['Next_Move'] > 0 else "red"
                        arrow = "⬆️" if row['Next_Move'] > 0 else "⬇️"
                        st.markdown(f"### #{idx+1} Eşleşme")
                        st.markdown(f"**Tarih:** {row['Date'].strftime('%d %B %Y')}")
                        st.markdown(f"**Benzerlik:** %{row['Score']:.2f}")
                        st.markdown(f"<div style='background-color:#262730; padding:10px; border-radius:5px;'>Sonraki 10 mum:<br><b style='color:{move_color}; font-size:18px'>{arrow} %{row['Next_Move']:.2f}</b></div>", unsafe_allow_html=True)
            elif isinstance(matches, str):
                st.error(matches)
else:
    st.error("Veri çekilemedi.")
