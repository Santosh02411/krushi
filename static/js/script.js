// Krushi frontend — talks to the Flask API in app.py.

const $ = (id) => document.getElementById(id);
let userCoords = null; // real GPS coords once granted
let referenceData = null;
let currentUser = null;

document.addEventListener('DOMContentLoaded', () => {
  loadModelInfo();
  loadReferenceData();
  checkSession();

  $('detect-btn').addEventListener('click', detectLocation);
  $('fetch-weather-btn').addEventListener('click', fetchWeatherPreview);
  $('recommend-btn').addEventListener('click', getRecommendations);
  $('water-btn').addEventListener('click', getIrrigationSchedule);
  $('soil-health-btn').addEventListener('click', getSoilHealth);
  $('market-search-btn').addEventListener('click', searchMarket);
  $('state').addEventListener('change', populateDistricts);
  $('fertilizer-btn').addEventListener('click', getFertilizerPlan);
  $('load-symptoms-btn').addEventListener('click', loadSymptoms);
  $('disease-check-btn').addEventListener('click', checkDisease);
  $('disease-photo-input').addEventListener('change', uploadDiseasePhoto);
  $('calendar-btn').addEventListener('click', buildCropCalendar);
  if ($('cal-sowing-date')) $('cal-sowing-date').value = new Date().toISOString().slice(0, 10);
  $('yield-predict-btn').addEventListener('click', predictYield);
  $('profit-btn').addEventListener('click', estimateProfit);
  $('rec-type').addEventListener('change', toggleRecordCategory);
  $('add-record-btn').addEventListener('click', addFarmRecord);
  $('map-refresh-btn').addEventListener('click', refreshFarmMap);
  document.querySelectorAll('.kb-tab').forEach(tab => tab.addEventListener('click', () => switchKbTab(tab.dataset.kb)));
  loadKnowledgeBase();

  document.querySelectorAll('.auth-tab').forEach(tab => {
    tab.addEventListener('click', () => switchAuthTab(tab.dataset.tab));
  });
  $('login-form').addEventListener('submit', handleLogin);
  $('register-form').addEventListener('submit', handleRegister);
  $('forgot-form').addEventListener('submit', handleForgot);
  $('reset-form').addEventListener('submit', handleReset);
  $('save-profile-btn').addEventListener('click', saveProfile);
  $('logout-btn').addEventListener('click', handleLogout);
});

// ---------------------------------------------------------------------- //
// Model stats
// ---------------------------------------------------------------------- //
async function loadModelInfo() {
  try {
    const res = await fetch('/api/model-info');
    const data = await res.json();
    if (data.success) {
      const cm = data.crop_model;
      $('stat-samples').textContent = cm.training_samples.toLocaleString();
      $('stat-crops').textContent = cm.crop_classes;
      $('stat-market-r2').textContent = data.market_model.test_r2;
      $('stat-accuracy').textContent = cm.test_accuracy_pct + '%';

      const circumference = 326.7;
      const offset = circumference * (1 - cm.test_accuracy_pct / 100);
      const arc = $('accuracy-arc');
      requestAnimationFrame(() => { arc.style.transition = 'stroke-dashoffset 1.1s ease'; arc.setAttribute('stroke-dashoffset', offset); });
    }
  } catch (e) { /* panel just keeps its placeholder dashes */ }
}

async function loadReferenceData() {
  try {
    const res = await fetch('/api/reference-data');
    const data = await res.json();
    if (!data.success) return;
    referenceData = data;

    fillSelect($('state'), data.states, 'Select state');
    fillSelect($('soil-type'), data.soil_types, 'Select soil type');
    fillSelect($('season'), data.seasons, 'Select season');
    fillSelect($('yp-state'), data.states, 'Any state');
    fillSelect($('yp-season'), data.seasons, 'Any season');
    fillSelect($('reg-soil-type'), data.soil_types, 'Select soil type');
    fillSelect($('profile-soil-type'), data.soil_types, 'Select soil type');
    fillLangSelect($('reg-language'), data.languages);
    fillLangSelect($('profile-language'), data.languages);
  } catch (e) { /* selects stay empty; user can still fill n/p/k/ph manually */ }
}

function fillSelect(select, values, placeholder) {
  if (!select) return;
  select.innerHTML = `<option value="">${placeholder}</option>` + values.map(v => `<option value="${v}">${v}</option>`).join('');
}
function fillLangSelect(select, languages) {
  if (!select) return;
  select.innerHTML = languages.map(l => `<option value="${l.code}">${l.label}</option>`).join('');
}

function populateDistricts() {
  const state = $('state').value;
  const districts = (referenceData && referenceData.districts_by_state[state]) || [];
  fillSelect($('district'), districts, 'Select district');
}

// ---------------------------------------------------------------------- //
// Auth
// ---------------------------------------------------------------------- //
function switchAuthTab(tab) {
  document.querySelectorAll('.auth-tab').forEach(t => t.classList.toggle('active', t.dataset.tab === tab));
  document.querySelectorAll('.auth-form').forEach(f => f.classList.remove('active'));
  const map = { login: 'login-form', register: 'register-form', forgot: 'forgot-form' };
  ($(map[tab]) || $('reset-form')).classList.add('active');
}

async function checkSession() {
  try {
    const res = await fetch('/api/auth/me', { credentials: 'include' });
    const data = await res.json();
    if (data.success && data.user) applyLoggedInState(data.user);
  } catch (e) { /* not logged in */ }
}

function applyLoggedInState(user) {
  currentUser = user;
  $('nav-account-link').textContent = `Hi, ${user.name}`;
  $('auth-forms-wrap').style.display = 'none';
  $('account-panel').classList.add('show');
  $('profile-name').textContent = user.name;
  $('profile-role').textContent = user.role;
  $('profile-location').value = user.location || '';
  $('profile-farm-size').value = user.farm_size_acres || '';
  if ($('profile-soil-type')) $('profile-soil-type').value = user.soil_type || '';
  if ($('profile-language')) $('profile-language').value = user.preferred_language || 'en';

  if (user.location) $('location').value = user.location;

  $('dashboard-logged-out').style.display = 'none';
  $('dashboard-content').style.display = 'block';
  loadDashboard();

  if (user.role === 'admin') loadAdminUsers();
}

