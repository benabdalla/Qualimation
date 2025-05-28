import argparse
from flask import Flask, redirect, render_template
from sympy import false
from routes.auth_routes import auth_bp
from routes.main_routes import main_bp
from routes.gherkin_routes import gherkin_bp
from routes.recl_routes import recl_bp
from routes.results_routes import results_bp
import os
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "your-secret-key")

# Enregistrer les Blueprints
app.register_blueprint(auth_bp, url_prefix='/auth')
app.register_blueprint(main_bp, url_prefix='/main')
app.register_blueprint(gherkin_bp, url_prefix='/gherkin')
app.register_blueprint(results_bp, url_prefix='/results')
app.register_blueprint(recl_bp, url_prefix='/recl')



# Redirection vers page d’accueil (ex: auth.welcome) si route racine
@app.route('/')
def home():
    return render_template('welcome.html')

if __name__ == '__main__':
    app.run(debug=false,host='0.0.0.0',port=5001)
