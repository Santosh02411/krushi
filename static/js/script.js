// Navigation functionality
document.addEventListener('DOMContentLoaded', function() {
    // Navigation handling
    const navLinks = document.querySelectorAll('.nav-link');
    const sections = document.querySelectorAll('.section');

    navLinks.forEach(link => {
        link.addEventListener('click', function(e) {
            e.preventDefault();
            
            // Remove active class from all links and sections
            navLinks.forEach(l => l.classList.remove('active'));
            sections.forEach(s => s.classList.remove('active'));
            
            // Add active class to clicked link
            this.classList.add('active');
            
            // Show corresponding section
            const targetSection = document.querySelector(this.getAttribute('href'));
            if (targetSection) {
                targetSection.classList.add('active');
            }
        });
    });

    // Make feature cards and buttons clickable
    const featureCards = document.querySelectorAll('.feature-card');
    featureCards.forEach(card => {
        card.style.cursor = 'pointer';
        
        // Handle both card click and button click
        card.addEventListener('click', function(e) {
            const section = this.getAttribute('data-section');
            if (section) {
                const targetLink = document.querySelector(`[href="#${section}"]`);
                if (targetLink) {
                    targetLink.click();
                }
            }
        });
        
        // Handle feature button clicks
        const featureBtn = card.querySelector('.feature-btn');
        if (featureBtn) {
            featureBtn.addEventListener('click', function(e) {
                e.stopPropagation(); // Prevent card click
                const section = card.getAttribute('data-section');
                if (section) {
                    const targetLink = document.querySelector(`[href="#${section}"]`);
                    if (targetLink) {
                        targetLink.click();
                    }
                }
            });
        }
    });

    // Auto-detect user location
    detectUserLocationImproved();

    // Crop recommendation functionality
    const getRecommendationsBtn = document.getElementById('get-recommendations');
    if (getRecommendationsBtn) {
        getRecommendationsBtn.addEventListener('click', getCropRecommendations);
    }

    // Weather functionality
    const getWeatherBtn = document.getElementById('get-weather');
    if (getWeatherBtn) {
        getWeatherBtn.addEventListener('click', getWeatherData);
    }

    // Market functionality
    const getMarketBtn = document.getElementById('get-market-data');
    if (getMarketBtn) {
        getMarketBtn.addEventListener('click', getMarketData);
    }

    // Water management functionality
    const getWaterAdviceBtn = document.getElementById('get-water-advice');
    if (getWaterAdviceBtn) {
        getWaterAdviceBtn.addEventListener('click', getWaterAdvice);
    }
});

// Utility functions
function showLoading() {
    document.getElementById('loading').style.display = 'flex';
}

function hideLoading() {
    document.getElementById('loading').style.display = 'none';
}

function showAlert(message, type = 'info') {
    const alertDiv = document.createElement('div');
    alertDiv.className = `alert alert-${type}`;
    alertDiv.textContent = message;
    
    // Insert at the top of the active section
    const activeSection = document.querySelector('.section.active');
    const container = activeSection.querySelector('.container');
    container.insertBefore(alertDiv, container.firstChild);
    
    // Remove alert after 5 seconds
    setTimeout(() => {
        alertDiv.remove();
    }, 5000);
}

// Crop Recommendations
async function getCropRecommendations() {
    const location = document.getElementById('location').value;
    const soilType = document.getElementById('soil-type').value;
    const waterAvailability = document.getElementById('water-availability').value;
    const farmSize = document.getElementById('farm-size').value;

    if (!location || !soilType || !waterAvailability) {
        showAlert('Please fill in all required fields', 'error');
        return;
    }

    showLoading();

    try {
        const response = await fetch('/api/recommend-crops', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                location: location,
                soil_type: soilType,
                water_availability: waterAvailability,
                farm_size: parseFloat(farmSize) || 1.0
            })
        });

        const data = await response.json();

        if (data.success) {
            displayCropRecommendations(data.recommendations, data.weather);
            showAlert('Crop recommendations generated successfully!', 'success');
        } else {
            showAlert('Error getting recommendations: ' + data.error, 'error');
        }
    } catch (error) {
        showAlert('Network error: ' + error.message, 'error');
    } finally {
        hideLoading();
    }
}

