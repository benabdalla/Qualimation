import sys
import json
import os
import time
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
                             QPushButton, QMessageBox, QTextEdit, QFrame, QFileDialog, QStackedWidget, QCheckBox,
                             QScrollArea, QDialog)
from PyQt6.QtCore import (QThread, pyqtSignal, Qt, QPropertyAnimation, QEasingCurve, QRect, QTimer, pyqtProperty)
from PyQt6.QtGui import (QPixmap, QBrush, QPalette, QPainter, QColor, QLinearGradient, QIcon)
from werkzeug.security import generate_password_hash, check_password_hash
import asyncio
import logging
from datetime import datetime
from config_app.agent.service import Agent
from config_app.browser.browser import Browser, BrowserConfig
from config_app.browser.context import BrowserContextConfig, BrowserContextWindowSize
from langchain_google_genai import ChatGoogleGenerativeAI
from pydantic import SecretStr
from dotenv import load_dotenv
import matplotlib.pyplot as plt
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
import speech_recognition as sr
import numpy as np

# Load environment variables
load_dotenv()


# Custom logging formatter with colors
class ColoredFormatter(logging.Formatter):
    GREEN = '\033[92m'
    RED = '\033[91m'
    RESET = '\033[0m'
    BOLD = '\033[1m'

    def format(self, record):
        msg = super().format(record)
        if "✅ Successfully" in msg or "📄 Result" in msg or "✅ Task completed" in msg:
            if "All steps completed successfully" in msg or "✅ Successfully" in msg:
                return f"{self.GREEN}{self.BOLD}{msg}{self.RESET}"
            return f"{self.GREEN}{msg}{self.RESET}"
        elif "controller" in record.name and ("🔗" in msg or "⌨️" in msg or "🖱️" in msg):
            if "Failed" not in msg:
                return f"{self.GREEN}{msg}{self.RESET}"
            else:
                return f"{self.RED}{msg}{self.RESET}"
        elif "Error" in msg or "FAILED" in msg:
            return f"{self.RED}{self.BOLD}{msg}{self.RESET}"
        return msg


handler = logging.StreamHandler(sys.stdout)
handler.setFormatter(ColoredFormatter("%(asctime)s %(levelname)-8s [%(name)s] %(message)s"))
logging.basicConfig(level=logging.INFO, handlers=[handler])
logger = logging.getLogger(__name__)

# Constants
DEFAULT_CONFIG = {
    "headless": True, "disable_security": False, "window_w": 1280, "window_h": 720,
    "max_steps": 100, "save_recording_path": "./recordings", "save_trace_path": "./traces"
}
USERS_DB = "users.json"
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY") or "YOUR_GEMINI_API_KEY"
JIRA_URL = os.getenv("JIRA_URL") or "https://your-jira-instance"
JIRA_API_TOKEN = os.getenv("JIRA_API_TOKEN") or "YOUR_JIRA_API_TOKEN"
BACKGROUND_IMAGE_PATH = r"C:\Users\raefet.jlidi\PycharmProjects\LastBot\static\back.png"
LOGO_PATH = r"C:\Users\raefet.jlidi\PycharmProjects\LastBot\static\sd.png"
CHAT_LOGO_PATH = r"C:\Users\raefet.jlidi\PycharmProjects\DesktopAppBot\8943377.png"


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


class User:
    def __init__(self, username, job):
        self.id = username
        self.job = job


class ResultsWindow(QMainWindow):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Execution Results")
        self.pass_count = 0
        self.fail_count = 0
        self.results_data = []
        self.initUI()

    def initUI(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)
        layout.setContentsMargins(20, 20, 20, 20)
        self.result_display = QTextEdit()
        self.result_display.setReadOnly(True)
        self.result_display.setStyleSheet("""
            QTextEdit {
                background-color: rgba(245, 246, 250, 0.8);
                border: 2px solid #42A5F5;
                border-radius: 10px;
                padding: 15px;
                font-size: 16px;
            }
        """)
        layout.addWidget(self.result_display)

        button_layout = QHBoxLayout()
        self.show_graph_button = QPushButton("Show Detailed Report")
        self.show_graph_button.setStyleSheet("""
            QPushButton {
                background: qlineargradient(spread:pad, x1:0, y1:0, x2:1, y2:1, stop:0 #AB47BC, stop:1 #7B1FA2);
                color: white;
                border-radius: 12px;
                padding: 15px 25px;
                font-size: 18px;
                font-weight: bold;
            }
            QPushButton:hover {
                background: qlineargradient(spread:pad, x1:0, y1:0, x2:1, y2:1, stop:0 #BA68C8, stop:1 #8E24AA);
            }
            QPushButton:pressed {
                background: qlineargradient(spread:pad, x1:0, y1:0, x2:1, y2:1, stop:0 #9C27B0, stop:1 #6A1B9A);
            }
        """)
        self.show_graph_button.clicked.connect(self.show_graph)
        self.show_graph_button.setEnabled(False)
        button_layout.addWidget(self.show_graph_button)

        self.close_button = QPushButton("Close")
        self.close_button.setStyleSheet("""
            QPushButton {
                background: qlineargradient(spread:pad, x1:0, y1:0, x2:1, y2:1, stop:0 #FF9800, stop:1 #F57C00);
                color: white;
                border-radius: 12px;
                padding: 15px 25px;
                font-size: 18px;
                font-weight: bold;
            }
            QPushButton:hover {
                background: qlineargradient(spread:pad, x1:0, y1:0, x2:1, y2:1, stop:0 #FFB300, stop:1 #FB8C00);
            }
            QPushButton:pressed {
                background: qlineargradient(spread:pad, x1:0, y1:0, x2:1, y2:1, stop:0 #F57C00, stop:1 #EF6C00);
            }
        """)
        self.close_button.clicked.connect(self.hide)
        button_layout.addWidget(self.close_button)

        layout.addLayout(button_layout)

    def append_result(self, text, success=None, duration=None):
        if success is True:
            status = "PASSED"
            self.result_display.append(f'<span style="color: green; font-weight: bold;">{status}: {text}</span>' +
                                       (f' [Duration: {duration:.2f}s]' if duration else ''))
            self.pass_count += 1
            self.results_data.append({"status": "PASSED", "text": text, "duration": duration})
        elif success is False:
            status = "FAILED"
            self.result_display.append(f'<span style="color: red; font-weight: bold;">{status}: {text}</span>' +
                                       (f' [Duration: {duration:.2f}s]' if duration else ''))
            self.fail_count += 1
            self.results_data.append({"status": "FAILED", "text": text, "duration": duration})
        else:
            self.result_display.append(f'<span style="color: black">{text}</span>' +
                                       (f' [Duration: {duration:.2f}s]' if duration else ''))
            self.results_data.append({"status": "INFO", "text": text, "duration": duration})
        self.result_display.ensureCursorVisible()

    def show_graph(self):
        if not self.results_data:
            QMessageBox.information(self, "Info", "No results to display.")
            return

        graph_window = QWidget()
        graph_window.setWindowTitle("Execution Report")
        layout = QVBoxLayout(graph_window)
        layout.setContentsMargins(20, 20, 20, 20)

        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5))
        fig.suptitle("Execution Summary")
        labels = ['Passed', 'Failed']
        sizes = [self.pass_count, self.fail_count]
        colors = ['#4CAF50', '#F44336']
        ax1.pie(sizes, labels=labels, colors=colors, autopct='%1.1f%%', startangle=90)
        ax1.axis('equal')
        ax1.set_title("Pass/Fail Ratio")
        ax2.bar(['Passed', 'Failed'], [self.pass_count, self.fail_count], color=colors)
        ax2.set_title("Pass/Fail Count")
        ax2.set_ylabel("Number of Steps")
        plt.tight_layout()

        canvas = FigureCanvas(fig)
        layout.addWidget(canvas)

        table_label = QLabel("Detailed Results:")
        table_label.setStyleSheet("font-weight: bold; font-size: 18px;")
        layout.addWidget(table_label)

        results_table = QTextEdit()
        results_table.setReadOnly(True)
        results_table.setStyleSheet("""
            QTextEdit {
                background-color: rgba(245, 246, 250, 0.8);
                border: 2px solid #42A5F5;
                border-radius: 10px;
                padding: 15px;
                font-size: 16px;
            }
        """)
        html = """
        <style>
            table { border-collapse: collapse; width: 100%; }
            th, td { padding: 10px; text-align: left; border-bottom: 1px solid #ddd; }
            th { background-color: #42A5F5; color: white; }
            .passed { color: #4CAF50; font-weight: bold; }
            .failed { color: #F44336; font-weight: bold; }
            .info { color: #2196F3; }
        </style>
        <table>
            <tr><th>Status</th><th>Details</th><th>Duration (s)</th></tr>
        """
        for result in self.results_data:
            status_class = result["status"].lower()
            duration = result["duration"] if result["duration"] is not None else "N/A"
            html += f"<tr><td class='{status_class}'>{result['status']}</td><td>{result['text']}</td><td>{duration}</td></tr>"
        html += "</table>"
        results_table.setHtml(html)
        layout.addWidget(results_table)

        graph_window.showFullScreen()


