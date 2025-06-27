import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime
import os

# Configuração da página
st.set_page_config(page_title="Dashboard de Agentes Biológicos", layout="wide")
st.title("Dashboard de Visualização - Agentes Biológicos")

# Nome do arquivo que deve estar no repositório
ARQUIVO_DADOS = "Base_insumos_biológicos_correto.xlsx"

# Verificar se o arquivo existe e carregar automaticamente
@st.cache_data
def carregar_dados():
    """Carrega dados automaticamente do arquivo Excel"""
    if os.path.exists(ARQUIVO_DADOS):
        try:
            df = pd.read_excel(ARQUIVO_DADOS)
            return df, None
        except Exception as e:
            return None, f"Erro ao ler o arquivo: {str(e)}"
    else:
        return None, f"Arquivo '{ARQUIVO_DADOS}' não encontrado no repositório"

# Carregar dados automaticamente
st.info("🔄 Carregando dados automaticamente...")
df_raw, erro = carregar_dados()

if erro:
    st.error(f"❌ {erro}")
    st.info("📋 Certifique-se de que o arquivo 'Base_insumos_biológicos_correto.xlsx' está no repositório")
    st.stop()

if df_raw is not None:
    try:
        df = df_raw.copy()
        
        # Verificar se as colunas necessárias existem
        colunas_necessarias = ['data', 'estado', 'cidade', 'agente biológico', 'preço']
        colunas_faltando = [col for col in colunas_necessarias if col not in df.columns]

        if colunas_faltando:
            st.error(f"❌ Colunas faltando no arquivo: {', '.join(colunas_faltando)}")
            st.info("📋 Colunas necessárias: data, estado, cidade, agente biológico, preço")
            st.info("📋 Colunas encontradas: " + ", ".join(df.columns.tolist()))
            st.stop()

        # Limpar dados e tratar valores nulos
        df = df.dropna(subset=colunas_necessarias)

        # Converter a coluna de data para datetime
        try:
            df['data'] = pd.to_datetime(df['data'])
        except:
            st.error("❌ Erro ao converter a coluna 'data'. Verifique se o formato está correto.")
            st.stop()

        # Extrair componentes de data
        df['ano'] = df['data'].dt.year
        df['mes'] = df['data'].dt.month
        df['dia'] = df['data'].dt.day

        # Padronizar nomes das colunas para facilitar o uso
        df = df.rename(columns={
            'agente biológico': 'agente_biologico',
            'preço': 'preco'
        })

        # Verificar se a coluna preço é numérica
        try:
            df['preco'] = pd.to_numeric(df['preco'], errors='coerce')
            # Remover linhas onde preço não pôde ser convertido
            df = df.dropna(subset=['preco'])
        except:
            st.error("❌ Erro ao converter a coluna 'preço' para valores numéricos.")
            st.stop()

        # Função para criar faixas de preço automaticamente
        def criar_faixas_preco(precos, agente):
            """
            Cria faixas de preço baseadas em gaps significativos entre valores.
            Para poucos dados, agrupa valores similares.
            Para muitos dados, usa detecção de gaps relativos.
            """
            if len(precos) <= 1:
                return [{"nome": "Faixa Única", "min": min(precos), "max": max(precos), "valores": precos}]

            # Ordenar preços
            precos_ordenados = sorted(precos)

            # Para poucos dados (≤ 10), usar abordagem mais simples
            if len(precos) <= 10:
                faixas = []
                valores_processados = set()

                for preco in precos_ordenados:
                    if preco in valores_processados:
                        continue

                    # Encontrar valores similares (dentro de 20% de diferença)
                    valores_similares = [p for p in precos if abs(p - preco) / preco <= 0.2]

                    if valores_similares:
                        faixas.append({
                            "nome": f"Faixa {len(faixas) + 1}",
                            "min": min(valores_similares),
                            "max": max(valores_similares),
                            "valores": valores_similares
                        })
                        valores_processados.update(valores_similares)

                return faixas

            # Para mais dados, usar detecção de gaps
            faixas = []
            faixa_atual = [precos_ordenados[0]]
            inicio_faixa = precos_ordenados[0]

            for i in range(1, len(precos_ordenados)):
                atual = precos_ordenados[i]
                anterior = precos_ordenados[i - 1]

                # Calcular gap relativo
                gap = (atual - anterior) / anterior if anterior > 0 else 0

                # Se gap > 100%, criar nova faixa
                if gap > 1.0:
                    # Finalizar faixa atual
                    faixas.append({
                        "nome": f"Faixa {len(faixas) + 1}",
                        "min": inicio_faixa,
                        "max": faixa_atual[-1],
                        "valores": faixa_atual.copy()
                    })

                    # Iniciar nova faixa
                    faixa_atual = [atual]
                    inicio_faixa = atual
                else:
                    faixa_atual.append(atual)

            # Adicionar última faixa
            if faixa_atual:
                faixas.append({
                    "nome": f"Faixa {len(faixas) + 1}",
                    "min": inicio_faixa,
                    "max": faixa_atual[-1],
                    "valores": faixa_atual.copy()
                })

            return faixas

        # Criar mapeamento de faixas de preço para cada agente biológico
        with st.spinner("Processando faixas de preço por agente biológico..."):
            faixas_por_agente = {}

            for agente in df['agente_biologico'].unique():
                precos_agente = df[df['agente_biologico'] == agente]['preco'].tolist()
                faixas = criar_faixas_preco(precos_agente, agente)

                # Adicionar informações de descrição para cada faixa
                for faixa in faixas:
                    if faixa['min'] == faixa['max']:
                        faixa['descricao'] = f"R$ {faixa['min']:.2f}"
                    else:
                        faixa['descricao'] = f"R$ {faixa['min']:.2f} - R$ {faixa['max']:.2f}"
                    faixa['label'] = f"{faixa['nome']} ({faixa['descricao']})"

                faixas_por_agente[agente] = faixas

        # Criar coluna de faixa de preço no dataframe
        def obter_faixa_preco(row):
            agente = row['agente_biologico']
            preco = row['preco']

            if agente in faixas_por_agente:
                for faixa in faixas_por_agente[agente]:
                    if faixa['min'] <= preco <= faixa['max']:
                        return faixa['nome']
            return "Sem Faixa"

        df['faixa_preco'] = df.apply(obter_faixa_preco, axis=1)

        # Adicionar contador de registros
        st.success(f"✅ Dados carregados automaticamente com sucesso!")
        st.info(f"📊 Base de dados contém {len(df)} registros no total")

        # Mostrar preview dos dados
        with st.expander("Visualizar dados carregados (primeiras 5 linhas)"):
            st.dataframe(df.head())

        # Mostrar informações sobre as faixas de preço criadas
        with st.expander("📊 Faixas de Preço por Agente Biológico"):
            st.markdown(
                "**As faixas foram criadas automaticamente baseadas na distribuição de preços de cada agente:**")

            for agente, faixas in faixas_por_agente.items():
                if len(faixas) > 1:  # Só mostrar agentes com múltiplas faixas
                    st.write(f"**{agente}:**")
                    for faixa in faixas:
                        count_registros = len(faixa['valores'])
                        st.write(f"  • {faixa['label']} - {count_registros} registro(s)")
                    st.write("")

        # Função auxiliar para atualizar as opções de filtro
        def obter_opcoes_filtro(dataframe, coluna, incluir_todos=True, texto_todos="Todos"):
            opcoes = sorted(dataframe[coluna].unique())
            if incluir_todos:
                return [texto_todos] + list(opcoes)
            return list(opcoes)

        # Adicionar texto explicativo sobre os filtros
        with st.expander("Como usar os filtros (clique para expandir)"):
            st.markdown("""
            ### Como usar os filtros dinâmicos

            Esta plataforma usa **filtros dinâmicos**, o que significa:

            - Cada filtro é atualizado com base nas seleções anteriores
            - Apenas opções que retornarão resultados são mostradas
            - A ordem de seleção importa (de cima para baixo e da esquerda para a direita)

            **Exemplo**: Se você selecionar um estado específico, apenas as cidades desse estado estarão disponíveis no filtro de Cidade.

            Para reiniciar os filtros, use o botão "Resetar Todos os Filtros" ou selecione a opção "Todos"/"Todas" em cada filtro.
            """)

        # Criar filtros
        st.subheader("🔍 Filtros")

        # Começar com o dataframe completo
        df_temp = df.copy()

        # Primeira linha de filtros - Tempo
        col1, col2, col3 = st.columns(3)

        with col1:
            # Filtro de ano
            anos_disponiveis = obter_opcoes_filtro(df_temp, "ano")
            filtro_ano = st.selectbox("Ano", anos_disponiveis, key="ano")

            if filtro_ano != "Todos":
                df_temp = df_temp[df_temp["ano"] == filtro_ano]

        with col2:
            # Filtro de mês
            meses_disponiveis = obter_opcoes_filtro(df_temp, "mes")
            filtro_mes = st.selectbox("Mês", meses_disponiveis, key="mes")

            if filtro_mes != "Todos":
                df_temp = df_temp[df_temp["mes"] == filtro_mes]

        with col3:
            # Filtro de dia
            dias_disponiveis = obter_opcoes_filtro(df_temp, "dia")
            filtro_dia = st.selectbox("Dia", dias_disponiveis, key="dia")

            if filtro_dia != "Todos":
                df_temp = df_temp[df_temp["dia"] == filtro_dia]

        # Segunda linha de filtros - Localização e Agentes
        col1, col2, col3, col4, col5 = st.columns(5)

        with col1:
            # Opções de agrupamento focadas em agente biológico
            opcoes_agrupamento = ["agente_biologico", "estado", "cidade", "faixa_preco"]
            opcao_agrupamento = st.selectbox(
                "Agrupar Resultados Por",
                options=opcoes_agrupamento,
                index=0,  # Padrão: agente biológico
                format_func=lambda x: {
                    "agente_biologico": "Agente Biológico",
                    "estado": "Estado",
                    "cidade": "Cidade",
                    "faixa_preco": "Faixa de Preço"
                }[x],
                key="agrupar_por"
            )

        with col2:
            opcoes_estado = obter_opcoes_filtro(df_temp, "estado")
            filtro_estado = st.selectbox("Estado", opcoes_estado, key="estado")

            if filtro_estado != "Todos":
                df_temp = df_temp[df_temp["estado"] == filtro_estado]

        with col3:
            opcoes_cidade = obter_opcoes_filtro(df_temp, "cidade", texto_todos="Todas")
            filtro_cidade = st.selectbox("Cidade", opcoes_cidade, key="cidade")

            if filtro_cidade != "Todas":
                df_temp = df_temp[df_temp["cidade"] == filtro_cidade]

        with col4:
            opcoes_agente = obter_opcoes_filtro(df_temp, "agente_biologico", texto_todos="Todos")
            filtro_agente = st.selectbox("Agente Biológico", opcoes_agente, key="agente")

            if filtro_agente != "Todos":
                df_temp = df_temp[df_temp["agente_biologico"] == filtro_agente]

        with col5:
            # Filtro de faixa de preço - só aparece se um agente específico for selecionado
            if filtro_agente != "Todos" and filtro_agente in faixas_por_agente:
                faixas_disponiveis = faixas_por_agente[filtro_agente]
                if len(faixas_disponiveis) > 1:
                    opcoes_faixa = ["Todas"] + [faixa['label'] for faixa in faixas_disponiveis]
                    filtro_faixa = st.selectbox("Faixa de Preço", opcoes_faixa, key="faixa_preco")

                    if filtro_faixa != "Todas":
                        # Encontrar a faixa selecionada
                        faixa_selecionada = None
                        for faixa in faixas_disponiveis:
                            if faixa['label'] == filtro_faixa:
                                faixa_selecionada = faixa
                                break

                        if faixa_selecionada:
                            df_temp = df_temp[
                                (df_temp['preco'] >= faixa_selecionada['min']) &
                                (df_temp['preco'] <= faixa_selecionada['max'])
                                ]
                else:
                    st.write("🔘 Faixa Única")
            else:
                # Filtro geral de faixa quando nenhum agente específico está selecionado
                opcoes_faixa_geral = obter_opcoes_filtro(df_temp, "faixa_preco", texto_todos="Todas")
                if len(opcoes_faixa_geral) > 2:  # Mais que "Todas" + uma faixa
                    filtro_faixa_geral = st.selectbox("Faixa de Preço", opcoes_faixa_geral, key="faixa_geral")

                    if filtro_faixa_geral != "Todas":
                        df_temp = df_temp[df_temp["faixa_preco"] == filtro_faixa_geral]
                else:
                    st.write("🔘 Sem Múltiplas Faixas")

        # Dataframe final filtrado
        df_filtrado = df_temp

        # Contador de resultados atualizado
        st.info(f"Exibindo {len(df_filtrado)} registros de um total de {len(df)}")

        # Botão para resetar filtros
        if st.button("Resetar Todos os Filtros"):
            st.rerun()

        # Calcular estatísticas
        if not df_filtrado.empty:
            num_registros = len(df_filtrado)
            num_agentes = df_filtrado["agente_biologico"].nunique()
            num_estados = df_filtrado["estado"].nunique()
            num_cidades = df_filtrado["cidade"].nunique()
            preco_medio = df_filtrado["preco"].mean()
            preco_total = df_filtrado["preco"].sum()

            # Período de dados
            data_min = df_filtrado["data"].min()
            data_max = df_filtrado["data"].max()
        else:
            num_registros = num_agentes = num_estados = num_cidades = 0
            preco_medio = preco_total = 0
            data_min = data_max = None

        # Exibir estatísticas
        st.subheader("📈 Estatísticas")
        col1, col2, col3, col4, col5, col6 = st.columns(6)
        with col1:
            st.metric("Total de Registros", f"{num_registros}")
        with col2:
            st.metric("Agentes Biológicos", f"{num_agentes}")
        with col3:
            st.metric("Estados", f"{num_estados}")
        with col4:
            st.metric("Cidades", f"{num_cidades}")
        with col5:
            st.metric("Preço Médio", f"R$ {preco_medio:.2f}")
        with col6:
            st.metric("Valor Total", f"R$ {preco_total:.2f}")

        # Mostrar período dos dados se houver dados
        if data_min and data_max:
            st.info(f"Período dos dados: {data_min.strftime('%d/%m/%Y')} a {data_max.strftime('%d/%m/%Y')}")

        # Preparar dados para gráficos
        if not df_filtrado.empty:
            # **CORREÇÃO PRINCIPAL**: Modificar a lógica para permitir visualização mesmo com um único valor
            # Verificar quantos grupos únicos existem
            num_grupos_unicos = df_filtrado[opcao_agrupamento].nunique()

            if num_grupos_unicos >= 1:  # Mudança: >= 1 ao invés de > 1
                # Fazer agregação - contar ocorrências e calcular valores por grupo
                df_grafico = df_filtrado.groupby(opcao_agrupamento).agg({
                    'preco': ['mean', 'sum', 'count']
                }).reset_index()

                # Simplificar nomes das colunas
                df_grafico.columns = [opcao_agrupamento, 'preco_medio', 'preco_total', 'count']
                df_grafico = df_grafico.sort_values(by="preco_total", ascending=False)

                # Criar visualizações
                st.subheader("📊 Visualizações")

                # Limitar exibição se houver muitos grupos
                if len(df_grafico) > 15:
                    st.info(f"Exibindo os 15 principais itens por valor total de um total de {len(df_grafico)}.")
                    df_grafico_top = df_grafico.head(15)
                else:
                    df_grafico_top = df_grafico

                # **NOVA LÓGICA**: Adaptar visualizações para um ou múltiplos grupos
                grupo_nome = {
                    "agente_biologico": "Agente Biológico",
                    "estado": "Estado",
                    "cidade": "Cidade",
                    "faixa_preco": "Faixa de Preço"
                }[opcao_agrupamento]

                # Se há apenas um grupo, mostrar análise detalhada desse grupo
                if num_grupos_unicos == 1:
                    st.info(f"📊 Análise detalhada para: **{df_grafico_top.iloc[0][opcao_agrupamento]}**")

                    # Mostrar métricas específicas
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.metric("Valor Total", f"R$ {df_grafico_top.iloc[0]['preco_total']:.2f}")
                    with col2:
                        st.metric("Preço Médio", f"R$ {df_grafico_top.iloc[0]['preco_medio']:.2f}")
                    with col3:
                        st.metric("Quantidade de Registros", f"{df_grafico_top.iloc[0]['count']}")

                    # Para um único agente, mostrar distribuição por outras dimensões
                    st.subheader(f"📈 Análise Detalhada - {df_grafico_top.iloc[0][opcao_agrupamento]}")

                    # Análise por estado se não foi filtrado por estado
                    if filtro_estado == "Todos" and df_filtrado['estado'].nunique() > 1:
                        df_estados = df_filtrado.groupby('estado').agg({
                            'preco': ['mean', 'sum', 'count']
                        }).reset_index()
                        df_estados.columns = ['estado', 'preco_medio', 'preco_total', 'count']
                        df_estados = df_estados.sort_values(by="preco_total", ascending=False)

                        col1, col2 = st.columns(2)
                        with col1:
                            fig_estados = px.bar(
                                df_estados,
                                x='estado',
                                y='preco_total',
                                title=f"Valor Total por Estado - {df_grafico_top.iloc[0][opcao_agrupamento]}",
                                labels={'preco_total': 'Valor Total (R$)', 'estado': 'Estado'}
                            )
                            fig_estados.update_layout(height=400, template="plotly_white")
                            st.plotly_chart(fig_estados, use_container_width=True)

                        with col2:
                            fig_estados_pie = px.pie(
                                df_estados,
                                values='preco_total',
                                names='estado',
                                title=f"Distribuição por Estado - {df_grafico_top.iloc[0][opcao_agrupamento]}"
                            )
                            fig_estados_pie.update_layout(height=400)
                            st.plotly_chart(fig_estados_pie, use_container_width=True)

                    # Análise por cidade se não foi filtrado por cidade
                    elif filtro_cidade == "Todas" and df_filtrado['cidade'].nunique() > 1:
                        df_cidades = df_filtrado.groupby('cidade').agg({
                            'preco': ['mean', 'sum', 'count']
                        }).reset_index()
                        df_cidades.columns = ['cidade', 'preco_medio', 'preco_total', 'count']
                        df_cidades = df_cidades.sort_values(by="preco_total", ascending=False).head(10)

                        col1, col2 = st.columns(2)
                        with col1:
                            fig_cidades = px.bar(
                                df_cidades,
                                x='cidade',
                                y='preco_total',
                                title=f"Valor Total por Cidade - {df_grafico_top.iloc[0][opcao_agrupamento]}",
                                labels={'preco_total': 'Valor Total (R$)', 'cidade': 'Cidade'}
                            )
                            fig_cidades.update_layout(height=400, template="plotly_white", xaxis_tickangle=-45)
                            st.plotly_chart(fig_cidades, use_container_width=True)

                        with col2:
                            fig_cidades_pie = px.pie(
                                df_cidades,
                                values='preco_total',
                                names='cidade',
                                title=f"Distribuição por Cidade - {df_grafico_top.iloc[0][opcao_agrupamento]}"
                            )
                            fig_cidades_pie.update_layout(height=400)
                            st.plotly_chart(fig_cidades_pie, use_container_width=True)

                else:
                    # Lógica original para múltiplos grupos
                    col1, col2 = st.columns(2)

                    with col1:
                        # Gráfico de valor total
                        fig_valor = go.Figure()
                        fig_valor.add_trace(
                            go.Bar(
                                x=df_grafico_top[opcao_agrupamento],
                                y=df_grafico_top["preco_total"],
                                marker_color='rgb(41, 128, 185)',
                                name="Valor Total"
                            )
                        )

                        fig_valor.update_layout(
                            title=f"Valor Total por {grupo_nome}",
                            xaxis_title=grupo_nome,
                            yaxis_title="Valor Total (R$)",
                            height=400,
                            template="plotly_white",
                            xaxis_tickangle=-45
                        )

                        st.plotly_chart(fig_valor, use_container_width=True)

                    with col2:
                        # Gráfico de preço médio
                        fig_medio = go.Figure()
                        fig_medio.add_trace(
                            go.Bar(
                                x=df_grafico_top[opcao_agrupamento],
                                y=df_grafico_top["preco_medio"],
                                marker_color='rgb(39, 174, 96)',
                                name="Preço Médio"
                            )
                        )

                        fig_medio.update_layout(
                            title=f"Preço Médio por {grupo_nome}",
                            xaxis_title=grupo_nome,
                            yaxis_title="Preço Médio (R$)",
                            height=400,
                            template="plotly_white",
                            xaxis_tickangle=-45
                        )

                        st.plotly_chart(fig_medio, use_container_width=True)

                    # Terceira linha com gráficos de pizza
                    col1, col2 = st.columns(2)

                    with col1:
                        # Gráfico de pizza para valor total
                        fig_pie_valor = px.pie(
                            df_grafico_top,
                            values='preco_total',
                            names=opcao_agrupamento,
                            title=f"Distribuição de Valor Total por {grupo_nome}"
                        )
                        fig_pie_valor.update_traces(textposition='inside', textinfo='percent+label')
                        fig_pie_valor.update_layout(height=400)

                        st.plotly_chart(fig_pie_valor, use_container_width=True)

                    with col2:
                        # Gráfico de pizza para quantidade
                        fig_pie_count = px.pie(
                            df_grafico_top,
                            values='count',
                            names=opcao_agrupamento,
                            title=f"Distribuição de Quantidade por {grupo_nome}"
                        )
                        fig_pie_count.update_traces(textposition='inside', textinfo='percent+label')
                        fig_pie_count.update_layout(height=400)

                        st.plotly_chart(fig_pie_count, use_container_width=True)

                # Análise temporal (sempre mostrar se há dados suficientes)
                st.subheader("⏰ Análise Temporal")

                # Permitir escolha do período de agrupamento e métrica
                col1, col2 = st.columns([1, 1])
                with col1:
                    periodo = st.selectbox("Período", ["Mês", "Ano"], index=0)
                with col2:
                    metrica_temporal = st.selectbox("Métrica", ["Valor Total", "Preço Médio", "Quantidade"], index=0)

                # Preparar dados temporais
                df_tempo = df_filtrado.copy()

                # Criar coluna de período
                if periodo == "Mês":
                    df_tempo['periodo_str'] = df_tempo['data'].dt.strftime('%Y-%m')
                    df_tempo['periodo_dt'] = pd.to_datetime(df_tempo['periodo_str'] + '-01')
                    formato_data = '%b %Y'
                else:  # Ano
                    df_tempo['periodo_str'] = df_tempo['data'].dt.strftime('%Y')
                    df_tempo['periodo_dt'] = pd.to_datetime(df_tempo['periodo_str'] + '-01-01')
                    formato_data = '%Y'

                # Agrupar por período e agente biológico
                if metrica_temporal == "Valor Total":
                    df_tempo_grupo = df_tempo.groupby(['periodo_dt', 'periodo_str', 'agente_biologico'])[
                        'preco'].sum().reset_index()
                    y_column = 'preco'
                    y_label = "Valor Total (R$)"
                elif metrica_temporal == "Preço Médio":
                    df_tempo_grupo = df_tempo.groupby(['periodo_dt', 'periodo_str', 'agente_biologico'])[
                        'preco'].mean().reset_index()
                    y_column = 'preco'
                    y_label = "Preço Médio (R$)"
                else:  # Quantidade
                    df_tempo_grupo = df_tempo.groupby(
                        ['periodo_dt', 'periodo_str', 'agente_biologico']).size().reset_index(name='quantidade')
                    y_column = 'quantidade'
                    y_label = "Quantidade de Registros"

                if len(df_tempo_grupo) > 0:
                    # Criar gráfico de linha temporal
                    fig_tempo = px.line(
                        df_tempo_grupo,
                        x='periodo_dt',
                        y=y_column,
                        color='agente_biologico',
                        title=f"Evolução Temporal - {metrica_temporal} por Agente Biológico ({periodo})",
                        labels={
                            'periodo_dt': periodo,
                            y_column: y_label,
                            'agente_biologico': 'Agente Biológico'
                        },
                        markers=True
                    )

                    # Melhorar formatação do eixo X
                    fig_tempo.update_xaxes(
                        tickformat=formato_data,
                        dtick="M1" if periodo == "Mês" else "M12"
                    )

                    fig_tempo.update_layout(
                        height=500,
                        template="plotly_white",
                        legend=dict(
                            orientation="h",
                            yanchor="bottom",
                            y=1.02,
                            xanchor="right",
                            x=1
                        ),
                        xaxis_title=f"{periodo} (formato: {formato_data})",
                        yaxis_title=y_label
                    )

                    st.plotly_chart(fig_tempo, use_container_width=True)

        # Seção de dados detalhados - mover para posição mais visível
        st.subheader("📋 Dados Detalhados e Download")

        # Opção para download - sempre disponível quando há dados filtrados
        if not df_filtrado.empty:
            col1, col2 = st.columns([2, 1])

            with col1:
                st.info(f"📊 {len(df_filtrado)} registros disponíveis para download e visualização")

            with col2:
                # Preparar dados para download (todos os dados filtrados)
                df_download = df_filtrado.copy()
                df_download['data'] = df_download['data'].dt.strftime('%d/%m/%Y')
                df_download = df_download[['data', 'estado', 'cidade', 'agente_biologico', 'faixa_preco', 'preco']]
                df_download = df_download.rename(columns={
                    'agente_biologico': 'Agente Biológico',
                    'faixa_preco': 'Faixa de Preço',
                    'preco': 'Preço (R$)'
                })

                csv = df_download.to_csv(index=False)
                st.download_button(
                    label=f"📥 Download CSV ({len(df_download)} registros)",
                    data=csv,
                    file_name="agentes_biologicos_filtrados.csv",
                    mime="text/csv",
                    use_container_width=True
                )

        # Seção de dados detalhados
        st.sidebar.markdown("---")
        st.sidebar.subheader("Opções de Visualização")
        mostrar_dados = st.sidebar.checkbox("Mostrar Tabela de Dados", value=False)

        if mostrar_dados and not df_filtrado.empty:
            # Configurar número de linhas a exibir
            max_linhas = min(100, len(df_filtrado))
            # Corrigir o problema do slider quando min_value = max_value
            if max_linhas <= 10:
                num_linhas = max_linhas
                st.sidebar.info(f"Exibindo todas as {max_linhas} linhas disponíveis")
            else:
                num_linhas = st.sidebar.slider(
                    "Linhas na tabela",
                    min_value=10,
                    max_value=max_linhas,
                    value=min(50, max_linhas),
                    step=10
                )

            st.subheader("📋 Tabela de Dados")

            # Preparar dados para exibição
            df_display = df_filtrado.copy()
            df_display['data'] = df_display['data'].dt.strftime('%d/%m/%Y')
            df_display = df_display[['data', 'estado', 'cidade', 'agente_biologico', 'faixa_preco', 'preco']].head(
                num_linhas)
            df_display = df_display.rename(columns={
                'agente_biologico': 'Agente Biológico',
                'faixa_preco': 'Faixa de Preço',
                'preco': 'Preço (R$)'
            })

            st.dataframe(df_display, use_container_width=True)

            if len(df_filtrado) > num_linhas:
                st.info(f"Exibindo {num_linhas} de {len(df_filtrado)} linhas.")

            # Opção para download - sempre disponível quando há dados filtrados
            if len(df_filtrado) > 0:
                # Preparar dados para download (todos os dados filtrados, não apenas os exibidos)
                df_download = df_filtrado.copy()
                df_download['data'] = df_download['data'].dt.strftime('%d/%m/%Y')
                df_download = df_download[['data', 'estado', 'cidade', 'agente_biologico', 'faixa_preco', 'preco']]
                df_download = df_download.rename(columns={
                    'agente_biologico': 'Agente Biológico',
                    'faixa_preco': 'Faixa de Preço',
                    'preco': 'Preço (R$)'
                })

                csv = df_download.to_csv(index=False)
                st.download_button(
                    label=f"📥 Download dos Dados Filtrados (CSV) - {len(df_download)} registros",
                    data=csv,
                    file_name="agentes_biologicos_filtrados.csv",
                    mime="text/csv"
                )

        # Resumo estatístico adicional
        if st.sidebar.checkbox("Mostrar Resumo Estatístico"):
            st.subheader("📊 Resumo Estatístico Detalhado")

            col1, col2 = st.columns(2)

            with col1:
                st.write("**Top 10 Agentes Biológicos por Valor Total:**")
                top_agentes = df_filtrado.groupby('agente_biologico')['preco'].sum().sort_values(ascending=False).head(
                    10)
                for agente, valor in top_agentes.items():
                    st.write(f"• {agente}: R$ {valor:.2f}")

            with col2:
                st.write("**Top 10 Estados por Valor Total:**")
                top_estados = df_filtrado.groupby('estado')['preco'].sum().sort_values(ascending=False).head(10)
                for estado, valor in top_estados.items():
                    st.write(f"• {estado}: R$ {valor:.2f}")

    except Exception as e:
        st.error(f"❌ Erro ao processar o arquivo: {str(e)}")
        st.info("Verifique se o arquivo está no formato correto e contém as colunas necessárias.")

