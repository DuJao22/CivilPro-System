"""
CiviPro - SaaS Engenharia Civil (Versão Profissional)
Sistema SaaS CiviPro | Desenvolvido por João Layon - Desenvolvedor Full Stack
Sistema completo para gestão de obras e orçamentos
"""

import os
import sqlite3
from datetime import datetime, timedelta
from io import BytesIO
from flask import (
    Flask, render_template, request, redirect, url_for, flash, session,
    send_file, jsonify
)
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps

from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib.units import cm
import mercadopago

app = Flask(__name__)
app.secret_key = os.environ.get("SESSION_SECRET", "troque_essa_chave_producao")
DB = "database.db"

def get_db_conn():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_conn()
    c = conn.cursor()

    c.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        email TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        created_at TEXT,
        trial_start_date TEXT,
        trial_end_date TEXT,
        subscription_status TEXT DEFAULT 'trial',
        subscription_id TEXT,
        plan_id TEXT
    )
    """)

    c.execute("""
    CREATE TABLE IF NOT EXISTS clients (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        name TEXT NOT NULL,
        email TEXT,
        phone TEXT,
        cpf_cnpj TEXT,
        address TEXT,
        created_at TEXT,
        FOREIGN KEY(user_id) REFERENCES users(id)
    )
    """)

    c.execute("""
    CREATE TABLE IF NOT EXISTS suppliers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        name TEXT NOT NULL,
        email TEXT,
        phone TEXT,
        cnpj TEXT,
        address TEXT,
        category TEXT DEFAULT 'geral',
        created_at TEXT,
        FOREIGN KEY(user_id) REFERENCES users(id)
    )
    """)

    c.execute("""
    CREATE TABLE IF NOT EXISTS labor (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        name TEXT NOT NULL,
        category TEXT,
        unit TEXT DEFAULT 'hora',
        price REAL,
        description TEXT,
        updated_at TEXT,
        FOREIGN KEY(user_id) REFERENCES users(id)
    )
    """)

    c.execute("""
    CREATE TABLE IF NOT EXISTS equipment (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        name TEXT NOT NULL,
        category TEXT,
        unit TEXT DEFAULT 'dia',
        price REAL,
        description TEXT,
        updated_at TEXT,
        FOREIGN KEY(user_id) REFERENCES users(id)
    )
    """)

    c.execute("""
    CREATE TABLE IF NOT EXISTS projects (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        client_id INTEGER,
        name TEXT,
        client TEXT,
        area REAL,
        project_type TEXT DEFAULT 'residencial',
        finish_level TEXT,
        status TEXT DEFAULT 'em_andamento',
        deadline TEXT,
        notes TEXT,
        real_cost REAL DEFAULT 0,
        created_at TEXT,
        FOREIGN KEY(user_id) REFERENCES users(id),
        FOREIGN KEY(client_id) REFERENCES clients(id)
    )
    """)

    c.execute("""
    CREATE TABLE IF NOT EXISTS materials (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        name TEXT,
        unit TEXT,
        price REAL,
        category TEXT DEFAULT 'geral',
        updated_at TEXT,
        FOREIGN KEY(user_id) REFERENCES users(id)
    )
    """)

    c.execute("""
    CREATE TABLE IF NOT EXISTS budgets (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        project_id INTEGER,
        item_type TEXT DEFAULT 'material',
        material TEXT,
        quantity REAL,
        unit TEXT,
        cost REAL,
        created_at TEXT,
        FOREIGN KEY(project_id) REFERENCES projects(id)
    )
    """)

    try:
        c.execute("ALTER TABLE projects ADD COLUMN project_type TEXT DEFAULT 'residencial'")
    except:
        pass
    
    try:
        c.execute("ALTER TABLE projects ADD COLUMN status TEXT DEFAULT 'em_andamento'")
    except:
        pass
    
    try:
        c.execute("ALTER TABLE projects ADD COLUMN notes TEXT")
    except:
        pass
    
    try:
        c.execute("ALTER TABLE projects ADD COLUMN real_cost REAL DEFAULT 0")
    except:
        pass
    
    try:
        c.execute("ALTER TABLE materials ADD COLUMN category TEXT DEFAULT 'geral'")
    except:
        pass
    
    try:
        c.execute("ALTER TABLE projects ADD COLUMN client_id INTEGER")
    except:
        pass
    
    try:
        c.execute("ALTER TABLE budgets ADD COLUMN item_type TEXT DEFAULT 'material'")
    except:
        pass
    
    try:
        c.execute("ALTER TABLE users ADD COLUMN trial_start_date TEXT")
    except:
        pass
    
    try:
        c.execute("ALTER TABLE users ADD COLUMN trial_end_date TEXT")
    except:
        pass
    
    try:
        c.execute("ALTER TABLE users ADD COLUMN subscription_status TEXT DEFAULT 'trial'")
    except:
        pass
    
    try:
        c.execute("ALTER TABLE users ADD COLUMN subscription_id TEXT")
    except:
        pass
    
    try:
        c.execute("ALTER TABLE users ADD COLUMN plan_id TEXT")
    except:
        pass

    conn.commit()
    conn.close()

if not os.path.exists(DB):
    init_db()
else:
    init_db()

def current_user():
    uid = session.get("user_id")
    if not uid:
        return None
    conn = get_db_conn()
    user = conn.execute(
        """SELECT id, name, email, trial_start_date, trial_end_date, 
        subscription_status, subscription_id, plan_id FROM users WHERE id=?""", 
        (uid,)
    ).fetchone()
    conn.close()
    return user

def check_subscription_status(user):
    if not user:
        return {'active': False, 'status': 'no_user', 'days_left': 0}
    
    status = user['subscription_status'] or 'trial'
    
    if status == 'active':
        return {'active': True, 'status': 'active', 'days_left': None, 'is_trial': False}
    
    if status == 'trial':
        if user['trial_end_date']:
            trial_end = datetime.fromisoformat(user['trial_end_date'])
            now = datetime.utcnow()
            if now < trial_end:
                days_left = (trial_end - now).days + 1
                return {'active': True, 'status': 'trial', 'days_left': days_left, 'is_trial': True}
        
        return {'active': False, 'status': 'trial_expired', 'days_left': 0, 'is_trial': False}
    
    return {'active': False, 'status': status, 'days_left': 0, 'is_trial': False}

def require_active_subscription(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        user = current_user()
        if not user:
            flash("Faça login para acessar esta página", "warning")
            return redirect(url_for("login"))
        
        subscription = check_subscription_status(user)
        if not subscription['active']:
            flash("Seu período de teste expirou. Assine um plano para continuar usando o CiviPro.", "danger")
            return redirect(url_for("subscription_plans"))
        
        return f(*args, **kwargs)
    return decorated_function

def init_default_materials(user_id):
    conn = get_db_conn()
    existing = conn.execute("SELECT COUNT(*) as count FROM materials WHERE user_id=?", (user_id,)).fetchone()
    
    if existing["count"] == 0:
        default_materials = [
            ("Cimento", "sacos", 35.00, "estrutura"),
            ("Areia", "m³", 80.00, "estrutura"),
            ("Brita", "m³", 90.00, "estrutura"),
            ("Tijolos", "un", 0.75, "alvenaria"),
            ("Ferro 6mm", "kg", 6.50, "estrutura"),
            ("Ferro 8mm", "kg", 6.50, "estrutura"),
            ("Ferro 10mm", "kg", 6.50, "estrutura"),
            ("Cal", "sacos", 12.00, "acabamento"),
            ("Argamassa", "sacos", 8.50, "acabamento"),
            ("Cerâmica", "m²", 25.00, "acabamento"),
            ("Azulejo", "m²", 30.00, "acabamento"),
            ("Tinta", "lata", 95.00, "acabamento"),
            ("Tubos PVC", "m", 15.00, "hidráulica"),
            ("Fios elétricos", "m", 3.50, "elétrica"),
        ]
        
        for name, unit, price, category in default_materials:
            conn.execute(
                "INSERT INTO materials (user_id, name, unit, price, category, updated_at) VALUES (?,?,?,?,?,?)",
                (user_id, name, unit, price, category, datetime.utcnow().isoformat())
            )
        conn.commit()
    conn.close()

def init_default_labor(user_id):
    conn = get_db_conn()
    existing = conn.execute("SELECT COUNT(*) as count FROM labor WHERE user_id=?", (user_id,)).fetchone()
    
    if existing["count"] == 0:
        default_labor = [
            ("Pedreiro", "pedreiro", "dia", 180.00, "Profissional qualificado em alvenaria"),
            ("Servente", "ajudante", "dia", 120.00, "Auxiliar de pedreiro"),
            ("Eletricista", "eletricista", "dia", 200.00, "Instalações elétricas"),
            ("Encanador", "encanador", "dia", 200.00, "Instalações hidráulicas"),
            ("Carpinteiro", "carpinteiro", "dia", 190.00, "Esquadrias e formas"),
            ("Pintor", "pintor", "dia", 160.00, "Pintura interna e externa"),
            ("Mestre de obras", "mestre", "dia", 250.00, "Coordenação da obra"),
        ]
        
        for name, category, unit, price, description in default_labor:
            conn.execute(
                "INSERT INTO labor (user_id, name, category, unit, price, description, updated_at) VALUES (?,?,?,?,?,?,?)",
                (user_id, name, category, unit, price, description, datetime.utcnow().isoformat())
            )
        conn.commit()
    conn.close()

def init_default_equipment(user_id):
    conn = get_db_conn()
    existing = conn.execute("SELECT COUNT(*) as count FROM equipment WHERE user_id=?", (user_id,)).fetchone()
    
    if existing["count"] == 0:
        default_equipment = [
            ("Betoneira", "misturador", "dia", 80.00, "Misturador de concreto e argamassa"),
            ("Andaime", "estrutura", "dia", 50.00, "Estrutura de acesso em altura"),
            ("Serra circular", "ferramenta", "dia", 40.00, "Corte de madeira"),
            ("Furadeira industrial", "ferramenta", "dia", 35.00, "Perfuração de concreto e alvenaria"),
            ("Compactador de solo", "compactação", "dia", 120.00, "Compactação de terreno"),
            ("Martelete", "ferramenta", "dia", 45.00, "Demolição e perfuração"),
        ]
        
        for name, category, unit, price, description in default_equipment:
            conn.execute(
                "INSERT INTO equipment (user_id, name, category, unit, price, description, updated_at) VALUES (?,?,?,?,?,?,?)",
                (user_id, name, category, unit, price, description, datetime.utcnow().isoformat())
            )
        conn.commit()
    conn.close()

@app.context_processor
def inject_datetime():
    user = current_user()
    subscription = check_subscription_status(user) if user else None
    return {
        'datetime': datetime, 
        'current_user': current_user,
        'subscription_status': subscription
    }

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        name = request.form["name"].strip()
        email = request.form["email"].strip().lower()
        password = request.form["password"]

        if not name or not email or not password:
            flash("Preencha todos os campos", "warning")
            return redirect(url_for("register"))

        conn = get_db_conn()
        try:
            pw_hash = generate_password_hash(password)
            now = datetime.utcnow()
            trial_end = now + timedelta(days=7)
            
            c = conn.cursor()
            c.execute(
                """INSERT INTO users 
                (name, email, password_hash, created_at, trial_start_date, trial_end_date, subscription_status) 
                VALUES (?,?,?,?,?,?,?)""",
                (name, email, pw_hash, now.isoformat(), now.isoformat(), trial_end.isoformat(), 'trial')
            )
            conn.commit()
            user_id = c.lastrowid
            init_default_materials(user_id)
            init_default_labor(user_id)
            init_default_equipment(user_id)
            flash("Conta criada! Você tem 7 dias de teste grátis com todos os recursos.", "success")
            return redirect(url_for("login"))
        except sqlite3.IntegrityError:
            flash("E-mail já cadastrado", "danger")
            return redirect(url_for("register"))
        finally:
            conn.close()

    return render_template("login.html", action="register")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form["email"].strip().lower()
        password = request.form["password"]

        conn = get_db_conn()
        user = conn.execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()
        conn.close()

        if not user or not check_password_hash(user["password_hash"], password):
            flash("Credenciais inválidas", "danger")
            return redirect(url_for("login"))

        session["user_id"] = user["id"]
        flash("Login realizado", "success")
        return redirect(url_for("dashboard"))

    return render_template("login.html", action="login")

@app.route("/logout")
def logout():
    session.clear()
    flash("Deslogado", "info")
    return redirect(url_for("login"))

@app.route("/subscription-plans")
def subscription_plans():
    user = current_user()
    subscription = check_subscription_status(user) if user else None
    
    plans = [
        {
            'id': 'basic',
            'name': 'Básico',
            'price': 97.00,
            'features': [
                'Até 10 projetos ativos',
                'Biblioteca de materiais',
                'Orçamentos básicos',
                'Exportação PDF',
                'Suporte por email'
            ]
        },
        {
            'id': 'professional',
            'name': 'Profissional',
            'price': 197.00,
            'popular': True,
            'features': [
                'Projetos ilimitados',
                'Biblioteca completa de recursos',
                'Orçamentos avançados (materiais + mão de obra + equipamentos)',
                'Dashboard com gráficos',
                'Exportação PDF profissional',
                'Simulador de cenários',
                'Suporte prioritário'
            ]
        },
        {
            'id': 'enterprise',
            'name': 'Enterprise',
            'price': 397.00,
            'features': [
                'Tudo do Profissional +',
                'Múltiplos usuários',
                'API de integração',
                'Relatórios personalizados',
                'Suporte 24/7',
                'Treinamento personalizado'
            ]
        }
    ]
    
    return render_template("subscription_plans.html", plans=plans, subscription=subscription)

@app.route("/create-subscription", methods=["POST"])
def create_subscription():
    user = current_user()
    if not user:
        flash("Faça login primeiro", "warning")
        return redirect(url_for("login"))
    
    plan_id = request.form.get("plan_id")
    
    plan_prices = {
        'basic': 97.00,
        'professional': 197.00,
        'enterprise': 397.00
    }
    
    plan_names = {
        'basic': 'Básico',
        'professional': 'Profissional',
        'enterprise': 'Enterprise'
    }
    
    if plan_id not in plan_prices:
        flash("Plano inválido", "danger")
        return redirect(url_for("subscription_plans"))
    
    access_token = os.environ.get("MERCADOPAGO_ACCESS_TOKEN")
    if not access_token:
        flash("Configuração de pagamento pendente. Entre em contato com o suporte.", "danger")
        return redirect(url_for("subscription_plans"))
    
    try:
        sdk = mercadopago.SDK(access_token)
        
        preapproval_data = {
            "reason": f"CiviPro {plan_names[plan_id]} - Assinatura Mensal",
            "external_reference": f"user_{user['id']}",
            "payer_email": user['email'],
            "auto_recurring": {
                "frequency": 1,
                "frequency_type": "months",
                "transaction_amount": plan_prices[plan_id],
                "currency_id": "BRL",
                "free_trial": {
                    "frequency": 7,
                    "frequency_type": "days"
                }
            },
            "back_url": url_for("subscription_success", _external=True),
            "status": "pending"
        }
        
        result = sdk.preapproval().create(preapproval_data)
        response = result["response"]
        
        if result["status"] == 201:
            conn = get_db_conn()
            conn.execute(
                "UPDATE users SET subscription_id=?, plan_id=? WHERE id=?",
                (response["id"], plan_id, user["id"])
            )
            conn.commit()
            conn.close()
            
            return redirect(response["init_point"])
        else:
            flash("Erro ao criar assinatura. Tente novamente.", "danger")
            return redirect(url_for("subscription_plans"))
            
    except Exception as e:
        flash(f"Erro ao processar pagamento: {str(e)}", "danger")
        return redirect(url_for("subscription_plans"))

@app.route("/subscription-success")
def subscription_success():
    user = current_user()
    if not user:
        return redirect(url_for("login"))
    
    flash("Assinatura criada com sucesso! Aguarde a confirmação do pagamento.", "success")
    return redirect(url_for("subscription_manage"))

@app.route("/subscription-manage")
def subscription_manage():
    user = current_user()
    if not user:
        return redirect(url_for("login"))
    
    subscription = check_subscription_status(user)
    
    plan_names = {
        'basic': 'Básico',
        'professional': 'Profissional',
        'enterprise': 'Enterprise'
    }
    
    plan_prices = {
        'basic': 97.00,
        'professional': 197.00,
        'enterprise': 397.00
    }
    
    current_plan = plan_names.get(user['plan_id'], 'Nenhum') if user['plan_id'] else 'Nenhum'
    current_price = plan_prices.get(user['plan_id'], 0) if user['plan_id'] else 0
    
    return render_template("subscription_manage.html", 
                         user=user, 
                         subscription=subscription,
                         current_plan=current_plan,
                         current_price=current_price)

@app.route("/mercadopago-webhook", methods=["POST"])
def mercadopago_webhook():
    try:
        data = request.json
        
        if data.get("type") == "subscription_preapproval":
            preapproval_id = data.get("data", {}).get("id")
            
            if not preapproval_id:
                return jsonify({"status": "error", "message": "No preapproval_id"}), 400
            
            access_token = os.environ.get("MERCADOPAGO_ACCESS_TOKEN")
            if not access_token:
                return jsonify({"status": "error", "message": "No access token"}), 500
            
            sdk = mercadopago.SDK(access_token)
            result = sdk.preapproval().get(preapproval_id)
            
            if result["status"] == 200:
                preapproval = result["response"]
                external_ref = preapproval.get("external_reference", "")
                status = preapproval.get("status")
                
                if external_ref.startswith("user_"):
                    user_id = int(external_ref.replace("user_", ""))
                    
                    conn = get_db_conn()
                    
                    if status == "authorized":
                        conn.execute(
                            "UPDATE users SET subscription_status='active' WHERE id=?",
                            (user_id,)
                        )
                    elif status in ["paused", "cancelled"]:
                        conn.execute(
                            "UPDATE users SET subscription_status='cancelled' WHERE id=?",
                            (user_id,)
                        )
                    
                    conn.commit()
                    conn.close()
        
        return jsonify({"status": "ok"}), 200
        
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route("/cancel-subscription", methods=["POST"])
def cancel_subscription():
    user = current_user()
    if not user:
        flash("Faça login primeiro", "warning")
        return redirect(url_for("login"))
    
    if not user['subscription_id']:
        flash("Você não possui uma assinatura ativa", "warning")
        return redirect(url_for("subscription_manage"))
    
    access_token = os.environ.get("MERCADOPAGO_ACCESS_TOKEN")
    if not access_token:
        flash("Erro ao processar cancelamento", "danger")
        return redirect(url_for("subscription_manage"))
    
    try:
        sdk = mercadopago.SDK(access_token)
        result = sdk.preapproval().update(user['subscription_id'], {"status": "cancelled"})
        
        if result["status"] == 200:
            conn = get_db_conn()
            conn.execute(
                "UPDATE users SET subscription_status='cancelled' WHERE id=?",
                (user["id"],)
            )
            conn.commit()
            conn.close()
            
            flash("Assinatura cancelada com sucesso", "success")
        else:
            flash("Erro ao cancelar assinatura", "danger")
            
    except Exception as e:
        flash(f"Erro ao cancelar: {str(e)}", "danger")
    
    return redirect(url_for("subscription_manage"))

@app.route("/")
@app.route("/dashboard")
def dashboard():
    user = current_user()
    if not user:
        return redirect(url_for("login"))

    conn = get_db_conn()
    projects = conn.execute("SELECT * FROM projects WHERE user_id=? ORDER BY created_at DESC", (user["id"],)).fetchall()
    materials = conn.execute("SELECT * FROM materials WHERE user_id=?", (user["id"],)).fetchall()
    clients = conn.execute("SELECT * FROM clients WHERE user_id=?", (user["id"],)).fetchall()
    suppliers = conn.execute("SELECT * FROM suppliers WHERE user_id=?", (user["id"],)).fetchall()
    labor = conn.execute("SELECT * FROM labor WHERE user_id=?", (user["id"],)).fetchall()
    equipment = conn.execute("SELECT * FROM equipment WHERE user_id=?", (user["id"],)).fetchall()

    total_projects = len(projects)
    active_projects = len([p for p in projects if p["status"] == "em_andamento"])
    total_materials = len(materials)
    total_clients = len(clients)
    total_suppliers = len(suppliers)
    total_labor = len(labor)
    total_equipment = len(equipment)
    
    total_estimated = conn.execute("""
        SELECT SUM(cost) as total FROM budgets
        WHERE project_id IN (SELECT id FROM projects WHERE user_id=?)
    """, (user["id"],)).fetchone()["total"] or 0
    
    total_real = conn.execute("""
        SELECT SUM(real_cost) as total FROM projects WHERE user_id=?
    """, (user["id"],)).fetchone()["total"] or 0
    
    project_costs = []
    project_real_costs = []
    for proj in projects[:5]:
        cost = conn.execute("SELECT SUM(cost) as total FROM budgets WHERE project_id=?", (proj["id"],)).fetchone()["total"] or 0
        project_costs.append(cost)
        project_real_costs.append(proj["real_cost"] or 0)
    
    cost_materials = conn.execute("""
        SELECT SUM(cost) as total FROM budgets
        WHERE project_id IN (SELECT id FROM projects WHERE user_id=?) AND item_type='material'
    """, (user["id"],)).fetchone()["total"] or 0
    
    cost_labor = conn.execute("""
        SELECT SUM(cost) as total FROM budgets
        WHERE project_id IN (SELECT id FROM projects WHERE user_id=?) AND item_type='labor'
    """, (user["id"],)).fetchone()["total"] or 0
    
    cost_equipment = conn.execute("""
        SELECT SUM(cost) as total FROM budgets
        WHERE project_id IN (SELECT id FROM projects WHERE user_id=?) AND item_type='equipment'
    """, (user["id"],)).fetchone()["total"] or 0
    
    projects_over_budget = []
    for proj in projects:
        estimated = conn.execute("SELECT SUM(cost) as total FROM budgets WHERE project_id=?", (proj["id"],)).fetchone()["total"] or 0
        real = proj["real_cost"] or 0
        if real > 0 and real > estimated:
            diff = real - estimated
            diff_percent = (diff / estimated * 100) if estimated > 0 else 0
            projects_over_budget.append({
                "name": proj["name"],
                "estimated": estimated,
                "real": real,
                "diff": diff,
                "diff_percent": diff_percent
            })

    conn.close()
    return render_template("dashboard.html", user=user, projects=projects,
                           materials=materials, total_projects=total_projects,
                           active_projects=active_projects,
                           total_materials=total_materials, 
                           total_clients=total_clients,
                           total_suppliers=total_suppliers,
                           total_labor=total_labor,
                           total_equipment=total_equipment,
                           total_estimated=total_estimated,
                           total_real=total_real,
                           project_costs=project_costs,
                           project_real_costs=project_real_costs,
                           cost_materials=cost_materials,
                           cost_labor=cost_labor,
                           cost_equipment=cost_equipment,
                           projects_over_budget=projects_over_budget)

@app.route("/projects")
def projects_list():
    user = current_user()
    if not user:
        return redirect(url_for("login"))
    conn = get_db_conn()
    projs = conn.execute("SELECT * FROM projects WHERE user_id=? ORDER BY created_at DESC", (user["id"],)).fetchall()
    conn.close()
    return render_template("projetos.html", projects=projs, user=user)

@app.route("/projects/add", methods=["GET", "POST"])
def projects_add():
    user = current_user()
    if not user:
        return redirect(url_for("login"))

    if request.method == "POST":
        name = request.form["name"]
        client_id_raw = request.form.get("client_id", "")
        client_name = request.form.get("client_name", "")
        area = float(request.form.get("area") or 0)
        project_type = request.form.get("project_type", "residencial")
        finish = request.form.get("finish", "simples")
        deadline = request.form.get("deadline", "")
        notes = request.form.get("notes", "")

        client_id = None
        final_client_name = ""
        
        if client_id_raw and client_id_raw != "new" and client_id_raw != "":
            client_id = int(client_id_raw)
            conn = get_db_conn()
            client_row = conn.execute("SELECT name FROM clients WHERE id=? AND user_id=?", (client_id, user["id"])).fetchone()
            conn.close()
            if client_row:
                final_client_name = client_row["name"]
        elif client_name:
            final_client_name = client_name

        conn = get_db_conn()
        c = conn.cursor()
        c.execute("""INSERT INTO projects (user_id, client_id, name, client, area, project_type, finish_level, status, deadline, notes, created_at)
                     VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                  (user["id"], client_id, name, final_client_name, area, project_type, finish, "em_andamento", deadline, notes, datetime.utcnow().isoformat()))
        conn.commit()
        project_id = c.lastrowid
        conn.close()
        flash("Projeto criado", "success")
        return redirect(url_for("project_view", project_id=project_id))

    conn = get_db_conn()
    clients = conn.execute("SELECT * FROM clients WHERE user_id=? ORDER BY name", (user["id"],)).fetchall()
    conn.close()
    return render_template("add_project.html", user=user, clients=clients)

