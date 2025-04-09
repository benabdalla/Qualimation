import torch
import h5py
import json
import os
import requests
import asyncio
import logging
from transformers import AutoModelForSeq2SeqLM, AutoTokenizer
from flask import Flask, request, jsonify, render_template, redirect, url_for, flash, send_file
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.middleware.proxy_fix import ProxyFix
from langchain_google_genai import ChatGoogleGenerativeAI
from config_app.agent.service import Agent
from config_app.browser.browser import Browser, BrowserConfig
from config_app.browser.context import BrowserContextConfig, BrowserContextWindowSize
from pydantic import SecretStr, BaseModel
from datetime import datetime
import base64

# Load environment variables
from dotenv import load_dotenv
load_dotenv()

# Flask app setup
app = Flask(__name__)
app.secret_key = os.urandom(24)  # Secure secret key for sessions
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_host=1)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Flask-Login setup
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"

# Constants
MODEL_PATH = "Salesforce/codet5p-220m"
WEIGHTS_FILE = "../DesktopAppBot/model_weights.h5"
FEEDBACK_FILE = "feedback_data.json"
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY") or "YOUR_GEMINI_API_KEY"
GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-pro:generateContent"
USERS_DB = "users.json"

# Browser automation globals
_global_browser = None
_global_browser_context = None
_global_agent = None

DEFAULT_CONFIG = {
    "headless": True,
    "disable_security": False,
    "window_w": 1280,
    "window_h": 720,
    "max_steps": 100,
    "use_vision": False,
    "save_recording_path": "./recordings",
    "save_trace_path": "./traces"
}
# User class for Flask-Login
class User(UserMixin):
    def __init__(self, username, job):
        self.id = username
        self.job = job

# Load users from JSON
def load_users():
    if not os.path.exists(USERS_DB):
        with open(USERS_DB, 'w') as f:
            json.dump({}, f)
    with open(USERS_DB, 'r') as f:
        return json.load(f)

# Save users to JSON
def save_users(users):
    with open(USERS_DB, 'w') as f:
        json.dump(users, f, indent=4)

@login_manager.user_loader
def load_user(username):
    users = load_users()
    if username in users:
        return User(username, users[username]["job"])
    return None

# Utility to handle async.js routes in Flask
def async_to_sync(func):
    def wrapper(*args, **kwargs):
        return asyncio.run(func(*args, **kwargs))
    return wrapper

# Authentication routes
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        users = load_users()
        if username in users and check_password_hash(users[username]["password"], password):
            user = User(username, users[username]["job"])
            login_user(user)
            if user.job == "Employee":
                return redirect(url_for('home'))
            elif user.job == "Developer":
                return redirect(url_for('developer_home'))
            flash("Invalid job role for this application!")
            return redirect(url_for('login'))
        else:
            flash("Invalid username or password!")
            return redirect(url_for('login'))
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        job = request.form.get('job')
        if not username or not password or not job:
            flash("All fields are required!")
            return redirect(url_for('register'))
        if job not in ["Employee", "Developer"]:
            flash("Job must be 'Employee' or 'Developer'!")
            return redirect(url_for('register'))
        users = load_users()
        if username in users:
            flash("Username already exists!")
            return redirect(url_for('register'))
        users[username] = {
            "password": generate_password_hash(password),
            "job": job
        }
        save_users(users)
        user = User(username, job)
        login_user(user)
        flash("Registration successful!")
        if user.job == "Employee":
            return redirect(url_for('home'))
        elif user.job == "Developer":
            return redirect(url_for('developer_home'))
        return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash("You have been logged out.")
    return redirect(url_for('login'))

# Browser automation routes
class TaskInput(BaseModel):
    task: str
    url: str = None
    add_infos: str = None
    max_steps: int = DEFAULT_CONFIG["max_steps"]
    headless: bool = DEFAULT_CONFIG["headless"]
    use_vision: bool = DEFAULT_CONFIG["use_vision"]

@app.route('/')
@login_required
def home():
    if current_user.job in ["Employee", "Developer"]:
        logger.info("Rendering home page")
        return render_template("index.html", config=DEFAULT_CONFIG)
    flash("Access restricted to Employees and Developers!")
    return redirect(url_for('login'))