async function handleLogin(e) {
  e.preventDefault();
  $('login-error').classList.remove('show');
  try {
    const res = await fetch('/api/auth/login', {
      method: 'POST', credentials: 'include', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email: $('login-email').value, password: $('login-password').value }),
    });
    const data = await res.json();
    if (!data.success) throw new Error(data.error);
    applyLoggedInState(data.user);
  } catch (err) {
    $('login-error').textContent = err.message || 'Login failed.';
    $('login-error').classList.add('show');
  }
}

async function handleRegister(e) {
  e.preventDefault();
  $('register-error').classList.remove('show');
  try {
    const res = await fetch('/api/auth/register', {
      method: 'POST', credentials: 'include', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        name: $('reg-name').value, email: $('reg-email').value, password: $('reg-password').value,
        location: $('reg-location').value, farm_size_acres: parseFloat($('reg-farm-size').value) || null,
        soil_type: $('reg-soil-type').value, preferred_language: $('reg-language').value,
      }),
    });
    const data = await res.json();
    if (!data.success) throw new Error(data.error);
    applyLoggedInState(data.user);
  } catch (err) {
    $('register-error').textContent = err.message || 'Registration failed.';
    $('register-error').classList.add('show');
  }
}

async function handleForgot(e) {
  e.preventDefault();
  const note = $('forgot-note');
  note.style.display = 'block';
  note.textContent = 'Sending…';
  try {
    const res = await fetch('/api/auth/forgot-password', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email: $('forgot-email').value }),
    });
    const data = await res.json();
    if (data.reset_token) {
      note.textContent = `${data.message} Token: ${data.reset_token}`;
      $('reset-email').value = $('forgot-email').value;
      $('reset-token').value = data.reset_token;
      switchAuthTab('reset');
    } else {
      note.textContent = data.message || 'If that email has an account, a reset link has been issued.';
    }
  } catch (err) {
    note.textContent = 'Could not process request.';
  }
}

async function handleReset(e) {
  e.preventDefault();
  $('reset-error').classList.remove('show');
  try {
    const res = await fetch('/api/auth/reset-password', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        email: $('reset-email').value, token: $('reset-token').value,
        new_password: $('reset-new-password').value,
      }),
    });
    const data = await res.json();
    if (!data.success) throw new Error(data.error);
    switchAuthTab('login');
    $('login-email').value = $('reset-email').value;
  } catch (err) {
    $('reset-error').textContent = err.message || 'Reset failed.';
    $('reset-error').classList.add('show');
  }
}

async function saveProfile() {
  try {
    const res = await fetch('/api/auth/profile', {
      method: 'PUT', credentials: 'include', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        location: $('profile-location').value, farm_size_acres: parseFloat($('profile-farm-size').value) || null,
        soil_type: $('profile-soil-type').value, preferred_language: $('profile-language').value,
      }),
    });
    const data = await res.json();
    if (data.success) applyLoggedInState(data.user);
  } catch (e) { /* leave form as-is */ }
}

async function handleLogout() {
  await fetch('/api/auth/logout', { method: 'POST', credentials: 'include' });
  currentUser = null;
  $('nav-account-link').textContent = 'Login / Register';
  $('auth-forms-wrap').style.display = '';
  $('account-panel').classList.remove('show');
  $('dashboard-logged-out').style.display = 'block';
  $('dashboard-content').style.display = 'none';
}

async function loadAdminUsers() {
  try {
    const res = await fetch('/api/admin/users', { credentials: 'include' });
    const data = await res.json();
    if (!data.success) return;
    $('admin-panel').style.display = 'block';
    $('admin-users').innerHTML = `
      <p class="hint">${data.stats.total_users} registered farmers · ${data.stats.total_recommendations_generated} recommendations generated</p>
      <table class="schedule-table"><thead><tr><th>Name</th><th>Email</th><th>Location</th><th>Role</th></tr></thead>
      <tbody>${data.users.map(u => `<tr><td>${u.name}</td><td>${u.email}</td><td>${u.location || '—'}</td><td>${u.role}</td></tr>`).join('')}</tbody></table>`;
  } catch (e) { /* not admin or request failed */ }
}

// ---------------------------------------------------------------------- //
// Location — browser GPS is the accurate path; IP lookup is a fallback
// ---------------------------------------------------------------------- //
async function detectLocation() {
  const btn = $('detect-btn');
  const status = $('location-status');
  btn.disabled = true;
  btn.textContent = 'Locating…';
  status.className = 'location-status';
  status.textContent = '';

  if (!navigator.geolocation) {
    status.textContent = 'Your browser does not support GPS location — please type it in.';
    status.classList.add('warn');
    btn.disabled = false;
    btn.textContent = 'Use my GPS location';
    return;
  }

  navigator.geolocation.getCurrentPosition(
    async (position) => {
      const { latitude, longitude, accuracy } = position.coords;
      userCoords = { lat: latitude, lon: longitude, accuracy };
      try {
        const res = await fetch(`/api/reverse-geocode?lat=${latitude}&lon=${longitude}`);
        const data = await res.json();
        if (data.success) {
          $('location').value = data.location_string || `${latitude.toFixed(4)}, ${longitude.toFixed(4)}`;
          if (data.state && referenceData && referenceData.states.includes(data.state)) {
            $('state').value = data.state;
            populateDistricts();
          }
          status.textContent = `GPS-located (±${Math.round(accuracy)}m). Weather and climate values will use these exact coordinates.`;
          status.classList.add('ok');
        }
      } catch (e) {
        $('location').value = `${latitude.toFixed(4)}, ${longitude.toFixed(4)}`;
        status.textContent = `GPS coordinates captured (±${Math.round(accuracy)}m).`;
        status.classList.add('ok');
      }
      btn.disabled = false;
      btn.textContent = 'Use my GPS location';
    },
    async (err) => {
      status.textContent = 'GPS access denied or unavailable — falling back to network-based location (less accurate).';
      status.classList.add('warn');
      try {
        const res = await fetch('/api/detect-location');
        const data = await res.json();
        if (data.success) {
          $('location').value = data.location;
          userCoords = { lat: data.lat, lon: data.lon, accuracy: null };
          status.textContent = (data.accuracy_warning || '') + ' Detected: ' + data.location;
        }
      } catch (e2) { /* keep warning message */ }
      btn.disabled = false;
      btn.textContent = 'Use my GPS location';
    },
    { enableHighAccuracy: true, timeout: 10000 }
  );
}

