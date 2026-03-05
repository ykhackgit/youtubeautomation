import re

with open("telegram_bot.py", "r") as f:
    content = f.read()

# Add urllib import if missing
if "import urllib.parse" not in content:
    content = content.replace("import time\n", "import time\nimport urllib.parse\nimport shutil\n")

# Extract the block to replace: 'async def create_video_command(...)' until the next definition.
# We will just replace it with our new conversational block.
pattern_old = r"async def create_video_command\(update: Update, context: ContextTypes\.DEFAULT_TYPE\):.*?await update\.message\.reply_text\(\"Sorry, I encountered an unexpected error during the auto-generation process\.\"\)\n"

replacement_new = '''# --- Raw Video Generation Conversation Handler States ---
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
    
    message = "🎵 **Select a song to convert into a Raw Music Video:**\\n\\n"
    for i, file in enumerate(files):
        clean_name = file.replace("generated_song_", "").replace(".mp3", "")
        message += f"*{i + 1}.* `{clean_name}`\\n"
        
    message += "\\n_Reply with the number of the song you want to use._\\n_(Type /cancel to abort)_"
    
    await update.message.reply_text(message, parse_mode='Markdown')
    return SELECT_AUDIO_RAW

async def process_raw_video_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Process the user's selection, generate image, copy files, and merge with ffmpeg."""
    try:
        selection = int(update.message.text.strip()) - 1
        files = context.user_data.get('available_audio_files', [])
        
        if selection < 0 or selection >= len(files):
            await update.message.reply_text("Invalid selection. Please reply with a valid number from the list.")
            return SELECT_AUDIO_RAW
            
        selected_file = files[selection]
        source_audio_path = os.path.join("downloaded_music", selected_file)
        
        # Clean up the title for the folder name and prompt
        import re as standard_re
        base_title = standard_re.sub(r'generated_song_\d+_', '', selected_file).replace('.mp3', '')
        if not base_title or base_title.isdigit():
            base_title = "Custom_Music_Track"
            
        safe_title = "".join([c if c.isalnum() else "_" for c in base_title])
        output_dir = os.path.join("ready_to_upload", safe_title)
        os.makedirs(output_dir, exist_ok=True)
        
        status_message = await update.message.reply_text(f"✨ Creating raw video for `{base_title}`...\\n\\n_Step 1/3: Generating cinematic cover image..._", parse_mode='Markdown')
        
        # Step 1: Generate Image Prompt using Gemini
        image_prompt_request = f"Write a scenic, highly detailed, visually stunning image prompt for an AI image generator. The image should perfectly represent a song titled '{base_title}'. Do NOT include any text, letters, or words in the image itself. Make it cinematic and 16:9 ratio compatible."
        
        try:
            response = client.models.generate_content(
                model='gemini-2.5-flash',
                contents=image_prompt_request,
            )
            image_prompt = response.text.replace('\\n', ' ').strip()
        except:
            image_prompt = f"A beautiful, scenic, highly detailed, cinematic background representing the song {base_title}. No text, no words, 8k resolution, masterpiece."
            
        # Step 2: Download Image from Pollinations
        encoded_prompt = urllib.parse.quote(image_prompt)
        image_url = f"https://image.pollinations.ai/prompt/{encoded_prompt}?width=1920&height=1080&nologo=true"
        
        image_response = requests.get(image_url, timeout=30)
        image_response.raise_for_status()
        
        # Save image and copy audio to the new directory
        target_image_path = os.path.join(output_dir, f"{safe_title}.jpg")
        target_audio_path = os.path.join(output_dir, f"{safe_title}.mp3")
        
        with open(target_image_path, "wb") as f:
            f.write(image_response.content)
        shutil.copy2(source_audio_path, target_audio_path)
            
        await status_message.edit_text(f"✨ Creating raw video for `{base_title}`...\\n\\n_Step 2/3: Merging audio and image into MP4 (this may take a minute)..._", parse_mode='Markdown')
        
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
            
        await status_message.edit_text(f"✨ Creating raw video for `{base_title}`...\\n\\n_Step 3/3: Uploading video to Telegram..._", parse_mode='Markdown')
        
        # Step 4: Send the video back
        with open(output_mp4_path, "rb") as video:
            await context.bot.send_video(
                chat_id=update.effective_chat.id, 
                video=video, 
                caption=f"🎥 **{base_title}**\\n\\nYour raw video is ready and saved to `ready_to_upload/{safe_title}/`!",
                parse_mode='Markdown'
            )
            
        await status_message.delete()
        return ConversationHandler.END
        
    except ValueError:
        await update.message.reply_text("Please enter a valid number.")
        return SELECT_AUDIO_RAW
    except Exception as e:
        print(f"Error in video generation workflow: {e}", file=sys.stderr)
        await update.message.reply_text(f"Sorry, an error occurred while generating the video: {e}")
        return ConversationHandler.END

async def cancel_raw_video(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cancel the video generation process."""
    await update.message.reply_text("Raw video creation canceled.")
    return ConversationHandler.END
'''

content, count1 = re.subn(pattern_old, replacement_new, content, flags=re.DOTALL)
print(f"Replaced {count1} function bodies.")

# Register command handler
pattern_old_cmd = r"application\.add_handler\(CommandHandler\(\"create_video\", create_video_command\)\)"
replacement_new_cmd = '''raw_video_conv_handler = ConversationHandler(
        entry_points=[CommandHandler('create_raw_video', create_raw_video_start)],
        states={
            SELECT_AUDIO_RAW: [MessageHandler(filters.TEXT & ~(filters.COMMAND), process_raw_video_selection)],
        },
        fallbacks=[CommandHandler('cancel', cancel_raw_video)]
    )
    application.add_handler(raw_video_conv_handler)'''

content, count2 = re.subn(pattern_old_cmd, replacement_new_cmd, content)
print(f"Replaced {count2} handler registrations.")

# There might actually be an orphan add_handler(CommandHandler("create_video", create_video_command)) left over if we weren't careful. Let's explicitly look for it:
content = content.replace('application.add_handler(CommandHandler("create_video", create_video_command))\n', '')

with open("telegram_bot.py", "w") as f:
    f.write(content)

