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

# Botão de atualização manual
if st.sidebar.button("🔄 Atualizar Dados"):
    # Limpa o cache de todas as funções decoradas com @st.cache_data
    st.session_state.dados_carregados = True # Marca que o botão foi clicado
    st.cache_data.clear()
    # Força o rerun do script para buscar novos dados
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
    """Obtém a cotação mais recente de uma ação, com tratamento de erro para rate limit."""
    try:
        ticker = yf.Ticker(acao)
        # Tenta obter o preço mais recente
        hist = ticker.history(period='1d', interval='1m') # Tenta intraday mais recente
        if not hist.empty:
            return hist['Close'].iloc[-1]
        else:
            # Se intraday falhar, tenta o fechamento do dia anterior
            hist_daily = ticker.history(period='2d')
            if not hist_daily.empty:
                return hist_daily['Close'].iloc[-1]
            else:
                # st.warning(f"Não foi possível obter cotação recente para {acao}.") # Comentado para reduzir warnings
                return None
    except Exception as e:
        err_msg = str(e).lower()
        if "too many requests" in err_msg or "rate limited" in err_msg:
            st.warning(f"Limite de requisições atingido para {acao}. Tente atualizar mais tarde.")
        # else:
            # st.error(f"Erro ao obter cotação de {acao}: {e}") # Comentado para reduzir erros
        return None

# Função para obter série histórica
@st.cache_data(ttl=300)  # Cache por 5 minutos
def obter_serie_historica(acao, periodo='1y'):
    """Obtém a série histórica de uma ação, com tratamento de erro para rate limit."""
    try:
        ticker = yf.Ticker(acao)
        if periodo == 'max':
            dados = ticker.history(period=periodo, auto_adjust=True)
            dados = dados.loc['2016-01-01':]
        else:
            dados = ticker.history(period=periodo, auto_adjust=True)
        
        if dados.empty:
             # st.warning(f"Dados históricos não encontrados para {acao} no período {periodo}.") # Comentado
             return None

        # Exibe informações sobre ações corporativas se disponíveis
        try:
            acoes_corporativas = ticker.actions
            if not acoes_corporativas.empty:
                acoes_corporativas = acoes_corporativas.loc['2016-01-01':]
                if not acoes_corporativas.empty:
                    has_splits = 'Stock Splits' in acoes_corporativas.columns and (acoes_corporativas['Stock Splits'] > 0).any()
                    
                    with st.sidebar.expander(f"Ações Corporativas - {acao}", expanded=False):
                        st.dataframe(acoes_corporativas)
                    
                    if has_splits:
                        splits = acoes_corporativas[acoes_corporativas['Stock Splits'] > 0]
                        with st.sidebar.expander(f"🔍 DESDOBRAMENTOS - {acao}", expanded=True):
                            st.write(f"**Desdobramentos desde 2016:**")
                            for data, row in splits.iterrows():
                                st.write(f"- {data.strftime('%d/%m/%Y')}: **{row['Stock Splits']:.0f}:1**") # Format split ratio
                            st.info("""
                            **Nota:** Desdobramentos são automaticamente considerados no cálculo do ratio (preços ajustados).
                            """)
        except Exception:
            # Ignora erros ao buscar ações corporativas, não é crítico
            pass 
            
        return dados
    except Exception as e:
        err_msg = str(e).lower()
        if "too many requests" in err_msg or "rate limited" in err_msg:
            st.warning(f"Limite de requisições atingido para dados históricos de {acao}. Tente atualizar mais tarde.")
        # elif "no data found" in err_msg:
             # st.warning(f"Nenhum dado histórico encontrado para {acao} no período solicitado.") # Comentado
        # else:
            # st.error(f"Erro ao obter série histórica de {acao}: {e}") # Comentado
        return None

# --- Lógica Principal --- 

