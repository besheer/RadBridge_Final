
import os, re, secrets, io, zipfile, json
from datetime import datetime
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, session, flash, abort, send_file
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash

app=Flask(__name__)
app.secret_key=os.environ["PLATFORM_SECRET_KEY"]
app.config["SQLALCHEMY_DATABASE_URI"]=os.environ.get("PLATFORM_DATABASE_URL","postgresql+psycopg2://platform:platform@platform-db:5432/platform")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"]=False
app.config["SESSION_COOKIE_HTTPONLY"]=True
app.config["SESSION_COOKIE_SAMESITE"]="Strict"
app.config["SESSION_COOKIE_SECURE"]=os.environ.get("PLATFORM_COOKIE_SECURE","true").lower()=="true"
db=SQLAlchemy(app)

class PlatformUser(db.Model):
    id=db.Column(db.Integer,primary_key=True)
    username=db.Column(db.String(80),unique=True,nullable=False)
    password_hash=db.Column(db.String(255),nullable=False)
    active=db.Column(db.Boolean,default=True)
    created_at=db.Column(db.DateTime,default=datetime.utcnow)

class Plan(db.Model):
    id=db.Column(db.Integer,primary_key=True)
    code=db.Column(db.String(40),unique=True,nullable=False)
    name=db.Column(db.String(100),nullable=False)
    storage_gb=db.Column(db.Integer,default=100)
    max_users=db.Column(db.Integer,default=20)
    active=db.Column(db.Boolean,default=True)

class Tenant(db.Model):
    id=db.Column(db.Integer,primary_key=True)
    tenant_id=db.Column(db.String(40),unique=True,nullable=False,index=True)
    company_name=db.Column(db.String(160),nullable=False)
    subdomain=db.Column(db.String(120),unique=True,nullable=False)
    plan_id=db.Column(db.Integer,db.ForeignKey("plan.id"))
    status=db.Column(db.String(30),default="PROVISIONING",index=True)
    storage_gb=db.Column(db.Integer,default=100)
    admin_email=db.Column(db.String(180),default="")
    notes=db.Column(db.Text,default="")
    created_at=db.Column(db.DateTime,default=datetime.utcnow)
    updated_at=db.Column(db.DateTime,default=datetime.utcnow,onupdate=datetime.utcnow)
    plan=db.relationship("Plan")

class PlatformAudit(db.Model):
    id=db.Column(db.Integer,primary_key=True)
    created_at=db.Column(db.DateTime,default=datetime.utcnow,index=True)
    username=db.Column(db.String(80),default="")
    action=db.Column(db.String(80),nullable=False)
    tenant_id=db.Column(db.String(40),default="")
    details=db.Column(db.Text,default="")
    ip=db.Column(db.String(80),default="")

def audit(action,tenant_id="",details=""):
    db.session.add(PlatformAudit(
        username=session.get("username",""),
        action=action,tenant_id=tenant_id,details=details,
        ip=request.headers.get("X-Forwarded-For",request.remote_addr or "")[:80]
    ))

def login_required(fn):
    @wraps(fn)
    def w(*a,**kw):
        if not session.get("uid"):
            return redirect(url_for("login",next=request.path))
        return fn(*a,**kw)
    return w

def csrf_token():
    if "csrf" not in session: session["csrf"]=secrets.token_urlsafe(32)
    return session["csrf"]
app.jinja_env.globals["csrf_token"]=csrf_token

def verify_csrf():
    if request.form.get("csrf")!=session.get("csrf"): abort(400,"Invalid CSRF token")

@app.before_request
def security_headers_marker():
    pass

@app.after_request
def security_headers(resp):
    resp.headers["X-Frame-Options"]="DENY"
    resp.headers["X-Content-Type-Options"]="nosniff"
    resp.headers["Referrer-Policy"]="no-referrer"
    resp.headers["Content-Security-Policy"]="default-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; script-src 'self' 'unsafe-inline'; frame-ancestors 'none'"
    return resp