@app.route("/execute-bot", methods=["POST"], endpoint="execute_bot_endpoint")
@login_required
@async_to_sync
async def execute_bot():
    if current_user.job not in ["Employee", "Developer"]:
        return jsonify({"error": "Unauthorized access"}), 403

    global _global_browser, _global_browser_context, _global_agent
    logger.info("Received /execute-bot request")
    xray_report_filename = None
    agent_report_filename = None
    extracted_report_filename = None
    errors = []
    final_result = None
    model_actions = []
    model_thoughts = []
    logs = []
    extracted_from_page = None
    start_time = datetime.now().strftime("%Y-%m-%dT%H:%M:%S+01:00")
    screenshot_base64 = None
    task_completed = True  # Default to True, will set to False if unfinished or fails

    try:
        data = TaskInput(**request.json)
        logger.info(f"Task input: {data}")
        task = data.task
        url = data.url
        add_infos = data.add_infos
        max_steps = data.max_steps
        headless = data.headless
        use_vision = data.use_vision

        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            logger.error("Gemini API key missing")
            errors.append("Gemini API key missing")
            raise ValueError("Gemini API key missing")

        llm = ChatGoogleGenerativeAI(
            model="gemini-1.5-flash",
            api_key=SecretStr(api_key)
        )
        logger.info("LLM initialized")

        browser_config = BrowserConfig(
            headless=headless,
            disable_security=DEFAULT_CONFIG["disable_security"],
            extra_chromium_args=[f"--window-size={DEFAULT_CONFIG['window_w']},{DEFAULT_CONFIG['window_h']}"]
        )
        context_config = BrowserContextConfig(
            trace_path=DEFAULT_CONFIG["save_trace_path"],
            save_recording_path=DEFAULT_CONFIG["save_recording_path"],
            no_viewport=False,
            browser_window_size=BrowserContextWindowSize(width=DEFAULT_CONFIG["window_w"], height=DEFAULT_CONFIG["window_h"])
        )

        os.makedirs(DEFAULT_CONFIG["save_recording_path"], exist_ok=True)
        os.makedirs(DEFAULT_CONFIG["save_trace_path"], exist_ok=True)
        os.makedirs("./reports", exist_ok=True)
        logger.info("Directories ensured")

        if _global_browser is None:
            _global_browser = Browser(config=browser_config)
            logger.info("Browser initialized")
        if _global_browser_context is None:
            _global_browser_context = await _global_browser.new_context(config=context_config)
            logger.info("Browser context initialized")

        if url:
            task = f"Start at {url} and {task}"
        if add_infos:
            task = f"{task} Additional info: {add_infos}"
        if "leave when you finish all steps" not in task.lower():
            task += " leave when you finish all steps"
        logger.info(f"Refined task: {task}")

        _global_agent = Agent(
            task=task,
            llm=llm,
            use_vision=use_vision,
            browser=_global_browser,
            browser_context=_global_browser_context,
            max_actions_per_step=5,
            save_conversation_path="./conversations"
        )
        logger.info(f"Agent initialized with task: {task}")

        def log_callback(message):
            logs.append(message)
            logger.info(message)
            nonlocal extracted_from_page
            if "Extracted from page" in message:
                extracted_from_page = message
                logger.info(f"Set extracted_from_page: {extracted_from_page}")

        history = await _global_agent.run(max_steps=max_steps)
        logger.info("Agent run completed")

        # Get results and actions
        final_result = history.final_result() if history and history.final_result() else None
        errors = history.errors() if history else []
        model_actions = history.model_actions() if history else []
        model_thoughts = history.model_thoughts() if history else []

        # Log key information for debugging
        logger.info(f"Final result: {final_result}")
        logger.info(f"Errors: {errors}")
        logger.info(f"Model actions: {len(model_actions)} actions recorded")

        # Fallback to extract "Extracted from page" from history
        if not extracted_from_page and history:
            for action_result in history.action_results():
                if action_result.extracted_content and "Extracted from page" in action_result.extracted_content:
                    extracted_from_page = action_result.extracted_content
                    logger.info(f"Extracted from page set from history: {extracted_from_page}")
                    break

        if final_result and extracted_from_page:
            final_result = f"{extracted_from_page}\n{final_result}"
        elif extracted_from_page and not final_result:
            final_result = extracted_from_page

        if not final_result:
            if history and history.history:
                last_result = history.history[-1].result[-1] if history.history[-1].result else None
                last_extracted = last_result.extracted_content if last_result and last_result.extracted_content else "No specific result extracted"
                final_result = f"{extracted_from_page}\n{last_extracted}" if extracted_from_page else last_extracted
            else:
                final_result = "Page content unavailable"
            logger.info(f"Fallback result: {final_result}")

        logger.warning("Screenshot capture skipped: BrowserContext.pages not available in browser_use API")
        screenshot_base64 = None

    except ValueError as ve:
        logger.error(f"Invalid input: {str(ve)}")
        errors.append(f"Invalid input: {str(ve)}")
        task_completed = False
    except Exception as e:
        logger.error(f"Error executing bot: {str(e)}")
        errors.append(str(e))
        task_completed = False

    finally:
        filtered_errors = [str(e) for e in errors if e is not None]
        critical_errors = len(filtered_errors) > 0

        # Check logs for "❌ Unfinished" to determine if the task is unfinished
        is_unfinished = any("❌ Unfinished" in log for log in logs)
        logger.info(f"Is unfinished (based on '❌ Unfinished' in logs): {is_unfinished}")
        logger.info(f"All logs: {logs}")

        if is_unfinished:
            task_completed = False
            logger.info("Task marked as incomplete due to '❌ Unfinished' in logs")

        # Additional heuristic checks if not explicitly unfinished
        if not critical_errors and not is_unfinished:
            if history and len(history.history) >= max_steps:
                logger.info("Task incomplete: Hit max_steps limit")
                task_completed = False
            elif not model_actions and final_result == "Page content unavailable":
                logger.info("Task incomplete: No actions recorded and no meaningful result")
                task_completed = False
            else:
                completion_indicators = ["task completed", "finished all steps", "successfully executed"]
                if any(indicator in final_result.lower() for indicator in completion_indicators):
                    task_completed = True
                    logger.info("Task completed: Found completion indicator in final_result")
                elif len(model_actions) > 0 and final_result != "Page content unavailable":
                    task_completed = True
                    logger.info("Task completed: Actions recorded and non-trivial result")
                else:
                    logger.info("Task incomplete: No clear completion indicator")
                    task_completed = False

        # Determine status
        status = "SUCCESSFUL" if task_completed and not critical_errors else "FAILED"
        status = "FAILED" if is_unfinished else "SUCCESSFUL"
        finish_time = datetime.now().strftime("%Y-%m-%dT%H:%M:%S+01:00")

        # Log final status determination
        logger.info(f"Task completed: {task_completed}, Critical errors: {critical_errors}, Status: {status}")

        # Generate XRay report
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        xray_report_filename = f"xray_report_{timestamp}.json"
        xray_report_path = os.path.join("./reports", xray_report_filename)
        xray_report = {
            "tests": [
                {
                    "testKey": "QUALI-456",
                    "start": start_time,
                    "finish": finish_time,
                    "comment": "Automated test execution",
                    "status": "PASSED" if status == "SUCCESSFUL" else "FAILED",
                    "steps": [
                        {
                            "status": "PASSED" if status == "SUCCESSFUL" else "FAILED",
                            "actualResult": "" if status == "SUCCESSFUL" else "Step 1: Task incomplete or failed"
                        }
                    ]
                }
            ]
        }

        # Generate agent report with add_infos
        agent_report_filename = f"agent_report_{timestamp}.json"
        agent_report_path = os.path.join("./reports", agent_report_filename)
        agent_report = {
            "task": task if 'task' in locals() else "Unknown task",
            "url": url if 'url' in locals() else "N/A",
            "add_infos": add_infos if 'add_infos' in locals() else "N/A",
            "start_time": start_time,
            "finish_time": finish_time,
            "status": status,
            "final_result": final_result if 'final_result' in locals() else "N/A",
            "errors": filtered_errors,
            "model_actions": [str(action) for action in model_actions] if 'model_actions' in locals() else [],
            "model_thoughts": [thought.model_dump() for thought in model_thoughts] if 'model_thoughts' in locals() else [],
            "logs": logs if 'logs' in locals() else []
        }

        # Save extracted_from_page to a JSON file
        if extracted_from_page:
            extracted_report_filename = f"extracted_report_{timestamp}.json"
            extracted_report_path = os.path.join("./reports", extracted_report_filename)
            try:
                json_start = extracted_from_page.find("```json")
                json_end = extracted_from_page.rfind("```")
                if json_start != -1 and json_end != -1:
                    json_content = extracted_from_page[json_start + 7:json_end].strip()
                    extracted_data = json.loads(json_content)
                else:
                    extracted_data = {"content": extracted_from_page}
                with open(extracted_report_path, "w", encoding="utf-8") as f:
                    json.dump(extracted_data, f, indent=2)
                logger.info(f"Extracted report saved: {extracted_report_path}")
            except Exception as e:
                logger.error(f"Failed to save extracted report: {str(e)}")
                extracted_report_filename = None

        # Save reports
        try:
            with open(xray_report_path, "w", encoding="utf-8") as f:
                json.dump(xray_report, f, indent=2)
            with open(agent_report_path, "w", encoding="utf-8") as f:
                json.dump(agent_report, f, indent=2)
            logger.info(f"Reports saved: {xray_report_path}, {agent_report_path}")
        except Exception as e:
            logger.error(f"Failed to save reports: {str(e)}")
            xray_report_filename = None
            agent_report_filename = None

        # Cleanup
        if _global_browser_context:
            try:
                await _global_browser_context.close()
                logger.info("Browser context closed")
            except Exception as e:
                logger.error(f"Error closing browser context: {str(e)}")
        if _global_browser:
            try:
                await _global_browser.close()
                logger.info("Browser closed")
            except Exception as e:
                logger.error(f"Error closing browser: {str(e)}")
        _global_browser = None
        _global_browser_context = None
        _global_agent = None

        response = {
            "success": bool(task_completed and not critical_errors),
            "final_result": final_result if 'final_result' in locals() else "Execution failed",
            "extracted_from_page": extracted_from_page,
            "errors": filtered_errors,
            "status": status,
            "xray_report_url": f"/download-report/{xray_report_filename}" if xray_report_filename else None,
            "agent_report_url": f"/download-report/{agent_report_filename}" if agent_report_filename else None,
            "extracted_report_url": f"/download-report/{extracted_report_filename}" if extracted_report_filename else None
        }
        logger.info(f"Sending response: {json.dumps(response, default=str)}")
        return jsonify(response)