# Inicializa variáveis e placeholders
decisao = "Aguardando dados"
ratio_atual = None
z_score_atual = None
cotacoes_ok = False
precos_atuais = {}
serie_acao1 = None
serie_acao2 = None
serie_brent = None

# Verifica se o botão de atualizar foi clicado ou se é a primeira execução
# Usaremos session_state para carregar dados apenas após o clique
if 'dados_carregados' not in st.session_state:
    st.session_state.dados_carregados = False

if st.session_state.dados_carregados:
    # Tenta obter cotações atuais
    if acoes_selecionadas:
        cotacoes_ok = True
        for acao in acoes_selecionadas:
            preco = obter_cotacao(acao)
            if preco is None:
                cotacoes_ok = False # Marca como erro se qualquer cotação falhar
            precos_atuais[acao] = preco
        
        commodity_preco = obter_cotacao(commodity_symbol)
        precos_atuais[commodity_symbol] = commodity_preco # Guarda mesmo se for None

    # Tenta obter séries históricas se as cotações estiverem ok e 2 ações selecionadas
    if len(acoes_selecionadas) == 2 and cotacoes_ok:
        serie_acao1 = obter_serie_historica(acoes_selecionadas[0], periodo=periodo_valor)
        serie_acao2 = obter_serie_historica(acoes_selecionadas[1], periodo=periodo_valor)
        serie_brent = obter_serie_historica(commodity_symbol, periodo=periodo_valor)

# --- Exibição --- 

st.subheader("Cotações Atuais")
if not st.session_state.dados_carregados:
    st.info("📈 Por favor, clique no botão '🔄 Atualizar Dados' na barra lateral para carregar as informações.")
elif acoes_selecionadas:
    cols = st.columns(len(acoes_selecionadas) + 1)
    for i, acao in enumerate(acoes_selecionadas):
        preco = precos_atuais.get(acao)
        cols[i].metric(label=acao, value=f"R$ {preco:.2f}" if preco is not None else "Erro")
    
    commodity_preco_display = precos_atuais.get(commodity_symbol)
    cols[-1].metric(label=f"{commodity_symbol}", value=f"US$ {commodity_preco_display:.2f}" if commodity_preco_display is not None else "Erro")
else:
    st.info("Selecione ações na barra lateral.")

# Análise de Pair Trading
st.markdown("--- ")
st.subheader(f"Análise de Pair Trading")

if not st.session_state.dados_carregados:
    pass # Mensagem já exibida acima