@app.route("/login",methods=["GET","POST"])
def login():
    if request.method=="POST":
        u=PlatformUser.query.filter_by(username=request.form.get("username","").strip()).first()
        if u and u.active and check_password_hash(u.password_hash,request.form.get("password","")):
            session.clear();session["uid"]=u.id;session["username"]=u.username;session["csrf"]=secrets.token_urlsafe(32)
            audit("LOGIN");db.session.commit()
            return redirect(url_for("dashboard"))
        flash("Invalid username or password.","danger")
    return render_template("login.html")

@app.post("/logout")
@login_required
def logout():
    verify_csrf();audit("LOGOUT");db.session.commit();session.clear()
    return redirect(url_for("login"))

@app.get("/")
@login_required
def dashboard():
    tenants=Tenant.query.order_by(Tenant.company_name).all()
    stats={
      "total":len(tenants),
      "active":sum(1 for x in tenants if x.status=="ACTIVE"),
      "suspended":sum(1 for x in tenants if x.status=="SUSPENDED"),
      "provisioning":sum(1 for x in tenants if x.status=="PROVISIONING"),
    }
    return render_template("dashboard.html",tenants=tenants,stats=stats)

@app.route("/companies/new",methods=["GET","POST"])
@login_required
def company_new():
    plans=Plan.query.filter_by(active=True).order_by(Plan.name).all()
    if request.method=="POST":
        verify_csrf()
        name=request.form.get("company_name","").strip()
        tid=request.form.get("tenant_id","").strip().lower()
        sub=request.form.get("subdomain","").strip().lower()
        if not re.fullmatch(r"[a-z0-9][a-z0-9-]{2,31}",tid):
            flash("Tenant ID must be 3-32 lowercase letters, numbers or hyphens.","danger")
            return render_template("company_form.html",plans=plans)
        if not re.fullmatch(r"[a-z0-9][a-z0-9-]{1,62}",sub):
            flash("Invalid subdomain.","danger");return render_template("company_form.html",plans=plans)
        if Tenant.query.filter((Tenant.tenant_id==tid)|(Tenant.subdomain==sub)).first():
            flash("Tenant ID or subdomain already exists.","danger");return render_template("company_form.html",plans=plans)
        plan=Plan.query.get(request.form.get("plan_id",type=int))
        t=Tenant(tenant_id=tid,company_name=name,subdomain=sub,plan=plan,
                 storage_gb=(plan.storage_gb if plan else 100),
                 admin_email=request.form.get("admin_email","").strip(),
                 notes=request.form.get("notes","").strip())
        db.session.add(t);audit("TENANT_CREATE_REQUEST",tid,f"name={name};subdomain={sub}")
        db.session.commit()
        flash("Company created in PROVISIONING state. Download the deployment bundle and deploy it in Portainer.","success")
        return redirect(url_for("company_detail",tenant_id=tid))
    return render_template("company_form.html",plans=plans)

@app.get("/companies/<tenant_id>")
@login_required
def company_detail(tenant_id):
    t=Tenant.query.filter_by(tenant_id=tenant_id).first_or_404()
    events=PlatformAudit.query.filter_by(tenant_id=tenant_id).order_by(PlatformAudit.id.desc()).limit(30).all()
    return render_template("company_detail.html",t=t,events=events)

@app.post("/companies/<tenant_id>/status")
@login_required
def company_status(tenant_id):
    verify_csrf()
    t=Tenant.query.filter_by(tenant_id=tenant_id).first_or_404()
    new=request.form.get("status","")
    allowed={"PROVISIONING","ACTIVE","SUSPENDED","ARCHIVED","DELETION_PENDING"}
    if new not in allowed: abort(400)
    old=t.status;t.status=new
    audit("TENANT_STATUS",tenant_id,f"{old}->{new}")
    db.session.commit()
    flash(f"Status changed to {new}.","success")
    return redirect(url_for("company_detail",tenant_id=tenant_id))

