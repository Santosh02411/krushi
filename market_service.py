import requests
import json
import random
from datetime import datetime, timedelta

class MarketService:
    def __init__(self, api_key):
        self.api_key = api_key
        self.base_prices = {
            # Cereals
            'rice': 2500, 'wheat': 2000, 'maize': 1800, 'barley': 1600, 'bajra': 1400,
            'jowar': 1500, 'ragi': 1700,
            # Cash Crops
            'cotton': 5500, 'sugarcane': 350, 'jute': 4200, 'tobacco': 8000,
            # Pulses
            'soybean': 4000, 'groundnut': 5000, 'chickpea': 4500, 'pigeon_pea': 3800,
            'black_gram': 6000, 'green_gram': 5500, 'lentil': 5200,
            # Vegetables
            'tomato': 2000, 'potato': 1200, 'onion': 1500, 'cabbage': 800,
            'cauliflower': 1000, 'brinjal': 1800, 'okra': 2200, 'chili': 8000,
            'cucumber': 1200, 'bitter_gourd': 2500, 'bottle_gourd': 1000,
            # Spices
            'turmeric': 12000, 'ginger': 8000, 'coriander': 6000, 'cumin': 25000,
            'fenugreek': 4000,
            # Fruits
            'mango': 3000, 'banana': 1500, 'grapes': 4000, 'pomegranate': 6000,
            # Oilseeds
            'sunflower': 4500, 'mustard': 4200, 'sesame': 8000, 'safflower': 4000
        }
    
    def get_price_trend(self, crop):
        """Get price trend data for a crop"""
        try:
            # Since we don't have a real market API, we'll generate realistic mock data
            return self._generate_price_trend(crop)
            
        except Exception as e:
            print(f"Market API error: {e}")
            return self._generate_price_trend(crop)
    
    def predict_prices(self, crop):
        """Predict future prices for a crop"""
        try:
            current_price = self.base_prices.get(crop.lower(), 2000)
            predictions = []
            
            # Generate predictions for next 6 months
            for i in range(6):
                # Add some realistic price variation
                variation = random.uniform(-0.15, 0.20)  # -15% to +20%
                seasonal_factor = self._get_seasonal_factor(crop, i)
                
                predicted_price = current_price * (1 + variation + seasonal_factor)
                
                future_date = datetime.now() + timedelta(days=30 * (i + 1))
                predictions.append({
                    'month': future_date.strftime('%B %Y'),
                    'predicted_price': round(predicted_price, 2),
                    'confidence': random.uniform(70, 90),
                    'trend': 'up' if variation > 0 else 'down'
                })
            
            return predictions
            
        except Exception as e:
            print(f"Price prediction error: {e}")
            return []
    
    def _generate_price_trend(self, crop):
        """Generate realistic price trend data"""
        base_price = self.base_prices.get(crop.lower(), 2000)
        trend_data = []
        
        # Generate data for last 12 months
        for i in range(12):
            date = datetime.now() - timedelta(days=30 * (11 - i))
            
            # Add seasonal and random variations
            seasonal_factor = self._get_seasonal_factor(crop, i)
            random_factor = random.uniform(-0.10, 0.15)
            
            price = base_price * (1 + seasonal_factor + random_factor)
            
            trend_data.append({
                'date': date.strftime('%Y-%m-%d'),
                'price': round(price, 2),
                'volume': random.randint(1000, 5000),  # Trading volume
                'market': random.choice(['Delhi', 'Mumbai', 'Chennai', 'Kolkata'])
            })
        
        # Calculate trend indicators
        recent_prices = [item['price'] for item in trend_data[-3:]]
        older_prices = [item['price'] for item in trend_data[-6:-3]]
        
        trend_direction = 'up' if sum(recent_prices) > sum(older_prices) else 'down'
        volatility = self._calculate_volatility([item['price'] for item in trend_data])
        
        return {
            'crop': crop,
            'current_price': trend_data[-1]['price'],
            'trend_direction': trend_direction,
            'volatility': volatility,
            'historical_data': trend_data,
            'market_analysis': self._get_market_analysis(crop, trend_direction, volatility)
        }
    
    def _get_seasonal_factor(self, crop, month_offset):
        """Get seasonal price variation factor for crops"""
        seasonal_patterns = {
            'rice': [0.1, 0.05, -0.05, -0.1, -0.15, -0.1, 0.0, 0.05, 0.1, 0.15, 0.1, 0.05],
            'wheat': [0.15, 0.1, 0.05, -0.05, -0.1, -0.15, -0.1, 0.0, 0.05, 0.1, 0.15, 0.1],
            'cotton': [0.0, 0.05, 0.1, 0.15, 0.1, 0.05, -0.05, -0.1, -0.15, -0.1, -0.05, 0.0],
            'tomato': [0.2, 0.15, 0.1, 0.0, -0.1, -0.15, -0.1, 0.0, 0.1, 0.15, 0.2, 0.15],
            'onion': [0.1, 0.15, 0.2, 0.1, 0.0, -0.1, -0.15, -0.1, 0.0, 0.05, 0.1, 0.05]
        }
        
        pattern = seasonal_patterns.get(crop.lower(), [0] * 12)
        return pattern[month_offset % 12]
    
    def _calculate_volatility(self, prices):
        """Calculate price volatility"""
        if len(prices) < 2:
            return 0
        
        avg_price = sum(prices) / len(prices)
        variance = sum((price - avg_price) ** 2 for price in prices) / len(prices)
        volatility = (variance ** 0.5) / avg_price * 100
        
        return round(volatility, 2)
    
    def _get_market_analysis(self, crop, trend, volatility):
        """Generate market analysis text"""
        analysis = []
        
        if trend == 'up':
            analysis.append(f"{crop.title()} prices are showing an upward trend.")
        else:
            analysis.append(f"{crop.title()} prices are declining.")
        
        if volatility > 15:
            analysis.append("High price volatility indicates market uncertainty.")
        elif volatility < 5:
            analysis.append("Low volatility suggests stable market conditions.")
        else:
            analysis.append("Moderate volatility indicates normal market fluctuations.")
        
        # Add crop-specific insights
        crop_insights = {
            'rice': "Monsoon patterns and government procurement policies significantly impact rice prices.",
            'wheat': "International wheat prices and domestic production levels are key factors.",
            'cotton': "Global textile demand and fiber quality affect cotton pricing.",
            'tomato': "Seasonal supply variations cause significant price fluctuations.",
            'onion': "Storage capacity and export policies influence onion prices."
        }
        
        if crop.lower() in crop_insights:
            analysis.append(crop_insights[crop.lower()])
        
        return " ".join(analysis)
    
    def get_market_news(self, crop=None):
        """Get market news and updates"""
        # Mock market news data
        news_items = [
            {
                'title': 'Monsoon forecast positive for Kharif crops',
                'summary': 'IMD predicts normal rainfall, benefiting rice and cotton cultivation.',
                'date': datetime.now().strftime('%Y-%m-%d'),
                'impact': 'positive'
            },
            {
                'title': 'Export demand for wheat increases',
                'summary': 'International buyers showing interest in Indian wheat varieties.',
                'date': (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d'),
                'impact': 'positive'
            },
            {
                'title': 'Storage facilities expansion announced',
                'summary': 'Government plans to increase cold storage capacity for vegetables.',
                'date': (datetime.now() - timedelta(days=2)).strftime('%Y-%m-%d'),
                'impact': 'positive'
            }
        ]
        
        if crop:
            # Filter news relevant to specific crop
            relevant_news = [item for item in news_items if crop.lower() in item['title'].lower() or crop.lower() in item['summary'].lower()]
            return relevant_news if relevant_news else news_items[:2]
        
        return news_items