async function fetchWeatherPreview() {
  const location = $('location').value.trim();
  if (!userCoords && !location) {
    $('location-status').textContent = 'Enter a location or use GPS first.';
    $('location-status').className = 'location-status warn';
    return;
  }
  const btn = $('fetch-weather-btn');
  btn.disabled = true;
  btn.textContent = 'Fetching…';
  try {
    const url = userCoords
      ? `/api/weather-by-coords?lat=${userCoords.lat}&lon=${userCoords.lon}&label=${encodeURIComponent(location)}`
      : `/api/weather/${encodeURIComponent(location)}`;
    const res = await fetch(url);
    const data = await res.json();
    if (data.success && data.current) {
      const c = data.current;
      $('temperature').value = c.temperature ?? '';
      $('humidity').value = c.humidity ?? '';
      $('rainfall').value = c.rainfall ?? 0;

      const preview = $('weather-preview');
      preview.innerHTML = `
        <span><b>${c.temperature}°C</b></span>
        <span>${c.humidity}% humidity</span>
        <span>wind ${c.wind_speed ?? '—'} km/h</span>
        <span>UV ${c.uv_index ?? '—'}</span>
        <span>${c.weather}</span>
        <span class="src">source: ${c.source || 'unknown'}</span>`;
      preview.classList.add('show');
    }
  } catch (e) { /* form still usable with manual values */
  } finally {
    btn.disabled = false;
    btn.textContent = 'Fetch live weather for this location';
  }
}