@app.get("/companies/<tenant_id>/bundle")
@login_required
def company_bundle(tenant_id):
    t=Tenant.query.filter_by(tenant_id=tenant_id).first_or_404()
    domain=f"{t.subdomain}.{os.environ.get('BASE_DOMAIN','radbridges.com')}"
    dbpass=secrets.token_hex(32);secret=secrets.token_hex(48);pacspass=secrets.token_hex(32)
    aet=re.sub(r"[^A-Z0-9_]","_",t.tenant_id.upper())[:16]
    env=f"""TENANT_ID={t.tenant_id}
TENANT_NAME={t.company_name}
RIS_PUBLIC_URL=https://{domain}
RIS_LOCAL_PORT=18090
DB_NAME=ris
DB_USER=ris
DB_PASSWORD={dbpass}
SECRET_KEY={secret}
PACS_AET={aet}
PACS_USER=orthanc
PACS_PASSWORD={pacspass}
PACS_BIND_IP=127.0.0.1
PACS_DICOM_PORT=14242
ORTHANC_PUBLIC_URL=
"""
    compose=open("/app/templates-assets/docker-compose.tenant.yml",encoding="utf-8").read()
    readme=f"""RadBridge tenant provisioning bundle
Company: {t.company_name}
Tenant: {t.tenant_id}
Host: {domain}

1. Create a Portainer Stack named radbridge_{t.tenant_id}
2. Use compose.yml as the stack definition.
3. Enter .env values as Portainer environment variables/secrets.
4. Route HTTPS {domain} to the local RIS port.
5. Restrict DICOM to approved site/VPN IPs.
6. After health checks pass, mark the tenant ACTIVE in admin.radbridges.com.

This bundle contains infrastructure secrets. Store it securely and delete local copies after deployment.
"""
    mem=io.BytesIO()
    with zipfile.ZipFile(mem,"w",zipfile.ZIP_DEFLATED) as z:
        z.writestr("compose.yml",compose);z.writestr(".env",env);z.writestr("README.txt",readme)
    mem.seek(0);audit("TENANT_BUNDLE_DOWNLOAD",t.tenant_id);db.session.commit()
    return send_file(mem,as_attachment=True,download_name=f"radbridge-{t.tenant_id}-provisioning.zip",mimetype="application/zip")

@app.get("/plans")
@login_required
def plans():
    return render_template("plans.html",plans=Plan.query.order_by(Plan.id).all())

@app.route("/plans/new",methods=["GET","POST"])
@login_required
def plan_new():
    if request.method=="POST":
        verify_csrf()
        p=Plan(code=request.form["code"].strip().upper(),name=request.form["name"].strip(),
               storage_gb=request.form.get("storage_gb",100,type=int),max_users=request.form.get("max_users",20,type=int))
        db.session.add(p);audit("PLAN_CREATE",details=p.code);db.session.commit()
        return redirect(url_for("plans"))
    return render_template("plan_form.html")

@app.get("/audit")
@login_required
def audit_page():
    return render_template("audit.html",rows=PlatformAudit.query.order_by(PlatformAudit.id.desc()).limit(500).all())

def bootstrap():
    db.create_all()
    if Plan.query.count()==0:
        db.session.add_all([
            Plan(code="CLINIC",name="Clinic",storage_gb=100,max_users=15),
            Plan(code="PRO",name="Professional",storage_gb=500,max_users=50),
            Plan(code="MULTI",name="Multi-Branch",storage_gb=2000,max_users=150),
            Plan(code="ENTERPRISE",name="Enterprise",storage_gb=5000,max_users=500),
        ])
    admin_user=os.environ.get("PLATFORM_ADMIN_USER","platformadmin")
    admin_pass=os.environ.get("PLATFORM_ADMIN_PASSWORD")
    if admin_pass and not PlatformUser.query.filter_by(username=admin_user).first():
        db.session.add(PlatformUser(username=admin_user,password_hash=generate_password_hash(admin_pass)))
    db.session.commit()

