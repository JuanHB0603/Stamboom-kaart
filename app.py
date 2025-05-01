import dash
from dash import dcc, html, Input, Output
from dash.dependencies import Input, Output, State, MATCH, ALL
from folium.plugins import AntPath
import folium
import pandas as pd 
from flask import Flask
import numpy as np
from datetime import datetime

# 📂 Stap 1: Excel-bestand inlezen
file_path = "Stamboom anoniem.xlsx"  # Vervang dit met jouw bestandsnaam
df = pd.read_excel(
    file_path,
    dtype={"Geboortejaar": "Int64", "Overlijdensjaar": "Int64"},
    engine="openpyxl"  # Explicit engine (veilig voor .xlsx)
)

# Flask-server voor Dash
server = Flask(__name__)
app = dash.Dash(__name__, server=server)

def bezier_curve(p1, p2, control_offset=0.5):
    """Genereer een Bézier-curve tussen twee punten."""
    p1_lat, p1_lon = p1
    p2_lat, p2_lon = p2

    # Controlepunt iets hoger om de boog te laten buigen
    mid_lat = (p1_lat + p2_lat) / 2 + control_offset
    mid_lon = (p1_lon + p2_lon) / 2 + control_offset

    # Bézier-punten berekenen
    t_values = np.linspace(0, 1, num=20)  # Hoe meer punten, hoe vloeiender
    bezier_points = [
        [
            (1 - t) ** 2 * p1_lat + 2 * (1 - t) * t * mid_lat + t ** 2 * p2_lat,
            (1 - t) ** 2 * p1_lon + 2 * (1 - t) * t * mid_lon + t ** 2 * p2_lon
        ]
        for t in t_values
    ]
    
    return bezier_points

def generate_map(start_year, end_year, focus_person=None):
    """Genereer een kaart met familieleden die leefden tussen start_year en end_year."""
    # 📍 Bepaal startlocatie
    default_location = [50.97997636622107, 7.719660025389912]
    zoom_level = 6

    # Als er een focuspersoon is, wijzig de locatie en zoom
    filtered_df = df[(df["Geboortejaar"] <= end_year) & (df["Overlijdensjaar"] >= start_year)]
    if focus_person:
        focus_row = filtered_df[filtered_df["Naam"].str.strip().str.lower() == focus_person.strip().lower()]
        if not focus_row.empty:
            default_location = [focus_row.iloc[0]["Latitude"], focus_row.iloc[0]["Longitude"]]
            zoom_level = 15

    # 🌍 Maak kaart aan met correcte startlocatie en zoom
    m = folium.Map(location=default_location, zoom_start=zoom_level, zoom_control=False)

    for col in ["Geboortejaar", "Overlijdensjaar", "Aantal kinderen", "Generatie", "Leeftijd"]:
        df[col] = pd.to_numeric(df[col], errors="coerce").astype("Int64")

    for _, row in filtered_df.iterrows():
        # Popup-tekst maken
        popup_html = f"""
        <div style="width: 200px;">
            <h4 style="margin-bottom: 5px;">{row['Naam']}</h4>
            <p><b>Geboren:</b> {row['Geboortejaar']}<br>
            <b>Geboorteplaats:</b> {row['Geboorteplaats']}</p>
            <b>Leeftijd:</b> {row['Leeftijd']}<br>
            <b>Generatie:</b> {row['Generatie']}<br>
            <b>Aantal kinderen:</b> {row['Aantal kinderen']}</p>
            <p><b>Vader:</b> {row['Vader']}<br>
            <b>Moeder:</b> {row['Moeder']}</p>
        </div>  
        """
        popup = folium.Popup(html=popup_html, max_width=200)
        folium.Marker(
            location=[row["Latitude"], row["Longitude"]],
            popup=popup,
            icon=folium.Icon(color="blue", icon="user-circle", prefix="fa")
        ).add_to(m)

        # Voeg een lijn toe als deze persoon een ouder heeft
        for ouder_type, kleur in [("Vader", "blue"), ("Moeder", "red")]:
            ouder_naam = row[ouder_type]
            if ouder_naam:
                ouder_row = df[df["Naam"] == ouder_naam]
                if not ouder_row.empty:
                    ouder_locatie = [ouder_row.iloc[0]["Latitude"], ouder_row.iloc[0]["Longitude"]]
                    kind_locatie = [row["Latitude"], row["Longitude"]]
                    curve_points = bezier_curve(ouder_locatie, kind_locatie, control_offset=0.001)

                    # ✨ Geanimeerde lijnen
                    AntPath(
                        locations=curve_points,
                        color=kleur,  # Blauw voor vader, rood voor moeder
                        weight=4,
                        opacity=0.8,
                        dash_array=[10, 20],
                        delay=1000  # Animatie vertragen
                    ).add_to(m)

    # Opslaan als HTML en inladen in Dash
    m.save("map.html")
    with open("map.html", "r", encoding="utf-8") as f:
        map_html = f.read()

    return map_html
    
