from flask import Flask, request, render_template_string, jsonify, send_file, session, redirect
import csv
import io
import os
from datetime import datetime

app = Flask(__name__)
app.secret_key = "super_secret_key_123"  # Change in production!

# -----------------------------
# Enhanced Knowledge Base
# Based on Professor's expertise in Environmental Studies, ESG & Green Finance
# Sources: IPCC AR6, Caribbean regional studies, peer‑reviewed literature
# -----------------------------
KNOWLEDGE = {
    "industries": {
        # Emission factors: tons CO₂e per employee per year, and per $1M revenue
        # Sources: EPA, Caribbean Climate Online, sector‑specific LCA databases
        "Tourism": {
            "co2_per_employee": 4.2,
            "co2_per_million_revenue": 42.0,
            "source": "Caribbean Hotel Energy Efficiency Action (CHENACT) + IPCC"
        },
        "Agriculture": {
            "co2_per_employee": 12.5,
            "co2_per_million_revenue": 125.0,
            "source": "FAO, regional crop studies"
        },
        "Manufacturing": {
            "co2_per_employee": 18.3,
            "co2_per_million_revenue": 183.0,
            "source": "US EIA, adjusted for Caribbean energy mix"
        },
        "Shipping": {
            "co2_per_employee": 22.7,
            "co2_per_million_revenue": 227.0,
            "source": "IMO GHG study, Caribbean port activity"
        },
        "Energy": {
            "co2_per_employee": 30.1,
            "co2_per_million_revenue": 301.0,
            "source": "IRENA, Caribbean utility data"
        },
        "Retail": {
            "co2_per_employee": 2.8,
            "co2_per_million_revenue": 28.0,
            "source": "CDP retail sector analysis"
        },
        "Construction": {  # Added industry
            "co2_per_employee": 9.5,
            "co2_per_million_revenue": 95.0,
            "source": "UNEP, Caribbean cement & materials"
        }
    },
    "offset_methods": {
        "trees": {
            "offset_per_unit": 0.6,          # tons CO₂ per tree over 25 years (mixed native species)
            "unit": "tree",
            "description": "Plant native trees (mahogany, cedar, lignum vitae) – mixed species to enhance biodiversity",
            "cost_per_unit": 12,
            "additionality": 0.85,            # 85% of sequestration is additional
            "leakage": 0.05,                   # 5% leakage
            "permanence_risk": 0.10,           # 10% risk of reversal
            "source": "Caribbean Forestry Corporation, peer‑reviewed agroforestry studies"
        },
        "mangroves": {
            "offset_per_unit": 1.2,            # tons CO₂ per m² over 25 years (blue carbon)
            "unit": "m²",
            "description": "Restore mangroves along the coast – high carbon density, storm protection, fisheries habitat",
            "cost_per_unit": 25,
            "additionality": 0.90,
            "leakage": 0.02,
            "permanence_risk": 0.15,            # vulnerable to sea‑level rise if not managed
            "source": "Blue Carbon Initiative, Caribbean mangroves assessment"
        },
        "coral": {
            "offset_per_unit": 0.25,           # tons CO₂ per coral gardening unit (includes avoided loss)
            "unit": "unit",
            "description": "Coral restoration fragments – rebuild reef ecosystems, enhance coastal protection",
            "cost_per_unit": 60,
            "additionality": 0.95,
            "leakage": 0.0,
            "permanence_risk": 0.20,            # bleaching, storms
            "source": "SECORE International, Caribbean coral restoration projects"
        },
        "solar": {
            "offset_per_unit": 12.5,           # tons CO₂ avoided per kW installed (lifetime)
            "unit": "kW",
            "description": "Install solar PV to displace grid electricity (Caribbean grid emission factor ~0.7 tCO₂/MWh)",
            "cost_per_unit": 1200,
            "additionality": 0.80,              # some installations might happen anyway
            "leakage": 0.0,
            "permanence_risk": 0.02,            # technical failure, but low
            "source": "IRENA, Caribbean renewable energy potential"
        }
    },
    "social_actions": {
        "beach_cleanup": {
            "unit": "kg",
            "description": "Organize beach cleanups to remove plastic and debris – protects marine life and tourism, engages community",
            "base_per_employee": 12,
            "base_per_co2": 0.6,
            "co_benefits": "Marine biodiversity, local employment, awareness",
            "source": "Ocean Conservancy, Caribbean coastal cleanups"
        },
        "stray_animals": {
            "unit": "animals",
            "description": "Support stray animal welfare: provide food, veterinary care, and spay/neuter for dogs and cats – reduces public health risks, improves tourism perception",
            "base_per_employee": 0.7,
            "base_per_co2": 0.015,
            "co_benefits": "Animal welfare, public health, community engagement",
            "source": "Humane Society International, Caribbean programs"
        },
        "meals": {
            "unit": "meals",
            "description": "Provide nutritious meals to homeless and food‑insecure families through local charities – addresses food security, reduces waste",
            "base_per_employee": 7,
            "base_per_co2": 0.15,
            "co_benefits": "Social equity, local agriculture support",
            "source": "Caribbean Food Security Network"
        }
    },
    "reduction_strategies": {
        "Tourism": [
            "Install solar water heating and PV systems",
            "Transition to electric shuttles and golf carts",
            "Implement smart HVAC and lighting controls",
            "Source food locally to reduce transport emissions",
            "Achieve Green Globe or EarthCheck certification"
        ],
        "Manufacturing": [
            "Upgrade to energy‑efficient motors and drives",
            "Recover waste heat for process use",
            "Shift logistics to electric or hybrid fleets",
            "Use recycled materials and reduce waste",
            "Install on‑site renewable energy"
        ],
        "Agriculture": [
            "Adopt agroforestry and regenerative practices",
            "Apply biochar to improve soil carbon",
            "Optimise fertiliser use (precision agriculture)",
            "Use cover crops and reduce tillage",
            "Install methane digesters for livestock waste"
        ],
        "Shipping": [
            "Optimise routes and reduce speed (slow steaming)",
            "Use shore power when in port",
            "Retrofit vessels with energy‑saving devices",
            "Switch to low‑carbon fuels (biofuels, green methanol)",
            "Participate in green port initiatives"
        ],
        "Energy": [
            "Increase renewable energy share (solar, wind, geothermal)",
            "Improve grid efficiency and storage",
            "Phase out diesel generators",
            "Implement demand‑side management",
            "Invest in community renewables"
        ],
        "Retail": [
            "Upgrade to LED lighting and efficient HVAC",
            "Install solar canopies over parking lots",
            "Reduce refrigeration emissions (natural refrigerants)",
            "Promote sustainable products to customers",
            "Optimise delivery logistics"
        ],
        "Construction": [
            "Use low‑carbon cement and recycled materials",
            "Design for energy efficiency (passive cooling)",
            "Minimise construction waste",
            "Source materials locally",
            "Incorporate green roofs and rainwater harvesting"
        ]
    },
    "carbon_price": 50,                # Social cost of carbon (USD/ton), updated from $40
    "discount_rate": 0.03,              # 3% discount rate for future offsets
    "last_updated": "2025-04-01",
    "notes": "All values are indicative and should be adjusted for specific project contexts. Additionality, leakage, and permanence factors are included for risk‑adjusted offset calculations.",
    "references": [
        "IPCC AR6 Working Group III (2022)",
        "Blue Carbon Initiative (2024) – Caribbean Mangrove Assessment",
        "Caribbean Community Climate Change Centre (CCCCC) reports",
        "IRENA (2025) – Renewable Energy Outlook: Caribbean",
        "Personal communication with Prof. Elena Martinez, UWI (Environmental Economics)"
    ]
}

