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

1. Crie um projeto Supabase e execute o arquivo de migração
   supabase/migrations/202609230001_create_articles.sql no SQL Editor.
2. Copie .env.example para .env e preencha as chaves da API e do Supabase.
   O painel usa SUPABASE_ANON_KEY; a coleta usa SUPABASE_SERVICE_ROLE_KEY.
3. Instale as dependências: pip install -r requirements.txt.
4. Rode a coleta: python -m src.collect.
5. Inicie o painel: streamlit run app.py.

Não envie .env nem a chave service_role para o GitHub.

## GitHub Actions

Adicione estes Repository Secrets em Settings → Secrets and variables → Actions:

- GNEWS_API_KEY
- SUPABASE_URL
- SUPABASE_SERVICE_ROLE_KEY

O workflow .github/workflows/collect-news.yml executa diariamente às 09:00
no horário de São Paulo e também pode ser iniciado manualmente na aba Actions.

## Publicar o painel

Conecte este repositório ao Streamlit Community Cloud e configure SUPABASE_URL
e SUPABASE_ANON_KEY nos Secrets do app. O painel usa acesso somente leitura;
reserve a chave service_role para o workflow de coleta.

## Estado do MVP

A primeira versão armazena e apresenta notícias e volume diário. As análises
textuais (palavras-chave, entidades e sentimento em PT-BR) serão adicionadas
com uma biblioteca/modelo de licença aberta e avaliada para português.