// ---------------------------------------------------------------------- //
// Crop recommendations
// ---------------------------------------------------------------------- //
async function getRecommendations() {
  const errorEl = $('recommend-error');
  const loadingEl = $('recommend-loading');
  errorEl.classList.remove('show');
  loadingEl.classList.add('show');
  $('recommend-btn').disabled = true;

  const payload = {
    location: $('location').value.trim() || 'Delhi',
    state: $('state').value || null,
    district: $('district').value || null,
    season: $('season').value || null,
    n: parseFloat($('n').value) || 0,
    p: parseFloat($('p').value) || 0,
    k: parseFloat($('k').value) || 0,
    ph: parseFloat($('ph').value) || 6.5,
  };
  if (userCoords) { payload.lat = userCoords.lat; payload.lon = userCoords.lon; }
  if ($('temperature').value !== '') payload.temperature = parseFloat($('temperature').value);
  if ($('humidity').value !== '') payload.humidity = parseFloat($('humidity').value);
  if ($('rainfall').value !== '') payload.rainfall = parseFloat($('rainfall').value);

  try {
    const res = await fetch('/api/recommend-crops', {
      method: 'POST', credentials: 'include', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    const data = await res.json();
    if (!data.success) throw new Error(data.error || 'Request failed');

    renderWeatherSummary(data.weather);
    renderCropResults(data.recommendations);
    $('results').classList.add('show');
    $('results').scrollIntoView({ behavior: 'smooth', block: 'start' });

    if (userCoords) {
      try {
        const wres = await fetch(`/api/weather-by-coords?lat=${userCoords.lat}&lon=${userCoords.lon}`);
        const wdata = await wres.json();
        if (wdata.success) { renderForecast(wdata.forecast); renderAlerts(wdata.alerts); }
      } catch (e) { /* skip forecast/alerts if unavailable */ }
    }
  } catch (e) {
    errorEl.textContent = 'Could not get recommendations: ' + e.message;
    errorEl.classList.add('show');
  } finally {
    loadingEl.classList.remove('show');
    $('recommend-btn').disabled = false;
  }
}

function renderWeatherSummary(weather) {
  const el = $('weather-summary');
  if (!weather) { el.innerHTML = ''; return; }
  el.innerHTML = `
    <div class="temp">${weather.temperature}°C</div>
    <div class="meta">${weather.location} · ${weather.humidity}% humidity · wind ${weather.wind_speed ?? '—'} km/h · UV ${weather.uv_index ?? '—'} · ${weather.weather}</div>
    <div class="source-note">source: ${weather.source || 'unknown'}</div>
  `;
}

function renderForecast(forecast) {
  const el = $('forecast-strip');
  if (!forecast || !forecast.length) { el.innerHTML = ''; return; }
  el.innerHTML = forecast.map(d => `
    <div class="forecast-day">
      <div class="date">${d.date}</div>
      <div class="temp">${d.temperature ?? '—'}°</div>
      <div class="rain">${d.rainfall ?? 0}mm rain</div>
    </div>`).join('');
}

function renderAlerts(alerts) {
  const el = $('weather-alerts');
  if (!alerts || !alerts.length) { el.innerHTML = ''; return; }
  el.innerHTML = alerts.map(a => `<div class="alert-banner ${a.type}">⚠ ${a.message}</div>`).join('');
}

function renderCropResults(recommendations) {
  const hero = recommendations[0];
  const alternatives = recommendations.slice(1);

  $('hero-crop').innerHTML = '';
  $('hero-crop').appendChild(buildCropCard(hero, 1, true));
  requestAnimationFrame(() => animateBar($('hero-crop')));

  const grid = $('crop-grid');
  grid.innerHTML = '';
  alternatives.forEach((rec, i) => {
    const card = buildCropCard(rec, i + 2, false);
    grid.appendChild(card);
  });
  requestAnimationFrame(() => animateBar(grid));

  const altList = document.createElement('div');
  altList.className = 'alt-list';
  altList.innerHTML = alternatives.map(r => `<span class="alt-chip">${r.crop}</span>`).join('');
  $('crop-grid').before(altList);
}

function animateBar(container) {
  container.querySelectorAll('.confidence-fill').forEach(fill => { fill.style.width = fill.dataset.pct + '%'; });
}

function buildCropCard(rec, rank, isHero) {
  const demandClass = `demand-${rec.market_demand}`;
  const card = document.createElement('div');
  card.className = 'card crop-card' + (isHero ? ' hero-crop-card' : '');
  card.innerHTML = `
    <span class="rank">${isHero ? '✅ #1' : '#' + rank}</span>
    <h3>${rec.crop.replace(/_/g, ' ')}</h3>
    <p class="desc">${rec.description || ''}</p>

    <div class="confidence-track"><div class="confidence-fill" data-pct="${rec.confidence}"></div></div>
    <div class="confidence-label">${rec.confidence}% model confidence</div>

    <div class="badge-row">
      <span class="badge season">${rec.season}</span>
      <span class="badge water">${rec.water_requirement} water need</span>
      <span class="badge ${demandClass}">${rec.market_demand} demand</span>
      ${rec.season_match === true ? '<span class="badge season">✓ matches your season</span>' : ''}
      ${rec.season_match === false ? '<span class="badge demand-low">off-season</span>' : ''}
    </div>

    ${rec.advice && rec.advice.length ? `<ul class="advice-list">${rec.advice.map(a => `<li>${a}</li>`).join('')}</ul>` : ''}

    <div class="yield-row">
      <span>Expected yield</span>
      <span class="v">${rec.yield_estimate.covered
        ? rec.yield_estimate.predicted_yield_tonnes_per_ha + ' t/ha (real, R²=' + rec.yield_estimate.test_r2 + ')'
        : '<span class="not-available">no real yield data for this crop</span>'}</span>
    </div>
    <div class="profit-row">
      <span>Profitability</span>
      <span class="v">${rec.profitability.covered
        ? `<span class="rating-pill ${rec.profitability.rating}">${rec.profitability.rating}</span> ₹${rec.profitability.estimated_revenue_per_ha_rs}/ha revenue`
        : '<span class="not-available">insufficient real data</span>'}</span>
    </div>

    ${renderMarketPanel(rec.market_estimate)}
  `;

  const toggle = card.querySelector('.market-toggle');
  if (toggle) {
    toggle.addEventListener('click', () => {
      const panel = card.querySelector('.market-panel');
      panel.classList.toggle('show');
      toggle.textContent = panel.classList.contains('show') ? 'Hide market data ▴' : 'View market data ▾';
    });
  }
  return card;
}

function renderMarketPanel(market) {
  if (!market) return '';
  if (market.covered) {
    return `
      <button class="market-toggle" type="button">View market data ▾</button>
      <div class="market-panel">
        <span class="price">₹${market.predicted_modal_price} <span style="font-size:.7rem;color:var(--ink-soft)">/ quintal (ML-predicted)</span></span><br>
        <span class="hint">Observed range: ₹${market.observed_price_range[0]}–₹${market.observed_price_range[1]} (${market.state_used || 'nearest state'})</span><br>
        <span class="tag real">real data · R²=${market.test_r2}</span>
      </div>`;
  }
  return `
    <button class="market-toggle" type="button">View market data ▾</button>
    <div class="market-panel"><p class="not-covered">${market.message}</p><span class="tag none">no real dataset for this crop</span></div>`;
}

// ---------------------------------------------------------------------- //
// Soil health
// ---------------------------------------------------------------------- //
async function getSoilHealth() {
  const errorEl = $('soil-health-error');
  const loadingEl = $('soil-health-loading');
  errorEl.classList.remove('show');
  loadingEl.classList.add('show');
  $('soil-health-btn').disabled = true;

  try {
    const res = await fetch('/api/soil-health', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        n: parseFloat($('sh-n').value) || 0, p: parseFloat($('sh-p').value) || 0,
        k: parseFloat($('sh-k').value) || 0, ph: parseFloat($('sh-ph').value) || 6.5,
        organic_carbon: $('sh-oc').value !== '' ? parseFloat($('sh-oc').value) : null,
      }),
    });
    const data = await res.json();
    if (!data.success) throw new Error(data.error || 'Request failed');
    renderSoilHealth(data.result);
  } catch (e) {
    errorEl.textContent = 'Could not analyze soil: ' + e.message;
    errorEl.classList.add('show');
  } finally {
    loadingEl.classList.remove('show');
    $('soil-health-btn').disabled = false;
  }
}

function renderSoilHealth(result) {
  $('soil-health-results').style.display = 'block';
  $('soil-score-n').textContent = result.soil_health_score;
  const circumference = 263.9;
  const offset = circumference * (1 - result.soil_health_score / 100);
  const arc = $('soil-score-arc');
  requestAnimationFrame(() => { arc.style.transition = 'stroke-dashoffset .8s ease'; arc.setAttribute('stroke-dashoffset', offset); });

  const tiles = [
    ['Nitrogen', result.nitrogen_status], ['Phosphorus', result.phosphorus_status],
    ['Potassium', result.potassium_status], ['pH', result.ph_status],
  ];
  if (result.organic_carbon_status) tiles.push(['Organic Carbon', result.organic_carbon_status]);
  $('nutrient-grid').innerHTML = tiles.map(([name, status]) => `
    <div class="nutrient-tile ${status}"><div class="name">${name}</div><div class="status">${status}</div></div>`).join('');

  $('fert-list').innerHTML = result.fertilizer_recommendation.map(f => `
    <div class="fert-item">
      <div class="name">${f.fertilizer}</div>
      <div class="reason">${f.reason}</div>
      <div class="guidance">${f.guidance}</div>
    </div>`).join('');

  $('soil-suggestions').innerHTML = result.improvement_suggestions.map(s => `<li>${s}</li>`).join('');
}