@app.route("/projects/<int:project_id>")
def project_view(project_id):
    user = current_user()
    if not user:
        return redirect(url_for("login"))
    conn = get_db_conn()
    proj = conn.execute("SELECT * FROM projects WHERE id=? AND user_id=?", (project_id, user["id"])).fetchone()
    if not proj:
        conn.close()
        flash("Projeto não encontrado", "danger")
        return redirect(url_for("projects_list"))

    budget = conn.execute("SELECT material, quantity, unit, cost FROM budgets WHERE project_id=?", (project_id,)).fetchall()
    conn.close()
    total = sum([b["cost"] for b in budget]) if budget else 0
    return render_template("view_project.html", project=proj, budget=budget, total=total, user=user)

@app.route("/projects/<int:project_id>/edit", methods=["GET", "POST"])
def project_edit(project_id):
    user = current_user()
    if not user:
        return redirect(url_for("login"))
    
    conn = get_db_conn()
    proj = conn.execute("SELECT * FROM projects WHERE id=? AND user_id=?", (project_id, user["id"])).fetchone()
    if not proj:
        conn.close()
        flash("Projeto não encontrado", "danger")
        return redirect(url_for("projects_list"))
    
    if request.method == "POST":
        name = request.form["name"]
        client_id_raw = request.form.get("client_id", "")
        client_name = request.form.get("client_name", "")
        area = float(request.form.get("area") or 0)
        project_type = request.form.get("project_type", "residencial")
        finish = request.form.get("finish", "simples")
        status = request.form.get("status", "em_andamento")
        deadline = request.form.get("deadline", "")
        notes = request.form.get("notes", "")
        real_cost = float(request.form.get("real_cost") or 0)
        
        client_id = None
        final_client_name = ""
        
        if client_id_raw and client_id_raw != "new" and client_id_raw != "":
            client_id = int(client_id_raw)
            conn_temp = get_db_conn()
            client_row = conn_temp.execute("SELECT name FROM clients WHERE id=? AND user_id=?", (client_id, user["id"])).fetchone()
            conn_temp.close()
            if client_row:
                final_client_name = client_row["name"]
        elif client_name:
            final_client_name = client_name
        
        conn.execute("""UPDATE projects SET name=?, client_id=?, client=?, area=?, project_type=?, finish_level=?, 
                        status=?, deadline=?, notes=?, real_cost=? WHERE id=?""",
                     (name, client_id, final_client_name, area, project_type, finish, status, deadline, notes, real_cost, project_id))
        conn.commit()
        conn.close()
        flash("Projeto atualizado", "success")
        return redirect(url_for("project_view", project_id=project_id))
    
    clients = conn.execute("SELECT * FROM clients WHERE user_id=? ORDER BY name", (user["id"],)).fetchall()
    conn.close()
    return render_template("edit_project.html", project=proj, user=user, clients=clients)

