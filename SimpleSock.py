# Wichtige Bibliotheken importieren
import pystray
from PIL import Image
import os
import subprocess
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import json
import sys
import winreg
import time
import webbrowser
import locale

# --- Anwendungs- und Versionsinformationen ---
APP_NAME = 'SimpleSock'
APP_VERSION = '0.1 (beta)'
APP_AUTHOR = 'Dominik Scharrer'
APP_GITHUB = 'https://github.com/hellodosi/SimpleSock'
# --- Ende der Infos ---

# Standardpfad zur Wiresock-Binärdatei
DEFAULT_WIRESOCK_PATH = 'C:\\Program Files\\WireSock Secure Connect\\bin\\wiresock-client.exe'

# Dateinamen für die Konfigurationsverwaltung und den Autostart-Key definieren
SETTINGS_FILE = 'app_settings.json'
AUTOSTART_REGISTRY_KEY = 'SimpleSockTrayUI'
LANG_DIR = 'lang'
DEFAULT_LANG = 'en'
TRANSLATIONS = {}

def get_system_language():
    """Versucht, die Systemsprache zu ermitteln."""
    try:
        # Gibt den Sprachcode des Systems zurück (z.B. 'de_DE' oder 'en_US')
        return locale.getlocale()[0][:2]
    except Exception:
        return DEFAULT_LANG

def load_translations(lang_code):
    """Lädt die Übersetzungen aus der JSON-Datei für die angegebene Sprache."""
    global TRANSLATIONS
    lang_path = os.path.join(os.path.dirname(os.path.abspath(sys.argv[0])), LANG_DIR, f"{lang_code}.json")
    if os.path.exists(lang_path):
        with open(lang_path, 'r', encoding='utf-8') as f:
            try:
                TRANSLATIONS = json.load(f)
            except json.JSONDecodeError as e:
                print(f"Fehler beim Laden der Übersetzungsdatei '{lang_path}': {e}")
                TRANSLATIONS = {}
    else:
        # Fallback auf Standard-Englisch, wenn die Zielsprache nicht gefunden wird
        print(f"Warnung: Übersetzungsdatei für '{lang_code}' nicht gefunden. Verwende Fallback-Sprache.")
        TRANSLATIONS = {}

def get_text(key, **kwargs):
    """Gibt den übersetzten Text zurück und ersetzt Platzhalter."""
    text = TRANSLATIONS.get(key, key)
    return text.format(**kwargs)

def check_wiresock_installation(path_to_check):
    """Prüft, ob Wiresock installiert ist und bietet die Installation über Winget an."""
    if os.path.exists(path_to_check):
        return True
    
    response = messagebox.askyesno(
        get_text("msg_box_title_error"),
        get_text("msg_box_wiresock_not_found", path=path_to_check)
    )
    
    if response:
        try:
            # Starte die Installation über winget in einem separaten Fenster
            subprocess.run(['start', 'winget', 'install', 'NTKERNEL.WireSockVPNClient'], shell=True, check=True)
            
            time.sleep(2)
            if os.path.exists(DEFAULT_WIRESOCK_PATH):
                messagebox.showinfo(get_text("msg_box_title_success"), get_text("msg_box_install_success"))
                return True
            else:
                messagebox.showerror(get_text("msg_box_title_error"), get_text("msg_box_install_failed"))
                return False
        except Exception as e:
            messagebox.showerror(get_text("msg_box_title_error"), get_text("msg_box_install_error", error=e))
            return False
    else:
        return False

