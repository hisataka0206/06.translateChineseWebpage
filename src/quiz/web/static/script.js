const startScreen = document.getElementById('start-screen');
const quizScreen = document.getElementById('quiz-screen');
const resultsScreen = document.getElementById('results-screen');

const btnStart = document.getElementById('btn-start');
const btnNext = document.getElementById('btn-next');
const btnRestart = document.getElementById('btn-restart');
const btnHome = document.getElementById('btn-home');
const countBtns = document.querySelectorAll('.count-btn');
const statusText = document.getElementById('local-status');
const setupPanel = document.getElementById('setup-panel');

let fullVocabList = [];
let questions = [];
let currentQuestionIndex = 0;
let score = 0;
let selectedCount = 10;

// Utility: Array Shuffle (Fisher-Yates)
function shuffle(array) {
    let currentIndex = array.length;
    while (currentIndex != 0) {
        let randomIndex = Math.floor(Math.random() * currentIndex);
        currentIndex--;
        [array[currentIndex], array[randomIndex]] = [array[randomIndex], array[currentIndex]];
    }
    return array;
}

// Init
async function loadVocab() {
    try {
        statusText.innerText = "辞書データを読み込み中...";
        // Fetch static json file
        const res = await fetch('local_vocab.json');
        if (!res.ok) throw new Error("JSON Fetch Failed");
        
        fullVocabList = await res.json();
        
        if (fullVocabList.length >= 4) {
            statusText.innerText = `読み込み完了: ${fullVocabList.length} 件の単語が登録されています。`;
            setupPanel.classList.remove('hidden');
        } else {
            statusText.innerText = `エラー: 辞書データが不足しています（最低4単語必要です）。`;
        }
    } catch (e) {
        console.error("Vocabulary Load Error:", e);
        statusText.innerText = "辞書データの読み込みに失敗しました。GitHub Actionsでの初回デプロイをお待ちください。";
    }
}

function showScreen(screen) {
    document.querySelectorAll('.screen').forEach(s => s.classList.remove('active'));
    screen.classList.add('active');
}

// Handle question count selection
countBtns.forEach(btn => {
    btn.addEventListener('click', (e) => {
        countBtns.forEach(b => b.classList.remove('active-count'));
        e.target.classList.add('active-count');
        selectedCount = parseInt(e.target.getAttribute('data-count'));
    });
});

// Start Quiz logic (generate questions client-side)
btnStart.addEventListener('click', () => {
    const qCount = Math.min(selectedCount, fullVocabList.length);
    if (qCount < 4) return alert("データが足りません");
    
    // Pick random target words
    const shuffledVocab = shuffle([...fullVocabList]);
    const targetWords = shuffledVocab.slice(0, qCount);
    
    questions = targetWords.map(target => {
        const correctMeaning = target.meaning;
        
        // Find distractors
        let uniqueMeanings = [...new Set(fullVocabList.filter(v => v.meaning !== correctMeaning).map(v => v.meaning))];
        let distractors = [];
        
        if (uniqueMeanings.length >= 3) {
            distractors = shuffle(uniqueMeanings).slice(0, 3);
        } else {
            // Fallback
            let flatList = fullVocabList.filter(v => v.meaning !== correctMeaning).map(v => v.meaning);
            distractors = shuffle(flatList).slice(0, 3);
        }
        
        let choices = [...distractors, correctMeaning];
        choices = shuffle(choices);
        
        return {
            word: target.word,
            choices: choices,
            correct_idx: choices.indexOf(correctMeaning),
            pinyin: target.pinyin,
            context_cn: target.context_cn,
            meaning: correctMeaning
        };
    });
    
    currentQuestionIndex = 0;
    score = 0;
    renderQuestion();
    showScreen(quizScreen);
});

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

btnRestart.addEventListener('click', () => {
    showScreen(startScreen);
});
btnHome.addEventListener('click', () => {
    showScreen(startScreen);
});

// Initialize on load
loadVocab();
