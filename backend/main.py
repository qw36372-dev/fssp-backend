"""
ФССП Test Bot - Backend для Telegram Mini App
FastAPI сервер для тестирования с 11 специализациями
"""
from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import List, Dict, Optional, Set
from datetime import datetime, timedelta
import json
import random
import sqlite3
from pathlib import Path
import hashlib
import hmac
from urllib.parse import parse_qs

app = FastAPI(
    title="ФССП Test Bot API",
    description="API для Telegram Mini App тестирования сотрудников ФССП",
    version="1.0.0"
)

# CORS для работы с Telegram Mini App
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # В продакшене указать конкретный домен
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# === MODELS ===

class Question(BaseModel):
    id: int
    question: str
    options: List[str]
    correct_answers: Set[int]

class StartTestRequest(BaseModel):
    telegram_id: int
    full_name: str
    position: str
    department: str
    specialization: str
    difficulty: str

class SubmitAnswerRequest(BaseModel):
    telegram_id: int
    session_id: str
    question_id: int
    selected_answers: List[int]

class FinishTestRequest(BaseModel):
    telegram_id: int
    session_id: str

class TestResult(BaseModel):
    correct: int
    total: int
    percentage: float
    grade: str
    time_spent: int

# === DATABASE ===

DB_PATH = Path(__file__).parent / "test_bot.db"

