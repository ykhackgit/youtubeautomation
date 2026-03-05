import os
import sys
import asyncio
import json
import requests
import whisper
import time
import urllib.parse
import shutil
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes, ConversationHandler
from google import genai
from google.genai.errors import APIError
from googleapiclient.discovery import build

# Import the newly created browser selenium session
from browser_gemini import BrowserGeminiSession

# Load environment variables
load_dotenv()

# Get API keys
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY")
CHROME_PROFILE_PATH = os.environ.get("CHROME_PROFILE_PATH")
SYSTEM_PERSONA = os.environ.get("SYSTEM_PERSONA", "You are a helpful AI assistant.")
YOUTUBE_API_KEY = os.environ.get("YOUTUBE_API_KEY")
YOUTUBE_CHANNEL_ID = os.environ.get("YOUTUBE_CHANNEL_ID")
SUNO_API_KEY = os.environ.get("SUNO_API_KEY")
SUNO_API_URL = os.environ.get("SUNO_API_URL", "https://api.sunoapi.org") # Base URL for sunoapi.org
SUNO_PROMPT = os.environ.get("SUNO_PROMPT", "Create a fun song based on these facts:")
OLLAMA_HOST = os.environ.get("OLLAMA_HOST", "http://localhost")
OLLAMA_PORT = os.environ.get("OLLAMA_PORT", "11434")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "llama3")

if not TELEGRAM_BOT_TOKEN:
    print("Error: TELEGRAM_BOT_TOKEN environment variable is not set.", file=sys.stderr)
    print("Please set it in your .env file.", file=sys.stderr)
    sys.exit(1)

if not GEMINI_API_KEY:
    print("Error: GEMINI_API_KEY environment variable is not set.", file=sys.stderr)
    print("Please set it in your .env file.", file=sys.stderr)
    sys.exit(1)

# Initialize Gemini Client
client = genai.Client()

# Initialize Whisper model
print("Loading Whisper model...")
whisper_model = whisper.load_model("base")
print("Whisper model loaded.")

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send a message when the command /start is issued."""
    user = update.effective_user
    await update.message.reply_html(
        rf"Hi {user.mention_html()}! I'm your Gemini AI assistant. Send me a message and I'll reply using Gemini."
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send a message when the command /help is issued."""
    help_text = (
        "Here are the available actions you can take:\n\n"
        "🗣️ *Send Text/Audio*\n"
        "Just send a text or voice message, and I will reply using Google's Gemini AI.\n\n"
        "📜 */star [topic]*\n"
        "Generate a creative YouTube video script. You can provide an optional topic.\n\n"
        "📊 */get_channel_data*\n"
        "Fetch your lifetime YouTube channel statistics (views, subscribers, video count).\n\n"
        "🆕 */recent_videos*\n"
        "Fetch your 10 most recently uploaded videos.\n\n"
        "🔥 */top_videos*\n"
        "Fetch your 10 highest performing videos by view count.\n\n"
        "🎥 */all_videos*\n"
        "Fetch a list of up to 50 of your videos.\n\n"
        "🎵 */create_video*\n"
        "Automatically generate a song/video about your top 10 YouTube videos using AI.\n\n"
        "🎤 */create_custom_music*\n"
        "Create a custom song by providing your own title, style, and lyrics!\n\n"
        "🎬 */create_raw_video*\n"
        "Generate a raw video given an already generated custom song.\n\n"
        "🎧 */downloaded_songs*\n"
        "List and preview all currently downloaded AI songs.\n\n"
        "📺 */ready_videos*\n"
        "List and preview all fully generated raw videos ready for upload.\n\n"
        "🤖 */select_model*\n"
        "Choose which AI model to chat with (Gemini, Browser Gemini, DeepSeek, or Local Ollama).\n\n"
        "❓ */help*\n"
        "Show this help message."
    )
    await update.message.reply_markdown(help_text)

async def star_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Generate a YouTube video script."""
    print(f"Received /star command from {update.effective_user.first_name}")
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action='typing')

    try:
        prompt = "Please write a creative and engaging YouTube video script."
        if context.args:
            topic = " ".join(context.args)
            prompt = f"Please write a creative and engaging YouTube video script about: {topic}"

        # Call the Gemini API
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=[prompt],
            config={"system_instruction": "You are an expert YouTube scriptwriter."}
        )
        
        await update.message.reply_text(response.text)
        print("YouTube script sent successfully.\n")
        
    except Exception as e:
        print(f"Error calling Gemini API for /star: {e}", file=sys.stderr)
        await update.message.reply_text("Sorry, I encountered an error generating the script.")

async def get_channel_data_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Fetch and display YouTube channel statistics."""
    print(f"Received /get_channel_data command from {update.effective_user.first_name}")
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action='typing')

    if not YOUTUBE_API_KEY or not YOUTUBE_CHANNEL_ID:
        await update.message.reply_text("Error: YouTube API Key or Channel ID is missing from the environment variables.")
        return

    try:
        # Build the YouTube service securely
        youtube = build('youtube', 'v3', developerKey=YOUTUBE_API_KEY)

        # Make request to the channels endpoint
        request = youtube.channels().list(
            part="statistics,snippet",
            id=YOUTUBE_CHANNEL_ID
        )
        response = request.execute()

        if response.get('items'):
            channel = response['items'][0]
            stats = channel['statistics']
            snippet = channel['snippet']
            
            # Format the output
            message =  f"📊 **Channel Data for {snippet.get('title', 'Unknown')}** 📊\n\n"
            message += f"👁️ Total Lifetime Views: {int(stats.get('viewCount', 0)):,}\n"
            message += f"👥 Total Subscribers: {int(stats.get('subscriberCount', 0)):,}\n"
            message += f"🎬 Total Videos: {int(stats.get('videoCount', 0)):,}\n"
            
            await update.message.reply_markdown(message)
            print("Channel data sent successfully.\n")
        else:
            await update.message.reply_text("No channel found with that ID.")

    except Exception as e:
        print(f"Error fetching YouTube data: {e}", file=sys.stderr)
        await update.message.reply_text("Sorry, I encountered an error while fetching your channel data.")

