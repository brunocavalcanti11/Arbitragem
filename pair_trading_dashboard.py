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
    st.cache_data.clear()
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

# --- Lógica Principal --- 

# Inicializa variáveis para evitar erros se os dados não forem carregados
decisao = "Aguardando dados"
ratio_atual = None
z_score_atual = None

# Exibir cotações atuais
if acoes_selecionadas:
    st.subheader("Cotações Atuais")
    
    # Criar colunas para exibir as cotações
    cols = st.columns(len(acoes_selecionadas) + 1)  # +1 para a commodity
    
    # Exibir cotações das ações selecionadas
    cotacoes_ok = True
    precos_atuais = {}
    for i, acao in enumerate(acoes_selecionadas):
        preco = obter_cotacao(acao)
        if preco is None:
            cotacoes_ok = False
            cols[i].metric(label=acao, value="Erro")
        else:
            precos_atuais[acao] = preco
            cols[i].metric(label=acao, value=f"R$ {preco:.2f}")
    
    # Exibir cotação da commodity
    commodity_preco = obter_cotacao(commodity_symbol)
    if commodity_preco is None:
        # Não impede a análise principal se a commodity falhar
        cols[-1].metric(label=f"{commodity_symbol}", value="Erro")
    else:
        cols[-1].metric(label=f"{commodity_symbol}", value=f"US$ {commodity_preco:.2f}")

# Análise de Pair Trading
if len(acoes_selecionadas) == 2 and cotacoes_ok:
    st.subheader(f"Análise de Pair Trading: {acoes_selecionadas[0]} vs {acoes_selecionadas[1]}")
    
    # Obter séries históricas
    serie_acao1 = obter_serie_historica(acoes_selecionadas[0], periodo=periodo_valor)
    serie_acao2 = obter_serie_historica(acoes_selecionadas[1], periodo=periodo_valor)
    serie_brent = obter_serie_historica(commodity_symbol, periodo=periodo_valor)
    
    if serie_acao1 is not None and serie_acao2 is not None:
        # Alinhar as séries temporais das ações
        common_index_stocks = serie_acao1.index.intersection(serie_acao2.index)
        serie_acao1_aligned = serie_acao1.loc[common_index_stocks]
        serie_acao2_aligned = serie_acao2.loc[common_index_stocks]

        if not common_index_stocks.empty:
            # Calcular o ratio entre as ações usando preços ajustados para desdobramentos
            ratio = serie_acao1_aligned['Close'] / serie_acao2_aligned['Close']
            
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
            ratio_atual = ratio.iloc[-1]
            z_score_atual = z_score[-1]
            col1, col2, col3 = st.columns(3)
            col1.metric("Ratio Atual", f"{ratio_atual:.4f}")
            col2.metric("Z-Score Atual", f"{z_score_atual:.4f}")
            
            # Tomada de decisão com base nos limites do z-score
            if z_score_atual > limite_superior_zscore:
                decisao = f"Vender {acoes_selecionadas[0]} / Comprar {acoes_selecionadas[1]}"
            elif z_score_atual < limite_inferior_zscore:
                decisao = f"Comprar {acoes_selecionadas[0]} / Vender {acoes_selecionadas[1]}"
            else:
                decisao = "Neutro"
            
            col3.metric("Sinal", decisao)
            
            # Criar figura para o gráfico
            fig, ax1 = plt.subplots(figsize=(12, 8))
            
            # Plotar o ratio
            ax1.plot(ratio.index, ratio.values, label='Ratio', color='blue')
            ax1.axhline(y=media_ratio, color='green', linestyle='-', label='Média')
            ax1.axhline(y=media_ratio + limite_superior_zscore * desvio_padrao_ratio, color='red', linestyle='--', 
                       label=f'+{limite_superior_zscore:.1f} Desvios Padrões')
            ax1.axhline(y=media_ratio + limite_inferior_zscore * desvio_padrao_ratio, color='red', linestyle='--', # Use + limite_inferior which is negative
                       label=f'{limite_inferior_zscore:.1f} Desvios Padrões')
            
            # Configurar eixo Y primário (ratio)
            ax1.set_xlabel('Data')
            ax1.set_ylabel('Ratio', color='blue')
            ax1.tick_params(axis='y', labelcolor='blue')
            
            # Criar eixo Y secundário para a commodity (se disponível)
            if serie_brent is not None:
                # Alinhar commodity com ratio
                common_index_all = ratio.index.intersection(serie_brent.index)
                serie_brent_aligned = serie_brent.loc[common_index_all]
                if not common_index_all.empty:
                    ax2 = ax1.twinx()
                    ax2.plot(serie_brent_aligned.index, serie_brent_aligned['Close'], color='orange', linestyle='-.', label=commodity_symbol)
                    ax2.set_ylabel(f'Preço de {commodity_symbol} (USD)', color='orange')
                    ax2.tick_params(axis='y', labelcolor='orange')
                    # Combinar legendas
                    lines1, labels1 = ax1.get_legend_handles_labels()
                    lines2, labels2 = ax2.get_legend_handles_labels()
                    ax1.legend(lines1 + lines2, labels1 + labels2, loc='upper left')
                else:
                    ax1.legend(loc='upper left') # Legenda só do ratio
            else:
                 ax1.legend(loc='upper left') # Legenda só do ratio

            # Configurar título e legenda
            plt.title(f'Ratio entre {acoes_selecionadas[0]} e {acoes_selecionadas[1]} com {commodity_symbol} - {periodo_selecionado}')
            
            # Formatar datas no eixo X
            ax1.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d'))
            plt.xticks(rotation=45)
            
            # Ajustar layout
            plt.tight_layout()
            
            # Exibir o gráfico no Streamlit
            st.pyplot(fig)
            
            # Exibir tabela de dados
            st.subheader("Dados Históricos")
            
            # Criar DataFrame combinado para tabela (pode usar índices diferentes do gráfico se a commodity falhou)
            df_combinado_tabela = pd.DataFrame({
                f"{acoes_selecionadas[0]} (Fechamento)": serie_acao1_aligned['Close'],
                f"{acoes_selecionadas[1]} (Fechamento)": serie_acao2_aligned['Close'],
                "Ratio": ratio,
                "Z-Score": pd.Series(z_score, index=ratio.index)
            })
            # Adicionar commodity se disponível
            if serie_brent is not None:
                 common_index_table = df_combinado_tabela.index.intersection(serie_brent.index)
                 if not common_index_table.empty:
                     df_combinado_tabela[f"{commodity_symbol} (USD)"] = serie_brent.loc[common_index_table, 'Close']
            
            # Exibir os últimos 10 registros
            st.dataframe(df_combinado_tabela.tail(10))
            
            # Opção para download dos dados
            csv = df_combinado_tabela.to_csv().encode('utf-8')
            st.download_button(
                label="Download dos dados em CSV",
                data=csv,
                file_name=f"pair_trading_{acoes_selecionadas[0]}_{acoes_selecionadas[1]}_{periodo_valor}.csv",
                mime="text/csv",
            )
        else:
            st.error("Não foi possível alinhar os dados históricos das ações selecionadas.")
    elif not cotacoes_ok:
         st.warning("Análise de Pair Trading não pode ser exibida devido a erro na obtenção das cotações atuais.")
    else:
        st.error("Não foi possível obter os dados históricos para as ações selecionadas.")

