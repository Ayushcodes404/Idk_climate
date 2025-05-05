import requests
import geopy
from geopy.geocoders import Nominatim
import json
import sys
from datetime import datetime

# --- Helper Functions ---

def get_coordinates(location_name):
    """Converts a location name to latitude and longitude using OpenStreetMap."""
    print(f"\nGeocoding location: '{location_name}'...")
    try:
        geolocator = Nominatim(user_agent="weather_proxy_script_v2") # Use a descriptive user agent
        location = geolocator.geocode(location_name, timeout=10)
        if location:
            print(f"Found coordinates: Lat={location.latitude:.4f}, Lon={location.longitude:.4f}")
            return location.latitude, location.longitude
        else:
            print(f"ERROR: Could not find coordinates for '{location_name}'. Please be more specific or check spelling.")
            return None, None
    except Exception as e:
        print(f"ERROR during geocoding: {e}")
        return None, None

def get_weather_aqi_data(lat, lon):
    """Fetches weather and AQI data from Open-Meteo API."""
    if lat is None or lon is None:
        return None

    print(f"\nFetching data from Open-Meteo for Lat={lat:.4f}, Lon={lon:.4f}...")

    # Construct the Open-Meteo API URL
    # Requesting current weather (temp, humidity, apparent temp) and air quality (US AQI, PM2.5, Ozone)
    # CAMS Global is the source for AQI data here
    base_url = "https://api.open-meteo.com/v1/forecast"
    aqi_url = "https://air-quality-api.open-meteo.com/v1/air-quality"

    weather_params = {
        "latitude": lat,
        "longitude": lon,
        "current": "temperature_2m,relative_humidity_2m,apparent_temperature",
        "temperature_unit": "celsius", # Or 'fahrenheit'
        "wind_speed_unit": "kmh",
        "precipitation_unit": "mm",
        "timezone": "auto" # Automatically determine timezone
    }

    aqi_params = {
        "latitude": lat,
        "longitude": lon,
        "current": "us_aqi,pm2_5,ozone", # Request US AQI standard, PM2.5, and Ozone
         "domains": "cams_global" # Use global model, alternatives exist for Europe etc.
    }

    results = {}

    try:
        # --- Get Weather Data ---
        response_weather = requests.get(base_url, params=weather_params, timeout=15) # 15 second timeout
        response_weather.raise_for_status() # Raise an exception for bad status codes (4xx or 5xx)
        weather_data = response_weather.json()
        # print("Weather API Response:", json.dumps(weather_data, indent=2)) # Uncomment for debugging

        if "current" in weather_data:
             results['apparent_temperature_celsius'] = weather_data["current"].get("apparent_temperature")
             results['actual_temperature_celsius'] = weather_data["current"].get("temperature_2m")
             results['relative_humidity_percent'] = weather_data["current"].get("relative_humidity_2m")
             results['weather_time'] = weather_data["current"].get("time")
             print("  Fetched current weather data.")
        else:
            print("  WARNING: Could not parse current weather data from API response.")


        # --- Get Air Quality Data ---
        response_aqi = requests.get(aqi_url, params=aqi_params, timeout=15)
        response_aqi.raise_for_status()
        aqi_data = response_aqi.json()
        # print("AQI API Response:", json.dumps(aqi_data, indent=2)) # Uncomment for debugging

        if "current" in aqi_data:
            results['us_aqi'] = aqi_data["current"].get("us_aqi")
            results['pm25'] = aqi_data["current"].get("pm2_5") # µg/m³
            results['ozone'] = aqi_data["current"].get("ozone") # µg/m³
            results['aqi_time'] = aqi_data["current"].get("time")
            print("  Fetched current air quality data.")
        else:
            print("  WARNING: Could not parse current air quality data from API response.")


        print("Data fetching finished.")
        return results

    except requests.exceptions.RequestException as e:
        print(f"\nERROR: Could not connect to Open-Meteo API or request failed.")
        print(f"  Details: {e}")
        return None
    except json.JSONDecodeError:
        print("\nERROR: Could not decode the JSON response from the API.")
        return None
    except Exception as e:
        print(f"\nERROR: An unexpected error occurred during data fetching: {e}")
        return None