def fetch_videos(order='date', max_results=10):
    """Helper function to fetch videos from the channel using the search endpoint."""
    if not YOUTUBE_API_KEY or not YOUTUBE_CHANNEL_ID:
        raise Exception("API Key or Channel ID missing")
        
    youtube = build('youtube', 'v3', developerKey=YOUTUBE_API_KEY)
    
    # We use search to easily order by date or viewCount
    search_response = youtube.search().list(
        channelId=YOUTUBE_CHANNEL_ID,
        type="video",
        order=order,
        part="id,snippet",
        maxResults=max_results
    ).execute()
    
    videos = []
    # If we need view counts, we have to make a separate request to the videos endpoint
    video_ids = [item['id']['videoId'] for item in search_response.get('items', [])]
    
    if not video_ids:
        return videos
        
    videos_response = youtube.videos().list(
        id=",".join(video_ids),
        part="statistics,snippet"
    ).execute()
    
    for item in videos_response.get('items', []):
        videos.append({
            'title': item['snippet']['title'],
            'views': int(item['statistics'].get('viewCount', 0)),
            'date': item['snippet']['publishedAt'][:10] # Get just the YYYY-MM-DD
        })
        
    # the /videos endpoint doesn't guarantee order, so we re-sort based on the search requirement
    if order == 'date':
        videos.sort(key=lambda x: x['date'], reverse=True)
    elif order == 'viewCount':
        videos.sort(key=lambda x: x['views'], reverse=True)
        
    return videos

async def get_recent_videos_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Fetch 10 recent videos."""
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action='typing')
    try:
        videos = fetch_videos(order='date', max_results=10)
        if not videos:
            await update.message.reply_text("No videos found.")
            return
            
        message = "🆕 **Top 10 Recent Videos** 🆕\n\n"
        for i, v in enumerate(videos, 1):
            message += f"{i}. 🎬 {v['title']}\n   👀 {v['views']:,} views | 📅 {v['date']}\n\n"
            
        await update.message.reply_markdown(message)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        await update.message.reply_text("Failed to fetch videos.")

async def get_top_videos_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Fetch 10 top performing videos by views."""
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action='typing')
    try:
        videos = fetch_videos(order='viewCount', max_results=10)
        if not videos:
            await update.message.reply_text("No videos found.")
            return
            
        message = "🔥 **Top 10 Performing Videos** 🔥\n\n"
        for i, v in enumerate(videos, 1):
            message += f"{i}. 🎬 {v['title']}\n   👀 {v['views']:,} views | 📅 {v['date']}\n\n"
            
        await update.message.reply_markdown(message)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        await update.message.reply_text("Failed to fetch videos.")

async def get_all_videos_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Fetch up to 50 videos."""
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action='typing')
    try:
        videos = fetch_videos(order='date', max_results=50)
        if not videos:
            await update.message.reply_text("No videos found.")
            return
            
        message = f"🎥 **All Videos (Top {len(videos)})** 🎥\n\n"
        for i, v in enumerate(videos, 1):
            # Keep it slightly more compact for the long list
            message += f"`{v['date']}` | 👀 {v['views']:,} | {v['title']}\n"
            
        await update.message.reply_markdown(message)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        await update.message.reply_text("Failed to fetch videos.")

# --- Interactive Preview Commands ---

async def list_downloaded_songs_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """List all downloaded songs with inline buttons to preview them."""
    if not os.path.exists("downloaded_music"):
        await update.message.reply_text("No downloaded music folder found.")
        return
        
    files = [f for f in sorted(os.listdir("downloaded_music")) if f.endswith(".mp3")]
    if not files:
        await update.message.reply_text("No downloaded songs found.")
        return
        
    keyboard = []
    for f in files:
        clean_name = f.replace("generated_song_", "").replace(".mp3", "")
        # The callback data contains the filename so we know what to send
        # Be careful of length limits (64 bytes)
        callback_data = f"preview_song_{f}"
        # If the filename is super long, we might need a mapping, but for now we try direct:
        if len(callback_data) > 64:
             callback_data = callback_data[:64]
             
        keyboard.append([InlineKeyboardButton(clean_name, callback_data=callback_data)])
        
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("🎧 **Downloaded Songs:**\nClick a song to preview it.", reply_markup=reply_markup, parse_mode='Markdown')

async def list_ready_videos_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """List all ready videos with inline buttons to preview them."""
    if not os.path.exists("ready_to_upload"):
        await update.message.reply_text("No ready videos folder found.")
        return
        
    # the folder structure is ready_to_upload/Title/Title.mp4
    video_paths = []
    for root, dirs, files in os.walk("ready_to_upload"):
        for f in files:
            if f.endswith(".mp4"):
                # store relative path like Title/Title.mp4
                rel_path = os.path.relpath(os.path.join(root, f), "ready_to_upload")
                video_paths.append(rel_path)
                
    if not video_paths:
        await update.message.reply_text("No ready videos found.")
        return
        
    keyboard = []
    for p in sorted(video_paths):
        # We use the folder name / file name
        clean_name = os.path.basename(p).replace(".mp4", "")
        
        callback_data = f"preview_video_{p}"
        if len(callback_data) > 64:
             # Just use the basename if too long
             callback_data = f"preview_video_{os.path.basename(p)}"[:64]
             
        keyboard.append([InlineKeyboardButton(clean_name, callback_data=callback_data)])
        
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("📺 **Ready Videos:**\nClick a video to preview it.", reply_markup=reply_markup, parse_mode='Markdown')

async def handle_preview_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle callback button clicks for previewing media outside of workflows."""
    query = update.callback_query
    await query.answer()
    
    data = query.data
    
    if data.startswith("preview_song_"):
        filename = data.replace("preview_song_", "")
        filepath = os.path.join("downloaded_music", filename)
        
        if os.path.exists(filepath):
            await context.bot.send_chat_action(chat_id=update.effective_chat.id, action='upload_audio')
            with open(filepath, "rb") as audio:
                await context.bot.send_audio(
                    chat_id=update.effective_chat.id, 
                    audio=audio, 
                    caption=f"🎧 Preview: {filename.replace('generated_song_', '').replace('.mp3', '')}"
                )
        else:
            await query.message.reply_text(f"Sorry, could not find {filename}.")
            
    elif data.startswith("preview_video_"):
        rel_path = data.replace("preview_video_", "")
        filepath = os.path.join("ready_to_upload", rel_path)
        
        # fallback trying to guess the path if it was truncated
        if not os.path.exists(filepath):
            filepath = os.path.join("ready_to_upload", rel_path.replace(".mp4", ""), rel_path)
            
        if os.path.exists(filepath):
            await context.bot.send_chat_action(chat_id=update.effective_chat.id, action='upload_video')
            with open(filepath, "rb") as video:
                await context.bot.send_video(
                    chat_id=update.effective_chat.id, 
                    video=video, 
                    caption=f"📺 Preview: {os.path.basename(filepath)}"
                )
        else:
            await query.message.reply_text(f"Sorry, could not find the video {rel_path}.")
            
    elif data.startswith("set_model_"):
        new_model = data.replace("set_model_", "")
        context.user_data['selected_model'] = new_model
        
        display_names = {
            "gemini": "Gemini 2.5 Flash",
            "browser": "Browser-Based Gemini",
            "deepseek": "DeepSeek V3",
            "ollama": f"Local Ollama ({OLLAMA_MODEL})"
        }
        await query.message.edit_text(f"✅ Active model changed to **{display_names.get(new_model, new_model)}**.", parse_mode='Markdown')

