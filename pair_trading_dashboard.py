import streamlit as st
import yfinance as yf
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
from scipy.stats import zscore
import sys
import os
from datetime import datetime, timedelta
import matplotlib.dates as mdates
from streamlit_autorefresh import st_autorefresh

# Configuração da página
st.set_page_config(
    page_title="Dashboard de Pair Trading com Brent",
    page_icon="📈",
    layout="wide"
)

# Auto-refresh every 10 minutes (600000 milliseconds)
st_autorefresh(interval=600000, key="data_refresh")

# Título do dashboard
st.title("Dashboard de Pair Trading com Cotação do Brent")

# Sidebar para configurações
st.sidebar.header("Configurações")

# Lista de ações disponíveis (bancos e Petrobras da Bovespa)
acoes_disponiveis = {
    'Bancos': ['ITUB3.SA', 'ITUB4.SA', 'BBDC3.SA', 'BBDC4.SA', 'BBAS3.SA', 'SANB3.SA', 'SANB4.SA', 'BPAC3.SA', 'BPAC5.SA', 'BPAC11.SA'],
    'Petrobras': ['PETR3.SA', 'PETR4.SA']
}

# Opções de período
periodos = {
    '1 mês': '1mo',
    '3 meses': '3mo',
    '6 meses': '6mo',
    '1 ano': '1y',
    '2 anos': '2y',
    '5 anos': '5y',
    'Desde 2016': 'max'  # Usando 'max' para obter dados desde o início e depois filtraremos para 2016
}

# Seleção de categoria
categoria = st.sidebar.selectbox("Categoria", list(acoes_disponiveis.keys()), index=1 if 'Petrobras' in acoes_disponiveis else 0)

# Seleção de ações baseada na categoria
acoes_selecionadas = st.sidebar.multiselect(
    "Selecione as ações para análise (máximo 2)",
    acoes_disponiveis[categoria],
    default=acoes_disponiveis[categoria][:2] if len(acoes_disponiveis[categoria]) >= 2 else acoes_disponiveis[categoria]
)

# Limitar a seleção a 2 ações
if len(acoes_selecionadas) > 2:
    st.sidebar.warning("Por favor, selecione no máximo 2 ações para a análise de pair trading.")
    acoes_selecionadas = acoes_selecionadas[:2]

# Seleção de período
periodo_selecionado = st.sidebar.selectbox("Período de análise", list(periodos.keys()))
periodo_valor = periodos[periodo_selecionado]

# Configuração de Z-score
st.sidebar.subheader("Configuração de Z-score")
limite_superior_zscore = st.sidebar.slider("Limite Superior Z-score", 0.5, 3.0, 1.0, 0.1)
limite_inferior_zscore = -limite_superior_zscore

# Opções de símbolos para petróleo/commodities
commodities_disponiveis = {
    'USO': 'United States Oil Fund (cerca de $69)',
    'BNO': 'United States Brent Oil Fund',
    'UCO': 'ProShares Ultra Bloomberg Crude Oil',
    'XLE': 'Energy Select Sector SPDR Fund',
    'XOP': 'SPDR S&P Oil & Gas Exploration & Production ETF',
    'OIH': 'VanEck Oil Services ETF'
}

# Seleção do símbolo da commodity
commodity_symbol = st.sidebar.selectbox(
    "Selecione a commodity de referência",
    list(commodities_disponiveis.keys()),
    format_func=lambda x: f"{x} - {commodities_disponiveis[x]}"
)

# Função para obter cotação atual
@st.cache_data(ttl=300)  # Cache por 5 minutos
def obter_cotacao(acao):
    try:
        dados = yf.Ticker(acao)
        preco_atual = dados.history(period='1d')['Close'].iloc[0]
        return preco_atual
    except Exception as e:
        st.error(f"Erro ao obter cotação de {acao}: {e}")
        return None