@app.route("/projects/<int:project_id>/delete", methods=["POST"])
def project_delete(project_id):
    user = current_user()
    if not user:
        return redirect(url_for("login"))
    
    conn = get_db_conn()
    conn.execute("DELETE FROM budgets WHERE project_id=?", (project_id,))
    conn.execute("DELETE FROM projects WHERE id=? AND user_id=?", (project_id, user["id"]))
    conn.commit()
    conn.close()
    flash("Projeto excluído", "success")
    return redirect(url_for("projects_list"))

@app.route("/materials")
def materials_list():
    user = current_user()
    if not user:
        return redirect(url_for("login"))
    conn = get_db_conn()
    mats = conn.execute("SELECT * FROM materials WHERE user_id=? ORDER BY category, name", (user["id"],)).fetchall()
    conn.close()
    return render_template("materiais.html", materials=mats, user=user)

@app.route("/materials/add", methods=["POST"])
def materials_add():
    user = current_user()
    if not user:
        return redirect(url_for("login"))
    name = request.form["name"]
    unit = request.form["unit"]
    price = float(request.form.get("price") or 0)
    category = request.form.get("category", "geral")
    conn = get_db_conn()
    conn.execute("INSERT INTO materials (user_id, name, unit, price, category, updated_at) VALUES (?,?,?,?,?,?)",
                 (user["id"], name, unit, price, category, datetime.utcnow().isoformat()))
    conn.commit()
    conn.close()
    flash("Material adicionado", "success")
    return redirect(url_for("materials_list"))

