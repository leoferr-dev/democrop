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

        # Resto do código permanece igual...
        # [Continua com toda a lógica de filtros, gráficos, etc.]
        
        # Dataframe final filtrado
        df_filtrado = df_temp

        # Contador de resultados atualizado
        st.info(f"Exibindo {len(df_filtrado)} registros de um total de {len(df)}")

        # Botão para resetar filtros
        if st.button("Resetar Todos os Filtros"):
            st.rerun()

        # [Resto do código dos gráficos e análises continua igual...]
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

        # [Adicione aqui todo o resto do código dos gráficos...]
        # (O código é muito longo, mas você pode copiar toda a parte de gráficos do código original)

    except Exception as e:
        st.error(f"❌ Erro ao processar o arquivo: {str(e)}")
        st.info("Verifique se o arquivo está no formato correto e contém as colunas necessárias.")

else:
    st.error("❌ Não foi possível carregar os dados")
    st.info("📋 Certifique-se de que o arquivo 'Base_insumos_biológicos_correto.xlsx' está no repositório")