class TaskThread(QThread):
    result = pyqtSignal(dict)
    error = pyqtSignal(str)
    planner_update = pyqtSignal(str)
    action_update = pyqtSignal(str, float)
    action_log_update = pyqtSignal(str, bool)

    def __init__(self, task, url, add_infos, max_steps, headless, use_vision, test_key, results_window):
        super().__init__()
        self.task = task
        self.url = url
        self.add_infos = add_infos
        self.max_steps = max_steps
        self.headless = headless
        self.use_vision = use_vision
        self.test_key = test_key
        self.results_window = results_window
        self.browser = None
        self.browser_context = None
        self.agent = None
        self._stop_flag = False

    def stop(self):
        self._stop_flag = True

    def run(self):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            result = loop.run_until_complete(self.execute_bot())
            if not self._stop_flag:
                self.result.emit(result)
        except Exception as e:
            logger.error(f"TaskThread error: {str(e)}")
            self.error.emit(str(e))
        finally:
            if not loop.is_closed():
                loop.close()

    async def execute_bot(self):
        errors = []
        final_result = None
        extracted_from_page = None
        start_time = datetime.utcnow().isoformat() + "Z"
        try:
            api_key = os.getenv("GEMINI_API_KEY")
            if not api_key:
                raise ValueError("Gemini API key missing")
            llm = ChatGoogleGenerativeAI(model="gemini-1.5-flash", api_key=SecretStr(api_key))
            browser_config = BrowserConfig(
                headless=self.headless, disable_security=DEFAULT_CONFIG["disable_security"],
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
            self.browser = Browser(config=browser_config)
            self.browser_context = await self.browser.new_context(config=context_config)
            task = self.task
            if self.url:
                task = f"Start at {self.url} and {task}"
            if self.add_infos:
                task = f"{task} Additional info: {self.add_infos}"
            logger.info(f"Refined task: {task}")
            self.agent = Agent(
                task=task, llm=llm, use_vision=self.use_vision, browser=self.browser,
                browser_context=self.browser_context, max_actions_per_step=5, planner_interval=1,
                register_action_log_callback=self.emit_action_log
            )

            original_step = self.agent.step

            async def custom_step(step_info=None):
                if self._stop_flag:
                    raise Exception("Task stopped by user")
                step_start_time = time.time()
                if self.agent.settings.planner_llm and self.agent.state.n_steps % self.agent.settings.planner_interval == 0:
                    plan = await self.agent._run_planner()
                    if plan:
                        self.planner_update.emit(f"Planner Output:\n{plan}")

                await original_step(step_info)

                step_duration = time.time() - step_start_time
                if self.agent.state.history.history:
                    last_history = self.agent.state.history.history[-1]
                    if last_history.model_output and last_history.model_output.action:
                        for i, action in enumerate(last_history.model_output.action):
                            action_desc = f"Step {self.agent.state.n_steps}: Action {i + 1}/{len(last_history.model_output.action)}: {action.model_dump_json(exclude_unset=True)}"
                            self.action_update.emit(action_desc, step_duration)
                return None

            self.agent.step = custom_step

            history = await self.agent.run(max_steps=self.max_steps)
            finish_time = datetime.utcnow().isoformat() + "Z"
            final_result = history.final_result() if history and history.final_result() else "No result"
            errors = [e for e in (history.errors() if history else []) if e is not None]
            if not extracted_from_page and history:
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
            if self._stop_flag:
                final_result = "Task stopped by user"
            elif (history and history.history and history.history[-1].model_output and
                  history.history[-1].model_output.action):
                last_action = history.history[-1].model_output.action[0]
                action_json = json.loads(last_action.model_dump_json(exclude_unset=True))
                if (action_json.get("done") and
                        "success" in action_json["done"] and
                        action_json["done"]["success"] and
                        "Successfully" in final_result):
                    overall_status = "PASSED"
                    logger.info("Task completed successfully based on 'done' action and result")

            test_key = self.test_key if self.test_key else "QUALI-456"
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
                "url": self.url,
                "add_infos": self.add_infos,
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

            self.results_window.append_result(
                f"Task completed with status: {overall_status}\nFinal result: {final_result}",
                success=(overall_status == "PASSED")
            )

            return {
                "final_result": final_result,
                "extracted_from_page": extracted_from_page,
                "errors": errors,
                "status": overall_status,
                "xray_report_path": xray_path,
                "agent_report_path": agent_path,
                "extracted_report_path": extracted_path
            }
        except Exception as e:
            errors.append(str(e))
            finish_time = datetime.utcnow().isoformat() + "Z"
            self.results_window.append_result(
                f"Task completed with status: FAILED\nFinal result: {final_result or 'Task failed'}",
                success=False
            )
            return {
                "final_result": final_result or "Task failed",
                "errors": errors,
                "status": "FAILED",
                "xray_report_path": None,
                "agent_report_path": None,
                "extracted_report_path": None
            }
        finally:
            if self.browser_context:
                await self.browser_context.close()
            if self.browser:
                await self.browser.close()
            self.results_window.show_graph_button.setEnabled(True)

    def emit_action_log(self, action_text, success):
        self.action_log_update.emit(action_text, success)


class VoiceRecognitionThread(QThread):
    result = pyqtSignal(str)
    error = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.recognizer = sr.Recognizer()

    def run(self):
        try:
            with sr.Microphone() as source:
                logger.info("Adjusting for ambient noise... Please wait.")
                self.recognizer.adjust_for_ambient_noise(source, duration=1)
                logger.info("Listening... Speak your task now.")
                audio = self.recognizer.listen(source, timeout=5, phrase_time_limit=5)
                text = self.recognizer.recognize_google(audio)
                logger.info(f"Recognized text: {text}")
                self.result.emit(text)
        except sr.WaitTimeoutError:
            self.error.emit("No speech detected within timeout.")
        except sr.UnknownValueError:
            self.error.emit("Could not understand audio.")
        except sr.RequestError as e:
            self.error.emit(f"Speech recognition request failed: {str(e)}")
        except Exception as e:
            self.error.emit(f"Unexpected error: {str(e)}")


class AnimatedButton(QPushButton):
    def __init__(self, text, parent=None, gradient_start="#42A5F5", gradient_end="#1976D2"):
        super().__init__(text, parent)
        self.setStyleSheet(f"""
            QPushButton {{
                background: qlineargradient(spread:pad, x1:0, y1:0, x2:1, y2:1, stop:0 {gradient_start}, stop:1 {gradient_end});
                color: white;
                border-radius: 12px;
                padding: 15px 30px;
                font-size: 18px;
                font-weight: bold;
                border: none;
                box-shadow: 0 4px 15px rgba(0, 0, 0, 0.2);
            }}
            QPushButton:hover {{
                background: qlineargradient(spread:pad, x1:0, y1:0, x2:1, y2:1, stop:0 {self.lighten_color(gradient_start)}, stop:1 {self.lighten_color(gradient_end)});
            }}
            QPushButton:pressed {{
                background: qlineargradient(spread:pad, x1:0, y1:0, x2:1, y2:1, stop:0 {self.darken_color(gradient_start)}, stop:1 {self.darken_color(gradient_end)});
                box-shadow: 0 2px 5px rgba(0, 0, 0, 0.2);
            }}
        """)
        self.clicked.connect(self.animate_click)

    def lighten_color(self, hex_color):
        color = QColor(hex_color)
        return QColor(min(color.red() + 30, 255), min(color.green() + 30, 255), min(color.blue() + 30, 255)).name()

    def darken_color(self, hex_color):
        color = QColor(hex_color)
        return QColor(max(0, color.red() - 30), max(0, color.green() - 30), max(0, color.blue() - 30)).name()

    def animate_click(self):
        animation = QPropertyAnimation(self, b"geometry")
        animation.setDuration(150)
        start_rect = self.geometry()
        end_rect = start_rect.adjusted(-5, -5, 5, 5)
        animation.setStartValue(start_rect)
        animation.setEndValue(end_rect)
        animation.setEasingCurve(QEasingCurve.Type.InOutElastic)
        animation.finished.connect(lambda: self.reset_geometry(start_rect))
        animation.start()

    def reset_geometry(self, original_rect):
        animation = QPropertyAnimation(self, b"geometry")
        animation.setDuration(150)
        animation.setStartValue(self.geometry())
        animation.setEndValue(original_rect)
        animation.setEasingCurve(QEasingCurve.Type.InOutElastic)
        animation.start()


class VoiceButton(QWidget):
    clicked = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(40, 40)
        self.is_recording = False

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        btn_gradient = QLinearGradient(0, 0, 0, self.height())
        btn_gradient.setColorAt(0, QColor("#2196F3"))
        btn_gradient.setColorAt(1, QColor("#1976D2"))
        painter.setBrush(QBrush(btn_gradient))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(0, 0, self.width(), self.height())

        painter.setBrush(QColor("white"))
        painter.drawEllipse(self.width() // 2 - 8, self.height() // 2 - 12, 16, 24)
        painter.drawRect(self.width() // 2 - 4, self.height() // 2 + 4, 8, 8)

    def mousePressEvent(self, event):
        self.clicked.emit()


class VoiceWaveWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(50)
        self.amplitude = 0
        self.hide()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(QColor("#2196F3"))
        height = self.height()
        width = self.width()
        y = height // 2 - int(self.amplitude * (height // 2))
        painter.drawLine(0, height // 2, width, y)

    def set_amplitude(self, amplitude):
        self.amplitude = min(max(amplitude, 0), 1)
        self.update()

    def start(self):
        self.show()

    def stop(self):
        self.hide()


class AnimatedLineEdit(QLineEdit):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet("""
            QLineEdit {
                background-color: #FFFFFF;
                border: 2px solid #42A5F5;
                border-radius: 12px;
                padding: 15px;
                font-size: 18px;
                color: #1e3c72;
            }
            QLineEdit:focus {
                border: 2px solid #1976D2;
                box-shadow: 0 0 10px rgba(66, 165, 245, 0.5);
            }
        """)
        self.focusInEvent = self.animate_focus_in
        self.focusOutEvent = self.animate_focus_out

    def animate_focus_in(self, event):
        animation = QPropertyAnimation(self, b"geometry")
        animation.setDuration(200)
        start_rect = self.geometry()
        animation.setStartValue(start_rect)
        animation.setEndValue(start_rect.adjusted(-2, -2, 2, 2))
        animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        animation.start()
        super().focusInEvent(event)

    def animate_focus_out(self, event):
        animation = QPropertyAnimation(self, b"geometry")
        animation.setDuration(200)
        start_rect = self.geometry()
        animation.setStartValue(start_rect)
        animation.setEndValue(start_rect.adjusted(2, 2, -2, -2))
        animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        animation.start()
        super().focusOutEvent(event)


class AnimatedTextEdit(QTextEdit):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet("""
            QTextEdit {
                background-color: #FFFFFF;
                border: 2px solid #42A5F5;
                border-radius: 12px;
                padding: 15px;
                font-size: 18px;
                color: #1e3c72;
            }
            QTextEdit:focus {
                border: 2px solid #1976D2;
                box-shadow: 0 0 10px rgba(66, 165, 245, 0.5);
            }
        """)
        self.focusInEvent = self.animate_focus_in
        self.focusOutEvent = self.animate_focus_out

    def animate_focus_in(self, event):
        animation = QPropertyAnimation(self, b"geometry")
        animation.setDuration(200)
        start_rect = self.geometry()
        animation.setStartValue(start_rect)
        animation.setEndValue(start_rect.adjusted(-2, -2, 2, 2))
        animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        animation.start()
        super().focusInEvent(event)

    def animate_focus_out(self, event):
        animation = QPropertyAnimation(self, b"geometry")
        animation.setDuration(200)
        start_rect = self.geometry()
        animation.setStartValue(start_rect)
        animation.setEndValue(start_rect.adjusted(2, 2, -2, -2))
        animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        animation.start()
        super().focusOutEvent(event)


class SpinnerWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(60, 60)
        self._angle = 0
        self.animation = QPropertyAnimation(self, b"angle")
        self.animation.setStartValue(0)
        self.animation.setEndValue(360)
        self.animation.setDuration(800)
        self.animation.setLoopCount(-1)
        self.hide()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.translate(self.width() / 2, self.height() / 2)
        painter.rotate(self._angle)
        gradient = QLinearGradient(0, -15, 0, 15)
        gradient.setColorAt(0, QColor("#42A5F5"))
        gradient.setColorAt(1, QColor("#1976D2"))
        painter.setBrush(QBrush(gradient))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(-20, -20, 40, 40)
        painter.end()

    def setAngle(self, angle):
        self._angle = angle
        self.update()

    def getAngle(self):
        return self._angle

    angle = pyqtProperty(int, getAngle, setAngle)

    def start(self):
        self.show()
        self.animation.start()

    def stop(self):
        self.animation.stop()
        self.hide()


class ChatBubble(QWidget):
    clicked = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(50, 50)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        gradient = QLinearGradient(0, 0, 0, self.height())
        gradient.setColorAt(0, QColor("#42A5F5"))
        gradient.setColorAt(1, QColor("#1976D2"))
        painter.setBrush(QBrush(gradient))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(0, 0, self.width(), self.height())

        pixmap = QPixmap(CHAT_LOGO_PATH)
        if not pixmap.isNull():
            scaled_pixmap = pixmap.scaled(40, 40, Qt.AspectRatioMode.KeepAspectRatio)
            painter.drawPixmap(5, 5, scaled_pixmap)

    def mousePressEvent(self, event):
        self.clicked.emit()


class ChatAssistant(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Assistant Chat")
        self.setFixedSize(600, 700)
        self.messages = []
        self.chat_display = None
        self.chat_input = None
        self.voice_button = None
        self.send_button = None
        self.close_button = None
        self.voice_thread = None
        self.initUI()

    def initUI(self):
        self.setStyleSheet("""
            QDialog {
                background: qlineargradient(spread:pad, x1:0, y1:0, x2:1, y2:1, stop:0 #ECEFF1, stop:1 #CFD8DC);
                border-radius: 15px;
            }
        """)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(15)

        header_layout = QHBoxLayout()
        header_label = QLabel("Assistant Chat")
        header_label.setStyleSheet("""
            font-size: 24px;
            font-weight: bold;
            color: #37474F;
        """)
        header_layout.addWidget(header_label)
        header_layout.addStretch()

        self.close_button = QPushButton("✖")
        self.close_button.setFixedSize(30, 30)
        self.close_button.setStyleSheet("""
            QPushButton {
                background-color: #EF5350;
                color: white;
                border-radius: 15px;
                font-size: 16px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #E53935;
            }
        """)
        self.close_button.clicked.connect(self.close)
        header_layout.addWidget(self.close_button)

        main_layout.addLayout(header_layout)

        self.chat_display = QTextEdit()
        self.chat_display.setReadOnly(True)
        self.chat_display.setStyleSheet("""
            QTextEdit {
                background-color: #FFFFFF;
                border: 1px solid #B0BEC5;
                border-radius: 10px;
                padding: 15px;
                font-size: 16px;
            }
            QScrollBar:vertical {
                border: none;
                background: #ECEFF1;
                width: 10px;
                margin: 0px;
            }
            QScrollBar::handle:vertical {
                background: #90A4AE;
                min-height: 20px;
                border-radius: 5px;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
            }
        """)
        main_layout.addWidget(self.chat_display)

        input_frame = QFrame()
        input_frame.setStyleSheet("""
            background-color: #FFFFFF;
            border: 1px solid #B0BEC5;
            border-radius: 10px;
            padding: 10px;
        """)
        input_layout = QHBoxLayout(input_frame)
        input_layout.setSpacing(10)

        self.chat_input = QLineEdit()
        self.chat_input.setPlaceholderText("Tapez votre message ou utilisez le micro...")
        self.chat_input.setStyleSheet("""
            QLineEdit {
                border: none;
                padding: 10px;
                font-size: 16px;
                color: #37474F;
                background: transparent;
            }
            QLineEdit:focus {
                border: none;
                outline: none;
            }
        """)
        self.chat_input.returnPressed.connect(self.send_message)
        input_layout.addWidget(self.chat_input)

        self.voice_button = VoiceButton(self)
        self.voice_button.clicked.connect(self.start_voice_chat)
        input_layout.addWidget(self.voice_button)

        self.send_button = AnimatedButton("Envoyer", gradient_start="#4CAF50", gradient_end="#2E7D32")
        self.send_button.setFixedWidth(100)
        self.send_button.clicked.connect(self.send_message)
        input_layout.addWidget(self.send_button)

        main_layout.addWidget(input_frame)

        self.add_message("Assistant", "Bonjour! Comment puis-je vous aider aujourd'hui?")

    def add_message(self, sender, message):
        self.messages.append((sender, message))
        html = "<style>"
        html += """
            .bubble {
                max-width: 70%;
                padding: 12px 18px;
                margin: 10px;
                border-radius: 15px;
                font-size: 16px;
                line-height: 1.4;
                display: inline-block;
                word-wrap: break-word;
            }
            .user {
                background-color: #42A5F5;
                color: white;
                float: right;
                clear: both;
            }
            .assistant {
                background-color: #E0E0E0;
                color: #37474F;
                float: left;
                clear: both;
            }
            .sender {
                font-weight: bold;
                margin-bottom: 5px;
                color: inherit;
            }
        """
        html += "</style>"

        for s, m in self.messages:
            bubble_class = "user" if s == "Vous" else "assistant"
            align = "right" if s == "Vous" else "left"
            html += f"""
                <div style="text-align: {align};">
                    <div class="bubble {bubble_class}">
                        <div class="sender">{s}</div>
                        {m}
                    </div>
                </div>
            """
        self.chat_display.setHtml(html)
        self.chat_display.verticalScrollBar().setValue(self.chat_display.verticalScrollBar().maximum())

    def send_message(self):
        message = self.chat_input.text().strip()
        if message:
            self.add_message("Vous", message)
            self.chat_input.clear()
            self.process_message(message)

    def process_message(self, message):
        response = self.generate_response(message)
        self.add_message("Assistant", response)

    def generate_response(self, message):
        message = message.lower()
        if "facebook" in message and "compte" in message:
            return """Pour créer un compte Facebook, suivez ces étapes :
1. Allez sur www.facebook.com
2. Cliquez sur "Créer un nouveau compte"
3. Remplissez le formulaire avec votre nom, email ou numéro de téléphone, mot de passe, date de naissance et genre
4. Cliquez sur "S’inscrire"
5. Confirmez votre email ou numéro de téléphone
Voulez-vous que j'exécute ces étapes pour vous?"""
        elif "étapes" in message or "expliquer" in message:
            return "Je peux expliquer les étapes pour diverses tâches. Dites-moi ce que vous voulez faire!"
        return "Je suis ici pour discuter et vous aider. Que voulez-vous faire?"

    def start_voice_chat(self):
        self.voice_thread = VoiceRecognitionThread(self)
        self.voice_thread.result.connect(self.on_chat_voice_result)
        self.voice_thread.error.connect(self.on_chat_voice_error)
        self.voice_thread.start()
        QMessageBox.information(self, "Écoute", "Parlez maintenant...")

    def on_chat_voice_result(self, text):
        self.chat_input.setText(text)
        self.send_message()

    def on_chat_voice_error(self, error):
        self.add_message("Assistant", f"Erreur de reconnaissance vocale: {error}")


class WelcomeWindow(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.welcome_label = None
        self.animation = None
        self.initUI()

    def initUI(self):
        palette = QPalette()
        pixmap = QPixmap(BACKGROUND_IMAGE_PATH)
        if pixmap.isNull():
            self.setStyleSheet(
                "background: qlineargradient(spread:pad, x1:0, y1:0, x2:1, y2:1, stop:0 #E0F2FE, stop:1 #BAE6FD);")
        else:
            brush = QBrush(pixmap.scaled(self.size(), Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                                         Qt.TransformationMode.SmoothTransformation))
            palette.setBrush(QPalette.ColorRole.Window, brush)
            self.setPalette(palette)
            self.setAutoFillBackground(True)

        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.welcome_label = QLabel()
        pixmap = QPixmap(LOGO_PATH)
        if pixmap.isNull():
            self.welcome_label.setText("Welcome to QualiMation")
            self.welcome_label.setStyleSheet("color: #1e3c72; font-size: 48px; font-weight: bold;")
        else:
            scaled_pixmap = pixmap.scaled(600, 300, Qt.AspectRatioMode.KeepAspectRatio,
                                          Qt.TransformationMode.SmoothTransformation)
            self.welcome_label.setPixmap(scaled_pixmap)
        self.welcome_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.welcome_label)

    def showEvent(self, event):
        if self.welcome_label:
            self.animation = QPropertyAnimation(self.welcome_label, b"geometry")
            self.animation.setDuration(1500)
            start_rect = QRect(self.width() // 2 - 300, self.height() // 2 - 150, 600, 300)
            end_rect = start_rect.adjusted(0, -20, 0, 20)
            self.welcome_label.setGeometry(start_rect)
            self.animation.setStartValue(start_rect)
            self.animation.setEndValue(end_rect)
            self.animation.setEasingCurve(QEasingCurve.Type.InOutElastic)
            self.animation.setLoopCount(-1)
            self.animation.start()
        super().showEvent(event)

    def resizeEvent(self, event):
        palette = self.palette()
        pixmap = QPixmap(BACKGROUND_IMAGE_PATH)
        if not pixmap.isNull():
            brush = QBrush(pixmap.scaled(self.size(), Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                                         Qt.TransformationMode.SmoothTransformation))
            palette.setBrush(QPalette.ColorRole.Window, brush)
            self.setPalette(palette)
        super().resizeEvent(event)

    def mousePressEvent(self, event):
        self.parent().setCurrentIndex(1)


class RegisterWindow(QMainWindow):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Register")
        self.username_input = None
        self.password_input = None
        self.register_button = None
        self.back_button = None
        self.initUI()

    def initUI(self):
        central_widget = QWidget(self)
        self.setCentralWidget(central_widget)

        palette = QPalette()
        pixmap = QPixmap(BACKGROUND_IMAGE_PATH)
        brush = QBrush(pixmap.scaled(self.size(), Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                                     Qt.TransformationMode.SmoothTransformation))
        palette.setBrush(QPalette.ColorRole.Window, brush)
        central_widget.setPalette(palette)
        central_widget.setAutoFillBackground(True)

        main_layout = QVBoxLayout(central_widget)
        main_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        form_frame = QFrame()
        form_frame.setStyleSheet("""
            background: #FFFFFF;
            border-radius: 20px;
            padding: 40px;
            box-shadow: 0 4px 15px rgba(0, 0, 0, 0.2);
        """)
        form_layout = QVBoxLayout(form_frame)
        form_layout.setSpacing(20)

        logo_label = QLabel()
        pixmap = QPixmap(LOGO_PATH)
        logo_label.setPixmap(pixmap.scaled(400, 200, Qt.AspectRatioMode.KeepAspectRatio,
                                           Qt.TransformationMode.SmoothTransformation))
        logo_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        form_layout.addWidget(logo_label)

        title = QLabel("Register")
        title.setStyleSheet("color: #1e3c72; font-size: 32px; font-weight: bold;")
        form_layout.addWidget(title, alignment=Qt.AlignmentFlag.AlignCenter)

        self.username_input = AnimatedLineEdit()
        self.username_input.setPlaceholderText("Username")
        form_layout.addWidget(self.username_input)

        self.password_input = AnimatedLineEdit()
        self.password_input.setPlaceholderText("Password")
        self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
        form_layout.addWidget(self.password_input)

        self.register_button = AnimatedButton("Create Account", gradient_start="#AB47BC", gradient_end="#7B1FA2")
        self.register_button.clicked.connect(self.handle_register)
        form_layout.addWidget(self.register_button, alignment=Qt.AlignmentFlag.AlignCenter)

        self.back_button = AnimatedButton("Back", gradient_start="#FF9800", gradient_end="#F57C00")
        self.back_button.clicked.connect(self.close)
        form_layout.addWidget(self.back_button, alignment=Qt.AlignmentFlag.AlignCenter)

        main_layout.addWidget(form_frame)

    def handle_register(self):
        username = self.username_input.text()
        password = self.password_input.text()
        users = load_users()

        if not username or not password:
            QMessageBox.warning(self, "Error", "All fields are required!")
            return
        if username in users:
            QMessageBox.warning(self, "Error", "Username already exists!")
            return

        try:
            users[username] = {"password": generate_password_hash(password), "job": "User"}
            save_users(users)
            QMessageBox.information(self, "Success", "Registration successful! Please log in.")
            self.close()
        except Exception as e:
            logger.error(f"Registration error: {str(e)}")
            QMessageBox.critical(self, "Error", f"Failed to register: {str(e)}")

    def resizeEvent(self, event):
        palette = self.centralWidget().palette()
        pixmap = QPixmap(BACKGROUND_IMAGE_PATH)
        brush = QBrush(pixmap.scaled(self.size(), Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                                     Qt.TransformationMode.SmoothTransformation))
        palette.setBrush(QPalette.ColorRole.Window, brush)
        self.centralWidget().setPalette(palette)
        super().resizeEvent(event)


class AuthWindow(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.username_input = None
        self.password_input = None
        self.login_button = None
        self.loading_spinner = None
        self.register_link = None
        self.register_window = None
        self.initUI()

    def initUI(self):
        palette = QPalette()
        pixmap = QPixmap(BACKGROUND_IMAGE_PATH)
        brush = QBrush(pixmap.scaled(self.size(), Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                                     Qt.TransformationMode.SmoothTransformation))
        palette.setBrush(QPalette.ColorRole.Window, brush)
        self.setPalette(palette)
        self.setAutoFillBackground(True)

        main_layout = QVBoxLayout(self)
        main_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        form_frame = QFrame()
        form_frame.setStyleSheet("""
            background: #FFFFFF;
            border-radius: 20px;
            padding: 40px;
            box-shadow: 0 4px 15px rgba(0, 0, 0, 0.2);
        """)
        form_layout = QVBoxLayout(form_frame)
        form_layout.setSpacing(20)

        logo_label = QLabel()
        pixmap = QPixmap(LOGO_PATH)
        logo_label.setPixmap(pixmap.scaled(400, 200, Qt.AspectRatioMode.KeepAspectRatio,
                                           Qt.TransformationMode.SmoothTransformation))
        logo_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        form_layout.addWidget(logo_label)

        title = QLabel("Login")
        title.setStyleSheet("color: #1e3c72; font-size: 32px; font-weight: bold;")
        form_layout.addWidget(title, alignment=Qt.AlignmentFlag.AlignCenter)

        self.username_input = AnimatedLineEdit()
        self.username_input.setPlaceholderText("Username")
        form_layout.addWidget(self.username_input)

        self.password_input = AnimatedLineEdit()
        self.password_input.setPlaceholderText("Password")
        self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
        form_layout.addWidget(self.password_input)

        self.login_button = AnimatedButton("Login", gradient_start="#AB47BC", gradient_end="#7B1FA2")
        self.login_button.clicked.connect(self.handle_login)
        form_layout.addWidget(self.login_button, alignment=Qt.AlignmentFlag.AlignCenter)

        self.loading_spinner = SpinnerWidget(self)
        form_layout.addWidget(self.loading_spinner, alignment=Qt.AlignmentFlag.AlignCenter)

        self.register_link = QLabel("Register")
        self.register_link.setStyleSheet("""
            color: #42A5F5;
            font-size: 18px;
            text-decoration: underline;
        """)
        self.register_link.setCursor(Qt.CursorShape.PointingHandCursor)
        self.register_link.mousePressEvent = self.open_register_window
        form_layout.addWidget(self.register_link, alignment=Qt.AlignmentFlag.AlignCenter)

        main_layout.addWidget(form_frame)

    def resizeEvent(self, event):
        palette = self.palette()
        pixmap = QPixmap(BACKGROUND_IMAGE_PATH)
        brush = QBrush(pixmap.scaled(self.size(), Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                                     Qt.TransformationMode.SmoothTransformation))
        palette.setBrush(QPalette.ColorRole.Window, brush)
        self.setPalette(palette)
        super().resizeEvent(event)

    def open_register_window(self, event):
        if self.register_window is None or not self.register_window.isVisible():
            self.register_window = RegisterWindow(self)
            self.register_window.showFullScreen()

    def handle_login(self):
        username = self.username_input.text()
        password = self.password_input.text()

        self.loading_spinner.start()
        self.login_button.setEnabled(False)
        self.username_input.setEnabled(False)
        self.password_input.setEnabled(False)
        self.register_link.setEnabled(False)

        users = load_users()
        if username in users and check_password_hash(users[username]["password"], password):
            user = User(username, users[username]["job"])
            QTimer.singleShot(1000, lambda: self.login_success(user))
        else:
            QTimer.singleShot(1000, self.login_failed)

    def login_success(self, user):
        self.loading_spinner.stop()
        self.login_button.setEnabled(True)
        self.username_input.setEnabled(True)
        self.password_input.setEnabled(True)
        self.register_link.setEnabled(True)
        self.parent().parent().show_main_window(user)

    def login_failed(self):
        self.loading_spinner.stop()
        self.login_button.setEnabled(True)
        self.username_input.setEnabled(True)
        self.password_input.setEnabled(True)
        self.register_link.setEnabled(True)
        QMessageBox.warning(self, "Error", "Invalid username or password!")


class ActionLogWindow(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Action Log")
        self.log_display = None
        self.initUI()

    def initUI(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        self.log_display = QTextEdit()
        self.log_display.setReadOnly(True)
        self.log_display.setStyleSheet("""
            QTextEdit {
                background-color: rgba(245, 246, 250, 0.8);
                border: 2px solid #42A5F5;
                border-radius: 10px;
                padding: 15px;
                font-size: 16px;
            }
        """)
        layout.addWidget(self.log_display)

    def append_action(self, action_text, success):
        color = "green" if success else "red"
        self.log_display.append(
            f'<span style="color: {color}; font-weight: bold;">{"PASSED" if success else "FAILED"}: {action_text}</span>')


class ModulesWindow(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Modules")
        self.setFixedSize(400, 400)
        self.twitter_window = None
        self.retour_button = None
        self.close_button = None
        self.initUI()

    def initUI(self):
        self.setStyleSheet("background: rgba(255, 255, 255, 0.9);")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)

        buttons = [
            ("Action", self.on_action_click, "#42A5F5", "#1976D2"),
            ("Documentation", self.on_documentation_click, "#42A5F5", "#1976D2"),
            ("Employee", self.on_employee_click, "#42A5F5", "#1976D2"),
            ("Twitter", self.on_twitter_click, "#42A5F5", "#1976D2"),
            ("Facebook", self.on_facebook_click, "#42A5F5", "#1976D2")
        ]

        for text, callback, start_color, end_color in buttons:
            btn = AnimatedButton(text, gradient_start=start_color, gradient_end=end_color)
            btn.clicked.connect(callback)
            layout.addWidget(btn)

        nav_layout = QHBoxLayout()
        self.retour_button = AnimatedButton("Retour", gradient_start="#FF9800", gradient_end="#F57C00")
        self.retour_button.clicked.connect(self.hide)
        nav_layout.addWidget(self.retour_button)

        self.close_button = AnimatedButton("Close", gradient_start="#F44336", gradient_end="#D32F2F")
        self.close_button.clicked.connect(self.close)
        nav_layout.addWidget(self.close_button)

        layout.addLayout(nav_layout)
        layout.addStretch()

    def on_action_click(self):
        QMessageBox.information(self, "Action", "Action module selected (not implemented).")

    def on_documentation_click(self):
        QMessageBox.information(self, "Documentation", "Documentation module selected (not implemented).")

    def on_employee_click(self):
        QMessageBox.information(self, "Employee", "Employee module selected (not implemented).")

    def on_twitter_click(self):
        if self.twitter_window is None or not self.twitter_window.isVisible():
            self.twitter_window = TwitterOptionsWindow(self)
            self.twitter_window.show()

    def on_facebook_click(self):
        QMessageBox.information(self, "Facebook", "Facebook module selected (not implemented).")


class TwitterOptionsWindow(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Twitter Options")
        self.setFixedSize(300, 200)
        self.initUI()

    def initUI(self):
        self.setStyleSheet("background: rgba(255, 255, 255, 0.9);")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)

        buttons = [
            ("Create", self.on_create_click, "#42A5F5", "#1976D2"),
            ("Modify", self.on_modify_click, "#42A5F5", "#1976D2"),
            ("Delete", self.on_delete_click, "#42A5F5", "#1976D2")
        ]

        for text, callback, start_color, end_color in buttons:
            btn = AnimatedButton(text, gradient_start=start_color, gradient_end=end_color)
            btn.clicked.connect(callback)
            layout.addWidget(btn)

        layout.addStretch()

    def on_create_click(self):
        if self.parent() and self.parent().parent():
            main_window = self.parent().parent()
            main_window.task_input.setPlainText("create a twitter account")
            main_window.execute_task()
        self.close()

    def on_modify_click(self):
        QMessageBox.information(self, "Modify", "Modify Twitter account (not implemented).")
        self.close()

    def on_delete_click(self):
        QMessageBox.information(self, "Delete", "Delete Twitter account (not implemented).")
        self.close()
class ReclamationOptionsWindow(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Reclamation Options")
        self.setFixedSize(300, 300)
        self.initUI()

    def initUI(self):
        self.setStyleSheet("background: rgba(255, 255, 255, 0.9);")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)

        buttons = [
            ("Reclamation Client", self.on_reclamation_client_click, "#42A5F5", "#1976D2"),
            ("Type Reclamation", self.on_type_reclamation_click, "#42A5F5", "#1976D2"),
            ("Nature de Reclamation", self.on_nature_reclamation_click, "#42A5F5", "#1976D2")
        ]

        for text, callback, start_color, end_color in buttons:
            btn = AnimatedButton(text, gradient_start=start_color, gradient_end=end_color)
            btn.clicked.connect(callback)
            layout.addWidget(btn)

        layout.addStretch()

    def on_reclamation_client_click(self):
        if self.parent() and self.parent().parent():
            main_window = self.parent().parent()
            task = """open http://10.66.245.30/w254/
connect with MO,MO
select "Filiale 1"
go to http://10.66.245.30/w254/Satisfaction%20client/ReclamationClient/ReclamationClt.aspx
Click on "ctl00$ContentPlaceHolder1$tb_reclamation"
Enter "piwpiw" into "ctl00$ContentPlaceHolder1$tb_reclamation"
Click on "Sélectionner"
Click on "Tunis 3"
Click on "Sélectionner"
Click on "1508"
select "Retard de production" from "DEDEDE dfsff nature 1 Nature 10 j Nature 12 Nature 12 j Nature 15 j Nature 2 "
select "Type 15 j" from "Type 15 j"""
            main_window.task_input.setPlainText(task)
            main_window.execute_task()
        self.close()

    def on_type_reclamation_click(self):
        QMessageBox.information(self, "Type Reclamation", "Type Reclamation selected (not implemented).")
        self.close()

    def on_nature_reclamation_click(self):
        QMessageBox.information(self, "Nature de Reclamation", "Nature de Reclamation selected (not implemented).")
        self.close()


class ModulesWindow(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Modules")
        self.setFixedSize(400, 500)  # Increased size to accommodate new button
        self.twitter_window = None
        self.reclamation_window = None
        self.retour_button = None
        self.close_button = None
        self.initUI()

    def initUI(self):
        self.setStyleSheet("background: rgba(255, 255, 255, 0.9);")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)

        buttons = [
            ("Action", self.on_action_click, "#42A5F5", "#1976D2"),
            ("Documentation", self.on_documentation_click, "#42A5F5", "#1976D2"),
            ("Employee", self.on_employee_click, "#42A5F5", "#1976D2"),
            ("Twitter", self.on_twitter_click, "#42A5F5", "#1976D2"),
            ("Facebook", self.on_facebook_click, "#42A5F5", "#1976D2"),
            ("Reclamation", self.on_reclamation_click, "#42A5F5", "#1976D2")  # New Reclamation button
        ]

        for text, callback, start_color, end_color in buttons:
            btn = AnimatedButton(text, gradient_start=start_color, gradient_end=end_color)
            btn.clicked.connect(callback)
            layout.addWidget(btn)

        nav_layout = QHBoxLayout()
        self.retour_button = AnimatedButton("Retour", gradient_start="#FF9800", gradient_end="#F57C00")
        self.retour_button.clicked.connect(self.hide)
        nav_layout.addWidget(self.retour_button)

        self.close_button = AnimatedButton("Close", gradient_start="#F44336", gradient_end="#D32F2F")
        self.close_button.clicked.connect(self.close)
        nav_layout.addWidget(self.close_button)

        layout.addLayout(nav_layout)
        layout.addStretch()

    def on_action_click(self):
        QMessageBox.information(self, "Action", "Action module selected (not implemented).")

    def on_documentation_click(self):
        QMessageBox.information(self, "Documentation", "Documentation module selected (not implemented).")

    def on_employee_click(self):
        QMessageBox.information(self, "Employee", "Employee module selected (not implemented).")

    def on_twitter_click(self):
        if self.twitter_window is None or not self.twitter_window.isVisible():
            self.twitter_window = TwitterOptionsWindow(self)
            self.twitter_window.show()

    def on_facebook_click(self):
        QMessageBox.information(self, "Facebook", "Facebook module selected (not implemented).")

    def on_reclamation_click(self):
        if self.reclamation_window is None or not self.reclamation_window.isVisible():
            self.reclamation_window = ReclamationOptionsWindow(self)
            self.reclamation_window.show()

class MainWindow(QMainWindow):
    def __init__(self, user):
        super().__init__()
        self.user = user
        self.setWindowTitle(f"QualiMation - {self.user.id}")
        self.results_window = None
        self.modules_window = None
        self.action_log_window = None
        self.chat_assistant = None
        self.test_key_input = None
        self.task_input = None
        self.voice_button = None
        self.extract_button = None
        self.chat_bubble = None
        self.wave_widget = None
        self.url_input = None
        self.add_infos_input = None
        self.max_steps_input = None
        self.headless_checkbox = None
        self.use_vision_checkbox = None
        self.run_button = None
        self.stop_button = None
        self.modules_button = None
        self.results_button = None
        self.loading_spinner = None
        self.result_display = None
        self.xray_report_button = None
        self.extracted_report_button = None
        self.xray_report_path = None
        self.agent_report_path = None
        self.extracted_report_path = None
        self.task_thread = None
        self.voice_thread = None
        self.wave_timer = None
        self.initUI()
        self.action_log_window = ActionLogWindow(self)
        self.action_log_window.show()

    def initUI(self):
        central_widget = QWidget(self)
        self.setCentralWidget(central_widget)

        palette = QPalette()
        pixmap = QPixmap(BACKGROUND_IMAGE_PATH)
        if pixmap.isNull():
            central_widget.setStyleSheet(
                "background: qlineargradient(spread:pad, x1:0, y1:0, x2:1, y2:1, stop:0 #E0F2FE, stop:1 #BAE6FD);")
        else:
            brush = QBrush(pixmap.scaled(self.size(), Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                                         Qt.TransformationMode.SmoothTransformation))
            palette.setBrush(QPalette.ColorRole.Window, brush)
            central_widget.setPalette(palette)
            central_widget.setAutoFillBackground(True)

        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(40, 40, 40, 40)
        main_layout.setSpacing(20)

        header_layout = QHBoxLayout()
        logo_label = QLabel()
        pixmap = QPixmap(LOGO_PATH)
        logo_label.setPixmap(pixmap.scaled(200, 100, Qt.AspectRatioMode.KeepAspectRatio,
                                           Qt.TransformationMode.SmoothTransformation))
        header_layout.addWidget(logo_label)

        title = QLabel("QualiMation Bot")
        title.setStyleSheet("color: #1e3c72; font-size: 40px; font-weight: bold;")
        header_layout.addWidget(title, alignment=Qt.AlignmentFlag.AlignCenter)

        logout_button = AnimatedButton("Logout", gradient_start="#AB47BC", gradient_end="#7B1FA2")
        logout_button.clicked.connect(self.logout)
        header_layout.addWidget(logout_button, alignment=Qt.AlignmentFlag.AlignRight)
        main_layout.addLayout(header_layout)

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setStyleSheet("QScrollArea { border: none; background: transparent; }")
        content_widget = QWidget()
        scroll_area.setWidget(content_widget)
        content_layout = QVBoxLayout(content_widget)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(20)

        content_frame = QFrame()
        content_frame.setStyleSheet("""
            background: rgba(255, 255, 255, 0.7);
            border-radius: 20px;
            padding: 30px;
        """)
        frame_layout = QVBoxLayout(content_frame)
        frame_layout.setSpacing(25)

        input_layout = QVBoxLayout()
        input_layout.setSpacing(15)

        self.test_key_input = AnimatedLineEdit()
        self.test_key_input.setPlaceholderText("Test Key (e.g., PROJ-200)")
        input_layout.addWidget(self.test_key_input)

        task_layout = QHBoxLayout()
        self.task_input = AnimatedTextEdit()
        self.task_input.setPlaceholderText(
            "Enter your task (e.g., Navigate to Google) or use voice input or extract from file")
        self.task_input.setMinimumHeight(150)
        task_layout.addWidget(self.task_input)

        self.voice_button = VoiceButton(self)
        self.voice_button.clicked.connect(self.start_voice_recognition)
        task_layout.addWidget(self.voice_button)

        self.extract_button = AnimatedButton("Extract from File", gradient_start="#FF5722", gradient_end="#E64A19")
        self.extract_button.clicked.connect(self.extract_and_execute_file)
        task_layout.addWidget(self.extract_button)

        self.chat_bubble = ChatBubble(self)
        self.chat_bubble.clicked.connect(self.show_chat_assistant)
        task_layout.addWidget(self.chat_bubble)

        input_layout.addLayout(task_layout)

        self.wave_widget = VoiceWaveWidget(self)
        input_layout.addWidget(self.wave_widget)

        self.url_input = AnimatedLineEdit()
        self.url_input.setPlaceholderText("Starting URL (e.g., https://www.google.com)")
        input_layout.addWidget(self.url_input)

        self.add_infos_input = AnimatedTextEdit()
        self.add_infos_input.setPlaceholderText("Additional instructions (optional)")
        self.add_infos_input.setMinimumHeight(100)
        input_layout.addWidget(self.add_infos_input)

        frame_layout.addLayout(input_layout)

        options_layout = QHBoxLayout()
        options_layout.setSpacing(25)

        left_options = QVBoxLayout()
        left_options.setSpacing(15)
        self.max_steps_input = AnimatedLineEdit()
        self.max_steps_input.setText("100")
        self.max_steps_input.setPlaceholderText("Max Steps")
        self.max_steps_input.setFixedWidth(200)
        left_options.addWidget(self.max_steps_input)

        checkbox_layout = QHBoxLayout()
        self.headless_checkbox = QCheckBox("Headless Mode")
        self.headless_checkbox.setStyleSheet("color: #1e3c72; font-size: 16px;")
        self.headless_checkbox.setChecked(False)
        checkbox_layout.addWidget(self.headless_checkbox)

        self.use_vision_checkbox = QCheckBox("Use Vision")
        self.use_vision_checkbox.setStyleSheet("color: #1e3c72; font-size: 16px;")
        self.use_vision_checkbox.setChecked(True)
        checkbox_layout.addWidget(self.use_vision_checkbox)
        left_options.addLayout(checkbox_layout)
        options_layout.addLayout(left_options)

        button_layout = QVBoxLayout()
        button_layout.setSpacing(20)
        button_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        run_stop_layout = QHBoxLayout()
        run_stop_layout.setSpacing(20)
        self.run_button = AnimatedButton("Run Bot", gradient_start="#4CAF50", gradient_end="#2E7D32")
        self.run_button.clicked.connect(self.execute_task)
        run_stop_layout.addWidget(self.run_button)

        self.stop_button = AnimatedButton("Stop Bot", gradient_start="#F44336", gradient_end="#D32F2F")
        self.stop_button.clicked.connect(self.stop_task)
        self.stop_button.setEnabled(False)
        run_stop_layout.addWidget(self.stop_button)
        button_layout.addLayout(run_stop_layout)

        self.modules_button = AnimatedButton("Modules", gradient_start="#FF9800", gradient_end="#F57C00")
        self.modules_button.clicked.connect(self.show_modules_window)
        button_layout.addWidget(self.modules_button)

        self.results_button = AnimatedButton("Show Results", gradient_start="#AB47BC", gradient_end="#7B1FA2")
        self.results_button.clicked.connect(self.show_results_window)
        button_layout.addWidget(self.results_button)

        self.loading_spinner = SpinnerWidget(self)
        button_layout.addWidget(self.loading_spinner, alignment=Qt.AlignmentFlag.AlignCenter)

        options_layout.addLayout(button_layout)
        frame_layout.addLayout(options_layout)

        self.result_display = AnimatedTextEdit()
        self.result_display.setReadOnly(True)
        self.result_display.setPlaceholderText("Bot results will appear here")
        self.result_display.setMinimumHeight(200)
        frame_layout.addWidget(self.result_display)

        report_layout = QHBoxLayout()
        report_layout.setSpacing(20)
        self.xray_report_button = AnimatedButton("Download Xray Report", gradient_start="#42A5F5",
                                                 gradient_end="#1976D2")
        self.xray_report_button.clicked.connect(lambda: self.download_report("xray"))
        self.xray_report_button.setEnabled(False)
        report_layout.addWidget(self.xray_report_button)

        self.extracted_report_button = AnimatedButton("Download Extracted Report", gradient_start="#42A5F5",
                                                      gradient_end="#1976D2")
        self.extracted_report_button.clicked.connect(lambda: self.download_report("extracted"))
        self.extracted_report_button.setEnabled(False)
        report_layout.addWidget(self.extracted_report_button)

        frame_layout.addLayout(report_layout)
        content_layout.addWidget(content_frame)
        content_layout.addStretch()
        main_layout.addWidget(scroll_area, stretch=1)

    def resizeEvent(self, event):
        palette = self.centralWidget().palette()
        pixmap = QPixmap(BACKGROUND_IMAGE_PATH)
        if not pixmap.isNull():
            brush = QBrush(pixmap.scaled(self.size(), Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                                         Qt.TransformationMode.SmoothTransformation))
            palette.setBrush(QPalette.ColorRole.Window, brush)
            self.centralWidget().setPalette(palette)
        super().resizeEvent(event)

    def show_modules_window(self):
        if self.modules_window is None or not self.modules_window.isVisible():
            self.modules_window = ModulesWindow(self)
            self.modules_window.show()

    def show_results_window(self):
        logger.info("Show Results button clicked")
        if self.results_window is None:
            logger.info("Creating new ResultsWindow")
            self.results_window = ResultsWindow(self)
        else:
            logger.info("Reusing existing ResultsWindow")
        self.results_window.showFullScreen()
        self.results_window.raise_()
        self.results_window.activateWindow()
        logger.info(f"ResultsWindow visible: {self.results_window.isVisible()}")

    def show_chat_assistant(self):
        if self.chat_assistant is None or not self.chat_assistant.isVisible():
            self.chat_assistant = ChatAssistant(self)
            self.chat_assistant.show()

    def start_voice_recognition(self):
        self.loading_spinner.start()
        self.wave_widget.start()
        QMessageBox.information(self, "Voice Input", "Speak your task now. Listening for 5 seconds...")

        self.voice_thread = VoiceRecognitionThread(self)
        self.voice_thread.result.connect(self.on_voice_result)
        self.voice_thread.error.connect(self.on_voice_error)
        self.voice_thread.finished.connect(self.on_voice_finished)

        self.wave_timer = QTimer(self)
        self.wave_timer.timeout.connect(lambda: self.wave_widget.set_amplitude(np.random.random()))
        self.wave_timer.start(100)

        self.voice_thread.start()

    def on_voice_result(self, text):
        self.task_input.setPlainText(text)

    def on_voice_error(self, error_msg):
        logger.warning(error_msg)
        QMessageBox.warning(self, "Voice Input", f"Error: {error_msg}")

    def on_voice_finished(self):
        self.loading_spinner.stop()
        self.wave_widget.stop()
        if self.wave_timer:
            self.wave_timer.stop()

    def extract_and_execute_file(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select File to Extract",
            "",
            "Text Files (*.txt);;JSON Files (*.json);;All Files (*.*)"
        )

        if not file_path:
            return

        try:
            with open(file_path, 'r', encoding='utf-8') as file:
                content = file.read()

            file_extension = os.path.splitext(file_path)[1].lower()
            task = ""

            if file_extension == '.json':
                try:
                    data = json.loads(content)
                    task = data.get('task', content)
                except json.JSONDecodeError:
                    task = content
            else:
                task = content.strip()

            if not task:
                QMessageBox.warning(self, "Error", "No task found in the file!")
                return

            self.task_input.setPlainText(task)

            reply = QMessageBox.question(
                self,
                "Confirm Execution",
                f"Extracted task:\n\n{task}\n\nWould you like to execute this task?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )

            if reply == QMessageBox.Yes:
                self.execute_task()
            else:
                QMessageBox.information(self, "Info", "Task loaded but not executed.")

        except Exception as e:
            logger.error(f"Error extracting file: {str(e)}")
            QMessageBox.warning(self, "Error", f"Failed to extract file: {str(e)}")

    def execute_task(self):
        task = self.task_input.toPlainText()
        url = self.url_input.text()
        add_infos = self.add_infos_input.toPlainText()
        test_key = self.test_key_input.text()
        try:
            max_steps = int(self.max_steps_input.text())
        except ValueError:
            QMessageBox.warning(self, "Error", "Max Steps must be a number!")
            return
        headless = self.headless_checkbox.isChecked()
        use_vision = self.use_vision_checkbox.isChecked()

        if not task:
            QMessageBox.warning(self, "Error", "Task is required!")
            return

        self.run_button.setEnabled(False)
        self.stop_button.setEnabled(True)
        self.loading_spinner.start()
        self.result_display.clear()
        self.action_log_window.log_display.clear()
        if self.results_window:
            self.results_window.result_display.clear()
            self.results_window.pass_count = 0
            self.results_window.fail_count = 0
            self.results_window.results_data = []
        else:
            self.results_window = ResultsWindow(self)
        self.xray_report_button.setEnabled(False)
        self.extracted_report_button.setEnabled(False)

        self.task_thread = TaskThread(task, url, add_infos, max_steps, headless, use_vision, test_key,
                                      self.results_window)
        self.task_thread.result.connect(self.on_task_finished)
        self.task_thread.error.connect(self.on_task_error)
        self.task_thread.planner_update.connect(self.on_planner_update)
        self.task_thread.action_update.connect(self.on_action_update)
        self.task_thread.action_log_update.connect(self.on_action_log_update)
        self.task_thread.finished.connect(self.on_thread_finished)
        self.task_thread.start()
        logger.info("Task thread started")

    def on_task_finished(self, result):
        try:
            logger.info("Task finished with result: %s", result)
            overall_status = result.get('status', 'FAILED')
            final_result = result.get('final_result', 'No result')

            status_color = "green" if overall_status == "PASSED" else "red"
            self.result_display.append(
                f'<span style="color: {status_color}; font-weight: bold;">\nStatus: {overall_status}</span>\n'
                f"Final Result: {final_result}"
            )
            self.results_window.append_result(
                f"Task completed with status: {overall_status}\nFinal result: {final_result}",
                success=(overall_status == "PASSED")
            )

            self.xray_report_path = result.get('xray_report_path')
            self.agent_report_path = result.get('agent_report_path')
            self.extracted_report_path = result.get('extracted_report_path')

            self.xray_report_button.setEnabled(bool(self.xray_report_path and os.path.exists(self.xray_report_path)))
            self.extracted_report_button.setEnabled(
                bool(self.extracted_report_path and os.path.exists(self.extracted_report_path)))
        except Exception as e:
            logger.error(f"Error in on_task_finished: {str(e)}")
            self.result_display.append(
                f'<span style="color: red; font-weight: bold;">\nStatus: FAILED</span>\nFinal Result: Task failed')
            self.results_window.append_result(
                "Task completed with status: FAILED\nFinal result: Task failed",
                success=False
            )

    def on_task_error(self, error):
        logger.error(f"Task error: {error}")
        self.result_display.append(
            f'<span style="color: red; font-weight: bold;">\nStatus: FAILED</span>\nFinal Result: Task failed')
        self.results_window.append_result(
            "Task completed with status: FAILED\nFinal result: Task failed",
            success=False
        )
        self.run_button.setEnabled(True)
        self.stop_button.setEnabled(False)
        self.loading_spinner.stop()

    def on_planner_update(self, planner_output):
        self.result_display.append(f"\n{planner_output}")
        self.results_window.append_result(planner_output)

    def on_action_update(self, action_desc, duration):
        self.result_display.append(f"\n{action_desc} [Duration: {duration:.2f}s]")
        self.results_window.append_result(action_desc, duration=duration)

    def on_action_log_update(self, action_text, success):
        self.action_log_window.append_action(action_text, success)

    def on_thread_finished(self):
        logger.info("Thread finished")
        self.run_button.setEnabled(True)
        self.stop_button.setEnabled(False)
        self.loading_spinner.stop()
        self.results_window.show_graph_button.setEnabled(True)

    def stop_task(self):
        if hasattr(self, 'task_thread') and self.task_thread and self.task_thread.isRunning():
            self.task_thread.stop()
            self.task_thread.wait()
            self.result_display.append(
                '<span style="color: red; font-weight: bold;">\nStatus: FAILED</span>\nFinal Result: Task stopped by user')
            self.results_window.append_result(
                "Task completed with status: FAILED\nFinal result: Task stopped by user",
                success=False
            )
            self.run_button.setEnabled(True)
            self.stop_button.setEnabled(False)
            self.loading_spinner.stop()

    def download_report(self, report_type):
        paths = {"xray": self.xray_report_path, "agent": self.agent_report_path,
                 "extracted": self.extracted_report_path}
        path = paths.get(report_type)
        if path and os.path.exists(path):
            file_path, _ = QFileDialog.getSaveFileName(self, "Save Report", os.path.basename(path),
                                                       "JSON Files (*.json)")
            if file_path:
                try:
                    with open(path, 'rb') as src, open(file_path, 'wb') as dst:
                        dst.write(src.read())
                    QMessageBox.information(self, "Success", "Report downloaded successfully!")
                except Exception as e:
                    logger.error(f"Error downloading report {report_type}: {str(e)}")
                    QMessageBox.warning(self, "Error", f"Failed to download report: {str(e)}")
        else:
            logger.warning(f"Report file not found for {report_type}: {path}")
            QMessageBox.warning(self, "Error", "Report file not found!")

    def logout(self):
        self.parent().setCurrentIndex(0)
        self.hide()


class App(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("QualiMation")
        self.stack = None
        self.welcome_window = None
        self.auth_window = None
        self.main_window = None
        self.initUI()

    def initUI(self):
        self.stack = QStackedWidget(self)
        self.setCentralWidget(self.stack)

        self.welcome_window = WelcomeWindow(self.stack)
        self.auth_window = AuthWindow(self.stack)
        self.stack.addWidget(self.welcome_window)
        self.stack.addWidget(self.auth_window)
        self.stack.setCurrentIndex(0)

    def show_main_window(self, user):
        if self.main_window is None:
            self.main_window = MainWindow(user)
            self.stack.addWidget(self.main_window)
        self.stack.setCurrentIndex(2)


if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = App()
    window.showFullScreen()
    sys.exit(app.exec())