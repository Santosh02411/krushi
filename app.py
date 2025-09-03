from flask import Flask, render_template, request, jsonify
from flask_cors import CORS
import os
from dotenv import load_dotenv
import sqlite3
from ml_models import CropRecommendationModel, WaterManagementAdvisor
from weather_service import WeatherService
from market_service import MarketService
from location_service import LocationService

# Load environment variables
load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', 'krushi-secret-key')
CORS(app)

# Initialize services
crop_model = CropRecommendationModel()
water_advisor = WaterManagementAdvisor()
weather_service = WeatherService(os.getenv('OPENWEATHER_API_KEY'))
market_service = MarketService(os.getenv('MARKET_API_KEY'))
location_service = LocationService()

def init_db():
    """Initialize the database"""
    conn = sqlite3.connect('krushi.db')
    cursor = conn.cursor()
    
    # Create users table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            location TEXT NOT NULL,
            farm_size REAL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Create recommendations table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS recommendations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            soil_type TEXT,
            climate_data TEXT,
            water_availability TEXT,
            recommended_crops TEXT,
            confidence_score REAL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    ''')
    
    conn.commit()
    conn.close()

@app.route('/')
def index():
    """Main dashboard page"""
    return render_template('index.html')

@app.route('/api/recommend-crops', methods=['POST'])
def recommend_crops():
    """Get crop recommendations based on input parameters"""
    try:
        data = request.json
        
        # Extract parameters
        soil_type = data.get('soil_type')
        location = data.get('location')
        water_availability = data.get('water_availability')
        farm_size = data.get('farm_size', 1.0)
        
        # Get weather data for location
        weather_data = weather_service.get_current_weather(location)
        
        # Get crop recommendations
        recommendations = crop_model.recommend_crops(
            soil_type=soil_type,
            temperature=weather_data.get('temperature', 25),
            humidity=weather_data.get('humidity', 60),
            rainfall=weather_data.get('rainfall', 100),
            water_availability=water_availability
        )
        
        # Get market trends for recommended crops
        market_data = {}
        for crop in recommendations[:5]:  # Top 5 crops for market data
            market_data[crop['crop']] = market_service.get_price_trend(crop['crop'])
        
        return jsonify({
            'success': True,
            'recommendations': recommendations,
            'weather': weather_data,
            'market_trends': market_data
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/water-management', methods=['POST'])
def water_management():
    """Get water management advice"""
    try:
        data = request.json
        
        crop_type = data.get('crop_type')
        soil_type = data.get('soil_type')
        location = data.get('location')
        
        # Get weather forecast
        weather_forecast = weather_service.get_forecast(location)
        
        # Get water management advice
        advice = water_advisor.get_irrigation_advice(
            crop_type=crop_type,
            soil_type=soil_type,
            weather_forecast=weather_forecast
        )
        
        return jsonify({
            'success': True,
            'advice': advice,
            'forecast': weather_forecast
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/detect-location')
def detect_location():
    """Auto-detect user location"""
    try:
        location_data = location_service.get_location_from_ip()
        if location_data:
            enhanced_data = location_service.enhance_location_with_gemini(location_data['location_string'])
            return jsonify({
                'success': True,
                'location': location_data['location_string'],
                'details': enhanced_data
            })
        else:
            return jsonify({
                'success': True,
                'location': 'Delhi, India',
                'details': location_service._get_basic_location_info('delhi')
            })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/weather/<location>')
def get_weather(location):
    """Get weather data for a location"""
    try:
        weather_data = weather_service.get_current_weather(location)
        forecast = weather_service.get_forecast(location)
        
        return jsonify({
            'success': True,
            'current': weather_data,
            'forecast': forecast
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/market-trends/<crop>')
def get_market_trends(crop):
    """Get market trends for a specific crop"""
    try:
        trends = market_service.get_price_trend(crop)
        predictions = market_service.predict_prices(crop)
        
        return jsonify({
            'success': True,
            'trends': trends,
            'predictions': predictions
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

if __name__ == '__main__':
    init_db()
    app.run(debug=True, host='0.0.0.0', port=5000)
