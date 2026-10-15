"""Direct PostgreSQL SQL console and repository migration runner."""

from __future__ import annotations

import os
import queue
import threading
from pathlib import Path
from tkinter import END, BOTH, LEFT, RIGHT, TOP, X, Y, StringVar, Toplevel, Text, ttk

from dotenv import load_dotenv


MIGRATIONS_DIR = Path(__file__).resolve().parent.parent / "supabase" / "migrations"
TRACKING_TABLE = "public._news_analytics_migrations"


class SQLConsoleWindow:
    """Small desktop SQL editor that connects directly to PostgreSQL."""

    def __init__(self, parent) -> None:
        load_dotenv()
        self.dsn = os.getenv("SUPABASE_DB_URL", "").strip()
        self.window = Toplevel(parent)
        self.window.title("Console SQL — Radar de IA")
        self.window.geometry("1100x760")
        self.window.minsize(820, 580)
        self.window.transient(parent)
        self.worker_queue: queue.Queue = queue.Queue()
        self.busy = False
        self.status = StringVar(
            value=(
                "Conexão PostgreSQL configurada"
                if self.dsn
                else "Configure SUPABASE_DB_URL no .env"
            )
        )

        self._build_ui()
        self.window.after(200, self._poll_worker)

    def _build_ui(self) -> None:
        outer = ttk.Frame(self.window, padding=16)
        outer.pack(fill=BOTH, expand=True)

        heading = ttk.Frame(outer)
        heading.pack(fill=X, pady=(0, 10))
        ttk.Label(heading, text="Console SQL", font=("Segoe UI", 18, "bold")).pack(
            side=LEFT
        )
        ttk.Label(
            heading,
            text="Conexão direta ao PostgreSQL via TLS",
            foreground="#68748c",
        ).pack(side=LEFT, padx=(14, 0), pady=(5, 0))

        actions = ttk.Frame(outer)
        actions.pack(fill=X, pady=(0, 8))
        self.test_button = ttk.Button(
            actions, text="Testar conexão", command=self.test_connection
        )
        self.test_button.pack(side=LEFT, padx=(0, 8))
        self.run_selection_button = ttk.Button(
            actions, text="Executar seleção", command=self.execute_selection
        )
        self.run_selection_button.pack(side=LEFT, padx=(0, 8))
        self.run_all_button = ttk.Button(
            actions, text="Executar editor", command=self.execute_all
        )
        self.run_all_button.pack(side=LEFT, padx=(0, 8))
        self.migrations_button = ttk.Button(
            actions,
            text="Aplicar migrações do projeto",
            command=self.apply_migrations,
        )
        self.migrations_button.pack(side=LEFT)

        ttk.Label(
            outer,
            text=(
                "As consultas usam SUPABASE_DB_URL. O endereço contém a senha do "
                "banco; deixe-o somente no .env local, que não é versionado."
            ),
            foreground="#68748c",
            wraplength=1040,
        ).pack(anchor="w", pady=(0, 10))

        editor_frame = ttk.Frame(outer)
        editor_frame.pack(fill=BOTH, expand=True)
        self.editor = Text(
            editor_frame,
            height=15,
            wrap="none",
            undo=True,
            font=("Consolas", 10),
            background="#172033",
            foreground="#e5eaf4",
            insertbackground="#ffffff",
            padx=12,
            pady=10,
        )
        editor_y = ttk.Scrollbar(editor_frame, orient="vertical", command=self.editor.yview)
        editor_x = ttk.Scrollbar(editor_frame, orient="horizontal", command=self.editor.xview)
        self.editor.configure(yscrollcommand=editor_y.set, xscrollcommand=editor_x.set)
        self.editor.pack(side=LEFT, fill=BOTH, expand=True)
        editor_y.pack(side=RIGHT, fill=Y)
        editor_x.pack(side=TOP, fill=X)
        self.editor.insert(
            "1.0",
            "-- Digite uma consulta SQL aqui. Exemplo:\n"
            "select id, title, source_name, published_at\n"
            "from public.articles\n"
            "order by published_at desc\n"
            "limit 20;\n",
        )

        result_label = ttk.Label(
            outer, text="Resultado", font=("Segoe UI", 11, "bold")
        )
        result_label.pack(anchor="w", pady=(12, 6))
        result_frame = ttk.Frame(outer)
        result_frame.pack(fill=BOTH, expand=True)
        self.result_tree = ttk.Treeview(result_frame, show="headings", height=10)
        result_y = ttk.Scrollbar(
            result_frame, orient="vertical", command=self.result_tree.yview
        )
        result_x = ttk.Scrollbar(
            result_frame, orient="horizontal", command=self.result_tree.xview
        )
        self.result_tree.configure(
            yscrollcommand=result_y.set, xscrollcommand=result_x.set
        )
        self.result_tree.pack(side=LEFT, fill=BOTH, expand=True)
        result_y.pack(side=RIGHT, fill=Y)
        result_x.pack(side=TOP, fill=X)

        ttk.Label(outer, textvariable=self.status, foreground="#68748c").pack(
            anchor="w", pady=(8, 0)
        )

    def _require_dsn(self) -> bool:
        if self.dsn:
            return True
        self.status.set(
            "Falta SUPABASE_DB_URL no .env. Use a connection string PostgreSQL do projeto."
        )
        return False

    def _submit(self, operation: str, sql: str = "") -> None:
        if self.busy:
            return
        if not self._require_dsn():
            return
        self.busy = True
        self._set_buttons_enabled(False)
        self.status.set("Executando no PostgreSQL…")
        thread = threading.Thread(
            target=self._worker, args=(operation, sql), daemon=True
        )
        thread.start()

    def _worker(self, operation: str, sql: str) -> None:
        try:
            import psycopg
            from psycopg.rows import dict_row

            with psycopg.connect(
                self.dsn,
                sslmode="require",
                connect_timeout=15,
                row_factory=dict_row,
            ) as connection:
                if operation == "test":
                    with connection.cursor() as cursor:
                        cursor.execute(
                            "select current_database() as database, "
                            "current_user as role, version() as postgres_version"
                        )
                        rows = cursor.fetchall()
                        columns = list(rows[0].keys()) if rows else []
                    self.worker_queue.put(
                        ("success", columns, rows, "Conexão PostgreSQL estabelecida.")
                    )
                    return

                if operation == "query":
                    with connection.cursor() as cursor:
                        cursor.execute(sql)
                        if cursor.description:
                            columns = [column.name for column in cursor.description]
                            rows = cursor.fetchall()
                        else:
                            columns = []
                            rows = []
                        status = cursor.statusmessage or "Consulta executada."
                    self.worker_queue.put(("success", columns, rows, status))
                    return

                if operation == "migrations":
                    if not MIGRATIONS_DIR.exists():
                        raise RuntimeError(
                            f"Diretório de migrações não encontrado: {MIGRATIONS_DIR}"
                        )
                    applied_now = []
                    with connection.transaction():
                        connection.execute(
                            f"""
                            create table if not exists {TRACKING_TABLE} (
                                version text primary key,
                                applied_at timestamptz not null default now()
                            )
                            """
                        )
                        applied = {
                            row["version"]
                            for row in connection.execute(
                                f"select version from {TRACKING_TABLE}"
                            ).fetchall()
                        }
                        for migration in sorted(MIGRATIONS_DIR.glob("*.sql")):
                            if migration.name in applied:
                                continue
                            sql_text = migration.read_text(encoding="utf-8")
                            if sql_text.strip():
                                connection.execute(sql_text)
                            connection.execute(
                                f"insert into {TRACKING_TABLE} (version) values (%s)",
                                (migration.name,),
                            )
                            applied_now.append(migration.name)
                        connection.execute("notify pgrst, 'reload schema'")
                    self.worker_queue.put(
                        (
                            "success",
                            ["Migrações"],
                            [{"Migrações aplicadas nesta execução": len(applied_now)}],
                            (
                                "Nenhuma migração pendente."
                                if not applied_now
                                else "Aplicadas: " + ", ".join(applied_now)
                            ),
                        )
                    )
        except Exception as exc:
            self.worker_queue.put(("error", str(exc)))

    def test_connection(self) -> None:
        self._submit("test")

    def execute_selection(self) -> None:
        try:
            sql = self.editor.get("sel.first", "sel.last").strip()
        except Exception:
            sql = ""
        if not sql:
            self.status.set("Selecione um trecho SQL no editor para executar.")
            return
        self._submit("query", sql)

    def execute_all(self) -> None:
        sql = self.editor.get("1.0", END).strip()
        if sql:
            self._submit("query", sql)

    def apply_migrations(self) -> None:
        self._submit("migrations")

    def _poll_worker(self) -> None:
        try:
            result = self.worker_queue.get_nowait()
        except queue.Empty:
            self.window.after(200, self._poll_worker)
            return

        self.busy = False
        self._set_buttons_enabled(True)
        if result[0] == "error":
            self.status.set("Falha na execução SQL.")
            self._show_message("Erro PostgreSQL", result[1])
        else:
            _, columns, rows, message = result
            self._show_rows(columns, rows)
            self.status.set(message)
        self.window.after(200, self._poll_worker)

    def _set_buttons_enabled(self, enabled: bool) -> None:
        state = ["!disabled"] if enabled else ["disabled"]
        for button in (
            self.test_button,
            self.run_selection_button,
            self.run_all_button,
            self.migrations_button,
        ):
            button.state(state)

    def _show_rows(self, columns: list[str], rows: list[dict]) -> None:
        self.result_tree.delete(*self.result_tree.get_children())
        self.result_tree["columns"] = columns
        for column in columns:
            self.result_tree.heading(column, text=column)
            self.result_tree.column(column, width=170, minwidth=90, stretch=True)
        for row in rows:
            self.result_tree.insert(
                "",
                END,
                values=tuple(self._format_cell(row.get(column)) for column in columns),
            )

    @staticmethod
    def _format_cell(value) -> str:
        if value is None:
            return "NULL"
        if isinstance(value, (dict, list)):
            return str(value)
        return str(value)

    def _show_message(self, title: str, message: str) -> None:
        from tkinter import messagebox

        messagebox.showerror(title, message, parent=self.window)