elif len(acoes_selecionadas) == 2:
    if cotacoes_ok and serie_acao1 is not None and serie_acao2 is not None:
        st.markdown(f"**{acoes_selecionadas[0]} vs {acoes_selecionadas[1]}**")
        # Alinhar as séries temporais das ações
        common_index_stocks = serie_acao1.index.intersection(serie_acao2.index)
        if not common_index_stocks.empty:
            serie_acao1_aligned = serie_acao1.loc[common_index_stocks]
            serie_acao2_aligned = serie_acao2.loc[common_index_stocks]
            ratio = serie_acao1_aligned['Close'] / serie_acao2_aligned['Close']
            
            st.info("""
            **Nota sobre o cálculo do ratio:** Calculado com preços ajustados para desdobramentos desde 2016.
            """)
            
            # Evitar erro se ratio tiver NaNs ou for muito curto
            if ratio.dropna().shape[0] > 1:
                z_score = zscore(ratio.dropna())
                media_ratio = ratio.mean()
                desvio_padrao_ratio = ratio.std()
                ratio_atual = ratio.iloc[-1]
                z_score_atual = z_score[-1]
            else:
                z_score_atual = np.nan
                media_ratio = np.nan
                desvio_padrao_ratio = np.nan
                ratio_atual = ratio.iloc[-1] if not ratio.empty else np.nan
                st.warning("Não há dados suficientes para calcular Z-Score.")

            col1, col2, col3 = st.columns(3)
            col1.metric("Ratio Atual", f"{ratio_atual:.4f}" if not np.isnan(ratio_atual) else "N/A")
            col2.metric("Z-Score Atual", f"{z_score_atual:.4f}" if not np.isnan(z_score_atual) else "N/A")
            
            # Tomada de decisão
            if not np.isnan(z_score_atual):
                if z_score_atual > limite_superior_zscore:
                    decisao = f"Vender {acoes_selecionadas[0]} / Comprar {acoes_selecionadas[1]}"
                elif z_score_atual < limite_inferior_zscore:
                    decisao = f"Comprar {acoes_selecionadas[0]} / Vender {acoes_selecionadas[1]}"
                else:
                    decisao = "Neutro"
            else:
                decisao = "Indefinido"
            col3.metric("Sinal", decisao)
            
            # Gráfico
            fig, ax1 = plt.subplots(figsize=(12, 6)) # Reduzido tamanho
            ax1.plot(ratio.index, ratio.values, label='Ratio', color='blue', linewidth=1.5)
            if not np.isnan(media_ratio):
                ax1.axhline(y=media_ratio, color='green', linestyle='-', label='Média', linewidth=1)
                ax1.axhline(y=media_ratio + limite_superior_zscore * desvio_padrao_ratio, color='red', linestyle='--', label=f'+{limite_superior_zscore:.1f}σ', linewidth=1)
                ax1.axhline(y=media_ratio + limite_inferior_zscore * desvio_padrao_ratio, color='red', linestyle='--', label=f'{limite_inferior_zscore:.1f}σ', linewidth=1)
            
            ax1.set_xlabel('Data')
            ax1.set_ylabel('Ratio', color='blue')
            ax1.tick_params(axis='y', labelcolor='blue')
            ax1.grid(True, axis='y', linestyle=':', alpha=0.6)

            # Eixo Y secundário para commodity
            ax2 = None # Inicializa ax2
            if serie_brent is not None:
                common_index_all = ratio.index.intersection(serie_brent.index)
                if not common_index_all.empty:
                    serie_brent_aligned = serie_brent.loc[common_index_all]
                    ax2 = ax1.twinx()
                    ax2.plot(serie_brent_aligned.index, serie_brent_aligned['Close'], color='orange', linestyle='-.', label=commodity_symbol, linewidth=1.5)
                    ax2.set_ylabel(f'{commodity_symbol} (USD)', color='orange')
                    ax2.tick_params(axis='y', labelcolor='orange')
            
            # Legendas combinadas
            lines1, labels1 = ax1.get_legend_handles_labels()
            if ax2:
                lines2, labels2 = ax2.get_legend_handles_labels()
                ax1.legend(lines1 + lines2, labels1 + labels2, loc='best')
            else:
                ax1.legend(lines1, labels1, loc='best')

            plt.title(f'Ratio ({acoes_selecionadas[0]}/{acoes_selecionadas[1]}) e {commodity_symbol} - {periodo_selecionado}', fontsize=14)
            ax1.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d'))
            plt.xticks(rotation=30, ha='right') # Adjusted rotation
            plt.tight_layout()
            st.pyplot(fig)
            
            # Tabela de dados
            with st.expander("Ver Dados Históricos", expanded=False):
                df_combinado_tabela = pd.DataFrame({
                    f"{acoes_selecionadas[0]}": serie_acao1_aligned['Close'],
                    f"{acoes_selecionadas[1]}": serie_acao2_aligned['Close'],
                    "Ratio": ratio,
                    "Z-Score": pd.Series(z_score, index=ratio.index) if not np.isnan(z_score_atual) else np.nan
                })
                if serie_brent is not None:
                     common_index_table = df_combinado_tabela.index.intersection(serie_brent.index)
                     if not common_index_table.empty:
                         df_combinado_tabela[f"{commodity_symbol}"] = serie_brent.loc[common_index_table, 'Close']
                
                st.dataframe(df_combinado_tabela.tail(10))
                csv = df_combinado_tabela.to_csv().encode('utf-8')
                st.download_button(
                    label="Download CSV",
                    data=csv,
                    file_name=f"pair_trading_{acoes_selecionadas[0]}_{acoes_selecionadas[1]}_{periodo_valor}.csv",
                    mime="text/csv",
                )
        else:
            st.error("Não foi possível alinhar os dados históricos das ações selecionadas.")
    elif not cotacoes_ok:
         st.warning("Análise não pode ser exibida devido a erro na obtenção das cotações atuais.")
    else:
        st.error("Não foi possível obter dados históricos. Verifique a seleção ou tente atualizar.")
