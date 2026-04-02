#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import shlex
import subprocess
import time
from pathlib import Path
from typing import Dict, List, Tuple

from dash import Dash, Input, Output, State, ALL, ctx, dcc, html, no_update
from dash.exceptions import PreventUpdate

# ============================================================
# KONFIGURACJA DO SZYBKIEJ ZMIANY
# ============================================================
# Ustaw lokalny katalog repozytorium na tym komputerze. Nie jest pokazywany w GUI.
REPO_DIR = Path(r"C:\Users\marsieradzka\Documents\GitHub\ris_system")

# Jeśli masz inną strukturę repo, dodaj tu kolejne możliwe ścieżki.
PARAMETER_CANDIDATES = [
    REPO_DIR / "helpers" / "parameters.py",
    REPO_DIR / "ris_system-final" / "helpers" / "parameters.py",
]

# Opóźnienie między kolejnymi startami/stopami w Start all / Stop all.
START_ALL_DELAY_SEC = 1.5
STOP_ALL_DELAY_SEC = 0.8

# Polecenia uruchamiane zdalnie przez SSH.
# To są jedyne miejsca, które zwykle trzeba dopasować do Twojego projektu.
REMOTE_MAIN_DIR = "~/ris_system"
PYTHON_BIN = "python3"


def build_start_command(kind: str, idx: int) -> str:
    """Zwraca komendę startową uruchamianą na zdalnej maszynie.
    Dostosuj ją do sposobu uruchamiania Twojego projektu.
    """
    return (
        f"cd {shlex.quote(REMOTE_MAIN_DIR)} && "
        f"{PYTHON_BIN} main.py {kind} {idx}"
    )


def build_stop_command(kind: str, idx: int) -> str:
    """Zwraca komendę zatrzymującą proces zdalny.
    Tu jest wersja prosta oparta o pkill po fragmencie komendy.
    """
    pattern = f"main.py {kind} {idx}"
    return f"pkill -f {shlex.quote(pattern)}"


# ============================================================
# ODCZYT parameters.py
# ============================================================
def find_parameters_file() -> Path:
    for path in PARAMETER_CANDIDATES:
        if path.exists():
            return path
    raise FileNotFoundError("Nie znaleziono helpers/parameters.py")


PARAM_PATH = find_parameters_file()


def read_counts() -> Tuple[int, int]:
    content = PARAM_PATH.read_text(encoding="utf-8", errors="ignore")

    rx_match = re.search(r"rx_count\s*:\s*int\s*=\s*(\d+)", content)
    ris_match = re.search(r"ris_count\s*:\s*int\s*=\s*(\d+)", content)

    if not rx_match:
        raise ValueError("Nie udało się odczytać rx_count z parameters.py")
    if not ris_match:
        raise ValueError("Nie udało się odczytać ris_count z parameters.py")

    return int(rx_match.group(1)), int(ris_match.group(1))


# ============================================================
# SSH
# ============================================================
def run_ssh(ip: str, remote_command: str) -> Tuple[bool, str]:
    ip = (ip or "").strip()
    if not ip:
        return False, "brak IP"

    try:
        # StrictHostKeyChecking=no upraszcza pierwsze połączenie.
        cmd = [
            "ssh",
            "-o",
            "StrictHostKeyChecking=no",
            "-o",
            "ConnectTimeout=5",
            ip,
            remote_command,
        ]
        subprocess.Popen(cmd)
        return True, "OK"
    except Exception as exc:
        return False, f"Błąd SSH: {exc}"


# ============================================================
# DANE KOMPONENTÓW
# ============================================================
def build_components() -> List[Dict[str, object]]:
    rx_count, ris_count = read_counts()

    components: List[Dict[str, object]] = [
        {"kind": "generator", "idx": 0, "label": "Generator 0"}
    ]

    for i in range(ris_count):
        components.append({"kind": "ris", "idx": i, "label": f"RIS {i}"})

    for i in range(rx_count):
        components.append({"kind": "rx", "idx": i, "label": f"RX {i}"})

    return components


# ============================================================
# UI
# ============================================================
app = Dash(__name__)
server = app.server
app.title = "ContRIS Remote GUI"

CARD_STYLE = {
    "background": "#ffffff",
    "border": "1px solid #d9e2f1",
    "borderRadius": "18px",
    "padding": "18px",
    "boxShadow": "0 6px 20px rgba(16, 24, 40, 0.08)",
}

