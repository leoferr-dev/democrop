import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime
import os

# Configuração da página
st.set_page_config(page_title="Dashboard de Agentes Biológicos", layout="wide")
st.title("Demonstração de Dashboard de Visualização")

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

        # Função auxiliar para atualizar as opções de filtro
        def obter_opcoes_filtro(dataframe, coluna, incluir_todos=True, texto_todos="Todos"):
            opcoes = sorted(dataframe[coluna].unique())
            if incluir_todos:
                return [texto_todos] + list(opcoes)
            return list(opcoes)

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
        col1, col2, col3, col4 = st.columns(4)

        with col1:
            opcoes_estado = obter_opcoes_filtro(df_temp, "estado")
            filtro_estado = st.selectbox("Estado", opcoes_estado, key="estado")

            if filtro_estado != "Todos":
                df_temp = df_temp[df_temp["estado"] == filtro_estado]

        with col2:
            opcoes_cidade = obter_opcoes_filtro(df_temp, "cidade", texto_todos="Todas")
            filtro_cidade = st.selectbox("Cidade", opcoes_cidade, key="cidade")

            if filtro_cidade != "Todas":
                df_temp = df_temp[df_temp["cidade"] == filtro_cidade]

        with col3:
            opcoes_agente = obter_opcoes_filtro(df_temp, "agente_biologico", texto_todos="Todos")
            filtro_agente = st.selectbox("Agente Biológico", opcoes_agente, key="agente")

            if filtro_agente != "Todos":
                df_temp = df_temp[df_temp["agente_biologico"] == filtro_agente]

        with col4:
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

        # Calcular estatísticas
        if not df_filtrado.empty:
            preco_medio = df_filtrado["preco"].mean()
            preco_total = df_filtrado["preco"].sum()
            preco_maximo = df_filtrado["preco"].max()
            preco_minimo = df_filtrado["preco"].min()

            # Período de dados
            data_min = df_filtrado["data"].min()
            data_max = df_filtrado["data"].max()
        else:
            preco_medio = preco_total = preco_maximo = preco_minimo = 0
            data_min = data_max = None

        # Exibir estatísticas
        st.subheader("📈 Estatísticas")
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Preço Médio", f"R$ {preco_medio:.2f}")
        with col2:
            st.metric("Valor Total", f"R$ {preco_total:.2f}")
        with col3:
            st.metric("Preço Máximo", f"R$ {preco_maximo:.2f}")
        with col4:
            st.metric("Preço Mínimo", f"R$ {preco_minimo:.2f}")

        # Mostrar período dos dados se houver dados
        if data_min and data_max:
            st.info(f"Período dos dados: {data_min.strftime('%d/%m/%Y')} a {data_max.strftime('%d/%m/%Y')}")

        # Preparar dados para gráficos
        if not df_filtrado.empty:
            # Verificar quantos grupos únicos existem
            num_grupos_unicos = df_filtrado["agente_biologico"].nunique()

            if num_grupos_unicos >= 1:
                # Fazer agregação - contar ocorrências e calcular valores por grupo
                df_grafico = df_filtrado.groupby("agente_biologico").agg({
                    'preco': ['mean', 'sum', 'count']
                }).reset_index()

                # Simplificar nomes das colunas
                df_grafico.columns = ["agente_biologico", 'preco_medio', 'preco_total', 'count']
                df_grafico = df_grafico.sort_values(by="preco_total", ascending=False)

                # Criar visualizações
                st.subheader("📊 Visualizações")

                # Limitar exibição se houver muitos grupos
                if len(df_grafico) > 15:
                    st.info(f"Exibindo os 15 principais itens por valor total de um total de {len(df_grafico)}.")
                    df_grafico_top = df_grafico.head(15)
                else:
                    df_grafico_top = df_grafico

                # Se há apenas um grupo, mostrar análise detalhada desse grupo
                if num_grupos_unicos == 1:
                    st.info(f"📊 Análise detalhada para: **{df_grafico_top.iloc[0]['agente_biologico']}**")

                    # Mostrar métricas específicas
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.metric("Valor Total", f"R$ {df_grafico_top.iloc[0]['preco_total']:.2f}")
                    with col2:
                        st.metric("Preço Médio", f"R$ {df_grafico_top.iloc[0]['preco_medio']:.2f}")
                    with col3:
                        st.metric("Quantidade de Registros", f"{df_grafico_top.iloc[0]['count']}")

                    # Para um único agente, mostrar distribuição por outras dimensões
                    st.subheader(f"📈 Análise Detalhada - {df_grafico_top.iloc[0]['agente_biologico']}")

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
                                title=f"Valor Total por Estado - {df_grafico_top.iloc[0]['agente_biologico']}",
                                labels={'preco_total': 'Valor Total (R$)', 'estado': 'Estado'}
                            )
                            fig_estados.update_layout(height=400, template="plotly_white")
                            st.plotly_chart(fig_estados, use_container_width=True)

                        with col2:
                            fig_estados_pie = px.pie(
                                df_estados,
                                values='preco_total',
                                names='estado',
                                title=f"Distribuição por Estado - {df_grafico_top.iloc[0]['agente_biologico']}"
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
                                title=f"Valor Total por Cidade - {df_grafico_top.iloc[0]['agente_biologico']}",
                                labels={'preco_total': 'Valor Total (R$)', 'cidade': 'Cidade'}
                            )
                            fig_cidades.update_layout(height=400, template="plotly_white", xaxis_tickangle=-45)
                            st.plotly_chart(fig_cidades, use_container_width=True)

                        with col2:
                            fig_cidades_pie = px.pie(
                                df_cidades,
                                values='preco_total',
                                names='cidade',
                                title=f"Distribuição por Cidade - {df_grafico_top.iloc[0]['agente_biologico']}"
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
                                x=df_grafico_top["agente_biologico"],
                                y=df_grafico_top["preco_total"],
                                marker_color='rgb(41, 128, 185)',
                                name="Valor Total"
                            )
                        )

                        fig_valor.update_layout(
                            title="Valor Total por Agente Biológico",
                            xaxis_title="Agente Biológico",
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
                                x=df_grafico_top["agente_biologico"],
                                y=df_grafico_top["preco_medio"],
                                marker_color='rgb(39, 174, 96)',
                                name="Preço Médio"
                            )
                        )

                        fig_medio.update_layout(
                            title="Preço Médio por Agente Biológico",
                            xaxis_title="Agente Biológico",
                            yaxis_title="Preço Médio (R$)",
                            height=400,
                            template="plotly_white",
                            xaxis_tickangle=-45
                        )

                        st.plotly_chart(fig_medio, use_container_width=True)

                # Análise temporal - sempre mostrar se há dados suficientes
                st.subheader("⏰ Análise Temporal")

                # Período fixo: Mês
                periodo = "Mês"

                # Preparar dados temporais
                df_tempo = df_filtrado.copy()

                # Criar coluna de período
                df_tempo['periodo_str'] = df_tempo['data'].dt.strftime('%Y-%m')
                df_tempo['periodo_dt'] = pd.to_datetime(df_tempo['periodo_str'] + '-01')
                formato_data = '%b %Y'

                # Agrupar por período e agente biológico - Preço Médio
                df_tempo_grupo = df_tempo.groupby(['periodo_dt', 'periodo_str', 'agente_biologico'])[
                    'preco'].mean().reset_index()
                y_column = 'preco'
                y_label = "Preço Médio (R$)"

                if len(df_tempo_grupo) > 0:
                    # Criar gráfico de linha temporal
                    fig_tempo = px.line(
                        df_tempo_grupo,
                        x='periodo_dt',
                        y=y_column,
                        color='agente_biologico',
                        title="Evolução Temporal - Preço Médio por Agente Biológico (Mês)",
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
                        dtick="M1"
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



    except Exception as e:
        st.error(f"❌ Erro ao processar o arquivo: {str(e)}")
        st.info("Verifique se o arquivo está no formato correto e contém as colunas necessárias.")

else:
    st.error("❌ Não foi possível carregar os dados")
    st.info("📋 Certifique-se de que o arquivo 'Base_insumos_biológicos_correto.xlsx' está no repositório")