class WiresockApp:
    def __init__(self, root):
        self.root = root
        # Initialisierung der Anwendungs- und UI-Zustände
        self.is_connected = False
        self.active_connection_name = None
        self.wiresock_process = None
        self.settings = {}
        self.settings_window = None
        self.status_window = None
        self.lang_var = None

        # Sicherstellen, dass die Verzeichnisse existieren
        self.app_dir = os.path.dirname(os.path.abspath(sys.argv[0]))
        self.configs_dir = os.path.join(self.app_dir, 'configs')
        self.lang_dir = os.path.join(self.app_dir, LANG_DIR)
        os.makedirs(self.configs_dir, exist_ok=True)
        os.makedirs(self.lang_dir, exist_ok=True)

        # Sicherstellen, dass die Standard-Sprachdatei existiert und gefüllt ist
        default_lang_path = os.path.join(self.lang_dir, f"{DEFAULT_LANG}.json")
        if not os.path.exists(default_lang_path) or os.path.getsize(default_lang_path) == 0:
            initial_translations = {
                "app_name": "SimpleSock",
                "tray_menu_connect": "Connect ({name})",
                "tray_menu_disconnect": "Disconnect ({name})",
                "tray_menu_no_connections": "No connections available",
                "tray_menu_settings": "Settings",
                "tray_menu_help_info": "Help & Info",
                "tray_menu_exit": "Exit",
                "win_title_settings": "Wiresock Settings",
                "win_title_info": "About SimpleSock",
                "info_text_version": "Version {version}",
                "info_text_author": "Author: {author}",
                "info_text_github": "GitHub: {github}",
                "settings_path_frame": "Path to Wiresock Installation",
                "settings_path_button": "Save",
                "settings_import_frame": "Import Configuration File",
                "settings_import_name_label": "Name for connection:",
                "settings_import_button": "Import",
                "settings_connections_frame": "Manage Connections",
                "settings_connections_delete": "Delete",
                "settings_connections_rename": "Rename",
                "settings_connections_edit": "Edit",
                "settings_startup_frame": "Startup Settings",
                "settings_autostart_checkbox": "Start automatically with Windows",
                "settings_default_connection_label": "Default connection on startup:",
                "settings_default_connection_none": "None",
                "msg_box_title_success": "Success",
                "msg_box_title_warning": "Warning",
                "msg_box_title_error": "Error",
                "msg_box_title_confirm": "Confirm",
                "msg_box_title_autostart": "Autostart",
                "msg_box_wiresock_not_found": "Wiresock was not found at '{path}'. Do you want to install it now via Winget?",
                "msg_box_autostart_enabled": "The application will now start automatically with Windows.",
                "msg_box_autostart_disabled": "Automatic startup has been disabled.",
                "msg_box_path_saved": "The path has been successfully updated. The application will now use this path.",
                "msg_box_path_invalid": "Invalid path. Please check if the file exists.",
                "msg_box_name_required": "Please enter a name for the connection.",
                "msg_box_name_exists": "The name '{name}' already exists. Please choose another one.",
                "msg_box_import_success": "'{name}' was imported successfully.",
                "msg_box_delete_confirm": "Are you sure you want to delete '{name}'?",
                "msg_box_delete_success": "'{name}' was deleted successfully.",
                "msg_box_rename_success": "'{old_name}' was renamed to '{new_name}'.",
                "msg_box_rename_title": "Rename",
                "msg_box_connect_active": "A connection is already active: {name}",
                "msg_box_config_not_found": "The configuration '{name}' was not found.",
                "msg_box_file_not_found": "The configuration file '{path}' was not found.",
                "msg_box_wiresock_not_found_connect": "The file '{path}' was not found. Please install Wiresock or correct the path in the settings.",
                "msg_box_connection_success": "Connection with '{name}' was successfully established.",
                "msg_box_disconnect_success": "The connection was successfully disconnected.",
                "msg_box_select_connection_delete": "Please select a connection to delete.",
                "msg_box_select_connection_rename": "Please select a connection to rename.",
                "msg_box_select_connection_edit": "Please select a connection to edit.",
                "msg_box_install_failed": "The installation could not be verified. Please try it manually.",
                "msg_box_install_error": "An error occurred during the Winget installation: {error}",
                "msg_box_app_exit_info": "The application cannot be executed without Wiresock.",
                "msg_box_default_set": "Standard connection set to '{name}'.",
                "msg_box_open_error": "An error occurred while opening the file: {error}",
                "settings_language_label": "Language:",
                "settings_language_frame": "Language Settings",
                "settings_close_button": "Close",
                "settings_import_title": "Select a Wiresock configuration file (.conf)",
                "settings_file_type": "Configuration files",
                "win_title_status": "Status",
                "status_connecting": "Connecting to {name}...",
                "status_disconnecting": "Disconnecting...",
                "status_closing": "Closing...",
                "status_connected": "Connected",
                "status_connection_failed": "Connection failed"
            }
            with open(default_lang_path, 'w', encoding='utf-8') as f:
                json.dump(initial_translations, f, indent=4)

        # Konfigurationen und Anwendungseinstellungen laden
        self.load_settings()
        
        # UI initialisieren
        self.tray_icon = None
        self.create_tray_icon()
        
    def load_settings(self):
        """Lädt die Anwendungseinstellungen aus der JSON-Datei."""
        settings_path = os.path.join(self.app_dir, SETTINGS_FILE)
        if os.path.exists(settings_path):
            with open(settings_path, 'r', encoding='utf-8') as f:
                self.settings = json.load(f)
        else:
            self.settings = {}
        
        # Sicherstellen, dass alle Schlüssel vorhanden sind
        self.settings.setdefault("wiresock_path", DEFAULT_WIRESOCK_PATH)
        self.settings.setdefault("configs", {})
        self.settings.setdefault("startup_config", None)
        self.settings.setdefault("autostart_enabled", False)
        # Standard-Sprache basierend auf den Systemeinstellungen festlegen
        if "language" not in self.settings:
            # Check if system language file exists, otherwise use default
            system_lang_code = get_system_language()
            if os.path.exists(os.path.join(self.lang_dir, f"{system_lang_code}.json")):
                self.settings["language"] = system_lang_code
            else:
                self.settings["language"] = DEFAULT_LANG
        
        # Sprachdateien laden
        load_translations(self.settings["language"])

        self.save_settings()

    def save_settings(self):
        """Speichert die Anwendungseinstellungen in der JSON-Datei."""
        settings_path = os.path.join(self.app_dir, SETTINGS_FILE)
        with open(settings_path, 'w', encoding='utf-8') as f:
            json.dump(self.settings, f, indent=4)

    def set_language(self, event=None):
        """Ändert die Sprache der Anwendung."""
        new_lang = self.lang_var.get()
        if new_lang != self.settings["language"]:
            self.settings["language"] = new_lang
            self.save_settings()
            load_translations(new_lang)
            # UI-Elemente aktualisieren
            if self.settings_window and self.settings_window.winfo_exists():
                self.update_settings_ui()
            self.update_tray_menu()


    def set_autostart(self, enable):
        """Aktiviert oder deaktiviert den automatischen Start mit Windows."""
        try:
            key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_SET_VALUE)
            
            if enable:
                # Pfad zur ausführbaren Datei (EXE) des Skripts
                exe_path = os.path.abspath(sys.argv[0])
                winreg.SetValueEx(key, AUTOSTART_REGISTRY_KEY, 0, winreg.REG_SZ, exe_path)
                messagebox.showinfo(get_text("msg_box_title_autostart"), get_text("msg_box_autostart_enabled"))
            else:
                try:
                    winreg.DeleteValue(key, AUTOSTART_REGISTRY_KEY)
                    messagebox.showinfo(get_text("msg_box_title_autostart"), get_text("msg_box_autostart_disabled"))
                except FileNotFoundError:
                    pass # Der Key existiert nicht, alles gut
            
            winreg.CloseKey(key)
            self.settings["autostart_enabled"] = enable
            self.save_settings()
            
        except Exception as e:
            messagebox.showerror(get_text("msg_box_title_error"), get_text("msg_box_autostart_error", error=e))

    def get_icon_image(self):
        """Wählt das Icon basierend auf dem Verbindungsstatus aus."""
        icon_path = ""
        if self.is_connected:
            icon_path = os.path.join(self.app_dir, 'icon_green.png')
        elif self.active_connection_name:
             # Aktive Verbindung, aber nicht verbunden (z.B. Verbindungsversuch)
            icon_path = os.path.join(self.app_dir, 'icon_yellow.png')
        else:
            icon_path = os.path.join(self.app_dir, 'icon_red.png')
        
        if not os.path.exists(icon_path):
            # Fallback zu einem generischen Icon, falls keines gefunden wird
            return Image.new('RGB', (64, 64), color='gray')
            
        return Image.open(icon_path)

    def create_tray_icon(self):
        """Erstellt das System-Tray-Icon und sein Menü."""
        image = self.get_icon_image()
        menu_items = self.create_menu_items()
        
        self.tray_icon = pystray.Icon(
            APP_NAME,
            image,
            APP_NAME,
            menu=menu_items
        )
        
        # Startet das Icon in einem separaten Thread, damit es nicht blockiert
        threading.Thread(target=self.tray_icon.run, daemon=True).start()

    def create_menu_items(self):
        """Erstellt das Menü für das System-Tray-Icon basierend auf dem aktuellen Zustand."""
        menu_items = []

        if self.is_connected:
            menu_items.append(pystray.MenuItem(get_text("tray_menu_disconnect", name=self.active_connection_name), lambda icon, item: self.disconnect()))
        else:
            if not self.settings["configs"]:
                menu_items.append(pystray.MenuItem(get_text("tray_menu_no_connections"), None, enabled=False))
            else:
                for name in self.settings["configs"]:
                    # Helferfunktion, um den Verbinden-Callback zu erstellen
                    def create_connect_handler(connection_name):
                        return lambda icon, item: self.connect(connection_name)
                    menu_items.append(pystray.MenuItem(get_text("tray_menu_connect", name=name), create_connect_handler(name)))

        menu_items.append(pystray.Menu.SEPARATOR)
        menu_items.append(pystray.MenuItem(get_text("tray_menu_settings"), lambda icon, item: self.show_settings_window()))
        menu_items.append(pystray.MenuItem(get_text("tray_menu_help_info"), lambda icon, item: self.show_info_window()))
        menu_items.append(pystray.MenuItem(get_text("tray_menu_exit"), lambda icon, item: self.quit_app()))
        
        return pystray.Menu(*menu_items)

    def update_tray_menu(self):
        """Aktualisiert das Menü des Tray-Icons und dessen Icon."""
        if self.tray_icon:
            self.tray_icon.menu = self.create_menu_items()
            self.tray_icon.icon = self.get_icon_image()


    def show_connection_progress_window(self, name):
        """Zeigt ein Fenster mit dem Verbindungsstatus an."""
        if self.status_window and self.status_window.winfo_exists():
            self.status_window.lift()
            return
            
        self.status_window = tk.Toplevel(self.root)
        self.status_window.title(get_text("win_title_status"))
        self.status_window.geometry("400x300")
        self.status_window.resizable(False, False)
        # Verhindert, dass das Fenster geschlossen wird
        self.status_window.protocol("WM_DELETE_WINDOW", lambda: None)
        
        status_text_label = ttk.Label(self.status_window, text=get_text("status_connecting", name=name), padding=10)
        status_text_label.pack()

        # Textfeld für die Ausgabe von Wiresock
        self.status_text = tk.Text(self.status_window, wrap=tk.WORD, height=10)
        self.status_text.pack(expand=True, fill=tk.BOTH, padx=10, pady=5)
        self.status_text.config(state=tk.DISABLED) # Start mit disabled
        
        # Zentriert das Fenster
        self.status_window.update_idletasks()
        width = self.status_window.winfo_width()
        height = self.status_window.winfo_height()
        x = (self.status_window.winfo_screenwidth() // 2) - (width // 2)
        y = (self.status_window.winfo_screenheight() // 2) - (height // 2)
        self.status_window.geometry(f'+{x}+{y}')
        
        self.status_window.update()
        
    def _read_stdout(self):
        """Liest die Ausgabe von Wiresock und schreibt sie in das Textfeld."""
        while self.wiresock_process and self.wiresock_process.poll() is None:
            output_line = self.wiresock_process.stdout.readline()
            if output_line:
                self.status_window.after(0, self._update_status_text, output_line.decode('utf-8'))
        
        # Schließt das Fenster, wenn der Prozess beendet wurde
        self.status_window.after(2000, self.status_window.destroy)
        self.is_connected = False
        self.active_connection_name = None
        self.update_tray_menu()


    def _update_status_text(self, text_to_add):
        """Aktualisiert das Textfeld im Statusfenster mit neuer Ausgabe."""
        if self.status_window and self.status_window.winfo_exists():
            self.status_text.config(state=tk.NORMAL)
            self.status_text.insert(tk.END, text_to_add)
            self.status_text.see(tk.END)
            self.status_text.config(state=tk.DISABLED)


    def connect(self, config_name):
        """Stellt die Verbindung her und startet den Wiresock-Prozess."""
        if self.is_connected:
            messagebox.showinfo(get_text("msg_box_title_success"), get_text("msg_box_connect_active", name=self.active_connection_name))
            return
        
        # Prüfen, ob eine Instanz von Wiresock läuft und diese beenden
        self.disconnect()
        time.sleep(1) # Kurze Pause, um dem Prozess Zeit zum Beenden zu geben
        
        self.show_connection_progress_window(config_name)
        self.status_window.update()

        self.active_connection_name = config_name
        self.update_tray_menu()

        config_file = self.settings["configs"].get(config_name)
        if not config_file:
            messagebox.showerror(get_text("msg_box_title_error"), get_text("msg_box_config_not_found", name=config_name))
            self.active_connection_name = None
            self.update_tray_menu()
            self.status_window.destroy()
            return

        full_config_path = os.path.join(self.configs_dir, config_file)
        if not os.path.exists(full_config_path):
            messagebox.showerror(get_text("msg_box_title_error"), get_text("msg_box_file_not_found", path=full_config_path))
            self.active_connection_name = None
            self.update_tray_menu()
            self.status_window.destroy()
            return

        try:
            # Korrigierter Befehl mit 'run -config' und Anführungszeichen für den Pfad
            cmd = [self.settings["wiresock_path"], 'run', '-config', f'{full_config_path}']
            
            # Starte den Wiresock-Prozess und leite die Ausgabe um
            self.wiresock_process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            
            # Starte Thread zum Lesen der Ausgabe
            threading.Thread(target=self._read_stdout, daemon=True).start()
            
            # Warte kurz, um zu sehen, ob der Prozess sofort fehlschlägt
            time.sleep(1)
            
            # Überprüfe den Status des Prozesses
            if self.wiresock_process.poll() is None:
                self.is_connected = True
                self.update_tray_menu()
                messagebox.showinfo(get_text("msg_box_title_success"), get_text("msg_box_connection_success", name=config_name))
                self.status_window.destroy()
            else:
                self.is_connected = False
                self.update_tray_menu()
                # Fenster bleibt offen, um den Fehler anzuzeigen
                messagebox.showerror(get_text("msg_box_title_error"), get_text("status_connection_failed"))
            
        except FileNotFoundError:
            messagebox.showerror(get_text("msg_box_title_error"), get_text("msg_box_wiresock_not_found_connect", path=self.settings['wiresock_path']))
            self.wiresock_process = None
            self.is_connected = False
            self.status_window.destroy()
        except Exception as e:
            messagebox.showerror(get_text("msg_box_title_error"), get_text("msg_box_connect_error", error=e))
            self.wiresock_process = None
            self.is_connected = False
            self.status_window.destroy()
            
    def disconnect(self):
        """Trennt die aktuelle Verbindung und beendet den Wiresock-Prozess."""
        if not self.wiresock_process:
            return

        try:
            self.wiresock_process.terminate()
            self.wiresock_process.wait(timeout=5)
        except Exception as e:
            print(f"Fehler beim Beenden des Prozesses: {e}")
            try:
                self.wiresock_process.kill()
            except Exception:
                pass

        self.wiresock_process = None
        self.is_connected = False
        self.active_connection_name = None
        self.update_tray_menu()

    def quit_app(self):
        """Beendet die Anwendung, inklusive laufendem Wiresock-Prozess."""
        self.disconnect()
        if self.tray_icon:
            self.tray_icon.stop()
        self.root.destroy()
        sys.exit(0)

    def show_info_window(self):
        """Zeigt ein Fenster mit Informationen über die Anwendung an."""
        info_window = tk.Toplevel(self.root)
        info_window.title(get_text("win_title_info"))
        info_window.geometry("500x200")
        info_window.resizable(False, False)

        info_frame = ttk.Frame(info_window, padding=20)
        info_frame.pack(fill="both", expand=True)

        # Container für Text und Bild
        content_frame = ttk.Frame(info_frame)
        content_frame.pack(fill="both", expand=True)

        text_frame = ttk.Frame(content_frame)
        text_frame.pack(side="left", fill="both", expand=True)
        
        ttk.Label(text_frame, text=get_text("info_text_version", version=APP_VERSION), font=("TkDefaultFont", 12, "bold")).pack(pady=5, anchor="w")
        ttk.Label(text_frame, text=get_text("info_text_author", author=APP_AUTHOR)).pack(anchor="w")
        
        # Link zum GitHub-Repository erstellen
        github_label = ttk.Label(text_frame, text=get_text("info_text_github", github=APP_GITHUB), foreground="blue", cursor="hand2")
        github_label.pack(anchor="w")
        github_label.bind("<Button-1>", lambda e: webbrowser.open(APP_GITHUB))

        # Bild-Container
        image_path = os.path.join(self.app_dir, 'icon.png')
        if os.path.exists(image_path):
            app_logo = Image.open(image_path)
            app_logo = app_logo.resize((100, 100))
            app_logo_tk = tk.PhotoImage(app_logo)
            # Speichern Sie die Referenz, um sie vor der Garbage Collection zu schützen
            info_window.app_logo_tk = app_logo_tk
            
            logo_label = ttk.Label(content_frame, image=app_logo_tk)
            logo_label.pack(side="right", padx=10)
        
        close_button = ttk.Button(info_frame, text=get_text("settings_close_button"), command=info_window.destroy)
        close_button.pack(pady=10)


    def show_settings_window(self):
        """Zeigt das Einstellungsfenster an."""
        if self.settings_window and self.settings_window.winfo_exists():
            self.settings_window.lift()
            return
            
        self.settings_window = tk.Toplevel(self.root)
        self.settings_window.title(get_text("win_title_settings"))
        self.settings_window.geometry("600x570")
        self.settings_window.resizable(False, False)
        self.settings_window.protocol("WM_DELETE_WINDOW", lambda: self.settings_window.destroy())

        # Frame für den Pfad zur Wiresock-Installation
        path_frame = tk.LabelFrame(self.settings_window, text=get_text("settings_path_frame"), padx=10, pady=10)
        path_frame.pack(fill="x", padx=10, pady=5)
        self.path_entry = ttk.Entry(path_frame)
        self.path_entry.insert(0, self.settings["wiresock_path"])
        self.path_entry.pack(side="left", expand=True, fill="x")
        ttk.Button(path_frame, text=get_text("settings_path_button"), command=self.update_wiresock_path).pack(side="left", padx=(5,0))

        # Frame für die Spracheinstellungen
        lang_frame = tk.LabelFrame(self.settings_window, text=get_text("settings_language_frame"), padx=10, pady=5)
        lang_frame.pack(fill="x", padx=10, pady=5)
        
        tk.Label(lang_frame, text=get_text("settings_language_label")).pack(side="left", padx=(0, 5))
        
        self.lang_var = tk.StringVar(value=self.settings["language"])
        available_languages = [os.path.splitext(f)[0] for f in os.listdir(self.lang_dir) if f.endswith('.json')]
        self.lang_dropdown = ttk.Combobox(lang_frame, textvariable=self.lang_var, values=available_languages, state="readonly")
        self.lang_dropdown.pack(side="left", fill="x", expand=True)
        self.lang_dropdown.bind("<<ComboboxSelected>>", self.set_language)

        # Frame für den Import-Bereich
        import_frame = tk.LabelFrame(self.settings_window, text=get_text("settings_import_frame"), padx=10, pady=5)
        import_frame.pack(fill="x", padx=10, pady=5)

        tk.Label(import_frame, text=get_text("settings_import_name_label")).pack(side="left", padx=(0, 5))
        self.config_name_entry = ttk.Entry(import_frame)
        self.config_name_entry.pack(side="left", expand=True, fill="x")
        ttk.Button(import_frame, text=get_text("settings_import_button"), command=self.import_config).pack(side="left", padx=(5, 0))

        # Frame für die Verbindungsliste
        connections_frame = tk.LabelFrame(self.settings_window, text=get_text("settings_connections_frame"), padx=10, pady=5)
        connections_frame.pack(fill="both", expand=True, padx=10, pady=5)
        
        self.connections_listbox = tk.Listbox(connections_frame)
        self.connections_listbox.pack(side="left", fill="both", expand=True)
        
        connections_scrollbar = ttk.Scrollbar(connections_frame, orient="vertical", command=self.connections_listbox.yview)
        connections_scrollbar.pack(side="right", fill="y")
        self.connections_listbox.config(yscrollcommand=connections_scrollbar.set)

        # Buttons zum Löschen, Umbenennen und Bearbeiten
        actions_frame = ttk.Frame(connections_frame)
        actions_frame.pack(side="top", padx=5)
        ttk.Button(actions_frame, text=get_text("settings_connections_delete"), command=self.delete_config).pack(pady=5)
        ttk.Button(actions_frame, text=get_text("settings_connections_rename"), command=self.rename_config).pack(pady=5)
        ttk.Button(actions_frame, text=get_text("settings_connections_edit"), command=self.edit_config).pack(pady=5)

    def update_settings_ui(self):
        """Aktualisiert alle UI-Elemente im Einstellungsfenster basierend auf der aktuellen Sprache."""
        if not self.settings_window or not self.settings_window.winfo_exists():
            return
            
        self.settings_window.title(get_text("win_title_settings"))
        self.settings_window.children['!labelframe'].config(text=get_text("settings_path_frame"))
        self.settings_window.children['!labelframe2'].config(text=get_text("settings_language_frame"))
        self.settings_window.children['!labelframe3'].config(text=get_text("settings_import_frame"))
        self.settings_window.children['!labelframe4'].config(text=get_text("settings_connections_frame"))
        
        # Labels und Buttons
        self.settings_window.children['!labelframe'].children['!button'].config(text=get_text("settings_path_button"))
        self.settings_window.children['!labelframe2'].children['!label'].config(text=get_text("settings_language_label"))
        self.settings_window.children['!labelframe3'].children['!label'].config(text=get_text("settings_import_name_label"))
        self.settings_window.children['!labelframe3'].children['!button'].config(text=get_text("settings_import_button"))
        self.settings_window.children['!labelframe4'].children['!frame'].children['!button'].config(text=get_text("settings_connections_delete"))
        self.settings_window.children['!labelframe4'].children['!frame'].children['!button2'].config(text=get_text("settings_connections_rename"))
        self.settings_window.children['!labelframe4'].children['!frame'].children['!button3'].config(text=get_text("settings_connections_edit"))
        

    def update_wiresock_path(self):
        """Aktualisiert den Pfad zur Wiresock-Installation und speichert ihn."""
        new_path = self.path_entry.get().strip()
        if new_path and os.path.exists(new_path):
            self.settings["wiresock_path"] = new_path
            self.save_settings()
            messagebox.showinfo(get_text("msg_box_title_success"), get_text("msg_box_path_saved"))
        else:
            messagebox.showerror(get_text("msg_box_title_error"), get_text("msg_box_path_invalid"))

    def update_connections_list(self):
        """Aktualisiert die Listbox mit den importierten Verbindungen."""
        self.connections_listbox.delete(0, tk.END)
        for name in self.settings["configs"]:
            self.connections_listbox.insert(tk.END, name)

    def update_startup_dropdown(self):
        """Diese Methode ist jetzt leer, da die Autostart-Funktion entfernt wurde."""
        pass

    def set_default_config(self, event):
        """Diese Methode ist jetzt leer, da die Autostart-Funktion entfernt wurde."""
        pass

    def import_config(self):
        """Öffnet den Dateidialog, kopiert die ausgewählte Datei und fügt sie zur Liste hinzu."""
        file_path = filedialog.askopenfilename(
            title=get_text("settings_import_title"),
            filetypes=[(get_text("settings_file_type"), "*.conf")]
        )
        if not file_path:
            return

        config_name = self.config_name_entry.get().strip()
        if not config_name:
            messagebox.showwarning(get_text("msg_box_title_warning"), get_text("msg_box_name_required"))
            return

        # Überprüfen, ob der Name bereits existiert
        if config_name in self.settings["configs"]:
            messagebox.showwarning(get_text("msg_box_title_warning"), get_text("msg_box_name_exists", name=config_name))
            return

        try:
            filename = os.path.basename(file_path)
            destination = os.path.join(self.configs_dir, filename)
            
            # Kopieren der Datei in das Anwendungsverzeichnis
            with open(file_path, 'rb') as src, open(destination, 'wb') as dst:
                dst.write(src.read())

            self.settings["configs"][config_name] = filename
            self.save_settings()
            self.update_connections_list()
            self.update_tray_menu()
            self.update_startup_dropdown()
            messagebox.showinfo(get_text("msg_box_title_success"), get_text("msg_box_import_success", name=config_name))
        except Exception as e:
            messagebox.showerror(get_text("msg_box_title_error"), get_text("msg_box_import_error", error=e))

    def delete_config(self):
        """Löscht die ausgewählte Konfigurationsdatei und den Eintrag."""
        selected_name = self.connections_listbox.get(tk.ACTIVE)
        if not selected_name:
            messagebox.showwarning(get_text("msg_box_title_warning"), get_text("msg_box_select_connection_delete"))
            return

        if messagebox.askyesno(get_text("msg_box_title_confirm"), get_text("msg_box_delete_confirm", name=selected_name)):
            filename_to_delete = self.settings["configs"].pop(selected_name, None)
            
            # Standardverbindung zurücksetzen, wenn sie gelöscht wurde
            if self.settings["startup_config"] == selected_name:
                self.settings["startup_config"] = None
                
            self.save_settings()
            self.update_connections_list()
            self.update_tray_menu()
            self.update_startup_dropdown()
            messagebox.showinfo(get_text("msg_box_title_success"), get_text("msg_box_delete_success", name=selected_name))
            # Löschen der physischen Datei
            if filename_to_delete:
                file_path = os.path.join(self.configs_dir, filename_to_delete)
                if os.path.exists(file_path):
                    os.remove(file_path)

    def rename_config(self):
        """Ermöglicht das Umbenennen einer ausgewählten Verbindung."""
        selected_name = self.connections_listbox.get(tk.ACTIVE)
        if not selected_name:
            messagebox.showwarning(get_text("msg_box_title_warning"), get_text("msg_box_select_connection_rename"))
            return

        new_name = tk.simpledialog.askstring(get_text("msg_box_rename_title"), get_text("msg_box_rename_title", old_name=selected_name), parent=self.settings_window)
        if new_name and new_name.strip() and new_name != selected_name:
            if new_name in self.settings["configs"]:
                messagebox.showwarning(get_text("msg_box_title_warning"), get_text("msg_box_name_exists", name=new_name))
                return

            filename = self.settings["configs"].pop(selected_name)
            self.settings["configs"][new_name] = filename
            
            # Standardverbindung aktualisieren, falls umbenannt
            if self.settings["startup_config"] == selected_name:
                self.settings["startup_config"] = new_name
            
            self.save_settings()
            self.update_connections_list()
            self.update_tray_menu()
            self.update_startup_dropdown()
            messagebox.showinfo(get_text("msg_box_title_success"), get_text("msg_box_rename_success", old_name=selected_name, new_name=new_name))

    def edit_config(self):
        """Öffnet die ausgewählte Konfigurationsdatei in einem Texteditor."""
        selected_name = self.connections_listbox.get(tk.ACTIVE)
        if not selected_name:
            messagebox.showwarning(get_text("msg_box_title_warning"), get_text("msg_box_select_connection_edit"))
            return
            
        config_file_name = self.settings["configs"].get(selected_name)
        if not config_file_name:
            messagebox.showerror(get_text("msg_box_title_error"), get_text("msg_box_config_not_found", name=selected_name))
            return
            
        full_path = os.path.join(self.configs_dir, config_file_name)
        
        try:
            # Versucht, die Datei mit dem Standardprogramm zu öffnen
            os.startfile(full_path)
        except FileNotFoundError:
            messagebox.showerror(get_text("msg_box_title_error"), get_text("msg_box_file_not_found", path=full_path))
        except Exception as e:
            messagebox.showerror(get_text("msg_box_title_error"), get_text("msg_box_open_error", error=e))

    def run_default_on_startup(self):
        """Stellt die Standardverbindung her, wenn der Autostart aktiviert ist."""
        if self.settings["autostart_enabled"] and self.settings["startup_config"]:
            self.root.after(500, self.connect, self.settings["startup_config"])


if __name__ == '__main__':
    # Laden der Pfadeinstellungen vor dem Installations-Check
    root = tk.Tk()
    root.withdraw()

    temp_app = WiresockApp(root)
    
    # Prüfen, ob Wiresock installiert ist, bevor die Anwendung startet
    if check_wiresock_installation(temp_app.settings["wiresock_path"]):
        app = temp_app
        # Automatische Verbindung bei Start der Anwendung, falls konfiguriert
        app.run_default_on_startup()
        
        # Tkinter Hauptschleife starten, damit Dialoge und Fenster funktionieren
        root.mainloop()
    else:
        # Wenn Wiresock nicht gefunden wird und der Nutzer die Installation ablehnt,
        # wird die Anwendung gestartet und sofort das Einstellungsfenster angezeigt.
        app = temp_app
        app.show_settings_window()
        root.mainloop()