@app.route("/download-report/<filename>")
@login_required
def download_report(filename):
    if current_user.job not in ["Employee", "Developer"]:
        return jsonify({"error": "Unauthorized access"}), 403
    report_path = os.path.join("./reports", filename)
    if os.path.exists(report_path):
        logger.info(f"Serving report file: {report_path}")
        return send_file(report_path, as_attachment=True, download_name=filename)
    else:
        logger.error(f"Report file not found: {report_path}")
        return jsonify({"error": "Report file not found"}), 404

@app.route("/stop-bot", methods=["POST"], endpoint="stop_bot_endpoint")
@login_required
@async_to_sync
async def stop_bot():
    if current_user.job not in ["Employee", "Developer"]:
        return jsonify({"error": "Unauthorized access"}), 403
    global _global_agent
    logger.info("Received /stop-bot request")
    try:
        if _global_agent:
            _global_agent.stop()
            logger.info("Bot stop requested")
            return jsonify({"message": "Bot stop requested"})
        logger.warning("No active bot to stop")
        return jsonify({"message": "No active bot to stop"}), 400
    except Exception as e:
        logger.error(f"Error stopping bot: {str(e)}")
        return jsonify({"error": str(e)}), 500


@app.route("/stop-bot", methods=["POST"], endpoint="stop_bot_endpoint")
@login_required
@async_to_sync
async def stop_bot():
    if current_user.job not in ["Employee", "Developer"]:
        return jsonify({"error": "Unauthorized access"}), 403
    global _global_agent
    logger.info("Received /stop-bot request")
    try:
        if _global_agent:
            _global_agent.stop()
            logger.info("Bot stop requested")
            return jsonify({"message": "Bot stop requested"})
        logger.warning("No active bot to stop")
        return jsonify({"message": "No active bot to stop"}), 400
    except Exception as e:
        logger.error(f"Error stopping bot: {str(e)}")
        return jsonify({"error": str(e)}), 500

