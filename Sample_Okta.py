import time
from cloakbrowser import launch

# --- Configuration ---
TARGET_URL = "" # Replace with your app's actual login URL
OKTA_USERNAME = ""
OKTA_PASSWORD = ""
BURP_PROXY = "http://127.0.0.1:8080"  # Default Burp Proxy address
REFRESH_INTERVAL_MINUTES = 4          # Time between refreshes (should be less than your session timeout)

def perform_login():
    print(f"[{time.strftime('%X')}] Starting Okta login flow...")
    # Launch CloakBrowser. We set the proxy to point to Burp Suite.
    # Set headless=False if you want to visually see the browser typing in your credentials.
    browser = launch(
        headless=False, 
        proxy=BURP_PROXY
    )
    
    # We must ignore HTTPS errors because Burp uses a custom CA certificate 
    # that the Playwright browser won't trust by default.
    context = browser.new_context(ignore_https_errors=True)
    page = context.new_page()

    try:
        # 1. Navigate to the application. It will automatically redirect to Okta.
        print(f"[{time.strftime('%X')}] Navigating to target URL...")
        page.goto(TARGET_URL)

        # 2. Handle Okta Login
        # Wait for the username field (this selector works for most Okta tenants)
        print(f"[{time.strftime('%X')}] Entering credentials...")
        page.wait_for_selector('input[name="identifier"]', timeout=15000)
        page.fill('input[name="identifier"]', OKTA_USERNAME)
        
        # Some Okta tenants use a split page (enter username -> click next -> enter password)
        next_button = page.locator('input[value="Next"]')
        if next_button.is_visible():
            next_button.click()
            
        # Wait for the password field and enter password
        page.wait_for_selector('input[name="credentials.passcode"]', timeout=15000)
        page.fill('input[name="credentials.passcode"]', OKTA_PASSWORD)
        
        # Click the submit/verify button
        page.locator('input[type="submit"], input[value="Verify"]').click()

        # 3. Wait for successful login
        # Wait until Okta redirects us back to the main target website domain
        print(f"[{time.strftime('%X')}] Waiting for Okta to redirect back to target app...")
        domain = TARGET_URL.split('://')[-1].split('/')[0]
        page.wait_for_url(f"**{domain}**", timeout=45000)
        
        print(f"[{time.strftime('%X')}] Redirected to target app. Waiting for page to settle...")
        page.wait_for_load_state('networkidle')
        
        # Explicitly wait a few seconds to ensure all background scripts and cookies are fully processed
        print(f"[{time.strftime('%X')}] Waiting 5 seconds on the main page to ensure cookies are captured...")
        page.wait_for_timeout(5000)
        
        # Note: Because the browser traffic goes through the proxy (127.0.0.1:8080), 
        # Burp Suite will automatically intercept the final responses and update its Cookie Jar.
        print(f"[{time.strftime('%X')}] Login successful! Burp Cookie Jar has been updated.")

    except Exception as e:
        print(f"[{time.strftime('%X')}] Error during login flow: {e}")
    finally:
        browser.close()

if __name__ == "__main__":
    print(f"--- Okta Session Refresher Started ---")
    print(f"Ensure Burp Suite is running at {BURP_PROXY}")
    print("Ensure 'Proxy' is checked in Burp: Settings -> Sessions -> Cookie jar")
    
    while True:
        perform_login()
        print(f"[{time.strftime('%X')}] Sleeping for {REFRESH_INTERVAL_MINUTES} minutes before next refresh...")
        time.sleep(REFRESH_INTERVAL_MINUTES * 60)
