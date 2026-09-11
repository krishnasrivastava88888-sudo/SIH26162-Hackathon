import json
import os

JSON_SOURCE = "data/processed/classified_hotspots.json"

with open(JSON_SOURCE, "r", encoding="utf-8") as f:
    hotspots_data = json.load(f)

dashboard_template = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ThermoGuard AI | Tactical Thermal Intelligence Dashboard</title>
    <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
    <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
    <style>
        :root {{
            --bg-base: #0a0d14;
            --bg-card: rgba(16, 22, 34, 0.95);
            --border-line: #1e293b;
            --color-critical: #ef4444;
            --color-flare: #eab308;
            --color-wildfire: #f97316;
            --color-agri: #10b981;
            --text-main: #f8fafc;
            --text-muted: #94a3b8;
        }}

        * {{ box-sizing: border-box; margin: 0; padding: 0; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            background-color: var(--bg-base);
            color: var(--text-main);
            overflow: hidden;
            display: flex;
            flex-direction: column;
            height: 100vh;
        }}

        header {{
            height: 54px;
            background: #0f172a;
            border-bottom: 1px solid var(--border-line);
            display: flex;
            align-items: center;
            justify-content: space-between;
            padding: 0 20px;
            z-index: 100;
        }}
        .brand {{ display: flex; align-items: center; gap: 10px; font-size: 15px; font-weight: 700; }}
        .brand span {{ color: #38bdf8; font-weight: 400; }}
        .status-pill {{
            font-size: 12px;
            background: rgba(16, 185, 129, 0.15);
            color: #34d399;
            border: 1px solid rgba(16, 185, 129, 0.3);
            padding: 4px 10px;
            border-radius: 9999px;
            display: flex;
            align-items: center;
            gap: 6px;
        }}
        .status-dot {{ width: 8px; height: 8px; border-radius: 50%; background: #34d399; }}

        .kpi-row {{
            display: grid;
            grid-template-columns: repeat(4, 1fr);
            gap: 12px;
            padding: 10px 20px;
            background: rgba(15, 23, 42, 0.7);
            border-bottom: 1px solid var(--border-line);
        }}
        .kpi-card {{
            background: var(--bg-card);
            border: 1px solid var(--border-line);
            border-radius: 8px;
            padding: 10px 14px;
            display: flex;
            flex-direction: column;
            justify-content: center;
            position: relative;
        }}
        .kpi-label {{ font-size: 11px; text-transform: uppercase; color: var(--text-muted); font-weight: 600; }}
        .kpi-value {{ font-size: 22px; font-weight: 800; margin-top: 4px; }}
        .pulse-indicator {{
            width: 10px; height: 10px;
            background-color: var(--color-critical);
            border-radius: 50%;
            position: absolute; top: 12px; right: 12px;
            box-shadow: 0 0 0 0 rgba(239, 68, 68, 0.7);
            animation: pulse-red 1.6s infinite;
        }}
        @keyframes pulse-red {{
            0% {{ transform: scale(0.95); box-shadow: 0 0 0 0 rgba(239, 68, 68, 0.7); }}
            70% {{ transform: scale(1); box-shadow: 0 0 0 8px rgba(239, 68, 68, 0); }}
            100% {{ transform: scale(0.95); box-shadow: 0 0 0 0 rgba(239, 68, 68, 0); }}
        }}

        .filter-bar {{
            padding: 10px 20px;
            background: #0b1120;
            border-bottom: 1px solid var(--border-line);
            display: flex;
            flex-wrap: wrap;
            align-items: center;
            gap: 14px;
            font-size: 13px;
        }}
        .pills {{ display: flex; gap: 8px; }}
        .pill-btn {{
            background: #1e293b;
            color: var(--text-muted);
            border: 1px solid transparent;
            padding: 5px 12px;
            border-radius: 6px;
            cursor: pointer;
            font-size: 12px;
            font-weight: 600;
            transition: all 0.15s;
        }}
        .pill-btn.active {{ background: #38bdf8; color: #000; border-color: #38bdf8; }}
        .pill-btn:hover:not(.active) {{ background: #334155; color: #fff; }}

        .search-box {{ flex-grow: 1; max-width: 280px; }}
        .search-box input {{
            width: 100%;
            background: #1e293b;
            border: 1px solid #334155;
            padding: 6px 12px;
            border-radius: 6px;
            color: #fff;
            font-size: 12px;
            outline: none;
        }}
        .slider-box {{ display: flex; align-items: center; gap: 8px; color: var(--text-muted); font-size: 12px; }}
        .slider-box input {{ accent-color: #38bdf8; cursor: pointer; }}

        .export-btn {{
            background: #22c55e;
            color: #000;
            border: none;
            padding: 5px 12px;
            border-radius: 6px;
            cursor: pointer;
            font-size: 12px;
            font-weight: 700;
            display: flex;
            align-items: center;
            gap: 6px;
            margin-left: auto;
        }}
        .export-btn:hover {{ background: #16a34a; }}

        .workspace {{ display: flex; flex-grow: 1; position: relative; overflow: hidden; }}
        #map {{ flex-grow: 1; height: 100%; background: #000; }}

        .feed-drawer {{
            width: 380px;
            background: var(--bg-card);
            border-left: 1px solid var(--border-line);
            display: flex;
            flex-direction: column;
            overflow: hidden;
            z-index: 10;
        }}
        .feed-header {{
            padding: 12px 16px;
            border-bottom: 1px solid var(--border-line);
            font-size: 13px;
            font-weight: 700;
            display: flex;
            justify-content: space-between;
        }}
        .feed-list {{ flex-grow: 1; overflow-y: auto; padding: 10px; display: flex; flex-direction: column; gap: 8px; }}
        .incident-card {{
            background: #131b2e;
            border: 1px solid var(--border-line);
            border-radius: 6px;
            padding: 10px 12px;
            cursor: pointer;
            transition: border 0.15s;
        }}
        .incident-card:hover {{ border-color: #38bdf8; }}
        .card-top {{ display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px; }}
        .badge {{
            font-size: 10px;
            font-weight: 700;
            padding: 2px 6px;
            border-radius: 4px;
            text-transform: uppercase;
        }}
        .badge.CRITICAL {{ background: rgba(239,68,68,0.2); color: #f87171; border: 1px solid #ef4444; }}
        .badge.FLARE {{ background: rgba(234,179,8,0.2); color: #facc15; border: 1px solid #eab308; }}
        .badge.AGRI {{ background: rgba(16,185,129,0.2); color: #34d399; border: 1px solid #10b981; }}
        .badge.WILD {{ background: rgba(249,115,22,0.2); color: #fb923c; border: 1px solid #f97316; }}

        .card-title {{ font-size: 13px; font-weight: 600; margin-bottom: 4px; }}
        .card-meta {{ font-size: 11px; color: var(--text-muted); display: flex; justify-content: space-between; }}
    </style>
</head>
<body>

    <header>
        <div class="brand">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#38bdf8" stroke-width="2.5"><path d="M12 2c0 4-4 6-4 10a4 4 0 0 0 8 0c0-4-4-6-4-10z"/></svg>
            ThermoGuard AI <span>/ NTRO Intelligence Gateway</span>
        </div>
        <div class="status-pill"><div class="status-dot"></div> VIIRS NOAA-21 LIVE ORBIT FEED</div>
    </header>

    <div class="kpi-row">
        <div class="kpi-card">
            <div class="kpi-label">Active Anomalies</div>
            <div class="kpi-value" id="kpi-total">0</div>
        </div>
        <div class="kpi-card">
            <div class="pulse-indicator"></div>
            <div class="kpi-label" style="color: #f87171;">Critical Industrial Fires</div>
            <div class="kpi-value" id="kpi-critical" style="color: #f87171;">0</div>
        </div>
        <div class="kpi-card">
            <div class="kpi-label" style="color: #facc15;">Persistent Industrial Flares</div>
            <div class="kpi-value" id="kpi-flares" style="color: #facc15;">0</div>
        </div>
        <div class="kpi-card">
            <div class="kpi-label" style="color: #34d399;">Agricultural Stubble Burns</div>
            <div class="kpi-value" id="kpi-agri" style="color: #34d399;">0</div>
        </div>
    </div>

    <div class="filter-bar">
        <div class="pills">
            <button class="pill-btn active" onclick="setCategoryFilter('ALL', this)">All Detections</button>
            <button class="pill-btn" onclick="setCategoryFilter('CRITICAL_ACCIDENTAL', this)">Critical Fires</button>
            <button class="pill-btn" onclick="setCategoryFilter('INDUSTRIAL_FLARE', this)">Industrial Flares</button>
            <button class="pill-btn" onclick="setCategoryFilter('AGRICULTURAL_FIRE', this)">Agricultural</button>
            <button class="pill-btn" onclick="setCategoryFilter('WILDFIRE_BIOMASS', this)">Wildfires</button>
        </div>

        <div class="search-box">
            <input type="text" id="searchInput" placeholder="Search facility, coordinates..." onkeyup="handleSearch(this.value)">
        </div>

        <div class="slider-box">
            <span>Min FRP:</span>
            <input type="range" id="frpSlider" min="0" max="300" step="5" value="0" oninput="handleSlider(this.value)">
            <b id="frpValueDisplay" style="color: #fff; min-width: 45px;">0 MW</b>
        </div>

        <button class="export-btn" onclick="exportGeoJSON()">⭳ Export GeoJSON</button>
    </div>

    <div class="workspace">
        <div id="map"></div>
        <aside class="feed-drawer">
            <div class="feed-header">
                <span>INCIDENT LOG FEED</span>
                <span id="renderedCount" style="color: #38bdf8;">0 Items</span>
            </div>
            <div class="feed-list" id="incidentFeed"></div>
        </aside>
    </div>

    <script>
        const rawHotspots = {json.dumps(hotspots_data)};
        let activeCategory = 'ALL';
        let currentSearch = '';
        let minFrpThreshold = 0;
        let currentlyFilteredData = [];

        const map = L.map('map', {{ zoomControl: true }}).setView([22.8, 82.0], 5);
        L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{{z}}/{{y}}/{{x}}', {{
            maxZoom: 18,
            attribution: 'Tiles &copy; Esri'
        }}).addTo(map);

        const markerGroup = L.layerGroup().addTo(map);

        function getClassificationConfig(cls) {{
            switch(cls) {{
                case 'CRITICAL_ACCIDENTAL':
                    return {{ color: '#ef4444', label: 'CRITICAL FIRE', badge: 'CRITICAL', radius: 8 }};
                case 'INDUSTRIAL_FLARE':
                    return {{ color: '#eab308', label: 'PERSISTENT FLARE', badge: 'FLARE', radius: 6 }};
                case 'AGRICULTURAL_FIRE':
                    return {{ color: '#10b981', label: 'AGRICULTURAL', badge: 'AGRI', radius: 4 }};
                default:
                    return {{ color: '#f97316', label: 'WILDFIRE', badge: 'WILD', radius: 5 }};
            }}
        }}

        function updateKPIs(data) {{
            let crit = 0, flares = 0, agri = 0;
            data.forEach(item => {{
                if (item.classification === 'CRITICAL_ACCIDENTAL') crit++;
                else if (item.classification === 'INDUSTRIAL_FLARE') flares++;
                else if (item.classification === 'AGRICULTURAL_FIRE') agri++;
            }});
            document.getElementById('kpi-total').innerText = data.length;
            document.getElementById('kpi-critical').innerText = crit;
            document.getElementById('kpi-flares').innerText = flares;
            document.getElementById('kpi-agri').innerText = agri;
        }}

        function renderView() {{
            markerGroup.clearLayers();
            const feedContainer = document.getElementById('incidentFeed');
            feedContainer.innerHTML = '';

            currentlyFilteredData = rawHotspots.filter(d => {{
                const matchCategory = (activeCategory === 'ALL') || (d.classification === activeCategory);
                const matchFRP = d.frp >= minFrpThreshold;
                const matchQuery = currentSearch === '' || 
                    d.nearest_facility.toLowerCase().includes(currentSearch) ||
                    d.classification.toLowerCase().includes(currentSearch) ||
                    String(d.latitude).includes(currentSearch) ||
                    String(d.longitude).includes(currentSearch);

                return matchCategory && matchFRP && matchQuery;
            }});

            document.getElementById('renderedCount').innerText = `${{currentlyFilteredData.length}} Items`;
            updateKPIs(currentlyFilteredData);

            currentlyFilteredData.forEach(item => {{
                const cfg = getClassificationConfig(item.classification);

                const marker = L.circleMarker([item.latitude, item.longitude], {{
                    radius: cfg.radius,
                    fillColor: cfg.color,
                    color: '#ffffff',
                    weight: 1,
                    opacity: 0.95,
                    fillOpacity: 0.85
                }}).bindPopup(`
                    <div style="color: #0f172a; font-size: 13px; line-height: 1.5;">
                        <span style="font-weight: 800; color: ${{cfg.color}};">${{cfg.label}}</span><br>
                        <b>Facility:</b> ${{item.nearest_facility}}<br>
                        <b>FRP:</b> ${{item.frp}} MW<br>
                        <b>Brightness:</b> ${{item.brightness_k}} K<br>
                        <b>30d Recurrence:</b> ${{item.persistence_count_30d}} active days<br>
                        <b>Confidence:</b> ${{Math.round(item.confidence_score * 100)}}%<br>
                        <b>Time (IST):</b> ${{item.acq_timestamp_ist}}
                    </div>
                `);

                markerGroup.addLayer(marker);

                const card = document.createElement('div');
                card.className = 'incident-card';
                card.onclick = () => {{
                    map.flyTo([item.latitude, item.longitude], 13, {{ duration: 1.2 }});
                    marker.openPopup();
                }};
                card.innerHTML = `
                    <div class="card-top">
                        <span class="badge ${{cfg.badge}}">${{cfg.label}}</span>
                        <span style="font-size: 11px; font-weight: bold; color: ${{cfg.color}};">${{item.frp}} MW</span>
                    </div>
                    <div class="card-title">${{item.nearest_facility !== 'None (Open / Rural Area)' ? item.nearest_facility : 'Rural Sector'}}</div>
                    <div class="card-meta">
                        <span>Recurrence: ${{item.persistence_count_30d}}d</span>
                        <span>${{item.latitude}}, ${{item.longitude}}</span>
                    </div>
                `;
                feedContainer.appendChild(card);
            }});
        }}

        function setCategoryFilter(category, btnElement) {{
            activeCategory = category;
            document.querySelectorAll('.pill-btn').forEach(b => b.classList.remove('active'));
            btnElement.classList.add('active');
            renderView();
        }}

        function handleSearch(val) {{
            currentSearch = val.trim().toLowerCase();
            renderView();
        }}

        function handleSlider(val) {{
            minFrpThreshold = parseFloat(val);
            document.getElementById('frpValueDisplay').innerText = `${{val}} MW`;
            renderView();
        }}

        function exportGeoJSON() {{
            const geojson = {{
                type: "FeatureCollection",
                features: currentlyFilteredData.map(d => ({{
                    type: "Feature",
                    geometry: {{ type: "Point", coordinates: [d.longitude, d.latitude] }},
                    properties: d
                }}))
            }};
            const dataStr = "data:text/json;charset=utf-8," + encodeURIComponent(JSON.stringify(geojson, null, 2));
            const downloadAnchor = document.createElement('a');
            downloadAnchor.setAttribute("href", dataStr);
            downloadAnchor.setAttribute("download", `thermoguard_export_${{activeCategory.toLowerCase()}}.geojson`);
            document.body.appendChild(downloadAnchor);
            downloadAnchor.click();
            downloadAnchor.remove();
        }}

        renderView();
    </script>
</body>
</html>
"""

with open("dashboard.html", "w", encoding="utf-8") as f:
    f.write(dashboard_template)

print("dashboard.html recompiled with GeoJSON export functionality.")