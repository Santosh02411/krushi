import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import LabelEncoder
import joblib
import os

class CropRecommendationModel:
    def __init__(self):
        self.model = None
        self.label_encoders = {}
        self.crop_data = self._load_crop_database()
        self._train_model()
    
    def _load_crop_database(self):
        """Load comprehensive crop database with characteristics"""
        crops_data = {
            # Cereals
            'rice': {
                'soil_types': ['clay', 'loamy', 'alluvial'],
                'temp_range': (20, 35),
                'humidity_range': (80, 95),
                'rainfall_range': (150, 300),
                'water_requirement': 'high',
                'season': 'kharif',
                'market_demand': 'high'
            },
            'wheat': {
                'soil_types': ['loamy', 'clay', 'alluvial'],
                'temp_range': (15, 25),
                'humidity_range': (50, 70),
                'rainfall_range': (50, 100),
                'water_requirement': 'medium',
                'season': 'rabi',
                'market_demand': 'high'
            },
            'maize': {
                'soil_types': ['loamy', 'sandy'],
                'temp_range': (21, 27),
                'humidity_range': (60, 80),
                'rainfall_range': (50, 100),
                'water_requirement': 'medium',
                'season': 'kharif',
                'market_demand': 'medium'
            },
            'barley': {
                'soil_types': ['loamy', 'sandy'],
                'temp_range': (12, 22),
                'humidity_range': (40, 60),
                'rainfall_range': (30, 75),
                'water_requirement': 'low',
                'season': 'rabi',
                'market_demand': 'medium'
            },
            'bajra': {
                'soil_types': ['sandy', 'loamy'],
                'temp_range': (25, 35),
                'humidity_range': (40, 70),
                'rainfall_range': (40, 65),
                'water_requirement': 'low',
                'season': 'kharif',
                'market_demand': 'medium'
            },
            'jowar': {
                'soil_types': ['loamy', 'clay'],
                'temp_range': (26, 30),
                'humidity_range': (50, 70),
                'rainfall_range': (45, 65),
                'water_requirement': 'low',
                'season': 'kharif',
                'market_demand': 'medium'
            },
            'ragi': {
                'soil_types': ['red', 'loamy', 'laterite'],
                'temp_range': (20, 27),
                'humidity_range': (60, 80),
                'rainfall_range': (50, 100),
                'water_requirement': 'medium',
                'season': 'kharif',
                'market_demand': 'medium'
            },
            
            # Cash Crops
            'cotton': {
                'soil_types': ['clay', 'loamy', 'black'],
                'temp_range': (21, 30),
                'humidity_range': (50, 80),
                'rainfall_range': (50, 100),
                'water_requirement': 'high',
                'season': 'kharif',
                'market_demand': 'high'
            },
            'sugarcane': {
                'soil_types': ['loamy', 'clay'],
                'temp_range': (21, 27),
                'humidity_range': (70, 90),
                'rainfall_range': (75, 150),
                'water_requirement': 'very_high',
                'season': 'annual',
                'market_demand': 'medium'
            },
            'jute': {
                'soil_types': ['clay', 'loamy'],
                'temp_range': (24, 35),
                'humidity_range': (80, 90),
                'rainfall_range': (120, 150),
                'water_requirement': 'high',
                'season': 'kharif',
                'market_demand': 'medium'
            },
            'tobacco': {
                'soil_types': ['sandy', 'loamy'],
                'temp_range': (20, 30),
                'humidity_range': (60, 80),
                'rainfall_range': (50, 125),
                'water_requirement': 'medium',
                'season': 'rabi',
                'market_demand': 'medium'
            },
            
            # Pulses
            'soybean': {
                'soil_types': ['loamy', 'clay'],
                'temp_range': (20, 30),
                'humidity_range': (70, 80),
                'rainfall_range': (75, 100),
                'water_requirement': 'medium',
                'season': 'kharif',
                'market_demand': 'medium'
            },
            'groundnut': {
                'soil_types': ['sandy', 'loamy'],
                'temp_range': (20, 30),
                'humidity_range': (50, 70),
                'rainfall_range': (50, 75),
                'water_requirement': 'low',
                'season': 'kharif',
                'market_demand': 'medium'
            },
            'chickpea': {
                'soil_types': ['loamy', 'clay'],
                'temp_range': (20, 30),
                'humidity_range': (60, 80),
                'rainfall_range': (60, 90),
                'water_requirement': 'medium',
                'season': 'rabi',
                'market_demand': 'high'
            },
            'pigeon_pea': {
                'soil_types': ['loamy', 'sandy'],
                'temp_range': (20, 30),
                'humidity_range': (60, 80),
                'rainfall_range': (60, 100),
                'water_requirement': 'medium',
                'season': 'kharif',
                'market_demand': 'medium'
            },
            'black_gram': {
                'soil_types': ['loamy', 'clay'],
                'temp_range': (25, 35),
                'humidity_range': (70, 80),
                'rainfall_range': (60, 100),
                'water_requirement': 'medium',
                'season': 'kharif',
                'market_demand': 'high'
            },
            'green_gram': {
                'soil_types': ['sandy', 'loamy'],
                'temp_range': (25, 30),
                'humidity_range': (60, 80),
                'rainfall_range': (50, 75),
                'water_requirement': 'low',
                'season': 'kharif',
                'market_demand': 'high'
            },
            'lentil': {
                'soil_types': ['loamy', 'clay'],
                'temp_range': (18, 25),
                'humidity_range': (60, 70),
                'rainfall_range': (25, 50),
                'water_requirement': 'low',
                'season': 'rabi',
                'market_demand': 'high'
            },
            
            # Vegetables
            'tomato': {
                'soil_types': ['loamy', 'sandy'],
                'temp_range': (20, 25),
                'humidity_range': (60, 80),
                'rainfall_range': (50, 100),
                'water_requirement': 'medium',
                'season': 'both',
                'market_demand': 'high'
            },
            'potato': {
                'soil_types': ['loamy', 'sandy'],
                'temp_range': (15, 20),
                'humidity_range': (80, 90),
                'rainfall_range': (50, 70),
                'water_requirement': 'medium',
                'season': 'rabi',
                'market_demand': 'high'
            },
            'onion': {
                'soil_types': ['loamy', 'sandy'],
                'temp_range': (13, 24),
                'humidity_range': (70, 80),
                'rainfall_range': (25, 50),
                'water_requirement': 'low',
                'season': 'rabi',
                'market_demand': 'high'
            },
            'cabbage': {
                'soil_types': ['loamy', 'clay'],
                'temp_range': (15, 20),
                'humidity_range': (80, 90),
                'rainfall_range': (60, 100),
                'water_requirement': 'medium',
                'season': 'rabi',
                'market_demand': 'medium'
            },
            'cauliflower': {
                'soil_types': ['loamy', 'sandy'],
                'temp_range': (15, 20),
                'humidity_range': (80, 90),
                'rainfall_range': (60, 100),
                'water_requirement': 'medium',
                'season': 'rabi',
                'market_demand': 'medium'
            },
            'brinjal': {
                'soil_types': ['loamy', 'sandy'],
                'temp_range': (22, 32),
                'humidity_range': (60, 80),
                'rainfall_range': (60, 100),
                'water_requirement': 'medium',
                'season': 'both',
                'market_demand': 'medium'
            },
            'okra': {
                'soil_types': ['loamy', 'sandy'],
                'temp_range': (24, 27),
                'humidity_range': (60, 80),
                'rainfall_range': (50, 100),
                'water_requirement': 'medium',
                'season': 'kharif',
                'market_demand': 'medium'
            },
            'chili': {
                'soil_types': ['loamy', 'sandy'],
                'temp_range': (20, 30),
                'humidity_range': (60, 80),
                'rainfall_range': (60, 120),
                'water_requirement': 'medium',
                'season': 'both',
                'market_demand': 'high'
            },
            'cucumber': {
                'soil_types': ['sandy', 'loamy'],
                'temp_range': (18, 24),
                'humidity_range': (60, 70),
                'rainfall_range': (50, 100),
                'water_requirement': 'medium',
                'season': 'both',
                'market_demand': 'medium'
            },
            'bitter_gourd': {
                'soil_types': ['loamy', 'sandy'],
                'temp_range': (24, 27),
                'humidity_range': (60, 80),
                'rainfall_range': (60, 100),
                'water_requirement': 'medium',
                'season': 'kharif',
                'market_demand': 'medium'
            },
            'bottle_gourd': {
                'soil_types': ['loamy', 'sandy'],
                'temp_range': (24, 27),
                'humidity_range': (60, 80),
                'rainfall_range': (60, 100),
                'water_requirement': 'medium',
                'season': 'kharif',
                'market_demand': 'medium'
            },
            
            # Spices
            'turmeric': {
                'soil_types': ['loamy', 'clay', 'red'],
                'temp_range': (20, 30),
                'humidity_range': (70, 85),
                'rainfall_range': (150, 250),
                'water_requirement': 'high',
                'season': 'kharif',
                'market_demand': 'high'
            },
            'ginger': {
                'soil_types': ['loamy', 'sandy', 'laterite'],
                'temp_range': (25, 30),
                'humidity_range': (70, 90),
                'rainfall_range': (150, 300),
                'water_requirement': 'high',
                'season': 'kharif',
                'market_demand': 'high'
            },
            'coriander': {
                'soil_types': ['loamy', 'sandy'],
                'temp_range': (20, 30),
                'humidity_range': (60, 70),
                'rainfall_range': (60, 100),
                'water_requirement': 'low',
                'season': 'rabi',
                'market_demand': 'high'
            },
            'cumin': {
                'soil_types': ['sandy', 'loamy'],
                'temp_range': (25, 30),
                'humidity_range': (50, 70),
                'rainfall_range': (30, 50),
                'water_requirement': 'low',
                'season': 'rabi',
                'market_demand': 'high'
            },
            'fenugreek': {
                'soil_types': ['loamy', 'clay'],
                'temp_range': (20, 30),
                'humidity_range': (60, 70),
                'rainfall_range': (40, 60),
                'water_requirement': 'low',
                'season': 'rabi',
                'market_demand': 'medium'
            },
            
            # Fruits
            'mango': {
                'soil_types': ['loamy', 'sandy'],
                'temp_range': (24, 27),
                'humidity_range': (50, 75),
                'rainfall_range': (75, 250),
                'water_requirement': 'medium',
                'season': 'annual',
                'market_demand': 'high'
            },
            'banana': {
                'soil_types': ['loamy', 'clay'],
                'temp_range': (26, 30),
                'humidity_range': (75, 85),
                'rainfall_range': (100, 180),
                'water_requirement': 'high',
                'season': 'annual',
                'market_demand': 'high'
            },
            'grapes': {
                'soil_types': ['sandy', 'loamy'],
                'temp_range': (15, 25),
                'humidity_range': (60, 70),
                'rainfall_range': (50, 100),
                'water_requirement': 'medium',
                'season': 'annual',
                'market_demand': 'high'
            },
            'pomegranate': {
                'soil_types': ['sandy', 'loamy'],
                'temp_range': (15, 35),
                'humidity_range': (35, 65),
                'rainfall_range': (50, 100),
                'water_requirement': 'low',
                'season': 'annual',
                'market_demand': 'high'
            },
            
            # Oilseeds
            'sunflower': {
                'soil_types': ['loamy', 'sandy'],
                'temp_range': (20, 25),
                'humidity_range': (60, 80),
                'rainfall_range': (50, 75),
                'water_requirement': 'medium',
                'season': 'both',
                'market_demand': 'medium'
            },
            'mustard': {
                'soil_types': ['loamy', 'clay'],
                'temp_range': (18, 25),
                'humidity_range': (60, 70),
                'rainfall_range': (25, 40),
                'water_requirement': 'low',
                'season': 'rabi',
                'market_demand': 'medium'
            },
            'sesame': {
                'soil_types': ['sandy', 'loamy'],
                'temp_range': (25, 30),
                'humidity_range': (50, 70),
                'rainfall_range': (50, 65),
                'water_requirement': 'low',
                'season': 'kharif',
                'market_demand': 'medium'
            },
            'safflower': {
                'soil_types': ['loamy', 'clay'],
                'temp_range': (16, 25),
                'humidity_range': (50, 70),
                'rainfall_range': (35, 75),
                'water_requirement': 'low',
                'season': 'rabi',
                'market_demand': 'medium'
            }
        }
        return crops_data
    
    def _generate_training_data(self):
        """Generate synthetic training data based on crop characteristics"""
        data = []
        
        for crop, characteristics in self.crop_data.items():
            # Generate multiple samples for each crop
            for _ in range(100):
                # Generate random values within the crop's optimal ranges
                temp = np.random.uniform(
                    characteristics['temp_range'][0] - 5,
                    characteristics['temp_range'][1] + 5
                )
                humidity = np.random.uniform(
                    characteristics['humidity_range'][0] - 10,
                    characteristics['humidity_range'][1] + 10
                )
                rainfall = np.random.uniform(
                    characteristics['rainfall_range'][0] - 25,
                    characteristics['rainfall_range'][1] + 25
                )
                
                # Random soil type (biased towards suitable ones)
                if np.random.random() < 0.7:
                    soil_type = np.random.choice(characteristics['soil_types'])
                else:
                    soil_type = np.random.choice(['clay', 'loamy', 'sandy', 'black', 'red', 'laterite', 'alluvial'])
                
                # Random water availability
                water_avail = np.random.choice(['low', 'medium', 'high'])
                
                data.append({
                    'soil_type': soil_type,
                    'temperature': temp,
                    'humidity': humidity,
                    'rainfall': rainfall,
                    'water_availability': water_avail,
                    'crop': crop
                })
        
        return pd.DataFrame(data)
    
    def _train_model(self):
        """Train the crop recommendation model"""
        # Generate training data
        df = self._generate_training_data()
        
        # Prepare features
        categorical_features = ['soil_type', 'water_availability']
        numerical_features = ['temperature', 'humidity', 'rainfall']
        
        # Encode categorical variables
        X_encoded = df[numerical_features].copy()
        
        for feature in categorical_features:
            le = LabelEncoder()
            X_encoded[feature] = le.fit_transform(df[feature])
            self.label_encoders[feature] = le
        
        # Prepare target
        y = df['crop']
        
        # Train model
        self.model = RandomForestClassifier(n_estimators=100, random_state=42)
        self.model.fit(X_encoded, y)
    
    def recommend_crops(self, soil_type, temperature, humidity, rainfall, water_availability):
        """Recommend crops based on input parameters"""
        try:
            # Prepare input data
            input_data = pd.DataFrame({
                'temperature': [temperature],
                'humidity': [humidity],
                'rainfall': [rainfall],
                'soil_type': [self.label_encoders['soil_type'].transform([soil_type])[0]],
                'water_availability': [self.label_encoders['water_availability'].transform([water_availability])[0]]
            })
            
            # Get predictions and probabilities
            predictions = self.model.predict(input_data)
            probabilities = self.model.predict_proba(input_data)[0]
            
            # Get top recommendations
            crop_classes = self.model.classes_
            crop_probs = list(zip(crop_classes, probabilities))
            crop_probs.sort(key=lambda x: x[1], reverse=True)
            
            recommendations = []
            for crop, prob in crop_probs[:10]:  # Top 10 recommendations
                crop_info = self.crop_data.get(crop, {})
                suitability = self._calculate_suitability(
                    crop, soil_type, temperature, humidity, rainfall, water_availability
                )
                
                # Adjust confidence based on location-specific factors
                location_factor = self._get_location_factor(temperature, humidity, rainfall)
                adjusted_confidence = min(100, prob * 100 * location_factor)
                
                recommendations.append({
                    'crop': crop,
                    'confidence': round(adjusted_confidence, 2),
                    'suitability_score': suitability,
                    'season': crop_info.get('season', 'unknown'),
                    'water_requirement': crop_info.get('water_requirement', 'medium'),
                    'market_demand': crop_info.get('market_demand', 'medium'),
                    'location_specific_advice': self._get_location_advice(crop, temperature, humidity, rainfall)
                })
            
            return recommendations
            
        except Exception as e:
            # Fallback recommendations
            return self._get_fallback_recommendations(soil_type, water_availability)
    
    def _calculate_suitability(self, crop, soil_type, temperature, humidity, rainfall, water_availability):
        """Calculate suitability score based on crop characteristics"""
        if crop not in self.crop_data:
            return 50
        
        crop_info = self.crop_data[crop]
        score = 0
        
        # Soil type match
        if soil_type in crop_info['soil_types']:
            score += 25
        
        # Temperature range
        temp_range = crop_info['temp_range']
        if temp_range[0] <= temperature <= temp_range[1]:
            score += 25
        elif abs(temperature - temp_range[0]) <= 5 or abs(temperature - temp_range[1]) <= 5:
            score += 15
        
        # Humidity range
        humidity_range = crop_info['humidity_range']
        if humidity_range[0] <= humidity <= humidity_range[1]:
            score += 25
        elif abs(humidity - humidity_range[0]) <= 10 or abs(humidity - humidity_range[1]) <= 10:
            score += 15
        
        # Rainfall range
        rainfall_range = crop_info['rainfall_range']
        if rainfall_range[0] <= rainfall <= rainfall_range[1]:
            score += 25
        elif abs(rainfall - rainfall_range[0]) <= 25 or abs(rainfall - rainfall_range[1]) <= 25:
            score += 15
        
        return min(score, 100)
    
    def _get_fallback_recommendations(self, soil_type, water_availability):
        """Provide fallback recommendations when model fails"""
        fallback_crops = {
            'clay': ['rice', 'wheat', 'cotton'],
            'loamy': ['wheat', 'maize', 'tomato'],
            'sandy': ['groundnut', 'potato', 'onion'],
            'black': ['cotton', 'soybean', 'sugarcane']
        }
        
        crops = fallback_crops.get(soil_type, ['wheat', 'rice', 'maize'])
        recommendations = []
        
        for i, crop in enumerate(crops):
            crop_info = self.crop_data.get(crop, {})
            recommendations.append({
                'crop': crop,
                'confidence': 70 - (i * 10),
                'suitability_score': 60 - (i * 5),
                'season': crop_info.get('season', 'unknown'),
                'water_requirement': crop_info.get('water_requirement', 'medium'),
                'market_demand': crop_info.get('market_demand', 'medium')
            })
        
        return recommendations
    
    def _get_location_factor(self, temperature, humidity, rainfall):
        """Calculate location-specific adjustment factor"""
        # Base factor
        factor = 1.0
        
        # Adjust based on extreme conditions
        if temperature > 35 or temperature < 10:
            factor *= 0.8  # Reduce confidence for extreme temperatures
        
        if humidity > 90 or humidity < 30:
            factor *= 0.9  # Reduce confidence for extreme humidity
        
        if rainfall > 200 or rainfall < 10:
            factor *= 0.85  # Adjust for extreme rainfall
        
        return factor
    
    def _get_location_advice(self, crop, temperature, humidity, rainfall):
        """Get location-specific advice for the crop"""
        advice = []
        
        if temperature > 30:
            advice.append(f"High temperature detected. Consider heat-resistant varieties of {crop}.")
        
        if humidity > 80:
            advice.append("High humidity may increase disease risk. Ensure proper ventilation.")
        
        if rainfall > 150:
            advice.append("High rainfall area. Focus on drainage and fungal disease prevention.")
        elif rainfall < 50:
            advice.append("Low rainfall area. Plan for irrigation and drought-resistant varieties.")
        
        return advice


