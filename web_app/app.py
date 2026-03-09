"""Dash application entry point."""

import dash
import dash_bootstrap_components as dbc

from web_app.layouts import create_layout
from web_app.callbacks import register_callbacks


def create_app() -> dash.Dash:
    app = dash.Dash(
        __name__,
        external_stylesheets=[
            dbc.themes.BOOTSTRAP,  # ← غيرنا من DARKLY لـ BOOTSTRAP
            "https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap",
        ],
        title="AI Job Aggregator",
        suppress_callback_exceptions=True,
        meta_tags=[
            {"name": "viewport", "content": "width=device-width, initial-scale=1.0"},
        ],
    )

    app.layout = create_layout()
    register_callbacks(app)

    return app