async def select_model_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Present inline keyboard to choose the active LLM."""
    keyboard = [
        [InlineKeyboardButton("Gemini 2.5 Flash", callback_data="set_model_gemini")],
        [InlineKeyboardButton("Browser Gemini (Scrape)", callback_data="set_model_browser")],
        [InlineKeyboardButton("DeepSeek V3", callback_data="set_model_deepseek")],
        [InlineKeyboardButton(f"Local Ollama ({OLLAMA_MODEL})", callback_data="set_model_ollama")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    current_model = context.user_data.get('selected_model', 'gemini')
    await update.message.reply_text(
        f"🤖 **Select AI Model**\n\nYour currently selected model is: `{current_model}`\nChoose a model to respond to your text and voice messages:", 
        reply_markup=reply_markup, 
        parse_mode='Markdown'
    )

async def execute_suno_generation(title: str, style: str, lyrics: str, instrumental: bool, update: Update, context: ContextTypes.DEFAULT_TYPE, status_message):
    """Helper function to execute the Suno API generation, polling, and downloading process."""
    if not SUNO_API_KEY:
        await status_message.edit_text("Error: SUNO_API_KEY is not configured in .env")
        return

    headers = {
        "Authorization": f"Bearer {SUNO_API_KEY}",
        "Content-Type": "application/json"
    }
    
    suno_payload = {
        "prompt": lyrics if not instrumental else "",
        "style": style,
        "title": title[:80] if title else "My Song",
        "customMode": True,
        "instrumental": instrumental,
        "model": "V4_5ALL",
        "callBackUrl": "https://webhook.site/dummy"
    }
    
    try:
        loop = asyncio.get_running_loop()
        generate_endpoint = f"{SUNO_API_URL.rstrip('/')}/api/v1/generate"
        print(f"Sending POST to {generate_endpoint} with Bearer authentication...")
        
        response = await loop.run_in_executor(
            None, 
            lambda: requests.post(generate_endpoint, json=suno_payload, headers=headers, timeout=30)
        )
        response.raise_for_status()
        suno_result = response.json()
        
        if suno_result.get("code") != 200:
            raise Exception(f"Suno API Creation Error: {suno_result.get('msg')}")
            
        task_id = suno_result.get("data", {}).get("taskId")
        if not task_id:
            raise Exception("No taskId returned from Suno API.")
            
        await status_message.edit_text(f"⏳ Song requested! Task ID: `{task_id}`\n\nWaiting for generation to finish... (This usually takes ~2-5 minutes).", parse_mode='Markdown')

        # Poll the API until the song is ready
        poll_endpoint = f"{SUNO_API_URL.rstrip('/')}/api/v1/generate/record-info?taskId={task_id}"
        audio_url = None
        max_retries = 30 # Up to 30 * 15 seconds = 7.5 minutes wait time
        
        for _ in range(max_retries):
            await asyncio.sleep(15) # Wait 15 seconds before polling
            
            poll_response = await loop.run_in_executor(
                None,
                lambda: requests.get(poll_endpoint, headers=headers, timeout=30)
            )
            poll_response.raise_for_status()
            poll_result = poll_response.json()
            
            status = poll_result.get("data", {}).get("status")
            print(f"Polling taskId {task_id}: {status}")
            
            if status == "SUCCESS":
                suno_data = poll_result.get("data", {}).get("response", {}).get("sunoData", [])
                if suno_data and len(suno_data) > 0:
                    audio_url = suno_data[0].get("audioUrl")
                break
            elif status in ["CREATE_TASK_FAILED", "GENERATE_AUDIO_FAILED", "CALLBACK_EXCEPTION", "SENSITIVE_WORD_ERROR"]:
                raise Exception(f"Suno task failed with status: {status}")

        if not audio_url:
            raise Exception(f"Failed to retrieve audio URL after maximum retries. Final status: {status}")

        await status_message.edit_text("⏳ Downloading finished song...")
        
        # Ensure download directory exists
        os.makedirs("downloaded_music", exist_ok=True)
        
        # Download the actual audio file
        audio_response = await loop.run_in_executor(None, lambda: requests.get(audio_url, timeout=60))
        audio_response.raise_for_status()
        
        audio_filename = f"downloaded_music/generated_song_{update.effective_user.id}_{int(time.time())}.mp3"
        with open(audio_filename, "wb") as f:
            f.write(audio_response.content)

        # Send back to user
        await status_message.delete()
        caption = f"🎵 **{title}**\n🎸 _Style:_ {style}\n\nHere is your custom song!"
        with open(audio_filename, "rb") as audio:
            await context.bot.send_audio(chat_id=update.effective_chat.id, audio=audio, caption=caption, parse_mode='Markdown')
        
        print(f"Successfully generated and saved audio to {audio_filename}")
        
    except requests.exceptions.RequestException as req_err:
        print(f"Suno API communication error: {req_err}", file=sys.stderr)
        await status_message.edit_text(f"❌ Failed to connect to or generate from the Suno API.\nDetails: {str(req_err)}")
    except Exception as e:
        print(f"Error in Suno execution: {e}", file=sys.stderr)
        await status_message.edit_text(f"❌ Custom song generation failed: {e}")

async def create_video_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Automated workflow to generate a song based on top youtube videos."""
    print(f"Received /create_video command from {update.effective_user.first_name}")
    
    if not SUNO_API_KEY:
        await update.message.reply_text("Error: SUNO_API_KEY is not configured in .env")
        return

    # Keep user informed since this is a multi-step slow process
    status_message = await update.message.reply_text("⏳ Step 1/3: Reading channel facts from fact.txt...")
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action='typing')

    try:
        # Step 1: Read existing fact.txt
        try:
            with open("fact.txt", "r") as f:
                fact_content = f.read()
        except FileNotFoundError:
            await status_message.edit_text("❌ `fact.txt` not found. Please create one with facts about the channel before running this command.", parse_mode='Markdown')
            return
            
        await status_message.edit_text("⏳ Step 2/3: Generating AI song prompt and lyrics from your facts...")

        # Step 2: Generate JSON prompt using Gemini
        json_schema_prompt = f"""
{SUNO_PROMPT}

Channel Facts:
{fact_content}

You must return ONLY a valid JSON object with the following exact keys:
"title": (A short, catchy title for the song)
"style": (The musical genre or acoustic style, e.g. "Funk Music", "Upbeat Pop", "Synthwave")
"lyrics": (The actual lyrics of the song with verse/chorus markers like [Verse 1], [Chorus])
"""
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=[json_schema_prompt],
            config={"response_mime_type": "application/json"}
        )
        
        try:
            song_data = json.loads(response.text)
        except json.JSONDecodeError:
            print(f"Failed to parse Gemini JSON: {response.text}")
            await status_message.edit_text("Error: AI failed to generate valid song metadata.")
            return

        title = song_data.get("title", "My YouTube Journey")
        style = song_data.get("style", "Pop")
        lyrics = song_data.get("lyrics", "")

        await status_message.edit_text(f"⏳ Step 3/3: Requesting song generation from Suno...\n\n_Title:_ {title}\n_Style:_ {style}")
        print(f"Suno parameters generated:\nTitle: {title}\nStyle: {style}\nLyrics:\n{lyrics}")

        # Step 3: Call external Suno API using the new helper
        await execute_suno_generation(title=title, style=style, lyrics=lyrics, instrumental=False, update=update, context=context, status_message=status_message)

    except Exception as e:
        print(f"Error in create_video automation workflow: {e}", file=sys.stderr)
        await update.message.reply_text("Sorry, I encountered an unexpected error during the auto-generation process.")

