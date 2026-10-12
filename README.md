# Radar de IA

Coleta diária de notícias sobre inteligência artificial em português do Brasil,
armazenamento no Supabase Postgres e painel exploratório em Streamlit.

## Ferramentas

- Python, Streamlit, pandas e Plotly (open source)
- Supabase Postgres (plano gratuito disponível)
- GitHub Actions para executar a coleta diária
- GNews API para descoberta de artigos (plano grátis sujeito a limites e termos)

O plano gratuito da GNews disponibiliza trechos, não necessariamente o artigo
completo. Este projeto guarda os metadados e os campos disponibilizados pela API;
consulte os termos do provedor antes de publicar ou reutilizar os dados.

## Configuração local

1. Crie um projeto Supabase e execute os arquivos em
   supabase/migrations/ no SQL Editor, em ordem alfabética.
2. Copie .env.example para .env e preencha as chaves da API e do Supabase.
   O painel usa SUPABASE_PUBLISHABLE_KEY; a coleta usa SUPABASE_SECRET_KEY.
3. Instale as dependências: pip install -r requirements.txt.
4. Rode a coleta: python -m src.collect.
5. Inicie o painel: streamlit run app.py.

Não envie .env nem SUPABASE_SECRET_KEY para o GitHub.

## GitHub Actions

Adicione estes Repository Secrets em Settings → Secrets and variables → Actions:

- GNEWS_API_KEY
- SUPABASE_URL
- SUPABASE_SECRET_KEY

O workflow .github/workflows/collect-news.yml executa diariamente às 09:00
no horário de São Paulo e também pode ser iniciado manualmente na aba Actions.

## Publicar o painel

Conecte este repositório ao Streamlit Community Cloud e configure SUPABASE_URL
e SUPABASE_PUBLISHABLE_KEY nos Secrets do app. O painel usa acesso somente
leitura; reserve SUPABASE_SECRET_KEY para o workflow de coleta.

## Análise textual

O coletor calcula métricas descritivas em português com Python padrão:
contagem de palavras, tamanho médio das palavras e termos mais frequentes,
removendo uma lista de palavras funcionais comuns. Os resultados ficam em
article_analyses e o painel apresenta estatísticas agregadas.

As métricas se baseiam no título, descrição e trecho retornado pela API; elas
não representam a análise do artigo completo nem incluem classificação de
sentimento.
