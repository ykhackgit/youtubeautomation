import asyncio
from browser_gemini import BrowserGeminiSession

async def main():
    bs = BrowserGeminiSession(headless=False)
    
    print("Generating image...")
    # Send a prompt to generate an image
    response = await bs.generate_content_async("Generate an image of a red cube")
    print(f"Text Response: {response}")
    
    # Get the last message's HTML to see the image structure
    html = await bs.page.evaluate('''() => {
        const msgs = document.querySelectorAll('message-content');
        if (msgs.length > 0) {
            return msgs[msgs.length - 1].innerHTML;
        }
        return '';
    }''')
    
    with open('image_test.html', 'w', encoding='utf-8') as f:
        f.write(html)
        
    print("Saved HTML to image_test.html")
    await bs.close()

if __name__ == "__main__":
    asyncio.run(main())