# --- Raw Video Generation Conversation Handler States ---
SELECT_AUDIO_RAW = range(1)

async def create_raw_video_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start the raw video generation workflow by listing available audio files."""
    os.makedirs("downloaded_music", exist_ok=True)
    files = [f for f in sorted(os.listdir("downloaded_music")) if f.endswith(".mp3")]
    
    if not files:
        await update.message.reply_text("No downloaded music found. Please use /create_custom_music first to generate some songs!")
        return ConversationHandler.END
        
    # Store the files list in context for the next step
    context.user_data['available_audio_files'] = files
    
    message = "🎵 **Select a song to convert into a Raw Music Video:**\n\n"
    for i, file in enumerate(files):
        clean_name = file.replace("generated_song_", "").replace(".mp3", "")
        message += f"*{i + 1}.* `{clean_name}`\n"
        
    message += "\n_Reply with the number of the song you want to use._\n_(Type /cancel to abort)_"
    
    await update.message.reply_text(message, parse_mode='Markdown')
    return SELECT_AUDIO_RAW

async def process_raw_video_bg_task(chat_id: int, bot, base_title: str, safe_title: str, source_audio_path: str):
    """Background task to generate image, copy files, merge with ffmpeg, and send video."""
    output_dir = os.path.join("ready_to_upload", safe_title)
    os.makedirs(output_dir, exist_ok=True)
    
    try:
        status_message = await bot.send_message(chat_id=chat_id, text=f"✨ Creating raw video for `{base_title}`...\n\n_Step 1/3: Generating cinematic cover image..._", parse_mode='Markdown')
        
        # Step 1: Generate Image Prompt using Gemini
        image_prompt_request = f"Write a scenic, highly detailed, visually stunning image prompt for an AI image generator. The image should perfectly represent a song titled '{base_title}'. Do NOT include any text, letters, or words in the image itself. Make it cinematic and 16:9 ratio compatible."
        
        try:
            response = client.models.generate_content(
                model='gemini-2.5-flash',
                contents=image_prompt_request,
            )
            image_prompt = response.text.replace('\n', ' ').strip()
        except:
            image_prompt = f"A beautiful, scenic, highly detailed, cinematic background representing the song {base_title}. No text, no words, 8k resolution, masterpiece."
            
        # Ensure prompt is not too long to avoid URI errors
        if len(image_prompt) > 800:
            image_prompt = image_prompt[:800]
            
        # Step 2: Download Image from Pollinations using a simple base text
        encoded_prompt = urllib.parse.quote(image_prompt)
        image_url = f"https://image.pollinations.ai/prompt/{encoded_prompt}?width=1920&height=1080&nologo=true"
        
        # Run synchronous request in executor
        loop = asyncio.get_running_loop()
        try:
            image_response = await loop.run_in_executor(None, lambda: requests.get(image_url, timeout=30))
            image_response.raise_for_status()
        except Exception as img_err:
            print(f"Failed to fetch original prompt image: {img_err}. Falling back to basic prompt.")
            fallback_prompt = urllib.parse.quote(f"beautiful abstract background of song {base_title}")
            image_url = f"https://image.pollinations.ai/prompt/{fallback_prompt}?width=1920&height=1080&nologo=true"
            image_response = await loop.run_in_executor(None, lambda: requests.get(image_url, timeout=30))
            image_response.raise_for_status()
            
        # Save image and copy audio to the new directory
        target_image_path = os.path.join(output_dir, f"{safe_title}.jpg")
        target_audio_path = os.path.join(output_dir, f"{safe_title}.mp3")
        
        with open(target_image_path, "wb") as f:
            f.write(image_response.content)
        shutil.copy2(source_audio_path, target_audio_path)
            
        await status_message.edit_text(f"✨ Creating raw video for `{base_title}`...\n\n_Step 2/3: Merging audio and image into MP4 (this may take a minute)..._", parse_mode='Markdown')
        
        # Step 3: Use FFmpeg to merge
        output_mp4_path = os.path.join(output_dir, f"{safe_title}.mp4")
        
        # Run ffmpeg as a subprocess to prevent blocking the async loop
        ffmpeg_cmd = [
            "ffmpeg", "-y",
            "-loop", "1",
            "-i", target_image_path,
            "-i", target_audio_path,
            "-c:v", "libx264",
            "-tune", "stillimage",
            "-c:a", "aac",
            "-b:a", "192k",
            "-pix_fmt", "yuv420p",
            "-shortest", 
            output_mp4_path
        ]
        
        process = await asyncio.create_subprocess_exec(
            *ffmpeg_cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        _, stderr = await process.communicate()
        
        if process.returncode != 0:
            error_msg = stderr.decode('utf-8')
            print(f"FFmpeg Error: {error_msg}")
            raise Exception("FFmpeg encountered an error while merging.")
            
        await status_message.edit_text(f"✨ Creating raw video for `{base_title}`...\n\n_Step 3/3: Uploading video to Telegram..._", parse_mode='Markdown')
        
        # Step 4: Send the video back
        with open(output_mp4_path, "rb") as video:
            await bot.send_video(
                chat_id=chat_id, 
                video=video, 
                caption=f"🎥 **{base_title}**\n\nYour raw video is ready and saved to `ready_to_upload/{safe_title}/`!",
                parse_mode='Markdown'
            )
            
        await status_message.delete()
        
    except Exception as e:
        print(f"Error in background video generation workflow: {e}", file=sys.stderr)
        await bot.send_message(chat_id=chat_id, text=f"Sorry, an error occurred while generating the video: {e}")

from telegram import InlineKeyboardButton, InlineKeyboardMarkup # Added this import

async def create_raw_video_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start the raw video generation workflow by listing available audio files."""
    os.makedirs("downloaded_music", exist_ok=True)
    files = [f for f in sorted(os.listdir("downloaded_music")) if f.endswith(".mp3")]
    
    if not files:
        await update.message.reply_text("No downloaded music found. Please use /create_custom_music first to generate some songs!")
        return ConversationHandler.END
        
    # We no longer strictly need to store the files list in user_data since the callback can hold the filename,
    # but storing it can help validate. Let's just use the callback data.
    
    keyboard = []
    for f in files:
        clean_name = f.replace("generated_song_", "").replace(".mp3", "")
        # Prefix for this specific conversation handler
        callback_data = f"select_raw_{f}"
        if len(callback_data) > 64:
            callback_data = callback_data[:64]
        keyboard.append([InlineKeyboardButton(clean_name, callback_data=callback_data)])
        
    keyboard.append([InlineKeyboardButton("❌ Cancel", callback_data="cancel_raw")])
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "🎵 **Select a song to convert into a Raw Music Video:**\n"
        "_Click the song you want to use._",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )
    return SELECT_AUDIO_RAW