# Layout van de Dash-app
app.layout = html.Div(className="app-container", children=[
    html.Div(className="map-wrapper", children=[
        html.Iframe(id="map", srcDoc=generate_map(1600, 1800))
    ]),
    
    # 🔘 Slider
    html.Div([
        html.H3("Kies begin- en eindjaar:"),
        dcc.RangeSlider(
            id="year-slider",
            min=1600,
            max=2025,
            value=[1600, 1800],
            marks={str(y): str(y) for y in range(1600, 2025, 50)},
            step=1,
            allowCross=False,
        )
    ], className="slider-container"),

    # ☰ Toggle knop
    html.Button("☰", id="toggle-info-panel", n_clicks=0, className="toggle-button"),

    # ℹ️ Info onderin
    html.Div(id="info-panel", className="info-panel hidden", children=[
        html.H3("Geselecteerd persoon"),
        html.Div(id="persoon-info", style={"minHeight": "150px", "overflowY": "auto"})
    ])
])

@app.callback(
    Output("map", "srcDoc"),
    Output("info-panel", "children"),
    # Output("persoon-info", "children"),
    Input("year-slider", "value"),
    Input({"type": "persoon-button", "index": ALL}, "n_clicks"),
    State({"type": "persoon-button", "index": ALL}, "id")
)

def update_content(selected_years, n_clicks_list, ids):
    start_year, end_year = selected_years
    filtered_df = df[(df["Geboortejaar"] <= end_year) & (df["Overlijdensjaar"] >= start_year)]

    # Genereer knoppen
    person_buttons = [
        html.Button(
            naam,
            id={"type": "persoon-button", "index": naam},
            className="knop",
            n_clicks=0
        )
        for naam in filtered_df["Naam"]
    ]

    # Check wie er is aangeklikt
    focus_person = None
    if any(n_clicks_list):
        clicked_idx = n_clicks_list.index(max(n_clicks_list))  # hoogste klikwaarde
        focus_person = ids[clicked_idx]["index"]
    
    # Huidig jaartal ophalen
    current_year = datetime.now().year

    # 🔍 Info-balk: Extra details van geselecteerde persoon
    persoon_info = html.Div("Klik op een persoon om details te zien.")  # Default message
    # info_class = "info-panel hidden"  # Standaardwaarde voor info_class
    if focus_person:
        # info_class = "info-panel visible"  # Update info_class als er een focuspersoon is
        focus_row = filtered_df[filtered_df["Naam"] == focus_person]
        if not focus_row.empty:
            overlijdensjaar = focus_row.iloc[0]["Overlijdensjaar"]
        # Controleer of overlijdensjaar niet gelijk is aan het huidige jaartal
            overlijdensjaar_text = (
            f"Overlijdensjaar: {overlijdensjaar}" 
            if not pd.isna(overlijdensjaar) and overlijdensjaar != current_year 
            else ""
        )
        
        persoon_info = html.Details([
            html.Summary(focus_row.iloc[0]["Naam"]),
            html.P(f"Geboortejaar: {focus_row.iloc[0]['Geboortejaar']}"),
            html.P(overlijdensjaar_text),
            html.P(f"Leeftijd: {focus_row.iloc[0]['Leeftijd']}"),
            html.P(f"Geboorteplaats: {focus_row.iloc[0]['Geboorteplaats']}"),
            html.P(f"Aantal kinderen: {focus_row.iloc[0]['Aantal kinderen']}"),
            html.P(f"Generatie: {focus_row.iloc[0]['Generatie']}"),
            html.P(f"Vader: {focus_row.iloc[0]['Vader']}"),
            html.P(f"Moeder: {focus_row.iloc[0]['Moeder']}"),
            html.P(f"Biografie: {focus_row.iloc[0]['Bio']}"),
        ])
            
    # Combineer knoppen en info
    info_panel = html.Div([
        *person_buttons,
        persoon_info
    ])

    return generate_map(start_year, end_year, focus_person), info_panel, 

@app.callback(
    Output("info-panel", "className"),
    Input("toggle-info-panel", "n_clicks"),
    prevent_initial_call=True
)
def toggle_info_panel(n_clicks):
    if n_clicks and n_clicks % 2 == 1:
        return "info-panel visible"
    return "info-panel hidden"

if __name__ == "__main__":
    app.run(debug=True, use_reloader=False)
