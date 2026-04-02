import os
import random
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from src.quiz.vocab_manager import VocabManager

app = FastAPI(title="Vocab Quiz UI")
manager = VocabManager()

# Static Files
static_dir = os.path.join(os.path.dirname(__file__), "static")
if not os.path.exists(static_dir):
    os.makedirs(static_dir)

app.mount("/static", StaticFiles(directory=static_dir), name="static")

@app.get("/")
def read_index():
    return FileResponse(os.path.join(static_dir, "index.html"))

@app.get("/api/status")
def get_status():
    has_local = manager.has_local_data()
    count = len(manager.load_local_data()) if has_local else 0
    return {"has_local_data": has_local, "word_count": count}

@app.post("/api/download")
def download_data():
    try:
        data = manager.download_from_notion()
        return {"success": True, "word_count": len(data)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/questions")
def get_questions(num: int = 10):
    if not manager.has_local_data():
        raise HTTPException(status_code=400, detail="No local data available. Please download first.")
        
    vocab_list = manager.load_local_data()
    if len(vocab_list) < 4:
        raise HTTPException(status_code=400, detail="Not enough data (needs at least 4 items) to run the quiz.")
        
    questions_count = min(num, len(vocab_list))
    target_words = random.sample(vocab_list, questions_count)
    
    quiz_data = []
    
    for target in target_words:
        correct_meaning = target["meaning"]
        all_unique_meanings = list(set([v["meaning"] for v in vocab_list if v["meaning"] != correct_meaning]))
        
        if len(all_unique_meanings) >= 3:
            distractors = random.sample(all_unique_meanings, 3)
        else:
            distractors = []
            while len(distractors) < 3:
                 candidate = random.choice(vocab_list)
                 if candidate["meaning"] != correct_meaning:
                     distractors.append(candidate["meaning"])
                     
        choices = distractors + [correct_meaning]
        random.shuffle(choices)
        
        correct_idx = choices.index(correct_meaning)
        
        quiz_data.append({
            "word": target["word"],
            "choices": choices,
            "correct_idx": correct_idx, # 0-indexed for frontend array
            "pinyin": target.get("pinyin", ""),
            "context_cn": target.get("context_cn", ""),
            "meaning": correct_meaning
        })
        
    return {"questions": quiz_data}