async def process_raw_video_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Process the user's callback selection, and spawn a background task."""
    query = update.callback_query
    await query.answer()
    
    data = query.data
    
    if data == "cancel_raw":
        await query.edit_message_text("Raw video creation canceled.")
        return ConversationHandler.END
        
    if not data.startswith("select_raw_"):
        return SELECT_AUDIO_RAW
        
    filename = data.replace("select_raw_", "")
    
    # We edit the message to just show the text to avoid pressing again
    await query.edit_message_text(f"Selected: `{filename.replace('.mp3', '')}`")
    
    try:
        source_audio_path = os.path.join("downloaded_music", filename)
        
        if not os.path.exists(source_audio_path):
            await query.message.reply_text(f"File {filename} no longer exists.")
            return ConversationHandler.END
            
        # Clean up the title for the folder name and prompt
        import re as standard_re
        base_title = standard_re.sub(r'generated_song_\d+_', '', filename).replace('.mp3', '')
        if not base_title or base_title.isdigit():
            base_title = "Custom_Music_Track"
            
        safe_title = "".join([c if c.isalnum() else "_" for c in base_title])
        
        chat_id = update.effective_chat.id
        await query.message.reply_text(f"Starting video generation for `{base_title}` in the background. You can continue using the bot!", parse_mode='Markdown')
        
        # Spawn background task
        asyncio.create_task(process_raw_video_bg_task(
            chat_id=chat_id,
            bot=context.bot,
            base_title=base_title,
            safe_title=safe_title,
            source_audio_path=source_audio_path
        ))
        
        return ConversationHandler.END
        
    except Exception as e:
        print(f"Error starting video generation workflow: {e}", file=sys.stderr)
        await query.message.reply_text(f"Sorry, an error occurred: {e}")
        return ConversationHandler.END