// ---------------------------------------------------------------------- //
// Market
// ---------------------------------------------------------------------- //
async function searchMarket() {
  const crop = $('market-crop').value.trim();
  const errorEl = $('market-error');
  const loadingEl = $('market-loading');
  errorEl.classList.remove('show');
  if (!crop) { errorEl.textContent = 'Enter a crop name.'; errorEl.classList.add('show'); return; }
  loadingEl.classList.add('show');
  $('market-search-btn').disabled = true;

  try {
    const state = $('state').value || '';
    const [predRes, mandiRes] = await Promise.all([
      fetch(`/api/market-trends/${encodeURIComponent(crop)}${state ? '?state=' + encodeURIComponent(state) : ''}`),
      fetch(`/api/market-prices/${encodeURIComponent(crop)}`),
    ]);
    const predData = await predRes.json();
    const mandiData = await mandiRes.json();

    renderMarketPrediction(predData.estimate);
    renderMandiTable(mandiData.result);

    if (userCoords) {
      const nearRes = await fetch(`/api/market-nearby/${encodeURIComponent(crop)}?lat=${userCoords.lat}&lon=${userCoords.lon}`);
      const nearData = await nearRes.json();
      renderNearbyTable(nearData.result);
      $('nearby-hint').textContent = '';
    } else {
      $('nearby-table').querySelector('tbody').innerHTML = '';
      $('nearby-hint').textContent = 'Use your GPS location above (in the crop advisor section) to see distances.';
    }

    $('market-results').style.display = 'block';
  } catch (e) {
    errorEl.textContent = 'Could not fetch market data: ' + e.message;
    errorEl.classList.add('show');
  } finally {
    loadingEl.classList.remove('show');
    $('market-search-btn').disabled = false;
  }
}

function renderMarketPrediction(estimate) {
  const el = $('market-prediction-card');
  if (!estimate || !estimate.covered) {
    el.innerHTML = `<p class="not-covered">${(estimate && estimate.message) || 'No prediction available for this crop.'}</p>`;
    return;
  }
  el.innerHTML = `
    <div class="market-panel show" style="border:none; padding:0; margin:0;">
      <span class="price">₹${estimate.predicted_modal_price} <span style="font-size:.7rem;color:var(--ink-soft)">/ quintal</span></span><br>
      <span class="hint">Observed range: ₹${estimate.observed_price_range[0]}–₹${estimate.observed_price_range[1]} · ${estimate.state_used || ''}</span><br>
      <span class="tag real">${estimate.data_source} · R²=${estimate.test_r2 ?? '—'}</span>
    </div>`;
}

function renderMandiTable(result) {
  const tbody = $('mandi-table').querySelector('tbody');
  if (!result || !result.covered) {
    tbody.innerHTML = `<tr><td colspan="4" class="not-available">${(result && result.message) || 'No real market records for this crop.'}</td></tr>`;
    return;
  }
  tbody.innerHTML = `<tr><th>Market</th><th>State</th><th>Typical price (₹/quintal)</th><th>Range</th></tr>` +
    result.markets.map(m => `
      <tr><td>${m.market}</td><td>${m.state}</td><td class="price">₹${m.typical_price}</td>
      <td>₹${m.price_range[0]}–₹${m.price_range[1]}</td></tr>`).join('');
}

function renderNearbyTable(result) {
  const tbody = $('nearby-table').querySelector('tbody');
  if (!result || !result.covered) {
    tbody.innerHTML = `<tr><td colspan="4" class="not-available">${(result && result.message) || 'No nearby real market data.'}</td></tr>`;
    return;
  }
  tbody.innerHTML = `<tr><th>Market</th><th>Distance</th><th>Typical price (₹/quintal)</th><th></th></tr>` +
    result.markets.map((m, i) => `
      <tr><td>${m.market}, ${m.state}</td><td>${m.distance_km} km</td><td class="price">₹${m.typical_price}</td>
      <td>${i === 0 ? '<span class="nearest-tag">nearest</span>' : ''}</td></tr>`).join('');
}

// ---------------------------------------------------------------------- //
// Irrigation schedule
// ---------------------------------------------------------------------- //
async function getIrrigationSchedule() {
  const errorEl = $('water-error');
  const loadingEl = $('water-loading');
  errorEl.classList.remove('show');
  loadingEl.classList.add('show');
  $('water-btn').disabled = true;

  const payload = {
    crop_type: $('water-crop').value.trim() || 'rice',
    soil_type: $('water-soil').value.trim() || 'loamy',
    location: $('water-location').value.trim() || $('location').value.trim() || 'Delhi',
  };
  if (userCoords) { payload.lat = userCoords.lat; payload.lon = userCoords.lon; }

  try {
    const res = await fetch('/api/water-management', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    const data = await res.json();
    if (!data.success) throw new Error(data.error || 'Request failed');
    renderWaterAdvice(data.advice, data.summary);
  } catch (e) {
    errorEl.textContent = 'Could not build schedule: ' + e.message;
    errorEl.classList.add('show');
  } finally {
    loadingEl.classList.remove('show');
    $('water-btn').disabled = false;
  }
}

function renderWaterAdvice(advice, summary) {
  $('water-summary-card').style.display = 'block';
  $('water-crop-title').textContent = advice.crop.replace(/_/g, ' ');
  $('water-meta').textContent =
    `Seasonal requirement: ~${advice.seasonal_requirement_mm} mm · ` +
    `Target soil moisture: ${advice.soil_moisture_target_pct}% · ` +
    `Critical stages: ${advice.critical_stages.join(', ')}`;
  $('water-tips').innerHTML = advice.water_conservation_tips.map(t => `<li>${t}</li>`).join('');

  if (summary) {
    $('irrigation-headline').innerHTML = `
      <div class="stat"><span class="n">${summary.water_required_mm}mm</span><span class="label">Water required</span></div>
      <div class="stat"><span class="n">${summary.next_irrigation_in_days ? 'After ' + summary.next_irrigation_in_days + ' day' + (summary.next_irrigation_in_days !== 1 ? 's' : '') : 'Not needed'}</span><span class="label">Next irrigation</span></div>`;
  }

  const tbody = $('schedule-body');
  tbody.innerHTML = advice.irrigation_schedule.map(day => `
    <tr>
      <td>${day.day}</td><td>${day.date || '—'}</td>
      <td><span class="pill ${day.irrigation_needed ? 'yes' : 'no'}">${day.irrigation_needed ? 'Irrigate' : 'Skip'}</span></td>
      <td>${day.water_amount_mm || 0}</td><td>${day.reason}</td>
    </tr>`).join('');

  $('water-results').style.display = 'block';
}

// ---------------------------------------------------------------------- //
// Fertilizer recommendation
// ---------------------------------------------------------------------- //
async function getFertilizerPlan() {
  const errorEl = $('fertilizer-error');
  const loadingEl = $('fertilizer-loading');
  errorEl.classList.remove('show');
  loadingEl.classList.add('show');
  $('fertilizer-btn').disabled = true;

  try {
    const res = await fetch('/api/fertilizer-plan', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ crop: $('fert-crop').value.trim(), area_acres: parseFloat($('fert-area').value) || 1 }),
    });
    const data = await res.json();
    if (!data.success) throw new Error(data.error || 'Request failed');
    renderFertilizerPlan(data.result);
  } catch (e) {
    errorEl.textContent = 'Could not build plan: ' + e.message;
    errorEl.classList.add('show');
  } finally {
    loadingEl.classList.remove('show');
    $('fertilizer-btn').disabled = false;
  }
}