else:
    # Instruções quando nenhum arquivo foi carregado
    st.info("Faça upload de um arquivo Excel para começar a análise")

    st.markdown("""
    ### Formato do Arquivo

    O arquivo Excel deve conter as seguintes colunas:

    - **data**: Data no formato dd/mm/aaaa ou similar
    - **estado**: Estado (ex: SP, RJ, MG)
    - **cidade**: Nome da cidade
    - **agente biológico**: Nome do agente biológico
    - **preço**: Valor numérico do preço/custo

    ### Funcionalidades do Dashboard

    - **Filtros dinâmicos** por data, estado, cidade, agente biológico e faixa de preço
    - **Classificação automática de faixas de preço** baseada na distribuição de cada agente
    - Análises de valor: preço médio, valor total por categoria
    - Visualizações focadas em agentes biológicos
    - Análise temporal da evolução de preços e quantidades
    - Estatísticas detalhadas e resumos financeiros
    - Export dos dados filtrados em CSV
    - Gráficos interativos (barras, pizza, linha temporal)

    ### Sistema de Faixas de Preço

    O dashboard **automaticamente detecta** quando um agente biológico tem preços muito díspares e cria faixas inteligentes:

    - **Algoritmo adaptativo**: Identifica gaps superiores a 100% entre preços
    - **Faixas dinâmicas**: Cada agente tem suas próprias faixas baseadas em sua distribuição
    - **Filtro inteligente**: Aparece apenas quando há múltiplas faixas para o agente selecionado
    - **Tratamento de outliers**: Valores muito distantes ficam em faixas separadas

    **Exemplo**: Bacillus pode ter Faixa I (R$ 11-21), Faixa II (R$ 386) e Faixa III (R$ 13.667)

    ### Tipos de Visualização

    1. **Gráficos de Valor**: Valor total e preço médio por categoria
    2. **Gráficos de Pizza**: Distribuição percentual de valores e quantidades  
    3. **Análise Temporal**: Evolução de preços ao longo do tempo
    4. **Análise por Faixas**: Comparação entre diferentes faixas de preço
    5. **Tabela Detalhada**: Dados brutos filtrados com preços e faixas
    """)
