"""
Telegram Bot for DL Test Slot Booking Automation
"""

import os
import logging
import base64
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters
from telegram.error import Conflict
from dl_booking_automation import DLBookingAutomation
import asyncio
from datetime import datetime
import pytz
import time
import glob

# Try to load environment variables from .env file
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # python-dotenv not installed, skip

# Configure logging first
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Try to import google.genai for Gemini (new package)
try:
    from google import genai
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False
    logger.warning("google-genai not installed. AI captcha solving will not work.")

# Cache for Gemini client to avoid repeated initialization
_gemini_client_cache = {}

# Cleanup function for old captcha files
def cleanup_captcha_files():
    """Clean up any leftover captcha files"""
    try:
        captcha_files = glob.glob("captcha_image*.jpg") + glob.glob("captcha_image*.png")
        for file in captcha_files:
            try:
                if os.path.exists(file):
                    # Check if file is older than 5 minutes
                    file_age = time.time() - os.path.getmtime(file)
                    if file_age > 300:  # 5 minutes
                        os.remove(file)
                        logger.debug(f"Cleaned up old captcha file: {file}")
            except Exception as e:
                logger.debug(f"Could not remove captcha file {file}: {e}")
    except Exception as e:
        logger.debug(f"Error in cleanup_captcha_files: {e}")

# Run cleanup on import
cleanup_captcha_files()

# Bot token - Load from environment variable (required)
# For security: Use environment variable BOT_TOKEN in .env file
BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN environment variable is required. Please set it in your .env file.")

# Authorized user IDs - Load from environment variable (required)
# To find your user ID, start a chat with @userinfobot on Telegram
# Set via AUTHORIZED_USERS environment variable (comma-separated)
AUTHORIZED_USERS_STR = os.getenv("AUTHORIZED_USERS")
if not AUTHORIZED_USERS_STR:
    raise ValueError("AUTHORIZED_USERS environment variable is required. Please set it in your .env file.")
AUTHORIZED_USERS = [int(uid.strip()) for uid in AUTHORIZED_USERS_STR.split(",")]

# Store automation instances per user
user_automations = {}

# Global bot pause state
BOT_PAUSED = False
MANUAL_PAUSE_OVERRIDE = False  # True if user manually paused/resumed (overrides schedule)

# Scheduled pause/resume times (IST - GMT+5:30)
PAUSE_HOUR = 21  # 9 PM IST
RESUME_HOUR = 7  # 7 AM IST
IST = pytz.timezone('Asia/Kolkata')  # Indian Standard Time

# Check interval (in seconds) - Load from environment variable (required)
CHECK_INTERVAL_STR = os.getenv("CHECK_INTERVAL", "1800")
DEFAULT_CHECK_INTERVAL = int(CHECK_INTERVAL_STR)

# Application credentials - Load from environment variables (required)
DEFAULT_APPLICATION_NUMBER = os.getenv("APPLICATION_NUMBER")
if not DEFAULT_APPLICATION_NUMBER:
    raise ValueError("APPLICATION_NUMBER environment variable is required. Please set it in your .env file.")

DEFAULT_DOB = os.getenv("DOB")
if not DEFAULT_DOB:
    raise ValueError("DOB environment variable is required. Please set it in your .env file.")

# Captcha solving method: 'manual' or 'ai' - Load from environment variable
DEFAULT_CAPTCHA_METHOD = os.getenv("CAPTCHA_METHOD", "ai")

# Gemini API key - Load from environment variable (required)
DEFAULT_GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if not DEFAULT_GEMINI_API_KEY:
    raise ValueError("GEMINI_API_KEY environment variable is required. Please set it in your .env file.")


def is_authorized(user_id: int) -> bool:
    """Check if user is authorized to use the bot"""
    if not AUTHORIZED_USERS:
        logger.error("AUTHORIZED_USERS is empty. Please set it in your .env file.")
        return False
    return user_id in AUTHORIZED_USERS


