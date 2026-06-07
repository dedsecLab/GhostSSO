# GhostSSO
**By dedsecLab**

**GhostSSO** is a native Burp Suite extension designed to automatically handle complex Single Sign-On (SSO) logins, Multi-Factor Authentication (MFA), and keep your session tokens alive during active penetration testing.

If you've ever had a scan fail because an Okta or Azure AD session timed out, GhostSSO solves that problem by silently driving a stealth headless browser in the background to re-authenticate and feed fresh cookies directly into the Burp Suite Cookie Jar.

## Features
- **Universal Provider Support:** Works with Okta, Google, Microsoft (Azure AD), and GitHub.
- **MFA Support:** Supports manual MFA handling. If your target requires a hardware key or Authenticator app, GhostSSO can launch a visible browser window, wait for you to tap your key, and then save the session state so you don't have to do it again!
- **Stealth Browser:** Powered by [CloakBrowser](https://github.com/CloakHQ/CloakBrowser) to evade basic bot detection that blocks standard Playwright/Puppeteer scripts.
- **Burp Native UI:** Clean Java Swing interface directly inside Burp Suite to configure your targets and monitor live logs.

## Architecture
Because Burp Suite's native Python support (Jython) is stuck on Python 2.7, GhostSSO uses a **Controller-Worker** architecture:
1. **The Controller (`GhostSSO.py`):** Loaded into Burp Suite via Jython. Provides the GUI and spawns the background process.
2. **The Worker (`sso_worker.py`):** Runs on your local system's Python 3 installation, driving the CloakBrowser automation.

## Prerequisites
1. **Python 3** installed on your host machine.
2. **CloakBrowser** installed: `pip install cloakbrowser`
3. **Jython Standalone JAR** loaded into Burp Suite (`Extensions` -> `Extension Settings` -> `Python Environment`).

## Installation
1. Clone this repository to your local machine.
2. Open Burp Suite.
3. Go to **Extensions** -> **Installed** -> **Add**.
4. Set Extension Type to **Python**.
5. Select `GhostSSO.py` from the cloned repository.

## Usage
1. Go to the new **SSO Manager** tab in Burp Suite.
2. Enter the absolute path to `sso_worker.py` on your machine.
3. Enter your Target URL, Username, and Password.
4. Select your SSO Provider.
5. If the application requires MFA, check the **Manual MFA Required** box.
6. Click **Start Refreshing**.

GhostSSO will launch the worker, perform the login, and pipe the fresh cookies directly into Burp Suite's Cookie Jar.

## Security Warning
This tool requires entering plaintext credentials into the Burp UI, which are passed to the worker script. Do not use this tool on shared machines where other users can read process arguments.

## Contributing
Pull requests to add new SSO Providers to `sso_worker.py` are highly encouraged!