def init_db():
    """Инициализация базы данных"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Таблица тестовых сессий
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS test_sessions (
            session_id TEXT PRIMARY KEY,
            telegram_id INTEGER NOT NULL,
            full_name TEXT NOT NULL,
            position TEXT NOT NULL,
            department TEXT NOT NULL,
            specialization TEXT NOT NULL,
            difficulty TEXT NOT NULL,
            started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            finished_at TIMESTAMP,
            status TEXT DEFAULT 'active'
        )
    """)
    
    # Таблица ответов
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS answers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL,
            question_id INTEGER NOT NULL,
            selected_answers TEXT NOT NULL,
            is_correct INTEGER DEFAULT 0,
            answered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (session_id) REFERENCES test_sessions(session_id)
        )
    """)
    
    # Таблица результатов
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL,
            telegram_id INTEGER NOT NULL,
            specialization TEXT NOT NULL,
            difficulty TEXT NOT NULL,
            correct_answers INTEGER NOT NULL,
            total_questions INTEGER NOT NULL,
            percentage REAL NOT NULL,
            grade TEXT NOT NULL,
            time_spent INTEGER NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (session_id) REFERENCES test_sessions(session_id)
        )
    """)
    
    # Таблица статистики
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS user_stats (
            telegram_id INTEGER PRIMARY KEY,
            first_name TEXT,
            last_name TEXT,
            username TEXT,
            total_tests INTEGER DEFAULT 0,
            last_activity TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    conn.commit()
    conn.close()

# === QUESTION LOADER ===

QUESTIONS_DIR = Path(__file__).parent.parent / "questions"

def load_questions(specialization: str) -> List[Dict]:
    """Загрузка вопросов из JSON"""
    file_path = QUESTIONS_DIR / f"{specialization}.json"
    if not file_path.exists():
        return []
    
    with open(file_path, 'r', encoding='utf-8') as f:
        return json.load(f)

def select_questions(specialization: str, difficulty: str, count: int) -> List[Question]:
    """Выбор случайных вопросов по уровню сложности"""
    all_questions = load_questions(specialization)
    if not all_questions:
        return []
    
    # Перемешиваем и берем нужное количество
    random.shuffle(all_questions)
    selected = all_questions[:count]
    
    # Преобразуем в модель Question
    questions = []
    for i, q in enumerate(selected):
        correct = set(int(x) for x in q['correct_answers'].split(','))
        questions.append(Question(
            id=i,
            question=q['question'],
            options=q['options'],
            correct_answers=correct
        ))
    
    return questions

# === HELPERS ===

DIFFICULTY_CONFIG = {
    "резерв": {"questions": 20, "time": 35},
    "базовый": {"questions": 30, "time": 25},
    "стандартный": {"questions": 40, "time": 20},
    "продвинутый": {"questions": 50, "time": 20}
}

SPECIALIZATIONS = {
    "oupds": "ООУПДС",
    "ispolniteli": "Исполнители",
    "aliment": "Алименты",
    "doznanie": "Дознание",
    "rozyisk": "Розыск",
    "prof": "Профподготовка",
    "oko": "ОКО",
    "informatika": "Информатизация",
    "kadry": "Кадры",
    "bezopasnost": "Безопасность",
    "upravlenie": "Управление"
}

def calculate_grade(percentage: float) -> str:
    """Расчет оценки по проценту правильных ответов"""
    if percentage >= 80:
        return "отлично"
    elif percentage >= 70:
        return "хорошо"
    elif percentage >= 60:
        return "удовлетворительно"
    else:
        return "неудовлетворительно"

def generate_session_id(telegram_id: int) -> str:
    """Генерация уникального ID сессии"""
    timestamp = datetime.now().isoformat()
    return hashlib.sha256(f"{telegram_id}{timestamp}".encode()).hexdigest()[:16]

# === ENDPOINTS ===

@app.on_event("startup")
async def startup_event():
    """Инициализация при запуске"""
    init_db()
    print("✅ Database initialized")

@app.get("/")
async def root():
    """Проверка работоспособности API"""
    return {
        "status": "ok",
        "service": "ФССП Test Bot API",
        "version": "1.0.0"
    }

@app.get("/api/specializations")
async def get_specializations():
    """Получение списка специализаций"""
    return {
        "specializations": [
            {"id": k, "name": v} for k, v in SPECIALIZATIONS.items()
        ]
    }

@app.get("/api/difficulties")
async def get_difficulties():
    """Получение уровней сложности"""
    return {
        "difficulties": [
            {
                "id": k,
                "name": k.capitalize(),
                "questions": v["questions"],
                "time_minutes": v["time"]
            }
            for k, v in DIFFICULTY_CONFIG.items()
        ]
    }

@app.post("/api/test/start")
async def start_test(request: StartTestRequest):
    """Начало теста - получение вопросов"""
    # Проверка специализации и сложности
    if request.specialization not in SPECIALIZATIONS:
        raise HTTPException(status_code=400, detail="Invalid specialization")
    
    if request.difficulty not in DIFFICULTY_CONFIG:
        raise HTTPException(status_code=400, detail="Invalid difficulty")
    
    # Генерация session_id
    session_id = generate_session_id(request.telegram_id)
    
    # Получение вопросов
    config = DIFFICULTY_CONFIG[request.difficulty]
    questions = select_questions(
        request.specialization,
        request.difficulty,
        config["questions"]
    )
    
    if not questions:
        raise HTTPException(status_code=500, detail="Failed to load questions")
    
    # Сохранение сессии в БД
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("""
        INSERT INTO test_sessions 
        (session_id, telegram_id, full_name, position, department, specialization, difficulty)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (
        session_id,
        request.telegram_id,
        request.full_name,
        request.position,
        request.department,
        request.specialization,
        request.difficulty
    ))
    
    conn.commit()
    conn.close()
    
    # Возвращаем вопросы БЕЗ правильных ответов
    return {
        "session_id": session_id,
        "time_minutes": config["time"],
        "questions": [
            {
                "id": q.id,
                "question": q.question,
                "options": q.options
            }
            for q in questions
        ],
        # Храним правильные ответы отдельно для проверки
        "_answers": {str(q.id): list(q.correct_answers) for q in questions}
    }

@app.post("/api/test/answer")
async def submit_answer(request: SubmitAnswerRequest):
    """Сохранение ответа на вопрос (без проверки правильности)"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Проверка существования сессии
    cursor.execute(
        "SELECT status FROM test_sessions WHERE session_id = ?",
        (request.session_id,)
    )
    row = cursor.fetchone()
    
    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail="Session not found")
    
    if row[0] != "active":
        conn.close()
        raise HTTPException(status_code=400, detail="Session is not active")
    
    # Сохранение ответа
    cursor.execute("""
        INSERT OR REPLACE INTO answers (session_id, question_id, selected_answers)
        VALUES (?, ?, ?)
    """, (
        request.session_id,
        request.question_id,
        ','.join(map(str, request.selected_answers))
    ))
    
    conn.commit()
    conn.close()
    
    return {"status": "ok"}

@app.post("/api/test/finish")
async def finish_test(request: FinishTestRequest):
    """Завершение теста и расчет результата"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Получение информации о сессии
    cursor.execute("""
        SELECT specialization, difficulty, started_at, full_name, position, department
        FROM test_sessions
        WHERE session_id = ? AND telegram_id = ? AND status = 'active'
    """, (request.session_id, request.telegram_id))
    
    session = cursor.fetchone()
    if not session:
        conn.close()
        raise HTTPException(status_code=404, detail="Active session not found")
    
    specialization, difficulty, started_at, full_name, position, department = session
    
    # Загрузка правильных ответов
    questions = select_questions(specialization, difficulty, DIFFICULTY_CONFIG[difficulty]["questions"])
    correct_map = {str(q.id): q.correct_answers for q in questions}
    
    # Получение ответов пользователя
    cursor.execute("""
        SELECT question_id, selected_answers
        FROM answers
        WHERE session_id = ?
    """, (request.session_id,))
    
    user_answers = cursor.fetchall()
    
    # Подсчет правильных ответов
    correct_count = 0
    total_count = len(questions)
    
    for question_id, selected_str in user_answers:
        selected = set(int(x) for x in selected_str.split(',') if x)
        correct = correct_map.get(str(question_id), set())
        
        if selected == correct:
            correct_count += 1
    
    # Расчет процента и оценки
    percentage = (correct_count / total_count * 100) if total_count > 0 else 0
    grade = calculate_grade(percentage)
    
    # Расчет времени
    start_time = datetime.fromisoformat(started_at)
    time_spent = int((datetime.now() - start_time).total_seconds() / 60)
    
    # Обновление статуса сессии
    cursor.execute("""
        UPDATE test_sessions
        SET status = 'finished', finished_at = CURRENT_TIMESTAMP
        WHERE session_id = ?
    """, (request.session_id,))
    
    # Сохранение результата
    cursor.execute("""
        INSERT INTO results 
        (session_id, telegram_id, specialization, difficulty, correct_answers, 
         total_questions, percentage, grade, time_spent)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        request.session_id,
        request.telegram_id,
        specialization,
        difficulty,
        correct_count,
        total_count,
        percentage,
        grade,
        time_spent
    ))
    
    # Обновление статистики пользователя
    cursor.execute("""
        INSERT INTO user_stats (telegram_id, total_tests)
        VALUES (?, 1)
        ON CONFLICT(telegram_id) DO UPDATE SET
            total_tests = total_tests + 1,
            last_activity = CURRENT_TIMESTAMP
    """, (request.telegram_id,))
    
    conn.commit()
    conn.close()
    
    return {
        "result": {
            "correct": correct_count,
            "total": total_count,
            "percentage": round(percentage, 1),
            "grade": grade,
            "time_spent": time_spent,
            "full_name": full_name,
            "position": position,
            "department": department,
            "specialization": SPECIALIZATIONS[specialization]
        }
    }

