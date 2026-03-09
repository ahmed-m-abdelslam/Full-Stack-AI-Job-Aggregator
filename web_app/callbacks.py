"""Dash callbacks — connects UI interactions to data queries."""

from datetime import date, datetime, timedelta
from dash import Input, Output, State, callback, no_update, html, ctx
import dash_bootstrap_components as dbc

from database.connection import get_session
from database.repository import JobRepository
from database.models import Job
from utils.logger import logger


def register_callbacks(app):

    # ========== Quick Date Buttons ==========
    @app.callback(
        [
            Output("date-range-filter", "start_date"),
            Output("date-range-filter", "end_date"),
        ],
        [
            Input("btn-today", "n_clicks"),
            Input("btn-3days", "n_clicks"),
            Input("btn-7days", "n_clicks"),
            Input("btn-30days", "n_clicks"),
            Input("btn-all", "n_clicks"),
        ],
        prevent_initial_call=True,
    )
    def update_date_range(today, three, seven, thirty, all_btn):
        triggered = ctx.triggered_id
        end = date.today()

        if triggered == "btn-today":
            return end, end
        elif triggered == "btn-3days":
            return end - timedelta(days=3), end
        elif triggered == "btn-7days":
            return end - timedelta(days=7), end
        elif triggered == "btn-30days":
            return end - timedelta(days=30), end
        elif triggered == "btn-all":
            return None, None

        return no_update, no_update

    # ========== Main Dashboard Update ==========
    @app.callback(
        [
            Output("job-table", "rowData"),
            Output("stat-total", "children"),
            Output("stat-sources", "children"),
            Output("stat-companies", "children"),
            Output("stat-categories", "children"),
            Output("category-filter", "options"),
            Output("jobtype-filter", "options"),
            Output("source-filter", "options"),
            Output("results-count", "children"),
        ],
        [
            Input("refresh-interval", "n_intervals"),
            Input("search-input", "value"),
            Input("category-filter", "value"),
            Input("jobtype-filter", "value"),
            Input("source-filter", "value"),
            Input("location-filter", "value"),
            Input("date-range-filter", "start_date"),
            Input("date-range-filter", "end_date"),
        ],
    )
    def update_dashboard(
        n_intervals, search, category, job_type, source, location,
        start_date, end_date
    ):
        try:
            # تحويل التواريخ من string لـ datetime
            date_from = None
            date_to = None

            if start_date:
                if isinstance(start_date, str):
                    date_from = datetime.strptime(start_date[:10], "%Y-%m-%d")
                else:
                    date_from = datetime.combine(start_date, datetime.min.time())

            if end_date:
                if isinstance(end_date, str):
                    date_to = datetime.strptime(end_date[:10], "%Y-%m-%d").replace(
                        hour=23, minute=59, second=59
                    )
                else:
                    date_to = datetime.combine(end_date, datetime.max.time())

            with get_session() as session:
                jobs = JobRepository.get_jobs(
                    session,
                    search_query=search or None,
                    category_filter=category or None,
                    job_type_filter=job_type or None,
                    source_filter=source or None,
                    location_filter=location or None,
                    date_from=date_from,
                    date_to=date_to,
                    limit=500,
                )

                row_data = []
                for job in jobs:
                    skills_str = ", ".join(job.extracted_skills[:6]) if job.extracted_skills else ""
                    date_str = job.date_posted.strftime("%Y-%m-%d") if job.date_posted else ""

                    row_data.append({
                        "id": job.id,
                        "title": job.title,
                        "company": job.company,
                        "location": job.location or "—",
                        "category": job.category or "—",
                        "job_type": job.job_type or "—",
                        "source": job.source,
                        "skills": skills_str,
                        "date_posted": date_str,
                        "url": f"[Apply]({job.url})" if job.url else "—",
                        "summary": job.summary or "",
                        "description": (job.description or "")[:500],
                    })

                total_count = JobRepository.count_jobs(session)
                filter_options = JobRepository.get_filter_options(session)

                sources_count = len(filter_options["sources"])
                companies_count = len(filter_options["companies"])
                categories_count = len(filter_options["categories"])

                cat_options = [{"label": c, "value": c} for c in filter_options["categories"]]
                type_options = [{"label": t, "value": t} for t in filter_options["job_types"]]
                src_options = [{"label": s, "value": s} for s in filter_options["sources"]]

                # Results count text
                showing = len(row_data)
                date_text = ""
                if date_from and date_to:
                    date_text = f" • {date_from.strftime('%b %d')} → {date_to.strftime('%b %d')}"
                elif date_from:
                    date_text = f" • From {date_from.strftime('%b %d')}"

                results_text = f"Showing {showing} of {total_count} jobs{date_text}"

                return (
                    row_data,
                    f"{total_count:,}",
                    str(sources_count),
                    f"{companies_count:,}",
                    str(categories_count),
                    cat_options,
                    type_options,
                    src_options,
                    results_text,
                )

        except Exception as e:
            logger.error(f"Dashboard update error: {e}")
            return [], "0", "0", "0", "0", [], [], [], "Error loading data"

    # ========== Job Detail Modal ==========
    @app.callback(
        [
            Output("job-detail-modal", "is_open"),
            Output("modal-title", "children"),
            Output("modal-body", "children"),
        ],
        Input("job-table", "selectedRows"),
        State("job-detail-modal", "is_open"),
        prevent_initial_call=True,
    )
    def show_job_detail(selected_rows, is_open):
        if not selected_rows:
            return no_update, no_update, no_update

        row = selected_rows[0]

        modal_body = html.Div([
            dbc.Row([
                dbc.Col([
                    html.Strong("Company: "),
                    html.Span(row.get("company", "—")),
                ], md=6),
                dbc.Col([
                    html.Strong("Location: "),
                    html.Span(row.get("location", "—")),
                ], md=6),
            ], className="mb-2"),
            dbc.Row([
                dbc.Col([
                    html.Strong("Category: "),
                    html.Span(row.get("category", "—")),
                ], md=6),
                dbc.Col([
                    html.Strong("Type: "),
                    html.Span(row.get("job_type", "—")),
                ], md=6),
            ], className="mb-2"),
            dbc.Row([
                dbc.Col([
                    html.Strong("Source: "),
                    html.Span(row.get("source", "—")),
                ], md=6),
                dbc.Col([
                    html.Strong("Posted: "),
                    html.Span(row.get("date_posted", "—")),
                ], md=6),
            ], className="mb-3"),

            html.Hr(),

            html.H6("AI Summary", className="mt-3"),
            html.P(row.get("summary", "No summary available.")),

            html.H6("Skills", className="mt-3"),
            html.P(row.get("skills", "No skills extracted.")),

            html.H6("Description", className="mt-3"),
            html.P(
                row.get("description", "No description available."),
                style={"whiteSpace": "pre-wrap"},
            ),

            html.Div(
                dbc.Button(
                    "View Original Posting",
                    href=row.get("url", "").replace("[Apply](", "").rstrip(")"),
                    target="_blank",
                    color="primary",
                    className="mt-3",
                ) if row.get("url") and row["url"] != "—" else None,
            ),
        ])

        return True, row.get("title", "Job Details"), modal_body
    
        # ========== Scheduler Status ==========
    @app.callback(
        Output("next-update-text", "children"),
        Input("scheduler-interval", "n_intervals"),
    )
    def update_scheduler_status(n):
        try:
            from scheduler.job_scheduler import JobScheduler
            # نحاول نقرأ الـ next run time من الـ scheduler
            # لكن لأن الـ scheduler object مش متاح هنا مباشرة
            # نعرض الجدول الثابت
            from datetime import datetime
            now = datetime.now()
            hour = now.hour

            if hour < 8:
                next_run = "Next update: Today 8:00 AM"
            elif hour < 20:
                next_run = "Next update: Today 8:00 PM"
            else:
                next_run = "Next update: Tomorrow 8:00 AM"

            return f"• {next_run} • Last refresh: {now.strftime('%H:%M')}"
        except Exception:
            return "Auto-update scheduled"

    # ========== Manual Update Button ==========
    @app.callback(
        Output("update-status", "children"),
        Input("btn-update-now", "n_clicks"),
        prevent_initial_call=True,
    )
    def manual_update(n_clicks):
        if not n_clicks:
            return no_update

        try:
            import threading
            from scrapers.scraper_manager import ScraperManager

            def run_update():
                try:
                    manager = ScraperManager(sources=["remoteok", "linkedin", "wuzzuf"])
                    summary = manager.run_all(num_pages=2)
                    logger.info(f"Manual update complete: {summary['total_new']} new jobs")

                    # AI Processing
                    try:
                        from ai_processing import AIProcessor
                        processor = AIProcessor()
                        processor.process_unprocessed_jobs(batch_size=20)
                    except Exception as e:
                        logger.warning(f"AI processing after manual update failed: {e}")

                except Exception as e:
                    logger.error(f"Manual update failed: {e}")

            # نشغل في thread منفصل عشان ما يعلقش الداشبورد
            thread = threading.Thread(target=run_update, daemon=True)
            thread.start()

            from datetime import datetime
            return f"Update started at {datetime.now().strftime('%H:%M:%S')} — refresh in 1-2 minutes"

        except Exception as e:
            return f"Error: {str(e)}"

