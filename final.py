import sys, re
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, 
    QHBoxLayout, QTextEdit, QLineEdit, QPushButton,
    QFileDialog
)
from PyQt6.QtCore import QTimer, Qt, QObject, pyqtSignal
from PyQt6.QtGui import QTextCursor
from dotenv import load_dotenv
import os, datetime
from multiprocessing import Process, Pipe
import time
import html
import re, tempfile, multiprocessing
from ragflow_sdk import RAGFlow
print("lol")
# Загрузка .env файла
if getattr(sys, 'frozen', False):
    # Если запущено как exe
    import sys
    base_path = sys._MEIPASS
else:
    # Если запущено как скрипт
    base_path = os.path.dirname(os.path.abspath(__file__))

env_path = os.path.join(base_path, '.env')
load_dotenv(env_path)


def to_russian(text: str) -> str:
    """
    Оставляет кириллицу, пробелы, знаки препинания и мат. символы.
    Убирает латиницу, китайский и прочий "бред".
    """
    return bool(re.search(r'[\u4e00-\u9fff]', text))



def rag_worker_process(child_conn):
    """Функция, которая выполняется в RAG-процессе"""
    
    try:
        API_KEY = os.getenv("API_KEY")
        API_BASE_URL = os.getenv("API_SERVER")
        rag_object = RAGFlow(api_key=API_KEY, base_url=API_BASE_URL)
        assistant = rag_object.list_chats(name="bot")[0]
        sname = str(datetime.datetime.now())
        session = assistant.create_session(sname)
        
        while True:
            if child_conn.poll():
                message = child_conn.recv()
                
                if isinstance(message, tuple) and len(message) == 2:
                    msg_type, content = message
                elif isinstance(message, dict):
                    msg_type = message.get("type")
                    content = message.get("path")
                else:
                    continue
                
                if msg_type == 'question':
                    try:
                        start_time = datetime.datetime.now()
                        response = ""
                        
                        for ans in session.ask(content, stream=True):
                            response = ans.content
                            child_conn.send(('chunk', response))
                            time.sleep(0.01)
                        
                        response_time = (datetime.datetime.now() - start_time).total_seconds()
                        child_conn.send(('time', f"{response_time:.2f}"))
                        
                    except Exception as e:
                        child_conn.send(('error', str(e)))
                    finally:
                        child_conn.send(('done', ''))
                
                elif msg_type == 'exit':
                    break
                
                elif msg_type == 'file':
                    dataset = rag_object.list_datasets()[0]
                    print(f"Получен файл: {content}")
                    try:
                        with open(content, "rb") as f:
                            dataset.upload_documents([{
                                "displayed_name": os.path.basename(content), 
                                "blob": f.read()
                            }])
                        docs = dataset.list_documents()[0]
                        dataset.async_parse_documents([docs.id])
                        db = rag_object.get_dataset("db")
                        while (db.list_documents()[0].progress != 1):
                            db = rag_object.get_dataset("db")
                            time.sleep(0.5)
                        child_conn.send(('file_processed', f"Файл {os.path.basename(content)} успешно обработан"))
                        
                    except Exception as e:
                        child_conn.send(('error', f"Ошибка обработки файла: {str(e)}"))

                        
                    except Exception as e:
                        child_conn.send(('error', f"Ошибка обработки файла: {str(e)}"))
                    
    except Exception as e:
        child_conn.send(('error', f"RAG worker init failed: {str(e)}"))
    finally:
        child_conn.close()

class ChatWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Бот-Чат с RAGFlow")
        self.setGeometry(100, 100, 600, 500)
        self.window
        
        self.parent_conn, child_conn = Pipe()
        
        self.rag_process = Process(
            target=rag_worker_process,
            args=(child_conn,),
            daemon=False
        )
        self.rag_process.start()
        
        self.communication_timer = QTimer()
        self.communication_timer.timeout.connect(self.check_rag_messages)
        self.communication_timer.start(100)
        
        self.init_ui()
        
    def init_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        layout = QVBoxLayout()
        central_widget.setLayout(layout)
        
        self.message_display = QTextEdit()
        self.message_display.setReadOnly(True)
        self.message_display.setAcceptRichText(True)
        self.message_display.setStyleSheet("""
            QTextEdit {
                font-size: 14px;
                background-color: #f5f5f5;
                border: 1px solid #ddd;
                border-radius: 5px;
                padding: 10px;
            }
        """)
        layout.addWidget(self.message_display)
        
        self.upload_button = QPushButton("Загрузить файл")
        self.upload_button.setStyleSheet("""
            QPushButton {
                font-size: 14px;
                padding: 8px 15px;
                background-color: #2196F3;
                color: white;
                border: none;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #1976D2;
            }
        """)
        self.upload_button.clicked.connect(self.upload_file)
        layout.addWidget(self.upload_button)
        
        input_layout = QHBoxLayout()
        layout.addLayout(input_layout)
        
        self.message_input = QLineEdit()
        self.message_input.setPlaceholderText("Введите сообщение...")
        self.message_input.setStyleSheet("""
            QLineEdit {
                font-size: 14px;
                padding: 8px;
                border: 1px solid #ddd;
                border-radius: 5px;
            }
        """)
        input_layout.addWidget(self.message_input)
        
        self.send_button = QPushButton("Отправить")
        self.send_button.setStyleSheet("""
            QPushButton {
                font-size: 14px;
                padding: 8px 15px;
                background-color: #4CAF50;
                color: white;
                border: none;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
        """)
        self.send_button.clicked.connect(self.send_message)
        input_layout.addWidget(self.send_button)
        
        button_height = 40
        self.upload_button.setFixedHeight(button_height)
        self.send_button.setFixedHeight(button_height)
        
        self.message_input.returnPressed.connect(self.send_message)
        self.thinking_timer = QTimer()
        self.thinking_timer.timeout.connect(self.update_thinking_animation)
        self.thinking_phases = ["|", "/", "—", "\\"]
        self.thinking_phase = 0
        self.current_response = ""
        self.response_in_progress = False
        self.bot_message_started = False
        self.last_processed_position = 0

    def upload_file(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, 
            "Выберите файл", 
            "", 
            "Все файлы (*);;PDF файлы (*.pdf)"
        )
        if file_path:
            self.parent_conn.send({"type": "file", "path": file_path})
            self.message_display.append(f"<span style='color: #2196F3;'>✓ Загружен файл: {os.path.basename(file_path)}. Идет обработка...</span>")

    def send_message(self):
        message = self.message_input.text().strip()
        if message and not self.response_in_progress:
            self.message_input.setEnabled(False)
            self.message_input.setPlaceholderText("Бот обрабатывает ваш запрос...")
            
            self.display_user_message(message)
            self.message_input.clear()
            
            self.show_thinking_indicator()
            self.response_in_progress = True
            self.current_response = ""
            self.bot_message_started = False
            self.last_processed_position = 0
            
            self.parent_conn.send(('question', message))

    def display_user_message(self, message):
        escaped_message = html.escape(message)  # Экранируем HTML
        self.message_display.append(f"<div style='color: #2c3e50; margin: 5px 0;'><b>Вы:</b> {escaped_message}</div>")

    def show_thinking_indicator(self):
        self.thinking_phase = 0
        self.message_display.append("<div style='color: #27ae60; margin: 5px 0;'><b>Бот:</b> думает ")
        self.thinking_line = self.message_document().lineCount() - 1
        self.thinking_timer.start(150)

    def message_document(self):
        """Вспомогательный метод для получения документа"""
        return self.message_display.document()

    def update_thinking_animation(self):
        if not self.response_in_progress:
            return
            
        self.thinking_phase = (self.thinking_phase + 1) % len(self.thinking_phases)
        symbol = self.thinking_phases[self.thinking_phase]
        
        block = self.message_document().findBlockByLineNumber(self.thinking_line)
        cursor = QTextCursor(block)
        cursor.select(QTextCursor.SelectionType.LineUnderCursor)
        
        cursor.removeSelectedText()
        cursor.insertHtml(f"<div style='color: #27ae60; margin: 5px 0;'><b>Бот:</b> думает {symbol}</div>")

    def check_rag_messages(self):
        while self.parent_conn.poll():
            msg_type, content = self.parent_conn.recv()
            
            if msg_type == 'chunk':
                self.process_response_chunk(content)
            elif msg_type == 'time':
                self.show_response_time(content)
            elif msg_type == 'error':
                self.show_error(content)
            elif msg_type == 'done':
                self.finish_response()
            elif msg_type == 'file_processed':
                self.message_display.append(f"<span style='color: #2196F3;'>✓ {content}</span>")
            
    def format_markdown_to_html(self, text):
        """Преобразует markdown-разметку в HTML с корректным переносом текста"""
        text = html.escape(text)
        
        text = re.sub(r'\*\*(.*?)\*\*', r'<b>\1</b>', text)
        
        text = re.sub(r'\*(.*?)\*', r'<i>\1</i>', text)
        
        
        text = text.replace('\n', '<br/>')
        return text


    def process_response_chunk(self, chunk):
        """Обрабатывает часть ответа от RAG"""
        if not self.response_in_progress:
            return

        # фильтруем: оставляем русский + мат. символы
        if to_russian(chunk):
            chunk = "Некорректный ответ. Введите ваш вопрос еще раз"
        if not chunk.strip():
            return  # если после фильтра пусто — не выводим

        self.current_response = chunk
            
        self.current_response = chunk
        
        if not self.bot_message_started:
            if self.thinking_timer.isActive():
                self.thinking_timer.stop()
            
            block = self.message_document().findBlockByLineNumber(self.thinking_line)
            cursor = QTextCursor(block)
            cursor.select(QTextCursor.SelectionType.LineUnderCursor)
            cursor.removeSelectedText()
            
            cursor.movePosition(QTextCursor.MoveOperation.End)
            cursor.insertHtml("<div style='color: #000000; margin: 5px 0;'><b>Бот:</b> ")
            self.bot_message_started = True
        
        formatted_text = self.format_markdown_to_html(chunk)
        
        cursor = QTextCursor(self.message_document())
        cursor.movePosition(QTextCursor.MoveOperation.End)
        
        cursor.movePosition(QTextCursor.MoveOperation.StartOfBlock, QTextCursor.MoveMode.KeepAnchor)
        selected_text = cursor.selectedText()
        
        if "Бот:" in selected_text:
            cursor.removeSelectedText()
            cursor.insertHtml(f"<div style='color: #000000; margin: 5px 0;'><b>Бот:</b> {formatted_text}")

    def show_response_time(self, time_str):
        """Показывает время ответа"""
        self.message_display.append(f"<div style='color: #7f8c8d; font-size: 12px; margin: 5px 0;'>Ответ занял: {time_str} секунд</div>")

    def show_error(self, error):
        """Показывает ошибку"""
        safe_error = html.escape(error)
        self.message_display.append(f"<div style='color: #e74c3c; margin: 5px 0;'><b>Ошибка:</b> {safe_error}</div>")

    def finish_response(self):
        """Завершает обработку ответа"""
        self.response_in_progress = False
        self.message_input.setEnabled(True)
        self.message_input.setPlaceholderText("Введите сообщение...")
        self.message_input.setFocus()
        self.message_display.ensureCursorVisible()
        self.last_processed_position = 0

    def closeEvent(self, event):
        """Обработчик закрытия окна"""
        if hasattr(self, 'rag_process') and self.rag_process.is_alive():
            try:
                self.parent_conn.send(('exit', ''))
                self.rag_process.join(timeout=2)
                if self.rag_process.is_alive():
                    self.rag_process.terminate()
            except:
                pass
        if hasattr(self, 'parent_conn'):
            try:
                self.parent_conn.close()
            except:
                pass
        event.accept()  # Принимаем событие закрытия

if __name__ == "__main__":
    lock_file = os.path.join(tempfile.gettempdir(), "RAGFlowChatApp.lock")
    multiprocessing.freeze_support()
    try:
        # Для Windows
        if os.name == 'nt':
            import msvcrt
            lock_file_handle = open(lock_file, 'w')
            try:
                msvcrt.locking(lock_file_handle.fileno(), msvcrt.LK_NBLCK, 1)
            except IOError:
                sys.exit(0)  # Приложение уже запущено
                
    except Exception:
        pass  # В случае ошибки просто продолжаем
    
    app = QApplication(sys.argv)
    window = ChatWindow()
    window.show()
    sys.exit(app.exec())