function renderFertilizerPlan(result) {
  if (!result.covered) {
    $('fert-plan-list').innerHTML = `<p class="not-covered">${result.message}</p>`;
    $('fert-total-cost').textContent = '';
    $('fert-reference-note').textContent = '';
    $('fertilizer-results').style.display = 'block';
    return;
  }
  $('fert-plan-list').innerHTML = result.items.map(i => `
    <div class="fert-plan-item">
      <div class="left"><div class="name">${i.fertilizer}</div><div class="stage">${i.stage}</div></div>
      <div class="right"><div class="qty">${i.quantity_kg} kg</div><div class="cost">₹${i.approx_cost_rs}</div></div>
    </div>`).join('');
  $('fert-total-cost').textContent = `₹${result.total_approx_cost_rs}`;
  $('fert-reference-note').textContent = result.reference;
  $('fertilizer-results').style.display = 'block';
}

// ---------------------------------------------------------------------- //
// Disease check (symptom-based, not image AI)
// ---------------------------------------------------------------------- //
async function loadSymptoms() {
  const crop = $('disease-crop').value.trim();
  if (!crop) return;
  try {
    const res = await fetch(`/api/disease-symptoms/${encodeURIComponent(crop)}`);
    const data = await res.json();
    const list = $('symptom-list');
    if (!data.result.covered || !data.result.symptoms.length) {
      list.innerHTML = `<p class="not-covered">No symptom reference for '${crop}' yet.</p>`;
      return;
    }
    list.innerHTML = data.result.symptoms.map((s, i) => `
      <label class="symptom-check"><input type="checkbox" value="${s.replace(/"/g, '&quot;')}" id="sym-${i}"> ${s}</label>`).join('');
  } catch (e) { /* leave list as-is */ }
}

async function checkDisease() {
  const errorEl = $('disease-error');
  const loadingEl = $('disease-loading');
  errorEl.classList.remove('show');
  loadingEl.classList.add('show');
  $('disease-check-btn').disabled = true;

  const selected = Array.from(document.querySelectorAll('#symptom-list input:checked')).map(el => el.value);
  try {
    const res = await fetch('/api/disease-check', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ crop: $('disease-crop').value.trim(), symptoms: selected }),
    });
    const data = await res.json();
    if (!data.success) throw new Error(data.error || 'Request failed');
    renderDiseaseResults(data.result);
  } catch (e) {
    errorEl.textContent = 'Could not check symptoms: ' + e.message;
    errorEl.classList.add('show');
  } finally {
    loadingEl.classList.remove('show');
    $('disease-check-btn').disabled = false;
  }
}

function renderDiseaseResults(result) {
  const el = $('disease-results');
  el.style.display = 'block';
  if (!result.covered) { el.innerHTML = `<p class="not-covered">${result.message}</p>`; return; }
  if (!result.matches.length) { el.innerHTML = `<p class="not-covered">${result.message}</p>`; return; }
  el.innerHTML = result.matches.map(m => `
    <div class="disease-match">
      <h4>${m.disease}</h4>
      <div class="row"><b>Likely cause:</b> ${m.cause}</div>
      <div class="row"><b>Treatment:</b> ${m.treatment}</div>
      <div class="row"><b>Recommended:</b> ${m.recommended_fungicide}</div>
    </div>`).join('') + `<p class="hint">${result.disclaimer}</p>`;
}

async function uploadDiseasePhoto(e) {
  const file = e.target.files[0];
  if (!file) return;
  const preview = $('photo-preview');
  preview.src = URL.createObjectURL(file);
  preview.style.display = 'block';

  const formData = new FormData();
  formData.append('photo', file);
  try {
    await fetch('/api/disease-photo', { method: 'POST', body: formData });
  } catch (e2) { /* preview still shows locally even if upload fails */ }
}

// ---------------------------------------------------------------------- //
// Crop calendar
// ---------------------------------------------------------------------- //
async function buildCropCalendar() {
  const errorEl = $('calendar-error');
  const loadingEl = $('calendar-loading');
  errorEl.classList.remove('show');
  loadingEl.classList.add('show');
  $('calendar-btn').disabled = true;

  try {
    const res = await fetch('/api/crop-calendar', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ crop: $('cal-crop').value.trim(), sowing_date: $('cal-sowing-date').value }),
    });
    const data = await res.json();
    if (!data.success) throw new Error(data.error || 'Request failed');
    renderCropCalendar(data.result);
  } catch (e) {
    errorEl.textContent = 'Could not build calendar: ' + e.message;
    errorEl.classList.add('show');
  } finally {
    loadingEl.classList.remove('show');
    $('calendar-btn').disabled = false;
  }
}