async def cancel_raw_video(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cancel the video generation process."""
    await update.message.reply_text("Raw video creation canceled.")
    return ConversationHandler.END

# --- Custom Music Conversation Handler States ---
TITLE, STYLE, LYRICS = range(3)

async def create_custom_music_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start the custom music creation form."""
    await update.message.reply_text("🎵 Let's create some custom music! \n\nFirst, what should the **Title** be?\n\n_(Type /cancel to abort at any time)_", parse_mode='Markdown')
    return TITLE

async def custom_music_title(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Store the title and ask for the style."""
    context.user_data['custom_title'] = update.message.text
    await update.message.reply_text(f"Got it! Title: **{update.message.text}**\n\nNow, what **Style** or genre should the music be? (e.g., 'Upbeat Pop', 'Heavy Metal')", parse_mode='Markdown')
    return STYLE

async def custom_music_style(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Store the style and ask for lyrics."""
    context.user_data['custom_style'] = update.message.text
    await update.message.reply_text(f"Awesome! Style: **{update.message.text}**\n\nFinally, send me the **Lyrics** for the song.\n\n_If you want an instrumental track with auto-generated or no lyrics, type `none` or `skip`._", parse_mode='Markdown')
    return LYRICS

async def custom_music_lyrics(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Store lyrics, determine instrumental flag, and start generation."""
    user_lyrics = update.message.text.strip()
    
    if user_lyrics.lower() in ['none', 'skip', 'instrumental', 'no']:
        context.user_data['custom_lyrics'] = ""
        context.user_data['custom_instrumental'] = True
    else:
        context.user_data['custom_lyrics'] = user_lyrics
        context.user_data['custom_instrumental'] = False
        
    status_message = await update.message.reply_text("✨ Processing your request...")
    
    # Trigger the generation logic here
    await execute_suno_generation(
        title=context.user_data.get('custom_title', ''),
        style=context.user_data.get('custom_style', ''),
        lyrics=context.user_data.get('custom_lyrics', ''),
        instrumental=context.user_data.get('custom_instrumental', False),
        update=update,
        context=context,
        status_message=status_message
    )
    
    return ConversationHandler.END

async def cancel_custom_music(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cancel the custom music creation form."""
    await update.message.reply_text("Custom music creation canceled.")
    return ConversationHandler.END

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle incoming text messages and reply using the selected LLM."""
    user_message = update.message.text or update.message.caption or ""
    if not user_message and not update.message.photo and not update.message.document:
        return
        
    print(f"Received message from {update.effective_user.first_name}: {user_message}")

    # Send a "typing..." action so the user knows the bot is working
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action='typing')

    selected_model = context.user_data.get('selected_model', 'gemini')

    try:
        loop = asyncio.get_running_loop()
        
        if selected_model == 'gemini':
            response = await loop.run_in_executor(
                None,
                lambda: client.models.generate_content(
                    model="gemini-2.5-flash",
                    contents=[user_message],
                    config={"system_instruction": SYSTEM_PERSONA}
                )
            )
            reply_text = response.text
            
        elif selected_model == 'browser':
            # Check if initialization was attempted but completely failed to populate the key
            if 'browser_session_started' not in context.bot_data:
                await update.message.reply_text("⏳ Initializing Browser Gemini session in the background... please wait a moment and try again.")
                return
                
            bs = context.bot_data.get('browser_session')
            if not bs:
                await update.message.reply_text("❌ The Browser Gemini session encountered a fatal error during startup and is unavailable.")
                return
                
            reply_text = await bs.generate_content_async(user_message, timeout=60)
            
        elif selected_model == 'deepseek':
            if not DEEPSEEK_API_KEY:
                await update.message.reply_text("❌ DeepSeek API key (DEEPSEEK_API_KEY) is not configured.")
                return
            headers = {
                "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
                "Content-Type": "application/json"
            }
            payload = {
                "model": "deepseek-chat",
                "messages": [
                    {"role": "system", "content": SYSTEM_PERSONA},
                    {"role": "user", "content": user_message}
                ]
            }
            resp = await loop.run_in_executor(
                None,
                lambda: requests.post("https://api.deepseek.com/chat/completions", json=payload, headers=headers, timeout=60)
            )
            resp.raise_for_status()
            reply_text = resp.json()['choices'][0]['message']['content']
            
        elif selected_model == 'ollama':
            payload = {
                "model": OLLAMA_MODEL,
                "prompt": f"System: {SYSTEM_PERSONA}\nUser: {user_message}",
                "stream": False
            }
            endpoint = f"{OLLAMA_HOST.rstrip('/')}:{OLLAMA_PORT}/api/generate"
            resp = await loop.run_in_executor(
                None,
                lambda: requests.post(endpoint, json=payload, timeout=120)
            )
            resp.raise_for_status()
            reply_text = resp.json()['response']
            
        else:
            reply_text = "Unknown model selected."
        
        # Send the response back to the user
        await update.message.reply_text(reply_text)
        print("Reply sent successfully.\n")
        
    except Exception as e:
        print(f"Error calling API for {selected_model}: {e}", file=sys.stderr)
        await update.message.reply_text(f"Sorry, I encountered an error while processing your request with {selected_model}.")

async def handle_media(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle incoming photos and documents."""
    selected_model = context.user_data.get('selected_model', 'gemini')
    if selected_model != 'browser':
        await update.message.reply_text("The default Gemini API does not currently support image uploads in this bot. Please switch to 'Browser Gemini' using /select_model.")
        return

    # Check if initialization was attempted but completely failed to populate the key
    if 'browser_session_started' not in context.bot_data:
        await update.message.reply_text("⏳ Initializing Browser Gemini session in the background... please wait a moment and try again.")
        return
        
    bs = context.bot_data.get('browser_session')
    if not bs:
        await update.message.reply_text("❌ The Browser Gemini session encountered a fatal error during startup and is unavailable.")
        return
        
    if not getattr(bs, 'is_ready', False):
        await update.message.reply_text("⏳ Browser Gemini session is still initializing or restarting. Please try again in a moment.")
        return

    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action='upload_document')
    
    file_id = None
    mime_type = "image/jpeg" # Default guess
    
    if update.message.photo:
        file_id = update.message.photo[-1].file_id # Get highest res
    elif update.message.document:
        file_id = update.message.document.file_id
        mime_type = update.message.document.mime_type or "image/jpeg"
        
    if not file_id:
        return

    try:
        new_file = await context.bot.get_file(file_id)
        # Download as byte array
        import io
        import base64
        byte_arr = io.BytesIO()
        await new_file.download_to_memory(byte_arr)
        
        base64_data = base64.b64encode(byte_arr.getvalue()).decode('utf-8')
        
        await update.message.reply_text("Uploading file to Gemini Browser...")
        success = await bs.upload_file_async(base64_data, mime_type)
        
        if not success:
            await update.message.reply_text("❌ Failed to inject the image into the Gemini browser session.")
            return
            
        # If there's a caption, send it as a prompt, otherwise just say "What's this?"
        prompt = update.message.caption or "What's in this image?"
        
        await update.message.reply_text(f"File uploaded. Sending prompt: '{prompt}'...")
        await context.bot.send_chat_action(chat_id=update.effective_chat.id, action='typing')
        reply_text = await bs.generate_content_async(prompt, timeout=60)
        
        if reply_text:
            await update.message.reply_text(reply_text)
        else:
            await update.message.reply_text("Wait, the response came back empty. Did the browser session get stuck?")

    except Exception as e:
        print(f"Error handling media: {e}", file=sys.stderr)
        await update.message.reply_text(f"❌ Error processing media: {e}")

async def handle_audio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle incoming audio/voice messages."""
    print(f"Received audio from {update.effective_user.first_name}")
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action='record_voice')

    audio_file_id = None
    if update.message.voice:
        audio_file_id = update.message.voice.file_id
    elif update.message.audio:
        audio_file_id = update.message.audio.file_id
        
    if not audio_file_id:
        return

    try:
        # Download the file from Telegram
        file = await context.bot.get_file(audio_file_id)
        local_filename = f"temp_tg_audio_{update.effective_user.id}.ogg"
        await file.download_to_drive(local_filename)
        
        print(f"Downloaded audio to {local_filename}, transcribing with Whisper...")
        
        # Transcribe the audio using Whisper
        # Note: Whisper's transcribe is blocking, but for a simple bot we'll run it directly. 
        # In a high-traffic production bot, this should be run in a separate thread/executor.
        result = whisper_model.transcribe(local_filename)
        transcribed_text = result["text"].strip()
        
        print(f"Transcription complete: '{transcribed_text}'")
        
        # Determine the prompt
        base_prompt = "The user sent an audio message. Here is the transcript:"
        caption_text = f" They also included this caption: '{update.message.caption}'" if update.message.caption else ""
        
        final_prompt = f"{base_prompt} \"{transcribed_text}\"\n{caption_text}\n\nPlease respond to the user based on their voice message."
        
        selected_model = context.user_data.get('selected_model', 'gemini')
        loop = asyncio.get_running_loop()
        
        if selected_model == 'gemini':
            response = await loop.run_in_executor(
                None,
                lambda: client.models.generate_content(
                    model="gemini-2.5-flash",
                    contents=[final_prompt],
                    config={"system_instruction": SYSTEM_PERSONA}
                )
            )
            reply_text = response.text
            
        elif selected_model == 'browser':
            if 'browser_session_started' not in context.bot_data:
                await update.message.reply_text("⏳ Initializing Browser Gemini session in the background... please wait a moment and try again.")
                return
                
            bs = context.bot_data.get('browser_session')
            if not bs: # This should ideally not happen if browser_session is always set, even to a failed state
                await update.message.reply_text("❌ The Browser Gemini session encountered a fatal error during startup and is unavailable.")
                return
            
            if not bs.is_ready:
                # Attempt to restart it if dead
                if 'browser_session_restarting' not in context.bot_data:
                    context.bot_data['browser_session_restarting'] = True
                    await update.message.reply_text("🔄 Browser session was closed or crashed. Restarting it now, please wait 15 seconds and try again...")
                    
                    async def _restart_task():
                        try:
                            new_bs = await getattr(asyncio.get_running_loop(), 'run_in_executor')(None, init_bs)
                            context.bot_data['browser_session'] = new_bs
                        except Exception as e:
                            print(f"Failed to restart browser session: {e}")
                        finally:
                            if 'browser_session_restarting' in context.bot_data:
                                del context.bot_data['browser_session_restarting']
                    
                    asyncio.create_task(_restart_task())
                else:
                    await update.message.reply_text("⏳ Still restarting the Browser Gemini session... please wait a moment.")
                return
                
            reply_text = await bs.generate_content_async(final_prompt, timeout=60)
            
        elif selected_model == 'deepseek':
            if not DEEPSEEK_API_KEY:
                await update.message.reply_text("❌ DeepSeek API key is not configured.")
                return
            headers = {"Authorization": f"Bearer {DEEPSEEK_API_KEY}", "Content-Type": "application/json"}
            payload = {"model": "deepseek-chat", "messages": [{"role": "system", "content": SYSTEM_PERSONA}, {"role": "user", "content": final_prompt}]}
            resp = await loop.run_in_executor(None, lambda: requests.post("https://api.deepseek.com/chat/completions", json=payload, headers=headers, timeout=60))
            resp.raise_for_status()
            reply_text = resp.json()['choices'][0]['message']['content']
            
        elif selected_model == 'ollama':
            payload = {"model": OLLAMA_MODEL, "prompt": f"System: {SYSTEM_PERSONA}\nUser: {final_prompt}", "stream": False}
            endpoint = f"{OLLAMA_HOST.rstrip('/')}:{OLLAMA_PORT}/api/generate"
            resp = await loop.run_in_executor(None, lambda: requests.post(endpoint, json=payload, timeout=120))
            resp.raise_for_status()
            reply_text = resp.json()['response']
            
        else:
            reply_text = "Unknown model selected."
        
        # Send response back to user
        await update.message.reply_text(reply_text)
        print("Audio reply sent successfully.\n")
        
        # Cleanup
        try:
            os.remove(local_filename)
            print("Cleaned up temporary audio files.")
        except Exception as cleanup_error:
            print(f"Error cleaning up files: {cleanup_error}", file=sys.stderr)
        
    except Exception as e:
        print(f"Error processing audio message: {e}", file=sys.stderr)
        await update.message.reply_text("Sorry, I encountered an error while processing your audio.")

def init_bs():
    """Initializes the browser session."""
    # Set headless=False so the user can literally see the window and login if needed.
    # Once logged in, they can change this back to True.
    return BrowserGeminiSession(
        headless=False, 
        profile_path=CHROME_PROFILE_PATH
    )

async def post_init(application: Application):
    """Initialize background services when the bot starts."""
    print("Pre-initializing Browser Gemini session in the background...")
    
    loop = asyncio.get_running_loop()
    application.bot_data['browser_session_started'] = True
    
    # Run the init process asynchronously so it doesn't block the bot from starting
    async def _init_task():
        try:
            bs = await loop.run_in_executor(None, init_bs)
            application.bot_data['browser_session'] = bs
            
            if bs.is_ready:
                print("Browser-Based Gemini session initialized and ready for requests.")
            else:
                print(f"Browser session started but isn't ready: {bs.init_error}")
        except Exception as e:
            print(f"Fatal crash during background session init: {e}")
            application.bot_data['browser_session'] = None
            
    asyncio.create_task(_init_task())

def main():
    """Start the bot."""
    print("Starting Telegram bot...")
    
    # Create the Application and pass it your bot's token.
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).post_init(post_init).build()

    # on different commands - answer in Telegram
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("star", star_command))
    application.add_handler(CommandHandler("get_channel_data", get_channel_data_command))
    application.add_handler(CommandHandler("recent_videos", get_recent_videos_command))
    application.add_handler(CommandHandler("top_videos", get_top_videos_command))
    application.add_handler(CommandHandler("all_videos", get_all_videos_command))
    application.add_handler(CommandHandler("create_video", create_video_command))
    application.add_handler(CommandHandler("downloaded_songs", list_downloaded_songs_command))
    application.add_handler(CommandHandler("ready_videos", list_ready_videos_command))
    application.add_handler(CommandHandler("select_model", select_model_command))

    # Add the general callback handler for previews. Note: ConversationHandlers get priority
    # for their own specific callback states if they are matched first.
    application.add_handler(CallbackQueryHandler(handle_preview_callback, pattern='^(preview_|set_model_)'))

    raw_video_conv_handler = ConversationHandler(
        entry_points=[CommandHandler('create_raw_video', create_raw_video_start)],
        states={
            # Now listens for callback queries matching "select_raw_" or "cancel_raw"
            SELECT_AUDIO_RAW: [CallbackQueryHandler(process_raw_video_selection, pattern='^(select_raw_|cancel_raw)')],
        },
        fallbacks=[CommandHandler('cancel', cancel_raw_video)]
    )
    application.add_handler(raw_video_conv_handler)

    custom_music_conv_handler = ConversationHandler(
        entry_points=[CommandHandler('create_custom_music', create_custom_music_start)],
        states={
            TITLE: [MessageHandler(filters.TEXT & ~(filters.COMMAND), custom_music_title)],
            STYLE: [MessageHandler(filters.TEXT & ~(filters.COMMAND), custom_music_style)],
            LYRICS: [MessageHandler(filters.TEXT & ~(filters.COMMAND), custom_music_lyrics)]
        },
        fallbacks=[CommandHandler('cancel', cancel_custom_music)]
    )
    application.add_handler(custom_music_conv_handler)

    # on non command i.e message - echo the message on Telegram
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    application.add_handler(MessageHandler(filters.PHOTO | filters.Document.ALL, handle_media))
    application.add_handler(MessageHandler(filters.VOICE | filters.AUDIO, handle_audio))

    # Run the bot until the user presses Ctrl-C
    print("Bot is polling for new messages. Press Ctrl-C to stop.")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
