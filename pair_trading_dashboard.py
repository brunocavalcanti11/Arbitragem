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

/* Estilo para linhas de detalhes da operação (NOVO LAYOUT) */
.op-line {
    display: grid;
    grid-template-columns: 1fr 1.5fr 1fr 1.5fr; /* Colunas para Ação, Cotação, Qtd, Volume */
    gap: 15px;
    align-items: center;
    padding: 8px 0;
    border-bottom: 1px dashed #e0e0e0;
    font-size: 0.95em;
}
.op-line strong {
    color: #0056b3;
    font-weight: 600;
}
.op-line span {
    text-align: right;
}
.op-line .label {
    text-align: left;
    font-weight: 500;
    color: #333;
}

</style>
"""
st.markdown(simulator_css, unsafe_allow_html=True)

# Inicia o container da seção do simulador com a classe CSS
st.markdown('<div class="simulator-section">', unsafe_allow_html=True)

if not st.session_state.dados_carregados:
    st.info("Aguardando o carregamento dos dados...")
elif len(acoes_selecionadas) == 2 and cotacoes_ok and ratio_atual is not None and z_score_atual is not None and not np.isnan(ratio_atual) and not np.isnan(z_score_atual):
    # Garante que temos os nomes das ações selecionadas
    acao1_nome = acoes_selecionadas[0]
    acao2_nome = acoes_selecionadas[1]
    preco_atual_acao1 = precos_atuais.get(acao1_nome, 0)
    preco_atual_acao2 = precos_atuais.get(acao2_nome, 0)

    st.write(f"**Par Selecionado:** {acao1_nome} vs {acao2_nome}")
    st.write(f"**Sinal Atual:** {decisao}")

    # Determinar qual ação comprar/vender baseado no sinal
    acao_comprar_nome = None
    acao_vender_nome = None
    if "Comprar" in decisao:
        acao_comprar_nome = acao1_nome if f"Comprar {acao1_nome}" in decisao else acao2_nome
        acao_vender_nome = acao2_nome if acao_comprar_nome == acao1_nome else acao1_nome
    elif "Vender" in decisao:
        acao_vender_nome = acao1_nome if f"Vender {acao1_nome}" in decisao else acao2_nome
        acao_comprar_nome = acao2_nome if acao_vender_nome == acao1_nome else acao1_nome
    
    if acao_comprar_nome and acao_vender_nome:
        st.write(f"➡️ **Ação Sugerida a Comprar:** {acao_comprar_nome}")
        st.write(f"⬅️ **Ação Sugerida a Vender (Alugar):** {acao_vender_nome}")
        preco_compra_sugerido = precos_atuais.get(acao_comprar_nome, 0)
        preco_venda_sugerido = precos_atuais.get(acao_vender_nome, 0)

        st.markdown("#### Entradas para Simulação")
        col_sim_in1, col_sim_in2 = st.columns(2)

        with col_sim_in1:
            st.write("**Preços e Quantidade de Entrada**")
            preco_entrada_acao1 = st.number_input(f"Preço Entrada {acao1_nome}", value=float(preco_atual_acao1) if preco_atual_acao1 else 0.0, format="%.2f", key="preco_ent_a1")
            preco_entrada_acao2 = st.number_input(f"Preço Entrada {acao2_nome}", value=float(preco_atual_acao2) if preco_atual_acao2 else 0.0, format="%.2f", key="preco_ent_a2")
            
            acao_ref = st.selectbox("Ação de Referência (Qtd)", [acao1_nome, acao2_nome], key="acao_ref")
            qtd_ref = st.number_input(f"Quantidade {acao_ref}", min_value=100, step=100, value=1000, key="qtd_ref") # Default 1000
            
            # Calcular quantidade da outra ponta para equilíbrio financeiro
            preco_ref = preco_entrada_acao1 if acao_ref == acao1_nome else preco_entrada_acao2
            vol_ref = qtd_ref * preco_ref
            preco_outra = preco_entrada_acao2 if acao_ref == acao1_nome else preco_entrada_acao1
            qtd_outra = 0
            if preco_outra > 0:
                qtd_outra = int(round(vol_ref / preco_outra / 100.0) * 100) # Arredonda para lote de 100
            
            qtd_acao1 = qtd_ref if acao_ref == acao1_nome else qtd_outra
            qtd_acao2 = qtd_ref if acao_ref == acao2_nome else qtd_outra
            
            # Exibe quantidades calculadas (read-only style)
            st.markdown(f"<p style='margin-top: 10px; font-size: 0.9em;'>Qtd. Calculada {acao1_nome}: <strong style='color: #0056b3;'>{qtd_acao1}</strong></p>", unsafe_allow_html=True)
            st.markdown(f"<p style='font-size: 0.9em;'>Qtd. Calculada {acao2_nome}: <strong style='color: #0056b3;'>{qtd_acao2}</strong></p>", unsafe_allow_html=True)

        with col_sim_in2:
            st.write("**Preços de Saída**")
            preco_saida_acao1 = st.number_input(f"Preço Saída {acao1_nome}", value=preco_entrada_acao1 * 1.02, format="%.2f", key="preco_sai_a1") # Default +2%
            preco_saida_acao2 = st.number_input(f"Preço Saída {acao2_nome}", value=preco_entrada_acao2 * 0.98, format="%.2f", key="preco_sai_a2") # Default -2%
            
            st.write("**Custos e Duração**")
            acao_vendida_simulacao = acao_vender_nome # Assume a sugestão
            taxa_aluguel_aa = st.number_input(f"Taxa Aluguel Anual {acao_vendida_simulacao} (%)", min_value=0.0, value=5.0, step=0.1, format="%.2f", key="taxa_aluguel")
            duracao_dias = st.number_input("Duração Estimada (dias)", min_value=1, value=30, step=1, key="duracao")
            custo_corretagem = st.number_input("Corretagem Total (Entrada+Saída)", min_value=0.0, value=10.0, step=0.5, format="%.2f", key="corretagem") # Default 10
            custo_taxas_b3 = st.number_input("Taxas B3 Total (Entrada+Saída)", min_value=0.0, value=5.0, step=0.1, format="%.2f", key="taxas_b3") # Default 5

        st.markdown("#### Resultados da Simulação")
        
        # Cálculos de Volume
        vol_entrada_acao1 = qtd_acao1 * preco_entrada_acao1
        vol_entrada_acao2 = qtd_acao2 * preco_entrada_acao2
        vol_saida_acao1 = qtd_acao1 * preco_saida_acao1
        vol_saida_acao2 = qtd_acao2 * preco_saida_acao2

        # Cálculos de Ratio e Spread (Ação 1 / Ação 2)
        ratio_entrada = preco_entrada_acao1 / preco_entrada_acao2 if preco_entrada_acao2 != 0 else np.nan
        spread_entrada = preco_entrada_acao1 - preco_entrada_acao2
        ratio_saida = preco_saida_acao1 / preco_saida_acao2 if preco_saida_acao2 != 0 else np.nan
        spread_saida = preco_saida_acao1 - preco_saida_acao2

        # Cálculos de Resultado
        resultado_acao1 = (preco_saida_acao1 - preco_entrada_acao1) * qtd_acao1
        resultado_acao2 = (preco_saida_acao2 - preco_entrada_acao2) * qtd_acao2
        
        # Ajusta resultado baseado na direção (compra/venda sugerida pelo sinal)
        if acao_comprar_nome == acao1_nome:
            resultado_bruto = resultado_acao1 - resultado_acao2 # Compra A1, Vende A2
        else:
            resultado_bruto = resultado_acao2 - resultado_acao1 # Compra A2, Vende A1

        # Custo Aluguel
        custo_aluguel_total = 0
        qtd_vendida_sim = qtd_acao1 if acao_vender_nome == acao1_nome else qtd_acao2
        preco_entrada_vendida_sim = preco_entrada_acao1 if acao_vender_nome == acao1_nome else preco_entrada_acao2
        vol_vendido_entrada = qtd_vendida_sim * preco_entrada_vendida_sim
        if vol_vendido_entrada > 0 and taxa_aluguel_aa > 0 and duracao_dias > 0:
            taxa_aluguel_diaria = (taxa_aluguel_aa / 100.0) / 365.0
            custo_aluguel_total = vol_vendido_entrada * taxa_aluguel_diaria * duracao_dias
            
        custo_operacional_total = custo_corretagem + custo_taxas_b3
        resultado_liquido = resultado_bruto - custo_aluguel_total - custo_operacional_total
        
        # Exibição dos Resultados Reorganizada
        st.markdown("**Montagem (Entrada)**")
        st.markdown(f"""
        <div class="op-line">
            <span class="label"><strong>{acao1_nome}</strong></span>
            <span>R$ {preco_entrada_acao1:,.2f}</span>
            <span class="label">Qtd: {qtd_acao1}</span>
            <span>R$ {vol_entrada_acao1:,.2f}</span>
        </div>
        <div class="op-line">
            <span class="label"><strong>{acao2_nome}</strong></span>
            <span>R$ {preco_entrada_acao2:,.2f}</span>
            <span class="label">Qtd: {qtd_acao2}</span>
            <span>R$ {vol_entrada_acao2:,.2f}</span>
        </div>
        """, unsafe_allow_html=True)
        col_ratio_sp_ent1, col_ratio_sp_ent2 = st.columns(2)
        col_ratio_sp_ent1.metric("Ratio Entrada (A1/A2)", f"{ratio_entrada:.4f}" if not np.isnan(ratio_entrada) else "N/A")
        col_ratio_sp_ent2.metric("Spread Entrada (A1-A2)", f"R$ {spread_entrada:,.2f}")

        st.markdown("**Desmontagem (Saída)**")
        st.markdown(f"""
        <div class="op-line">
            <span class="label"><strong>{acao1_nome}</strong></span>
            <span>R$ {preco_saida_acao1:,.2f}</span>
            <span class="label">Qtd: {qtd_acao1}</span>
            <span>R$ {vol_saida_acao1:,.2f}</span>
        </div>
        <div class="op-line">
            <span class="label"><strong>{acao2_nome}</strong></span>
            <span>R$ {preco_saida_acao2:,.2f}</span>
            <span class="label">Qtd: {qtd_acao2}</span>
            <span>R$ {vol_saida_acao2:,.2f}</span>
        </div>
        """, unsafe_allow_html=True)
        col_ratio_sp_sai1, col_ratio_sp_sai2 = st.columns(2)
        col_ratio_sp_sai1.metric("Ratio Saída (A1/A2)", f"{ratio_saida:.4f}" if not np.isnan(ratio_saida) else "N/A")
        col_ratio_sp_sai2.metric("Spread Saída (A1-A2)", f"R$ {spread_saida:,.2f}")

        st.markdown("**Custos e Resultado**")
        res_col1, res_col2, res_col3 = st.columns(3)
        with res_col1:
            st.metric("Custo Total Aluguel", f"R$ {custo_aluguel_total:,.2f}")
        with res_col2:
            st.metric("Custo Operacional Total", f"R$ {custo_operacional_total:,.2f}")
        with res_col3:
            st.metric("Resultado Bruto", f"R$ {resultado_bruto:,.2f}")

        # Resultado Líquido Final Destacado
        st.markdown('<div class="final-result">', unsafe_allow_html=True)
        res_liq_col1, res_liq_col2 = st.columns(2)
        res_liq_col1.metric("**Resultado Líquido**", f"**R$ {resultado_liquido:,.2f}**")
        # Calcular % de lucro/prejuízo sobre o maior volume (aproximação do capital)
        capital_aprox = max(vol_entrada_acao1, vol_entrada_acao2)
        if capital_aprox > 0:
            perc_liquido = (resultado_liquido / capital_aprox) * 100
            res_liq_col2.metric("Resultado Líquido (%)", f"{perc_liquido:.2f}%")
        else:
            res_liq_col2.metric("Resultado Líquido (%)", "N/A")
        st.markdown('</div>', unsafe_allow_html=True)

    else:
        st.info("Aguardando sinal de Compra ou Venda válido para iniciar a simulação.")

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

