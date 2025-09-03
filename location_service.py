import google.generativeai as genai
import requests
import json
import os
from dotenv import load_dotenv

load_dotenv()

class LocationService:
    def __init__(self):
        self.gemini_api_key = os.getenv('GEMINI_API_KEY')
        if self.gemini_api_key:
            genai.configure(api_key=self.gemini_api_key)
            self.model = genai.GenerativeModel('gemini-pro')
    
    def get_location_from_ip(self):
        """Get location from IP address"""
        try:
            response = requests.get('http://ip-api.com/json/', timeout=5)
            data = response.json()
            
            if data['status'] == 'success':
                return {
                    'city': data['city'],
                    'region': data['regionName'],
                    'country': data['country'],
                    'lat': data['lat'],
                    'lon': data['lon'],
                    'location_string': f"{data['city']}, {data['regionName']}"
                }
        except Exception as e:
            print(f"IP location error: {e}")
        
        return None
    
    def enhance_location_with_gemini(self, location_string):
        """Use Gemini to get detailed location information"""
        if not self.gemini_api_key or self.gemini_api_key.strip() == "":
            print("No Gemini API key provided, using basic location info")
            return self._get_basic_location_info(location_string)
        
        try:
            prompt = f"""
            Analyze this location for agricultural purposes: {location_string}
            
            Provide information in this exact JSON format:
            {{
                "city": "city name",
                "state": "state name", 
                "climate_zone": "tropical/subtropical/temperate/arid",
                "avg_temperature": temperature_in_celsius,
                "avg_rainfall": rainfall_in_mm,
                "soil_types": ["common", "soil", "types"],
                "major_crops": ["crop1", "crop2", "crop3"],
                "agricultural_season": "kharif/rabi/both",
                "water_sources": ["river", "groundwater", "canal"],
                "farming_challenges": ["challenge1", "challenge2"]
            }}
            
            Only return the JSON, no other text.
            """
            
            print(f"Calling Gemini API for location analysis: {location_string}")
            response = self.model.generate_content(prompt)
            
            # Clean the response text
            response_text = response.text.strip()
            if response_text.startswith('```json'):
                response_text = response_text[7:-3]
            elif response_text.startswith('```'):
                response_text = response_text[3:-3]
            
            location_data = json.loads(response_text)
            print(f"Gemini API success for {location_string}")
            
            return location_data
            
        except Exception as e:
            print(f"Gemini location analysis error: {e}")
            return self._get_basic_location_info(location_string)
    
    def _get_basic_location_info(self, location_string):
        """Fallback location information"""
        # Basic location database
        location_db = {
            'delhi': {
                'city': 'Delhi', 'state': 'Delhi', 'climate_zone': 'subtropical',
                'avg_temperature': 25, 'avg_rainfall': 650,
                'soil_types': ['alluvial', 'loamy'], 'major_crops': ['wheat', 'rice', 'sugarcane'],
                'agricultural_season': 'both', 'water_sources': ['yamuna', 'groundwater'],
                'farming_challenges': ['water_scarcity', 'pollution']
            },
            'mumbai': {
                'city': 'Mumbai', 'state': 'Maharashtra', 'climate_zone': 'tropical',
                'avg_temperature': 27, 'avg_rainfall': 2200,
                'soil_types': ['laterite', 'alluvial'], 'major_crops': ['rice', 'cotton', 'sugarcane'],
                'agricultural_season': 'kharif', 'water_sources': ['rivers', 'wells'],
                'farming_challenges': ['flooding', 'soil_erosion']
            },
            'bangalore': {
                'city': 'Bangalore', 'state': 'Karnataka', 'climate_zone': 'tropical',
                'avg_temperature': 23, 'avg_rainfall': 900,
                'soil_types': ['red', 'laterite'], 'major_crops': ['ragi', 'maize', 'vegetables'],
                'agricultural_season': 'both', 'water_sources': ['lakes', 'borewells'],
                'farming_challenges': ['water_table_depletion', 'urbanization']
            }
        }
        
        city_key = location_string.lower().split(',')[0].strip()
        return location_db.get(city_key, location_db['delhi'])
