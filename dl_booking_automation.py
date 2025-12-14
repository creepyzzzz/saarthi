"""
DL Test Slot Booking - Complete Automation Script
Based on captured APIs from HAR file and state selection API
"""

import requests
import time
import json
import os
from datetime import datetime
from urllib.parse import urlencode, quote

class DLBookingAutomation:
    def __init__(self, application_number, dob):
        """
        Initialize the booking automation
        
        Args:
            application_number: Your application number (e.g., "3209941425")
            dob: Date of birth in DD-MM-YYYY format (e.g., "04-03-1974")
        """
        self.application_number = application_number
        self.dob = dob
        self.base_url = "https://sarathi.parivahan.gov.in"
        self.session = requests.Session()
        
        # Set headers to mimic browser
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Sec-Fetch-User': '?1',
        })
    
    def select_state(self, state_code="JK"):
        """
        Step 1: Select the state (Jammu and Kashmir)
        
        Args:
            state_code: State code (default: "JK" for Jammu and Kashmir)
        
        Returns:
            bool: True if successful
        """
        print(f"[STEP 1] Selecting state: {state_code}")
        
        # Get state selection page
        url = f"{self.base_url}/sarathiservice/stateSelection.do"
        response = self.session.get(url)
        
        if response.status_code != 200:
            print(f"[ERROR] Failed to load state selection page: {response.status_code}")
            return False
        
        # Submit state selection
        url = f"{self.base_url}/sarathiservice/stateSelectBean.do"
        data = {'stName': state_code}
        
        response = self.session.post(url, data=data, allow_redirects=True)
        
        if response.status_code == 200:
            print(f"[SUCCESS] State selected: {state_code}")
            return True
        else:
            print(f"[ERROR] Failed to select state: {response.status_code}")
            return False
    
    def navigate_to_appointments(self):
        """
        Step 2: Navigate to appointments page
        
        Returns:
            bool: True if successful
        """
        print("[STEP 2] Navigating to appointments page...")
        
        url = f"{self.base_url}/sarathiservice/appointment.do"
        response = self.session.get(url)
        
        if response.status_code == 200:
            print("[SUCCESS] Appointments page loaded")
            return True
        else:
            print(f"[ERROR] Failed to load appointments page: {response.status_code}")
            return False
    
    def navigate_to_dl_slot_booking(self):
        """
        Step 3: Navigate to DL Test Slot Booking page
        
        Returns:
            bool: True if successful
        """
        print("[STEP 3] Navigating to DL Test Slot Booking...")
        
        # Expected endpoint based on flow
        url = f"{self.base_url}/slots/dlslotbook.do"
        response = self.session.get(url)
        
        if response.status_code == 200:
            print("[SUCCESS] DL Slot Booking page loaded")
            # Check if we need to extract captcha or other data
            return True
        else:
            print(f"[ERROR] Failed to load DL slot booking page: {response.status_code}")
            print(f"[INFO] Response: {response.text[:500]}")
            return False
    
    def get_captcha_image(self):
        """
        Fetch the captcha image from the server
        
        Returns:
            str: Path to saved captcha image file, or None if failed
        """
        print("[INFO] Fetching captcha image...")
        
        # Confirmed captcha image endpoint
        url = f"{self.base_url}/slots/jsp/common/captchaimage.jsp"
        
        # Set headers for image request
        headers = {
            'Referer': f'{self.base_url}/slots/dlslotbook.do',
            'Accept': 'image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8',
            'Cache-Control': 'no-cache',
            'Pragma': 'no-cache'
        }
        
        try:
            response = self.session.get(url, headers=headers)
            
            if response.status_code == 200 and response.headers.get('content-type', '').startswith('image/'):
                # Save captcha image
                captcha_file = "captcha_image.jpg"
                with open(captcha_file, 'wb') as f:
                    f.write(response.content)
                
                print(f"[SUCCESS] Captcha image saved to: {captcha_file}")
                
                # Try to open the image (platform-specific)
                try:
                    if os.name == 'nt':  # Windows
                        os.startfile(captcha_file)
                    elif os.name == 'posix':  # macOS/Linux
                        if os.system(f'which xdg-open > /dev/null 2>&1') == 0:
                            os.system(f'xdg-open {captcha_file}')
                        elif os.system(f'which open > /dev/null 2>&1') == 0:
                            os.system(f'open {captcha_file}')
                except Exception as e:
                    print(f"[INFO] Could not auto-open image: {e}")
                    print(f"[INFO] Please manually open: {captcha_file}")
                
                return captcha_file
            else:
                print(f"[ERROR] Failed to fetch captcha image: {response.status_code}")
                return None
                
        except Exception as e:
            print(f"[ERROR] Exception while fetching captcha: {e}")
            return None
    
    def login(self, captcha_code):
        """
        Step 4: Login with application number, DOB, and captcha (CONFIRMED API)
        
        Args:
            captcha_code: The captcha code from the login page
        
        Returns:
            bool: True if login successful, False if failed, None if unclear
        """
        print("[STEP 4] Attempting login...")
        print(f"[INFO] Application Number: {self.application_number}")
        print(f"[INFO] DOB: {self.dob}")
        print(f"[INFO] Captcha: {captcha_code}")
        
        # Refresh the booking page first to ensure fresh session
        try:
            refresh_url = f"{self.base_url}/slots/dlslotbook.do"
            self.session.get(refresh_url, timeout=10)
            time.sleep(1)  # Small delay to avoid rate limiting
        except Exception as e:
            print(f"[WARNING] Could not refresh page: {e}")
        
        # Confirmed endpoint from captured API
        url = f"{self.base_url}/slots/dldetsubmit.do"
        
        # Confirmed payload format from captured API
        data = {
            'subtype': '1',  # Login type (1 = Application Number)
            'applno': self.application_number,
            'llno': '',  # Empty for application number login
            'dob': self.dob,
            'uName': '',  # Empty
            'hexUsrid': '',  # Empty
            'captcha': captcha_code,
            '+++SAVE+++': '++SUBMIT++'  # Submit button (spaces encoded as +)
        }
        
        # Critical headers from captured request
        login_headers = {
            'Referer': f'{self.base_url}/slots/dlslotbook.do',  # CRITICAL!
            'Origin': self.base_url,
            'Content-Type': 'application/x-www-form-urlencoded',
            'Cache-Control': 'no-cache',
            'Pragma': 'no-cache',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        }
        
        # Retry logic for connection errors
        max_retries = 3
        for attempt in range(max_retries):
            try:
                if attempt > 0:
                    print(f"[INFO] Retry attempt {attempt + 1}/{max_retries}...")
                    time.sleep(2 * attempt)  # Exponential backoff
                
                response = self.session.post(
                    url, 
                    data=data, 
                    headers=login_headers,
                    allow_redirects=True,
                    timeout=30  # 30 second timeout
                )
                
                if response.status_code == 200:
                    response_text = response.text
                    
                    # Check for specific error messages (more precise)
                    response_lower = response_text.lower()
                    error_indicators = [
                        "invalid application number",
                        "invalid dob",
                        "invalid captcha",
                        "captcha code is incorrect",
                        "captcha mismatch",
                        "please enter correct captcha",
                        "error in login",
                        "login failed"
                    ]
                    
                    # Check if any error indicator is present
                    has_error = any(indicator in response_lower for indicator in error_indicators)
                    
                    # Check for success indicators
                    success_indicators = [
                        "dl test appointment",
                        "appointment details",
                        "slot booking",
                        self.application_number
                    ]
                    has_success = any(indicator.lower() in response_lower for indicator in success_indicators if indicator)
                    
                    if has_error:
                        print("[ERROR] Login failed - check credentials or captcha")
                        # Try to extract specific error message
                        for indicator in error_indicators:
                            if indicator in response_lower:
                                print(f"[ERROR] Specific error: {indicator}")
                                break
                        return False
                    elif has_success:
                        print("[SUCCESS] Login successful!")
                        return True
                    elif response.url != url:
                        # Redirected to different page - likely success
                        print("[SUCCESS] Login successful (redirected to different page)")
                        return True
                    else:
                        print("[WARNING] Login response unclear - checking URL...")
                        # Check if we're on a different page than the login page
                        if "dlslotbook.do" not in response.url and "dldetsubmit.do" not in response.url:
                            print("[SUCCESS] Login successful (redirected away from login page)")
                            return True
                        print("[WARNING] Still on login page or unclear status")
                        return None
                else:
                    print(f"[ERROR] Login request failed: {response.status_code}")
                    if attempt < max_retries - 1:
                        continue
                    return False
                    
            except requests.exceptions.Timeout:
                print(f"[ERROR] Request timeout (attempt {attempt + 1}/{max_retries})")
                if attempt < max_retries - 1:
                    continue
                return False
            except requests.exceptions.ConnectionError as e:
                print(f"[ERROR] Connection error (attempt {attempt + 1}/{max_retries}): {e}")
                if attempt < max_retries - 1:
                    continue
                return False
            except Exception as e:
                print(f"[ERROR] Exception during login: {e}")
                if attempt < max_retries - 1:
                    continue
                return False
        
        return False
    
    def check_slot_availability(self):
        """
        Step 5: Check if slots are available
        
        Returns:
            dict: Slot availability information
        """
        print("[STEP 5] Checking slot availability...")
        
        # The slot availability might be shown on the application details page
        # or might require a separate API call
        # This needs to be determined from the captured APIs
        
        url = f"{self.base_url}/slots/dldetsubmit.do"
        response = self.session.get(url)
        
        if response.status_code == 200:
            # Check response for slot availability message
            if "Slots are not Available" in response.text:
                # Extract number of days
                import re
                match = re.search(r'Slots are not Available for the next (\d+) Days', response.text)
                if match:
                    days = match.group(1)
                    print(f"[INFO] No slots available for the next {days} days")
                    return {'available': False, 'days': int(days)}
                return {'available': False}
            elif "available" in response.text.lower() and "slot" in response.text.lower():
                print("[SUCCESS] Slots appear to be available!")
                return {'available': True}
            else:
                print("[INFO] Slot availability unclear from response")
                return {'available': None}
        
        return {'available': None}
    
    def book_slot(self, iscov="2", covcd="2,", trkcd=""):
        """
        Step 6: Book the slot (CONFIRMED API)
        
        Args:
            iscov: Class of vehicle ID (default: "2" for MCWOG)
            covcd: Class of vehicle code (default: "2," - comma, NOT URL encoded)
            trkcd: Track code (default: empty)
        
        Returns:
            dict: {'success': bool, 'message': str, 'days': int or None}
        """
        print("[STEP 6] Attempting to book slot...")
        
        url = f"{self.base_url}/slots/proceeddlapmnt.do"
        
        # Confirmed payload format from captured API
        data = {
            'iscov': iscov,
            '__checkbox_iscov': iscov,
            'covcd': covcd,  # Note: "2," with comma (NOT "2%2C"), URL encoding happens automatically
            'trkcd': trkcd,
            'method:proceedBookslot': '  PROCEED TO BOOK  '  # 2 spaces before and after
        }
        
        # Critical headers from captured request
        self.session.headers.update({
            'Referer': f'{self.base_url}/slots/dldetsubmit.do',  # CRITICAL!
            'Origin': self.base_url,
            'Content-Type': 'application/x-www-form-urlencoded',
            'Cache-Control': 'no-cache',
            'Pragma': 'no-cache'
        })
        
        try:
            response = self.session.post(url, data=data, allow_redirects=True)
            
            if response.status_code == 200:
                # Check response for success/failure (based on captured response)
                response_text = response.text
                
                if "Slots are not Available" in response_text:
                    # Extract number of days if available
                    import re
                    match = re.search(r'Slots are not Available for the next (\d+) Days', response_text)
                    if match:
                        days = int(match.group(1))
                        print(f"[INFO] No slots available for the next {days} days")
                        return {'success': False, 'message': f'No slots available for the next {days} days', 'days': days}
                    else:
                        print("[INFO] No slots available")
                        return {'success': False, 'message': 'No slots available', 'days': None}
                elif "success" in response_text.lower() or "booked" in response_text.lower() or "appointment" in response_text.lower():
                    print("[SUCCESS] Slot booked successfully!")
                    return {'success': True, 'message': 'Slot booked successfully!', 'days': None}
                elif "error" in response_text.lower() or "invalid" in response_text.lower():
                    print("[ERROR] Booking failed - check response")
                    return {'success': False, 'message': 'Booking failed - error in response', 'days': None}
                else:
                    # Response received but status unclear
                    print("[INFO] Booking response received, checking status...")
                    # The response is the booking page - check if it shows success or error
                    if "DL TEST APPOINTMENT" in response_text and "Slots are not Available" not in response_text:
                        print("[SUCCESS] Booking page loaded - slot may be available!")
                        return {'success': True, 'message': 'Booking page loaded - slot may be available', 'days': None}
                    return {'success': None, 'message': 'Booking status unclear', 'days': None}
            else:
                print(f"[ERROR] Booking request failed: {response.status_code}")
                return {'success': False, 'message': f'Booking request failed: {response.status_code}', 'days': None}
                
        except Exception as e:
            print(f"[ERROR] Exception during booking: {e}")
            return {'success': False, 'message': f'Exception during booking: {str(e)}', 'days': None}
    
    def complete_booking_flow(self, captcha_code=None, iscov="2", covcd="2,"):
        """
        Execute the complete booking flow
        
        Args:
            captcha_code: Captcha code from login page (None to fetch and display image)
            iscov: Class of vehicle ID
            covcd: Class of vehicle code
        
        Returns:
            bool: True if booking successful
        """
        print("=" * 70)
        print("DL TEST SLOT BOOKING - AUTOMATED FLOW")
        print("=" * 70)
        print(f"Application Number: {self.application_number}")
        print(f"DOB: {self.dob}")
        print("=" * 70 + "\n")
        
        # Step 1: Select state
        if not self.select_state("JK"):
            return False
        
        time.sleep(1)
        
        # Step 2: Navigate to appointments
        if not self.navigate_to_appointments():
            return False
        
        time.sleep(1)
        
        # Step 3: Navigate to DL slot booking
        if not self.navigate_to_dl_slot_booking():
            return False
        
        time.sleep(1)
        
        # Step 3.5: Get captcha image if not provided
        if captcha_code is None:
            captcha_file = self.get_captcha_image()
            if captcha_file:
                captcha_code = input("\nEnter the captcha code you see in the image: ").strip()
            else:
                captcha_code = input("\nEnter captcha code: ").strip()
        
        # Step 4: Login
        login_result = self.login(captcha_code)
        if login_result is False:
            return False
        elif login_result is None:
            print("[WARNING] Login status unclear, continuing...")
        
        time.sleep(1)
        
        # Step 5: Check slot availability
        availability = self.check_slot_availability()
        if availability.get('available') is False:
            print(f"[INFO] No slots available. Waiting...")
            return False
        
        time.sleep(1)
        
        # Step 6: Book slot
        booking_result = self.book_slot(iscov, covcd)
        return booking_result is True
    
    def monitor_and_book(self, captcha_solver=None, check_interval=300):
        """
        Continuously monitor for slot availability and book when available
        
        Args:
            captcha_solver: Function to solve captcha (returns captcha code)
            check_interval: Time in seconds between checks (default: 5 minutes)
        """
        print("=" * 70)
        print("DL SLOT MONITORING & AUTO-BOOKING")
        print("=" * 70)
        print(f"Application Number: {self.application_number}")
        print(f"DOB: {self.dob}")
        print(f"Check Interval: {check_interval} seconds")
        print("=" * 70)
        print("\n[INFO] Starting monitoring...")
        print("[WARNING] Captcha solving needs to be implemented!")
        print("\nPress Ctrl+C to stop\n")
        
        attempts = 0
        
        try:
            # Initial navigation
            if not self.select_state("JK"):
                print("[ERROR] Failed to select state")
                return
            time.sleep(1)
            
            if not self.navigate_to_appointments():
                print("[ERROR] Failed to navigate to appointments")
                return
            time.sleep(1)
            
            while True:
                attempts += 1
                print(f"\n[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Attempt #{attempts}")
                
                # Navigate to DL slot booking page (needed for captcha)
                if not self.navigate_to_dl_slot_booking():
                    print("[ERROR] Failed to navigate to DL slot booking page")
                    time.sleep(check_interval)
                    continue
                time.sleep(1)
                
                # Get captcha image first
                captcha_file = self.get_captcha_image()
                
                # Get captcha (if solver provided)
                if captcha_solver:
                    captcha = captcha_solver()
                else:
                    if captcha_file:
                        captcha = input("\nEnter the captcha code you see in the image (or 'q' to quit): ").strip()
                    else:
                        captcha = input("Enter captcha code (or 'q' to quit): ").strip()
                    if captcha.lower() == 'q':
                        break
                    
                    # Clean up captcha image file
                    if captcha_file and os.path.exists(captcha_file):
                        try:
                            os.remove(captcha_file)
                        except:
                            pass
                
                # Try to book
                success = self.complete_booking_flow(captcha)
                
                if success:
                    print("\n[SUCCESS] Booking completed! Exiting...")
                    break
                else:
                    print(f"[INFO] Waiting {check_interval} seconds before next attempt...")
                    time.sleep(check_interval)
                    
        except KeyboardInterrupt:
            print("\n\n[INFO] Monitoring stopped by user")
        except Exception as e:
            print(f"\n[ERROR] Monitoring error: {e}")


def main():
    """
    Main function - Configure your details here
    """
    # Configuration
    APPLICATION_NUMBER = "3209941425"
    DOB = "04-03-1974"
    
    # Create automation instance
    automation = DLBookingAutomation(APPLICATION_NUMBER, DOB)
    
    print("\n" + "=" * 70)
    print("DL TEST SLOT BOOKING AUTOMATION")
    print("=" * 70)
    print("\nOptions:")
    print("1. Complete booking flow (requires captcha)")
    print("2. Monitor and auto-book (requires captcha solver)")
    print("3. Test individual steps")
    print("=" * 70)
    
    choice = input("\nEnter choice (1/2/3): ").strip()
    
    if choice == "1":
        captcha = input("Enter captcha code: ")
        automation.complete_booking_flow(captcha)
    elif choice == "2":
        print("\n[INFO] Monitoring mode - you'll need to enter captcha for each attempt")
        automation.monitor_and_book(check_interval=300)
    elif choice == "3":
        print("\n[INFO] Testing individual steps...")
        automation.select_state("JK")
        automation.navigate_to_appointments()
        automation.navigate_to_dl_slot_booking()
    else:
        print("[ERROR] Invalid choice")


if __name__ == "__main__":
    main()


