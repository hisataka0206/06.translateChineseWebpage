import os
import random
import yaml
import time
from dotenv import load_dotenv
from notion_client import Client

class VocabQuiz:
    def __init__(self, config_path="config/config.yaml"):
        # Load Config
        with open(config_path, "r") as f:
            self.config = yaml.safe_load(f)
            
        load_dotenv()
        
        # Notion Setup
        self.notion_token = os.getenv("NOTION_TOKEN") or (self.config.get("notion") or {}).get("token")
        if not self.notion_token:
             raise ValueError("NOTION_TOKEN not found in environment or config.")
        self.notion = Client(auth=self.notion_token)
        
        self.chinese_dictionary_id = (self.config.get("notion") or {}).get("chinese_dictionary_id")
        if not self.chinese_dictionary_id:
             raise ValueError("chinese_dictionary_id not found in config.")
        
        # Prepare DB ID
        self.db_id = self.chinese_dictionary_id.split("?")[0]
        self.vocab_list = []

    def fetch_vocabulary(self):
        print("Notionから単語データを取得しています...")
        results = []
        has_more = True
        start_cursor = None
        
        while has_more:
            try:
                response = self.notion.databases.query(
                    database_id=self.db_id,
                    start_cursor=start_cursor
                )
                results.extend(response.get("results", []))
                has_more = response.get("has_more", False)
                start_cursor = response.get("next_cursor")
            except Exception as e:
                print(f"Failed to fetch dictionary: {e}")
                break
                
        # Parse results
        for page in results:
            props = page.get("properties", {})
            
            # Get Word
            word = ""
            if "Word" in props and "title" in props["Word"]:
                title_arr = props["Word"]["title"]
                if title_arr:
                    word = "".join([t.get("plain_text", "") for t in title_arr])
            
            # Get Meaning_ja
            meaning = ""
            if "Meaning_ja" in props and "rich_text" in props["Meaning_ja"]:
                rt_arr = props["Meaning_ja"]["rich_text"]
                if rt_arr:
                    meaning = "".join([t.get("plain_text", "") for t in rt_arr])
                    
            # Get Pinyin
            pinyin = ""
            if "Pinyin" in props and "rich_text" in props["Pinyin"]:
                rt_arr = props["Pinyin"]["rich_text"]
                if rt_arr:
                    pinyin = "".join([t.get("plain_text", "") for t in rt_arr])
                    
            # Get ContextCn (Optional)
            context_cn = ""
            if "ContextCn" in props and "rich_text" in props["ContextCn"]:
                rt_arr = props["ContextCn"]["rich_text"]
                if rt_arr:
                    context_cn = "".join([t.get("plain_text", "") for t in rt_arr])
            
            if word and meaning:
                self.vocab_list.append({
                    "word": word,
                    "meaning": meaning,
                    "pinyin": pinyin,
                    "context_cn": context_cn
                })
                
        print(f"取得完了: {len(self.vocab_list)} 件の単語が登録されています。\n")
        
    def run_quiz(self, num_questions=10):
        if len(self.vocab_list) < 4:
            print("エラー: 辞書に有効な単語(中国語と意味の両方が登録されているもの)が4件未満のため、4択クイズを実行できません。")
            return
            
        questions = min(num_questions, len(self.vocab_list))
        print(f"=== 中国語 単語テスト ({questions}問) ===")
        print("中国語の意味として正しいものを1〜4から選んでください。\n")
        
        # Select target words randomly
        target_words = random.sample(self.vocab_list, questions)
        score = 0
        
        for i, target in enumerate(target_words, 1):
            correct_meaning = target["meaning"]
            
            # Select 3 distractors
            # To ensure strict uniqueness of distractors in case some words have identical meanings
            all_unique_meanings = list(set([v["meaning"] for v in self.vocab_list if v["meaning"] != correct_meaning]))
            
            # If we don't have at least 3 unique wrong meanings, just pick what we can and maybe repeat 
            # (though our check len(vocab_list) >= 4 makes extremely unlucky cases rare but possible 
            # if multiple words share the exact same meaning)
            if len(all_unique_meanings) >= 3:
                distractors = random.sample(all_unique_meanings, 3)
            else:
                 # fallback to random choices, allowing duplicates
                distractors = []
                while len(distractors) < 3:
                     candidate = random.choice(self.vocab_list)
                     if candidate["meaning"] != correct_meaning:
                         distractors.append(candidate["meaning"])
                         
            choices = distractors + [correct_meaning]
            random.shuffle(choices)
            
            correct_idx = choices.index(correct_meaning) + 1
            
            print(f"【第{i}問】 {target['word']}")
            for j, c in enumerate(choices, 1):
                print(f"  {j}. {c}")
                
            # Get user input
            while True:
                try:
                    ans = input("\n答えを番号(1-4)で入力してください: ").strip()
                    if not ans:
                        continue
                    ans_idx = int(ans)
                    if 1 <= ans_idx <= 4:
                        break
                    print("1から4までの数字で入力してください。")
                except ValueError:
                    print("数字を入力してください。")
                except EOFError:
                    print("\nテストを中断します。")
                    return
            
            # Check answer
            if ans_idx == correct_idx:
                print("\n✅ 正解！")
                score += 1
            else:
                print(f"\n❌ 不正解... 正解は {correct_idx}. {correct_meaning} でした。")
            
            if target["pinyin"]:
                print(f"  ピンイン: {target['pinyin']}")
            if target["context_cn"]:
                 print(f"  例文: {target['context_cn']}")
                 
            print("-" * 40 + "\n")
            time.sleep(1) # Small pause for readability
            
        print("=== テスト結果 ===")
        print(f"正答率: {score}/{questions} ({int(score/questions*100)}%)")
        if score == questions:
            print("パーフェクト！素晴らしいです🎉")
        elif score >= questions * 0.8:
            print("よくできました！👍")
        else:
            print("さらに復習して定着させましょう！💪")

if __name__ == "__main__":
    try:
        quiz = VocabQuiz()
        quiz.fetch_vocabulary()
        quiz.run_quiz()
    except KeyboardInterrupt:
         print("\nテストを終了します。お疲れ様でした！")
    except Exception as e:
         print(f"\nエラーが発生しました: {e}")