elif len(acoes_selecionadas) != 2:
    st.info("Selecione duas ações na barra lateral para ver a análise e o simulador.")
else:
     st.info("📈 Por favor, clique no botão '🔄 Atualizar Dados' na barra lateral para carregar as informações.")

# --- Seção Simulador de Montagem/Desmontagem --- 
st.markdown("--- ")
st.subheader("Simulador de Montagem/Desmontagem de Operação")

# Define CSS para a seção do simulador
simulator_css = """
<style>
.simulator-section {
    background-color: #f0f2f6; /* Fundo cinza claro */
    padding: 20px;
    border-radius: 10px;
    border: 1px solid #d1d1d1;
    margin-top: 20px;
}

/* Estilo para inputs numéricos */
.simulator-section .stNumberInput input[type="number"] {
    background-color: #e8f0fe !important; /* Fundo azul bem claro */
    border: 1px solid #adc5e2 !important;
    border-radius: 4px;
}

/* Estilo para selectbox */
.simulator-section div[data-baseweb="select"] > div {
     background-color: #e8f0fe !important; /* Fundo azul bem claro */
     border: 1px solid #adc5e2 !important;
     border-radius: 4px;
}

/* Estilo para títulos H4 dentro da seção */
.simulator-section h4 {
    color: #0056b3; /* Azul mais escuro */
    margin-top: 15px;
    margin-bottom: 10px;
    border-bottom: 1px solid #d1d1d1;
    padding-bottom: 5px;
}

/* Estilo para labels dos inputs */
.simulator-section .stWidget label {
    font-weight: 500 !important;
    color: #333 !important;
    font-size: 0.95em !important;
}

/* Estilo para as métricas de resultado */
.simulator-section div[data-testid="stMetric"] {
     background-color: #ffffff;
     border: 1px solid #e6e6e6;
     padding: 10px 15px;
     border-radius: 5px;
     margin-bottom: 10px;
}
.simulator-section div[data-testid="stMetricLabel"] {
    font-size: 0.9em;
    color: #555;
}

/* Estilo para o resultado líquido final */
.simulator-section .final-result div[data-testid="stMetric"] {
    background-color: #d4edda; /* Fundo verde claro para sucesso */
    border-color: #c3e6cb;
}
.simulator-section .final-result div[data-testid="stMetricValue"] {
    color: #155724; /* Texto verde escuro */
}

/* Adiciona um pouco mais de espaço entre colunas de resultados */
.simulator-section .stMetric {
    margin-right: 5px; 
}

</style>
"""
st.markdown(simulator_css, unsafe_allow_html=True)

# Inicia o container da seção do simulador com a classe CSS
st.markdown('<div class="simulator-section">', unsafe_allow_html=True)

if not st.session_state.dados_carregados:
    st.info("Aguardando o carregamento dos dados...")
