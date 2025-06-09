import getpass
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

from App import GEMINI_API_KEY
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

def load_results():
    if os.path.exists(RESULTS_DB):
        with open(RESULTS_DB, 'r') as f:
            return json.load(f)
    return []
def save_results(results):
    with open(RESULTS_DB, 'w') as f:
        json.dump(results, f, indent=4)
# User management
def load_users():
    if not os.path.exists(USERS_DB):
        default_users = {"admin": {"password": generate_password_hash("admin123"), "job": "Developer"}}
        with open(USERS_DB, 'w') as f:
            json.dump(default_users, f, indent=4)
        return default_users
    with open(USERS_DB, 'r') as f:
        return json.load(f)
def save_users(users):
    with open(USERS_DB, 'w') as f:
        json.dump(users, f, indent=4)
def run_task(task_id, task, url, add_infos, max_steps, headless, use_vision, test_key):
    result = asyncio.run(execute_task(task, url, add_infos, max_steps, headless, use_vision, test_key, task_id))
    with app.app_context():
        if running_tasks.get(task_id) != "cancelled":
            all_results = load_results()
            all_results.append({
                "task": task_id,
                "status": result['status'],
                "final_result": result['final_result'],
                "timestamp": datetime.now(ZoneInfo("UTC")).isoformat()
            })

            start_time = datetime.now(ZoneInfo("UTC")).isoformat()
            finish_time = datetime.now(ZoneInfo("UTC")).isoformat()
            status = result['status']
            comment = "Test run automatically via AI agent."

            # création du JSON format Xray avec variables
            xray_result = {
                "testExecutionKey": "CDT-6272",
                "tests": [
                         {
                   "testKey": task_id,
                    "start": start_time,
                    "finish": finish_time,
                    "comment": comment,
                    "status": status
                          }
                          ]
                }
            token = get_auth_token()
            import_test_results_json(token,xray_result)
            # import_test_results_json_cucumber(token, xray_result)
            save_results(all_results)
        running_tasks.pop(task_id, None)
        return result['status'];
        # session.pop('current_task_id', None)
        # session.pop('prefilled_task', None)  # Clear prefilled task after execution
async def execute_task(task, url, add_infos, max_steps, headless, use_vision, test_key, task_id):
    errors = []
    final_result = "No result"
    extracted_from_page = None
    start_time = datetime.now(ZoneInfo("UTC")).isoformat()
    logger.info(f"Executing task: {task}, URL: {url}, Max Steps: {max_steps}, Task ID: {task_id}")
    try:

        llm = ChatGoogleGenerativeAI(model="gemini-1.5-flash", api_key=SecretStr(GEMINI_API_KEY))
        browser_config = BrowserConfig(
            headless=headless, disable_security=DEFAULT_CONFIG["disable_security"],
            extra_chromium_args=[f"--window-size={DEFAULT_CONFIG['window_w']},{DEFAULT_CONFIG['window_h']}"]
        )
        context_config = BrowserContextConfig(
            trace_path=DEFAULT_CONFIG["save_trace_path"], save_recording_path=DEFAULT_CONFIG["save_recording_path"],
            no_viewport=False, browser_window_size=BrowserContextWindowSize(
                width=DEFAULT_CONFIG["window_w"], height=DEFAULT_CONFIG["window_h"])
        )
        os.makedirs(DEFAULT_CONFIG["save_recording_path"], exist_ok=True)
        os.makedirs(DEFAULT_CONFIG["save_trace_path"], exist_ok=True)
        os.makedirs("./reports", exist_ok=True)
        browser = Browser(config=browser_config)
        browser_context = await browser.new_context(config=context_config)
        if url:
            task = f"Start at {url} and {task}"
        if add_infos:
            task = f"{task} Additional info: {add_infos}"

        agent = Agent(
            task=task, llm=llm, use_vision=use_vision, browser=browser,
            browser_context=browser_context, max_actions_per_step=5
        )
        history = await agent.run(max_steps=max_steps)
        finish_time = datetime.now(ZoneInfo("UTC")).isoformat()

        if running_tasks.get(task_id) == "cancelled":
            final_result = "Task cancelled by user"
            overall_status = "CANCELLED"
        else:
            final_result = history.final_result() if history and history.final_result() else "No result"
            errors = [e for e in (history.errors() if history else []) if e is not None]
            for action_result in history.action_results():
                if action_result.extracted_content and "Extracted from page" in action_result.extracted_content:
                    extracted_from_page = action_result.extracted_content
                    break
            if final_result and extracted_from_page:
                final_result = f"{extracted_from_page}\n{final_result}"
            elif extracted_from_page and not final_result:
                final_result = extracted_from_page

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            xray_report_filename = f"xray_report_{timestamp}.json"
            agent_report_filename = f"agent_report_{timestamp}.json"
            extracted_report_filename = f"extracted_report_{timestamp}.json" if extracted_from_page else None

            overall_status = "FAILED"
            if history and history.history and history.history[-1].model_output and history.history[
                -1].model_output.action:
                last_action = history.history[-1].model_output.action[0]
                action_json = json.loads(last_action.model_dump_json(exclude_unset=True))
                if (action_json.get("done") and

                        "success" in action_json["done"] and action_json["done"]["success"]):
                    overall_status = "PASSED"
            test_key = test_key if test_key else "QUALI-456"
            xray_report = {
                "tests": [{
                    "testKey": test_key,
                    "start": start_time,
                    "finish": finish_time,
                    "status": overall_status
                }]
            }
            agent_report = {
                "task": task,
                "url": url,
                "add_infos": add_infos,
                "final_result": final_result,
                "status": overall_status,
                "errors": errors
            }
            xray_path = os.path.join("./reports", xray_report_filename)
            agent_path = os.path.join("./reports", agent_report_filename)
            extracted_path = os.path.join("./reports", extracted_report_filename) if extracted_from_page else None

            with open(xray_path, "w") as f:
                json.dump(xray_report, f, indent=4)
            with open(agent_path, "w") as f:
                json.dump(agent_report, f, indent=4)
            if extracted_from_page:
                with open(extracted_path, "w") as f:
                    json.dump({"extracted": extracted_from_page}, f, indent=4)

        return {
            "final_result": final_result,
            "extracted_from_page": extracted_from_page,
            "errors": errors,
            "status": overall_status,
            "xray_report_path": xray_path if overall_status != "CANCELLED" else None,
            "agent_report_path": agent_path if overall_status != "CANCELLED" else None,
            "extracted_report_path": extracted_path if overall_status != "CANCELLED" else None
        }
    except Exception as e:
        logger.error(f"Task execution failed: {str(e)}", exc_info=True)
        errors.append(str(e))
        return {
            "final_result": final_result,
            "errors": errors,
            "status": "FAILED",
            "xray_report_path": None,
            "agent_report_path": None,
            "extracted_report_path": None
        }
    finally:
        if 'browser_context' in locals():
            await browser_context.close()
        if 'browser' in locals():
            await browser.close()
def get_latest_status_by_task():
    with open('results_database.json', encoding='utf-8') as f:
        data = json.load(f)

    status_by_task = {}
    for entry in sorted(data, key=lambda x: x["timestamp"], reverse=True):
        task = entry["task"]
        if task not in status_by_task:
            status_by_task[task] = entry["status"]
    return status_by_task