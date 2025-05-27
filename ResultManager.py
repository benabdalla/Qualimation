import json
import os


class ResultManager:
    RESULTS_DB = "results_database.json"

    @staticmethod
    def load_results():
        if os.path.exists(ResultManager.RESULTS_DB):
            with open(ResultManager.RESULTS_DB, 'r') as f:
                return json.load(f)
        return []

    @staticmethod
    def save_results(results):
        with open(ResultManager.RESULTS_DB, 'w') as f:
            json.dump(results, f, indent=4)

    @staticmethod
    def get_stats(results):
        total = len(results)
        passed = sum(1 for r in results if r['status'] == 'PASSED')
        failed = sum(1 for r in results if r['status'] == 'FAILED')
        cancelled = total - passed - failed
        return {
            'passed': passed,
            'failed': failed,
            'cancelled': cancelled,
            'passed_pct': (passed / total * 100) if total else 0,
            'failed_pct': (failed / total * 100) if total else 0,
            'cancelled_pct': (cancelled / total * 100) if total else 0
        }