function renderCropCalendar(result) {
  $('calendar-results').style.display = 'block';
  if (!result.covered) {
    $('calendar-summary').textContent = result.message;
    $('calendar-list').innerHTML = '';
    return;
  }
  if (result.type === 'perennial') {
    $('calendar-summary').textContent = result.message;
    $('calendar-list').innerHTML = '';
    return;
  }
  $('calendar-summary').textContent = `${result.duration_days}-day crop · sown ${result.sowing_date} · expected harvest ${result.expected_harvest_date}`;
  $('calendar-list').innerHTML = result.events.map(ev => `
    <li class="calendar-event"><span class="dot ${ev.type}"></span><span class="date">${ev.date}</span><span class="label">${ev.label}</span></li>`).join('');
}

// ---------------------------------------------------------------------- //
// Standalone yield prediction
// ---------------------------------------------------------------------- //
async function predictYield() {
  const errorEl = $('yield-error');
  const loadingEl = $('yield-loading');
  errorEl.classList.remove('show');
  loadingEl.classList.add('show');
  $('yield-predict-btn').disabled = true;

  try {
    const res = await fetch('/api/yield-prediction', {
      method: 'POST', credentials: 'include', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        crop: $('yp-crop').value.trim(), area_acres: parseFloat($('yp-area').value) || 1,
        state: $('yp-state').value || null, season: $('yp-season').value || null,
      }),
    });
    const data = await res.json();
    if (!data.success) throw new Error(data.error || 'Request failed');
    renderYieldResult(data.result);
  } catch (e) {
    errorEl.textContent = 'Could not predict yield: ' + e.message;
    errorEl.classList.add('show');
  } finally {
    loadingEl.classList.remove('show');
    $('yield-predict-btn').disabled = false;
  }
}

function renderYieldResult(result) {
  const el = $('yield-results');
  el.style.display = 'block';
  if (!result.covered) {
    el.innerHTML = `<p class="not-covered">No real yield data for '${result.crop}'. Currently covers: rice, maize, chickpea, pigeonpeas, mothbeans, mungbean, blackgram, lentil, banana, cotton, jute.</p>`;
    return;
  }
  el.innerHTML = `
    <div class="result-headline">
      <div class="stat"><span class="n">${result.total_expected_yield_tonnes}</span><span class="label">Expected yield (tonnes)</span></div>
      <div class="stat"><span class="n">${Math.round(result.test_r2 * 100)}%</span><span class="label">Model fit (R²)</span></div>
    </div>
    <p class="hint">${result.predicted_yield_tonnes_per_ha} t/ha over ${result.area_acres} acres · observed range in training data: ${result.observed_range_tonnes_per_ha[0]}–${result.observed_range_tonnes_per_ha[1]} t/ha (${result.state_used}, ${result.season_used})</p>
    <p class="hint" style="font-size:.76rem;">${result.accuracy_pct_note}</p>`;
}

// ---------------------------------------------------------------------- //
// Profit estimation
// ---------------------------------------------------------------------- //
async function estimateProfit() {
  const errorEl = $('profit-error');
  const loadingEl = $('profit-loading');
  errorEl.classList.remove('show');
  loadingEl.classList.add('show');
  $('profit-btn').disabled = true;

  const expenses = {
    seeds: parseFloat($('exp-seeds').value) || 0, fertilizer: parseFloat($('exp-fertilizer').value) || 0,
    labour: parseFloat($('exp-labour').value) || 0, water: parseFloat($('exp-water').value) || 0,
    pesticides: parseFloat($('exp-pesticides').value) || 0,
  };

  try {
    const res = await fetch('/api/profit-estimation', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        crop: $('profit-crop').value.trim(), area_acres: parseFloat($('profit-area').value) || 1,
        expenses,
        manual_price_rs_per_quintal: $('profit-manual-price').value ? parseFloat($('profit-manual-price').value) : null,
      }),
    });
    const data = await res.json();
    if (!data.success) throw new Error(data.error || 'Request failed');
    renderProfitResult(data.result);
  } catch (e) {
    errorEl.textContent = 'Could not estimate profit: ' + e.message;
    errorEl.classList.add('show');
  } finally {
    loadingEl.classList.remove('show');
    $('profit-btn').disabled = false;
  }
}

function renderProfitResult(result) {
  const el = $('profit-results');
  el.style.display = 'block';
  if (!result.covered) {
    el.innerHTML = `<p class="not-covered">${result.message} (Total expenses entered: ₹${result.total_expenses_rs})</p>`;
    return;
  }
  const cls = result.net_profit_rs >= 0 ? 'positive' : 'negative';
  el.innerHTML = `
    <div class="result-headline">
      <div class="stat"><span class="n">₹${result.income_rs}</span><span class="label">Income</span></div>
      <div class="stat"><span class="n">₹${result.total_expenses_rs}</span><span class="label">Expenses</span></div>
      <div class="stat profit"><span class="n ${cls}">₹${result.net_profit_rs}</span><span class="label">Net profit</span></div>
    </div>
    <p class="hint">${result.expected_yield_tonnes} tonnes × ₹${result.price_per_quintal_rs}/quintal (${result.price_source})</p>`;
}

// ---------------------------------------------------------------------- //
// Farm dashboard
// ---------------------------------------------------------------------- //
let dashCharts = {};

function toggleRecordCategory() {
  $('rec-category-field').style.display = $('rec-type').value === 'expense' ? 'block' : 'none';
}