BUTTON_STYLE = {
    "padding": "10px 16px",
    "borderRadius": "10px",
    "border": "none",
    "fontWeight": "600",
    "cursor": "pointer",
}

INPUT_STYLE = {
    "width": "100%",
    "padding": "12px 14px",
    "borderRadius": "10px",
    "border": "1px solid #c9d4e5",
    "fontSize": "15px",
    "boxSizing": "border-box",
}


def component_card(item: Dict[str, object]) -> html.Div:
    key = f"{item['kind']}-{item['idx']}"

    return html.Div(
        [
            html.Div(
                [
                    html.Div(item["label"], style={"fontSize": "22px", "fontWeight": "700"}),
                    html.Div(
                        id={"type": "status", "index": key},
                        children="Nieuruchomiony",
                        style={
                            "fontSize": "14px",
                            "padding": "6px 10px",
                            "borderRadius": "999px",
                            "background": "#eef2ff",
                            "color": "#3730a3",
                            "display": "inline-block",
                        },
                    ),
                ],
                style={"display": "flex", "justifyContent": "space-between", "alignItems": "center", "gap": "12px"},
            ),
            html.Div(style={"height": "14px"}),
            dcc.Input(
                id={"type": "ip", "index": key},
                placeholder=f"IP dla {item['label']}",
                style=INPUT_STYLE,
            ),
            html.Div(style={"height": "14px"}),
            html.Div(
                [
                    html.Button(
                        "Start",
                        id={"type": "start", "index": key},
                        n_clicks=0,
                        style={**BUTTON_STYLE, "background": "#2563eb", "color": "white"},
                    ),
                    html.Button(
                        "Stop",
                        id={"type": "stop", "index": key},
                        n_clicks=0,
                        style={**BUTTON_STYLE, "background": "#e5e7eb", "color": "#111827"},
                    ),
                ],
                style={"display": "flex", "gap": "10px", "flexWrap": "wrap"},
            ),
        ],
        style=CARD_STYLE,
    )


app.layout = html.Div(
    [
        dcc.Store(id="components-store", data=build_components()),
        dcc.Store(id="status-store", data={}),
        html.Div(
            [
                html.H1("ContRIS Remote GUI", style={"margin": "0", "fontSize": "42px"}),
                html.Div(
                    "Zdalne sterowanie generatorem, RIS-ami i odbiornikami",
                    style={"fontSize": "16px", "color": "#475467", "marginTop": "8px"},
                ),
            ]
        ),
        html.Div(style={"height": "24px"}),
        html.Div(
            [
                html.Button(
                    "Refresh lokalnego parameters.py",
                    id="refresh-layout",
                    n_clicks=0,
                    style={**BUTTON_STYLE, "background": "#111827", "color": "white"},
                ),
                html.Button(
                    "Start all",
                    id="start-all",
                    n_clicks=0,
                    style={**BUTTON_STYLE, "background": "#16a34a", "color": "white"},
                ),
                html.Button(
                    "Stop all",
                    id="stop-all",
                    n_clicks=0,
                    style={**BUTTON_STYLE, "background": "#dc2626", "color": "white"},
                ),
                html.Div(id="global-info", style={"fontSize": "14px", "color": "#475467", "marginLeft": "8px"}),
            ],
            style={
                "display": "flex",
                "gap": "12px",
                "alignItems": "center",
                "flexWrap": "wrap",
                "marginBottom": "22px",
            },
        ),
        html.Div(id="cards-container"),
    ],
    style={
        "maxWidth": "1400px",
        "margin": "0 auto",
        "padding": "28px",
        "fontFamily": "Inter, Segoe UI, Arial, sans-serif",
        "background": "linear-gradient(180deg, #f8fbff 0%, #eef4ff 100%)",
        "minHeight": "100vh",
    },
)


@app.callback(
    Output("components-store", "data"),
    Output("global-info", "children"),
    Input("refresh-layout", "n_clicks"),
    prevent_initial_call=True,
)
def refresh_components(_):
    try:
        # Refresh czyta lokalny plik helpers/parameters.py z tego komputera,
        # z katalogu ustawionego w REPO_DIR / PARAMETER_CANDIDATES.
        components = build_components()
        rx_count = sum(1 for c in components if c["kind"] == "rx")
        ris_count = sum(1 for c in components if c["kind"] == "ris")
        return components, f"Odświeżono lokalnie z parameters.py: generator=1, ris={ris_count}, rx={rx_count}"
    except Exception as exc:
        return no_update, f"Błąd lokalnego odczytu parameters.py: {exc}"