# Função para obter série histórica
@st.cache_data(ttl=300)  # Cache por 5 minutos
def obter_serie_historica(acao, periodo='1y'):
    try:
        # Obtém os dados históricos com preços ajustados para desdobramentos/bonificações
        ticker = yf.Ticker(acao)
        
        # Se o período for 'Desde 2016', obtemos o máximo de dados e filtramos
        if periodo == 'max':
            dados = ticker.history(period=periodo, auto_adjust=True)
            # Filtra para dados a partir de 2016-01-01
            dados = dados.loc['2016-01-01':]
        else:
            dados = ticker.history(period=periodo, auto_adjust=True)
        
        # Exibe informações sobre ações corporativas se disponíveis
        try:
            acoes_corporativas = ticker.actions
            if not acoes_corporativas.empty:
                # Filtra para ações corporativas a partir de 2016
                acoes_corporativas = acoes_corporativas.loc['2016-01-01':]
                if not acoes_corporativas.empty:
                    # Verifica se existem desdobramentos
                    has_splits = False
                    if 'Stock Splits' in acoes_corporativas.columns:
                        splits = acoes_corporativas[acoes_corporativas['Stock Splits'] > 0]
                        has_splits = not splits.empty
                    
                    # Cria um expander para mostrar todas as ações corporativas (dividendos, etc.)
                    with st.sidebar.expander(f"Ações Corporativas - {acao}", expanded=False):
                        st.dataframe(acoes_corporativas)
                    
                    # Cria um expander separado e destacado para desdobramentos, se houver
                    if has_splits:
                        with st.sidebar.expander(f"🔍 DESDOBRAMENTOS - {acao}", expanded=True):
                            st.write(f"**Desdobramentos desde 2016:**")
                            for data, row in splits.iterrows():
                                st.write(f"- {data.strftime('%d/%m/%Y')}: **{row['Stock Splits']}:1**")
                            
                            # Adiciona uma nota explicativa sobre o impacto no ratio
                            st.info(f"""
                            **Nota:** Os desdobramentos acima são automaticamente considerados no cálculo do ratio.
                            Por exemplo, um desdobramento de 2:1 significa que o preço da ação foi ajustado para metade
                            do valor para manter a consistência histórica.
                            """)
        except Exception as e:
            st.warning(f"Não foi possível obter ações corporativas para {acao}: {e}")
            
        return dados
    except Exception as e:
        st.error(f"Erro ao obter série histórica de {acao}: {e}")
        return None

# Exibir cotações atuais
if acoes_selecionadas:
    st.subheader("Cotações Atuais")
    
    # Criar colunas para exibir as cotações
    cols = st.columns(len(acoes_selecionadas) + 1)  # +1 para a commodity
    
    # Exibir cotações das ações selecionadas
    for i, acao in enumerate(acoes_selecionadas):
        preco = obter_cotacao(acao)
        if preco is not None:
            cols[i].metric(label=acao, value=f"R$ {preco:.2f}")
    
    # Exibir cotação da commodity
    commodity_preco = obter_cotacao(commodity_symbol)
    if commodity_preco is not None:
        cols[-1].metric(label=f"{commodity_symbol}", value=f"US$ {commodity_preco:.2f}")

