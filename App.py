import os
import json
import asyncio
import logging
from datetime import datetime
from zoneinfo import ZoneInfo
from flask import Flask, render_template, request, redirect, url_for, flash, send_file, jsonify, session
from sympy import false, true
from werkzeug.security import generate_password_hash, check_password_hash
from dotenv import load_dotenv
from Xray import get_auth_token, import_test_results, import_test_results_json, import_test_results_json_cucumber
from config_app.agent.service import Agent
from config_app.browser.browser import Browser, BrowserConfig
from config_app.browser.context import BrowserContextConfig, BrowserContextWindowSize
from langchain_google_genai import ChatGoogleGenerativeAI
from pydantic import SecretStr
from threading import Thread
import uuid
from testCases.Client import TestCaseReclmationClient


# Load environment variables
load_dotenv()


app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "your-secret-key")  # Set a secure secret key in .env
# Constants
USERS_DB = "users.json"
RESULTS_DB = "results_database.json"
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY") or "YOUR_GEMINI_API_KEY"
DEFAULT_CONFIG = {
    "headless": True, "disable_security": False, "window_w": 1280, "window_h": 720,
    "max_steps": 100, "save_recording_path": "./recordings", "save_trace_path": "./traces"
}
# Logging setup
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
# Task management
running_tasks = {}  # Dictionary to track running tasks: {task_id: status}
# Load/save results

