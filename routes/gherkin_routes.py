from flask import Blueprint, render_template, session

gherkin_bp = Blueprint('gherkin', __name__)

@gherkin_bp.route('/gherkin', methods=['GET', 'POST'])
def gherkin():
    form_data = {
        "test_key": "",
        "task": "",
        "url": "",
        "add_infos": "",
        "max_steps": 100,
        "headless": True,
        "use_vision": True
    }
    prefilled_task = "Navigate to Google"
    task_running = False

    return render_template(
        'GherkinBot.html',
        form_data=form_data,
        prefilled_task=prefilled_task,
        task_running=task_running,
        user=session.get('user', {"id": "mootez"})
    )
