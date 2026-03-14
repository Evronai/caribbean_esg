import os
import json
import csv
import io
from datetime import datetime
from flask import (
    Flask, request, render_template_string, jsonify,
    send_file, session, redirect, url_for, flash
)
from flask_sqlalchemy import SQLAlchemy
from weasyprint import HTML
import tempfile
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'dev-secret-key')
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///sustainability.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

PASSWORD = os.getenv('APP_PASSWORD', 'climate2026')  # fallback

# -----------------------------
# Database Model
# -----------------------------
class Analysis(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    industry = db.Column(db.String(50))
    employees = db.Column(db.Integer, nullable=True)
    revenue = db.Column(db.Float, nullable=True)
    co2 = db.Column(db.Float)
    rating = db.Column(db.String(20))
    esg_score = db.Column(db.Integer)
    carbon_cost = db.Column(db.Float)
    offsets = db.Column(db.JSON)      # store as JSON
    social = db.Column(db.JSON)
    strategies = db.Column(db.JSON)

# -----------------------------
# Enhanced Knowledge Base
# -----------------------------
KNOWLEDGE = {
    "industries": {
        "Tourism": { "co2_per_employee": 4.2, "co2_per_million_revenue": 42.0, "source": "CHENACT+IPCC" },
        "Agriculture": { "co2_per_employee": 12.5, "co2_per_million_revenue": 125.0, "source": "FAO" },
        "Manufacturing": { "co2_per_employee": 18.3, "co2_per_million_revenue": 183.0, "source": "EIA adjusted" },
        "Shipping": { "co2_per_employee": 22.7, "co2_per_million_revenue": 227.0, "source": "IMO" },
        "Energy": { "co2_per_employee": 30.1, "co2_per_million_revenue": 301.0, "source": "IRENA" },
        "Retail": { "co2_per_employee": 2.8, "co2_per_million_revenue": 28.0, "source": "CDP" },
        "Construction": { "co2_per_employee": 9.5, "co2_per_million_revenue": 95.0, "source": "UNEP" },
        "Mining": { "co2_per_employee": 35.0, "co2_per_million_revenue": 350.0, "source": "ICMM" },
        "Healthcare": { "co2_per_employee": 3.5, "co2_per_million_revenue": 35.0, "source": "Healthcare Climate Council" },
        "Education": { "co2_per_employee": 2.0, "co2_per_million_revenue": 20.0, "source": "Second Nature" },
        "Transportation": { "co2_per_employee": 25.0, "co2_per_million_revenue": 250.0, "source": "EPA" },
        "Technology": { "co2_per_employee": 1.8, "co2_per_million_revenue": 18.0, "source": "IEA" }
    },
    "offset_methods": {
        "trees": {
            "offset_per_unit": 0.6, "unit": "tree", "description": "Native tree planting",
            "cost_per_unit": 12, "additionality": 0.85, "leakage": 0.05, "permanence_risk": 0.10,
            "lifetime_years": 25, "maintenance_yearly": 0.5
        },
        "mangroves": {
            "offset_per_unit": 1.2, "unit": "m²", "description": "Mangrove restoration",
            "cost_per_unit": 25, "additionality": 0.90, "leakage": 0.02, "permanence_risk": 0.15,
            "lifetime_years": 25, "maintenance_yearly": 1.0
        },
        "coral": {
            "offset_per_unit": 0.25, "unit": "unit", "description": "Coral gardening",
            "cost_per_unit": 60, "additionality": 0.95, "leakage": 0.0, "permanence_risk": 0.20,
            "lifetime_years": 10, "maintenance_yearly": 5.0
        },
        "solar": {
            "offset_per_unit": 12.5, "unit": "kW", "description": "Solar PV installation",
            "cost_per_unit": 1200, "additionality": 0.80, "leakage": 0.0, "permanence_risk": 0.02,
            "lifetime_years": 25, "maintenance_yearly": 10.0
        }
    },
    "social_actions": {
        "beach_cleanup": { "unit": "kg", "description": "Beach cleanups", "base_per_employee": 12, "base_per_co2": 0.6 },
        "stray_animals": { "unit": "animals", "description": "Stray animal care", "base_per_employee": 0.7, "base_per_co2": 0.015 },
        "meals": { "unit": "meals", "description": "Community meals", "base_per_employee": 7, "base_per_co2": 0.15 }
    },
    "reduction_strategies": {
        "Tourism": ["Solar water heating", "Electric shuttles", "Smart HVAC", "Local sourcing", "Green certification"],
        "Manufacturing": ["Efficient motors", "Waste heat recovery", "Electric logistics", "Recycled materials", "On-site solar"],
        "Agriculture": ["Regenerative farming", "Biochar", "Precision fertiliser", "Cover crops", "Methane digesters"],
        "Shipping": ["Slow steaming", "Shore power", "Energy-saving devices", "Low-carbon fuels", "Green ports"],
        "Energy": ["Renewable share", "Grid efficiency", "Phase out diesel", "Demand management", "Community solar"],
        "Retail": ["LED lighting", "Solar canopies", "Natural refrigerants", "Sustainable products", "Delivery optimisation"],
        "Construction": ["Low-carbon cement", "Passive design", "Waste minimisation", "Local materials", "Green roofs"],
        "Mining": ["Renewable energy", "Electric vehicles", "Methane capture", "Land rehabilitation", "Water efficiency"],
        "Healthcare": ["Energy efficiency", "Telemedicine", "Sustainable procurement", "Waste reduction", "Green building"],
        "Education": ["Campus efficiency", "Remote learning", "Sustainable commuting", "Curriculum integration", "Green labs"],
        "Transportation": ["Fleet electrification", "Route optimisation", "Eco-driving", "Alternative fuels", "Modal shift"],
        "Technology": ["Cloud optimisation", "Device efficiency", "E-waste recycling", "Remote work", "Renewable procurement"]
    },
    "carbon_price": 50,
    "discount_rate": 0.03,
    "last_updated": "2025-04-01"
}

# -----------------------------
# Carbon Engine (Enhanced)
# -----------------------------
class CarbonOffsetCalculator:
    def __init__(self, kb):
        self.kb = kb

    def calculate_co2(self, industry, employees, revenue):
        if employees:
            return employees * self.kb['industries'][industry]['co2_per_employee']
        if revenue:
            return revenue * self.kb['industries'][industry]['co2_per_million_revenue']
        return 0

    def get_rating(self, co2):
        if co2 < 50: return "A (Low Impact)"
        if co2 < 200: return "B (Moderate Impact)"
        if co2 < 500: return "C (High Impact)"
        return "D (Critical Impact)"

    def get_esg_score(self, co2):
        if co2 < 50: return 90
        if co2 < 200: return 75
        if co2 < 500: return 55
        return 30

    def benchmark(self, industry, co2_per_employee):
        """Compare company's per-employee emissions to industry average."""
        industry_avg = self.kb['industries'][industry]['co2_per_employee']
        if co2_per_employee < industry_avg * 0.8:
            return "Top 20% (better than average)"
        elif co2_per_employee < industry_avg:
            return "Above average"
        elif co2_per_employee < industry_avg * 1.2:
            return "Near average"
        else:
            return "Below average (needs improvement)"

    def offsets(self, co2):
        # Basic (raw) quantities
        return {name: int(co2 / m['offset_per_unit']) for name, m in self.kb['offset_methods'].items()}

    def risk_adjusted_offsets(self, co2):
        """Calculate offset quantities after applying additionality, leakage, permanence."""
        adjusted = {}
        for name, method in self.kb['offset_methods'].items():
            # Effective offset per unit = offset_per_unit * additionality * (1 - leakage) * (1 - permanence_risk)
            effective = method['offset_per_unit'] * method['additionality'] * (1 - method['leakage']) * (1 - method['permanence_risk'])
            adjusted[name] = int(co2 / effective)
        return adjusted

    def financial_analysis(self, method_name, quantity):
        """Compute NPV, IRR, payback for a given offset method and quantity."""
        method = self.kb['offset_methods'][method_name]
        cost_per_unit = method['cost_per_unit']
        maintenance = method.get('maintenance_yearly', 0)
        lifetime = method['lifetime_years']
        discount_rate = self.kb['discount_rate']
        # Simple model: assume offsets accrue linearly over lifetime
        annual_offset = method['offset_per_unit'] * quantity / lifetime
        annual_revenue = annual_offset * self.kb['carbon_price']
        initial_cost = cost_per_unit * quantity
        # NPV calculation (simplified)
        npv = -initial_cost
        for t in range(1, lifetime+1):
            npv += (annual_revenue - maintenance) / ((1 + discount_rate) ** t)
        # IRR (rough approximation)
        irr = discount_rate  # placeholder
        payback = initial_cost / (annual_revenue - maintenance) if (annual_revenue - maintenance) > 0 else 999
        return {
            'npv': round(npv, 2),
            'irr': round(irr, 2),
            'payback_years': round(payback, 1)
        }

    def neutrality_status(self, co2, offsets):
        total = sum(qty * self.kb['offset_methods'][name]['offset_per_unit'] for name, qty in offsets.items())
        return "✅ Neutral Achievable" if total >= co2 else "⚠️ Reductions needed"

    def reduction_strategy(self, industry):
        return self.kb['reduction_strategies'].get(industry, ["Improve efficiency"])

    def social_metrics(self, co2, employees, revenue):
        scale = employees if employees else (revenue * 10 if revenue else co2 / 10)
        return {name: int(scale * act.get('base_per_employee',0) + co2 * act.get('base_per_co2',0))
                for name, act in self.kb['social_actions'].items()}

calc = CarbonOffsetCalculator(KNOWLEDGE)

# -----------------------------
# Templates (using Bootstrap 5)
# -----------------------------
LOCK_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>🔒 Access Locked</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <style>
        body { background: #0a1024; color: white; display: flex; align-items: center; justify-content: center; height: 100vh; }
        .lock-box { background: #101c3d; padding: 2rem; border-radius: 1rem; max-width: 400px; width: 100%; }
        .lock-box input, .lock-box button { width: 100%; }
    </style>
</head>
<body>
    <div class="lock-box">
        <h2 class="text-center mb-4">🔒 Tool Locked</h2>
        <p class="text-center">Enter the password to access the dashboard.</p>
        <form method="post">
            <input type="password" name="password" class="form-control mb-3" placeholder="Password" required>
            <button type="submit" class="btn btn-success">Unlock</button>
            {% if error %}<div class="alert alert-danger mt-3">{{ error }}</div>{% endif %}
        </form>
    </div>
</body>
</html>
"""

DASHBOARD_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>🌍 Big 4 Sustainability Terminal</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        body { background: #f8f9fa; font-family: 'Inter', sans-serif; }
        .navbar { background: #0b1736; color: white; }
        .card { border-radius: 1rem; box-shadow: 0 0.5rem 1rem rgba(0,0,0,0.1); margin-bottom: 1.5rem; }
        .metric { font-size: 1.8rem; font-weight: 600; }
        .badge-custom { background: #e9f0ff; padding: 0.5rem 1rem; border-radius: 2rem; }
        .footer { color: #6c757d; text-align: center; margin: 2rem 0; }
    </style>
</head>
<body>
    <nav class="navbar navbar-dark px-4">
        <span class="navbar-brand mb-0 h1">🌍 Big 4 Sustainability Intelligence Terminal</span>
        <div>
            <a href="/history" class="btn btn-outline-light btn-sm me-2">📜 History</a>
            <a href="/logout" class="btn btn-outline-light btn-sm">Logout</a>
        </div>
    </nav>

    <div class="container mt-4">
        <!-- Input Card -->
        <div class="card p-4">
            <form method="post">
                <div class="row">
                    <div class="col-md-4 mb-3">
                        <label class="form-label">Industry</label>
                        <select name="industry" class="form-select">
                            {% for i in industries %}
                            <option value="{{i}}" {% if request.form and request.form.industry==i %}selected{% endif %}>{{i}}</option>
                            {% endfor %}
                        </select>
                    </div>
                    <div class="col-md-4 mb-3">
                        <label class="form-label">Employees (optional)</label>
                        <input type="number" name="employees" class="form-control" value="{{ request.form.employees if request.form else '' }}">
                    </div>
                    <div class="col-md-4 mb-3">
                        <label class="form-label">Revenue $M (optional)</label>
                        <input type="number" step="0.1" name="revenue" class="form-control" value="{{ request.form.revenue if request.form else '' }}">
                    </div>
                </div>
                <button type="submit" class="btn btn-primary">Analyse Sustainability</button>
                {% if error %}<div class="alert alert-danger mt-3">{{ error }}</div>{% endif %}
            </form>
        </div>

        {% if result %}
        <!-- Results -->
        <div class="card p-4">
            <h3>Carbon Impact</h3>
            <div class="row">
                <div class="col-md-3 mb-2"><span class="badge-custom">📊 CO₂: {{ result.co2 }} tons</span></div>
                <div class="col-md-3 mb-2"><span class="badge-custom">💰 Cost: ${{ result.cost }}</span></div>
                <div class="col-md-3 mb-2"><span class="badge-custom">🏷️ Rating: {{ result.rating }}</span></div>
                <div class="col-md-3 mb-2"><span class="badge-custom">📈 ESG: {{ result.esg_score }}/100</span></div>
                <div class="col-md-3 mb-2"><span class="badge-custom">⚖️ Neutrality: {{ result.neutrality }}</span></div>
                <div class="col-md-3 mb-2"><span class="badge-custom">📊 Benchmark: {{ result.benchmark }}</span></div>
            </div>
        </div>

        <!-- Tabs for Basic / Risk-Adjusted Offsets -->
        <div class="card p-4">
            <ul class="nav nav-tabs" id="offsetTabs" role="tablist">
                <li class="nav-item" role="presentation">
                    <button class="nav-link active" id="basic-tab" data-bs-toggle="tab" data-bs-target="#basic" type="button" role="tab">Basic Offsets</button>
                </li>
                <li class="nav-item" role="presentation">
                    <button class="nav-link" id="risk-tab" data-bs-toggle="tab" data-bs-target="#risk" type="button" role="tab">Risk‑Adjusted</button>
                </li>
                <li class="nav-item" role="presentation">
                    <button class="nav-link" id="finance-tab" data-bs-toggle="tab" data-bs-target="#finance" type="button" role="tab">Financial Analysis</button>
                </li>
            </ul>
            <div class="tab-content mt-3">
                <div class="tab-pane active" id="basic" role="tabpanel">
                    <div class="row">
                        {% for key, val in result.offsets.items() %}
                        <div class="col-md-3 mb-3">
                            <div class="card h-100">
                                <div class="card-body text-center">
                                    <h5 class="card-title">
                                        {% if key=='trees' %}🌳{% elif key=='mangroves' %}🌿{% elif key=='coral' %}🐠{% else %}☀️{% endif %}
                                        {{ key|capitalize }}
                                    </h5>
                                    <p class="display-6">{{ val }}</p>
                                    <p class="text-muted">{{ offset_descriptions[key] }}</p>
                                </div>
                            </div>
                        </div>
                        {% endfor %}
                    </div>
                </div>
                <div class="tab-pane" id="risk" role="tabpanel">
                    <div class="row">
                        {% for key, val in result.risk_adjusted.items() %}
                        <div class="col-md-3 mb-3">
                            <div class="card h-100">
                                <div class="card-body text-center">
                                    <h5 class="card-title">{{ key|capitalize }}</h5>
                                    <p class="display-6">{{ val }}</p>
                                    <p class="text-muted">Adjusted for risk</p>
                                </div>
                            </div>
                        </div>
                        {% endfor %}
                    </div>
                </div>
                <div class="tab-pane" id="finance" role="tabpanel">
                    <div class="table-responsive">
                        <table class="table table-bordered">
                            <thead>
                                <tr><th>Method</th><th>Quantity</th><th>NPV ($)</th><th>IRR (%)</th><th>Payback (years)</th></tr>
                            </thead>
                            <tbody>
                                {% for key, fin in result.financials.items() %}
                                <tr>
                                    <td>{{ key|capitalize }}</td>
                                    <td>{{ result.offsets[key] }}</td>
                                    <td>{{ fin.npv }}</td>
                                    <td>{{ fin.irr }}</td>
                                    <td>{{ fin.payback_years }}</td>
                                </tr>
                                {% endfor %}
                            </tbody>
                        </table>
                    </div>
                </div>
            </div>
        </div>

        <!-- Community Impact -->
        <div class="card p-4">
            <h3>🤝 Community Impact (Caribbean Models)</h3>
            <div class="row">
                {% for key, val in result.social.items() %}
                <div class="col-md-4 mb-3">
                    <div class="card">
                        <div class="card-body text-center">
                            <h5>{% if key=='beach_cleanup' %}🏖️{% elif key=='stray_animals' %}🐕{% else %}🍲{% endif %}
                                {{ key|replace('_',' ')|title }}</h5>
                            <p class="display-6">{{ val }}</p>
                            <p class="text-muted">{{ social_descriptions[key] }}</p>
                        </div>
                    </div>
                </div>
                {% endfor %}
            </div>
        </div>

        <!-- Reduction Strategies -->
        <div class="card p-4">
            <h3>📋 Reduction Strategies for {{ result.industry }}</h3>
            <ul class="list-group">
                {% for strat in result.strategies %}
                <li class="list-group-item">{{ strat }}</li>
                {% endfor %}
            </ul>
        </div>

        <!-- Chart -->
        <div class="card p-4">
            <h3>Impact Visualisation</h3>
            <canvas id="chart" style="max-height:400px;"></canvas>
        </div>

        <!-- Action Buttons -->
        <div class="d-flex justify-content-end gap-2 mb-4">
            <a href="/download_csv" class="btn btn-success">📥 CSV Report</a>
            <a href="/download_pdf" class="btn btn-danger">📄 PDF Report</a>
        </div>

        <script>
            const ctx = document.getElementById('chart').getContext('2d');
            new Chart(ctx, {
                type: 'bar',
                data: {
                    labels: ['CO₂', 'Trees', 'Mangroves', 'Coral', 'Solar'],
                    datasets: [{
                        label: 'Normalised (0-100)',
                        data: [
                            100,
                            {{ (result.offsets.trees / (result.co2 / 0.6) * 100) | round }},
                            {{ (result.offsets.mangroves / (result.co2 / 1.2) * 100) | round }},
                            {{ (result.offsets.coral / (result.co2 / 0.25) * 100) | round }},
                            {{ (result.offsets.solar / (result.co2 / 12.5) * 100) | round }}
                        ],
                        backgroundColor: '#0d6efd'
                    }]
                }
            });
        </script>
        {% endif %}

        <div class="footer">
            <a href="/knowledge" class="text-decoration-none">📚 Knowledge Base</a> | Data verified {{ last_updated }}
        </div>
    </div>

    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
</body>
</html>
"""

# -----------------------------
# Flask Routes
# -----------------------------
@app.before_first_request
def create_tables():
    db.create_all()

@app.route("/", methods=["GET", "POST"])
def home():
    if not session.get('unlocked'):
        error = None
        if request.method == 'POST':
            if request.form.get('password') == PASSWORD:
                session['unlocked'] = True
                return redirect('/')
            else:
                error = 'Incorrect password'
        return render_template_string(LOCK_TEMPLATE, error=error)

    error = None
    result = None

    if request.method == 'POST' and 'industry' in request.form:
        industry = request.form['industry']
        emp_str = request.form.get('employees', '').strip()
        rev_str = request.form.get('revenue', '').strip()

        employees = revenue = None
        if emp_str and rev_str:
            error = 'Provide either Employees OR Revenue, not both.'
        elif emp_str:
            try:
                employees = int(emp_str)
                if employees <= 0: error = 'Employees must be positive.'
            except ValueError:
                error = 'Employees must be a whole number.'
        elif rev_str:
            try:
                revenue = float(rev_str)
                if revenue <= 0: error = 'Revenue must be positive.'
            except ValueError:
                error = 'Revenue must be a number.'
        else:
            error = 'Please provide either Employees or Revenue.'

        if not error:
            co2 = calc.calculate_co2(industry, employees, revenue)
            if co2 > 0:
                rating = calc.get_rating(co2)
                esg_score = calc.get_esg_score(co2)
                # Benchmark (using per-employee if available)
                per_employee = co2 / employees if employees else None
                benchmark = calc.benchmark(industry, per_employee) if per_employee else 'N/A'
                offsets = calc.offsets(co2)
                risk_adjusted = calc.risk_adjusted_offsets(co2)
                # Financials for each method (using basic quantities)
                financials = {}
                for name, qty in offsets.items():
                    financials[name] = calc.financial_analysis(name, qty)
                neutrality = calc.neutrality_status(co2, offsets)
                strategies = calc.reduction_strategy(industry)
                social = calc.social_metrics(co2, employees, revenue)
                cost = co2 * KNOWLEDGE['carbon_price']

                result = {
                    'industry': industry,
                    'co2': round(co2, 2),
                    'rating': rating,
                    'esg_score': esg_score,
                    'benchmark': benchmark,
                    'cost': round(cost, 2),
                    'offsets': offsets,
                    'risk_adjusted': risk_adjusted,
                    'financials': financials,
                    'neutrality': neutrality,
                    'strategies': strategies,
                    'social': social
                }

                # Save to database
                analysis = Analysis(
                    industry=industry,
                    employees=employees,
                    revenue=revenue,
                    co2=co2,
                    rating=rating,
                    esg_score=esg_score,
                    carbon_cost=cost,
                    offsets=offsets,
                    social=social,
                    strategies=strategies
                )
                db.session.add(analysis)
                db.session.commit()

                # Save CSV for download
                csv_data = {
                    'industry': industry,
                    'employees': employees,
                    'revenue': revenue,
                    'co2_tons': co2,
                    'rating': rating,
                    'esg_score': esg_score,
                    'carbon_cost_usd': cost,
                    'neutrality_status': neutrality,
                    **{f'offset_{k}': v for k, v in offsets.items()},
                    **{f'social_{k}': v for k, v in social.items()},
                    'timestamp': datetime.utcnow().isoformat()
                }
                with open('sustainability_report.csv', 'w', newline='') as f:
                    writer = csv.writer(f)
                    writer.writerow(csv_data.keys())
                    writer.writerow(csv_data.values())
            else:
                error = 'CO₂ zero – check inputs.'

    return render_template_string(
        DASHBOARD_TEMPLATE,
        industries=KNOWLEDGE['industries'].keys(),
        result=result,
        error=error,
        carbon_price=KNOWLEDGE['carbon_price'],
        offset_descriptions={k: v['description'] for k, v in KNOWLEDGE['offset_methods'].items()},
        social_descriptions={k: v['description'] for k, v in KNOWLEDGE['social_actions'].items()},
        last_updated=KNOWLEDGE['last_updated']
    )

@app.route('/history')
def history():
    analyses = Analysis.query.order_by(Analysis.timestamp.desc()).limit(20).all()
    return render_template_string('''
    {% extends "base.html" %}
    {% block content %}
    <h2>Analysis History</h2>
    <table class="table table-striped">
        <thead><tr><th>Time</th><th>Industry</th><th>CO₂</th><th>Rating</th><th>ESG</th></tr></thead>
        <tbody>
        {% for a in analyses %}
        <tr>
            <td>{{ a.timestamp }}</td><td>{{ a.industry }}</td><td>{{ a.co2 }}</td><td>{{ a.rating }}</td><td>{{ a.esg_score }}</td>
        </tr>
        {% endfor %}
        </tbody>
    </table>
    {% endblock %}
    ''', analyses=analyses)

@app.route('/knowledge')
def show_knowledge():
    return jsonify(KNOWLEDGE)

@app.route('/download_csv')
def download_csv():
    if os.path.exists('sustainability_report.csv'):
        return send_file('sustainability_report.csv', as_attachment=True, download_name='sustainability_report.csv', mimetype='text/csv')
    return 'No report yet.', 404

@app.route('/download_pdf')
def download_pdf():
    # Very basic PDF generation – requires weasyprint
    html_content = '<h1>Sustainability Report</h1><p>Placeholder – would include all result data.</p>'
    pdf = HTML(string=html_content).write_pdf()
    return send_file(io.BytesIO(pdf), download_name='report.pdf', as_attachment=True, mimetype='application/pdf')

@app.route('/logout')
def logout():
    session.clear()
    return redirect('/')

if __name__ == '__main__':
    app.run(debug=True)
