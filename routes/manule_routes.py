from flask import Blueprint, render_template, session

import asyncio
import json
import uuid
from datetime import datetime
from threading import Thread
from zoneinfo import ZoneInfo

from flask import Blueprint
from flask import render_template, request, redirect, url_for, flash, session

from routes.auth_routes import login
from config_app.task_manager import running_tasks, load_results, save_results, execute_task, app
from routes.main_routes import manule, main

manule_bp = Blueprint('manule', __name__)
main_bp = Blueprint('main', __name__)


@manule_bp.route('/manule', methods=['POST'])
def manule():
    if 'user' not in session:
        return redirect(url_for('login'))
    task_id = session.get('current_task_id', None)
    task_running = task_id and running_tasks.get(task_id) == "running"

    if request.method == 'POST':
        if 'stop' in request.form:
            if task_id and running_tasks.get(task_id) == "running":
                running_tasks[task_id] = "cancelled"
                flash('Task cancellation requested.', 'info')
            return redirect(url_for('main'))
        if "login" in request.form:
            login()
        task = request.form.get('task', session.get('prefilled_task', ''))
        url = request.form.get('url', '')
        add_infos = request.form.get('add_infos', '')
        test_key = request.form.get('test_key', '')
        max_steps = request.form.get('max_steps', '100')
        headless = request.form.get('headless') == 'on'
        use_vision = request.form.get('use_vision') == 'on'
        file = request.files.get('task_file')

        # Handle file upload and override task if file is provided
        if file and file.filename:
            try:
                content = file.read().decode('utf-8')
                if file.filename.endswith('.json'):
                    data = json.loads(content)
                    task = data.get('task', content)
                else:
                    task = content.strip()
                flash('File uploaded successfully! Task updated.', 'success')
            except Exception as e:
                flash(f"Error reading file: {str(e)}", 'error')
                # Don’t return yet, let the form reload with the error

        # Store form data in session
        session['form_data'] = {
            'task': task,
            'url': url,
            'add_infos': add_infos,
            'test_key': test_key,
            'max_steps': max_steps,
            'headless': headless,
            'use_vision': use_vision
        }

        if 'start' in request.form or 'execute_module_task' in request.form:
            if not task:
                flash('Task is required!', 'error')
                return redirect(url_for('main'))

            try:
                max_steps = int(max_steps)
                session['form_data']['max_steps'] = max_steps
            except ValueError:
                flash('Max Steps must be a number!', 'error')
                return redirect(url_for('main'))

            task_id = str(uuid.uuid4())
            running_tasks[task_id] = "running"
            session['current_task_id'] = task_id

            def run_task(task_id, task, url, add_infos, max_steps, headless, use_vision, test_key):
                result = asyncio.run(
                    execute_task(task, url, add_infos, max_steps, headless, use_vision, test_key, task_id))
                with app.app_context():
                    if running_tasks.get(task_id) != "cancelled":
                        all_results = load_results()
                        all_results.append({
                            "task": task,
                            "status": result['status'],
                            "final_result": result['final_result'],
                            "timestamp": datetime.now(ZoneInfo("UTC")).isoformat()
                        })
                        save_results(all_results)
                    running_tasks.pop(task_id, None)
                    # session.pop('current_task_id', None)
                    # session.pop('prefilled_task', None)  # Clear prefilled task after execution

            Thread(target=run_task,
                   args=(task_id, task, url, add_infos, max_steps, headless, use_vision, test_key)).start()
            flash('Task started!', 'success')
        form_data = {
            "test_key": "",
            "task": "",
            "url": "",
            "add_infos": "",
            "max_steps": 100,
            "headless": False,
            "use_vision": True
        }
        prefilled_task = "Navigate to Google"  # ou vide
    return render_template(
            'GherkinBot.html',
            form_data=form_data,
            prefilled_task=prefilled_task,
            task_running=task_running,
            user={"id": "mootez"}  # ou le vrai user s’il y en a un
        )