function displayCropRecommendations(recommendations, weather) {
    const resultsSection = document.getElementById('recommendations-results');
    const cropCards = document.getElementById('crop-cards');
    
    cropCards.innerHTML = '';

    recommendations.forEach(crop => {
        const cropCard = document.createElement('div');
        cropCard.className = 'crop-card';
        
        cropCard.innerHTML = `
            <h4>${crop.crop}</h4>
            <div class="crop-info">
                <span><strong>Confidence:</strong> ${crop.confidence}%</span>
                <span><strong>Season:</strong> ${crop.season}</span>
                <span><strong>Water Need:</strong> ${crop.water_requirement}</span>
                <span><strong>Market Demand:</strong> ${crop.market_demand}</span>
            </div>
            <div class="confidence-bar">
                <div class="confidence-fill" style="width: ${crop.confidence}%"></div>
            </div>
            <p><strong>Suitability Score:</strong> ${crop.suitability_score}/100</p>
            ${crop.location_specific_advice && crop.location_specific_advice.length > 0 ? 
                `<div style="margin-top: 1rem; padding: 0.5rem; background: #fff3cd; border-radius: 5px; font-size: 0.9rem;">
                    <strong>Location Advice:</strong><br>
                    ${crop.location_specific_advice.join('<br>')}
                </div>` : ''}
        `;
        
        cropCards.appendChild(cropCard);
    });

    // Show weather info if available
    if (weather) {
        const weatherInfo = document.createElement('div');
        weatherInfo.className = 'weather-card';
        weatherInfo.innerHTML = `
            <h4>Current Weather in ${weather.location}</h4>
            <p><strong>Temperature:</strong> ${weather.temperature}°C</p>
            <p><strong>Humidity:</strong> ${weather.humidity}%</p>
            <p><strong>Weather:</strong> ${weather.weather}</p>
        `;
        cropCards.appendChild(weatherInfo);
    }

    resultsSection.style.display = 'block';
}

// Weather Data
async function getWeatherData() {
    const location = document.getElementById('weather-location').value;

    if (!location) {
        showAlert('Please enter a location', 'error');
        return;
    }

    showLoading();

    try {
        const response = await fetch(`/api/weather/${encodeURIComponent(location)}`);
        const data = await response.json();

        if (data.success) {
            displayWeatherData(data.current, data.forecast);
            showAlert('Weather data loaded successfully!', 'success');
        } else {
            showAlert('Error getting weather data: ' + data.error, 'error');
        }
    } catch (error) {
        showAlert('Network error: ' + error.message, 'error');
    } finally {
        hideLoading();
    }
}

function displayWeatherData(current, forecast) {
    const resultsSection = document.getElementById('weather-results');
    const currentWeatherData = document.getElementById('current-weather-data');
    const forecastData = document.getElementById('forecast-data');

    // Display current weather
    currentWeatherData.innerHTML = `
        <div class="weather-card">
            <h4>${current.location}</h4>
            <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 1rem;">
                <div>
                    <p><strong>Temperature:</strong> ${current.temperature}°C</p>
                    <p><strong>Weather:</strong> ${current.weather}</p>
                </div>
                <div>
                    <p><strong>Humidity:</strong> ${current.humidity}%</p>
                    <p><strong>Wind Speed:</strong> ${current.wind_speed} m/s</p>
                </div>
                <div>
                    <p><strong>Pressure:</strong> ${current.pressure} hPa</p>
                    <p><strong>Rainfall:</strong> ${current.rainfall} mm</p>
                </div>
            </div>
        </div>
    `;

    // Display forecast
    forecastData.innerHTML = '<div class="forecast-grid"></div>';
    const forecastGrid = forecastData.querySelector('.forecast-grid');

    forecast.forEach(day => {
        const dayCard = document.createElement('div');
        dayCard.className = 'forecast-day';
        dayCard.innerHTML = `
            <h5>${new Date(day.date).toLocaleDateString('en-US', { weekday: 'short', month: 'short', day: 'numeric' })}</h5>
            <p><strong>${day.temperature}°C</strong></p>
            <p>${day.weather}</p>
            <p>💧 ${day.rainfall}mm</p>
            <p>💨 ${day.wind_speed}m/s</p>
        `;
        forecastGrid.appendChild(dayCard);
    });

    resultsSection.style.display = 'block';
}

