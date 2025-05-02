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


# Configuração da página
st.set_page_config(
    page_title="Dashboard de Pair Trading com Brent",
    page_icon="📈",
    layout="wide"
)

# Título do dashboard
st.title("Dashboard de Pair Trading com Cotação do Brent")

# Sidebar para configurações
st.sidebar.header("Configurações")

# Inicializa o estado da sessão se não existir
if "first_load_done" not in st.session_state:
    st.session_state.first_load_done = False

# Botão de atualização manual
if st.sidebar.button("🔄 Atualizar Dados"):
    st.cache_data.clear() # Limpa o cache para buscar dados novos
    st.session_state.first_load_done = True # Marca que o botão foi clicado
    st.rerun()

st.sidebar.markdown("--- ") # Separador

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
    """Obtém a cotação atual de uma ação, com tratamento de erro para rate limit."""
    try:
        dados = yf.Ticker(acao)
        # Tenta obter o preço mais recente (pega 2 dias para garantir que há dados)
        hist = dados.history(period="2d") 
        if hist.empty:
            st.warning(f"Não foi possível obter cotação atual para {acao}. Pode ser um problema temporário ou limite de requisições. Tente atualizar mais tarde.")
            return None
        preco_atual = hist["Close"].iloc[-1] # Usar -1 para garantir o último disponível
        return preco_atual
    except Exception as e:
        # Verifica se o erro é relacionado a rate limit
        error_msg = str(e).lower()
        if "too many requests" in error_msg or "rate limited" in error_msg or "429" in error_msg:
            st.warning(f"Limite de requisições atingido para cotação de {acao}. Tente atualizar novamente em alguns minutos.")
        else:
            # Outro erro
            st.error(f"Erro ao obter cotação de {acao}: {e}")
        return None

# Função para obter série histórica
@st.cache_data(ttl=300)  # Cache por 5 minutos
def obter_serie_historica(acao, periodo='1y'):
    """Obtém a série histórica de uma ação usando yfinance, com tratamento de erro para rate limit."""
    try:
        # Obtém os dados históricos com preços ajustados para desdobramentos/bonificações
        ticker = yf.Ticker(acao)
        
        # Se o período for 'max', obtemos o máximo de dados e filtramos
        if periodo == 'max': # Use 'max' as string value for period
            dados = ticker.history(period=periodo, auto_adjust=True)
            # Filtra para dados a partir de 2016-01-01
            dados = dados.loc['2016-01-01':]
        else:
            dados = ticker.history(period=periodo, auto_adjust=True)

        # Verifica se os dados foram retornados (yfinance pode retornar vazio em caso de erro)
        if dados.empty:
            st.warning(f"Não foi possível obter dados históricos para {acao}. Pode ser um problema temporário ou limite de requisições. Tente atualizar mais tarde.")
            return None
            
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
        except Exception as e_actions:
            # Silenciosamente ignora erros ao buscar ações corporativas, pois não são essenciais
            pass
            
        return dados
        
    except Exception as e:
        # Verifica se o erro é relacionado a rate limit
        error_msg = str(e).lower()
        if "too many requests" in error_msg or "rate limited" in error_msg or "429" in error_msg:
            st.warning(f"Limite de requisições atingido para dados históricos de {acao}. Tente atualizar novamente em alguns minutos.")
        else:
            # Outro erro
            st.error(f"Erro ao obter série histórica de {acao}: {e}")
        return None