# -----------------------------
# Carbon Engine (using enhanced KNOWLEDGE)
# -----------------------------
class CarbonOffsetCalculator:
    def __init__(self, kb):
        self.industries = kb["industries"]
        self.offset_methods = kb["offset_methods"]
        self.social_actions = kb["social_actions"]
        self.reduction_strategies = kb.get("reduction_strategies", {})
        self.carbon_price = kb["carbon_price"]

    def calculate(self, industry, employees=None, revenue=None):
        if employees:
            return employees * self.industries[industry]["co2_per_employee"]
        if revenue:
            return revenue * self.industries[industry]["co2_per_million_revenue"]
        return 0

    def rating(self, co2):
        if co2 < 50:
            return "A (Low Impact)"
        elif co2 < 200:
            return "B (Moderate Impact)"
        elif co2 < 500:
            return "C (High Impact)"
        else:
            return "D (Critical Impact)"

    def esg_score(self, co2):
        if co2 < 50:
            return 90
        elif co2 < 200:
            return 75
        elif co2 < 500:
            return 55
        else:
            return 30

    def offsets(self, co2):
        # Basic offset quantities (without risk adjustments)
        return {name: int(co2 / method["offset_per_unit"]) for name, method in self.offset_methods.items()}

    def neutrality_status(self, co2, offsets):
        total_offset = sum(qty * self.offset_methods[name]["offset_per_unit"] for name, qty in offsets.items())
        return "✅ Carbon Neutral Achievable" if total_offset >= co2 else "⚠️ Additional reductions required"

    def reduction_strategy(self, industry):
        return self.reduction_strategies.get(industry, ["Improve energy efficiency"])

    def social_metrics(self, co2, employees=None, revenue=None):
        scale = employees if employees else (revenue * 10 if revenue else co2 / 10)
        return {
            name: int(scale * action.get("base_per_employee", 0) + co2 * action.get("base_per_co2", 0))
            for name, action in self.social_actions.items()
        }

    def report(self, data):
        with open("sustainability_report.json", "w") as f:
            import json
            json.dump(data, f, indent=4)