@app.get("/api/stats/{telegram_id}")
async def get_user_stats(telegram_id: int):
    """Получение статистики пользователя"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Общая статистика
    cursor.execute("""
        SELECT 
            COUNT(*) as total_tests,
            AVG(percentage) as avg_percentage,
            MAX(percentage) as best_percentage,
            SUM(CASE WHEN grade = 'отлично' THEN 1 ELSE 0 END) as excellent,
            SUM(CASE WHEN grade = 'хорошо' THEN 1 ELSE 0 END) as good,
            SUM(CASE WHEN grade = 'удовлетворительно' THEN 1 ELSE 0 END) as satisfactory,
            SUM(CASE WHEN grade = 'неудовлетворительно' THEN 1 ELSE 0 END) as fail
        FROM results
        WHERE telegram_id = ?
    """, (telegram_id,))
    
    stats = cursor.fetchone()
    
    # Последние результаты
    cursor.execute("""
        SELECT specialization, difficulty, grade, percentage, created_at
        FROM results
        WHERE telegram_id = ?
        ORDER BY created_at DESC
        LIMIT 5
    """, (telegram_id,))
    
    recent = cursor.fetchall()
    
    conn.close()
    
    return {
        "total_tests": stats[0] or 0,
        "avg_percentage": round(stats[1] or 0, 1),
        "best_percentage": round(stats[2] or 0, 1),
        "grades": {
            "excellent": stats[3] or 0,
            "good": stats[4] or 0,
            "satisfactory": stats[5] or 0,
            "fail": stats[6] or 0
        },
        "recent_results": [
            {
                "specialization": SPECIALIZATIONS.get(r[0], r[0]),
                "difficulty": r[1],
                "grade": r[2],
                "percentage": round(r[3], 1),
                "date": r[4]
            }
            for r in recent
        ]
    }

@app.get("/api/result/{session_id}")
async def get_test_result(session_id: str, telegram_id: int):
    """Получение детального результата теста с правильными ответами"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Проверка доступа
    cursor.execute("""
        SELECT specialization, difficulty, status
        FROM test_sessions
        WHERE session_id = ? AND telegram_id = ?
    """, (session_id, telegram_id))
    
    session = cursor.fetchone()
    if not session:
        conn.close()
        raise HTTPException(status_code=404, detail="Session not found")
    
    specialization, difficulty, status = session
    
    if status != "finished":
        conn.close()
        raise HTTPException(status_code=400, detail="Test not finished yet")
    
    # Загрузка вопросов с правильными ответами
    questions = select_questions(specialization, difficulty, DIFFICULTY_CONFIG[difficulty]["questions"])
    
    # Получение ответов пользователя
    cursor.execute("""
        SELECT question_id, selected_answers
        FROM answers
        WHERE session_id = ?
    """, (session_id,))
    
    user_answers_raw = cursor.fetchall()
    user_answers = {
        int(qid): set(int(x) for x in ans.split(',') if x)
        for qid, ans in user_answers_raw
    }
    
    conn.close()
    
    # Формирование детального результата
    detailed_results = []
    for q in questions:
        user_ans = user_answers.get(q.id, set())
        is_correct = user_ans == q.correct_answers
        
        detailed_results.append({
            "question_id": q.id,
            "question": q.question,
            "options": q.options,
            "user_answers": sorted(list(user_ans)),
            "correct_answers": sorted(list(q.correct_answers)),
            "is_correct": is_correct
        })
    
    return {
        "questions": detailed_results
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