# Análise de Pair Trading
if len(acoes_selecionadas) == 2:
    st.subheader(f"Análise de Pair Trading: {acoes_selecionadas[0]} vs {acoes_selecionadas[1]}")
    
    # Obter séries históricas
    serie_acao1 = obter_serie_historica(acoes_selecionadas[0], periodo=periodo_valor)
    serie_acao2 = obter_serie_historica(acoes_selecionadas[1], periodo=periodo_valor)
    serie_brent = obter_serie_historica(commodity_symbol, periodo=periodo_valor)
    
    if serie_acao1 is not None and serie_acao2 is not None and serie_brent is not None:
        # Calcular o ratio entre as ações usando preços ajustados para desdobramentos
        # Os preços já estão ajustados pelo parâmetro auto_adjust=True na função obter_serie_historica
        ratio = serie_acao1['Close'] / serie_acao2['Close']
        
        # Adicionar informação sobre o ratio ajustado com foco em desdobramentos
        st.info("""
        **Nota sobre o cálculo do ratio:** 
        O ratio é calculado usando preços ajustados para desdobramentos desde 2016.
        Isso garante que a análise leva em conta todas as mudanças na estrutura de capital das empresas,
        especialmente os desdobramentos (stock splits) que afetam diretamente a quantidade de ações.
        
        Os desdobramentos são destacados na barra lateral para cada ativo.
        """)
        
        # Calcular o z-score do ratio
        z_score = zscore(ratio)
        
        # Calcular a média e o desvio padrão do ratio
        media_ratio = ratio.mean()
        desvio_padrao_ratio = ratio.std()
        
        # Exibir estatísticas
        col1, col2, col3 = st.columns(3)
        col1.metric("Ratio Atual", f"{ratio.iloc[-1]:.4f}")
        col2.metric("Z-Score Atual", f"{z_score[-1]:.4f}")
        
        # Tomada de decisão com base nos limites do z-score
        if z_score[-1] > limite_superior_zscore:
            decisao = "Sinal de Venda"
        elif z_score[-1] < limite_inferior_zscore:
            decisao = "Sinal de Compra"
        else:
            decisao = "Neutro"
        
        col3.metric("Sinal", decisao)
        
        # Criar figura para o gráfico
        fig, ax1 = plt.subplots(figsize=(12, 8))
        
        # Plotar o ratio
        ax1.plot(ratio.index, ratio.values, label='Ratio', color='blue')
        ax1.axhline(y=media_ratio, color='green', linestyle='-', label='Média')
        ax1.axhline(y=media_ratio + limite_superior_zscore * desvio_padrao_ratio, color='red', linestyle='--', 
                   label=f'+{limite_superior_zscore} Desvios Padrões')
        ax1.axhline(y=media_ratio - limite_superior_zscore * desvio_padrao_ratio, color='red', linestyle='--', 
                   label=f'-{limite_superior_zscore} Desvios Padrões')
        
        # Configurar eixo Y primário (ratio)
        ax1.set_xlabel('Data')
        ax1.set_ylabel('Ratio', color='blue')
        ax1.tick_params(axis='y', labelcolor='blue')
        
        # Criar eixo Y secundário para a commodity
        ax2 = ax1.twinx()
        ax2.plot(serie_brent.index, serie_brent['Close'], color='orange', linestyle='-.', label=commodity_symbol)
        ax2.set_ylabel(f'Preço de {commodity_symbol} (USD)', color='orange')
        ax2.tick_params(axis='y', labelcolor='orange')
        
        # Configurar título e legenda
        plt.title(f'Ratio entre {acoes_selecionadas[0]} e {acoes_selecionadas[1]} com {commodity_symbol} - {periodo_selecionado}')
        
        # Combinar legendas dos dois eixos
        lines1, labels1 = ax1.get_legend_handles_labels()
        lines2, labels2 = ax2.get_legend_handles_labels()
        ax1.legend(lines1 + lines2, labels1 + labels2, loc='upper left')
        
        # Formatar datas no eixo X
        ax1.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d'))
        plt.xticks(rotation=45)
        
        # Ajustar layout
        plt.tight_layout()
        
        # Exibir o gráfico no Streamlit
        st.pyplot(fig)
        
        # Exibir tabela de dados
        st.subheader("Dados Históricos")
        
        # Criar DataFrame combinado - garantindo que todos os índices estejam alinhados
        # Primeiro, criamos um índice comum usando a interseção dos índices
        idx_comum = serie_acao1.index.intersection(serie_acao2.index).intersection(serie_brent.index)
        
        # Agora criamos o DataFrame usando apenas os dados com o índice comum
        df_combinado = pd.DataFrame({
            f"{acoes_selecionadas[0]} (Fechamento)": serie_acao1.loc[idx_comum, 'Close'],
            f"{acoes_selecionadas[1]} (Fechamento)": serie_acao2.loc[idx_comum, 'Close'],
            "Ratio": ratio.loc[idx_comum],
            "Z-Score": pd.Series(zscore(ratio.loc[idx_comum]), index=idx_comum),
            f"{commodity_symbol} (USD)": serie_brent.loc[idx_comum, 'Close']
        })
        
        # Exibir os últimos 10 registros
        st.dataframe(df_combinado.tail(10))
        
        # Opção para download dos dados
        csv = df_combinado.to_csv().encode('utf-8')
        st.download_button(
            label="Download dos dados em CSV",
            data=csv,
            file_name=f"pair_trading_{acoes_selecionadas[0]}_{acoes_selecionadas[1]}_{periodo_valor}.csv",
            mime="text/csv",
        )
    else:
        st.error("Não foi possível obter os dados históricos para as ações selecionadas ou para o Brent.")
elif len(acoes_selecionadas) == 1:
    st.info("Selecione duas ações para realizar a análise de pair trading.")
else:
    st.info("Selecione ações para começar a análise.")

# Informações adicionais
st.sidebar.markdown("---")
st.sidebar.subheader("Sobre")
st.sidebar.info("""
Este dashboard permite analisar estratégias de pair trading entre ações de bancos e Petrobras da Bovespa, 
incluindo a cotação do petróleo Brent como referência adicional.
""")