# Selenium Code Generator
tokenizer = AutoTokenizer.from_pretrained(MODEL_PATH)
model = AutoModelForSeq2SeqLM.from_pretrained(MODEL_PATH)

if os.path.exists(WEIGHTS_FILE):
    with h5py.File(WEIGHTS_FILE, 'r') as f:
        for name, param in model.named_parameters():
            param.data = torch.tensor(f[name][:])
    logger.info(f"Loaded weights from {WEIGHTS_FILE}")
else:
    logger.warning(f"Weights file {WEIGHTS_FILE} not found. Using default model weights from {MODEL_PATH}.")

device = "cuda" if torch.cuda.is_available() else "cpu"
model.to(device)

@app.route('/developer')
@login_required
def developer_home():
    if current_user.job != "Developer":
        flash("Access restricted to Developers only!")
        return redirect(url_for('home'))
    return render_template('gensel.html')

@app.route('/generate_from_data', methods=['POST'])
@login_required
def generate_from_data():
    if current_user.job != "Developer":
        return jsonify({"error": "Unauthorized access"}), 403
    scenario = request.json.get('scenario')
    if not scenario:
        return jsonify({"error": "No scenario provided"}), 400
    feedback = load_feedback()
    for entry in feedback:
        if entry["Scenario"].strip() == scenario.strip():
            return jsonify({"generated_code": entry["RealPage"]})
    inputs = tokenizer(scenario, return_tensors="pt", padding=True, truncation=True, max_length=128).to(device)
    with torch.no_grad():
        output_ids = model.generate(inputs["input_ids"], max_length=128, num_beams=5, early_stopping=True)
    return jsonify({"generated_code": tokenizer.decode(output_ids[0], skip_special_tokens=True)})

