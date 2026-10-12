"""Streamlit dashboard for AI news in Brazilian Portuguese."""

import os

import pandas as pd
import plotly.express as px
import streamlit as st
from dotenv import load_dotenv
from supabase import create_client

from src.config import normalize_supabase_url

load_dotenv()
st.set_page_config(page_title="Radar de IA", page_icon="🗞️", layout="wide")
st.title("🗞️ Radar de IA")
st.caption("Notícias sobre inteligência artificial publicadas no Brasil")


@st.cache_data(ttl=300)
def load_articles() -> pd.DataFrame:
    url = st.secrets.get("SUPABASE_URL", os.getenv("SUPABASE_URL"))
    key = st.secrets.get(
        "SUPABASE_PUBLISHABLE_KEY", os.getenv("SUPABASE_PUBLISHABLE_KEY")
    )
    if not url or not key:
        return pd.DataFrame()
    client = create_client(normalize_supabase_url(url), key)
    response = (
        client.table("articles")
        .select("id,title,description,url,source_name,published_at,fetched_at")
        .order("published_at", desc=True)
        .limit(1000)
        .execute()
    )
    articles = pd.DataFrame(response.data or [])
    if articles.empty:
        return articles
    analysis = (
        client.table("article_analyses")
        .select("article_id,word_count,unique_word_count,avg_word_length,top_terms")
        .execute()
    )
    metrics = pd.DataFrame(analysis.data or [])
    if metrics.empty:
        return articles
    return articles.merge(metrics, left_on="id", right_on="article_id", how="left")


try:
    articles = load_articles()
except Exception as exc:
    st.error(f"Não foi possível carregar as notícias: {exc}")
    st.stop()

if articles.empty:
    st.info("Ainda não há notícias. Configure os Secrets e execute a coleta diária.")
    st.stop()

articles["published_at"] = pd.to_datetime(articles["published_at"], errors="coerce", utc=True)
articles["source_name"] = articles["source_name"].fillna("Fonte não informada")
articles = articles.dropna(subset=["published_at"])

sources = ["Todas"] + sorted(articles["source_name"].unique().tolist())
selected_source = st.sidebar.selectbox("Fonte", sources)
days = st.sidebar.slider("Período (dias)", min_value=7, max_value=90, value=30)
cutoff = pd.Timestamp.now(tz="UTC") - pd.Timedelta(days=days)
filtered = articles[articles["published_at"] >= cutoff]
if selected_source != "Todas":
    filtered = filtered[filtered["source_name"] == selected_source]

c1, c2, c3 = st.columns(3)
c1.metric("Notícias no período", len(filtered))
c2.metric("Fontes", filtered["source_name"].nunique())
c3.metric("Última coleta", articles["fetched_at"].max()[:10] if articles["fetched_at"].notna().any() else "—")

if filtered.empty:
    st.info("Nenhuma notícia encontrada com esses filtros.")
    st.stop()

daily = (
    filtered.assign(day=filtered["published_at"].dt.date)
    .groupby("day", as_index=False)
    .size()
    .rename(columns={"size": "notícias"})
)
st.subheader("Volume diário")
st.plotly_chart(px.line(daily, x="day", y="notícias", markers=True), use_container_width=True)

st.subheader("Estatísticas do texto")
analyzed = filtered.dropna(subset=["word_count"])
if analyzed.empty:
    st.info("As notícias ainda não foram analisadas. Execute a coleta para processá-las.")
else:
    a1, a2, a3 = st.columns(3)
    a1.metric("Textos analisados", len(analyzed))
    a2.metric("Média de palavras", f"{analyzed['word_count'].mean():.0f}")
    a3.metric("Vocabulário médio", f"{analyzed['unique_word_count'].mean():.0f} palavras únicas")

    term_counts: dict[str, int] = {}
    for terms in analyzed["top_terms"].dropna():
        for item in terms:
            term_counts[item["term"]] = term_counts.get(item["term"], 0) + item["count"]
    if term_counts:
        top_terms = (
            pd.DataFrame(
                sorted(term_counts.items(), key=lambda item: item[1], reverse=True)[:15],
                columns=["termo", "ocorrências"],
            )
        )
        st.plotly_chart(
            px.bar(top_terms.sort_values("ocorrências"), x="ocorrências", y="termo", orientation="h"),
            use_container_width=True,
        )

st.subheader("Notícias recentes")
for _, row in filtered.sort_values("published_at", ascending=False).iterrows():
    with st.container(border=True):
        st.markdown(f"**[{row['title']}]({row['url']})**")
        st.caption(f"{row['source_name']} · {row['published_at'].strftime('%d/%m/%Y %H:%M UTC')}")
        if pd.notna(row.get("word_count")):
            st.caption(
                f"Análise: {int(row['word_count'])} palavras · "
                f"{int(row['unique_word_count'])} palavras distintas"
            )
        if row.get("description"):
            st.write(row["description"])
