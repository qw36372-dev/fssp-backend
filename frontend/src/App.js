import React, { useState, useEffect } from 'react';
import './App.css';

// API Configuration
const API_BASE_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000';

// Telegram WebApp SDK
const tg = window.Telegram?.WebApp;

function App() {
  // States
  const [screen, setScreen] = useState('specialization'); // specialization, userInfo, difficulty, test, result, stats
  const [userData, setUserData] = useState({
    telegram_id: 0,
    full_name: '',
    position: '',
    department: '',
    specialization: '',
    difficulty: ''
  });
  
  const [specializations, setSpecializations] = useState([]);
  const [difficulties, setDifficulties] = useState([]);
  const [questions, setQuestions] = useState([]);
  const [currentQuestion, setCurrentQuestion] = useState(0);
  const [selectedAnswers, setSelectedAnswers] = useState(new Set());
  const [answersHistory, setAnswersHistory] = useState({});
  const [sessionId, setSessionId] = useState('');
  const [timeLeft, setTimeLeft] = useState(0);
  const [testResult, setTestResult] = useState(null);
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(false);

  // Initialize Telegram WebApp
  useEffect(() => {
    if (tg) {
      tg.ready();
      tg.expand();
      
      // Set theme
      document.body.classList.add('telegram-theme');
      
      // Get user data
      const user = tg.initDataUnsafe?.user;
      if (user) {
        setUserData(prev => ({
          ...prev,
          telegram_id: user.id
        }));
      }
    }
    
    // Load specializations
    loadSpecializations();
  }, []);

  // Timer
  useEffect(() => {
    if (screen === 'test' && timeLeft > 0) {
      const timer = setInterval(() => {
        setTimeLeft(prev => {
          if (prev <= 1) {
            handleFinishTest();
            return 0;
          }
          return prev - 1;
        });
      }, 1000);
      
      return () => clearInterval(timer);
    }
  }, [screen, timeLeft]);

  // API Calls
  const loadSpecializations = async () => {
    try {
      const response = await fetch(`${API_BASE_URL}/api/specializations`);
      const data = await response.json();
      setSpecializations(data.specializations);
    } catch (error) {
      console.error('Failed to load specializations:', error);
      tg?.showAlert('Ошибка загрузки специализаций');
    }
  };

  const loadDifficulties = async () => {
    try {
      const response = await fetch(`${API_BASE_URL}/api/difficulties`);
      const data = await response.json();
      setDifficulties(data.difficulties);
    } catch (error) {
      console.error('Failed to load difficulties:', error);
      tg?.showAlert('Ошибка загрузки уровней сложности');
    }
  };

  const startTest = async () => {
    setLoading(true);
    try {
      const response = await fetch(`${API_BASE_URL}/api/test/start`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(userData)
      });
      
      const data = await response.json();
      setSessionId(data.session_id);
      setQuestions(data.questions);
      setTimeLeft(data.time_minutes * 60);
      setCurrentQuestion(0);
      setSelectedAnswers(new Set());
      setAnswersHistory({});
      setScreen('test');
    } catch (error) {
      console.error('Failed to start test:', error);
      tg?.showAlert('Ошибка начала теста');
    } finally {
      setLoading(false);
    }
  };

  const submitAnswer = async () => {
    try {
      await fetch(`${API_BASE_URL}/api/test/answer`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          telegram_id: userData.telegram_id,
          session_id: sessionId,
          question_id: questions[currentQuestion].id,
          selected_answers: Array.from(selectedAnswers)
        })
      });
      
      // Save to history
      setAnswersHistory(prev => ({
        ...prev,
        [currentQuestion]: new Set(selectedAnswers)
      }));
      
      // Next question
      if (currentQuestion < questions.length - 1) {
        setCurrentQuestion(prev => prev + 1);
        setSelectedAnswers(answersHistory[currentQuestion + 1] || new Set());
      } else {
        handleFinishTest();
      }
    } catch (error) {
      console.error('Failed to submit answer:', error);
    }
  };

  const handleFinishTest = async () => {
    setLoading(true);
    try {
      const response = await fetch(`${API_BASE_URL}/api/test/finish`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          telegram_id: userData.telegram_id,
          session_id: sessionId
        })
      });
      
      const data = await response.json();
      setTestResult(data.result);
      setScreen('result');
    } catch (error) {
      console.error('Failed to finish test:', error);
      tg?.showAlert('Ошибка завершения теста');
    } finally {
      setLoading(false);
    }
  };

  const loadStats = async () => {
    try {
      const response = await fetch(`${API_BASE_URL}/api/stats/${userData.telegram_id}`);
      const data = await response.json();
      setStats(data);
      setScreen('stats');
    } catch (error) {
      console.error('Failed to load stats:', error);
      tg?.showAlert('Ошибка загрузки статистики');
    }
  };

  // Handlers
  const selectSpecialization = (spec) => {
    setUserData(prev => ({ ...prev, specialization: spec.id }));
    setScreen('userInfo');
  };

  const submitUserInfo = () => {
    if (!userData.full_name || !userData.position || !userData.department) {
      tg?.showAlert('Пожалуйста, заполните все поля');
      return;
    }
    loadDifficulties();
    setScreen('difficulty');
  };

  const selectDifficulty = (diff) => {
    setUserData(prev => ({ ...prev, difficulty: diff.id }));
    startTest();
  };

  const toggleAnswer = (index) => {
    setSelectedAnswers(prev => {
      const newSet = new Set(prev);
      if (newSet.has(index)) {
        newSet.delete(index);
      } else {
        newSet.add(index);
      }
      return newSet;
    });
  };

  const goToPreviousQuestion = () => {
    if (currentQuestion > 0) {
      setCurrentQuestion(prev => prev - 1);
      setSelectedAnswers(answersHistory[currentQuestion - 1] || new Set());
    }
  };

  const formatTime = (seconds) => {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins}:${secs.toString().padStart(2, '0')}`;
  };

  const getGradeColor = (grade) => {
    switch (grade) {
      case 'отлично': return '#4CAF50';
      case 'хорошо': return '#2196F3';
      case 'удовлетворительно': return '#FF9800';
      default: return '#F44336';
    }
  };

  // Render Screens
  const renderSpecialization = () => (
    <div className="screen">
      <div className="header">
        <h1>🧪 ФССП Тест-бот</h1>
        <p>Выберите специализацию для прохождения теста</p>
      </div>
      
      <div className="card-grid">
        {specializations.map(spec => (
          <button
            key={spec.id}
            className="card-button"
            onClick={() => selectSpecialization(spec)}
          >
            {spec.name}
          </button>
        ))}
      </div>
      
      <button className="secondary-button" onClick={loadStats}>
        📊 Моя статистика
      </button>
    </div>
  );

  const renderUserInfo = () => (
    <div className="screen">
      <div className="header">
        <h2>Информация о сотруднике</h2>
      </div>
      
      <div className="form">
        <div className="form-group">
          <label>ФИО</label>
          <input
            type="text"
            value={userData.full_name}
            onChange={(e) => setUserData(prev => ({ ...prev, full_name: e.target.value }))}
            placeholder="Иванов Иван Иванович"
          />
        </div>
        
        <div className="form-group">
          <label>Должность</label>
          <input
            type="text"
            value={userData.position}
            onChange={(e) => setUserData(prev => ({ ...prev, position: e.target.value }))}
            placeholder="Судебный пристав-исполнитель"
          />
        </div>
        
        <div className="form-group">
          <label>Подразделение</label>
          <input
            type="text"
            value={userData.department}
            onChange={(e) => setUserData(prev => ({ ...prev, department: e.target.value }))}
            placeholder="ОСП по г. Москва"
          />
        </div>
      </div>
      
      <div className="button-group">
        <button className="secondary-button" onClick={() => setScreen('specialization')}>
          ← Назад
        </button>
        <button className="primary-button" onClick={submitUserInfo}>
          Далее →
        </button>
      </div>
    </div>
  );

  const renderDifficulty = () => (
    <div className="screen">
      <div className="header">
        <h2>Уровень сложности</h2>
      </div>
      
      <div className="card-grid">
        {difficulties.map(diff => (
          <button
            key={diff.id}
            className="difficulty-card"
            onClick={() => selectDifficulty(diff)}
            disabled={loading}
          >
            <h3>{diff.name}</h3>
            <p>Вопросов: {diff.questions}</p>
            <p>Время: {diff.time_minutes} мин</p>
          </button>
        ))}
      </div>
      
      <button className="secondary-button" onClick={() => setScreen('userInfo')}>
        ← Назад
      </button>
    </div>
  );

  const renderTest = () => {
    const question = questions[currentQuestion];
    const numberEmojis = ['1️⃣', '2️⃣', '3️⃣', '4️⃣', '5️⃣'];
    
    return (
      <div className="screen test-screen">
        <div className="test-header">
          <div className="progress-bar">
            <div 
              className="progress-fill" 
              style={{ width: `${((currentQuestion + 1) / questions.length) * 100}%` }}
            />
          </div>
          
          <div className="test-info">
            <span>Вопрос {currentQuestion + 1} из {questions.length}</span>
            <span className="timer" style={{ color: timeLeft < 60 ? '#F44336' : '#4CAF50' }}>
              ⏰ {formatTime(timeLeft)}
            </span>
          </div>
        </div>
        
        <div className="question-card">
          <h3>{question.question}</h3>
          
          <div className="options">
            {question.options.map((option, index) => (
              <button
                key={index}
                className={`option-button ${selectedAnswers.has(index + 1) ? 'selected' : ''}`}
                onClick={() => toggleAnswer(index + 1)}
              >
                <span className="option-number">{numberEmojis[index]}</span>
                <span className="option-text">{option}</span>
                {selectedAnswers.has(index + 1) && <span className="check-mark">✅</span>}
              </button>
            ))}
          </div>
        </div>
        
        <div className="button-group">
          <button 
            className="secondary-button"
            onClick={goToPreviousQuestion}
            disabled={currentQuestion === 0}
          >
            ← Назад
          </button>
          
          <button 
            className="primary-button"
            onClick={submitAnswer}
            disabled={selectedAnswers.size === 0}
          >
            {currentQuestion === questions.length - 1 ? 'Завершить' : 'Далее →'}
          </button>
        </div>
      </div>
    );
  };

  const renderResult = () => {
    if (!testResult) return null;
    
    const gradeColor = getGradeColor(testResult.grade);
    
    return (
      <div className="screen result-screen">
        <div className="result-card" style={{ borderColor: gradeColor }}>
          <h1>🎉 Тест завершен!</h1>
          
          <div className="result-score" style={{ color: gradeColor }}>
            <div className="percentage">{testResult.percentage}%</div>
            <div className="grade">{testResult.grade.toUpperCase()}</div>
          </div>
          
          <div className="result-details">
            <div className="detail-row">
              <span>Правильных ответов:</span>
              <strong>{testResult.correct} из {testResult.total}</strong>
            </div>
            <div className="detail-row">
              <span>Время выполнения:</span>
              <strong>{testResult.time_spent} мин</strong>
            </div>
            <div className="detail-row">
              <span>ФИО:</span>
              <strong>{testResult.full_name}</strong>
            </div>
            <div className="detail-row">
              <span>Должность:</span>
              <strong>{testResult.position}</strong>
            </div>
            <div className="detail-row">
              <span>Подразделение:</span>
              <strong>{testResult.department}</strong>
            </div>
            <div className="detail-row">
              <span>Специализация:</span>
              <strong>{testResult.specialization}</strong>
            </div>
          </div>
        </div>
        
        <div className="button-group">
          <button className="secondary-button" onClick={() => setScreen('specialization')}>
            🏠 Главное меню
          </button>
          <button className="primary-button" onClick={() => setScreen('specialization')}>
            🔄 Пройти еще тест
          </button>
        </div>
      </div>
    );
  };

  const renderStats = () => {
    if (!stats) return null;
    
    return (
      <div className="screen stats-screen">
        <div className="header">
          <h2>📊 Моя статистика</h2>
        </div>
        
        <div className="stats-card">
          <div className="stat-item">
            <span>Всего тестов:</span>
            <strong>{stats.total_tests}</strong>
          </div>
          <div className="stat-item">
            <span>Средний балл:</span>
            <strong>{stats.avg_percentage}%</strong>
          </div>
          <div className="stat-item">
            <span>Лучший результат:</span>
            <strong>{stats.best_percentage}%</strong>
          </div>
        </div>
        
        <div className="grades-card">
          <h3>Оценки</h3>
          <div className="grade-item">
            <span>🥇 Отлично:</span>
            <strong>{stats.grades.excellent}</strong>
          </div>
          <div className="grade-item">
            <span>🥈 Хорошо:</span>
            <strong>{stats.grades.good}</strong>
          </div>
          <div className="grade-item">
            <span>🥉 Удовлетворительно:</span>
            <strong>{stats.grades.satisfactory}</strong>
          </div>
          <div className="grade-item">
            <span>❌ Неудовлетворительно:</span>
            <strong>{stats.grades.fail}</strong>
          </div>
        </div>
        
        {stats.recent_results.length > 0 && (
          <div className="recent-card">
            <h3>Последние результаты</h3>
            {stats.recent_results.map((result, index) => (
              <div key={index} className="recent-item">
                <div>
                  <strong>{result.specialization}</strong>
                  <span> ({result.difficulty})</span>
                </div>
                <div>
                  <span className="grade-badge" style={{ backgroundColor: getGradeColor(result.grade) }}>
                    {result.grade}
                  </span>
                  <span> {result.percentage}%</span>
                </div>
              </div>
            ))}
          </div>
        )}
        
        <button className="secondary-button" onClick={() => setScreen('specialization')}>
          ← Назад
        </button>
      </div>
    );
  };

  // Main Render
  return (
    <div className="App">
      {loading && <div className="loading-overlay">Загрузка...</div>}
      
      {screen === 'specialization' && renderSpecialization()}
      {screen === 'userInfo' && renderUserInfo()}
      {screen === 'difficulty' && renderDifficulty()}
      {screen === 'test' && renderTest()}
      {screen === 'result' && renderResult()}
      {screen === 'stats' && renderStats()}
    </div>
  );
}

export default App;