elif len(acoes_selecionadas) == 2 and cotacoes_ok and ratio_atual is not None and z_score_atual is not None and not np.isnan(ratio_atual) and not np.isnan(z_score_atual):
    acao1 = acoes_selecionadas[0]
    acao2 = acoes_selecionadas[1]
    preco_atual_acao1 = precos_atuais.get(acao1, 0)
    preco_atual_acao2 = precos_atuais.get(acao2, 0)

    st.write(f"**Par Selecionado:** {acao1} vs {acao2}")
    st.write(f"**Sinal Atual:** {decisao}")

    # Determinar qual ação comprar/vender baseado no sinal
    acao_comprar = None
    acao_vender = None
    if "Comprar" in decisao:
        acao_comprar = acao1 if f"Comprar {acao1}" in decisao else acao2
        acao_vender = acao2 if acao_comprar == acao1 else acao1
    elif "Vender" in decisao:
        acao_vender = acao1 if f"Vender {acao1}" in decisao else acao2
        acao_comprar = acao2 if acao_vender == acao1 else acao1
    
    if acao_comprar and acao_vender:
        st.write(f"➡️ **Ação a Comprar:** {acao_comprar}")
        st.write(f"⬅️ **Ação a Vender (Alugar):** {acao_vender}")
        preco_compra_atual = precos_atuais.get(acao_comprar, 0)
        preco_venda_atual = precos_atuais.get(acao_vender, 0)

        st.markdown("#### Entradas para Simulação")
        col_sim1, col_sim2 = st.columns(2)

        with col_sim1:
            st.write("**Montagem (Entrada)**")
            # Usar os preços atuais como default, mas permitir edição
            preco_entrada_compra = st.number_input(f"Preço Entrada {acao_comprar}", value=float(preco_compra_atual) if preco_compra_atual else 0.0, format="%.2f", key="preco_ent_compra")
            preco_entrada_venda = st.number_input(f"Preço Entrada {acao_vender}", value=float(preco_venda_atual) if preco_venda_atual else 0.0, format="%.2f", key="preco_ent_venda")
            # Input de quantidade baseado em uma das pontas
            acao_ref = st.selectbox("Ação de Referência para Quantidade", [acao_comprar, acao_vender], key="acao_ref")
            qtd_ref = st.number_input(f"Quantidade de {acao_ref}", min_value=100, step=100, value=1000, key="qtd_ref") # Default 1000
            
            # Calcular quantidade da outra ponta para equilíbrio financeiro
            vol_ref = qtd_ref * (preco_entrada_compra if acao_ref == acao_comprar else preco_entrada_venda)
            preco_outra = preco_entrada_venda if acao_ref == acao_comprar else preco_entrada_compra
            qtd_outra = 0
            if preco_outra > 0:
                qtd_outra = int(round(vol_ref / preco_outra / 100.0) * 100) # Arredonda para lote de 100
            
            qtd_compra = qtd_ref if acao_ref == acao_comprar else qtd_outra
            qtd_venda = qtd_ref if acao_ref == acao_vender else qtd_outra
            
            # Exibe quantidades calculadas (read-only style)
            st.markdown(f"<p style='margin-top: 10px;'>Quantidade Calculada {acao_comprar}: <strong style='color: #0056b3;'>{qtd_compra}</strong></p>", unsafe_allow_html=True)
            st.markdown(f"<p>Quantidade Calculada {acao_vender}: <strong style='color: #0056b3;'>{qtd_venda}</strong></p>", unsafe_allow_html=True)

        with col_sim2:
            st.write("**Desmontagem (Saída)**")
            preco_saida_compra = st.number_input(f"Preço Saída {acao_comprar}", value=preco_entrada_compra * 1.05, format="%.2f", key="preco_sai_compra") # Default +5%
            preco_saida_venda = st.number_input(f"Preço Saída {acao_vender}", value=preco_entrada_venda * 0.95, format="%.2f", key="preco_sai_venda") # Default -5%
            
            st.write("**Custos e Duração**")
            taxa_aluguel_aa = st.number_input(f"Taxa Aluguel Anual {acao_vender} (%)", min_value=0.0, value=5.0, step=0.1, format="%.2f", key="taxa_aluguel")
            duracao_dias = st.number_input("Duração Estimada da Operação (dias)", min_value=1, value=30, step=1, key="duracao")
            custo_corretagem = st.number_input("Custo Corretagem Total (Entrada+Saída)", min_value=0.0, value=10.0, step=0.5, format="%.2f", key="corretagem") # Default 10
            custo_taxas_b3 = st.number_input("Custo Taxas B3 Total (Entrada+Saída)", min_value=0.0, value=5.0, step=0.1, format="%.2f", key="taxas_b3") # Default 5

        st.markdown("#### Resultados da Simulação")
        
        # Cálculos
        vol_compra_entrada = qtd_compra * preco_entrada_compra
        vol_venda_entrada = qtd_venda * preco_entrada_venda
        saldo_entrada = vol_venda_entrada - vol_compra_entrada
        
        vol_compra_saida = qtd_compra * preco_saida_compra
        vol_venda_saida = qtd_venda * preco_saida_venda
        
        resultado_compra = vol_compra_saida - vol_compra_entrada
        resultado_venda = vol_venda_entrada - vol_venda_saida # Venda: ganha na queda
        resultado_bruto = resultado_compra + resultado_venda
        
        # Custo Aluguel
        custo_aluguel_total = 0
        if vol_venda_entrada > 0 and taxa_aluguel_aa > 0 and duracao_dias > 0:
            taxa_aluguel_diaria = (taxa_aluguel_aa / 100.0) / 365.0 # Use float division
            custo_aluguel_total = vol_venda_entrada * taxa_aluguel_diaria * duracao_dias
            
        custo_operacional_total = custo_corretagem + custo_taxas_b3
        resultado_liquido = resultado_bruto - custo_aluguel_total - custo_operacional_total
        
        # Exibição dos Resultados
        res_col1, res_col2, res_col3 = st.columns(3)
        with res_col1:
            st.metric("Volume Compra (Entrada)", f"R$ {vol_compra_entrada:,.2f}")
            st.metric("Volume Venda (Entrada)", f"R$ {vol_venda_entrada:,.2f}")
            st.metric("Saldo Financeiro (Entrada)", f"R$ {saldo_entrada:,.2f}")
        with res_col2:
            st.metric("Custo Total Aluguel", f"R$ {custo_aluguel_total:,.2f}")
            st.metric("Custo Operacional Total", f"R$ {custo_operacional_total:,.2f}")
            st.metric("Resultado Bruto", f"R$ {resultado_bruto:,.2f}")
        with res_col3:
             # Aplica a classe CSS para o resultado final
             st.markdown('<div class="final-result">', unsafe_allow_html=True)
             st.metric("**Resultado Líquido**", f"**R$ {resultado_liquido:,.2f}**")
             # Calcular % de lucro/prejuízo sobre o maior volume (aproximação do capital)
             capital_aprox = max(vol_compra_entrada, vol_venda_entrada)
             if capital_aprox > 0:
                 perc_liquido = (resultado_liquido / capital_aprox) * 100
                 st.metric("Resultado Líquido (%)", f"{perc_liquido:.2f}%")
             else:
                 st.metric("Resultado Líquido (%)", "N/A")
             st.markdown('</div>', unsafe_allow_html=True)

    else:
        st.info("Aguardando sinal de Compra ou Venda para iniciar a simulação.")

elif not st.session_state.dados_carregados:
    pass # Mensagem já exibida
elif len(acoes_selecionadas) != 2:
    st.info("Selecione duas ações na barra lateral para ver a análise e o simulador.")
else:
    st.warning("Não foi possível obter as cotações ou dados históricos. Clique em '🔄 Atualizar Dados' ou tente mais tarde.")

# Fecha o container da seção do simulador
st.markdown('</div>', unsafe_allow_html=True)

# Informações adicionais
st.sidebar.markdown("---")
st.sidebar.subheader("Sobre")
st.sidebar.info("""
Este dashboard permite analisar estratégias de pair trading entre ações de bancos e Petrobras da Bovespa, 
incluindo a cotação do petróleo Brent como referência adicional e um simulador de operações.
""")

