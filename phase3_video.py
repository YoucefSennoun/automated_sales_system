"""
Phase 3 — Video Assembly
Reads Phase 2 payload, generates TikTok-style TTS audio using edge-tts,
and stitches the scraped images into a 9:16 vertical video with captions using moviepy.
"""

import json
import logging
import os

# Patch for Pillow >= 10.0.0 which removed ANTIALIAS, breaking moviepy 1.0.3
import PIL.Image
if not hasattr(PIL.Image, 'ANTIALIAS'):
    PIL.Image.ANTIALIAS = PIL.Image.LANCZOS

from gtts import gTTS
from moviepy.editor import ImageClip, AudioFileClip, TextClip, CompositeVideoClip, concatenate_videoclips
from config import SHORTLIST_SIZE

log = logging.getLogger(__name__)

def generate_tts(text: str, output_file: str):
    """Generates an MP3 file using Google TTS (bypass edge-tts 403 error)."""
    tts = gTTS(text=text, lang='en', tld='com')
    tts.save(output_file)

def create_video_for_product(product: dict, output_dir: str = "output") -> str:
    """Stitches images, audio, and captions into a final MP4."""
    os.makedirs(output_dir, exist_ok=True)
    
    images = product.get("images", [])
    if not images:
        log.warning("No images found for %s. Skipping video generation.", product.get("title", "")[:20])
        return ""
        
    script_data = product.get("video_script", {})
    voiceover_text = script_data.get("voiceover_text", "")
    captions = script_data.get("captions", [])
    
    if not voiceover_text:
        log.warning("No voiceover text found for %s. Skipping.", product.get("title", "")[:20])
        return ""
        
    rank = product.get("rank", "0")
    safe_title = "".join(c if c.isalnum() else "_" for c in product.get("title", "")[:15])
    
    audio_path = os.path.join(output_dir, f"audio_{rank}_{safe_title}.mp3")
    video_path = os.path.join(output_dir, f"video_{rank}_{safe_title}.mp4")
    
    # 1. Generate TTS
    try:
        generate_tts(voiceover_text, audio_path)
    except Exception as e:
        log.error("TTS generation failed: %s", e)
        return ""
        
    try:
        # 2. Load Audio
        audio_clip = AudioFileClip(audio_path)
        duration = audio_clip.duration
        
        # 3. Create Image Clips
        img_duration = duration / len(images)
        video_clips = []
        
        # Tiktok size is 1080x1920 (9:16)
        W, H = 1080, 1920
        
        for img_path in images:
            # Load and resize image to fit the vertical format
            clip = ImageClip(img_path).set_duration(img_duration)
            clip = clip.resize(width=W)  # Resize to fit width
            # Create a black background composite
            clip = clip.on_color(size=(W, H), color=(0, 0, 0), pos='center')
            video_clips.append(clip)
            
        base_video = concatenate_videoclips(video_clips, method="compose")
        base_video = base_video.set_audio(audio_clip)
        
        # 4. Add Captions
        if captions:
            cap_duration = duration / len(captions)
            txt_clips = []
            
            for i, cap_text in enumerate(captions):
                # We need imagemagick for TextClip, so this requires standard env setup
                try:
                    txt = TextClip(cap_text, fontsize=70, color='white', font='Arial-Bold',
                                   stroke_color='black', stroke_width=3, bg_color='transparent',
                                   method='caption', size=(W-100, None))
                    txt = txt.set_position(('center', H*0.6)).set_duration(cap_duration).set_start(i * cap_duration)
                    txt_clips.append(txt)
                except Exception as e:
                    log.warning("Could not generate text clip for '%s': %s", cap_text, e)
                    
            if txt_clips:
                final_video = CompositeVideoClip([base_video] + txt_clips)
            else:
                final_video = base_video
        else:
            final_video = base_video
            
        # 5. Render
        final_video.write_videofile(
            video_path,
            fps=24,
            codec="libx264",
            audio_codec="aac",
            preset="ultrafast",
            logger=None
        )
        
        # Clean up
        base_video.close()
        audio_clip.close()
        
        log.info("Video successfully created: %s", video_path)
        return video_path
        
    except Exception as e:
        log.error("Video assembly failed for %s: %s", product.get("title", "")[:20], e)
        return ""

def run_phase3():
    log.info("Starting Phase 3: Video Assembly")
    
    if not os.path.exists("data/phase2_payload.json"):
        log.error("data/phase2_payload.json not found! Run Phase 2 first.")
        return []
        
    with open("data/phase2_payload.json", "r", encoding="utf-8") as f:
        products = json.load(f)
        
    for p in products:
        log.info("Assembling video for: %s", p["title"][:50])
        video_path = create_video_for_product(p)
        if video_path:
            p["video_path"] = video_path
            
    with open("data/phase3_payload.json", "w", encoding="utf-8") as f:
        json.dump(products, f, indent=2)
        
    log.info("Phase 3 complete. Payload saved to data/phase3_payload.json")
    return products

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s — %(message)s")
    run_phase3()