# --- Main Execution ---
if __name__ == "__main__":
    # Get location from command line arguments or prompt for input
    if len(sys.argv) > 1:
        location_input = ' '.join(sys.argv[1:])  # Join all arguments as location
    else:
        try:
            location_input = input("Enter a location (e.g., 'Paris, France', 'New York City', 'Tokyo'): ").strip()
            if not location_input:
                print("Error: Location cannot be empty.")
                sys.exit(1)
        except EOFError:
            print("\nError: No input provided.")
            sys.exit(1)
        except KeyboardInterrupt:
            print("\nOperation cancelled by user.")
            sys.exit(1)

    latitude, longitude = get_coordinates(location_input)

    if latitude is not None and longitude is not None:
        analysis_results = get_weather_aqi_data(latitude, longitude)

        print("\n--- Analysis Results (using free Open-Meteo API) ---")
        if analysis_results:
            # Proxy for "Trapped Heat" -> Apparent Temperature
            apparent_temp = analysis_results.get('apparent_temperature_celsius')
            actual_temp = analysis_results.get('actual_temperature_celsius')
            humidity = analysis_results.get('relative_humidity_percent')
            weather_time_str = analysis_results.get('weather_time', 'N/A')
            try:
                weather_dt = datetime.fromisoformat(weather_time_str).strftime('%Y-%m-%d %H:%M %Z') if weather_time_str != 'N/A' else 'N/A'
            except:
                weather_dt = weather_time_str # Keep original if parsing fails

            print(f"\nProxy for Current 'Heat Stress' (Time: {weather_dt}):")
            if apparent_temp is not None:
                print(f"  > Apparent Temperature (Feels Like): {apparent_temp:.1f} °C")
                print(f"  > Actual Temperature:              {actual_temp:.1f} °C")
                print(f"  > Relative Humidity:             {humidity:.0f} %")
                if apparent_temp > 32: # NOAA Heat Index Caution levels
                     print("  Interpretation: Heat index suggests caution or higher risk.")
                elif apparent_temp > 27:
                     print("  Interpretation: Becoming noticeably warm/humid.")
                else:
                     print("  Interpretation: Generally comfortable or cool.")
            else:
                print("  Apparent temperature data could not be retrieved.")

            # Proxy for "Carbon Emission Index" -> Air Quality Index / Pollutants
            aqi = analysis_results.get('us_aqi')
            pm25 = analysis_results.get('pm25')
            ozone = analysis_results.get('ozone')
            aqi_time_str = analysis_results.get('aqi_time', 'N/A')
            try:
                aqi_dt = datetime.fromisoformat(aqi_time_str).strftime('%Y-%m-%d %H:%M %Z') if aqi_time_str != 'N/A' else 'N/A'
            except:
                 aqi_dt = aqi_time_str # Keep original if parsing fails

            print(f"\n*Indirect* Proxy related to Local Pollution Sources (Time: {aqi_dt}):")
            print("  (Note: This AQI data is NOT a direct measure of CO2 or carbon emissions,")
            print("   but high pollutant levels often correlate with combustion activities.)")
            if aqi is not None:
                print(f"  > US Air Quality Index (AQI): {aqi:.0f}")
                # Basic AQI categories (US standard)
                if aqi <= 50: cat = "Good"
                elif aqi <= 100: cat = "Moderate"
                elif aqi <= 150: cat = "Unhealthy for Sensitive Groups"
                elif aqi <= 200: cat = "Unhealthy"
                elif aqi <= 300: cat = "Very Unhealthy"
                else: cat = "Hazardous"
                print(f"    Interpretation: {cat}")
            else:
                print("  US AQI data could not be retrieved.")

            if pm25 is not None:
                print(f"  > PM2.5 Concentration: {pm25:.1f} µg/m³")
            else:
                 print("  PM2.5 data could not be retrieved.")

            if ozone is not None:
                 print(f"  > Ozone Concentration: {ozone:.1f} µg/m³")
            else:
                 print("  Ozone data could not be retrieved.")

        else:
            print("Analysis could not be completed due to errors during data fetching.")

    else:
        print("Exiting due to inability to find coordinates.")