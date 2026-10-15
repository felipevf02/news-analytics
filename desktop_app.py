"""Desktop reader for the Radar de IA Supabase project."""

from __future__ import annotations

import os
import queue
import threading
import webbrowser
from collections import Counter
from datetime import datetime, timedelta, timezone
from tkinter import StringVar, Tk, messagebox, ttk

from dotenv import load_dotenv
from supabase import create_client

from src.config import normalize_supabase_url
from src.sql_console import SQLConsoleWindow


APP_BG = "#f3f5f9"
CARD_BG = "#ffffff"
INK = "#19243a"
MUTED = "#6c7890"
ACCENT = "#4257d6"


def fetch_dashboard_data() -> list[dict]:
    """Read article metadata and text metrics using the public client key."""
    load_dotenv()
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_PUBLISHABLE_KEY")
    missing = [
        name
        for name, value in (
            ("SUPABASE_URL", url),
            ("SUPABASE_PUBLISHABLE_KEY", key),
        )
        if not value
    ]
    if missing:
        raise RuntimeError(
            "Configure estas variáveis no arquivo .env: " + ", ".join(missing)
        )

    client = create_client(normalize_supabase_url(url), key)
    articles = (
        client.table("articles")
        .select("id,title,description,url,source_name,published_at")
        .order("published_at", desc=True)
        .limit(1000)
        .execute()
        .data
        or []
    )
    if not articles:
        return []

    analysis = (
        client.table("article_analyses")
        .select(
            "article_id,word_count,unique_word_count,avg_word_length,top_terms"
        )
        .limit(1000)
        .execute()
        .data
        or []
    )
    metrics_by_id = {row["article_id"]: row for row in analysis}
    for article in articles:
        article.update(metrics_by_id.get(article["id"], {}))
        article["source_name"] = article.get("source_name") or "Fonte não informada"
    return articles


def parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    except (TypeError, ValueError):
        return None


