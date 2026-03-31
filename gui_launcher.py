#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import subprocess
import time
from pathlib import Path

from dash import Dash, html, dcc, Input, Output, State, ALL

ROOT_DIR = Path(__file__).resolve().parent
STATE_FILE = ROOT_DIR / ".gui_launcher_state.json"

app = Dash(__name__)
server = app.server


def read_counts(repo_dir: Path):
    path = repo_dir / "helpers" / "parameters.py"

    if not path.exists():
        alt = repo_dir / "ris_system-final" / "helpers" / "parameters.py"
        if alt.exists():
            path = alt
            repo_dir = repo_dir / "ris_system-final"
        else:
            return None, None, repo_dir

    content = path.read_text()
    rx = int(re.search(r"rx_count\s*:\s*int\s*=\s*(\d+)", content).group(1))
    ris = int(re.search(r"ris_count\s*:\s*int\s*=\s*(\d+)", content).group(1))

    return rx, ris, repo_dir


def component_card(kind, idx):
    return html.Div([
        html.H4(f"{kind.upper()} {idx}"),
        dcc.Input(id={"type": "ip", "index": f"{kind}-{idx}"}, placeholder="IP", style={"width": "100%"}),
        html.Button("Start", id={"type": "start", "index": f"{kind}-{idx}"}),
        html.Button("Stop", id={"type": "stop", "index": f"{kind}-{idx}"}),
        html.Div(id={"type": "status", "index": f"{kind}-{idx}"})
    ], style={"border": "1px solid #ccc", "padding": "10px", "margin": "5px"})


app.layout = html.Div([
    html.H1("ContRIS DASH GUI"),

    dcc.Input(id="repo", value=str(ROOT_DIR), style={"width": "60%"}),
    html.Button("Load", id="load"),

    html.Div(id="components"),
])


@app.callback(
    Output("components", "children"),
    Input("load", "n_clicks"),
    State("repo", "value")
)
def load_components(n, repo):
    if not n:
        return []

    repo = Path(repo)
    rx, ris, repo = read_counts(repo)

    if rx is None:
        return [html.Div("Błąd ścieżki")]

    comps = []

    comps.append(component_card("generator", 0))

    for i in range(ris):
        comps.append(component_card("ris", i))

    for i in range(rx):
        comps.append(component_card("rx", i))

    return comps


@app.callback(
    Output({"type": "status", "index": ALL}, "children"),
    Input({"type": "start", "index": ALL}, "n_clicks"),
    State({"type": "ip", "index": ALL}, "value"),
    prevent_initial_call=True
)
def start_all(btns, ips):
    ctx = dash.callback_context
    if not ctx.triggered:
        return [""] * len(btns)

    trig = ctx.triggered[0]["prop_id"].split(".")[0]
    idx = json.loads(trig)["index"]

    out = []
    for i, ip in enumerate(ips):
        if ip:
            try:
                subprocess.Popen(f"ssh {ip} python3 main.py {idx.split('-')[0]} {idx.split('-')[1]}", shell=True)
                out.append("started")
            except:
                out.append("error")
        else:
            out.append("no ip")

    return out


if __name__ == "__main__":
    app.run(debug=True)