# --- Seção Simulador de Montagem/Desmontagem --- 
st.markdown("--- ")
st.subheader("Simulador de Montagem/Desmontagem de Operação")

if len(acoes_selecionadas) == 2 and cotacoes_ok and ratio_atual is not None and z_score_atual is not None:
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
            preco_entrada_compra = st.number_input(f"Preço Entrada {acao_comprar}", value=float(preco_compra_atual) if preco_compra_atual else 0.0, format="%.2f")
            preco_entrada_venda = st.number_input(f"Preço Entrada {acao_vender}", value=float(preco_venda_atual) if preco_venda_atual else 0.0, format="%.2f")
            # Input de quantidade baseado em uma das pontas
            acao_ref = st.selectbox("Ação de Referência para Quantidade", [acao_comprar, acao_vender])
            qtd_ref = st.number_input(f"Quantidade de {acao_ref}", min_value=100, step=100, value=100)
            
            # Calcular quantidade da outra ponta para equilíbrio financeiro
            vol_ref = qtd_ref * (preco_entrada_compra if acao_ref == acao_comprar else preco_entrada_venda)
            preco_outra = preco_entrada_venda if acao_ref == acao_comprar else preco_entrada_compra
            qtd_outra = 0
            if preco_outra > 0:
                qtd_outra = int(round(vol_ref / preco_outra / 100.0) * 100) # Arredonda para lote de 100
            
            qtd_compra = qtd_ref if acao_ref == acao_comprar else qtd_outra
            qtd_venda = qtd_ref if acao_ref == acao_vender else qtd_outra
            
            st.write(f"Quantidade Calculada {acao_comprar}: {qtd_compra}")
            st.write(f"Quantidade Calculada {acao_vender}: {qtd_venda}")

        with col_sim2:
            st.write("**Desmontagem (Saída)**")
            preco_saida_compra = st.number_input(f"Preço Saída {acao_comprar}", value=0.0, format="%.2f")
            preco_saida_venda = st.number_input(f"Preço Saída {acao_vender}", value=0.0, format="%.2f")
            
            st.write("**Custos e Duração**")
            taxa_aluguel_aa = st.number_input(f"Taxa Aluguel Anual {acao_vender} (%)", min_value=0.0, value=5.0, step=0.1, format="%.2f")
            duracao_dias = st.number_input("Duração Estimada da Operação (dias)", min_value=1, value=30, step=1)
            custo_corretagem = st.number_input("Custo Corretagem Total (Entrada+Saída)", min_value=0.0, value=0.0, step=0.5, format="%.2f")
            custo_taxas_b3 = st.number_input("Custo Taxas B3 Total (Entrada+Saída)", min_value=0.0, value=0.0, step=0.1, format="%.2f")

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
            taxa_aluguel_diaria = (taxa_aluguel_aa / 100) / 365
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
             st.metric("**Resultado Líquido**", f"**R$ {resultado_liquido:,.2f}**")
             # Calcular % de lucro/prejuízo sobre o maior volume (aproximação do capital)
             capital_aprox = max(vol_compra_entrada, vol_venda_entrada)
             if capital_aprox > 0:
                 perc_liquido = (resultado_liquido / capital_aprox) * 100
                 st.metric("Resultado Líquido (%)", f"{perc_liquido:.2f}%")
             else:
                 st.metric("Resultado Líquido (%)", "N/A")

    else:
        st.info("Aguardando sinal de Compra ou Venda para iniciar a simulação.")

elif len(acoes_selecionadas) != 2:
    st.info("Selecione duas ações na barra lateral para ver a análise e o simulador.")
else:
    st.warning("Não foi possível obter as cotações atuais. Clique em 'Atualizar Dados' ou tente mais tarde.")

# Informações adicionais
st.sidebar.markdown("---")
st.sidebar.subheader("Sobre")
st.sidebar.info("""
Este dashboard permite analisar estratégias de pair trading entre ações de bancos e Petrobras da Bovespa, 
incluindo a cotação do petróleo Brent como referência adicional e um simulador de operações.
""")