@app.callback(
    Output("cards-container", "children"),
    Input("components-store", "data"),
)
def render_cards(components):
    return html.Div(
        [component_card(item) for item in components],
        style={"display": "grid", "gridTemplateColumns": "repeat(auto-fit, minmax(360px, 1fr))", "gap": "18px"},
    )


@app.callback(
    Output("status-store", "data", allow_duplicate=True),
    Output("global-info", "children", allow_duplicate=True),
    Input({"type": "start", "index": ALL}, "n_clicks"),
    Input({"type": "stop", "index": ALL}, "n_clicks"),
    State({"type": "ip", "index": ALL}, "value"),
    State({"type": "ip", "index": ALL}, "id"),
    State("status-store", "data"),
    prevent_initial_call=True,
)
def handle_single_actions(_start_clicks, _stop_clicks, ips, ip_ids, status_data):
    triggered = ctx.triggered_id
    if triggered is None:
        raise PreventUpdate

    status_data = status_data or {}
    key = triggered["index"]
    action = triggered["type"]

    ip_map = {item_id["index"]: (ip or "") for item_id, ip in zip(ip_ids, ips)}
    ip = ip_map.get(key, "").strip()

    kind, idx_str = key.split("-")
    idx = int(idx_str)

    if action == "start":
        ok, msg = run_ssh(ip, build_start_command(kind, idx))
        status_data[key] = f"Uruchomiony ({ip})" if ok else f"Błąd startu: {msg}"
        return status_data, f"Start: {kind} {idx}"

    if action == "stop":
        ok, msg = run_ssh(ip, build_stop_command(kind, idx))
        status_data[key] = f"Zatrzymany ({ip})" if ok else f"Błąd stopu: {msg}"
        return status_data, f"Stop: {kind} {idx}"

    raise PreventUpdate


@app.callback(
    Output("status-store", "data", allow_duplicate=True),
    Output("global-info", "children", allow_duplicate=True),
    Input("start-all", "n_clicks"),
    Input("stop-all", "n_clicks"),
    State("components-store", "data"),
    State({"type": "ip", "index": ALL}, "value"),
    State({"type": "ip", "index": ALL}, "id"),
    State("status-store", "data"),
    prevent_initial_call=True,
)
def handle_bulk_actions(start_all_clicks, stop_all_clicks, components, ips, ip_ids, status_data):
    if not ctx.triggered_id:
        raise PreventUpdate

    status_data = status_data or {}
    ip_map = {item_id["index"]: (ip or "") for item_id, ip in zip(ip_ids, ips)}

    if ctx.triggered_id == "start-all":
        for item in components:
            key = f"{item['kind']}-{item['idx']}"
            ip = ip_map.get(key, "").strip()
            ok, msg = run_ssh(ip, build_start_command(item["kind"], item["idx"]))
            status_data[key] = f"Uruchomiony ({ip})" if ok else f"Błąd startu: {msg}"
            time.sleep(START_ALL_DELAY_SEC)
        return status_data, "Wykonano Start all"

    if ctx.triggered_id == "stop-all":
        for item in components:
            key = f"{item['kind']}-{item['idx']}"
            ip = ip_map.get(key, "").strip()
            ok, msg = run_ssh(ip, build_stop_command(item["kind"], item["idx"]))
            status_data[key] = f"Zatrzymany ({ip})" if ok else f"Błąd stopu: {msg}"
            time.sleep(STOP_ALL_DELAY_SEC)
        return status_data, "Wykonano Stop all"

    raise PreventUpdate


@app.callback(
    Output({"type": "status", "index": ALL}, "children"),
    Input("status-store", "data"),
    State({"type": "status", "index": ALL}, "id"),
)
def sync_statuses(status_data, status_ids):
    status_data = status_data or {}
    result = []
    for item_id in status_ids:
        result.append(status_data.get(item_id["index"], "Nieuruchomiony"))
    return result


if __name__ == "__main__":
    app.run(debug=True)