// Market Data
async function getMarketData() {
    const crop = document.getElementById('market-crop').value;

    if (!crop) {
        showAlert('Please select a crop', 'error');
        return;
    }

    showLoading();

    try {
        const response = await fetch(`/api/market-trends/${encodeURIComponent(crop)}`);
        const data = await response.json();

        if (data.success) {
            displayMarketData(data.trends, data.predictions);
            showAlert('Market data loaded successfully!', 'success');
        } else {
            showAlert('Error getting market data: ' + data.error, 'error');
        }
    } catch (error) {
        showAlert('Network error: ' + error.message, 'error');
    } finally {
        hideLoading();
    }
}

function displayMarketData(trends, predictions) {
    const resultsSection = document.getElementById('market-results');
    const priceData = document.getElementById('price-data');
    const predictionData = document.getElementById('prediction-data');

    // Display current price info
    priceData.innerHTML = `
        <div class="price-card">
            <h4>${trends.crop.toUpperCase()} Market Information</h4>
            <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 1rem;">
                <div>
                    <p><strong>Current Price:</strong> ₹${trends.current_price}/quintal</p>
                    <div class="price-trend ${trends.trend_direction === 'up' ? 'trend-up' : 'trend-down'}">
                        <i class="fas fa-arrow-${trends.trend_direction === 'up' ? 'up' : 'down'}"></i>
                        <span>${trends.trend_direction === 'up' ? 'Rising' : 'Falling'} Trend</span>
                    </div>
                </div>
                <div>
                    <p><strong>Volatility:</strong> ${trends.volatility}%</p>
                    <p><strong>Market Status:</strong> ${trends.volatility > 15 ? 'High Volatility' : 'Stable'}</p>
                </div>
            </div>
            <div style="margin-top: 1rem; padding: 1rem; background: #f8f9fa; border-radius: 5px;">
                <p><strong>Market Analysis:</strong> ${trends.market_analysis}</p>
            </div>
        </div>
    `;

    // Display predictions
    predictionData.innerHTML = '<div class="predictions-grid" style="display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 1rem;"></div>';
    const predictionsGrid = predictionData.querySelector('.predictions-grid');

    predictions.forEach(prediction => {
        const predictionCard = document.createElement('div');
        predictionCard.className = 'price-card';
        predictionCard.innerHTML = `
            <h5>${prediction.month}</h5>
            <p><strong>Predicted Price:</strong> ₹${prediction.predicted_price}/quintal</p>
            <p><strong>Confidence:</strong> ${prediction.confidence.toFixed(1)}%</p>
            <div class="price-trend ${prediction.trend === 'up' ? 'trend-up' : 'trend-down'}">
                <i class="fas fa-arrow-${prediction.trend === 'up' ? 'up' : 'down'}"></i>
                <span>${prediction.trend === 'up' ? 'Expected Rise' : 'Expected Fall'}</span>
            </div>
        `;
        predictionsGrid.appendChild(predictionCard);
    });

    resultsSection.style.display = 'block';
}

// Water Management
async function getWaterAdvice() {
    const cropType = document.getElementById('water-crop').value;
    const soilType = document.getElementById('water-soil').value;
    const location = document.getElementById('water-location').value;

    if (!cropType || !soilType || !location) {
        showAlert('Please fill in all fields', 'error');
        return;
    }

    showLoading();

    try {
        const response = await fetch('/api/water-management', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                crop_type: cropType,
                soil_type: soilType,
                location: location
            })
        });

        const data = await response.json();

        if (data.success) {
            displayWaterAdvice(data.advice, data.forecast);
            showAlert('Water management advice generated successfully!', 'success');
        } else {
            showAlert('Error getting water advice: ' + data.error, 'error');
        }
    } catch (error) {
        showAlert('Network error: ' + error.message, 'error');
    } finally {
        hideLoading();
    }
}