@app.route("/materials/<int:material_id>/edit", methods=["POST"])
def materials_edit(material_id):
    user = current_user()
    if not user:
        return redirect(url_for("login"))
    
    name = request.form["name"]
    unit = request.form["unit"]
    price = float(request.form.get("price") or 0)
    category = request.form.get("category", "geral")
    
    conn = get_db_conn()
    conn.execute("UPDATE materials SET name=?, unit=?, price=?, category=?, updated_at=? WHERE id=? AND user_id=?",
                 (name, unit, price, category, datetime.utcnow().isoformat(), material_id, user["id"]))
    conn.commit()
    conn.close()
    flash("Material atualizado", "success")
    return redirect(url_for("materials_list"))

@app.route("/materials/<int:material_id>/delete", methods=["POST"])
def materials_delete(material_id):
    user = current_user()
    if not user:
        return redirect(url_for("login"))
    conn = get_db_conn()
    conn.execute("DELETE FROM materials WHERE id=? AND user_id=?", (material_id, user["id"]))
    conn.commit()
    conn.close()
    flash("Material excluído", "success")
    return redirect(url_for("materials_list"))

@app.route("/clients")
def clients_list():
    user = current_user()
    if not user:
        return redirect(url_for("login"))
    conn = get_db_conn()
    clients = conn.execute("SELECT * FROM clients WHERE user_id=? ORDER BY name", (user["id"],)).fetchall()
    conn.close()
    return render_template("clientes.html", clients=clients, user=user)

