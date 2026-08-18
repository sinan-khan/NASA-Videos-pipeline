from moviepy.editor import VideoFileClip, AudioFileClip, ImageClip, concatenate_videoclips
import os

def create_chapter_video(audio_path, assets, output_path):
    audio = AudioFileClip(audio_path)
    target_duration = audio.duration
    clips = []
    
    current_time = 0
    asset_idx = 0
    
    while current_time < target_duration and asset_idx < len(assets):
        asset = assets[asset_idx]
        try:
            if asset['type'] == 'video':
                clip = VideoFileClip(asset['url']).resize(height=1080)
                # If video is too long for the remaining audio segment
                remaining = target_duration - current_time
                if clip.duration > remaining:
                    clip = clip.subclip(0, remaining)
            else:
                # Images default to 5 seconds or remaining time
                dur = min(5, target_duration - current_time)
                clip = ImageClip(asset['url']).set_duration(dur).resize(height=1080)
            
            clips.append(clip)
            current_time += clip.duration
            asset_idx += 1
        except Exception as e:
            print(f"Skipping asset {asset_idx} due to error: {e}")
            asset_idx += 1

    if clips:
        final_chapter = concatenate_videoclips(clips, method="compose").set_audio(audio)
        final_chapter.write_videofile(output_path, fps=24, codec="libx264", audio_codec="aac")
        return output_path
    return None
