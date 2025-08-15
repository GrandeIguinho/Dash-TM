import json
import warnings
from datetime import datetime, timedelta

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from plotly.subplots import make_subplots

warnings.filterwarnings('ignore')

# Configuração da página
st.set_page_config(
    page_title="Dashboard TM - Agendamentos",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# CSS customizado
st.markdown("""
<style>
    .metric-card {
        background-color: #f0f2f6;
        padding: 1rem;
        border-radius: 0.5rem;
        border-left: 4px solid #1f77b4;
    }
    .stTabs [data-baseweb="tab-list"] button [data-testid="stMarkdownContainer"] p {
        font-size: 16px;
        font-weight: bold;
    }
    .main-header {
        text-align: center;
        margin-bottom: 2rem;
    }
</style>
""", unsafe_allow_html=True)

# Configurar credenciais e escopo
SCOPES = ['https://www.googleapis.com/auth/spreadsheets']
credential_json = st.secrets["credentials"]
CREDENTIALS = json.loads(credential_json)
SPREADSHEET_ID = '1bFvyTbcYxiQI3SESD-bCE89wt3zaRyJ4QjxGTYo2SH0'

# Autenticação e criação do serviço
creds = Credentials.from_service_account_info(CREDENTIALS, scopes=SCOPES)
service = build('sheets', 'v4', credentials=creds)

# Funções para ler dados no Google Sheets
@st.cache_data(ttl=300)  # Cache por 5 minutos
def ler_dados(nome_aba, intervalo):
    try:
        resultado = service.spreadsheets().values().get(
            spreadsheetId=SPREADSHEET_ID,
            range=f'{nome_aba}!{intervalo}'
        ).execute()
        valores = resultado.get('values', [])
        return valores
    except Exception as e:
        st.error(f"Erro ao ler dados: {e}")
        return []

@st.cache_data(ttl=300)
def load_data():
    """Carrega e processa os dados da planilha"""
    try:
        aba_agendamentos = ler_dados("Agendamentos", "A1:X6000")
        if not aba_agendamentos:
            return None
        
        df = pd.DataFrame(aba_agendamentos[1:], columns=aba_agendamentos[0])
        
        # Limpeza e tratamento dos dados
        df.columns = df.columns.str.strip()
        
        # Conversão de datas
        date_columns = ['DATA', 'DATA DA CALL', 'DIA DA VENDA']
        for col in date_columns:
            if col in df.columns:
                df[col] = pd.to_datetime(df[col], format='%d/%m/%Y', errors='coerce')
        
        # Limpeza de valores monetários
        if 'VALOR' in df.columns:
            df['VALOR_NUM'] = df['VALOR'].astype(str).str.replace('R$ ', '').str.replace('.', '').str.replace(',', '.').replace('', '0')
            df['VALOR_NUM'] = pd.to_numeric(df['VALOR_NUM'], errors='coerce').fillna(0)
        
        # Limpeza de strings
        string_columns = ['SDR', 'CLOSER', 'FUNIL', 'STATUS', 'VENDA REALIZADA']
        for col in string_columns:
            if col in df.columns:
                df[col] = df[col].astype(str).str.strip()
        
        # Conversão do ciclo de vendas
        if 'CICLO DE VENDAS' in df.columns:
            df['CICLO DE VENDAS'] = pd.to_numeric(df['CICLO DE VENDAS'], errors='coerce')
        
        return df
    except Exception as e:
        st.error(f"Erro ao carregar os dados: {e}")
        return None

def create_metrics_cards(df, col1, col2, col3, col4):
    """Cria cards com métricas principais"""
    total_agendamentos = len(df)
    calls_realizadas = len(df[df['STATUS'] == 'Call Realizada'])
    vendas_ganhas = len(df[df['VENDA REALIZADA'] == 'Ganho'])
    receita_total = df[df['VENDA REALIZADA'] == 'Ganho']['VALOR_NUM'].sum()
    
    with col1:
        st.metric("Total Agendamentos", f"{total_agendamentos:,}")
    with col2:
        st.metric("Calls Realizadas", f"{calls_realizadas:,}")
    with col3:
        st.metric("Vendas Fechadas", f"{vendas_ganhas:,}")
    with col4:
        st.metric("Receita Total", f"R$ {receita_total:,.2f}")

def dashboard_geral(df):
    """Dashboard geral com visão consolidada"""
    st.header("📊 Dashboard Geral")
    
    # Métricas principais
    col1, col2, col3, col4 = st.columns(4)
    create_metrics_cards(df, col1, col2, col3, col4)
    
    # Métricas adicionais
    col1, col2, col3, col4 = st.columns(4)
    
    total_agendamentos = len(df)
    calls_realizadas = len(df[df['STATUS'] == 'Call Realizada'])
    vendas_ganhas = len(df[df['VENDA REALIZADA'] == 'Ganho'])
    no_shows = len(df[df['STATUS'] == 'No Show'])
    
    taxa_show = (calls_realizadas / total_agendamentos * 100) if total_agendamentos > 0 else 0
    taxa_conversao = (vendas_ganhas / calls_realizadas * 100) if calls_realizadas > 0 else 0
    taxa_no_show = (no_shows / total_agendamentos * 100) if total_agendamentos > 0 else 0
    
    # Calcular ciclo médio de vendas
    ciclo_medio = df[df['CICLO DE VENDAS'].notna() & (df['CICLO DE VENDAS'] > 0)]['CICLO DE VENDAS'].mean()
    
    with col1:
        st.metric("Taxa de Show", f"{taxa_show:.1f}%")
    with col2:
        st.metric("Taxa de Conversão", f"{taxa_conversao:.1f}%")
    with col3:
        st.metric("Taxa de No Show", f"{taxa_no_show:.1f}%")
    with col4:
        st.metric("Ciclo Médio", f"{ciclo_medio:.0f} dias" if pd.notna(ciclo_medio) else "N/A")
    
    st.markdown("---")
    
    # Gráficos principais
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("📈 Origem dos Agendamentos (Funil)")
        funil_counts = df['FUNIL'].value_counts()
        fig = px.pie(values=funil_counts.values, names=funil_counts.index,
                    title="Distribuição de Agendamentos por Funil")
        fig.update_layout(height=400)
        st.plotly_chart(fig, use_container_width=True)
    
    with col2:
        st.subheader("📅 Evolução Mensal de Agendamentos")
        if 'DATA' in df.columns:
            df_monthly = df.groupby(df['DATA'].dt.to_period('M')).size().reset_index()
            df_monthly['DATA'] = df_monthly['DATA'].astype(str)
            fig = px.line(df_monthly, x='DATA', y=0,
                         title="Agendamentos por Mês",
                         labels={'0': 'Quantidade', 'DATA': 'Mês'})
            fig.update_layout(height=400)
            st.plotly_chart(fig, use_container_width=True)
    
    # Status das calls
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("🎯 Volume de Reuniões: Agendadas x Realizadas x No Show")
        status_counts = df['STATUS'].value_counts()
        fig = px.bar(x=status_counts.index, y=status_counts.values,
                    title="Distribuição por Status",
                    labels={'x': 'Status', 'y': 'Quantidade'})
        fig.update_layout(height=400)
        st.plotly_chart(fig, use_container_width=True)
    
    with col2:
        st.subheader("💰 Faturamento por Closer")
        faturamento_closer = df[df['VENDA REALIZADA'] == 'Ganho'].groupby('CLOSER')['VALOR_NUM'].sum().sort_values(ascending=False)
        fig = px.bar(x=faturamento_closer.index, y=faturamento_closer.values,
                    title="Receita Total por Closer",
                    labels={'x': 'Closer', 'y': 'Receita (R$)'})
        fig.update_layout(height=400, xaxis_tickangle=-45)
        st.plotly_chart(fig, use_container_width=True)

def dashboard_vendedores(df):
    """Dashboard específico para vendedores/closers"""
    st.header("💼 Dashboard dos Vendedores (Closers)")
    
    # Seletor de vendedor
    closers = ['Todos'] + sorted(df['CLOSER'].dropna().unique().tolist())
    selected_closer = st.selectbox("Selecione o Closer:", closers)
    
    if selected_closer != 'Todos':
        df_filtered = df[df['CLOSER'] == selected_closer]
    else:
        df_filtered = df
    
    # Métricas por vendedor
    col1, col2, col3, col4 = st.columns(4)
    
    total_calls = len(df_filtered[df_filtered['STATUS'] == 'Call Realizada'])
    total_vendas = len(df_filtered[df_filtered['VENDA REALIZADA'] == 'Ganho'])
    taxa_conversao = (total_vendas / total_calls * 100) if total_calls > 0 else 0
    receita_total = df_filtered[df_filtered['VENDA REALIZADA'] == 'Ganho']['VALOR_NUM'].sum()
    
    with col1:
        st.metric("Calls Realizadas", f"{total_calls:,}")
    with col2:
        st.metric("Vendas Fechadas", f"{total_vendas:,}")
    with col3:
        st.metric("Taxa de Conversão", f"{taxa_conversao:.1f}%")
    with col4:
        st.metric("Receita Total", f"R$ {receita_total:,.2f}")
    
    st.markdown("---")
    
    # Análise detalhada por vendedor
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("📊 Taxa de Conversão por Closer")
        vendedor_stats = df.groupby('CLOSER').agg({
            'STATUS': lambda x: (x == 'Call Realizada').sum(),
            'VENDA REALIZADA': lambda x: (x == 'Ganho').sum(),
            'VALOR_NUM': lambda x: x[df.loc[x.index, 'VENDA REALIZADA'] == 'Ganho'].sum()
        }).reset_index()
        
        vendedor_stats['Taxa_Conversao'] = (vendedor_stats['VENDA REALIZADA'] / 
                                          vendedor_stats['STATUS'] * 100).round(1)
        vendedor_stats.columns = ['Vendedor', 'Calls_Realizadas', 'Vendas', 'Receita', 'Taxa_Conversao']
        
        # Gráfico de taxa de conversão
        fig = px.bar(vendedor_stats, x='Vendedor', y='Taxa_Conversao',
                    title="Taxa de Conversão por Closer (%)",
                    text='Taxa_Conversao')
        fig.update_traces(texttemplate='%{text}%', textposition='outside')
        fig.update_layout(height=400, xaxis_tickangle=-45)
        st.plotly_chart(fig, use_container_width=True)
    
    with col2:
        st.subheader("💰 Receita por Closer")
        fig = px.bar(vendedor_stats, x='Vendedor', y='Receita',
                    title="Receita Total por Closer (R$)")
        fig.update_layout(height=400, xaxis_tickangle=-45)
        st.plotly_chart(fig, use_container_width=True)
    
    # Tabela detalhada
    st.subheader("📋 Resumo Detalhado dos Closers")
    st.dataframe(vendedor_stats, use_container_width=True)

def dashboard_sdr(df):
    """Dashboard específico para SDRs"""
    st.header("📞 Dashboard do Time de SDR")
    
    # Seletor de SDR
    sdrs = ['Todos'] + sorted(df['SDR'].dropna().unique().tolist())
    selected_sdr = st.selectbox("Selecione o SDR:", sdrs)
    
    if selected_sdr != 'Todos':
        df_filtered = df[df['SDR'] == selected_sdr]
    else:
        df_filtered = df
    
    # Métricas por SDR
    col1, col2, col3, col4 = st.columns(4)
    
    total_agendamentos = len(df_filtered)
    calls_realizadas = len(df_filtered[df_filtered['STATUS'] == 'Call Realizada'])
    taxa_show = (calls_realizadas / total_agendamentos * 100) if total_agendamentos > 0 else 0
    no_shows = len(df_filtered[df_filtered['STATUS'] == 'No Show'])
    
    with col1:
        st.metric("Agendamentos", f"{total_agendamentos:,}")
    with col2:
        st.metric("Calls Realizadas", f"{calls_realizadas:,}")
    with col3:
        st.metric("Taxa de Show", f"{taxa_show:.1f}%")
    with col4:
        st.metric("No Shows", f"{no_shows:,}")
    
    st.markdown("---")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("📈 Performance por SDR")
        sdr_stats = df.groupby('SDR').agg({
            'STATUS': ['count', lambda x: (x == 'Call Realizada').sum(), lambda x: (x == 'No Show').sum()]
        }).reset_index()
        
        sdr_stats.columns = ['SDR', 'Total_Agendamentos', 'Calls_Realizadas', 'No_Shows']
        sdr_stats['Taxa_Show'] = (sdr_stats['Calls_Realizadas'] / sdr_stats['Total_Agendamentos'] * 100).round(1)
        
        fig = px.bar(sdr_stats, x='SDR', y='Taxa_Show',
                    title="Taxa de Show por SDR (%)",
                    text='Taxa_Show')
        fig.update_traces(texttemplate='%{text}%', textposition='outside')
        fig.update_layout(height=400, xaxis_tickangle=-45)
        st.plotly_chart(fig, use_container_width=True)
    
    with col2:
        st.subheader("📊 Volume de Agendamentos por SDR")
        fig = px.bar(sdr_stats, x='SDR', y='Total_Agendamentos',
                    title="Total de Agendamentos por SDR")
        fig.update_layout(height=400, xaxis_tickangle=-45)
        st.plotly_chart(fig, use_container_width=True)
    
    # Performance por funil e SDR
    st.subheader("🎯 Entrada de Leads por Funil (por SDR)")
    funil_sdr = df.groupby(['FUNIL', 'SDR']).size().reset_index(name='Agendamentos')
    fig = px.bar(funil_sdr, x='FUNIL', y='Agendamentos', color='SDR',
                title="Entrada de Leads por Funil e SDR")
    fig.update_layout(height=400, xaxis_tickangle=-45)
    st.plotly_chart(fig, use_container_width=True)
    
    # Tabela detalhada
    st.subheader("📋 Resumo Detalhado dos SDRs")
    st.dataframe(sdr_stats, use_container_width=True)

def dashboard_funis(df):
    """Dashboard análise de funis"""
    st.header("🎨 Dashboard dos Funis")
    
    # Análise geral dos funis
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("📊 Reuniões Agendadas x Realizadas por Funil")
        funil_analysis = df.groupby('FUNIL').agg({
            'STATUS': ['count', lambda x: (x == 'Call Realizada').sum()]
        }).reset_index()
        
        funil_analysis.columns = ['Funil', 'Agendamentos', 'Realizadas']
        funil_analysis['Taxa_Realizacao'] = (funil_analysis['Realizadas'] / 
                                           funil_analysis['Agendamentos'] * 100).round(1)
        
        fig = px.bar(funil_analysis, x='Funil', y=['Agendamentos', 'Realizadas'],
                    title="Agendamentos vs Calls Realizadas por Funil",
                    barmode='group')
        fig.update_layout(height=400, xaxis_tickangle=-45)
        st.plotly_chart(fig, use_container_width=True)
    
    with col2:
        st.subheader("🎯 Taxa de Conversão por Funil")
        conversao_funil = df[df['STATUS'] == 'Call Realizada'].groupby('FUNIL').agg({
            'VENDA REALIZADA': lambda x: (x == 'Ganho').sum(),
            'STATUS': 'count'
        }).reset_index()
        
        conversao_funil['Taxa_Conversao'] = (conversao_funil['VENDA REALIZADA'] / 
                                           conversao_funil['STATUS'] * 100).round(1)
        
        fig = px.bar(conversao_funil, x='FUNIL', y='Taxa_Conversao',
                    title="Taxa de Conversão por Funil (%)",
                    text='Taxa_Conversao')
        fig.update_traces(texttemplate='%{text}%', textposition='outside')
        fig.update_layout(height=400, xaxis_tickangle=-45)
        st.plotly_chart(fig, use_container_width=True)
    
    # Análise de entrada de leads por mês
    st.subheader("📈 Entrada de Leads por Funil (Mensal)")
    if 'DATA' in df.columns:
        leads_monthly = df.groupby([df['DATA'].dt.to_period('M'), 'FUNIL']).size().reset_index()
        leads_monthly['DATA'] = leads_monthly['DATA'].astype(str)
        leads_monthly.columns = ['Mes', 'Funil', 'Leads']
        
        fig = px.line(leads_monthly, x='Mes', y='Leads', color='Funil',
                     title="Evolução de Leads por Funil")
        fig.update_layout(height=400)
        st.plotly_chart(fig, use_container_width=True)
    
    # Tabela resumo dos funis
    st.subheader("📋 Resumo Completo dos Funis")
    funil_complete = df.groupby('FUNIL').agg({
        'STATUS': ['count', lambda x: (x == 'Call Realizada').sum(), lambda x: (x == 'No Show').sum()],
        'VENDA REALIZADA': lambda x: (x == 'Ganho').sum(),
        'VALOR_NUM': lambda x: x[df.loc[x.index, 'VENDA REALIZADA'] == 'Ganho'].sum()
    }).reset_index()
    
    funil_complete.columns = ['Funil', 'Total_Agendamentos', 'Calls_Realizadas', 'No_Shows', 'Vendas', 'Receita']
    funil_complete['Taxa_Show'] = (funil_complete['Calls_Realizadas'] / funil_complete['Total_Agendamentos'] * 100).round(1)
    funil_complete['Taxa_Conversao'] = (funil_complete['Vendas'] / funil_complete['Calls_Realizadas'] * 100).round(1)
    
    st.dataframe(funil_complete, use_container_width=True)

def dashboard_ciclo_vendas(df):
    """Dashboard análise do ciclo de vendas"""
    st.header("⏱️ Dashboard do Ciclo de Vendas")
    
    # Filtrar apenas registros com ciclo de vendas preenchido
    df_ciclo = df[df['CICLO DE VENDAS'].notna() & (df['CICLO DE VENDAS'] > 0)]
    
    if len(df_ciclo) == 0:
        st.warning("Não há dados de ciclo de vendas disponíveis.")
        return
    
    col1, col2, col3, col4 = st.columns(4)
    
    ciclo_medio = df_ciclo['CICLO DE VENDAS'].mean()
    ciclo_mediano = df_ciclo['CICLO DE VENDAS'].median()
    ciclo_min = df_ciclo['CICLO DE VENDAS'].min()
    ciclo_max = df_ciclo['CICLO DE VENDAS'].max()
    
    with col1:
        st.metric("Ciclo Médio", f"{ciclo_medio:.0f} dias")
    with col2:
        st.metric("Ciclo Mediano", f"{ciclo_mediano:.0f} dias")
    with col3:
        st.metric("Ciclo Mínimo", f"{ciclo_min:.0f} dias")
    with col4:
        st.metric("Ciclo Máximo", f"{ciclo_max:.0f} dias")
    
    st.markdown("---")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("📊 Distribuição do Ciclo de Vendas")
        fig = px.histogram(df_ciclo, x='CICLO DE VENDAS', nbins=20,
                          title="Distribuição do Ciclo de Vendas (dias)")
        fig.update_layout(height=400)
        st.plotly_chart(fig, use_container_width=True)
    
    with col2:
        st.subheader("🎯 Ciclo de Vendas por Funil")
        ciclo_funil = df_ciclo.groupby('FUNIL')['CICLO DE VENDAS'].agg(['mean', 'median', 'count']).reset_index()
        ciclo_funil.columns = ['Funil', 'Ciclo_Medio', 'Ciclo_Mediano', 'Quantidade']
        
        fig = px.bar(ciclo_funil, x='Funil', y='Ciclo_Medio',
                    title="Ciclo Médio de Vendas por Funil (dias)")
        fig.update_layout(height=400, xaxis_tickangle=-45)
        st.plotly_chart(fig, use_container_width=True)
    
    # Análise por vendedor
    st.subheader("💼 Ciclo de Vendas por Closer")
    ciclo_vendedor = df_ciclo.groupby('CLOSER')['CICLO DE VENDAS'].agg(['mean', 'median', 'count']).reset_index()
    ciclo_vendedor.columns = ['Closer', 'Ciclo_Medio', 'Ciclo_Mediano', 'Vendas']
    
    fig = px.bar(ciclo_vendedor, x='Closer', y='Ciclo_Medio',
                title="Ciclo Médio de Vendas por Closer (dias)")
    fig.update_layout(height=400, xaxis_tickangle=-45)
    st.plotly_chart(fig, use_container_width=True)
    
    # Tabelas detalhadas
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("📋 Resumo por Funil")
        st.dataframe(ciclo_funil, use_container_width=True)
    
    with col2:
        st.subheader("📋 Resumo por Closer")
        st.dataframe(ciclo_vendedor, use_container_width=True)

# Interface principal
def main():
    # Header com logo
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.image("https://tmjobs.io/assets/TmJobsLogoDarkMode-BInjDNva.svg", width=200)
    
    st.markdown('<h1 class="main-header">Dashboard TM - Gestão de Agendamentos</h1>', unsafe_allow_html=True)
    st.markdown("Dashboard completo para análise de agendamentos, vendas e performance do time.")
    
    # Carregamento dos dados
    with st.spinner('Carregando dados da planilha...'):
        df = load_data()
    
    if df is not None and not df.empty:
        st.sidebar.success(f"Dados carregados: {len(df)} registros")
        
        # Filtros globais na sidebar
        st.sidebar.header("🔍 Filtros")
        
        # Filtro de período para AGENDAMENTOS
        if 'DATA' in df.columns:
            st.sidebar.subheader("📅 Data de Agendamento")
            date_range_agendamento = st.sidebar.date_input(
                "Período de Agendamento:",
                value=(df['DATA'].min().date() if pd.notna(df['DATA'].min()) else datetime.now().date() - timedelta(days=30),
                       df['DATA'].max().date() if pd.notna(df['DATA'].max()) else datetime.now().date()),
                min_value=df['DATA'].min().date() if pd.notna(df['DATA'].min()) else datetime.now().date() - timedelta(days=365),
                max_value=df['DATA'].max().date() if pd.notna(df['DATA'].max()) else datetime.now().date(),
                key="agendamento_date"
            )
            
            if len(date_range_agendamento) == 2:
                start_date_agend, end_date_agend = date_range_agendamento
                df = df[(df['DATA'] >= pd.Timestamp(start_date_agend)) & 
                       (df['DATA'] <= pd.Timestamp(end_date_agend))]
        
        # Filtro de período para VENDAS
        if 'DIA DA VENDA' in df.columns:
            st.sidebar.subheader("💰 Data de Venda")
            usar_filtro_venda = st.sidebar.checkbox("Filtrar também por data de venda")
            
            if usar_filtro_venda:
                vendas_com_data = df[df['DIA DA VENDA'].notna()]
                if len(vendas_com_data) > 0:
                    date_range_venda = st.sidebar.date_input(
                        "Período de Venda:",
                        value=(vendas_com_data['DIA DA VENDA'].min().date(),
                               vendas_com_data['DIA DA VENDA'].max().date()),
                        min_value=vendas_com_data['DIA DA VENDA'].min().date(),
                        max_value=vendas_com_data['DIA DA VENDA'].max().date(),
                        key="venda_date"
                    )
                    
                    if len(date_range_venda) == 2:
                        start_date_venda, end_date_venda = date_range_venda
                        # Para vendas, filtramos apenas os registros que têm data de venda
                        mask_vendas = (df['DIA DA VENDA'] >= pd.Timestamp(start_date_venda)) & \
                                    (df['DIA DA VENDA'] <= pd.Timestamp(end_date_venda))
                        mask_sem_venda = df['DIA DA VENDA'].isna()  # Manter registros sem venda
                        df = df[mask_vendas | mask_sem_venda]
        
        # Outros filtros
        st.sidebar.subheader("🎯 Filtros Adicionais")
        
        # Filtro por produto
        produtos = ['Todos'] + sorted(df['PRODUTO'].dropna().unique().tolist())
        selected_produto = st.sidebar.selectbox("Produto:", produtos)
        if selected_produto != 'Todos':
            df = df[df['PRODUTO'] == selected_produto]
        
        # Filtro por funil
        funis = ['Todos'] + sorted(df['FUNIL'].dropna().unique().tolist())
        selected_funil = st.sidebar.selectbox("Funil:", funis)
        if selected_funil != 'Todos':
            df = df[df['FUNIL'] == selected_funil]
        
        # Filtro por status
        status_options = ['Todos'] + sorted(df['STATUS'].dropna().unique().tolist())
        selected_status = st.sidebar.selectbox("Status:", status_options)
        if selected_status != 'Todos':
            df = df[df['STATUS'] == selected_status]
        
        st.sidebar.markdown("---")
        st.sidebar.metric("📊 Registros Filtrados", len(df))
        
        # Abas principais
        tab1, tab2, tab3, tab4, tab5 = st.tabs([
            "🏠 Geral", "💼 Closers", "📞 SDRs", "🎨 Funis", "⏱️ Ciclo de Vendas"
        ])
        
        with tab1:
            dashboard_geral(df)
        
        with tab2:
            dashboard_vendedores(df)
        
        with tab3:
            dashboard_sdr(df)
        
        with tab4:
            dashboard_funis(df)
        
        with tab5:
            dashboard_ciclo_vendas(df)
        
        # Opção de download dos dados processados
        st.sidebar.markdown("---")
        st.sidebar.header("💾 Download")
        csv = df.to_csv(index=False)
        st.sidebar.download_button(
            label="📥 Download dados filtrados (CSV)",
            data=csv,
            file_name=f"agendamentos_filtrados_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
            mime="text/csv"
        )
        
        # Botão para atualizar dados
        if st.sidebar.button("🔄 Atualizar Dados"):
            st.cache_data.clear()
            st.rerun()
        
    else:
        st.error("❌ Não foi possível carregar os dados da planilha. Verifique:")
        st.write("- Se as credenciais do Google Sheets estão configuradas corretamente")
        st.write("- Se o ID da planilha está correto")
        st.write("- Se a aba 'Agendamentos' existe na planilha")
        st.write("- Se há dados na planilha")
        
        # Informações sobre o dashboard
        st.markdown("---")
        st.header("📋 Sobre este Dashboard")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("""
            ### 🎯 Funcionalidades Principais:
            
            **Dashboard Geral:**
            - Métricas consolidadas de agendamentos e vendas
            - Origem de cada agendamento (funil)
            - Taxa de conversão geral
            - Volume de reuniões agendadas vs realizadas vs no show
            - Faturamento por closer
            - Ciclo médio de vendas
            
            **Dashboard Closers:**
            - Taxa de conversão individual por closer
            - Volume de reuniões por vendedor
            - Performance comparativa entre closers
            - Receita total por closer
            """)
        
        with col2:
            st.markdown("""
            ### 📊 Análises Disponíveis:
            
            **Dashboard SDRs:**
            - Taxa de show up por SDR
            - Volume de agendamentos por SDR
            - Performance por funil
            - Entrada de leads por funil
            
            **Análise de Funis:**
            - Taxa de conversão por origem
            - Reuniões agendadas x realizadas por funil
            - Entrada de leads por funil (mensal)
            - Performance comparativa entre funis
            
            **Ciclo de Vendas:**
            - Tempo médio de fechamento
            - Análise por funil e closer
            - Distribuição temporal do ciclo
            """)
        
        st.markdown("---")
        st.markdown("""
        ### 🔧 Filtros Disponíveis:
        
        **Filtro de Data de Agendamento**: Filtra pela coluna "DATA" - quando o agendamento foi criado
        
        **Filtro de Data de Venda**: Filtra pela coluna "DIA DA VENDA" - quando a venda foi efetivamente fechada
        
        **Outros Filtros**: Produto, Funil, Status
        
        ### 📁 Estrutura dos Dados:
        
        O sistema puxa dados diretamente da planilha Google Sheets e espera as seguintes colunas:
        - **DATA**: Data do agendamento
        - **SDR**: Responsável pelo agendamento  
        - **CLOSER**: Vendedor responsável
        - **FUNIL**: Origem do lead
        - **STATUS**: Status da call (Call Realizada, No Show, etc.)
        - **VENDA REALIZADA**: Resultado da venda (Ganho, Cancelamento)
        - **VALOR**: Valor da venda
        - **DIA DA VENDA**: Data que a venda foi fechada
        - **CICLO DE VENDAS**: Dias para fechamento
        """)
    
    # Footer
    st.markdown("---")
    st.markdown("Dashboard desenvolvido por Igor Oliveira para análise de vendas e agendamentos | TM Jobs")
    st.sidebar.markdown("---")
    st.sidebar.info(f"Última atualização: {datetime.now().strftime('%d/%m/%Y %H:%M')}")


if __name__ == "__main__":
    main()
