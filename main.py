import os
from dotenv import load_dotenv
from src.script_gen import generate_long_script
from src.asset_fetcher import get_nasa_assets
from src.video_engine import create_chapter_video
from src.thumbnail_gen import create_pro_thumbnail

load_dotenv()

def main():
    topic = "The Mystery of Black Holes"
    api_key = os.getenv("GROQ_API_KEY")
    
    print("Step 1: Generating Script Chapters...")
    script_data = generate_long_script(topic, api_key)
    
    chapter_files = []
    
    for i, chapter in enumerate(script_data['chapters']):
        print(f"Processing Chapter {i+1}: {chapter['title']}")
        
        # Fetch assets for this chapter
        assets = get_nasa_assets(chapter['keywords'])
        
        # PLACEHOLDER: Here you would call your TTS function (edge-tts)
        # to generate 'chapter_audio.mp3' based on chapter['content']
        audio_path = f"chapter_{i}_audio.mp3" 
        
        # if os.path.exists(audio_path):
        #     out = create_chapter_video(audio_path, assets, f"chapter_{i}.mp4")
        #     chapter_files.append(out)

    # Final step: Generate Thumbnail using first chapter's first image
    first_asset = get_nasa_assets(script_data['chapters'][0]['keywords'])[0]['url']
    create_pro_thumbnail(first_asset, topic, "final_thumbnail.jpg")

if __name__ == "__main__":
    main()
