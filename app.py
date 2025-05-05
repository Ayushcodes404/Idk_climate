from flask import Flask, render_template, request, jsonify
import folium
import plotly.graph_objects as go
import plotly.utils
from weather import get_coordinates, get_weather_aqi_data
import json

app = Flask(__name__)

def create_heatmap(data):
    fig = go.Figure()
    
    # Create separate traces for each parameter
    parameters = {
        'AQI': data.get('us_aqi', 0),
        'PM2.5': data.get('pm25', 0),
        'Ozone': data.get('ozone', 0),
        'Temperature': data.get('actual_temperature_celsius', 0)
    }
    
    fig.add_trace(go.Heatmap(
        z=[list(parameters.values())],
        x=list(parameters.keys()),
        y=['Values'],
        colorscale='RdYlBu_r'
    ))
    
    fig.update_layout(
        title='Climate Parameters Heatmap',
        xaxis_title='Parameters',
        yaxis_title='Intensity'
    )
    
    return json.dumps(fig, cls=plotly.utils.PlotlyJSONEncoder)

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/analyze', methods=['POST'])
def analyze():
    location = request.form.get('location')
    if not location:
        return jsonify({'error': 'Location is required'})

    lat, lon = get_coordinates(location)
    if lat is None or lon is None:
        return jsonify({'error': 'Could not find coordinates for the location'})

    data = get_weather_aqi_data(lat, lon)
    if not data:
        return jsonify({'error': 'Could not fetch weather data'})

    # Create map centered at the location
    map_obj = folium.Map(location=[lat, lon], zoom_start=10)
    folium.Marker(
        [lat, lon],
        popup=f"AQI: {data.get('us_aqi')}<br>PM2.5: {data.get('pm25')}<br>Ozone: {data.get('ozone')}"
    ).add_to(map_obj)

    # Create heatmap
    heatmap_data = create_heatmap(data)

    return jsonify({
        'weather_data': data,
        'map_html': map_obj._repr_html_(),
        'heatmap_data': heatmap_data
    })

if __name__ == '__main__':
    app.run(debug=True)