# --- Lógica Principal --- 
# Só executa a lógica principal se o botão de atualização já foi clicado uma vez
if st.session_state.first_load_done:
    # Exibir cotações atuais
    if acoes_selecionadas:
        st.subheader("Cotações Atuais")

        # Criar colunas para exibir as cotações
        cols = st.columns(len(acoes_selecionadas) + 1)  # +1 para a commodity

        # Exibir cotações das ações selecionadas
        cotacoes_ok = True # Resetar flag a cada atualização
        for i, acao in enumerate(acoes_selecionadas):
            preco = obter_cotacao(acao)
            if preco is None:
                cotacoes_ok = False # Marca se alguma cotação falhou
                # Mensagem de erro já é exibida por obter_cotacao
                cols[i].metric(label=acao, value="Erro")
            else:
                # Ajuste para exibir moeda correta (R$ para .SA)
                currency_prefix_stock = "R$" if ".SA" in acao else "$" 
                cols[i].metric(label=acao, value=f"{currency_prefix_stock} {preco:.2f}")

        # Exibir cotação da commodity
        commodity_preco = obter_cotacao(commodity_symbol)
        if commodity_preco is None:
            cotacoes_ok = False # Marca se a cotação da commodity falhou
            # Mensagem de erro já é exibida por obter_cotacao
            cols[len(acoes_selecionadas)].metric(label=commodity_symbol, value="Erro")
        else:
            # Determina a moeda com base no símbolo (simplificado)
            # Assumindo que todos os ETFs listados são USD
            currency_prefix_comm = "US$" 
            cols[len(acoes_selecionadas)].metric(label=commodity_symbol, value=f"{currency_prefix_comm} {commodity_preco:.2f}")

    # Análise de Pair Trading
    if len(acoes_selecionadas) == 2 and cotacoes_ok: # Só prossegue se as cotações foram obtidas
        st.subheader(f"Análise de Pair Trading: {acoes_selecionadas[0]} vs {acoes_selecionadas[1]}")

        # Nota sobre o cálculo do ratio
        st.info("""
        **Nota sobre o cálculo do ratio:** O ratio é calculado usando preços ajustados para desdobramentos desde 2016. 
        Isso garante que a análise leva em conta todas as mudanças na estrutura de capital das empresas, 
        especialmente os desdobramentos (stock splits) que afetam diretamente a quantidade de ações.
        
        Os desdobramentos são destacados na barra lateral para cada ativo.
        """)

        # Obter séries históricas
        serie_acao1 = obter_serie_historica(acoes_selecionadas[0], periodo=periodo_valor)
        serie_acao2 = obter_serie_historica(acoes_selecionadas[1], periodo=periodo_valor)
        serie_commodity = obter_serie_historica(commodity_symbol, periodo=periodo_valor)

        if serie_acao1 is not None and serie_acao2 is not None and serie_commodity is not None:
            # Alinhar as séries temporais (usando interseção dos índices)
            common_index = serie_acao1.index.intersection(serie_acao2.index).intersection(serie_commodity.index)
            serie_acao1 = serie_acao1.loc[common_index]
            serie_acao2 = serie_acao2.loc[common_index]
            serie_commodity = serie_commodity.loc[common_index]

            if not common_index.empty:
                # Calcular o ratio entre as ações (usando preços ajustados)
                ratio = serie_acao1["Close"] / serie_acao2["Close"]

                # Calcular Z-score do ratio
                z_score_ratio = zscore(ratio)

                # Calcular média e desvios padrão do ratio
                media_ratio = ratio.mean()
                std_ratio = ratio.std()
                limite_superior = media_ratio + limite_superior_zscore * std_ratio
                limite_inferior = media_ratio + limite_inferior_zscore * std_ratio

                # Exibir métricas atuais
                ratio_atual = ratio.iloc[-1]
                z_score_atual = z_score_ratio[-1]

                # Determinar sinal
                sinal = "Neutro"
                if z_score_atual > limite_superior_zscore:
                    sinal = f"Vender {acoes_selecionadas[0]} / Comprar {acoes_selecionadas[1]}"
                elif z_score_atual < limite_inferior_zscore:
                    sinal = f"Comprar {acoes_selecionadas[0]} / Vender {acoes_selecionadas[1]}"

                col1, col2, col3 = st.columns(3)
                col1.metric("Ratio Atual", f"{ratio_atual:.4f}")
                col2.metric("Z-Score Atual", f"{z_score_atual:.4f}")
                col3.metric("Sinal", sinal)

                # Plotar o gráfico
                st.subheader(f"Ratio entre {acoes_selecionadas[0]} e {acoes_selecionadas[1]} com {commodity_symbol} - {periodo_selecionado}") # Usar periodo_selecionado para o texto
                fig, ax1 = plt.subplots(figsize=(12, 6))

                # Eixo esquerdo para o Ratio
                color = "tab:blue"
                ax1.set_xlabel("Data")
                ax1.set_ylabel("Ratio", color=color)
                ax1.plot(ratio.index, ratio, label="Ratio", color=color)
                ax1.axhline(media_ratio, color="gray", linestyle="--", label="Média")
                ax1.axhline(limite_superior, color="red", linestyle="--", label=f"+{limite_superior_zscore:.1f} Desvios Padrões")
                ax1.axhline(limite_inferior, color="green", linestyle="--", label=f"-{abs(limite_inferior_zscore):.1f} Desvios Padrões") # Use abs() for negative limit label
                ax1.tick_params(axis="y", labelcolor=color)
                ax1.legend(loc="upper left")
                ax1.grid(True)

                # Eixo direito para a Commodity
                ax2 = ax1.twinx()  # instantiate a second axes that shares the same x-axis
                color = "tab:orange"
                ax2.set_ylabel(f"{commodity_symbol} (Preço)", color=color)  # we already handled the x-label with ax1
                ax2.plot(serie_commodity.index, serie_commodity["Close"], label=commodity_symbol, color=color, alpha=0.7)
                ax2.tick_params(axis="y", labelcolor=color)
                ax2.legend(loc="upper right")

                fig.tight_layout()  # otherwise the right y-label is slightly clipped

                # Formatar eixo X para mostrar datas de forma legível
                ax1.xaxis.set_major_locator(mdates.AutoDateLocator())
                ax1.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m-%d"))
                plt.setp(ax1.get_xticklabels(), rotation=45, ha="right")

                st.pyplot(fig)

                # Tabela de dados históricos
                st.subheader("Dados Históricos")
                dados_tabela = pd.DataFrame({
                    f"{acoes_selecionadas[0]}": serie_acao1["Close"],
                    f"{acoes_selecionadas[1]}": serie_acao2["Close"],
                    "Ratio": ratio,
                    "Z-Score": z_score_ratio,
                    f"{commodity_symbol}": serie_commodity["Close"]
                })
                st.dataframe(dados_tabela)

                # Botão de download CSV
                @st.cache_data
                def convert_df_to_csv(df):
                    return df.to_csv(index=True).encode("utf-8")

                csv = convert_df_to_csv(dados_tabela)
                st.download_button(
                    label="Download dados como CSV",
                    data=csv,
                    file_name=f"pair_trading_{acoes_selecionadas[0]}_{acoes_selecionadas[1]}_{periodo_selecionado}.csv", # Usar periodo_selecionado
                    mime="text/csv",
                )
            else:
                st.warning("Não há dados comuns suficientes no período selecionado para as ações e commodity.")
        else:
            # Mensagens de erro/aviso já foram exibidas pelas funções de obtenção de dados
            st.error("Não foi possível realizar a análise devido a erros na obtenção dos dados. Verifique os avisos acima.")

    elif len(acoes_selecionadas) != 2 and cotacoes_ok: # Adicionado cotacoes_ok aqui também
        st.warning("Por favor, selecione exatamente duas ações para análise de pair trading.")
    # Se cotacoes_ok for False, as mensagens de erro já foram exibidas na seção de cotações

else:
    # Mensagem exibida antes do primeiro clique no botão
    st.info("📈 Por favor, clique no botão '🔄 Atualizar Dados' na barra lateral para carregar as informações.")

# Informações adicionais
st.sidebar.markdown("---")
st.sidebar.subheader("Sobre")
st.sidebar.info("""
Este dashboard permite analisar estratégias de pair trading entre ações de bancos e Petrobras da Bovespa, 
incluindo a cotação do petróleo Brent como referência adicional.
""")