async def check_authorization(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """Check authorization and send message if unauthorized"""
    user_id = update.effective_user.id
    if not is_authorized(user_id):
        await update.message.reply_text(
            "❌ *Access Denied*\n\n"
            "You are not authorized to use this bot.\n"
            "Contact the bot administrator for access.",
            parse_mode='Markdown'
        )
        return False
    return True


def ensure_user_setup(user_id):
    """Ensure user has default setup, create if not exists"""
    if user_id not in user_automations:
        automation = DLBookingAutomation(DEFAULT_APPLICATION_NUMBER, DEFAULT_DOB)
        user_automations[user_id] = {
            'automation': automation,
            'app_no': DEFAULT_APPLICATION_NUMBER,
            'dob': DEFAULT_DOB,
            'monitoring': False,
            'waiting_for_captcha': False,
            'captcha_code': None,
            'check_interval': DEFAULT_CHECK_INTERVAL,
            'captcha_method': DEFAULT_CAPTCHA_METHOD,
            'gemini_api_key': DEFAULT_GEMINI_API_KEY,
            'waiting_for_setup_app_no': False,
            'waiting_for_setup_dob': False,
            'monitoring_task': None
        }


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start command handler"""
    if not await check_authorization(update, context):
        return
    user_id = update.effective_user.id
    ensure_user_setup(user_id)  # Auto-setup with defaults
    
    welcome_message = r"""
🤖 *DL Test Slot Booking Bot*

Welcome! I can help you automate DL test slot booking.

*Available Commands:*
/start - Show this help message
/myid - Get your Telegram user ID \(for authorization setup\)
/setup - Set application number and DOB \(optional, defaults are set\)
/check - Check slot availability once
/monitor - Start continuous monitoring
/stop - Stop monitoring
/pause - Pause all bot operations
/resume - Resume bot operations
/interval - Set check interval \(default: 30 minutes\)
/captcha_method - Set captcha solving method
/set_gemini_key - Set Gemini API key for AI solving
/status - Check current status

*Security Setup:*
1\. Use /myid to get your Telegram user ID
2\. Add your user ID to the AUTHORIZED_USERS list in telegram_bot.py
3\. Restart the bot to enable authorization

*How it works:*
1\. Default credentials are already set \(you can change with /setup\)
2\. Use /captcha_method to choose manual or AI solving
3\. If using AI, set your Gemini API key with /set_gemini_key
4\. Use /check to check once, or /monitor to continuously check
5\. Captcha will be solved automatically \(AI\) or manually \(you solve\)

Let's get started! Use /check or /monitor\.
"""
    await update.message.reply_text(welcome_message, parse_mode='Markdown')


async def get_my_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Get user's Telegram ID for authorization setup"""
    user_id = update.effective_user.id
    username = update.effective_user.username or "N/A"
    first_name = update.effective_user.first_name or "N/A"
    
    await update.message.reply_text(
        f"*Your Telegram Information:*\n\n"
        f"User ID: `{user_id}`\n"
        f"Username: @{username}\n"
        f"Name: {first_name}\n\n"
        f"*To authorize yourself:*\n"
        f"1. Open `telegram_bot.py`\n"
        f"2. Find the `AUTHORIZED_USERS` list\n"
        f"3. Add your user ID: `{user_id}`\n"
        f"4. Restart the bot\n\n"
        f"Example:\n"
        f"```python\n"
        f"AUTHORIZED_USERS = [\n"
        f"    {user_id}\n"
        f"]\n"
        f"```",
        parse_mode='Markdown'
    )


async def setup(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Setup command to configure application number and DOB"""
    user_id = update.effective_user.id
    
    if len(context.args) == 2:
        app_no = context.args[0]
        dob = context.args[1]
        
        # Create automation instance
        automation = DLBookingAutomation(app_no, dob)
        user_automations[user_id] = {
            'automation': automation,
            'app_no': app_no,
            'dob': dob,
            'monitoring': False,
            'waiting_for_captcha': False,
            'captcha_code': None,
            'check_interval': DEFAULT_CHECK_INTERVAL,
            'captcha_method': DEFAULT_CAPTCHA_METHOD,
            'gemini_api_key': DEFAULT_GEMINI_API_KEY,
            'waiting_for_setup_app_no': False,
            'waiting_for_setup_dob': False,
            'monitoring_task': None
        }
        
        await update.message.reply_text(
            f"✅ *Setup Complete!*\n\n"
            f"Application Number: `{app_no}`\n"
            f"Date of Birth: `{dob}`\n\n"
            f"Now you can use /check or /monitor",
            parse_mode='Markdown'
        )
    else:
        # Ask for input interactively
        ensure_user_setup(user_id)  # Ensure defaults are set first
        await update.message.reply_text(
            "📝 *Setup Credentials*\n\n"
            "Please send your Application Number:",
            parse_mode='Markdown'
        )
        user_automations[user_id]['waiting_for_setup_app_no'] = True
        user_automations[user_id]['waiting_for_setup_dob'] = False


async def solve_captcha_with_gemini(captcha_file, api_key):
    """
    Solve CAPTCHA using Gemini AI (optimized with client caching)
    Uses the new google.genai package
    
    Args:
        captcha_file: Path to CAPTCHA image file
        api_key: Gemini API key
        
    Returns:
        str: Solved CAPTCHA text, or None if failed
    """
    if not GEMINI_AVAILABLE:
        return None
    
    try:
        # Get or create Gemini client (cached per API key)
        cache_key = f"client_{api_key}"
        if cache_key not in _gemini_client_cache:
            client = genai.Client(api_key=api_key)
            _gemini_client_cache[cache_key] = client
            logger.debug("Created new Gemini client (cached)")
        else:
            client = _gemini_client_cache[cache_key]
            logger.debug("Using cached Gemini client")
        
        # Use gemini-2.5-flash as per official documentation
        # This is the recommended model from the quickstart guide
        model_name = 'gemini-2.5-flash'
        logger.info(f"Using model: {model_name}")
        
        # Create prompt - emphasize accuracy, order, and case sensitivity
        prompt = """You are an OCR system. Look at this CAPTCHA image carefully.

IMPORTANT RULES:
1. Read the characters from LEFT TO RIGHT in the exact order they appear
2. Preserve the EXACT case (uppercase/lowercase) of each character
3. Do NOT rearrange, swap, or reorder any characters
4. Do NOT add or remove any characters
5. Return ONLY the characters, nothing else - no explanations, no spaces, no punctuation

The CAPTCHA may have noise, distortion, or background patterns, but extract the visible text characters in their exact left-to-right order with correct case.

Example: If you see "AbC123" from left to right, return exactly "AbC123" - not "ABC123" or "123AbC"."""
        
        # Read image file using PIL (lazy import to save memory)
        from PIL import Image
        image = None
        try:
            image = Image.open(captcha_file)
            
            # Generate content using new google.genai API
            # According to official docs: https://ai.google.dev/gemini-api/docs/quickstart
            # The contents parameter can accept strings or multimodal content
            # For images, we'll use PIL Image object which should be automatically handled
            # Try with gemini-2.5-flash first (official recommended model)
            response = client.models.generate_content(
                model=model_name,
                contents=[prompt, image]
            )
        except Exception as api_error:
            error_str = str(api_error)
            logger.debug(f"API call failed: {api_error}")
            
            # Check if it's a quota/rate limit error
            if '429' in error_str or 'quota' in error_str.lower() or 'RESOURCE_EXHAUSTED' in error_str:
                logger.error("Gemini API quota/rate limit exceeded. Falling back to manual captcha entry.")
                raise  # Re-raise to trigger fallback to manual entry
            
            # Check if it's a 404 (model not found) - try alternative models
            if '404' in error_str or 'NOT_FOUND' in error_str:
                logger.warning(f"Model {model_name} not found, trying alternative models...")
                fallback_models = ['gemini-1.5-flash', 'gemini-1.5-pro', 'gemini-pro']
                for fallback_model in fallback_models:
                    try:
                        logger.info(f"Trying fallback model: {fallback_model}")
                        response = client.models.generate_content(
                            model=fallback_model,
                            contents=[prompt, image]
                        )
                        logger.info(f"Successfully used model: {fallback_model}")
                        break
                    except Exception as fallback_error:
                        logger.debug(f"Fallback model {fallback_model} failed: {fallback_error}")
                        continue
                else:
                    # All fallback models failed
                    logger.error("All models failed. Check API key and available models.")
                    raise api_error
            else:
                # Other error - re-raise
                raise
        finally:
            # Close image immediately to free memory
            if image:
                try:
                    image.close()
                except:
                    pass
        
        # Extract text from response
        captcha_text = None
        try:
            # New API structure - response should have text attribute
            if hasattr(response, 'text') and response.text:
                captcha_text = response.text.strip()
            elif hasattr(response, 'candidates') and response.candidates:
                # Fallback to candidates structure
                if len(response.candidates) > 0:
                    candidate = response.candidates[0]
                    if hasattr(candidate, 'content') and candidate.content:
                        if hasattr(candidate.content, 'parts') and candidate.content.parts:
                            if len(candidate.content.parts) > 0:
                                part = candidate.content.parts[0]
                                if hasattr(part, 'text') and part.text:
                                    captcha_text = part.text.strip()
        except Exception as e:
            logger.error(f"Error extracting text from Gemini response: {e}")
            logger.debug(f"Response object: {response}")
            return None
        
        if not captcha_text:
            logger.error("Could not extract text from Gemini response. Response structure may have changed.")
            logger.debug(f"Response type: {type(response)}, Response attributes: {dir(response)}")
            return None
        
        # Remove any extra whitespace, newlines, but preserve character order
        captcha_text = ''.join(captcha_text.split())
        
        # Keep only alphanumeric characters, preserving order
        import re
        captcha_text = ''.join(re.findall(r'[A-Za-z0-9]', captcha_text))
        
        logger.info(f"AI extracted captcha: '{captcha_text}'")
        
        return captcha_text if captcha_text else None
        
    except Exception as e:
        error_str = str(e)
        logger.error(f"Error solving captcha with Gemini: {e}")
        
        # Check for quota errors
        if 'quota' in error_str.lower() or '429' in error_str:
            logger.error("Gemini API quota exceeded. Possible reasons:")
            logger.error("1. Free tier quota exhausted")
            logger.error("2. API key doesn't have free tier access")
            logger.error("3. Rate limit exceeded - please wait and try again")
            logger.error("Consider using /set_gemini_key with a different API key or wait before retrying.")
        
        return None


async def attempt_login_with_retry(update, context, user_id, automation, captcha_method, attempt_num=None, is_monitoring=False):
    """
    Attempt login with captcha retry logic. Retries up to max_retries times.
    
    Returns:
        tuple: (success: bool, captcha_code: str or None, max_retries_reached: bool)
    """
    max_retries = 5  # Maximum retry attempts
    retry_count = 0
    
    while retry_count < max_retries:
        # Check if monitoring was stopped (for monitoring mode)
        if is_monitoring and not user_automations[user_id].get('monitoring', False):
            logger.info("Monitoring stopped during login attempt")
            return (False, None, False)
        
        retry_count += 1
        attempt_text = f" (Retry #{retry_count})" if retry_count > 1 else ""
        if attempt_num:
            attempt_text = f" - Attempt #{attempt_num}{attempt_text}"
        
        try:
            # Navigate to booking page and get captcha
            if not automation.select_state("JK"):
                if is_monitoring:
                    await context.bot.send_message(
                        chat_id=update.effective_chat.id,
                        text=f"❌ Failed to select state{attempt_text}"
                    )
                else:
                    await update.message.reply_text("❌ Failed to select state")
                return (False, None, False)
            
            await asyncio.sleep(0.5)  # Reduced delay
            
            if not automation.navigate_to_appointments():
                if is_monitoring:
                    await context.bot.send_message(
                        chat_id=update.effective_chat.id,
                        text=f"❌ Failed to navigate to appointments{attempt_text}"
                    )
                else:
                    await update.message.reply_text("❌ Failed to navigate to appointments")
                return (False, None, False)
            
            await asyncio.sleep(0.5)  # Reduced delay
            
            if not automation.navigate_to_dl_slot_booking():
                if is_monitoring:
                    await context.bot.send_message(
                        chat_id=update.effective_chat.id,
                        text=f"❌ Failed to navigate to DL slot booking{attempt_text}"
                    )
                else:
                    await update.message.reply_text("❌ Failed to navigate to DL slot booking")
                return (False, None, False)
            
            await asyncio.sleep(0.5)  # Reduced delay
            
            # Get captcha image
            captcha_file = automation.get_captcha_image()
            
            if not captcha_file or not os.path.exists(captcha_file):
                if is_monitoring:
                    await context.bot.send_message(
                        chat_id=update.effective_chat.id,
                        text=f"❌ Failed to fetch captcha image{attempt_text}. Retrying..."
                    )
                else:
                    await update.message.reply_text("❌ Failed to fetch captcha image. Retrying...")
                await asyncio.sleep(2)
                continue
            
            captcha_code = None
            
            # Try AI solving if method is 'ai'
            if captcha_method == 'ai':
                gemini_key = user_automations[user_id].get('gemini_api_key') or DEFAULT_GEMINI_API_KEY
                if gemini_key:
                    if is_monitoring:
                        await context.bot.send_message(
                            chat_id=update.effective_chat.id,
                            text=f"🤖 Solving captcha with AI{attempt_text}..."
                        )
                    else:
                        await update.message.reply_text(f"🤖 Solving captcha with AI{attempt_text}...")
                    
                    # Send captcha image even when using AI
                    with open(captcha_file, 'rb') as photo:
                        if is_monitoring:
                            await context.bot.send_photo(
                                chat_id=update.effective_chat.id,
                                photo=photo,
                                caption=f"🔐 CAPTCHA Image (AI solving...){attempt_text}"
                            )
                        else:
                            await update.message.reply_photo(
                                photo=photo,
                                caption=f"🔐 CAPTCHA Image (AI solving...){attempt_text}"
                            )
                    
                    captcha_code = await solve_captcha_with_gemini(captcha_file, gemini_key)
                    
                    if captcha_code:
                        if is_monitoring:
                            await context.bot.send_message(
                                chat_id=update.effective_chat.id,
                                text=f"✅ AI solved captcha: `{captcha_code}`{attempt_text}",
                                parse_mode='Markdown'
                            )
                        else:
                            await update.message.reply_text(
                                f"✅ AI solved captcha: `{captcha_code}`{attempt_text}\nProcessing...",
                                parse_mode='Markdown'
                            )
                    else:
                        if is_monitoring:
                            await context.bot.send_message(
                                chat_id=update.effective_chat.id,
                                text=f"❌ AI failed to solve captcha{attempt_text}. Please enter manually:"
                            )
                        else:
                            await update.message.reply_text(
                                f"❌ AI failed to solve captcha{attempt_text}. Please enter manually:"
                            )
                        # Fall through to manual entry
                else:
                    if is_monitoring:
                        await context.bot.send_message(
                            chat_id=update.effective_chat.id,
                            text=f"⚠️ AI method selected but no valid Gemini API key set{attempt_text}.\nPlease enter captcha manually:"
                        )
                    else:
                        await update.message.reply_text(
                            f"⚠️ AI method selected but no valid Gemini API key set{attempt_text}.\nPlease enter captcha manually:"
                        )
                    # Fall through to manual entry
            
            # Manual solving
            if captcha_method == 'manual' or not captcha_code:
                with open(captcha_file, 'rb') as photo:
                    if is_monitoring:
                        await context.bot.send_photo(
                            chat_id=update.effective_chat.id,
                            photo=photo,
                            caption=f"🔐 Please enter the captcha code{attempt_text}:"
                        )
                    else:
                        await update.message.reply_photo(
                            photo=photo,
                            caption=f"🔐 Please enter the captcha code{attempt_text}:"
                        )
                
                user_automations[user_id]['waiting_for_captcha'] = True
                if is_monitoring:
                    user_automations[user_id]['monitor_attempt'] = attempt_num if attempt_num else retry_count
                else:
                    user_automations[user_id]['check_mode'] = True
                
                # Wait for captcha input (check monitoring status frequently)
                # Break the wait into smaller chunks to check monitoring status
                waited = 0
                timeout = 30  # 30 seconds total
                check_interval = 2  # Check every 2 seconds
                
                while waited < timeout:
                    # Check if monitoring was stopped
                    if is_monitoring and not user_automations[user_id].get('monitoring', False):
                        user_automations[user_id]['waiting_for_captcha'] = False
                        logger.info("Monitoring stopped while waiting for captcha")
                        return (False, None, False)
                    
                    # Check if captcha was received
                    if not user_automations[user_id].get('waiting_for_captcha', False):
                        captcha_code = user_automations[user_id].get('captcha_code')
                        break
                    
                    await asyncio.sleep(check_interval)
                    waited += check_interval
                
                # Check one more time after timeout
                if not user_automations[user_id].get('waiting_for_captcha', False):
                    captcha_code = user_automations[user_id].get('captcha_code')
                else:
                    # Timeout
                    user_automations[user_id]['waiting_for_captcha'] = False
                    # Check if monitoring was stopped
                    if is_monitoring and not user_automations[user_id].get('monitoring', False):
                        logger.info("Monitoring stopped during captcha timeout")
                        return (False, None, False)
                    
                    if is_monitoring:
                        await context.bot.send_message(
                            chat_id=update.effective_chat.id,
                            text=f"⏱️ Captcha timeout{attempt_text}. Retrying..."
                        )
                    else:
                        await update.message.reply_text("⏱️ Captcha timeout. Retrying...")
                    await asyncio.sleep(1)  # Reduced delay
                    continue
            
            # Clean up captcha file immediately after use
            if captcha_file and os.path.exists(captcha_file):
                try:
                    os.remove(captcha_file)
                except Exception as e:
                    logger.debug(f"Could not remove captcha file: {e}")
            
            # Periodic cleanup of old files
            if retry_count % 3 == 0:  # Every 3 retries
                cleanup_captcha_files()
            
            # Try login with captcha
            if captcha_code:
                login_result = automation.login(captcha_code)
                
                if login_result:
                    # Login successful!
                    return (True, captcha_code, False)
                else:
                    # Login failed - wrong captcha, retry
                    if is_monitoring:
                        await context.bot.send_message(
                            chat_id=update.effective_chat.id,
                            text=f"❌ Login failed - wrong captcha{attempt_text}. Fetching new captcha and retrying..."
                        )
                    else:
                        await update.message.reply_text(f"❌ Login failed - wrong captcha{attempt_text}. Fetching new captcha and retrying...")
                    await asyncio.sleep(2)
                    continue
            else:
                # No captcha code available, retry
                    await asyncio.sleep(1)  # Reduced delay
                    continue
                
        except Exception as e:
            logger.error(f"Error in attempt_login_with_retry: {e}")
            if is_monitoring:
                await context.bot.send_message(
                    chat_id=update.effective_chat.id,
                    text=f"❌ Error{attempt_text}: {str(e)}. Retrying..."
                )
            else:
                await update.message.reply_text(f"❌ Error{attempt_text}: {str(e)}. Retrying...")
            await asyncio.sleep(1)  # Reduced delay
            continue
    
    # Max retries reached
    if is_monitoring:
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=f"❌ Max retries ({max_retries}) reached for attempt #{attempt_num if attempt_num else 'N/A'}. Will try again in next interval."
        )
    else:
        await update.message.reply_text(
            f"❌ Max retries ({max_retries}) reached. Login failed. Please try /check again later."
        )
    return (False, None, True)


async def check_slots(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Check slot availability once"""
    if not await check_authorization(update, context):
        return
    
    if BOT_PAUSED:
        await update.message.reply_text(
            "⏸️ *Bot is Paused*\n\n"
            "Bot operations are currently paused.\n"
            "Use /resume to activate the bot.",
            parse_mode='Markdown'
        )
        return
    
    user_id = update.effective_user.id
    ensure_user_setup(user_id)  # Auto-setup with defaults
    
    await update.message.reply_text("🔍 Checking slot availability...")
    
    try:
        # Ensure automation exists
        if 'automation' not in user_automations[user_id]:
            ensure_user_setup(user_id)  # Re-setup if missing
        
        automation = user_automations[user_id].get('automation')
        if not automation:
            # Create automation if it doesn't exist
            app_no = user_automations[user_id].get('app_no', DEFAULT_APPLICATION_NUMBER)
            dob = user_automations[user_id].get('dob', DEFAULT_DOB)
            automation = DLBookingAutomation(app_no, dob)
            user_automations[user_id]['automation'] = automation
        
        captcha_method = user_automations[user_id].get('captcha_method', DEFAULT_CAPTCHA_METHOD)
        
        # Attempt login with retry logic
        success, captcha_code, max_retries_reached = await attempt_login_with_retry(
            update, context, user_id, automation, captcha_method, 
            attempt_num=None, is_monitoring=False
        )
        
        if success:
            # Login successful, proceed with booking check
            await process_login_and_booking(update, context, user_id, captcha_code)
        elif max_retries_reached:
            # Max retries reached - stop check function
            await update.message.reply_text(
                f"❌ Max retries (5) reached. Check stopped. Please try /check again later."
            )
        else:
            # Other failure (shouldn't happen with current logic, but handle it)
            await update.message.reply_text(
                "❌ Failed to login. Please try /check again later."
            )
            
    except Exception as e:
        logger.error(f"Error in check_slots: {e}")
        await update.message.reply_text(f"❌ Error: {str(e)}")


async def process_login_and_booking(update, context, user_id, captcha_code):
    """Process login and booking after captcha is solved"""
    ensure_user_setup(user_id)  # Ensure setup exists
    automation = user_automations[user_id].get('automation')
    if not automation:
        app_no = user_automations[user_id].get('app_no', DEFAULT_APPLICATION_NUMBER)
        dob = user_automations[user_id].get('dob', DEFAULT_DOB)
        automation = DLBookingAutomation(app_no, dob)
        user_automations[user_id]['automation'] = automation
    
    try:
        login_result = automation.login(captcha_code)
        
        if login_result:
            await asyncio.sleep(0.5)  # Reduced delay
            availability = automation.check_slot_availability()
            
            if availability.get('available') is False:
                days = availability.get('days', 'N/A')
                await update.message.reply_text(
                    f"ℹ️ *Slot Availability*\n\n"
                    f"No slots available for the next {days} days.",
                    parse_mode='Markdown'
                )
            else:
                # Try to book
                booking_result = automation.book_slot()
                
                # Handle new dict return format
                if isinstance(booking_result, dict):
                    if booking_result.get('success') is True:
                        await update.message.reply_text(
                            "🎉 *SUCCESS! Slot booked!* 🎉",
                            parse_mode='Markdown'
                        )
                    elif booking_result.get('success') is False:
                        # Check if it's a "no slots" message
                        if booking_result.get('days'):
                            days = booking_result.get('days')
                            await update.message.reply_text(
                                f"ℹ️ *Slot Availability*\n\n"
                                f"No slots available for the next {days} days.",
                                parse_mode='Markdown'
                            )
                        else:
                            await update.message.reply_text(
                                f"⚠️ {booking_result.get('message', 'Booking failed')}"
                            )
                    else:
                        await update.message.reply_text(
                            f"ℹ️ {booking_result.get('message', 'Status unclear')}"
                        )
                # Backward compatibility with bool return
                elif booking_result:
                    await update.message.reply_text(
                        "🎉 *SUCCESS! Slot booked!* 🎉",
                        parse_mode='Markdown'
                    )
                else:
                    await update.message.reply_text(
                        "⚠️ Booking failed or status unclear"
                    )
        else:
            await update.message.reply_text("❌ Login failed. Please check credentials or captcha.")
            
    except Exception as e:
        logger.error(f"Error processing login/booking: {e}")
        await update.message.reply_text(f"❌ Error: {str(e)}")

async def start_monitoring(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start continuous monitoring"""
    if not await check_authorization(update, context):
        return
    
    if BOT_PAUSED:
        await update.message.reply_text(
            "⏸️ *Bot is Paused*\n\n"
            "Bot operations are currently paused.\n"
            "Use /resume to activate the bot.",
            parse_mode='Markdown'
        )
        return
    
    user_id = update.effective_user.id
    ensure_user_setup(user_id)  # Auto-setup with defaults
    
    if user_automations[user_id].get('monitoring', False):
        await update.message.reply_text(
            "⚠️ Monitoring is already running. Use /stop to stop it first."
        )
        return
    
    user_automations[user_id]['monitoring'] = True
    interval_minutes = user_automations[user_id].get('check_interval', DEFAULT_CHECK_INTERVAL) // 60
    await update.message.reply_text(
        f"🔄 *Monitoring Started!*\n\n"
        f"I'll check for slots every {interval_minutes} minutes.\n"
        f"You'll receive a notification when each check starts.\n"
        f"You'll be notified when slots become available.\n\n"
        f"Use /stop to stop monitoring.\n"
        f"Use /interval [minutes] to change check interval.",
        parse_mode='Markdown'
    )
    
    # Start monitoring in background and store task reference
    monitoring_task = asyncio.create_task(monitor_loop(update, context, user_id))
    user_automations[user_id]['monitoring_task'] = monitoring_task


async def monitor_loop(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int):
    """Background monitoring loop"""
    ensure_user_setup(user_id)  # Ensure setup exists
    automation = user_automations[user_id].get('automation')
    if not automation:
        app_no = user_automations[user_id].get('app_no', DEFAULT_APPLICATION_NUMBER)
        dob = user_automations[user_id].get('dob', DEFAULT_DOB)
        automation = DLBookingAutomation(app_no, dob)
        user_automations[user_id]['automation'] = automation
    
    attempts = 0
    
    try:
        while user_automations[user_id].get('monitoring', False):
            # Check monitoring status at the start of each iteration
            if not user_automations[user_id].get('monitoring', False):
                logger.info("Monitoring stopped, exiting loop")
                break
            
            # Refresh check_interval at the start of each iteration to get the latest value
            check_interval = user_automations[user_id].get('check_interval', DEFAULT_CHECK_INTERVAL)
            attempts += 1
            
            # Send notification that check is starting (only every 5th attempt to reduce spam)
            if attempts == 1 or attempts % 5 == 0:
                interval_minutes = check_interval // 60
                await context.bot.send_message(
                    chat_id=update.effective_chat.id,
                    text=f"🔔 *Check #{attempts} Starting*\n\n"
                         f"Starting slot check now. Please solve the captcha when I send it.\n"
                         f"Next check in {interval_minutes} minutes.",
                    parse_mode='Markdown'
                )
            
            # Check monitoring status before starting login attempt
            if not user_automations[user_id].get('monitoring', False):
                logger.info("Monitoring stopped before login attempt")
                break
                
            try:
                captcha_method = user_automations[user_id].get('captcha_method', DEFAULT_CAPTCHA_METHOD)
                
                # Attempt login with retry logic (will retry up to max_retries)
                success, captcha_code, max_retries_reached = await attempt_login_with_retry(
                    update, context, user_id, automation, captcha_method,
                    attempt_num=attempts, is_monitoring=True
                )
                
                # Check if monitoring was stopped during login attempt
                if not user_automations[user_id].get('monitoring', False):
                    logger.info("Monitoring stopped during login attempt")
                    break
                
                if max_retries_reached:
                    # Max retries reached - wait for next interval
                    await context.bot.send_message(
                        chat_id=update.effective_chat.id,
                        text=f"⏸️ Attempt #{attempts}: Max retries reached. Waiting for next check interval..."
                    )
                    # Continue to next interval (will break out of inner while and wait)
                    break
                
                if success:
                    # Login successful, proceed with slot checking/booking
                    await asyncio.sleep(0.5)  # Reduced delay
                    availability = automation.check_slot_availability()
                    
                    if availability.get('available') is False:
                        days = availability.get('days', 'N/A')
                        await context.bot.send_message(
                            chat_id=update.effective_chat.id,
                            text=f"ℹ️ Attempt #{attempts}: No slots available for the next {days} days"
                        )
                    else:
                        # Try to book
                        booking_result = automation.book_slot()
                        
                        # Handle new dict return format
                        if isinstance(booking_result, dict):
                            if booking_result.get('success') is True:
                                await context.bot.send_message(
                                    chat_id=update.effective_chat.id,
                                    text="🎉 *SUCCESS! Slot booked!* 🎉\n\nMonitoring stopped.",
                                    parse_mode='Markdown'
                                )
                                user_automations[user_id]['monitoring'] = False
                                break
                            elif booking_result.get('success') is False:
                                # Check if it's a "no slots" message
                                if booking_result.get('days'):
                                    days = booking_result.get('days')
                                    await context.bot.send_message(
                                        chat_id=update.effective_chat.id,
                                        text=f"ℹ️ Attempt #{attempts}: No slots available for the next {days} days"
                                    )
                                else:
                                    await context.bot.send_message(
                                        chat_id=update.effective_chat.id,
                                        text=f"⚠️ Attempt #{attempts}: {booking_result.get('message', 'Booking failed')}"
                                    )
                            else:
                                await context.bot.send_message(
                                    chat_id=update.effective_chat.id,
                                    text=f"ℹ️ Attempt #{attempts}: {booking_result.get('message', 'Status unclear')}"
                                )
                        # Backward compatibility with bool return
                        elif booking_result:
                            await context.bot.send_message(
                                chat_id=update.effective_chat.id,
                                text="🎉 *SUCCESS! Slot booked!* 🎉\n\nMonitoring stopped.",
                                parse_mode='Markdown'
                            )
                            user_automations[user_id]['monitoring'] = False
                            break
                        else:
                            await context.bot.send_message(
                                chat_id=update.effective_chat.id,
                                text=f"⚠️ Attempt #{attempts}: Booking failed or unclear status"
                            )
                    
                    # Wait before next check (only if monitoring is still active)
                    if user_automations[user_id].get('monitoring', False):
                        # Only send waiting message every 5th attempt
                        if attempts % 5 == 0:
                            await context.bot.send_message(
                                chat_id=update.effective_chat.id,
                                text=f"⏳ Waiting {check_interval // 60} minutes before next check..."
                            )
                        await asyncio.sleep(check_interval)
                else:
                    # Login failed (other error, not max retries - shouldn't normally happen)
                    await context.bot.send_message(
                        chat_id=update.effective_chat.id,
                        text=f"❌ Attempt #{attempts}: Login failed. Waiting for next check interval..."
                    )
                    # Wait before next check
                    if user_automations[user_id].get('monitoring', False):
                        # Only send waiting message every 5th attempt
                        if attempts % 5 == 0:
                            await context.bot.send_message(
                                chat_id=update.effective_chat.id,
                                text=f"⏳ Waiting {check_interval // 60} minutes before next check..."
                            )
                        await asyncio.sleep(check_interval)
                
            except Exception as e:
                logger.error(f"Error in monitor loop: {e}")
                # Refresh check_interval before waiting
                check_interval = user_automations[user_id].get('check_interval', DEFAULT_CHECK_INTERVAL)
                await context.bot.send_message(
                    chat_id=update.effective_chat.id,
                    text=f"❌ Error in attempt #{attempts}: {str(e)}"
                )
                await asyncio.sleep(check_interval)
                
    except Exception as e:
        logger.error(f"Fatal error in monitor loop: {e}")
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=f"❌ Fatal error: {str(e)}\nMonitoring stopped."
        )
        user_automations[user_id]['monitoring'] = False


async def set_interval(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Set check interval in minutes"""
    if not await check_authorization(update, context):
        return
    user_id = update.effective_user.id
    ensure_user_setup(user_id)  # Auto-setup with defaults
    
    if not context.args:
        current_interval = user_automations[user_id].get('check_interval', DEFAULT_CHECK_INTERVAL) // 60
        await update.message.reply_text(
            f"ℹ️ Current check interval: {current_interval} minutes\n\n"
            f"Now send the interval in minutes:"
        )
        user_automations[user_id]['waiting_for_interval'] = True
        return
    
    try:
        minutes = int(context.args[0])
        if minutes < 1:
            await update.message.reply_text("❌ Interval must be at least 1 minute")
            return
        if minutes > 1440:  # 24 hours
            await update.message.reply_text("❌ Interval cannot be more than 1440 minutes (24 hours)")
            return
        
        user_automations[user_id]['check_interval'] = minutes * 60
        await update.message.reply_text(
            f"✅ Check interval set to {minutes} minutes\n\n"
            f"Note: This will apply to the next monitoring cycle.\n"
            f"Use /monitor to start monitoring with this interval."
        )
    except ValueError:
        await update.message.reply_text("❌ Invalid number. Please provide minutes as a number.")


async def stop_monitoring(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Stop monitoring"""
    if not await check_authorization(update, context):
        return
    user_id = update.effective_user.id
    
    if user_id not in user_automations:
        await update.message.reply_text("❌ No active session")
        return
    
    if not user_automations[user_id].get('monitoring', False):
        await update.message.reply_text("ℹ️ Monitoring is not running")
        return
    
    # Set monitoring flag to False
    user_automations[user_id]['monitoring'] = False
    
    # Cancel the monitoring task if it exists
    monitoring_task = user_automations[user_id].get('monitoring_task')
    if monitoring_task and not monitoring_task.done():
        monitoring_task.cancel()
        try:
            await monitoring_task
        except asyncio.CancelledError:
            pass
    
    # Clear waiting states
    user_automations[user_id]['waiting_for_captcha'] = False
    
    await update.message.reply_text("✅ Monitoring stopped")


def check_scheduled_pause():
    """Check if bot should be paused based on schedule (IST time)"""
    global BOT_PAUSED, MANUAL_PAUSE_OVERRIDE
    
    # If user manually paused/resumed, don't auto-schedule
    if MANUAL_PAUSE_OVERRIDE:
        return
    
    # Get current IST time
    ist_now = datetime.now(IST)
    current_hour = ist_now.hour
    
    # Pause between 9 PM (21:00) and 7 AM (07:00)
    if current_hour >= PAUSE_HOUR or current_hour < RESUME_HOUR:
        if not BOT_PAUSED:
            BOT_PAUSED = True
            logger.info(f"🤖 Bot auto-paused at {ist_now.strftime('%H:%M:%S IST')} (scheduled pause)")
    else:
        if BOT_PAUSED:
            BOT_PAUSED = False
            logger.info(f"🤖 Bot auto-resumed at {ist_now.strftime('%H:%M:%S IST')} (scheduled resume)")


async def pause_bot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Pause bot operations (manual override)"""
    global BOT_PAUSED, MANUAL_PAUSE_OVERRIDE
    if not await check_authorization(update, context):
        return
    
    BOT_PAUSED = True
    MANUAL_PAUSE_OVERRIDE = True  # Override automatic schedule
    
    # Stop all active monitoring
    user_id = update.effective_user.id
    if user_id in user_automations:
        user_automations[user_id]['monitoring'] = False
    
    ist_now = datetime.now(IST)
    await update.message.reply_text(
        f"⏸️ *Bot Paused (Manual)*\n\n"
        f"All bot operations are paused.\n"
        f"Current time: {ist_now.strftime('%H:%M:%S IST')}\n\n"
        f"Use /resume to start again.\n"
        f"Note: Manual pause overrides scheduled pause/resume.",
        parse_mode='Markdown'
    )


async def resume_bot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Resume bot operations (manual override)"""
    global BOT_PAUSED, MANUAL_PAUSE_OVERRIDE
    if not await check_authorization(update, context):
        return
    
    BOT_PAUSED = False
    MANUAL_PAUSE_OVERRIDE = True  # Override automatic schedule
    
    ist_now = datetime.now(IST)
    await update.message.reply_text(
        f"▶️ *Bot Resumed (Manual)*\n\n"
        f"Bot operations are active again!\n"
        f"Current time: {ist_now.strftime('%H:%M:%S IST')}\n\n"
        f"You can now use /check or /monitor.\n"
        f"Note: Manual resume overrides scheduled pause/resume.",
        parse_mode='Markdown'
    )


async def set_captcha_method(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Set captcha solving method"""
    if not await check_authorization(update, context):
        return
    user_id = update.effective_user.id
    ensure_user_setup(user_id)  # Auto-setup with defaults
    
    if not context.args:
        current_method = user_automations[user_id].get('captcha_method', DEFAULT_CAPTCHA_METHOD)
        await update.message.reply_text(
            f"ℹ️ Current captcha method: *{current_method}*\n\n"
            f"Now send the method: `manual` or `ai`",
            parse_mode='Markdown'
        )
        user_automations[user_id]['waiting_for_captcha_method'] = True
        return
    
    method = context.args[0].lower()
    if method not in ['manual', 'ai']:
        await update.message.reply_text(
            "❌ Invalid method. Send `manual` or `ai`"
        )
        return
    
    user_automations[user_id]['captcha_method'] = method
    user_automations[user_id]['waiting_for_captcha_method'] = False
    method_emoji = "🤖" if method == 'ai' else "👤"
    await update.message.reply_text(
        f"✅ Captcha method set to: *{method}* {method_emoji}\n\n"
        f"{'Note: Make sure to set your Gemini API key with /set_gemini_key' if method == 'ai' else 'You will need to manually enter captcha codes when prompted.'}",
        parse_mode='Markdown'
    )


async def set_gemini_key(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Set Gemini API key for AI captcha solving"""
    if not await check_authorization(update, context):
        return
    user_id = update.effective_user.id
    ensure_user_setup(user_id)  # Auto-setup with defaults
    
    if not context.args:
        current_key = user_automations[user_id].get('gemini_api_key')
        if current_key:
            # Show only first and last few characters for security
            masked_key = current_key[:8] + "..." + current_key[-4:] if len(current_key) > 12 else "***"
            await update.message.reply_text(
                f"ℹ️ Current Gemini API key: `{masked_key}`\n\n"
                f"Now send your new Gemini API key:\n\n"
                f"Get your API key from: https://makersuite.google.com/app/apikey",
                parse_mode='Markdown'
            )
        else:
            await update.message.reply_text(
                "ℹ️ No Gemini API key set.\n\n"
                f"Now send your Gemini API key:\n\n"
                f"Get your API key from: https://makersuite.google.com/app/apikey"
            )
        user_automations[user_id]['waiting_for_gemini_key'] = True
        return
    
    api_key = context.args[0].strip()
    
    if not api_key or len(api_key) < 10:
        await update.message.reply_text(
            "❌ Invalid API key. Please provide a valid Gemini API key."
        )
        return
    
    user_automations[user_id]['gemini_api_key'] = api_key
    user_automations[user_id]['waiting_for_gemini_key'] = False
    masked_key = api_key[:8] + "..." + api_key[-4:] if len(api_key) > 12 else "***"
    await update.message.reply_text(
        f"✅ Gemini API key set: `{masked_key}`\n\n"
        f"Now you can use /captcha_method ai to enable AI captcha solving.",
        parse_mode='Markdown'
    )


async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Check current status"""
    if not await check_authorization(update, context):
        return
    user_id = update.effective_user.id
    ensure_user_setup(user_id)  # Auto-setup with defaults
    
    info = user_automations[user_id]
    monitoring_status = "🟢 Running" if info.get('monitoring', False) else "🔴 Stopped"
    bot_status = "⏸️ Paused" if BOT_PAUSED else "▶️ Active"
    pause_mode = "Manual Override" if MANUAL_PAUSE_OVERRIDE else "Auto Schedule"
    interval_minutes = info.get('check_interval', DEFAULT_CHECK_INTERVAL) // 60
    captcha_method = info.get('captcha_method', DEFAULT_CAPTCHA_METHOD)
    gemini_key = info.get('gemini_api_key')
    gemini_status = "✅ Set" if gemini_key else "❌ Not set"
    
    ist_now = datetime.now(IST)
    next_pause = f"{PAUSE_HOUR}:00 IST" if ist_now.hour < PAUSE_HOUR else f"Tomorrow {PAUSE_HOUR}:00 IST"
    next_resume = f"{RESUME_HOUR}:00 IST" if ist_now.hour >= PAUSE_HOUR or ist_now.hour < RESUME_HOUR else f"Today {RESUME_HOUR}:00 IST"
    
    status_text = f"""
*Current Status:*

Bot Status: {bot_status} ({pause_mode})
Current Time: {ist_now.strftime('%H:%M:%S IST')}
Schedule: Pause at {PAUSE_HOUR}:00 IST | Resume at {RESUME_HOUR}:00 IST
Next Pause: {next_pause}
Next Resume: {next_resume}

Application Number: `{info['app_no']}`
Date of Birth: `{info['dob']}`
Check Interval: {interval_minutes} minutes
Monitoring: {monitoring_status}
Captcha Method: *{captcha_method}* {'🤖' if captcha_method == 'ai' else '👤'}
Gemini API Key: {gemini_status}
"""
    
    await update.message.reply_text(status_text, parse_mode='Markdown')


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle text messages (captcha codes and interactive command inputs)"""
    user_id = update.effective_user.id
    
    # Check authorization first
    if not is_authorized(user_id):
        await update.message.reply_text(
            "❌ *Access Denied*\n\n"
            "You are not authorized to use this bot.\n"
            "Contact the bot administrator for access.",
            parse_mode='Markdown'
        )
        return
    
    ensure_user_setup(user_id)  # Auto-setup with defaults
    
    # Handle interactive setup
    if user_automations[user_id].get('waiting_for_setup_app_no', False):
        app_no = update.message.text.strip()
        user_automations[user_id]['temp_app_no'] = app_no
        user_automations[user_id]['waiting_for_setup_app_no'] = False
        user_automations[user_id]['waiting_for_setup_dob'] = True
        await update.message.reply_text(
            "✅ Application Number received.\n\n"
            "Now send your Date of Birth (DD-MM-YYYY format):\n"
            "Example: 04-03-1974"
        )
        return
    
    if user_automations[user_id].get('waiting_for_setup_dob', False):
        dob = update.message.text.strip()
        app_no = user_automations[user_id].get('temp_app_no')
        
        # Ensure we have a valid app_no
        if not app_no:
            app_no = DEFAULT_APPLICATION_NUMBER
        
        # Create automation instance
        automation = DLBookingAutomation(app_no, dob)
        # Update existing dictionary instead of replacing it
        user_automations[user_id].update({
            'automation': automation,
            'app_no': app_no,
            'dob': dob,
            'waiting_for_setup_app_no': False,
            'waiting_for_setup_dob': False
        })
        
        await update.message.reply_text(
            f"✅ *Setup Complete!*\n\n"
            f"Application Number: `{app_no}`\n"
            f"Date of Birth: `{dob}`\n\n"
            f"Now you can use /check or /monitor",
            parse_mode='Markdown'
        )
        return
    
    # Handle interactive interval setting
    if user_automations[user_id].get('waiting_for_interval', False):
        try:
            minutes = int(update.message.text.strip())
            if minutes < 1:
                await update.message.reply_text("❌ Interval must be at least 1 minute. Please send a valid number:")
                return
            if minutes > 1440:  # 24 hours
                await update.message.reply_text("❌ Interval cannot be more than 1440 minutes (24 hours). Please send a valid number:")
                return
            
            user_automations[user_id]['check_interval'] = minutes * 60
            user_automations[user_id]['waiting_for_interval'] = False
            await update.message.reply_text(
                f"✅ Check interval set to {minutes} minutes\n\n"
                f"Note: This will apply to the next monitoring cycle.\n"
                f"Use /monitor to start monitoring with this interval."
            )
        except ValueError:
            await update.message.reply_text("❌ Invalid number. Please send a valid number in minutes:")
        return
    
    # Handle interactive captcha method setting
    if user_automations[user_id].get('waiting_for_captcha_method', False):
        method = update.message.text.strip().lower()
        if method not in ['manual', 'ai']:
            await update.message.reply_text("❌ Invalid method. Please send `manual` or `ai`:")
            return
        
        user_automations[user_id]['captcha_method'] = method
        user_automations[user_id]['waiting_for_captcha_method'] = False
        method_emoji = "🤖" if method == 'ai' else "👤"
        await update.message.reply_text(
            f"✅ Captcha method set to: *{method}* {method_emoji}\n\n"
            f"{'Note: Make sure to set your Gemini API key with /set_gemini_key' if method == 'ai' else 'You will need to manually enter captcha codes when prompted.'}",
            parse_mode='Markdown'
        )
        return
    
    # Handle interactive Gemini API key setting
    if user_automations[user_id].get('waiting_for_gemini_key', False):
        api_key = update.message.text.strip()
        
        if not api_key or len(api_key) < 10:
            await update.message.reply_text("❌ Invalid API key. Please send a valid Gemini API key:")
            return
        
        user_automations[user_id]['gemini_api_key'] = api_key
        user_automations[user_id]['waiting_for_gemini_key'] = False
        masked_key = api_key[:8] + "..." + api_key[-4:] if len(api_key) > 12 else "***"
        await update.message.reply_text(
            f"✅ Gemini API key set: `{masked_key}`\n\n"
            f"Now you can use /captcha_method ai to enable AI captcha solving.",
            parse_mode='Markdown'
        )
        return
    
    # Handle captcha codes
    if user_automations[user_id].get('waiting_for_captcha', False):
        captcha_code = update.message.text.strip()
        user_automations[user_id]['captcha_code'] = captcha_code
        user_automations[user_id]['waiting_for_captcha'] = False
        
        await update.message.reply_text(f"✅ Captcha received: `{captcha_code}`\nProcessing...", parse_mode='Markdown')
        
        # If in check mode, process immediately with retry logic
        if user_automations[user_id].get('check_mode', False):
            user_automations[user_id]['check_mode'] = False
            ensure_user_setup(user_id)  # Ensure setup exists
            automation = user_automations[user_id].get('automation')
            if not automation:
                app_no = user_automations[user_id].get('app_no', DEFAULT_APPLICATION_NUMBER)
                dob = user_automations[user_id].get('dob', DEFAULT_DOB)
                automation = DLBookingAutomation(app_no, dob)
                user_automations[user_id]['automation'] = automation
            captcha_method = user_automations[user_id].get('captcha_method', DEFAULT_CAPTCHA_METHOD)
            
            try:
                login_result = automation.login(captcha_code)
                
                if login_result:
                    # Login successful, proceed with booking check
                    await asyncio.sleep(0.5)  # Reduced delay
                    availability = automation.check_slot_availability()
                    
                    if availability.get('available') is False:
                        days = availability.get('days', 'N/A')
                        await update.message.reply_text(
                            f"ℹ️ *Slot Availability*\n\n"
                            f"No slots available for the next {days} days.",
                            parse_mode='Markdown'
                        )
                    else:
                        # Try to book
                        booking_result = automation.book_slot()
                        
                        # Handle new dict return format
                        if isinstance(booking_result, dict):
                            if booking_result.get('success') is True:
                                await update.message.reply_text(
                                    "🎉 *SUCCESS! Slot booked!* 🎉",
                                    parse_mode='Markdown'
                                )
                            elif booking_result.get('success') is False:
                                # Check if it's a "no slots" message
                                if booking_result.get('days'):
                                    days = booking_result.get('days')
                                    await update.message.reply_text(
                                        f"ℹ️ *Slot Availability*\n\n"
                                        f"No slots available for the next {days} days.",
                                        parse_mode='Markdown'
                                    )
                                else:
                                    await update.message.reply_text(
                                        f"⚠️ {booking_result.get('message', 'Booking failed')}"
                                    )
                            else:
                                await update.message.reply_text(
                                    f"ℹ️ {booking_result.get('message', 'Status unclear')}"
                                )
                        # Backward compatibility with bool return
                        elif booking_result:
                            await update.message.reply_text(
                                "🎉 *SUCCESS! Slot booked!* 🎉",
                                parse_mode='Markdown'
                            )
                        else:
                            await update.message.reply_text(
                                "⚠️ Booking failed or status unclear"
                            )
                else:
                    # Login failed - wrong captcha, retry
                    await update.message.reply_text(
                        "❌ Login failed - wrong captcha. Fetching new captcha and retrying..."
                    )
                    # Retry with new captcha
                    success, new_captcha, max_retries_reached = await attempt_login_with_retry(
                        update, context, user_id, automation, captcha_method,
                        attempt_num=None, is_monitoring=False
                    )
                    if success:
                        await process_login_and_booking(update, context, user_id, new_captcha)
                    elif max_retries_reached:
                        await update.message.reply_text(
                            f"❌ Max retries (5) reached. Please try /check again later."
                        )
                    else:
                        await update.message.reply_text(
                            "❌ Failed to login. Please try /check again later."
                        )
                    
            except Exception as e:
                logger.error(f"Error processing check: {e}")
                await update.message.reply_text(f"❌ Error: {str(e)}")
        # If in monitoring mode, the attempt_login_with_retry function handles retries
        # The captcha_code is already set, and attempt_login_with_retry will check it
        # No additional handling needed here for monitoring mode
    else:
        await update.message.reply_text(
            "ℹ️ I'm not waiting for a captcha. Use /check or /monitor to start."
        )


# Global variable to store schedule checker task
schedule_checker_task = None

async def schedule_checker():
    """Background task to check and apply scheduled pause/resume (optimized)"""
    global schedule_checker_task
    while True:
        try:
            check_scheduled_pause()
            # Check every minute
            await asyncio.sleep(60)
        except asyncio.CancelledError:
            logger.info("Schedule checker task cancelled (shutting down)")
            break
        except Exception as e:
            logger.error(f"Error in schedule checker: {e}")
            await asyncio.sleep(60)


def main():
    """Start the bot"""
    try:
        # Validate required environment variables at startup
        required_vars = {
            "BOT_TOKEN": BOT_TOKEN,
            "AUTHORIZED_USERS": AUTHORIZED_USERS_STR,
            "APPLICATION_NUMBER": DEFAULT_APPLICATION_NUMBER,
            "DOB": DEFAULT_DOB,
            "GEMINI_API_KEY": DEFAULT_GEMINI_API_KEY
        }
        
        missing_vars = [var for var, value in required_vars.items() if not value]
        if missing_vars:
            error_msg = f"❌ Missing required environment variables: {', '.join(missing_vars)}\n"
            error_msg += "Please set these in your .env file."
            print(error_msg)
            raise ValueError(error_msg)
        
        # Create application with proper timeout configuration
        from telegram.ext import ApplicationBuilder
        
        # Start health check server for UptimeRobot keep-alive
        # This creates an HTTP endpoint that UptimeRobot can ping
        try:
            from health_check import start_health_check
            start_health_check()
            # Render will auto-detect the port and configure routing
            print("🏥 Health check server started (for UptimeRobot keep-alive)")
        except Exception as e:
            print(f"⚠️ Health check server not started: {e}")
            print("ℹ️ Bot will still work, but may sleep without UptimeRobot pings")
        
        print("🤖 Bot is starting...")
        print("✅ All environment variables loaded successfully")
        
        # Check initial schedule state
        check_scheduled_pause()
        ist_now = datetime.now(IST)
        pause_status = "⏸️ Paused" if BOT_PAUSED else "▶️ Active"
        print(f"📅 Schedule: Auto-pause at {PAUSE_HOUR}:00 IST, Auto-resume at {RESUME_HOUR}:00 IST")
        print(f"🕐 Current time: {ist_now.strftime('%H:%M:%S IST')} - Bot status: {pause_status}")
        
        # Create application with simplified configuration
        application = (
            ApplicationBuilder()
            .token(BOT_TOKEN)
            .concurrent_updates(True)
            .build()
        )
        
        # Add handlers
        application.add_handler(CommandHandler("start", start))
        application.add_handler(CommandHandler("myid", get_my_id))  # No auth check needed - helps setup
        application.add_handler(CommandHandler("setup", setup))
        application.add_handler(CommandHandler("check", check_slots))
        application.add_handler(CommandHandler("monitor", start_monitoring))
        application.add_handler(CommandHandler("stop", stop_monitoring))
        application.add_handler(CommandHandler("pause", pause_bot))
        application.add_handler(CommandHandler("resume", resume_bot))
        application.add_handler(CommandHandler("interval", set_interval))
        application.add_handler(CommandHandler("captcha_method", set_captcha_method))
        application.add_handler(CommandHandler("set_gemini_key", set_gemini_key))
        application.add_handler(CommandHandler("status", status))
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
        
        # Start schedule checker after event loop is running
        global schedule_checker_task
        async def post_init(application):
            """Start background tasks after bot is initialized"""
            global schedule_checker_task
            schedule_checker_task = asyncio.create_task(schedule_checker())
            print("📅 Schedule checker started (checks every minute)")
        
        # Add error handler for Conflict errors (expected during restarts)
        async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
            """Handle errors, especially Conflict errors during restarts"""
            error = context.error
            if isinstance(error, Conflict):
                # Conflict errors are normal during bot restarts/deployments
                logger.warning("Conflict error (expected during restart): Another instance may be starting")
                return
            # Log other errors
            logger.error(f"Exception while handling an update: {error}", exc_info=error)
        
        application.add_error_handler(error_handler)
        application.post_init = post_init
        
        # Handle shutdown gracefully
        async def post_shutdown(application):
            """Clean up background tasks on shutdown"""
            global schedule_checker_task
            if schedule_checker_task and not schedule_checker_task.done():
                schedule_checker_task.cancel()
                try:
                    await schedule_checker_task
                except asyncio.CancelledError:
                    pass
            logger.info("Background tasks cleaned up")
        
        application.post_shutdown = post_shutdown
        
        # Start bot
        print("✅ Bot is running! Press Ctrl+C to stop.")
        application.run_polling(
            allowed_updates=Update.ALL_TYPES,
            drop_pending_updates=True
        )
    except KeyboardInterrupt:
        print("\n🛑 Bot stopped by user.")
    except Exception as e:
        print(f"❌ Error starting bot: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()