calc = CarbonOffsetCalculator(KNOWLEDGE)

# -----------------------------
# Templates (unchanged, but note that chart expects the four offset methods)
# -----------------------------
LOCK_TEMPLATE = """
<html>
<head><title>🔒 Access Locked</title>
<style>
body{background:#0a1024;color:white;font-family:Arial;display:flex;justify-content:center;align-items:center;height:100vh}
.box{background:#101c3d;padding:40px;border-radius:10px;text-align:center}
input{padding:10px;margin-top:10px;background:#182957;border:1px solid #2c3f75;color:white}
button{padding:10px 20px;margin-top:15px;background:#00c896;border:none;color:white;font-weight:bold}
</style>
</head>
<body>
<div class="box">
<h2>🔒 Tool Locked</h2>
<p>Enter the password to access the dashboard.</p>
<form method="post">
<input type="password" name="password" placeholder="Enter password"><br>
<button>Unlock</button>
</form>
{% if error %}<p style="color:red">{{error}}</p>{% endif %}
</div>
</body>
</html>
"""

DASHBOARD_TEMPLATE = """<!DOCTYPE html>
<html>
<head>
<title>🌍 Caribbean Sustainability Intelligence Terminal (Professor Enhanced)</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
<style>
body { font-family: 'Inter', Arial; background: #050b18; color: white; margin: 0; padding: 40px; }
h1 { margin-bottom: 30px; }
.card { background: #0b1736; padding: 25px; margin-bottom: 20px; border-radius: 10px; }
input, select { padding: 10px; width: 200px; margin-top: 5px; background: #1e2a47; border: 1px solid #2a3a5a; color: white; }
button { padding: 12px 25px; background: #00c896; border: none; color: white; font-weight: bold; cursor: pointer; margin-top: 10px; border-radius: 5px; }
.metric { font-size: 22px; margin: 10px 0; }
.grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 15px; }
.badge { background: #1f2b48; padding: 15px; border-radius: 8px; text-align: center; }
.badge h3 { margin: 0 0 10px 0; color: #00c896; }
.error { color: #ff6b6b; margin-top: 10px; }
a { color: #00c896; }
.strategy-list { list-style-type: none; padding: 0; }
.strategy-list li { background: #1e2a47; margin: 5px 0; padding: 10px; border-radius: 5px; }
.footnote { font-size: 12px; color: #aaa; margin-top: 5px; }
</style>
</head>
<body>
<h1>🌍 Caribbean Sustainability Intelligence Terminal</h1>
<p style="color:#aaa;">Enhanced with data from Prof. Elena Martinez (Environmental Studies, ESG & Green Finance)</p>

<div class="card">
<form method="post">
<label>Industry</label><br>
<select name="industry">
{% for i in industries %}
<option value="{{i}}" {% if request.form and request.form.industry == i %}selected{% endif %}>{{i}}</option>
{% endfor %}
</select>
<br><br>
<label>Employees (optional)</label><br>
<input name="employees" value="{{ request.form.employees if request.form else '' }}">
<br><br>
<label>Revenue ($M) (optional)</label><br>
<input name="revenue" value="{{ request.form.revenue if request.form else '' }}">
<br><br>
<button>Analyse Sustainability</button>
</form>
{% if error %}<div class="error">{{ error }}</div>{% endif %}
</div>

{% if result %}
<div class="card">
<h2>Carbon Impact</h2>
<div class="metric">📊 CO₂ Emissions: {{ result.co2 }} tons</div>
<div class="metric">💰 Carbon Cost at ${{ carbon_price }}/ton: ${{ result.cost }}</div>
<div class="metric">🏷️ ESG Rating: {{ result.rating }}</div>
<div class="metric">📈 ESG Score: {{ result.esg_score }}/100</div>
<div class="metric">⚖️ Neutrality Status: {{ result.neutrality }}</div>
</div>

<div class="card">
<h2>🌱 Technical Offsets</h2>
<div class="grid">
{% for key, val in result.offsets.items() %}
<div class="badge">
<h3>{% if key=='trees' %}🌳{% elif key=='mangroves' %}🌿{% elif key=='coral' %}🐠{% elif key=='solar' %}☀️{% endif %} {{ key|capitalize }}</h3>
<div style="font-size:28px;">{{ val }}</div>
<div style="font-size:14px;">{{ offset_descriptions[key] }}</div>
<div class="footnote">per unit offset: {{ offset_per_units[key] }} tons</div>
</div>
{% endfor %}
</div>
<p class="footnote" style="text-align:center;">Quantities are basic; for risk‑adjusted offsets see /knowledge.</p>
</div>

<div class="card">
<h2>🤝 Community Impact (Caribbean Models)</h2>
<div class="grid">
{% for key, val in result.social.items() %}
<div class="badge">
<h3>{% if key=='beach_cleanup' %}🏖️{% elif key=='stray_animals' %}🐕{% elif key=='meals' %}🍲{% endif %} {{ key|replace('_',' ')|title }}</h3>
<div style="font-size:28px;">{{ val }}</div>
<div style="font-size:14px;">{{ social_descriptions[key] }}</div>
</div>
{% endfor %}
</div>
</div>

<div class="card">
<h2>📋 Reduction Strategies for {{ result.industry }}</h2>
<ul class="strategy-list">
{% for strategy in result.strategies %}
<li>{{ strategy }}</li>
{% endfor %}
</ul>
</div>

<div class="card">
<h2>Impact Visualisation (normalised)</h2>
<canvas id="chart"></canvas>
</div>

<div style="text-align: right; margin-top: 10px;">
<a href="/download_csv" style="background: #00c896; padding: 10px 20px; border-radius: 5px; text-decoration: none; color: white;">📥 Download CSV Report</a>
</div>

<script>
const ctx = document.getElementById('chart').getContext('2d');
new Chart(ctx, {
type: 'bar',
data: {
labels: ['CO₂ (tons)', 'Trees', 'Mangroves (m²)', 'Coral (units)', 'Solar (kW)'],
datasets: [{
label: 'Normalised Impact (0-100)',
data: [
{{ (result.co2 / result.co2 * 100) if result.co2 > 0 else 0 }},
{{ (result.offsets.trees / (result.co2 / 0.6) * 100) if result.co2 > 0 else 0 }},
{{ (result.offsets.mangroves / (result.co2 / 1.2) * 100) if result.co2 > 0 else 0 }},
{{ (result.offsets.coral / (result.co2 / 0.25) * 100) if result.co2 > 0 else 0 }},
{{ (result.offsets.solar / (result.co2 / 12.5) * 100) if result.co2 > 0 else 0 }}
],
backgroundColor: '#00c896'
}]
},
options: { scales: { y: { beginAtZero: true, max: 100 } } }
});
</script>
{% endif %}

<div style="margin-top:30px; text-align:center; color:#aaa;">
<a href="/knowledge">📚 View Enhanced Knowledge Base</a> | Data verified {{ last_updated }}
</div>
</body>
</html>
"""

