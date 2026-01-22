import ollama
import os

def analyze_image(image_path):
    """
    指定されたパスの画像を読み込み、VLMで内容を解説する関数
    """
    if not os.path.exists(image_path):
        print(f"エラー: {image_path} が見つかりません。")
        return

    print(f"--- 画像解析を開始します: {image_path} ---")

    # Ollamaを使用して画像解析を実行
    # モデル名はインストールしたものに合わせて適宜変更してください
    response = ollama.generate(
        model='moondream',
        prompt='なんて書いてあるのかを教えて',
        images=[image_path]
    )

    print("\n【AIの解析結果】")
    print(response['response'])

if __name__ == "__main__":
    # 解析したい画像ファイル名を指定
    target_file = 'IMG_2698.jpeg' 
    analyze_image(target_file)