@app.route("/clients/add", methods=["POST"])
def clients_add():
    user = current_user()
    if not user:
        return redirect(url_for("login"))
    name = request.form["name"]
    email = request.form.get("email", "")
    phone = request.form.get("phone", "")
    cpf_cnpj = request.form.get("cpf_cnpj", "")
    address = request.form.get("address", "")
    conn = get_db_conn()
    conn.execute("INSERT INTO clients (user_id, name, email, phone, cpf_cnpj, address, created_at) VALUES (?,?,?,?,?,?,?)",
                 (user["id"], name, email, phone, cpf_cnpj, address, datetime.utcnow().isoformat()))
    conn.commit()
    conn.close()
    flash("Cliente adicionado", "success")
    return redirect(url_for("clients_list"))

@app.route("/clients/<int:client_id>/edit", methods=["POST"])
def clients_edit(client_id):
    user = current_user()
    if not user:
        return redirect(url_for("login"))
    
    name = request.form["name"]
    email = request.form.get("email", "")
    phone = request.form.get("phone", "")
    cpf_cnpj = request.form.get("cpf_cnpj", "")
    address = request.form.get("address", "")
    
    conn = get_db_conn()
    conn.execute("UPDATE clients SET name=?, email=?, phone=?, cpf_cnpj=?, address=? WHERE id=? AND user_id=?",
                 (name, email, phone, cpf_cnpj, address, client_id, user["id"]))
    conn.commit()
    conn.close()
    flash("Cliente atualizado", "success")
    return redirect(url_for("clients_list"))

@app.route("/clients/<int:client_id>/delete", methods=["POST"])
def clients_delete(client_id):
    user = current_user()
    if not user:
        return redirect(url_for("login"))
    conn = get_db_conn()
    conn.execute("DELETE FROM clients WHERE id=? AND user_id=?", (client_id, user["id"]))
    conn.commit()
    conn.close()
    flash("Cliente excluído", "success")
    return redirect(url_for("clients_list"))

@app.route("/suppliers")
def suppliers_list():
    user = current_user()
    if not user:
        return redirect(url_for("login"))
    conn = get_db_conn()
    suppliers = conn.execute("SELECT * FROM suppliers WHERE user_id=? ORDER BY category, name", (user["id"],)).fetchall()
    conn.close()
    return render_template("fornecedores.html", suppliers=suppliers, user=user)

@app.route("/suppliers/add", methods=["POST"])
def suppliers_add():
    user = current_user()
    if not user:
        return redirect(url_for("login"))
    name = request.form["name"]
    email = request.form.get("email", "")
    phone = request.form.get("phone", "")
    cnpj = request.form.get("cnpj", "")
    address = request.form.get("address", "")
    category = request.form.get("category", "geral")
    conn = get_db_conn()
    conn.execute("INSERT INTO suppliers (user_id, name, email, phone, cnpj, address, category, created_at) VALUES (?,?,?,?,?,?,?,?)",
                 (user["id"], name, email, phone, cnpj, address, category, datetime.utcnow().isoformat()))
    conn.commit()
    conn.close()
    flash("Fornecedor adicionado", "success")
    return redirect(url_for("suppliers_list"))