async function addFarmRecord() {
  const type = $('rec-type').value;
  const payload = {
    amount_rs: parseFloat($('rec-amount').value) || 0,
    crop: $('rec-crop').value.trim() || null,
  };
  if (type === 'expense') payload.category = $('rec-category').value;
  try {
    await fetch(`/api/farm/${type}`, {
      method: 'POST', credentials: 'include', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    $('rec-amount').value = '0';
    loadDashboard();
  } catch (e) { /* leave form as-is */ }
}

async function loadDashboard() {
  try {
    const res = await fetch('/api/farm/dashboard', { credentials: 'include' });
    const data = await res.json();
    if (!data.success) return;
    renderDashboard(data.dashboard);
  } catch (e) { /* dashboard just stays empty */ }
}

function renderDashboard(dash) {
  const s = dash.summary;
  if (!s.records_present) {
    $('dashboard-empty').style.display = 'block';
    $('dashboard-charts-wrap').style.display = 'none';
    return;
  }
  $('dashboard-empty').style.display = 'none';
  $('dashboard-charts-wrap').style.display = 'block';

  $('dash-summary').innerHTML = `
    <div class="dash-stat"><div class="n">₹${s.total_income_rs}</div><div class="label">Total income</div></div>
    <div class="dash-stat"><div class="n">₹${s.total_expenses_rs}</div><div class="label">Total expenses</div></div>
    <div class="dash-stat"><div class="n">₹${s.net_profit_rs}</div><div class="label">Net profit</div></div>`;

  const catEntries = Object.entries(s.expenses_by_category);
  drawChart('chart-expenses', 'doughnut', catEntries.map(e => e[0]), [{
    data: catEntries.map(e => e[1]), backgroundColor: ['#E2892C', '#6FA96B', '#4C91C5', '#9C5A3C', '#24314F', '#C6871F'],
  }]);

  drawChart('chart-income-expense', 'bar', ['Income', 'Expenses'], [{
    data: [s.total_income_rs, s.total_expenses_rs], backgroundColor: ['#6FA96B', '#9C5A3C'],
  }]);

  const soilSorted = [...dash.soil_health_logs].reverse();
  drawChart('chart-soil', 'line', soilSorted.map(l => l.created_at.slice(0, 10)), [{
    label: 'Soil health score', data: soilSorted.map(l => l.score), borderColor: '#6FA96B', tension: .3,
  }]);

  const waterSorted = [...dash.water_usage_logs].reverse();
  drawChart('chart-water', 'bar', waterSorted.map(l => l.created_at.slice(0, 10)), [{
    label: 'Water (mm)', data: waterSorted.map(l => l.total_water_mm), backgroundColor: '#4C91C5',
  }]);
}

function drawChart(canvasId, type, labels, datasets) {
  if (typeof Chart === 'undefined') return;
  if (dashCharts[canvasId]) dashCharts[canvasId].destroy();
  const ctx = document.getElementById(canvasId);
  if (!ctx) return;
  dashCharts[canvasId] = new Chart(ctx, {
    type, data: { labels, datasets },
    options: { responsive: true, plugins: { legend: { display: type !== 'bar' || datasets.length > 1 } } },
  });
}

// ---------------------------------------------------------------------- //
// Interactive farm map (Leaflet + OpenStreetMap — free, no API key)
// ---------------------------------------------------------------------- //
let farmMap = null;

async function refreshFarmMap() {
  if (typeof L === 'undefined') return;
  const lat = userCoords ? userCoords.lat : 20.5937;
  const lon = userCoords ? userCoords.lon : 78.9629;

  if (!farmMap) {
    farmMap = L.map('farm-map').setView([lat, lon], userCoords ? 10 : 5);
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
      attribution: '© OpenStreetMap contributors',
    }).addTo(farmMap);
  } else {
    farmMap.setView([lat, lon], userCoords ? 10 : 5);
  }

  farmMap.eachLayer(layer => { if (layer instanceof L.Marker) farmMap.removeLayer(layer); });

  if (userCoords) {
    L.marker([lat, lon]).addTo(farmMap).bindPopup(
      `<b>Your farm location</b>${currentUser && currentUser.soil_type ? `<br>Soil type: ${currentUser.soil_type}` : ''}`
    ).openPopup();
  }

  const crop = $('map-crop').value.trim();
  if (crop && userCoords) {
    try {
      const res = await fetch(`/api/market-nearby/${encodeURIComponent(crop)}?lat=${lat}&lon=${lon}`);
      const data = await res.json();
      if (data.result && data.result.covered) {
        data.result.markets.forEach(m => {
          L.marker([m.lat, m.lon], { icon: L.divIcon({ className: '', html: '📍', iconSize: [20, 20] }) })
            .addTo(farmMap)
            .bindPopup(`<b>${m.market}, ${m.state}</b><br>${m.distance_km} km away<br>Typical price: ₹${m.typical_price}/quintal`);
        });
      }
    } catch (e) { /* map still shows farm location */ }
  }
}

// ---------------------------------------------------------------------- //
// Knowledge base
// ---------------------------------------------------------------------- //
let kbData = null;

async function loadKnowledgeBase() {
  try {
    const res = await fetch('/api/knowledge-base');
    const data = await res.json();
    if (data.success) { kbData = data.result; switchKbTab('articles'); }
  } catch (e) { /* section stays empty */ }
}

function switchKbTab(tab) {
  document.querySelectorAll('.kb-tab').forEach(t => t.classList.toggle('active', t.dataset.kb === tab));
  if (!kbData) return;
  const el = $('kb-content');

  if (tab === 'articles') {
    el.innerHTML = kbData.articles.map(a => `
      <div class="kb-article"><h4>${a.title}</h4><p class="hint">${a.summary}</p>
      <div class="search-hint">Search: "${a.search_term}"</div></div>`).join('') +
      `<p class="hint" style="margin-top:10px;">${kbData.videos_note}</p>`;
  } else if (tab === 'best_practices') {
    el.innerHTML = `<ul class="tips-list">${kbData.best_practices.map(t => `<li>${t}</li>`).join('')}</ul>`;
  } else if (tab === 'organic_farming') {
    el.innerHTML = `<ul class="tips-list">${kbData.organic_farming.map(t => `<li>${t}</li>`).join('')}</ul>`;
  } else if (tab === 'pest_management') {
    el.innerHTML = `<ul class="tips-list">${kbData.pest_management.map(t => `<li>${t}</li>`).join('')}</ul>`;
  } else if (tab === 'government_schemes') {
    el.innerHTML = kbData.government_schemes.map(s => `
      <div class="kb-scheme"><b>${s.name}</b><p class="hint" style="margin:4px 0;">${s.purpose}</p>
      <a href="${s.official_url}" target="_blank" rel="noopener">${s.official_url}</a></div>`).join('') +
      `<p class="hint" style="margin-top:10px;">${kbData.disclaimer}</p>`;
  }
}