class RadarDesktop(Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("Radar de IA")
        self.geometry("1220x790")
        self.minsize(960, 650)
        self.configure(bg=APP_BG)

        self.articles: list[dict] = []
        self.visible_articles: list[dict] = []
        self.worker_queue: queue.Queue = queue.Queue()
        self.days_var = StringVar(value="30 dias")
        self.source_var = StringVar(value="Todas as fontes")
        self.search_var = StringVar()
        self.status_var = StringVar(value="Conecte ao Supabase para carregar as notícias.")
        self.selected_article: dict | None = None

        self._configure_style()
        self._build_layout()
        self.search_var.trace_add("write", lambda *_: self.apply_filters())
        self.after(250, self.poll_worker)
        self.refresh_data()

    def _configure_style(self) -> None:
        style = ttk.Style(self)
        try:
            style.theme_use("clam")
        except Exception:
            pass
        style.configure("TFrame", background=APP_BG)
        style.configure("Card.TFrame", background=CARD_BG)
        style.configure("TLabel", background=APP_BG, foreground=INK, font=("Segoe UI", 10))
        style.configure("Muted.TLabel", background=APP_BG, foreground=MUTED, font=("Segoe UI", 9))
        style.configure("Title.TLabel", background=APP_BG, foreground=INK, font=("Segoe UI", 23, "bold"))
        style.configure("CardTitle.TLabel", background=CARD_BG, foreground=MUTED, font=("Segoe UI", 9))
        style.configure("Metric.TLabel", background=CARD_BG, foreground=INK, font=("Segoe UI", 21, "bold"))
        style.configure("Section.TLabel", background=CARD_BG, foreground=INK, font=("Segoe UI", 12, "bold"))
        style.configure(
            "Accent.TButton",
            background=ACCENT,
            foreground="#ffffff",
            padding=(15, 9),
            font=("Segoe UI", 10, "bold"),
        )
        style.map("Accent.TButton", background=[("active", "#3448c5"), ("disabled", "#aab2d9")])
        style.configure(
            "Treeview",
            background=CARD_BG,
            fieldbackground=CARD_BG,
            foreground=INK,
            rowheight=34,
            borderwidth=0,
            font=("Segoe UI", 9),
        )
        style.configure(
            "Treeview.Heading",
            background="#e9edf5",
            foreground=INK,
            font=("Segoe UI", 9, "bold"),
            padding=8,
        )
        style.map("Treeview", background=[("selected", "#dfe5ff")], foreground=[("selected", INK)])

    def _build_layout(self) -> None:
        page = ttk.Frame(self, padding=(24, 20))
        page.pack(fill="both", expand=True)

        header = ttk.Frame(page)
        header.pack(fill="x", pady=(0, 18))
        heading = ttk.Frame(header)
        heading.pack(side="left")
        ttk.Label(heading, text="Radar de IA", style="Title.TLabel").pack(anchor="w")
        ttk.Label(
            heading,
            text="Notícias e análise textual • Português do Brasil",
            style="Muted.TLabel",
        ).pack(anchor="w", pady=(3, 0))
        self.refresh_button = ttk.Button(
            header, text="Atualizar notícias", style="Accent.TButton", command=self.refresh_data
        )
        self.refresh_button.pack(side="right", anchor="center")
        self.sql_button = ttk.Button(
            header, text="Console SQL", command=self.open_sql_console
        )
        self.sql_button.pack(side="right", anchor="center", padx=(0, 10))

        filters = ttk.Frame(page)
        filters.pack(fill="x", pady=(0, 14))
        ttk.Label(filters, text="Período").pack(side="left", padx=(0, 7))
        period = ttk.Combobox(
            filters,
            textvariable=self.days_var,
            values=("7 dias", "30 dias", "90 dias", "Todo o período"),
            state="readonly",
            width=16,
        )
        period.pack(side="left", padx=(0, 18))
        period.bind("<<ComboboxSelected>>", lambda _event: self.apply_filters())
        ttk.Label(filters, text="Fonte").pack(side="left", padx=(0, 7))
        self.source_combo = ttk.Combobox(
            filters, textvariable=self.source_var, values=("Todas as fontes",), state="readonly", width=24
        )
        self.source_combo.pack(side="left", padx=(0, 18))
        self.source_combo.bind("<<ComboboxSelected>>", lambda _event: self.apply_filters())
        ttk.Label(filters, text="Buscar").pack(side="left", padx=(0, 7))
        search = ttk.Entry(filters, textvariable=self.search_var, width=34)
        search.pack(side="left", fill="x", expand=True)

        cards = ttk.Frame(page)
        cards.pack(fill="x", pady=(0, 14))
        self.article_metric = self._metric_card(cards, "NOTÍCIAS NO PERÍODO", "—")
        self.source_metric = self._metric_card(cards, "FONTES", "—")
        self.words_metric = self._metric_card(cards, "MÉDIA DE PALAVRAS", "—")
        self.article_metric.pack(side="left", fill="x", expand=True, padx=(0, 8))
        self.source_metric.pack(side="left", fill="x", expand=True, padx=8)
        self.words_metric.pack(side="left", fill="x", expand=True, padx=(8, 0))

        content = ttk.Panedwindow(page, orient="horizontal")
        content.pack(fill="both", expand=True)
        list_card = ttk.Frame(content, style="Card.TFrame", padding=12)
        detail_card = ttk.Frame(content, style="Card.TFrame", padding=18)
        content.add(list_card, weight=3)
        content.add(detail_card, weight=2)

        ttk.Label(list_card, text="Notícias recentes", style="Section.TLabel").pack(
            anchor="w", pady=(0, 10)
        )
        table_frame = ttk.Frame(list_card, style="Card.TFrame")
        table_frame.pack(fill="both", expand=True)
        columns = ("date", "source", "title", "words")
        self.tree = ttk.Treeview(table_frame, columns=columns, show="headings", selectmode="browse")
        self.tree.heading("date", text="DATA")
        self.tree.heading("source", text="FONTE")
        self.tree.heading("title", text="TÍTULO")
        self.tree.heading("words", text="PALAVRAS")
        self.tree.column("date", width=100, minwidth=90, stretch=False)
        self.tree.column("source", width=135, minwidth=100, stretch=False)
        self.tree.column("title", width=390, minwidth=220)
        self.tree.column("words", width=85, minwidth=70, stretch=False, anchor="center")
        scrollbar = ttk.Scrollbar(table_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        self.tree.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        self.tree.bind("<<TreeviewSelect>>", self.show_selected_article)

        ttk.Label(detail_card, text="Detalhes e análise", style="Section.TLabel").pack(
            anchor="w", pady=(0, 12)
        )
        self.detail_title = ttk.Label(
            detail_card,
            text="Selecione uma notícia",
            background=CARD_BG,
            foreground=INK,
            font=("Segoe UI", 16, "bold"),
            wraplength=380,
            justify="left",
        )
        self.detail_title.pack(anchor="w", fill="x")
        self.detail_meta = ttk.Label(
            detail_card, text="", background=CARD_BG, foreground=MUTED, font=("Segoe UI", 9)
        )
        self.detail_meta.pack(anchor="w", pady=(8, 15))
        self.detail_description = ttk.Label(
            detail_card,
            text="",
            background=CARD_BG,
            foreground=INK,
            font=("Segoe UI", 10),
            wraplength=380,
            justify="left",
        )
        self.detail_description.pack(anchor="w", fill="x")
        self.detail_analysis = ttk.Label(
            detail_card,
            text="",
            background=CARD_BG,
            foreground=INK,
            font=("Segoe UI", 10),
            wraplength=380,
            justify="left",
        )
        self.detail_analysis.pack(anchor="w", fill="x", pady=(18, 0))
        self.detail_terms = ttk.Label(
            detail_card,
            text="",
            background=CARD_BG,
            foreground=ACCENT,
            font=("Segoe UI", 10),
            wraplength=380,
            justify="left",
        )
        self.detail_terms.pack(anchor="w", fill="x", pady=(12, 0))
        self.open_button = ttk.Button(
            detail_card, text="Abrir notícia no navegador", command=self.open_selected_article
        )
        self.open_button.pack(anchor="w", pady=(20, 0))
        self.open_button.state(["disabled"])

        ttk.Label(page, textvariable=self.status_var, style="Muted.TLabel").pack(
            anchor="w", pady=(11, 0)
        )

    @staticmethod
    def _metric_card(parent: ttk.Frame, title: str, value: str) -> ttk.Frame:
        card = ttk.Frame(parent, style="Card.TFrame", padding=(16, 13))
        ttk.Label(card, text=title, style="CardTitle.TLabel").pack(anchor="w")
        label = ttk.Label(card, text=value, style="Metric.TLabel")
        label.pack(anchor="w", pady=(5, 0))
        card.metric_label = label
        return card

    def refresh_data(self) -> None:
        self.refresh_button.state(["disabled"])
        self.status_var.set("Conectando ao Supabase…")
        thread = threading.Thread(target=self._load_worker, daemon=True)
        thread.start()

    def _load_worker(self) -> None:
        try:
            self.worker_queue.put(("success", fetch_dashboard_data()))
        except Exception as exc:
            self.worker_queue.put(("error", str(exc)))

    def poll_worker(self) -> None:
        try:
            kind, payload = self.worker_queue.get_nowait()
        except queue.Empty:
            self.after(200, self.poll_worker)
            return

        self.refresh_button.state(["!disabled"])
        if kind == "error":
            self.status_var.set("Falha ao carregar dados.")
            messagebox.showerror(
                "Erro de conexão",
                f"Não foi possível carregar os dados do Supabase.\n\n{payload}",
                parent=self,
            )
        else:
            self.articles = payload
            sources = sorted(
                {article["source_name"] for article in self.articles if article.get("source_name")}
            )
            self.source_combo.configure(values=("Todas as fontes", *sources))
            if self.source_var.get() not in ("Todas as fontes", *sources):
                self.source_var.set("Todas as fontes")
            self.apply_filters()
            self.status_var.set(
                f"Atualizado às {datetime.now().strftime('%H:%M')} · "
                f"{len(self.articles)} notícias carregadas"
            )
        self.after(200, self.poll_worker)

    def apply_filters(self) -> None:
        now = datetime.now(timezone.utc)
        period = self.days_var.get()
        days = {"7 dias": 7, "30 dias": 30, "90 dias": 90}.get(period)
        source = self.source_var.get()
        search = self.search_var.get().strip().casefold()
        filtered = []

        for article in self.articles:
            published = parse_datetime(article.get("published_at"))
            if days and (published is None or published < now - timedelta(days=days)):
                continue
            if source != "Todas as fontes" and article.get("source_name") != source:
                continue
            haystack = " ".join(
                str(article.get(field) or "")
                for field in ("title", "description", "source_name")
            ).casefold()
            if search and search not in haystack:
                continue
            filtered.append(article)

        self.visible_articles = filtered
        self._update_metrics(filtered)
        self._populate_table(filtered)

    def _update_metrics(self, articles: list[dict]) -> None:
        sources = {article.get("source_name") for article in articles}
        word_counts = [
            article.get("word_count")
            for article in articles
            if isinstance(article.get("word_count"), (int, float))
        ]
        self.article_metric.metric_label.configure(text=str(len(articles)))
        self.source_metric.metric_label.configure(text=str(len(sources)))
        self.words_metric.metric_label.configure(
            text=f"{sum(word_counts) / len(word_counts):.0f}" if word_counts else "—"
        )

    def _populate_table(self, articles: list[dict]) -> None:
        for item in self.tree.get_children():
            self.tree.delete(item)
        for index, article in enumerate(articles):
            published = parse_datetime(article.get("published_at"))
            date_label = published.astimezone().strftime("%d/%m/%Y") if published else "—"
            words = article.get("word_count")
            self.tree.insert(
                "",
                "end",
                iid=str(index),
                values=(
                    date_label,
                    article.get("source_name") or "—",
                    article.get("title") or "(sem título)",
                    words if words is not None else "—",
                ),
            )

    def show_selected_article(self, _event=None) -> None:
        selection = self.tree.selection()
        if not selection:
            return
        self.selected_article = self.visible_articles[int(selection[0])]
        article = self.selected_article
        self.detail_title.configure(text=article.get("title") or "(sem título)")
        published = parse_datetime(article.get("published_at"))
        date_label = published.astimezone().strftime("%d/%m/%Y %H:%M") if published else "Data indisponível"
        self.detail_meta.configure(
            text=f"{article.get('source_name') or 'Fonte não informada'}  ·  {date_label}"
        )
        self.detail_description.configure(
            text=article.get("description") or "A API não forneceu uma descrição."
        )
        word_count = article.get("word_count")
        if word_count is None:
            analysis = "Análise textual ainda não disponível para esta notícia."
        else:
            analysis = (
                f"Palavras: {word_count}    "
                f"Palavras distintas: {article.get('unique_word_count', '—')}\n"
                f"Tamanho médio das palavras: {article.get('avg_word_length', '—')} caracteres"
            )
        self.detail_analysis.configure(text=analysis)
        terms = article.get("top_terms") or []
        term_text = "Termos frequentes: " + (
            " · ".join(f"{term['term']} ({term['count']})" for term in terms[:10])
            if terms
            else "sem termos calculados"
        )
        self.detail_terms.configure(text=term_text)
        self.open_button.state(["!disabled"] if article.get("url") else ["disabled"])

    def open_selected_article(self) -> None:
        if self.selected_article and self.selected_article.get("url"):
            webbrowser.open(self.selected_article["url"])

    def open_sql_console(self) -> None:
        SQLConsoleWindow(self)


if __name__ == "__main__":
    RadarDesktop().mainloop()