@app.route("/suppliers/<int:supplier_id>/edit", methods=["POST"])
def suppliers_edit(supplier_id):
    user = current_user()
    if not user:
        return redirect(url_for("login"))
    
    name = request.form["name"]
    email = request.form.get("email", "")
    phone = request.form.get("phone", "")
    cnpj = request.form.get("cnpj", "")
    address = request.form.get("address", "")
    category = request.form.get("category", "geral")
    
    conn = get_db_conn()
    conn.execute("UPDATE suppliers SET name=?, email=?, phone=?, cnpj=?, address=?, category=? WHERE id=? AND user_id=?",
                 (name, email, phone, cnpj, address, category, supplier_id, user["id"]))
    conn.commit()
    conn.close()
    flash("Fornecedor atualizado", "success")
    return redirect(url_for("suppliers_list"))

@app.route("/suppliers/<int:supplier_id>/delete", methods=["POST"])
def suppliers_delete(supplier_id):
    user = current_user()
    if not user:
        return redirect(url_for("login"))
    conn = get_db_conn()
    conn.execute("DELETE FROM suppliers WHERE id=? AND user_id=?", (supplier_id, user["id"]))
    conn.commit()
    conn.close()
    flash("Fornecedor excluído", "success")
    return redirect(url_for("suppliers_list"))

@app.route("/labor")
def labor_list():
    user = current_user()
    if not user:
        return redirect(url_for("login"))
    conn = get_db_conn()
    labor = conn.execute("SELECT * FROM labor WHERE user_id=? ORDER BY category, name", (user["id"],)).fetchall()
    conn.close()
    return render_template("mao_obra.html", labor=labor, user=user)

@app.route("/labor/add", methods=["POST"])
def labor_add():
    user = current_user()
    if not user:
        return redirect(url_for("login"))
    name = request.form["name"]
    category = request.form.get("category", "geral")
    unit = request.form.get("unit", "hora")
    price = float(request.form.get("price") or 0)
    description = request.form.get("description", "")
    conn = get_db_conn()
    conn.execute("INSERT INTO labor (user_id, name, category, unit, price, description, updated_at) VALUES (?,?,?,?,?,?,?)",
                 (user["id"], name, category, unit, price, description, datetime.utcnow().isoformat()))
    conn.commit()
    conn.close()
    flash("Mão de obra adicionada", "success")
    return redirect(url_for("labor_list"))

@app.route("/labor/<int:labor_id>/edit", methods=["POST"])
def labor_edit(labor_id):
    user = current_user()
    if not user:
        return redirect(url_for("login"))
    
    name = request.form["name"]
    category = request.form.get("category", "geral")
    unit = request.form.get("unit", "hora")
    price = float(request.form.get("price") or 0)
    description = request.form.get("description", "")
    
    conn = get_db_conn()
    conn.execute("UPDATE labor SET name=?, category=?, unit=?, price=?, description=?, updated_at=? WHERE id=? AND user_id=?",
                 (name, category, unit, price, description, datetime.utcnow().isoformat(), labor_id, user["id"]))
    conn.commit()
    conn.close()
    flash("Mão de obra atualizada", "success")
    return redirect(url_for("labor_list"))

@app.route("/labor/<int:labor_id>/delete", methods=["POST"])
def labor_delete(labor_id):
    user = current_user()
    if not user:
        return redirect(url_for("login"))
    conn = get_db_conn()
    conn.execute("DELETE FROM labor WHERE id=? AND user_id=?", (labor_id, user["id"]))
    conn.commit()
    conn.close()
    flash("Mão de obra excluída", "success")
    return redirect(url_for("labor_list"))

@app.route("/equipment")
def equipment_list():
    user = current_user()
    if not user:
        return redirect(url_for("login"))
    conn = get_db_conn()
    equipment = conn.execute("SELECT * FROM equipment WHERE user_id=? ORDER BY category, name", (user["id"],)).fetchall()
    conn.close()
    return render_template("equipamentos.html", equipment=equipment, user=user)

@app.route("/equipment/add", methods=["POST"])
def equipment_add():
    user = current_user()
    if not user:
        return redirect(url_for("login"))
    name = request.form["name"]
    category = request.form.get("category", "geral")
    unit = request.form.get("unit", "dia")
    price = float(request.form.get("price") or 0)
    description = request.form.get("description", "")
    conn = get_db_conn()
    conn.execute("INSERT INTO equipment (user_id, name, category, unit, price, description, updated_at) VALUES (?,?,?,?,?,?,?)",
                 (user["id"], name, category, unit, price, description, datetime.utcnow().isoformat()))
    conn.commit()
    conn.close()
    flash("Equipamento adicionado", "success")
    return redirect(url_for("equipment_list"))

@app.route("/equipment/<int:equipment_id>/edit", methods=["POST"])
def equipment_edit(equipment_id):
    user = current_user()
    if not user:
        return redirect(url_for("login"))
    
    name = request.form["name"]
    category = request.form.get("category", "geral")
    unit = request.form.get("unit", "dia")
    price = float(request.form.get("price") or 0)
    description = request.form.get("description", "")
    
    conn = get_db_conn()
    conn.execute("UPDATE equipment SET name=?, category=?, unit=?, price=?, description=?, updated_at=? WHERE id=? AND user_id=?",
                 (name, category, unit, price, description, datetime.utcnow().isoformat(), equipment_id, user["id"]))
    conn.commit()
    conn.close()
    flash("Equipamento atualizado", "success")
    return redirect(url_for("equipment_list"))

@app.route("/equipment/<int:equipment_id>/delete", methods=["POST"])
def equipment_delete(equipment_id):
    user = current_user()
    if not user:
        return redirect(url_for("login"))
    conn = get_db_conn()
    conn.execute("DELETE FROM equipment WHERE id=? AND user_id=?", (equipment_id, user["id"]))
    conn.commit()
    conn.close()
    flash("Equipamento excluído", "success")
    return redirect(url_for("equipment_list"))

def calc_quantities(area, finish_level, project_type):
    multiplier = 1.0
    if project_type == "comercial":
        multiplier = 1.2
    elif project_type == "industrial":
        multiplier = 1.5
    
    finish_mult = {"simples": 1.0, "medio": 1.3, "alto": 1.6}
    finish_factor = finish_mult.get(finish_level, 1.0)
    
    total_mult = multiplier * finish_factor
    
    materials = [
        ("Cimento", round(area * 5.0 * total_mult), "sacos"),
        ("Areia", round(area * 0.05 * total_mult, 3), "m³"),
        ("Brita", round(area * 0.04 * total_mult, 3), "m³"),
        ("Tijolos", int(area * 15 * total_mult), "un"),
        ("Ferro 10mm", round(area * 8.0 * total_mult, 2), "kg"),
        ("Argamassa", round(area * 0.03 * total_mult), "sacos"),
        ("Cerâmica", round(area * 0.8 * total_mult, 2), "m²"),
        ("Tinta", round(area * 0.25 * total_mult, 2), "lata"),
    ]
    
    dias_obra = max(15, int(area * 0.3 * total_mult))
    
    labor = [
        ("Pedreiro", dias_obra * 1.5, "dia"),
        ("Servente", dias_obra * 2.0, "dia"),
        ("Eletricista", max(5, int(dias_obra * 0.2)), "dia"),
        ("Encanador", max(5, int(dias_obra * 0.2)), "dia"),
        ("Pintor", max(3, int(dias_obra * 0.15)), "dia"),
    ]
    
    equipment = [
        ("Betoneira", min(dias_obra, 30), "dia"),
        ("Andaime", min(dias_obra, 20), "dia"),
        ("Serra circular", max(5, int(dias_obra * 0.1)), "dia"),
    ]
    
    return materials, labor, equipment

