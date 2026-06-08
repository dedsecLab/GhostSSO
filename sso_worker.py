import time
import argparse
import sys
import os
from cloakbrowser import launch

BURP_PROXY = "http://127.0.0.1:8080"
WORKER_DIR = os.path.dirname(os.path.abspath(__file__))
STATE_FILE = os.path.join(WORKER_DIR, "sso_state.json")

class BaseProvider:
    def login(self, page, username, password):
        raise NotImplementedError("Subclasses must implement login()")

class OktaProvider(BaseProvider):
    def login(self, page, username, password):
        print(f"[{time.strftime('%X')}] [Okta] Entering credentials...")
        page.wait_for_selector('input[name="identifier"]', timeout=15000)
        page.fill('input[name="identifier"]', username)
        
        next_button = page.locator('input[value="Next"]')
        if next_button.is_visible():
            next_button.click()
            
        page.wait_for_selector('input[name="credentials.passcode"]', timeout=15000)
        page.fill('input[name="credentials.passcode"]', password)
        page.locator('input[type="submit"], input[value="Verify"]').click()

class GoogleProvider(BaseProvider):
    def login(self, page, username, password):
        print(f"[{time.strftime('%X')}] [Google] Entering credentials...")
        page.wait_for_selector('input[type="email"]', timeout=15000)
        page.fill('input[type="email"]', username)
        page.click('#identifierNext')
        
        page.wait_for_selector('input[type="password"]', timeout=15000)
        page.fill('input[type="password"]', password)
        page.click('#passwordNext')

class MicrosoftProvider(BaseProvider):
    def login(self, page, username, password):
        print(f"[{time.strftime('%X')}] [Microsoft] Entering credentials...")
        page.wait_for_selector('input[type="email"]', timeout=15000)
        page.fill('input[type="email"]', username)
        page.click('input[type="submit"]')
        
        page.wait_for_selector('input[type="password"]', timeout=15000)
        page.fill('input[type="password"]', password)
        page.click('input[type="submit"]')
        
        # Handle "Stay signed in?" prompt if it appears
        try:
            page.wait_for_selector('#idSIButton9', timeout=5000)
            page.click('#idSIButton9')
        except:
            pass

class GithubProvider(BaseProvider):
    def login(self, page, username, password):
        print(f"[{time.strftime('%X')}] [GitHub] Entering credentials...")
        page.wait_for_selector('#login_field', timeout=15000)
        page.fill('#login_field', username)
        
        page.wait_for_selector('#password', timeout=15000)
        page.fill('#password', password)
        page.click('input[name="commit"]')

PROVIDERS = {
    "okta": OktaProvider(),
    "google": GoogleProvider(),
    "microsoft": MicrosoftProvider(),
    "github": GithubProvider()
}

def perform_login(args):
    print(f"[{time.strftime('%X')}] Starting SSO login flow for {args.provider}...")
    
    if args.clear_state:
        # Delete sso_state.json before every login attempt to force a fresh session
        if os.path.exists(STATE_FILE):
            try:
                os.remove(STATE_FILE)
                print(f"[{time.strftime('%X')}] Deleted sso_state.json to force a fresh login.")
            except Exception as e:
                print(f"[{time.strftime('%X')}] Failed to delete sso_state.json: {e}")
        else:
            print(f"[{time.strftime('%X')}] Force fresh login enabled, but no sso_state.json was found.")
        
    # If MFA is required, we launch visibly (headless=False)
    browser = launch(
        headless=not args.mfa, 
        proxy=BURP_PROXY
    )
    
    # Load previous session state if it exists to avoid repeated MFA
    # Skip loading when --clear-state is set to ensure a truly fresh login
    context_args = {"ignore_https_errors": True}
    if not args.clear_state and os.path.exists(STATE_FILE):
        context_args["storage_state"] = STATE_FILE
        print(f"[{time.strftime('%X')}] Loaded previous browser state (cookies).")

    context = browser.new_context(**context_args)
    page = context.new_page()

    try:
        print(f"[{time.strftime('%X')}] Navigating to target URL: {args.url}")
        page.goto(args.url)

        provider = PROVIDERS.get(args.provider.lower())
        if not provider:
            print(f"[ERROR] Provider {args.provider} not supported.")
            return

        # Attempt to login. If fields aren't found, it might be because we are already 
        # authenticated via the loaded storage_state.
        try:
            provider.login(page, args.user, args.password)
        except Exception as login_err:
            print(f"[{time.strftime('%X')}] Note: Login fields not found. We might already be authenticated via saved state.")

        if args.mfa:
            print(f"[{time.strftime('%X')}] [MFA] Waiting for you to complete MFA in the browser window...")

        print(f"[{time.strftime('%X')}] Waiting for provider to redirect back to target app...")
        domain = args.url.split('://')[-1].split('/')[0]
        
        # We give a long timeout (90 seconds) in case the user needs to manually approve MFA on their phone
        page.wait_for_url(f"**{domain}**", timeout=90000)
        
        print(f"[{time.strftime('%X')}] Redirected to target app. Waiting for page to settle...")
        page.wait_for_load_state('networkidle')
        page.wait_for_timeout(10000)
        
        # Save state so we don't have to do MFA next time
        context.storage_state(path=STATE_FILE)
        print(f"[{time.strftime('%X')}] Session saved to {STATE_FILE}. (This file will be recreated now to save the newly established session).")

        print(f"[{time.strftime('%X')}] [SUCCESS] Login successful! Burp Cookie Jar has been updated.")

    except Exception as e:
        print(f"[{time.strftime('%X')}] [ERROR] Error during login flow: {e}")
    finally:
        browser.close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="SSO Session Refresher for Burp Suite")
    parser.add_argument("--url", required=True, help="Target application URL")
    parser.add_argument("--user", required=True, help="SSO Username")
    parser.add_argument("--password", required=True, help="SSO Password")
    parser.add_argument("--provider", required=True, choices=["okta", "google", "microsoft", "github"], help="SSO Provider")
    parser.add_argument("--interval", type=int, default=4, help="Refresh interval in minutes")
    parser.add_argument("--mfa", action="store_true", help="Launch visibly to manually handle MFA")
    parser.add_argument("--clear-state", action="store_true", help="Clear previous session state before starting")
    
    args = parser.parse_args()

    print(f"--- SSO Session Refresher Worker Started ---")
    print(f"Target: {args.url}")
    print(f"Provider: {args.provider.capitalize()}")
    print(f"Routing traffic through: {BURP_PROXY}")
    if args.mfa:
        print(f"MFA Mode Enabled: Browser will be visible.")
    
    while True:
        perform_login(args)
        print(f"[{time.strftime('%X')}] Sleeping for {args.interval} minutes before next refresh...")
        time.sleep(args.interval * 60)