# def load_results():
#     if os.path.exists(RESULTS_DB):
#         with open(RESULTS_DB, 'r') as f:
#             return json.load(f)
#     return []
# def save_results(results):
#     with open(RESULTS_DB, 'w') as f:
#         json.dump(results, f, indent=4)
# # User management
# def load_users():
#     if not os.path.exists(USERS_DB):
#         default_users = {"admin": {"password": generate_password_hash("admin123"), "job": "Developer"}}
#         with open(USERS_DB, 'w') as f:
#             json.dump(default_users, f, indent=4)
#         return default_users
#     with open(USERS_DB, 'r') as f:
#         return json.load(f)
# def save_users(users):
#     with open(USERS_DB, 'w') as f:
#         json.dump(users, f, indent=4)
# # Routes
# @app.route('/')
# def welcome():
#     login()
#     return render_template('welcome.html')
# @app.route('/manule', methods=['GET', 'POST'])
# def manule():
#     # Tu peux adapter ce form_data selon tes besoins
#     form_data = {
#         "test_key": "",
#         "task": "",
#         "url": "",
#         "add_infos": "",
#         "max_steps": 100,
#         "headless": False,
#         "use_vision": True
#     }
#     prefilled_task = "Navigate to Google"  # ou vide
#     task_running = False  # à définir selon ton contexte
#     if request.method == 'POST':
#         main()
#     return (render_template(
#         'main.html',
#         form_data=form_data,
#         prefilled_task=prefilled_task,
#         task_running=task_running,
#         user={"id": "mootez"}  # ou le vrai user s’il y en a un
#     ))
# @app.route('/gherkin', methods=['GET', 'POST'])
# def gherkin():
#     # Tu peux adapter ce form_data selon tes besoins
#     form_data = {
#         "test_key": "",
#         "task": "",
#         "url": "",
#         "add_infos": "",
#         "max_steps": 100,
#         "headless": True,
#         "use_vision": True
#     }
#     prefilled_task = "Navigate to Google"  # ou vide
#     task_running = False  # à définir selon ton contexte
#
#     return render_template(
#         'GherkinBot.html',
#         form_data=form_data,
#         prefilled_task=prefilled_task,
#         task_running=task_running,
#         user={"id": "mootez"}  # ou le vrai user s’il y en a un
#     )
# @app.route('/login', methods=['GET', 'POST'])
# def login():
#     if request.method == 'POST':
#         username = request.form['username']
#         password = request.form['password']
#         users = load_users()
#         if username in users and check_password_hash(users[username]['password'], password):
#             session['user'] = {'id': username, 'job': users[username]['job']}
#             return redirect(url_for('main'))
#         flash('Invalid username or password!', 'error')
#     return render_template('wel'
#                            'come.html')
# @app.route('/register', methods=['GET', 'POST'])
# def register():
#     if request.method == 'POST':
#         username = request.form['username']
#         password = request.form['password']
#         users = load_users()
#         if username in users:
#             flash('Username already exists!', 'error')
#         elif not username or not password:
#             flash('All fields are required!', 'error')
#         else:
#             users[username] = {"password": generate_password_hash(password), "job": "User"}
#             save_users(users)
#             flash('Registration successful! Please log in.', 'success')
#             return redirect(url_for('login'))
#     return render_template('register.html')
# @app.route('/logout')
# def logout():
#     session.pop('user', None)
#     return redirect(url_for('login'))
# @app.route('/main', methods=['GET', 'POST'])
# def main():
#     if 'user' not in session:
#         return redirect(url_for('login'))
#     task_id = session.get('current_task_id', None)
#     task_running = task_id and running_tasks.get(task_id) == "running"
#
#     if request.method == 'POST':
#         if 'stop' in request.form:
#             if task_id and running_tasks.get(task_id) == "running":
#                 running_tasks[task_id] = "cancelled"
#                 flash('Task cancellation requested.', 'info')
#             return redirect(url_for('main'))
#         if "login" in request.form:
#             login()
#         task = request.form.get('task', session.get('prefilled_task', ''))
#         url = request.form.get('url', '')
#         add_infos = request.form.get('add_infos', '')
#         test_key = request.form.get('test_key', '')
#         max_steps = request.form.get('max_steps', '100')
#         headless = request.form.get('headless') == 'on'
#         use_vision = request.form.get('use_vision') == 'on'
#         file = request.files.get('task_file')
#
#         # Handle file upload and override task if file is provided
#         if file and file.filename:
#             try:
#                 content = file.read().decode('utf-8')
#                 if file.filename.endswith('.json'):
#                     data = json.loads(content)
#                     task = data.get('task', content)
#                 else:
#                     task = content.strip()
#                 flash('File uploaded successfully! Task updated.', 'success')
#             except Exception as e:
#                 flash(f"Error reading file: {str(e)}", 'error')
#                 # Don’t return yet, let the form reload with the error
#
#         # Store form data in session
#         session['form_data'] = {
#             'task': task,
#             'url': url,
#             'add_infos': add_infos,
#             'test_key': test_key,
#             'max_steps': max_steps,
#             'headless': headless,
#             'use_vision': use_vision
#         }
#
#         if 'start' in request.form or 'execute_module_task' in request.form:
#             if not task:
#                 flash('Task is required!', 'error')
#                 return redirect(url_for('main'))
#
#             try:
#                 max_steps = int(max_steps)
#                 session['form_data']['max_steps'] = max_steps
#             except ValueError:
#                 flash('Max Steps must be a number!', 'error')
#                 return redirect(url_for('main'))
#
#             task_id = str(uuid.uuid4())
#             running_tasks[task_id] = "running"
#             session['current_task_id'] = task_id
#
#             def run_task(task_id, task, url, add_infos, max_steps, headless, use_vision, test_key):
#                 result = asyncio.run(
#                     execute_task(task, url, add_infos, max_steps, headless, use_vision, test_key, task_id))
#                 with app.app_context():
#                     if running_tasks.get(task_id) != "cancelled":
#                         all_results = load_results()
#                         all_results.append({
#                             "task": task,
#                             "status": result['status'],
#                             "final_result": result['final_result'],
#                             "timestamp": datetime.now(ZoneInfo("UTC")).isoformat()
#                         })
#                         save_results(all_results)
#                     running_tasks.pop(task_id, None)
#                     # session.pop('current_task_id', None)
#                     # session.pop('prefilled_task', None)  # Clear prefilled task after execution
#
#             Thread(target=run_task,
#                    args=(task_id, task, url, add_infos, max_steps, headless, use_vision, test_key)).start()
#             flash('Task started!', 'success')
#         return redirect(url_for('main'))
#
#     form_data = session.get('form_data', {})
#     prefilled_task = session.get('prefilled_task', '')
#     return render_template('qualimationChoise.html', user=session['user'], task_running=task_running,
#                            form_data=form_data, prefilled_task=prefilled_task)
# @app.route('/results', methods=['GET', 'POST'])
# def results():
#     if 'user' not in session:
#         return redirect(url_for('login'))
#
#     all_results = load_results()
#
#     if request.method == 'POST' and 'delete' in request.form:
#         index = int(request.form['delete'])
#         if 0 <= index < len(all_results):
#             all_results.pop(index)
#             save_results(all_results)
#             flash('Result deleted successfully!', 'success')
#         return redirect(url_for('results'))
#
#     total = len(all_results)
#     passed = sum(1 for r in all_results if r['status'] == 'PASSED')
#     failed = sum(1 for r in all_results if r['status'] == 'FAILED')
#     cancelled = total - passed - failed
#     stats = {
#         'passed': passed,
#         'failed': failed,
#         'cancelled': cancelled,
#         'passed_pct': (passed / total * 100) if total > 0 else 0,
#         'failed_pct': (failed / total * 100) if total > 0 else 0,
#         'cancelled_pct': (cancelled / total * 100) if total > 0 else 0
#     }
#
#     return render_template('results.html', results=all_results, stats=stats)
# @app.route('/download/<report_type>/<int:result_index>')
# def download_report(report_type, result_index):
#     if 'user' not in session:
#         return redirect(url_for('login'))
#     all_results = load_results()
#     if result_index < len(all_results):
#         result = all_results[result_index]
#         paths = {
#             'xray': result.get('xray_report_path'),
#             'extracted': result.get('extracted_report_path')
#         }
#         path = paths.get(report_type)
#         if path and os.path.exists(path):
#             return send_file(path, as_attachment=True)
#     flash('Report not found!', 'error')
#     return redirect(url_for('results'))
# @app.route('/modules')
# def modules():
#     form_data = {}  # ou charge les vraies données ici
#     prefilled_task = "default value"
#     return render_template('modules.html', form_data=form_data, prefilled_task=prefilled_task)
#
# @app.route('/run_test<string:case_id>')
# def test_case(case_id):
#     test_case_mapping = {
#         'CDT-3669': TestCaseReclmationClient.CDT_3669,
#         'CDT-3681': TestCaseReclmationClient.CDT_3681,
#     }
#     case_id = request.args.get('case_id')
#     test_case = test_case_mapping.get(case_id)
#     if not test_case:
#         return f"Test case '{case_id}' not found", 404
#
#     form_data = {
#         "test_key": case_id,
#         "task": test_case,
#         "url": "",
#         "add_infos": "",
#         "max_steps": 100,
#         "headless": False,
#         "use_vision": True
#     }
#
#     run_task(case_id, form_data.get('task'), form_data.get('url'), form_data.get('add_infos'), 80000,
#              form_data.get('headless'), form_data.get('use_vision'), form_data.get('test_key'))
#     session['prefilled_task'] = ""
#     return redirect(url_for('all_test_rec'))
#
#     run_task(case_id, form_data.get('task'), form_data.get('url'), form_data.get('add_infos'), 80000,
#              form_data.get('headless'), form_data.get('use_vision'), form_data.get('test_key'))
#     session['prefilled_task'] = ""
#     return redirect(url_for('all_test_rec'))
#
#
# @app.route('/all_test_rec',methods=['GET', 'POST'])
# def all_test_rec():
#     with open("results_database.json", "r", encoding="utf-8") as file:
#         results = json.load(file)
#     form_data = {}
#     prefilled_task = "default value"
#     return render_template(
#         'reclamation.html',
#         form_data=form_data,
#         prefilled_task=prefilled_task,
#         results=results  # ← ✅ AJOUT ICI
#     )
#
#
# def run_task(task_id, task, url, add_infos, max_steps, headless, use_vision, test_key):
#     result = asyncio.run(execute_task(task, url, add_infos, max_steps, headless, use_vision, test_key, task_id))
#     with app.app_context():
#         if running_tasks.get(task_id) != "cancelled":
#             all_results = load_results()
#             all_results.append({
#                 "task": task_id,
#                 "status": result['status'],
#                 "final_result": result['final_result'],
#                 "timestamp": datetime.now(ZoneInfo("UTC")).isoformat()
#             })
#
#             start_time = datetime.now(ZoneInfo("UTC")).isoformat()
#             finish_time = datetime.now(ZoneInfo("UTC")).isoformat()
#             status = result['status']
#             comment = "Test run automatically via AI agent."
#
#             # création du JSON format Xray avec variables
#             xray_result = {
#                 "testExecutionKey": "CDT-6272",
#                 "tests": [
#                          {
#                    "testKey": task_id,
#                     "start": start_time,
#                     "finish": finish_time,
#                     "comment": comment,
#                     "status": status
#                           }
#                           ]
#                 }
#             token = get_auth_token()
#             import_test_results_json(token,xray_result)
#             # import_test_results_json_cucumber(token, xray_result)
#             save_results(all_results)
#         running_tasks.pop(task_id, None)
#         return result['status'];
#         # session.pop('current_task_id', None)
#         # session.pop('prefilled_task', None)  # Clear prefilled task after execution
#
# async def execute_task(task, url, add_infos, max_steps, headless, use_vision, test_key, task_id):
#     errors = []
#     final_result = "No result"
#     extracted_from_page = None
#     start_time = datetime.now(ZoneInfo("UTC")).isoformat()
#     logger.info(f"Executing task: {task}, URL: {url}, Max Steps: {max_steps}, Task ID: {task_id}")
#     try:
#
#         llm = ChatGoogleGenerativeAI(model="gemini-1.5-flash", api_key=SecretStr(GEMINI_API_KEY))
#         browser_config = BrowserConfig(
#             headless=headless, disable_security=DEFAULT_CONFIG["disable_security"],
#             extra_chromium_args=[f"--window-size={DEFAULT_CONFIG['window_w']},{DEFAULT_CONFIG['window_h']}"]
#         )
#         context_config = BrowserContextConfig(
#             trace_path=DEFAULT_CONFIG["save_trace_path"], save_recording_path=DEFAULT_CONFIG["save_recording_path"],
#             no_viewport=False, browser_window_size=BrowserContextWindowSize(
#                 width=DEFAULT_CONFIG["window_w"], height=DEFAULT_CONFIG["window_h"])
#         )
#         os.makedirs(DEFAULT_CONFIG["save_recording_path"], exist_ok=True)
#         os.makedirs(DEFAULT_CONFIG["save_trace_path"], exist_ok=True)
#         os.makedirs("./reports", exist_ok=True)
#         browser = Browser(config=browser_config)
#         browser_context = await browser.new_context(config=context_config)
#         if url:
#             task = f"Start at {url} and {task}"
#         if add_infos:
#             task = f"{task} Additional info: {add_infos}"
#
#         agent = Agent(
#             task=task, llm=llm, use_vision=use_vision, browser=browser,
#             browser_context=browser_context, max_actions_per_step=5
#         )
#         history = await agent.run(max_steps=max_steps)
#         finish_time = datetime.now(ZoneInfo("UTC")).isoformat()
#
#         if running_tasks.get(task_id) == "cancelled":
#             final_result = "Task cancelled by user"
#             overall_status = "CANCELLED"
#         else:
#             final_result = history.final_result() if history and history.final_result() else "No result"
#             errors = [e for e in (history.errors() if history else []) if e is not None]
#             for action_result in history.action_results():
#                 if action_result.extracted_content and "Extracted from page" in action_result.extracted_content:
#                     extracted_from_page = action_result.extracted_content
#                     break
#             if final_result and extracted_from_page:
#                 final_result = f"{extracted_from_page}\n{final_result}"
#             elif extracted_from_page and not final_result:
#                 final_result = extracted_from_page
#
#             timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
#             xray_report_filename = f"xray_report_{timestamp}.json"
#             agent_report_filename = f"agent_report_{timestamp}.json"
#             extracted_report_filename = f"extracted_report_{timestamp}.json" if extracted_from_page else None
#
#             overall_status = "FAILED"
#             if history and history.history and history.history[-1].model_output and history.history[
#                 -1].model_output.action:
#                 last_action = history.history[-1].model_output.action[0]
#                 action_json = json.loads(last_action.model_dump_json(exclude_unset=True))
#                 if (action_json.get("done") and
#
#                         "success" in action_json["done"] and action_json["done"]["success"]):
#                     overall_status = "PASSED"
#             test_key = test_key if test_key else "QUALI-456"
#             xray_report = {
#                 "tests": [{
#                     "testKey": test_key,
#                     "start": start_time,
#                     "finish": finish_time,
#                     "status": overall_status
#                 }]
#             }
#             agent_report = {
#                 "task": task,
#                 "url": url,
#                 "add_infos": add_infos,
#                 "final_result": final_result,
#                 "status": overall_status,
#                 "errors": errors
#             }
#             xray_path = os.path.join("./reports", xray_report_filename)
#             agent_path = os.path.join("./reports", agent_report_filename)
#             extracted_path = os.path.join("./reports", extracted_report_filename) if extracted_from_page else None
#
#             with open(xray_path, "w") as f:
#                 json.dump(xray_report, f, indent=4)
#             with open(agent_path, "w") as f:
#                 json.dump(agent_report, f, indent=4)
#             if extracted_from_page:
#                 with open(extracted_path, "w") as f:
#                     json.dump({"extracted": extracted_from_page}, f, indent=4)
#
#         return {
#             "final_result": final_result,
#             "extracted_from_page": extracted_from_page,
#             "errors": errors,
#             "status": overall_status,
#             "xray_report_path": xray_path if overall_status != "CANCELLED" else None,
#             "agent_report_path": agent_path if overall_status != "CANCELLED" else None,
#             "extracted_report_path": extracted_path if overall_status != "CANCELLED" else None
#         }
#     except Exception as e:
#         logger.error(f"Task execution failed: {str(e)}", exc_info=True)
#         errors.append(str(e))
#         return {
#             "final_result": final_result,
#             "errors": errors,
#             "status": "FAILED",
#             "xray_report_path": None,
#             "agent_report_path": None,
#             "extracted_report_path": None
#         }
#     finally:
#         if 'browser_context' in locals():
#             await browser_context.close()
#         if 'browser' in locals():
#             await browser.close()
#
# if __name__ == '__main__':
#     app.run(debug=false, host='0.0.0.0', port=5000)
