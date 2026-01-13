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
default_start = pd.Timestamp.now() - timedelta(days=30)
default_end = pd.Timestamp.now()
ref_start = st.sidebar.date_input("Başlangıç", default_start)
ref_end = st.sidebar.date_input("Bitiş", default_end)

# --- FONKSİYONLAR ---
@st.cache_data
def get_data(sym, inter, years):
    period = f"{years}y" if years < 10 else "max"
    try:
        # Veriyi indir (auto_adjust=False ile ham veriyi alıyoruz)
        df = yf.download(sym, interval=inter, period=period, progress=False, auto_adjust=False)
        
        # 1. MultiIndex Temizliği (Çift başlık varsa düzelt)
        if isinstance(df.columns, pd.MultiIndex):
            # Sadece ilk seviyeyi (Open, High, Low...) al
            df.columns = df.columns.get_level_values(0)
        
        # 2. İndeksi Sütuna Çevir
        df.reset_index(inplace=True)
        
        # 3. Tarih Sütununu Standartlaştır
        # Olası tarih sütun isimlerini kontrol et ve 'Datetime' yap
        date_cols = ['Date', 'date', 'index', 'Datetime']
        for col in date_cols:
            if col in df.columns:
                df.rename(columns={col: 'Datetime'}, inplace=True)
                break
        
        # 4. Kapanış Sütununu Standartlaştır ('Close' yoksa 'Adj Close' kullan)
        if 'Close' not in df.columns:
            if 'Adj Close' in df.columns:
                df.rename(columns={'Adj Close': 'Close'}, inplace=True)
            else:
                # Hiçbiri yoksa hata vermemesi için boş dataframe dön
                return pd.DataFrame()

        # 5. Tarih Formatını Garantiye Al (Timezone sorununu çöz)
        df['Datetime'] = pd.to_datetime(df['Datetime']).dt.tz_localize(None)
        
        return df
    except Exception as e:
        return pd.DataFrame()

def find_similar_patterns(df, start_date, end_date, top_n=3):
    # Veri Kontrolü
    if df.empty: return None, "Veri boş."
    if 'Close' not in df.columns: return None, "'Close' sütunu bulunamadı."

    # Tarihleri Panda formatına çevir
    s_date = pd.to_datetime(start_date)
    e_date = pd.to_datetime(end_date)

    # 1. Referans Datayı Kes
    mask = (df['Datetime'] >= s_date) & (df['Datetime'] <= e_date)
    ref_df = df.loc[mask].copy()
    
    if len(ref_df) < 5:
        return None, "Seçilen tarih aralığı çok kısa (En az 5 mum)."
    
    # 2. Normalizasyon
    first_close = ref_df['Close'].iloc[0]
    if pd.isna(first_close) or first_close == 0: return None, "Referans verisinde 0 veya hatalı değer var."
    
    ref_norm = (ref_df['Close'] - first_close) / first_close
    ref_len = len(ref_norm)
    
    # 3. Geçmişi Tara
    search_space = df[df['Datetime'] < s_date].copy()
    if len(search_space) < ref_len: return None, "Yeterli geçmiş veri yok."
    
    results = []
    closes = search_space['Close'].values
    ref_values = ref_norm.values
    
    # İlerleme Çubuğu
    progress_bar = st.progress(0)
    total_steps = len(closes) - ref_len
    step = 5 # Hız için atlama
    
    for i in range(0, len(closes) - ref_len, step):
        candidate_closes = closes[i : i + ref_len]
        
        # Adayın ilk değeri 0 ise atla (bölme hatası olmasın)
        if candidate_closes[0] == 0: continue
            
        cand_norm = (candidate_closes - candidate_closes[0]) / candidate_closes[0]
        
        # Boyutlar eşitse Korelasyon yap
        if len(ref_values) == len(cand_norm):
            try:
                corr, _ = pearsonr(ref_values, cand_norm)
                if not np.isnan(corr):
                    results.append({
                        'Date': search_space.iloc[i]['Datetime'],
                        'Score': corr * 100,
                        'Norm_Data': cand_norm,
                        'Next_Move': (closes[i+ref_len+10] - closes[i+ref_len]) / closes[i+ref_len] * 100 if i+ref_len+10 < len(closes) else 0
                    })
            except:
                pass # Matematiksel hata olursa atla
        
        if total_steps > 0 and i % 1000 == 0:
            progress_bar.progress(min(i / total_steps, 1.0))
            
    progress_bar.empty()
    
    if not results: return None, "Benzer formasyon bulunamadı."
    
    results_df = pd.DataFrame(results)
    results_df = results_df.sort_values(by='Score', ascending=False).head(top_n)
    
    return ref_df, results_df

# --- ANA EKRAN ---
st.title("🧠 Champion AI: Tarih Tekerrür Analizi")

# Veriyi Çek
df = get_data(symbol, interval, lookback_years)

# Hata Ayıklama (Debug) Kutusu - Gizli
with st.expander("🛠️ Veri Kontrol Paneli (Hata Alırsan Buraya Bak)"):
    if not df.empty:
        st.write("Veri başarıyla çekildi. İlk 5 satır:")
        st.write(df.head())
        st.write("Sütun İsimleri:", df.columns.tolist())
    else:
        st.error("Veri çekilemedi! Parite ismini veya Yahoo bağlantısını kontrol et.")

if not df.empty and 'Close' in df.columns:
    st.info(f"Analiz edilen veri: {len(df)} mum ({lookback_years} Yıl)")
    
    if st.button("🔍 BENZERLİKLERİ TARA"):
        with st.spinner("Yapay zeka geçmiş verileri tarıyor..."):
            ref_data, matches = find_similar_patterns(df, ref_start, ref_end)
            
            if matches is not None and not isinstance(matches, str):
                # GRAFİK
                fig = go.Figure()
                
                # Referans
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
                
                # SONUÇLAR
                st.subheader("📊 Benzerlik Detayları")
                cols = st.columns(3)
                for idx, (index, row) in enumerate(matches.iterrows()):
                    with cols[idx]:
                        move = row['Next_Move']
                        color = "green" if move > 0 else "red"
                        arrow = "⬆️" if move > 0 else "⬇️"
                        st.markdown(f"### #{idx+1} Eşleşme")
                        st.markdown(f"**Tarih:** {row['Date'].strftime('%d %B %Y')}")
                        st.markdown(f"**Benzerlik:** %{row['Score']:.2f}")
                        st.markdown(f"<div style='background-color:#262730; padding:10px; border-radius:5px;'>Sonraki 10 mum:<br><b style='color:{color}; font-size:18px'>{arrow} %{move:.2f}</b></div>", unsafe_allow_html=True)
            
            elif isinstance(matches, str):
                st.error(f"Hata: {matches}")
else:
    st.warning("Veri bekleniyor veya 'Close' sütunu bulunamadı.")
