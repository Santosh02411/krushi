# Krushi - AI-Based Agricultural Advisory Platform

Krushi is an intelligent web platform that helps farmers make informed decisions about crop selection, water management, and market trends using machine learning and real-time data.

## Features

- **Smart Crop Recommendation**: AI-powered suggestions based on soil type, climate, and water availability
- **Weather Integration**: Real-time weather data and forecasts
- **Market Trends**: Price predictions and market analysis
- **Water Management**: Irrigation scheduling and water conservation tips
- **Farmer-Friendly Interface**: Simple, intuitive design for easy use

## Setup Instructions

1. Install Python dependencies:
   ```bash
   pip install -r requirements.txt
   ```

2. Set up environment variables:
   - Copy `.env.example` to `.env`
   - Add your API keys for weather and market data

3. Run the application:
   ```bash
   python app.py
   ```

4. Open your browser and navigate to `http://localhost:5000`

## API Endpoints

- `/api/recommend-crops` - Get crop recommendations
- `/api/weather` - Get weather data
- `/api/market-trends` - Get market price trends
- `/api/water-management` - Get irrigation advice

## Technology Stack

- **Backend**: Flask (Python)
- **Frontend**: HTML, CSS, JavaScript
- **ML**: Scikit-learn
- **Database**: SQLite
- **APIs**: OpenWeatherMap, Market data APIs
