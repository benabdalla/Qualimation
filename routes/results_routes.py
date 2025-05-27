import os

from flask import Blueprint, session, render_template, redirect, request, flash, url_for, send_file
from config_app.task_manager import load_results, save_results
from config_app.task_manager import load_results, save_results

results_bp = Blueprint("results", __name__)

@results_bp.route('/results', methods=['GET', 'POST'])
def results():
    if 'user' not in session:
        return redirect(url_for('login'))

    all_results = load_results()

    if request.method == 'POST' and 'delete' in request.form:
        index = int(request.form['delete'])
        if 0 <= index < len(all_results):
            all_results.pop(index)
            save_results(all_results)
            flash('Result deleted successfully!', 'success')
        return redirect(url_for('results'))

    total = len(all_results)
    passed = sum(1 for r in all_results if r['status'] == 'PASSED')
    failed = sum(1 for r in all_results if r['status'] == 'FAILED')
    cancelled = total - passed - failed
    stats = {
        'passed': passed,
        'failed': failed,
        'cancelled': cancelled,
        'passed_pct': (passed / total * 100) if total > 0 else 0,
        'failed_pct': (failed / total * 100) if total > 0 else 0,
        'cancelled_pct': (cancelled / total * 100) if total > 0 else 0
    }

    return render_template('results.html', results=all_results, stats=stats)

@results_bp.route('/download/<report_type>/<int:result_index>')
def download_report(report_type, result_index):
    if 'user' not in session:
        return redirect(url_for('login'))
    all_results = load_results()
    if result_index < len(all_results):
        result = all_results[result_index]
        paths = {
            'xray': result.get('xray_report_path'),
            'extracted': result.get('extracted_report_path')
        }
        path = paths.get(report_type)
        if path and os.path.exists(path):
            return send_file(path, as_attachment=True)
    flash('Report not found!', 'error')
    return redirect(url_for('results'))
