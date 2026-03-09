"""Dash layout components for the dashboard."""

from datetime import date, timedelta
from dash import html, dcc
import dash_bootstrap_components as dbc
import dash_ag_grid as dag


def create_header() -> html.Div:
    return html.Div(
        className="dashboard-header",
        children=[
            html.H1("AI Job Aggregator", className="dashboard-title"),
            html.P(
                "Real-time AI & Data Science job listings from multiple sources",
                className="dashboard-subtitle",
            ),
        ],
    )


def create_stats_row() -> dbc.Row:
    return dbc.Row(
        id="stats-row",
        className="mb-4 px-3",
        children=[
            dbc.Col(
                html.Div(className="stat-card", children=[
                    html.Div(id="stat-total", className="stat-number", children="0"),
                    html.Div("Total Jobs", className="stat-label"),
                ]),
                xs=6, sm=6, md=3,
            ),
            dbc.Col(
                html.Div(className="stat-card", children=[
                    html.Div(id="stat-sources", className="stat-number", children="0"),
                    html.Div("Sources", className="stat-label"),
                ]),
                xs=6, sm=6, md=3,
            ),
            dbc.Col(
                html.Div(className="stat-card", children=[
                    html.Div(id="stat-companies", className="stat-number", children="0"),
                    html.Div("Companies", className="stat-label"),
                ]),
                xs=6, sm=6, md=3,
            ),
            dbc.Col(
                html.Div(className="stat-card", children=[
                    html.Div(id="stat-categories", className="stat-number", children="0"),
                    html.Div("Categories", className="stat-label"),
                ]),
                xs=6, sm=6, md=3,
            ),
        ],
    )


def create_filter_panel() -> html.Div:
    return html.Div(
        className="filter-panel mx-3",
        children=[
            # الصف الأول — البحث والفلاتر الأساسية
            dbc.Row([
                dbc.Col([
                    html.Label("Search", className="filter-label"),
                    dcc.Input(
                        id="search-input",
                        type="text",
                        placeholder="Search jobs, companies, skills...",
                        debounce=True,
                        className="w-100",
                    ),
                ], xs=12, md=4),
                dbc.Col([
                    html.Label("Category", className="filter-label"),
                    dcc.Dropdown(
                        id="category-filter",
                        placeholder="All Categories",
                        clearable=True,
                        className="dash-dropdown",
                    ),
                ], xs=6, md=2),
                dbc.Col([
                    html.Label("Job Type", className="filter-label"),
                    dcc.Dropdown(
                        id="jobtype-filter",
                        placeholder="All Types",
                        clearable=True,
                        className="dash-dropdown",
                    ),
                ], xs=6, md=2),
                dbc.Col([
                    html.Label("Source", className="filter-label"),
                    dcc.Dropdown(
                        id="source-filter",
                        placeholder="All Sources",
                        clearable=True,
                        className="dash-dropdown",
                    ),
                ], xs=6, md=2),
                dbc.Col([
                    html.Label("Location", className="filter-label"),
                    dcc.Input(
                        id="location-filter",
                        type="text",
                        placeholder="Filter by location...",
                        debounce=True,
                        className="w-100",
                    ),
                ], xs=6, md=2),
            ], className="mb-3"),

            # الصف التاني — فلتر التاريخ
            dbc.Row([
                dbc.Col([
                    html.Label("Date Range", className="filter-label"),
                    dcc.DatePickerRange(
                        id="date-range-filter",
                        start_date=date.today() - timedelta(days=30),
                        end_date=date.today(),
                        min_date_allowed=date(2024, 1, 1),
                        max_date_allowed=date.today() + timedelta(days=1),
                        display_format="YYYY-MM-DD",
                        start_date_placeholder_text="From date",
                        end_date_placeholder_text="To date",
                        clearable=True,
                        style={"width": "100%"},
                    ),
                ], xs=12, md=4),
                dbc.Col([
                    html.Label("Quick Date", className="filter-label"),
                    dbc.ButtonGroup(
                        [
                            dbc.Button("Today", id="btn-today", color="outline-primary", size="sm"),
                            dbc.Button("3 Days", id="btn-3days", color="outline-primary", size="sm"),
                            dbc.Button("7 Days", id="btn-7days", color="outline-primary", size="sm"),
                            dbc.Button("30 Days", id="btn-30days", color="outline-primary", size="sm"),
                            dbc.Button("All", id="btn-all", color="outline-primary", size="sm"),
                        ],
                        className="mt-1",
                    ),
                ], xs=12, md=5),
                dbc.Col([
                    html.Label("Results", className="filter-label"),
                    html.Div(
                        id="results-count",
                        className="mt-1",
                        style={
                            "fontSize": "0.95rem",
                            "color": "var(--text-secondary)",
                            "fontWeight": "500",
                        },
                        children="Showing all jobs",
                    ),
                ], xs=12, md=3),
            ]),
        ],
    )