@app.route("/projects/<int:project_id>/generate_budget", methods=["POST"])
def generate_budget(project_id):
    user = current_user()
    if not user:
        return redirect(url_for("login"))

    conn = get_db_conn()
    proj = conn.execute("SELECT * FROM projects WHERE id=? AND user_id=?", (project_id, user["id"])).fetchone()
    if not proj:
        conn.close()
        flash("Projeto inválido", "danger")
        return redirect(url_for("projects_list"))

    mats = {m["name"].lower(): m for m in conn.execute("SELECT * FROM materials WHERE user_id=?", (user["id"],)).fetchall()}
    labor_dict = {l["name"].lower(): l for l in conn.execute("SELECT * FROM labor WHERE user_id=?", (user["id"],)).fetchall()}
    equip_dict = {e["name"].lower(): e for e in conn.execute("SELECT * FROM equipment WHERE user_id=?", (user["id"],)).fetchall()}

    project_type = proj["project_type"] if "project_type" in proj.keys() else "residencial"
    materials, labor, equipment = calc_quantities(proj["area"], proj["finish_level"], project_type)
    
    c = conn.cursor()
    c.execute("DELETE FROM budgets WHERE project_id=?", (project_id,))

    total_cost = 0
    
    for name, qty, unit in materials:
        price = 0
        key = name.lower()
        if key in mats:
            price = mats[key]["price"] * qty
        total_cost += price
        c.execute("INSERT INTO budgets (project_id, item_type, material, quantity, unit, cost, created_at) VALUES (?,?,?,?,?,?,?)",
                  (project_id, "material", name, qty, unit, price, datetime.utcnow().isoformat()))
    
    for name, qty, unit in labor:
        price = 0
        key = name.lower()
        if key in labor_dict:
            price = labor_dict[key]["price"] * qty
        total_cost += price
        c.execute("INSERT INTO budgets (project_id, item_type, material, quantity, unit, cost, created_at) VALUES (?,?,?,?,?,?,?)",
                  (project_id, "labor", name, qty, unit, price, datetime.utcnow().isoformat()))
    
    for name, qty, unit in equipment:
        price = 0
        key = name.lower()
        if key in equip_dict:
            price = equip_dict[key]["price"] * qty
        total_cost += price
        c.execute("INSERT INTO budgets (project_id, item_type, material, quantity, unit, cost, created_at) VALUES (?,?,?,?,?,?,?)",
                  (project_id, "equipment", name, qty, unit, price, datetime.utcnow().isoformat()))
    
    c.execute("UPDATE projects SET real_cost=? WHERE id=?", (total_cost, project_id))
    conn.commit()
    conn.close()
    flash("Orçamento gerado com materiais + mão de obra + equipamentos", "success")
    return redirect(url_for("project_view", project_id=project_id))

