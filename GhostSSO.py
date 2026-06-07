import sys
import subprocess
import threading
import os

from burp import IBurpExtender
from burp import ITab
from javax.swing import JPanel, JButton, JTextField, JPasswordField, JLabel, JComboBox, JTextArea, JScrollPane, JCheckBox, SwingUtilities, BorderFactory
from java.awt import BorderLayout, FlowLayout, GridBagLayout, GridBagConstraints, Insets, Font

class BurpExtender(IBurpExtender, ITab):
    def registerExtenderCallbacks(self, callbacks):
        self._callbacks = callbacks
        self._helpers = callbacks.getHelpers()
        
        callbacks.setExtensionName("GhostSSO")
        
        # Print info to the Burp Extender Output tab when loaded
        callbacks.printOutput("===================================\n")
        callbacks.printOutput("GhostSSO - Automated SSO Session Manager\n")
        callbacks.printOutput("Authors: dedsecLab\n")
        callbacks.printOutput("===================================\n")
        
        self.worker_process = None
        
        try:
            ext_file = callbacks.getExtensionFilename()
            ext_dir = os.path.dirname(ext_file)
            self.default_worker_path = os.path.join(ext_dir, "sso_worker.py")
        except Exception as e:
            callbacks.printOutput("Warning: Could not resolve extension path - " + str(e) + "\n")
            self.default_worker_path = "sso_worker.py"
            
        self.init_gui()
        
        callbacks.addSuiteTab(self)

    def getTabCaption(self):
        return "GhostSSO"

    def getUiComponent(self):
        return self.panel

    def init_gui(self):
        self.panel = JPanel(BorderLayout(10, 10))
        self.panel.setBorder(BorderFactory.createEmptyBorder(10, 10, 10, 10))
        
        # --- Top Form Panel ---
        # We wrap the form in a FlowLayout aligned to the Left so it doesn't stretch across the whole Burp screen
        form_wrapper = JPanel(FlowLayout(FlowLayout.LEFT, 0, 0))
        
        form_panel = JPanel(GridBagLayout())
        form_panel.setBorder(BorderFactory.createTitledBorder("GhostSSO Configuration - by dedsecLab & Antigravity"))
        gbc = GridBagConstraints()
        gbc.insets = Insets(5, 5, 5, 5)
        gbc.anchor = GridBagConstraints.WEST
        gbc.fill = GridBagConstraints.HORIZONTAL

        def add_row(row, label_text, component):
            gbc.gridy = row
            gbc.gridx = 0
            gbc.weightx = 0.0
            form_panel.add(JLabel(label_text), gbc)
            
            gbc.gridx = 1
            gbc.weightx = 1.0
            form_panel.add(component, gbc)

        self.txt_script = JTextField(self.default_worker_path, 40)
        add_row(0, "Python Worker Script Path:", self.txt_script)

        self.txt_url = JTextField("", 40)
        add_row(1, "Target URL (e.g. https://app.com/login):", self.txt_url)
        
        self.txt_user = JTextField("", 40)
        add_row(2, "SSO Username:", self.txt_user)
        
        self.txt_pass = JPasswordField("", 40)
        add_row(3, "SSO Password:", self.txt_pass)
        
        self.combo_provider = JComboBox(["okta", "google", "microsoft", "github"])
        add_row(4, "Provider:", self.combo_provider)
        
        self.txt_interval = JTextField("4", 40)
        add_row(5, "Refresh Interval (minutes):", self.txt_interval)
        
        self.chk_mfa = JCheckBox()
        add_row(6, "Manual MFA Required? (Opens visible browser):", self.chk_mfa)
        
        self.chk_clear_state = JCheckBox()
        add_row(7, "Force Fresh Login (Clear previous session):", self.chk_clear_state)
        
        # --- Buttons ---
        btn_panel = JPanel(FlowLayout(FlowLayout.LEFT, 0, 0))
        self.btn_start = JButton("Start Refreshing", actionPerformed=self.start_worker)
        self.btn_stop = JButton("Stop", actionPerformed=self.stop_worker)
        self.btn_stop.setEnabled(False)
        btn_panel.add(self.btn_start)
        btn_panel.add(JLabel("   ")) # Spacer
        btn_panel.add(self.btn_stop)
        
        add_row(8, "", btn_panel)
        
        form_wrapper.add(form_panel)
        self.panel.add(form_wrapper, BorderLayout.NORTH)
        
        # --- Console Output ---
        self.console = JTextArea()
        self.console.setEditable(False)
        self.console.setFont(Font("Monospaced", Font.PLAIN, 12))
        
        scroll = JScrollPane(self.console)
        scroll.setBorder(BorderFactory.createTitledBorder("Worker Output Console"))
        
        self.panel.add(scroll, BorderLayout.CENTER)

    def log(self, message):
        def update_text():
            self.console.append(message + "\n")
            self.console.setCaretPosition(self.console.getDocument().getLength())
        SwingUtilities.invokeLater(update_text)

    def start_worker(self, event):
        script_path = self.txt_script.getText()
        url = self.txt_url.getText()
        user = self.txt_user.getText()
        password = "".join(self.txt_pass.getPassword()) # Extract from JPasswordField
        provider = self.combo_provider.getSelectedItem()
        interval = self.txt_interval.getText()
        mfa = self.chk_mfa.isSelected()
        clear_state = self.chk_clear_state.isSelected()

        if not url or not user or not password:
            self.log("[UI] Error: Please fill in URL, Username, and Password.")
            return

        cmd = ["python", script_path, 
               "--url", url, 
               "--user", user, 
               "--password", password, 
               "--provider", provider, 
               "--interval", interval]
        
        if mfa:
            cmd.append("--mfa")
            
        if clear_state:
            cmd.append("--clear-state")
            worker_dir = os.path.dirname(os.path.abspath(script_path))
            state_file = os.path.join(worker_dir, "sso_state.json")
            if os.path.exists(state_file):
                try:
                    os.remove(state_file)
                    self.log("[UI] Proactively deleted sso_state.json to force a fresh login.")
                except Exception as e:
                    self.log("[UI] Warning: Failed to delete sso_state.json: " + str(e))

        self.log("[UI] Starting background worker...")
        
        # Hide password in the logged command
        safe_cmd = list(cmd)
        if "--password" in safe_cmd:
            idx = safe_cmd.index("--password") + 1
            safe_cmd[idx] = "********"
        self.log("[UI] Command: " + " ".join(safe_cmd))
        
        try:
            self.worker_process = subprocess.Popen(
                cmd, 
                stdout=subprocess.PIPE, 
                stderr=subprocess.STDOUT, 
                bufsize=1, 
                universal_newlines=True
            )
            
            self.btn_start.setEnabled(False)
            self.btn_stop.setEnabled(True)
            
            # Start background thread to read output
            threading.Thread(target=self.read_output).start()
            
        except Exception as e:
            self.log("[UI] Error starting worker: " + str(e))

    def stop_worker(self, event):
        if self.worker_process:
            self.log("[UI] Stopping worker...")
            try:
                self.worker_process.terminate()
            except Exception as e:
                self.log("[UI] Error terminating process: " + str(e))
            self.worker_process = None
            
        self.btn_start.setEnabled(True)
        self.btn_stop.setEnabled(False)
        self.log("[UI] Worker stopped.")

    def read_output(self):
        if not self.worker_process:
            return
            
        try:
            # Read stdout line by line
            for line in iter(self.worker_process.stdout.readline, ''):
                if line:
                    self.log(line.rstrip())
                
                if self.worker_process is None or self.worker_process.poll() is not None:
                    break
        except Exception as e:
            self.log("[UI] Stream reading error: " + str(e))
            
        if self.worker_process and self.worker_process.poll() is not None:
            self.log("[UI] Worker process exited with code: " + str(self.worker_process.returncode))
            
        def reset_buttons():
            self.btn_start.setEnabled(True)
            self.btn_stop.setEnabled(False)
            
        SwingUtilities.invokeLater(reset_buttons)