class WaterManagementAdvisor:
    def __init__(self):
        self.irrigation_schedules = self._load_irrigation_data()
    
    def _load_irrigation_data(self):
        """Load irrigation requirements for different crops"""
        return {
            'rice': {
                'water_requirement': 1500,  # mm per season
                'critical_stages': ['transplanting', 'tillering', 'flowering'],
                'irrigation_interval': 3,  # days
                'soil_moisture_threshold': 80
            },
            'wheat': {
                'water_requirement': 450,
                'critical_stages': ['crown_root', 'tillering', 'flowering', 'grain_filling'],
                'irrigation_interval': 7,
                'soil_moisture_threshold': 60
            },
            'maize': {
                'water_requirement': 600,
                'critical_stages': ['germination', 'tasseling', 'grain_filling'],
                'irrigation_interval': 5,
                'soil_moisture_threshold': 70
            },
            'cotton': {
                'water_requirement': 800,
                'critical_stages': ['germination', 'flowering', 'boll_development'],
                'irrigation_interval': 7,
                'soil_moisture_threshold': 65
            },
            'tomato': {
                'water_requirement': 600,
                'critical_stages': ['transplanting', 'flowering', 'fruit_development'],
                'irrigation_interval': 2,
                'soil_moisture_threshold': 75
            }
        }
    
    def get_irrigation_advice(self, crop_type, soil_type, weather_forecast):
        """Get irrigation advice based on crop, soil, and weather"""
        crop_data = self.irrigation_schedules.get(crop_type.lower(), {})
        
        if not crop_data:
            return self._get_generic_advice(soil_type, weather_forecast)
        
        advice = {
            'crop': crop_type,
            'water_requirement': crop_data.get('water_requirement', 500),
            'irrigation_schedule': self._calculate_irrigation_schedule(crop_data, weather_forecast),
            'water_conservation_tips': self._get_conservation_tips(crop_type, soil_type),
            'critical_stages': crop_data.get('critical_stages', []),
            'soil_moisture_target': crop_data.get('soil_moisture_threshold', 70)
        }
        
        return advice
    
    def _calculate_irrigation_schedule(self, crop_data, weather_forecast):
        """Calculate irrigation schedule based on weather forecast"""
        schedule = []
        base_interval = crop_data.get('irrigation_interval', 5)
        
        # Adjust based on weather forecast
        for i, day_forecast in enumerate(weather_forecast[:7]):  # Next 7 days
            rainfall = day_forecast.get('rainfall', 0)
            temperature = day_forecast.get('temperature', 25)
            humidity = day_forecast.get('humidity', 60)
            
            # Calculate water need
            water_need = self._calculate_daily_water_need(temperature, humidity, rainfall)
            
            irrigation_needed = water_need > 5 and rainfall < 10
            
            schedule.append({
                'day': i + 1,
                'date': day_forecast.get('date', ''),
                'irrigation_needed': irrigation_needed,
                'water_amount': water_need if irrigation_needed else 0,
                'reason': self._get_irrigation_reason(rainfall, temperature, humidity)
            })
        
        return schedule
    
    def _calculate_daily_water_need(self, temperature, humidity, rainfall):
        """Calculate daily water requirement in mm"""
        # Simplified ET calculation
        base_et = 5  # Base evapotranspiration
        temp_factor = max(0, (temperature - 20) * 0.1)
        humidity_factor = max(0, (70 - humidity) * 0.05)
        
        et = base_et + temp_factor + humidity_factor
        water_need = max(0, et - rainfall)
        
        return round(water_need, 1)
    
    def _get_irrigation_reason(self, rainfall, temperature, humidity):
        """Get reason for irrigation recommendation"""
        if rainfall > 10:
            return "No irrigation needed - sufficient rainfall expected"
        elif temperature > 30:
            return "High temperature - increased water requirement"
        elif humidity < 50:
            return "Low humidity - higher evaporation rate"
        else:
            return "Regular irrigation schedule"
    
    def _get_conservation_tips(self, crop_type, soil_type):
        """Get water conservation tips"""
        tips = [
            "Use drip irrigation system for efficient water use",
            "Apply mulch to reduce evaporation",
            "Irrigate during early morning or evening hours",
            "Monitor soil moisture regularly"
        ]
        
        # Crop-specific tips
        crop_tips = {
            'rice': ["Use alternate wetting and drying (AWD) technique"],
            'wheat': ["Use furrow irrigation method"],
            'cotton': ["Deep, less frequent irrigation is better"],
            'tomato': ["Maintain consistent soil moisture"]
        }
        
        if crop_type.lower() in crop_tips:
            tips.extend(crop_tips[crop_type.lower()])
        
        # Soil-specific tips
        soil_tips = {
            'sandy': ["Irrigate more frequently with smaller amounts"],
            'clay': ["Allow proper drainage between irrigations"],
            'loamy': ["Ideal soil for water retention"]
        }
        
        if soil_type in soil_tips:
            tips.extend(soil_tips[soil_type])
        
        return tips
    
    def _get_generic_advice(self, soil_type, weather_forecast):
        """Provide generic irrigation advice when crop data is not available"""
        return {
            'crop': 'generic',
            'water_requirement': 500,
            'irrigation_schedule': [
                {
                    'day': i + 1,
                    'irrigation_needed': True,
                    'water_amount': 10,
                    'reason': 'Regular irrigation schedule'
                } for i in range(7)
            ],
            'water_conservation_tips': self._get_conservation_tips('generic', soil_type),
            'critical_stages': ['germination', 'flowering', 'maturity'],
            'soil_moisture_target': 70
        }