@app.route('/generate_from_gemini', methods=['POST'])
@login_required
def generate_from_gemini():
    if current_user.job != "Developer":
        return jsonify({"error": "Unauthorized access"}), 403
    scenario = request.json.get('scenario')
    if not scenario:
        return jsonify({"error": "No scenario provided"}), 400
    payload = {"contents": [{"parts": [{"text": f"Generate Selenium Java code for: '{scenario}'"}]}]}
    response = requests.post(f"{GEMINI_API_URL}?key={GEMINI_API_KEY}", json=payload)
    return jsonify({"generated_code": response.json().get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text", "Error: No response")})

@app.route('/correct', methods=['POST'])
@login_required
def correct():
    if current_user.job != "Developer":
        return jsonify({"error": "Unauthorized access"}), 403
    data = request.json
    scenario, corrected_code = data.get('scenario'), data.get('corrected_code')
    if not scenario or not corrected_code:
        return jsonify({"error": "Scenario and corrected code are required"}), 400
    feedback = load_feedback()
    for entry in feedback:
        if entry["Scenario"].strip() == scenario.strip():
            entry["RealPage"] = corrected_code
            break
    else:
        feedback.append({"Scenario": scenario, "RealPage": corrected_code})
    save_feedback(feedback)
    return jsonify({"message": "Correction saved successfully"})

def load_feedback():
    if not os.path.exists(FEEDBACK_FILE):
        with open(FEEDBACK_FILE, 'w', encoding='utf-8') as f:
            json.dump([], f)
    try:
        with open(FEEDBACK_FILE, 'r', encoding='utf-8') as f:
            return json.load(f) or []
    except json.JSONDecodeError:
        return []

def save_feedback(data):
    with open(FEEDBACK_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4)

if __name__ == "__main__":
    for file in [USERS_DB, FEEDBACK_FILE]:
        if not os.path.exists(file):
            with open(file, 'w') as f:
                json.dump([] if file == FEEDBACK_FILE else {}, f)
            logger.info(f"Created empty {file}")
    app.run(debug=True, host="127.0.0.1", port=5003)