function displayWaterAdvice(advice, forecast) {
    const resultsSection = document.getElementById('water-results');
    const irrigationData = document.getElementById('irrigation-data');
    const conservationTips = document.getElementById('conservation-tips');

    // Display irrigation schedule
    irrigationData.innerHTML = `
        <div style="margin-bottom: 1rem;">
            <p><strong>Crop:</strong> ${advice.crop}</p>
            <p><strong>Water Requirement:</strong> ${advice.water_requirement} mm/season</p>
            <p><strong>Target Soil Moisture:</strong> ${advice.soil_moisture_target}%</p>
        </div>
        <div class="schedule-grid"></div>
    `;

    const scheduleGrid = irrigationData.querySelector('.schedule-grid');
    advice.irrigation_schedule.forEach(day => {
        const dayCard = document.createElement('div');
        dayCard.className = `schedule-day ${day.irrigation_needed ? 'irrigation-needed' : ''}`;
        dayCard.innerHTML = `
            <h5>Day ${day.day}</h5>
            <p><strong>${day.irrigation_needed ? 'Irrigation Needed' : 'No Irrigation'}</strong></p>
            ${day.irrigation_needed ? `<p>Amount: ${day.water_amount}mm</p>` : ''}
            <p style="font-size: 0.9rem; color: #666;">${day.reason}</p>
        `;
        scheduleGrid.appendChild(dayCard);
    });

    // Display conservation tips
    conservationTips.innerHTML = '<ul class="tips-list"></ul>';
    const tipsList = conservationTips.querySelector('.tips-list');
    
    advice.water_conservation_tips.forEach(tip => {
        const tipItem = document.createElement('li');
        tipItem.textContent = tip;
        tipsList.appendChild(tipItem);
    });

    // Add critical stages info
    if (advice.critical_stages && advice.critical_stages.length > 0) {
        const criticalStagesDiv = document.createElement('div');
        criticalStagesDiv.innerHTML = `
            <h4 style="color: #2e7d32; margin-top: 1rem;">Critical Growth Stages</h4>
            <p>Pay special attention to water management during: ${advice.critical_stages.join(', ')}</p>
        `;
        irrigationData.appendChild(criticalStagesDiv);
    }

    resultsSection.style.display = 'block';
}

// Improved location detection
async function detectUserLocationImproved() {
    try {
        // Try server-side location detection first
        const response = await fetch('/api/detect-location');
        const data = await response.json();
        
        if (data.success) {
            setLocationFields(data.location);
            // Store location details for enhanced recommendations
            window.locationDetails = data.details;
            showAlert(`Location detected: ${data.location}`, 'success');
        } else {
            fallbackLocationDetection();
        }
    } catch (error) {
        console.log('Server location detection failed:', error);
        fallbackLocationDetection();
    }
}

function fallbackLocationDetection() {
    if (navigator.geolocation) {
        navigator.geolocation.getCurrentPosition(
            function(position) {
                // Use coordinates to get approximate location
                const lat = position.coords.latitude;
                const lon = position.coords.longitude;
                
                // Simple location mapping based on coordinates
                let location = getLocationFromCoordinates(lat, lon);
                setLocationFields(location);
                showAlert(`Location detected: ${location}`, 'info');
            },
            function(error) {
                console.log('Geolocation failed:', error);
                setDefaultLocation();
            },
            { timeout: 10000, enableHighAccuracy: false }
        );
    } else {
        setDefaultLocation();
    }
}

function getLocationFromCoordinates(lat, lon) {
    // Simple coordinate-based location detection for major Indian cities
    const cities = [
        { name: 'Mumbai, Maharashtra', lat: 19.0760, lon: 72.8777, range: 1 },
        { name: 'Delhi, India', lat: 28.7041, lon: 77.1025, range: 1 },
        { name: 'Bangalore, Karnataka', lat: 12.9716, lon: 77.5946, range: 1 },
        { name: 'Chennai, Tamil Nadu', lat: 13.0827, lon: 80.2707, range: 1 },
        { name: 'Kolkata, West Bengal', lat: 22.5726, lon: 88.3639, range: 1 },
        { name: 'Pune, Maharashtra', lat: 18.5204, lon: 73.8567, range: 1 },
        { name: 'Hyderabad, Telangana', lat: 17.3850, lon: 78.4867, range: 1 }
    ];
    
    for (let city of cities) {
        const distance = Math.sqrt(Math.pow(lat - city.lat, 2) + Math.pow(lon - city.lon, 2));
        if (distance < city.range) {
            return city.name;
        }
    }
    
    // Default to Delhi if no match
    return 'Delhi, India';
}

function setLocationFields(location) {
    // Set location in all relevant fields
    const locationFields = ['location', 'weather-location', 'water-location'];
    locationFields.forEach(fieldId => {
        const field = document.getElementById(fieldId);
        if (field) {
            field.value = location;
            field.style.backgroundColor = '#e8f5e8';
            field.style.border = '2px solid #4caf50';
        }
    });
}

function setDefaultLocation() {
    setLocationFields('Delhi, India');
    showAlert('Using default location: Delhi, India', 'info');
}
