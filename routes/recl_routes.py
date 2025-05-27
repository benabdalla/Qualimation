import json

from flask import Blueprint, request, session, redirect, url_for, render_template

from config_app.task_manager import run_task
from testCases.Client import TestCaseReclmationClient
from testCases.Client.TestCaseReclmationClient import TestCaseReclamationClient

recl_bp = Blueprint("recl", __name__)


@recl_bp.route('/run_test/<string:case_id>', methods=['GET', 'POST'])
def test_case(case_id):
    # Instanciation
    test_case_instance = TestCaseReclamationClient()
    test_case_mapping = {
        'CDT-3668': test_case_instance.CDT_3668,
        'CDT-3669': test_case_instance.CDT_3669,
        'CDT-3681': test_case_instance.CDT_3681,
        'CDT-3683': test_case_instance.CDT_3669,
        'CDT-3684': test_case_instance.CDT_3684,
        'CDT-3686': test_case_instance.CDT_3686,
        'CDT-3687': test_case_instance.CDT_3687,
        'CDT-3688': test_case_instance.CDT_3688,
        'CDT-3685': test_case_instance.CDT_3685,
        'CDT-3689': test_case_instance.CDT_3689,
    }
    test_case = test_case_mapping.get(case_id)
    if not test_case:
        return render_template('404.html', message=f"Test case '{case_id}' not found"), 404

    form_data = {
        "test_key": case_id,
        "task": test_case,
        "url": "",
        "add_infos": "",
        "max_steps": 100,
        "headless": False,
        "use_vision": True
    }

    try:
        run_task(case_id, form_data['task'], form_data['url'], form_data['add_infos'], 80000,
                 form_data['headless'], form_data['use_vision'], form_data['test_key'])
    except Exception as e:
        # Log error ici et afficher un message d'erreur friendly
        return render_template('error.html', message=str(e)), 500

    session['prefilled_task'] = case_id

    return redirect(url_for('recl.all_test_rec'))


@recl_bp.route('/all_test_rec', methods=['GET', 'POST'])
def all_test_rec():
    try:
        with open("results_database.json", "r", encoding="utf-8") as file:
            results = json.load(file)
    except (FileNotFoundError, json.JSONDecodeError):
        results = []  # ou un dict vide selon ta structure attendue

    form_data = {}
    prefilled_task = session.get('prefilled_task', "default value")

    # Exemple: extraire les statuts des tests depuis results pour passer au template
    task_statuses = {}
    for result in results:
        # Supposons que chaque 'result' a un champ 'case_id' et un champ 'status'
        case_id = result.get('task')
        status = result.get('status')
        if case_id and status:
            task_statuses[case_id] = status

    return render_template(
        'reclamation.html',
        form_data=form_data,
        prefilled_task=prefilled_task,
        results=results,
        task_statuses=task_statuses
    )
