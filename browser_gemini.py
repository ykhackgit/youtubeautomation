import sys
import time
import asyncio
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException

class BrowserGeminiSession:
    def __init__(self, headless=False, profile_path=None):
        """
        Initializes a Chrome browser session for scraping Gemini.
        Requires a profile with an active Google login session to avoid authentication blocks.
        Do NOT use automated send_keys for Google login, as it triggers anti-bot protections.
        """
        self.options = webdriver.ChromeOptions()
        if headless:
            self.options.add_argument('--headless=new')
        self.options.add_argument('--no-sandbox')
        self.options.add_argument('--disable-dev-shm-usage')
        self.options.add_argument('--disable-gpu')
        self.options.add_argument('--window-size=1920,1080')
        
        # Disable detection methods
        self.options.add_argument("--disable-blink-features=AutomationControlled")
        self.options.add_experimental_option("excludeSwitches", ["enable-automation"])
        self.options.add_experimental_option("useAutomationExtension", False)
        
        if profile_path:
            # Expand ~ if provided
            import os
            profile_path = os.path.expanduser(profile_path)
            self.options.add_argument(f"user-data-dir={profile_path}")
            
        print("Launching Gemini Browser Session (Local Profile Mode)...", file=sys.stderr)
        self.driver = webdriver.Chrome(options=self.options)
        
        # Provide a stealthy navigator property
        self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        
        self.driver.get('https://gemini.google.com/app')
        time.sleep(3)
        
        # Track chat count for periodic refreshing
        self.chat_count = 0
        
        # Wait for the chat box or login screen to determine status
        try:
            WebDriverWait(self.driver, 15).until(
                EC.presence_of_element_located((By.XPATH, "//*[@contenteditable='true'] | //textarea | //rich-textarea"))
            )
            print("Gemini chat interface loaded successfully.", file=sys.stderr)
            self.is_ready = True
        except TimeoutException:
            print("WARNING: Gemini chat interface did not load. You likely need to authenticate.", file=sys.stderr)
            print("Since you are running this with your local profile, make sure you are logged into Google in the popped-up window.", file=sys.stderr)
            self.is_ready = False

    def generate_content_sync(self, prompt: str, timeout: int = 60) -> str:
        """
        Synchronously sends a prompt to Gemini and waits for the response.
        Should be run inside an executor to avoid blocking async loops.
        """
        try:
            # Check if the driver is still alive before doing anything
            self.driver.current_url
        except Exception:
            self.is_ready = False
            return "Error: The Chrome browser window was closed or crashed. Please restart the bot."
            
        if getattr(self, 'init_error', None):
             return f"Error: Browser session failed to start properly. Details: {self.init_error}"
             
        if not getattr(self, 'is_ready', False):
            return "Error: Gemini browser session is not authenticated or failed to load."

        # Periodic refresh
        self.chat_count += 1
        if self.chat_count % 8 == 0:
            try:
                print("Refreshing Gemini session to clear memory and context...", file=sys.stderr)
                self.driver.refresh()
                WebDriverWait(self.driver, 15).until(
                    EC.presence_of_element_located((By.XPATH, "//*[@contenteditable='true'] | //textarea | //rich-textarea"))
                )
                time.sleep(2) # Give it a moment to fully initialize the chat hooks
            except Exception as e:
                print(f"Failed to refresh session: {e}", file=sys.stderr)

        try:
            # 1. Find the input box using multiple possible targets
            text_areas = WebDriverWait(self.driver, 10).until(
                EC.presence_of_all_elements_located((By.XPATH, "//*[@contenteditable='true'] | //rich-textarea//p | //rich-textarea//div | //textarea"))
            )
            
            interacted = False
            active_text_area = None
            
            for ta in reversed(text_areas): # Try innermost/last elements first
                try:
                    self.driver.execute_script("arguments[0].scrollIntoView(true);", ta)
                    time.sleep(0.2)
                    ta.click()
                    ta.send_keys(Keys.CONTROL + "a")
                    ta.send_keys(Keys.DELETE)
                    ta.send_keys(prompt)
                    active_text_area = ta
                    interacted = True
                    break
                except Exception:
                    continue
                    
            if not interacted:
                return "Error: Could not interact with any chat input box."

            time.sleep(0.5)
            
            # 3. Click send (or press Enter)
            try:
                # Often it's a button with aria-label="Send message" or similar
                send_button = self.driver.find_element(By.XPATH, "//button[contains(@aria-label, 'Send') or contains(@aria-label, 'Submit')] | //*[@aria-label='Send message']")
                self.driver.execute_script("arguments[0].click();", send_button)
            except NoSuchElementException:
                # Fallback to hitting enter
                if active_text_area:
                    active_text_area.send_keys(Keys.ENTER)
                
            time.sleep(1) # wait for animation to start
            
            # Track how many responses exist before generation starts
            initial_responses = len(self.driver.find_elements(By.TAG_NAME, "model-response"))
            
            # Wait for a new response bubble to appear
            start_time = time.time()
            while len(self.driver.find_elements(By.TAG_NAME, "model-response")) <= initial_responses:
                if time.time() - start_time > 15: # 15s wait for start
                    return "Error: Timed out waiting for Gemini to start responding."
                time.sleep(0.5)
            
            previous_text = ""
            stable_count = 0
            
            start_time = time.time()
            while time.time() - start_time < timeout:
                # Re-fetch the last response inside the loop to ensure we get dynamic DOM updates
                responses = self.driver.find_elements(By.TAG_NAME, "model-response")
                if not responses:
                    continue
                    
                last_response = responses[-1]
                current_text = last_response.text
                
                if current_text and current_text == previous_text:
                    stable_count += 1
                else:
                    stable_count = 0
                    previous_text = current_text
                
                # If text hasn't changed for ~3 seconds (6 * 0.5s checks), consider it done
                if stable_count >= 6:
                    break
                    
                time.sleep(0.5)
                
            return previous_text.strip()
            
        except Exception as e:
            return f"Error during browser scraping: {str(e)}"

    async def generate_content_async(self, prompt: str, timeout: int = 60) -> str:
        """Asynchronous wrapper for generate_content_sync."""
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, lambda: self.generate_content_sync(prompt, timeout))
        
    def upload_file_sync(self, base64_data: str, mime_type: str = "image/jpeg") -> bool:
        """Injects a file directly into the Gemini chat box using a simulated clipboard paste."""
        if not getattr(self, 'is_ready', False):
            return False
            
        js_script = """
        async function pasteImage(base64Data, mimeType) {
            try {
                const res = await fetch(`data:${mimeType};base64,${base64Data}`);
                const blob = await res.blob();
                const file = new File([blob], "upload.jpg", {type: mimeType});
                const dt = new DataTransfer();
                dt.items.add(file);
                
                const el = document.querySelector('.ql-editor') || document.querySelector('rich-textarea p');
                if (el) {
                    let e = new ClipboardEvent('paste', {
                        clipboardData: dt,
                        bubbles: true,
                        cancelable: true
                    });
                    el.dispatchEvent(e);
                    return true;
                }
                return false;
            } catch (err) {
                return false;
            }
        }
        return await pasteImage(arguments[0], arguments[1]);
        """
        try:
            return self.driver.execute_script(js_script, base64_data, mime_type)
        except Exception as e:
            print(f"File upload to browser failed: {e}", file=sys.stderr)
            return False

    async def upload_file_async(self, base64_data: str, mime_type: str = "image/jpeg") -> bool:
        """Asynchronous wrapper for upload_file_sync."""
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, lambda: self.upload_file_sync(base64_data, mime_type))

    def close(self):
        """Clean up the browser session."""
        try:
            self.driver.quit()
        except:
            pass