@app.route("/projects/<int:project_id>/export_pdf")
def export_pdf(project_id):
    user = current_user()
    if not user:
        return redirect(url_for("login"))
    conn = get_db_conn()
    proj = conn.execute("SELECT * FROM projects WHERE id=? AND user_id=?", (project_id, user["id"])).fetchone()
    if not proj:
        conn.close()
        flash("Projeto inválido", "danger")
        return redirect(url_for("projects_list"))
    
    budget_materials = conn.execute("SELECT material, quantity, unit, cost FROM budgets WHERE project_id=? AND item_type='material'", (project_id,)).fetchall()
    budget_labor = conn.execute("SELECT material, quantity, unit, cost FROM budgets WHERE project_id=? AND item_type='labor'", (project_id,)).fetchall()
    budget_equipment = conn.execute("SELECT material, quantity, unit, cost FROM budgets WHERE project_id=? AND item_type='equipment'", (project_id,)).fetchall()
    conn.close()

    buffer = BytesIO()
    p = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4
    y = height - 2*cm

    p.setFont("Helvetica-Bold", 18)
    p.drawString(2*cm, y, "ORÇAMENTO DE OBRA")
    y -= 1*cm
    
    p.setFont("Helvetica-Bold", 12)
    p.drawString(2*cm, y, f"Projeto: {proj['name']}")
    y -= 0.6*cm
    
    p.setFont("Helvetica", 10)
    p.drawString(2*cm, y, f"Cliente: {proj['client'] or '-'}")
    y -= 0.5*cm
    p.drawString(2*cm, y, f"Área: {proj['area']} m²")
    y -= 0.5*cm
    
    project_type_label = {"residencial": "Residencial", "comercial": "Comercial", "industrial": "Industrial"}.get(proj.get("project_type", "residencial"), "Residencial")
    p.drawString(2*cm, y, f"Tipo: {project_type_label} | Acabamento: {proj['finish_level'].title()}")
    y -= 0.5*cm
    
    status_label = {"em_andamento": "Em Andamento", "concluido": "Concluído", "pausado": "Pausado"}.get(proj.get("status", "em_andamento"), "Em Andamento")
    p.drawString(2*cm, y, f"Status: {status_label}")
    if proj.get("deadline"):
        p.drawString(10*cm, y, f"Prazo: {proj['deadline']}")
    y -= 1*cm

    total_geral = 0
    
    if budget_materials:
        p.setFont("Helvetica-Bold", 12)
        p.drawString(2*cm, y, "MATERIAIS")
        y -= 0.5*cm
        
        p.setFont("Helvetica-Bold", 10)
        p.drawString(2*cm, y, "Item")
        p.drawString(10*cm, y, "Qtd")
        p.drawString(13*cm, y, "Un")
        p.drawString(16*cm, y, "Custo (R$)")
        y -= 0.3*cm
        p.line(2*cm, y, width - 2*cm, y)
        y -= 0.5*cm

        p.setFont("Helvetica", 9)
        subtotal_mat = 0
        for row in budget_materials:
            if y < 3*cm:
                p.showPage()
                y = height - 2*cm
            p.drawString(2*cm, y, str(row["material"]))
            p.drawRightString(12*cm, y, f"{row['quantity']:.2f}")
            p.drawString(13*cm, y, row["unit"])
            p.drawRightString(19*cm, y, f"{row['cost']:.2f}")
            subtotal_mat += row["cost"]
            y -= 0.4*cm
        
        y -= 0.2*cm
        p.setFont("Helvetica-Bold", 10)
        p.drawString(13*cm, y, "Subtotal Materiais:")
        p.drawRightString(19*cm, y, f"R$ {subtotal_mat:,.2f}")
        total_geral += subtotal_mat
        y -= 0.8*cm
    
    if budget_labor:
        if y < 8*cm:
            p.showPage()
            y = height - 2*cm
        
        p.setFont("Helvetica-Bold", 12)
        p.drawString(2*cm, y, "MÃO DE OBRA")
        y -= 0.5*cm
        
        p.setFont("Helvetica-Bold", 10)
        p.drawString(2*cm, y, "Item")
        p.drawString(10*cm, y, "Qtd")
        p.drawString(13*cm, y, "Un")
        p.drawString(16*cm, y, "Custo (R$)")
        y -= 0.3*cm
        p.line(2*cm, y, width - 2*cm, y)
        y -= 0.5*cm

        p.setFont("Helvetica", 9)
        subtotal_labor = 0
        for row in budget_labor:
            if y < 3*cm:
                p.showPage()
                y = height - 2*cm
            p.drawString(2*cm, y, str(row["material"]))
            p.drawRightString(12*cm, y, f"{row['quantity']:.2f}")
            p.drawString(13*cm, y, row["unit"])
            p.drawRightString(19*cm, y, f"{row['cost']:.2f}")
            subtotal_labor += row["cost"]
            y -= 0.4*cm
        
        y -= 0.2*cm
        p.setFont("Helvetica-Bold", 10)
        p.drawString(13*cm, y, "Subtotal Mão de Obra:")
        p.drawRightString(19*cm, y, f"R$ {subtotal_labor:,.2f}")
        total_geral += subtotal_labor
        y -= 0.8*cm
    
    if budget_equipment:
        if y < 8*cm:
            p.showPage()
            y = height - 2*cm
        
        p.setFont("Helvetica-Bold", 12)
        p.drawString(2*cm, y, "EQUIPAMENTOS")
        y -= 0.5*cm
        
        p.setFont("Helvetica-Bold", 10)
        p.drawString(2*cm, y, "Item")
        p.drawString(10*cm, y, "Qtd")
        p.drawString(13*cm, y, "Un")
        p.drawString(16*cm, y, "Custo (R$)")
        y -= 0.3*cm
        p.line(2*cm, y, width - 2*cm, y)
        y -= 0.5*cm

        p.setFont("Helvetica", 9)
        subtotal_equip = 0
        for row in budget_equipment:
            if y < 3*cm:
                p.showPage()
                y = height - 2*cm
            p.drawString(2*cm, y, str(row["material"]))
            p.drawRightString(12*cm, y, f"{row['quantity']:.2f}")
            p.drawString(13*cm, y, row["unit"])
            p.drawRightString(19*cm, y, f"{row['cost']:.2f}")
            subtotal_equip += row["cost"]
            y -= 0.4*cm
        
        y -= 0.2*cm
        p.setFont("Helvetica-Bold", 10)
        p.drawString(13*cm, y, "Subtotal Equipamentos:")
        p.drawRightString(19*cm, y, f"R$ {subtotal_equip:,.2f}")
        total_geral += subtotal_equip
        y -= 0.8*cm
    
    if y < 5*cm:
        p.showPage()
        y = height - 2*cm
    
    y -= 0.3*cm
    p.line(2*cm, y, width - 2*cm, y)
    y -= 0.7*cm
    p.setFont("Helvetica-Bold", 14)
    p.drawString(2*cm, y, "TOTAL GERAL:")
    p.drawRightString(19*cm, y, f"R$ {total_geral:,.2f}")
    
    if proj.get("real_cost", 0) > 0:
        y -= 0.6*cm
        p.setFont("Helvetica", 10)
        p.drawString(2*cm, y, "Custo Real:")
        p.drawRightString(19*cm, y, f"R$ {proj['real_cost']:,.2f}")
        
        diff = proj['real_cost'] - total_geral
        y -= 0.5*cm
        color = "green" if diff < 0 else "red"
        p.drawString(2*cm, y, "Diferença:")
        p.drawRightString(19*cm, y, f"R$ {diff:,.2f}")
    
    if proj.get("notes"):
        y -= 1*cm
        p.setFont("Helvetica-Bold", 10)
        p.drawString(2*cm, y, "Observações:")
        y -= 0.5*cm
        p.setFont("Helvetica", 9)
        lines = proj["notes"].split('\n')
        for line in lines[:5]:
            p.drawString(2*cm, y, line[:80])
            y -= 0.4*cm

    p.setFont("Helvetica-Oblique", 8)
    p.drawString(2*cm, 1*cm, f"Gerado em: {datetime.utcnow().strftime('%d/%m/%Y %H:%M')}")
    p.drawString(2*cm, 0.6*cm, "Sistema desenvolvido por João Layon - Desenvolvedor Full Stack")

    p.showPage()
    p.save()
    buffer.seek(0)

    filename = f"orcamento_{proj['name'].replace(' ', '_')}.pdf"
    return send_file(buffer, mimetype="application/pdf", as_attachment=True, download_name=filename)

@app.route("/reports")
def reports():
    user = current_user()
    if not user:
        return redirect(url_for("login"))
    
    conn = get_db_conn()
    projects = conn.execute("""
        SELECT p.*, 
               (SELECT SUM(cost) FROM budgets WHERE project_id = p.id) as estimated_cost
        FROM projects p 
        WHERE p.user_id=? 
        ORDER BY p.created_at DESC
    """, (user["id"],)).fetchall()
    
    total_estimated = sum([p["estimated_cost"] or 0 for p in projects])
    total_real = sum([p["real_cost"] or 0 for p in projects])
    
    conn.close()
    return render_template("relatorios.html", projects=projects, 
                          total_estimated=total_estimated, 
                          total_real=total_real, user=user)

@app.route("/simulator")
def simulator():
    user = current_user()
    if not user:
        return redirect(url_for("login"))
    
    conn = get_db_conn()
    materials = conn.execute("SELECT * FROM materials WHERE user_id=? ORDER BY category, name", (user["id"],)).fetchall()
    labor = conn.execute("SELECT * FROM labor WHERE user_id=? ORDER BY category, name", (user["id"],)).fetchall()
    equipment = conn.execute("SELECT * FROM equipment WHERE user_id=? ORDER BY category, name", (user["id"],)).fetchall()
    conn.close()
    
    return render_template("simulador.html", user=user, materials=materials, labor=labor, equipment=equipment)

@app.route("/api/materials/search")
def api_material_search():
    q = request.args.get("q", "").strip().lower()
    user = current_user()
    if not user:
        return jsonify([])

    conn = get_db_conn()
    rows = conn.execute("SELECT id, name, unit, price FROM materials WHERE user_id=? AND LOWER(name) LIKE ? LIMIT 10",
                        (user["id"], f"%{q}%")).fetchall()
    conn.close()
    results = [dict(r) for r in rows]
    return jsonify(results)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