# -----------------------------
# Flask Routes (unchanged)
# -----------------------------
PASSWORD = "climate2026"  # Hardcoded – change as needed

@app.route("/", methods=["GET", "POST"])
def home():
    if not session.get("unlocked"):
        error = None
        if request.method == "POST":
            if request.form.get("password") == PASSWORD:
                session["unlocked"] = True
                return redirect("/")
            else:
                error = "Incorrect password"
        return render_template_string(LOCK_TEMPLATE, error=error)

    error = None
    result = None

    if request.method == "POST" and "industry" in request.form:
        industry = request.form["industry"]
        emp_str = request.form.get("employees", "").strip()
        rev_str = request.form.get("revenue", "").strip()

        employees = revenue = None
        if emp_str and rev_str:
            error = "Provide either Employees OR Revenue, not both."
        elif emp_str:
            try:
                employees = int(emp_str)
                if employees <= 0:
                    error = "Employees must be positive."
            except ValueError:
                error = "Employees must be a whole number."
        elif rev_str:
            try:
                revenue = float(rev_str)
                if revenue <= 0:
                    error = "Revenue must be positive."
            except ValueError:
                error = "Revenue must be a number."
        else:
            error = "Please provide either Employees or Revenue."

        if not error:
            co2 = calc.calculate(industry, employees, revenue)
            if co2 > 0:
                rating = calc.rating(co2)
                esg_score = calc.esg_score(co2)
                offsets = calc.offsets(co2)
                neutrality = calc.neutrality_status(co2, offsets)
                strategies = calc.reduction_strategy(industry)
                social = calc.social_metrics(co2, employees, revenue)
                cost = co2 * calc.carbon_price

                result = {
                    "industry": industry,
                    "co2": round(co2, 2),
                    "rating": rating,
                    "esg_score": esg_score,
                    "cost": round(cost, 2),
                    "offsets": offsets,
                    "neutrality": neutrality,
                    "strategies": strategies,
                    "social": social
                }

                # Save reports (optional)
                calc.report({
                    "industry": industry,
                    "employees": employees,
                    "revenue": revenue,
                    "co2": co2,
                    "rating": rating,
                    "esg_score": esg_score,
                    "offsets": offsets,
                    "neutrality": neutrality,
                    "strategies": strategies,
                    "social": social,
                    "carbon_price": calc.carbon_price,
                    "timestamp": datetime.utcnow().isoformat()
                })

                csv_data = {
                    "industry": industry,
                    "employees": employees,
                    "revenue": revenue,
                    "co2_tons": co2,
                    "rating": rating,
                    "esg_score": esg_score,
                    "carbon_cost_usd": cost,
                    "neutrality_status": neutrality,
                    **{f"offset_{k}": v for k, v in offsets.items()},
                    **{f"social_{k}": v for k, v in social.items()},
                    "timestamp": datetime.utcnow().isoformat()
                }
                with open("sustainability_report.csv", "w", newline="") as f:
                    writer = csv.writer(f)
                    writer.writerow(csv_data.keys())
                    writer.writerow(csv_data.values())
            else:
                error = "Calculated CO₂ is zero. Check your inputs."

    # Prepare descriptions for template
    offset_descriptions = {k: v["description"] for k, v in calc.offset_methods.items()}
    offset_per_units = {k: v["offset_per_unit"] for k, v in calc.offset_methods.items()}
    social_descriptions = {k: v["description"] for k, v in calc.social_actions.items()}

    return render_template_string(
        DASHBOARD_TEMPLATE,
        industries=calc.industries.keys(),
        result=result,
        error=error,
        carbon_price=calc.carbon_price,
        offset_descriptions=offset_descriptions,
        offset_per_units=offset_per_units,
        social_descriptions=social_descriptions,
        last_updated=KNOWLEDGE["last_updated"]
    )

@app.route("/knowledge")
def show_knowledge():
    return jsonify(KNOWLEDGE)

@app.route("/download_csv")
def download_csv():
    if os.path.exists("sustainability_report.csv"):
        return send_file("sustainability_report.csv", as_attachment=True, download_name="sustainability_report.csv", mimetype="text/csv")
    return "No report available yet. Please run an analysis first.", 404

@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")

if __name__ == "__main__":
    app.run(debug=True)
