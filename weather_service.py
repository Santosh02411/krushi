import requests
import json
from datetime import datetime, timedelta

class WeatherService:
    def __init__(self, api_key):
        self.api_key = api_key
        self.base_url = "http://api.openweathermap.org/data/2.5"
    
    def get_current_weather(self, location):
        """Get current weather data for a location"""
        if not self.api_key or self.api_key.strip() == "":
            print("No weather API key provided, using mock data")
            return self._get_mock_weather_data(location)
        
        try:
            url = f"{self.base_url}/weather"
            params = {
                'q': location,
                'appid': self.api_key,
                'units': 'metric'
            }
            
            print(f"Calling weather API for {location}")
            response = requests.get(url, params=params, timeout=10)
            
            if response.status_code == 401:
                print("Weather API key invalid, using mock data")
                return self._get_mock_weather_data(location)
            
            response.raise_for_status()
            data = response.json()
            
            print(f"Weather API success for {location}")
            return {
                'location': data['name'],
                'temperature': round(data['main']['temp'], 1),
                'humidity': data['main']['humidity'],
                'pressure': data['main']['pressure'],
                'weather': data['weather'][0]['description'],
                'wind_speed': round(data['wind']['speed'], 1),
                'rainfall': data.get('rain', {}).get('1h', 0),
                'timestamp': datetime.now().isoformat()
            }
            
        except Exception as e:
            print(f"Weather API error: {e}")
            return self._get_mock_weather_data(location)
    
    def get_forecast(self, location, days=7):
        """Get weather forecast for a location"""
        if not self.api_key or self.api_key.strip() == "":
            print("No weather API key provided, using mock forecast")
            return self._get_mock_forecast_data(days, location)
        
        try:
            url = f"{self.base_url}/forecast"
            params = {
                'q': location,
                'appid': self.api_key,
                'units': 'metric'
            }
            
            print(f"Calling weather forecast API for {location}")
            response = requests.get(url, params=params, timeout=10)
            
            if response.status_code == 401:
                print("Weather API key invalid for forecast, using mock data")
                return self._get_mock_forecast_data(days, location)
            
            response.raise_for_status()
            data = response.json()
            
            forecast = []
            processed_dates = set()
            
            for item in data['list']:
                dt = datetime.fromtimestamp(item['dt'])
                date_str = dt.strftime('%Y-%m-%d')
                
                # Take one forecast per day (prefer noon time)
                if date_str not in processed_dates and len(forecast) < days:
                    forecast.append({
                        'date': date_str,
                        'temperature': round(item['main']['temp'], 1),
                        'humidity': item['main']['humidity'],
                        'weather': item['weather'][0]['description'],
                        'rainfall': item.get('rain', {}).get('3h', 0),
                        'wind_speed': round(item['wind']['speed'], 1)
                    })
                    processed_dates.add(date_str)
            
            print(f"Weather forecast API success for {location}")
            return forecast
            
        except Exception as e:
            print(f"Weather forecast API error: {e}")
            return self._get_mock_forecast_data(days, location)
    
    def _get_mock_weather_data(self, location="Unknown"):
        """Return mock weather data when API is not available"""
        # Generate location-specific mock data
        location_variations = {
            'mumbai': {'temp': 28, 'humidity': 85, 'rainfall': 15},
            'delhi': {'temp': 32, 'humidity': 45, 'rainfall': 2},
            'bangalore': {'temp': 24, 'humidity': 70, 'rainfall': 8},
            'chennai': {'temp': 30, 'humidity': 80, 'rainfall': 12},
            'kolkata': {'temp': 29, 'humidity': 75, 'rainfall': 10},
            'pune': {'temp': 26, 'humidity': 60, 'rainfall': 5},
            'hyderabad': {'temp': 31, 'humidity': 55, 'rainfall': 3}
        }
        
        # Check if location matches any known city
        location_key = location.lower().split(',')[0].strip()
        weather_data = location_variations.get(location_key, {'temp': 25.5, 'humidity': 65, 'rainfall': 0})
        
        return {
            'location': location,
            'temperature': weather_data['temp'],
            'humidity': weather_data['humidity'],
            'pressure': 1013,
            'weather': 'partly cloudy' if weather_data['rainfall'] < 5 else 'light rain',
            'wind_speed': 3.2,
            'rainfall': weather_data['rainfall'],
            'timestamp': datetime.now().isoformat()
        }
    
    def _get_mock_forecast_data(self, days=7, location="Unknown"):
        """Return mock forecast data when API is not available"""
        forecast = []
        base_date = datetime.now()
        
        for i in range(days):
            date = base_date + timedelta(days=i)
            forecast.append({
                'date': date.strftime('%Y-%m-%d'),
                'temperature': 25 + (i % 3) * 2,  # Varying temperature
                'humidity': 60 + (i % 4) * 5,     # Varying humidity
                'weather': ['sunny', 'partly cloudy', 'cloudy', 'light rain'][i % 4],
                'rainfall': [0, 0, 2, 8][i % 4],  # Varying rainfall
                'wind_speed': 2.5 + (i % 3) * 0.5
            })
        
        return forecast