def create_job_table() -> html.Div:
    column_defs = [
        {
            "field": "title",
            "headerName": "Job Title",
            "minWidth": 280,
            "flex": 2,
        },
        {
            "field": "company",
            "headerName": "Company",
            "minWidth": 160,
            "flex": 1,
        },
        {
            "field": "location",
            "headerName": "Location",
            "minWidth": 140,
            "flex": 1,
        },
        {
            "field": "category",
            "headerName": "Category",
            "minWidth": 150,
            "flex": 1,
        },
        {
            "field": "job_type",
            "headerName": "Type",
            "minWidth": 100,
            "maxWidth": 120,
        },
        {
            "field": "source",
            "headerName": "Source",
            "minWidth": 100,
            "maxWidth": 120,
        },
        {
            "field": "skills",
            "headerName": "Skills",
            "minWidth": 200,
            "flex": 1.5,
            "tooltipField": "skills",
        },
        {
            "field": "date_posted",
            "headerName": "Posted",
            "minWidth": 110,
            "maxWidth": 130,
            "sort": "desc",
        },
        {
            "field": "url",
            "headerName": "Link",
            "minWidth": 80,
            "maxWidth": 80,
            "cellRenderer": "markdown",
        },
    ]

    return html.Div(
        className="mx-3 mt-3",
        children=[
            dag.AgGrid(
                id="job-table",
                columnDefs=column_defs,
                rowData=[],
                defaultColDef={
                    "resizable": True,
                    "sortable": True,
                    "filter": True,
                    "wrapText": True,
                    "autoHeight": True,
                },
                dashGridOptions={
                    "pagination": True,
                    "paginationPageSize": 25,
                    "animateRows": True,
                    "rowSelection": "single",
                    "domLayout": "autoHeight",
                },
                className="ag-theme-alpine",
                style={"width": "100%"},
            ),
        ],
    )


def create_job_detail_modal() -> dbc.Modal:
    return dbc.Modal(
        id="job-detail-modal",
        size="lg",
        is_open=False,
        children=[
            dbc.ModalHeader(
                dbc.ModalTitle(id="modal-title"),
                close_button=True,
            ),
            dbc.ModalBody(id="modal-body"),
        ],
    )

def create_scheduler_status() -> html.Div:
    return html.Div(
        className="filter-panel mx-3 mb-3",
        children=[
            dbc.Row([
                dbc.Col([
                    html.Div(
                        style={"display": "flex", "alignItems": "center", "gap": "10px"},
                        children=[
                            html.Div(
                                id="scheduler-dot",
                                style={
                                    "width": "10px",
                                    "height": "10px",
                                    "borderRadius": "50%",
                                    "backgroundColor": "#16a34a",
                                    "display": "inline-block",
                                },
                            ),
                            html.Span(
                                "Auto-Update Active",
                                style={"fontWeight": "600", "fontSize": "0.9rem"},
                            ),
                            html.Span(
                                id="next-update-text",
                                style={
                                    "color": "var(--text-secondary)",
                                    "fontSize": "0.85rem",
                                    "marginLeft": "10px",
                                },
                                children="",
                            ),
                        ],
                    ),
                ], md=8),
                dbc.Col([
                    dbc.Button(
                        "Update Now",
                        id="btn-update-now",
                        color="primary",
                        size="sm",
                        className="float-end",
                    ),
                    html.Div(
                        id="update-status",
                        style={
                            "fontSize": "0.8rem",
                            "color": "var(--text-secondary)",
                            "textAlign": "right",
                            "marginTop": "4px",
                        },
                    ),
                ], md=4),
            ]),
        ],
    )


def create_layout() -> html.Div:
    return html.Div([
        dcc.Interval(id="refresh-interval", interval=5 * 60 * 1000, n_intervals=0),
        # Interval لتحديث حالة الـ scheduler كل دقيقة
        dcc.Interval(id="scheduler-interval", interval=60 * 1000, n_intervals=0),

        create_header(),
        create_stats_row(),
        create_scheduler_status(),    # ← الإضافة الجديدة
        create_filter_panel(),
        create_job_table(),
        create_job_detail_modal(),

        html.Div(
            className="text-center py-4 mt-4",
            style={"color": "var(--text-muted)", "fontSize": "0.8rem"},
            children="AI Job Aggregator • Auto-updates daily at 8:00 AM & 8:00 PM",
        ),
    ])

