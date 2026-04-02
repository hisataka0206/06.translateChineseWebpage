const startScreen = document.getElementById('start-screen');
const loadingScreen = document.getElementById('loading-screen');
const quizScreen = document.getElementById('quiz-screen');
const resultsScreen = document.getElementById('results-screen');

const btnLocal = document.getElementById('btn-local');
const btnDownload = document.getElementById('btn-download');
const btnNext = document.getElementById('btn-next');
const btnRestart = document.getElementById('btn-restart');
const btnHome = document.getElementById('btn-home');

let questions = [];
let currentQuestionIndex = 0;
let score = 0;

// Init
async function checkStatus() {
    try {
        const res = await fetch('/api/status');
        const data = await res.json();
        const statusText = document.getElementById('local-status');
        
        if (data.has_local_data) {
            statusText.innerText = `ローカルデータ: ${data.word_count}件の単語が利用可能です。`;
            btnLocal.disabled = false;
        } else {
            statusText.innerText = `ローカルデータが見つかりません。Notionからダウンロードしてください。`;
            btnLocal.disabled = true;
        }
    } catch (e) {
        document.getElementById('local-status').innerText = "ステータス取得エラー";
    }
}

function showScreen(screen) {
    document.querySelectorAll('.screen').forEach(s => s.classList.remove('active'));
    screen.classList.add('active');
}

// Event Listeners
btnLocal.addEventListener('click', async () => {
    await startQuiz();
});

btnDownload.addEventListener('click', async () => {
    showScreen(loadingScreen);
    try {
        const res = await fetch('/api/download', { method: 'POST' });
        const data = await res.json();
        if (data.success) {
            await startQuiz();
        } else {
            alert('Download failed.');
            checkStatus();
            showScreen(startScreen);
        }
    } catch (e) {
        alert('API Error during download');
        checkStatus();
        showScreen(startScreen);
    }
});

async function startQuiz() {
    try {
        const res = await fetch('/api/questions?num=10');
        const data = await res.json();
        if (data.questions) {
            questions = data.questions;
            currentQuestionIndex = 0;
            score = 0;
            renderQuestion();
            showScreen(quizScreen);
        } else {
            alert('Failed to load questions.');
            showScreen(startScreen);
        }
    } catch (e) {
        alert('API Error while loading questions');
        showScreen(startScreen);
    }
}

function renderQuestion() {
    const q = questions[currentQuestionIndex];
    document.getElementById('question-counter').innerText = `Question ${currentQuestionIndex + 1}/${questions.length}`;
    document.getElementById('score-display').innerText = `Score: ${score}`;
    document.getElementById('target-word').innerText = q.word;
    
    const container = document.getElementById('choices-container');
    container.innerHTML = '';
    
    document.getElementById('feedback-panel').classList.add('hidden');
    
    q.choices.forEach((choice, index) => {
        const btn = document.createElement('button');
        btn.className = 'choice-btn';
        btn.innerText = choice;
        btn.onclick = () => handleAnswer(index, btn, q);
        container.appendChild(btn);
    });
}

function handleAnswer(selectedIndex, btn, q) {
    const allBtns = document.querySelectorAll('.choice-btn');
    allBtns.forEach(b => b.disabled = true); // lock answers
    
    const isCorrect = selectedIndex === q.correct_idx;
    if (isCorrect) {
        btn.classList.add('correct');
        score++;
        document.getElementById('score-display').innerText = `Score: ${score}`;
    } else {
        btn.classList.add('incorrect');
        allBtns[q.correct_idx].classList.add('correct');
    }
    
    showFeedback(isCorrect, q);
}

function showFeedback(isCorrect, q) {
    const panel = document.getElementById('feedback-panel');
    panel.classList.remove('hidden', 'correct-bg', 'incorrect-bg');
    panel.classList.add(isCorrect ? 'correct-bg' : 'incorrect-bg');
    
    document.getElementById('feedback-title').innerText = isCorrect ? '🎉 正解！' : '❌ 不正解...';
    document.getElementById('feedback-meaning').innerText = q.meaning;
    document.getElementById('feedback-pinyin').innerText = q.pinyin || '-';
    document.getElementById('feedback-context').innerText = q.context_cn || '-';
}

btnNext.addEventListener('click', () => {
    currentQuestionIndex++;
    if (currentQuestionIndex < questions.length) {
        renderQuestion();
    } else {
        showResults();
    }
});

function showResults() {
    document.getElementById('final-score').innerText = score;
    const total = questions.length;
    document.querySelector('.total').innerText = `/${total}`;
    
    const msg = document.getElementById('result-message');
    if (score === total) msg.innerText = "パーフェクト！素晴らしいです🎉";
    else if (score >= total * 0.8) msg.innerText = "よくできました！👍";
    else msg.innerText = "さらに復習して定着させましょう！💪";
    
    // Update circle degree
    const circle = document.querySelector('.score-circle');
    const deg = (score / total) * 360;
    circle.style.background = `conic-gradient(var(--primary) ${deg}deg, rgba(255,255,255,0.1) 0)`;
    
    showScreen(resultsScreen);
}

btnRestart.addEventListener('click', startQuiz);
btnHome.addEventListener('click', () => {
    checkStatus();
    showScreen(startScreen);
});

// Initialize on load
checkStatus();
