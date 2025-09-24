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

# Standardpfad zur Wiresock-Binärdatei
DEFAULT_WIRESOCK_PATH = 'C:\\Program Files\\WireSock Secure Connect\\bin\\wiresock-client.exe'

# Dateinamen für die Konfigurationsverwaltung und den Autostart-Key definieren
SETTINGS_FILE = 'app_settings.json'
AUTOSTART_REGISTRY_KEY = 'WiresockTrayUI'

def check_wiresock_installation(path_to_check):
    """Prüft, ob Wiresock installiert ist und bietet die Installation über Winget an."""
    if os.path.exists(path_to_check):
        return True
    
    response = messagebox.askyesno(
        "Wiresock nicht gefunden",
        f"Wiresock wurde unter dem Pfad '{path_to_check}' nicht gefunden. "
        "Möchtest du es jetzt über Winget installieren?"
    )
    
    if response:
        try:
            print("Starte Installation...")
            # Starte die Installation über winget in einem separaten Fenster
            # Fügen Sie 'start' am Anfang hinzu, um die Winget-Installation in einem neuen Fenster auszuführen
            subprocess.run(['start', 'winget', 'install', 'NTKERNEL.WireSockVPNClient'], shell=True, check=True)
            
            # Warten, bis die Installation abgeschlossen ist
            print("Installation abgeschlossen. Überprüfe Installation...")
            # Nach einer kurzen Pause den Pfad erneut überprüfen
            time.sleep(2)
            if os.path.exists(DEFAULT_WIRESOCK_PATH):
                messagebox.showinfo("Installation erfolgreich", "Wiresock wurde erfolgreich installiert. Die Anwendung wird gestartet.")
                return True
            else:
                messagebox.showerror("Installation fehlgeschlagen", "Die Installation konnte nicht überprüft werden. Bitte versuche es manuell.")
                return False
        except Exception as e:
            messagebox.showerror("Fehler bei der Installation", f"Ein Fehler ist bei der Winget-Installation aufgetreten: {e}")
            return False
    else:
        # Wenn der Benutzer "Nein" wählt, beenden wir das Skript nicht mehr
        # Stattdessen kehren wir zum Hauptprogramm zurück, um das Einstellungsfenster zu öffnen.
        return False

class WiresockApp:
    def __init__(self):
        # Initialisierung der Anwendungs- und UI-Zustände
        self.is_connected = False
        self.active_connection_name = None
        self.wiresock_process = None
        self.settings = {}
        self.settings_window = None

        # Sicherstellen, dass das Konfigurationsverzeichnis existiert
        self.app_dir = os.path.dirname(os.path.abspath(sys.argv[0]))
        self.configs_dir = os.path.join(self.app_dir, 'configs')
        os.makedirs(self.configs_dir, exist_ok=True)

        # Konfigurationen und Anwendungseinstellungen laden
        self.load_settings()
        
        # UI initialisieren
        self.tray_icon = None
        self.create_tray_icon()
        
    def load_settings(self):
        """Lädt die Anwendungseinstellungen aus der JSON-Datei."""
        settings_path = os.path.join(self.app_dir, SETTINGS_FILE)
        if os.path.exists(settings_path):
            with open(settings_path, 'r') as f:
                self.settings = json.load(f)
        else:
            self.settings = {}
        
        # Sicherstellen, dass alle Schlüssel vorhanden sind
        self.settings.setdefault("wiresock_path", DEFAULT_WIRESOCK_PATH)
        self.settings.setdefault("configs", {})
        self.settings.setdefault("startup_config", None)
        self.settings.setdefault("autostart_enabled", False)

        self.save_settings()

    def save_settings(self):
        """Speichert die Anwendungseinstellungen in der JSON-Datei."""
        settings_path = os.path.join(self.app_dir, SETTINGS_FILE)
        with open(settings_path, 'w') as f:
            json.dump(self.settings, f, indent=4)

    def set_autostart(self, enable):
        """Aktiviert oder deaktiviert den automatischen Start mit Windows."""
        try:
            key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_SET_VALUE)
            
            if enable:
                # Pfad zur ausführbaren Datei (EXE) des Skripts
                exe_path = os.path.abspath(sys.argv[0])
                winreg.SetValueEx(key, AUTOSTART_REGISTRY_KEY, 0, winreg.REG_SZ, exe_path)
                messagebox.showinfo("Autostart", "Die Anwendung wird nun automatisch mit Windows gestartet.")
            else:
                try:
                    winreg.DeleteValue(key, AUTOSTART_REGISTRY_KEY)
                    messagebox.showinfo("Autostart", "Der automatische Start wurde deaktiviert.")
                except FileNotFoundError:
                    pass # Der Key existiert nicht, alles gut
            
            winreg.CloseKey(key)
            self.settings["autostart_enabled"] = enable
            self.save_settings()
            
        except Exception as e:
            messagebox.showerror("Fehler", f"Autostart konnte nicht geändert werden: {e}")

    def create_tray_icon(self):
        """Erstellt das System-Tray-Icon und sein Menü."""
        icon_path = os.path.join(self.app_dir, 'icon.png')
        if not os.path.exists(icon_path):
            # Erstellt ein einfaches Standard-Icon, wenn keines gefunden wird
            image = Image.new('RGB', (64, 64), color='green')
            image.save(icon_path)
            
        image = Image.open(icon_path)
        menu_items = self.create_menu_items()
        
        self.tray_icon = pystray.Icon(
            'wiresock_ui',
            image,
            'Wiresock UI',
            menu=menu_items
        )
        
        # Startet das Icon in einem separaten Thread, damit es nicht blockiert
        threading.Thread(target=self.tray_icon.run, daemon=True).start()

    def create_menu_items(self):
        """Erstellt das Menü für das System-Tray-Icon basierend auf dem aktuellen Zustand."""
        menu_items = []

        if self.is_connected:
            menu_items.append(pystray.MenuItem(f'Trennen ({self.active_connection_name})', lambda icon, item: self.disconnect()))
        else:
            if not self.settings["configs"]:
                menu_items.append(pystray.MenuItem('Keine Verbindungen verfügbar', None, enabled=False))
            else:
                for name in self.settings["configs"]:
                    # Helferfunktion, um den Verbinden-Callback zu erstellen
                    def create_connect_handler(connection_name):
                        return lambda icon, item: self.connect(connection_name)
                    menu_items.append(pystray.MenuItem(f'Verbinden ({name})', create_connect_handler(name)))

        menu_items.append(pystray.Menu.SEPARATOR)
        menu_items.append(pystray.MenuItem('Einstellungen', lambda icon, item: self.show_settings_window()))
        menu_items.append(pystray.MenuItem('Beenden', lambda icon, item: self.quit_app()))
        
        return pystray.Menu(*menu_items)

    def update_tray_menu(self):
        """Aktualisiert das Menü des Tray-Icons."""
        if self.tray_icon:
            self.tray_icon.menu = self.create_menu_items()

    def connect(self, config_name):
        """Stellt die Verbindung her und startet den Wiresock-Prozess."""
        if self.is_connected:
            messagebox.showinfo("Verbindung", f"Es ist bereits eine Verbindung aktiv: {self.active_connection_name}")
            return

        config_file = self.settings["configs"].get(config_name)
        if not config_file:
            messagebox.showerror("Fehler", f"Die Konfiguration '{config_name}' wurde nicht gefunden.")
            return

        full_config_path = os.path.join(self.configs_dir, config_file)
        if not os.path.exists(full_config_path):
            messagebox.showerror("Fehler", f"Die Konfigurationsdatei '{full_config_path}' wurde nicht gefunden.")
            return

        try:
            # Starte den Wiresock-Prozess im Hintergrund
            self.wiresock_process = subprocess.Popen(
                [self.settings["wiresock_path"], '-c', full_config_path],
                creationflags=subprocess.CREATE_NO_WINDOW # Verhindert das Konsolenfenster unter Windows
            )
            self.is_connected = True
            self.active_connection_name = config_name
            messagebox.showinfo("Verbindung hergestellt", f"Verbindung mit '{config_name}' wurde erfolgreich aufgebaut.")
        except FileNotFoundError:
            messagebox.showerror("Fehler", f"Die Datei '{self.settings['wiresock_path']}' wurde nicht gefunden. Bitte installiere Wiresock oder korrigiere den Pfad in den Einstellungen.")
            self.wiresock_process = None
        except Exception as e:
            messagebox.showerror("Fehler", f"Ein Fehler ist beim Verbinden aufgetreten: {e}")
            self.wiresock_process = None

        self.update_tray_menu()

    def disconnect(self):
        """Trennt die aktuelle Verbindung und beendet den Wiresock-Prozess."""
        if not self.is_connected or not self.wiresock_process:
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

        self.is_connected = False
        self.active_connection_name = None
        self.wiresock_process = None
        messagebox.showinfo("Verbindung getrennt", "Die Verbindung wurde erfolgreich getrennt.")
        self.update_tray_menu()

    def quit_app(self):
        """Beendet die Anwendung, inklusive laufendem Wiresock-Prozess."""
        self.disconnect()
        if self.tray_icon:
            self.tray_icon.stop()
        sys.exit(0)

    def show_settings_window(self):
        """Zeigt das Einstellungsfenster an."""
        if self.settings_window and self.settings_window.winfo_exists():
            self.settings_window.lift()
            return
            
        self.settings_window = tk.Toplevel()
        self.settings_window.title("Wiresock-Einstellungen")
        self.settings_window.geometry("500x400")
        self.settings_window.protocol("WM_DELETE_WINDOW", lambda: self.settings_window.destroy())

        # Frame für den Pfad zur Wiresock-Installation
        path_frame = tk.LabelFrame(self.settings_window, text="Pfad zur Wiresock-Installation", padx=10, pady=10)
        path_frame.pack(fill="x", padx=10, pady=5)
        self.path_entry = ttk.Entry(path_frame)
        self.path_entry.insert(0, self.settings["wiresock_path"])
        self.path_entry.pack(side="left", expand=True, fill="x")
        ttk.Button(path_frame, text="Speichern", command=self.update_wiresock_path).pack(side="left", padx=(5,0))

        # Frame für den Import-Bereich
        import_frame = tk.LabelFrame(self.settings_window, text="Konfigurationsdatei importieren", padx=10, pady=10)
        import_frame.pack(fill="x", padx=10, pady=5)

        tk.Label(import_frame, text="Name für die Verbindung:").pack(side="left", padx=(0, 5))
        self.config_name_entry = ttk.Entry(import_frame)
        self.config_name_entry.pack(side="left", expand=True, fill="x")
        ttk.Button(import_frame, text="Importieren", command=self.import_config).pack(side="left", padx=(5, 0))

        # Frame für die Verbindungsliste
        connections_frame = tk.LabelFrame(self.settings_window, text="Verbindungen verwalten", padx=10, pady=10)
        connections_frame.pack(fill="both", expand=True, padx=10, pady=5)
        
        self.connections_listbox = tk.Listbox(connections_frame)
        self.connections_listbox.pack(side="left", fill="both", expand=True)
        
        connections_scrollbar = ttk.Scrollbar(connections_frame, orient="vertical", command=self.connections_listbox.yview)
        connections_scrollbar.pack(side="right", fill="y")
        self.connections_listbox.config(yscrollcommand=connections_scrollbar.set)

        # Buttons zum Löschen, Umbenennen und Bearbeiten
        actions_frame = ttk.Frame(connections_frame)
        actions_frame.pack(side="top", padx=5)
        ttk.Button(actions_frame, text="Löschen", command=self.delete_config).pack(side="left", padx=2, pady=5)
        ttk.Button(actions_frame, text="Umbenennen", command=self.rename_config).pack(side="left", padx=2, pady=5)
        ttk.Button(actions_frame, text="Bearbeiten", command=self.edit_config).pack(side="left", padx=2, pady=5)

        # Frame für Autostart und Standardverbindung
        startup_frame = tk.LabelFrame(self.settings_window, text="Start-Einstellungen", padx=10, pady=10)
        startup_frame.pack(fill="x", padx=10, pady=5)

        self.autostart_var = tk.BooleanVar(value=self.settings["autostart_enabled"])
        self.autostart_checkbox = ttk.Checkbutton(startup_frame, text="Beim Start von Windows starten", variable=self.autostart_var, command=lambda: self.set_autostart(self.autostart_var.get()))
        self.autostart_checkbox.pack(in_=startup_frame, anchor="w", pady=(0, 5))

        self.default_config_var = tk.StringVar(value=self.settings["startup_config"] or "")
        tk.Label(startup_frame, text="Standard-Verbindung beim Start:").pack(in_=startup_frame, anchor="w", pady=(5,0))
        self.default_config_dropdown = ttk.Combobox(startup_frame, textvariable=self.default_config_var, state="readonly")
        self.default_config_dropdown.pack(in_=startup_frame, fill="x", pady=5)
        self.default_config_dropdown.bind("<<ComboboxSelected>>", self.set_default_config)

        self.update_connections_list()
        self.update_startup_dropdown()

    def update_wiresock_path(self):
        """Aktualisiert den Pfad zur Wiresock-Installation und speichert ihn."""
        new_path = self.path_entry.get().strip()
        if new_path and os.path.exists(new_path):
            self.settings["wiresock_path"] = new_path
            self.save_settings()
            messagebox.showinfo("Pfad gespeichert", "Der Pfad wurde erfolgreich aktualisiert. Die Anwendung verwendet nun diesen Pfad.")
        else:
            messagebox.showerror("Fehler", "Ungültiger Pfad. Bitte überprüfe, ob die Datei existiert.")


    def update_connections_list(self):
        """Aktualisiert die Listbox mit den importierten Verbindungen."""
        self.connections_listbox.delete(0, tk.END)
        for name in self.settings["configs"]:
            self.connections_listbox.insert(tk.END, name)

    def update_startup_dropdown(self):
        """Aktualisiert die Dropdown-Liste für die Standardverbindung."""
        current_options = ["Keine"] + list(self.settings["configs"].keys())
        self.default_config_dropdown['values'] = current_options
        
        if self.settings["startup_config"] in current_options:
            self.default_config_var.set(self.settings["startup_config"])
        else:
            self.default_config_var.set("Keine")
            self.settings["startup_config"] = None
            self.save_settings()

    def set_default_config(self, event):
        """Setzt die ausgewählte Konfiguration als Standardverbindung."""
        selected_name = self.default_config_var.get()
        if selected_name == "Keine":
            self.settings["startup_config"] = None
        else:
            self.settings["startup_config"] = selected_name
        self.save_settings()
        messagebox.showinfo("Standard-Verbindung", f"'{selected_name}' wurde als Standard-Verbindung festgelegt.")

    def import_config(self):
        """Öffnet den Dateidialog, kopiert die ausgewählte Datei und fügt sie zur Liste hinzu."""
        file_path = filedialog.askopenfilename(
            title="Wähle eine Wiresock-Konfigurationsdatei (.conf)",
            filetypes=[("Konfigurationsdateien", "*.conf")]
        )
        if not file_path:
            return

        config_name = self.config_name_entry.get().strip()
        if not config_name:
            messagebox.showwarning("Warnung", "Bitte gib einen Namen für die Verbindung ein.")
            return

        # Überprüfen, ob der Name bereits existiert
        if config_name in self.settings["configs"]:
            messagebox.showwarning("Warnung", f"Der Name '{config_name}' existiert bereits. Bitte wähle einen anderen.")
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
            messagebox.showinfo("Import erfolgreich", f"'{config_name}' wurde erfolgreich importiert.")
        except Exception as e:
            messagebox.showerror("Fehler", f"Ein Fehler ist beim Import aufgetreten: {e}")

    def delete_config(self):
        """Löscht die ausgewählte Konfigurationsdatei und den Eintrag."""
        selected_name = self.connections_listbox.get(tk.ACTIVE)
        if not selected_name:
            messagebox.showwarning("Warnung", "Bitte wähle eine Verbindung zum Löschen aus.")
            return

        if messagebox.askyesno("Löschen bestätigen", f"Möchtest du '{selected_name}' wirklich löschen?"):
            filename_to_delete = self.settings["configs"].pop(selected_name, None)
            
            # Löschen der physischen Datei
            if filename_to_delete:
                file_path = os.path.join(self.configs_dir, filename_to_delete)
                if os.path.exists(file_path):
                    os.remove(file_path)
            
            # Standardverbindung zurücksetzen, wenn sie gelöscht wurde
            if self.settings["startup_config"] == selected_name:
                self.settings["startup_config"] = None
                
            self.save_settings()
            self.update_connections_list()
            self.update_tray_menu()
            self.update_startup_dropdown()
            messagebox.showinfo("Erfolgreich gelöscht", f"'{selected_name}' wurde gelöscht.")

    def rename_config(self):
        """Ermöglicht das Umbenennen einer ausgewählten Verbindung."""
        selected_name = self.connections_listbox.get(tk.ACTIVE)
        if not selected_name:
            messagebox.showwarning("Warnung", "Bitte wähle eine Verbindung zum Umbenennen aus.")
            return

        new_name = tk.simpledialog.askstring("Umbenennen", f"Neuer Name für '{selected_name}':", parent=self.settings_window)
        if new_name and new_name.strip() and new_name != selected_name:
            if new_name in self.settings["configs"]:
                messagebox.showwarning("Warnung", "Dieser Name existiert bereits.")
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
            messagebox.showinfo("Erfolgreich umbenannt", f"'{selected_name}' wurde in '{new_name}' umbenannt.")

    def edit_config(self):
        """Öffnet die ausgewählte Konfigurationsdatei in einem Texteditor."""
        selected_name = self.connections_listbox.get(tk.ACTIVE)
        if not selected_name:
            messagebox.showwarning("Warnung", "Bitte wähle eine Verbindung zum Bearbeiten aus.")
            return
            
        config_file_name = self.settings["configs"].get(selected_name)
        if not config_file_name:
            messagebox.showerror("Fehler", f"Konfigurationsdatei für '{selected_name}' nicht gefunden.")
            return
            
        full_path = os.path.join(self.configs_dir, config_file_name)
        
        try:
            # Versucht, die Datei mit dem Standardprogramm zu öffnen
            os.startfile(full_path)
        except FileNotFoundError:
            messagebox.showerror("Fehler", f"Datei nicht gefunden: {full_path}")
        except Exception as e:
            messagebox.showerror("Fehler", f"Ein Fehler ist beim Öffnen der Datei aufgetreten: {e}")

    def run_default_on_startup(self):
        """Stellt die Standardverbindung her, wenn der Autostart aktiviert ist."""
        if self.settings["autostart_enabled"] and self.settings["startup_config"]:
            self.connect(self.settings["startup_config"])


if __name__ == '__main__':
    # Laden der Pfadeinstellungen vor dem Installations-Check
    temp_app = WiresockApp()
    
    # Prüfen, ob Wiresock installiert ist, bevor die Anwendung startet
    if check_wiresock_installation(temp_app.settings["wiresock_path"]):
        app = temp_app
        # Automatische Verbindung bei Start der Anwendung, falls konfiguriert
        app.run_default_on_startup()
        
        # Tkinter Hauptschleife starten, damit Dialoge und Fenster funktionieren
        tk.Tk().withdraw()  # Verhindert, dass das Hauptfenster von Python angezeigt wird
        tk.mainloop()
    else:
        # Wenn Wiresock nicht gefunden wird und der Nutzer die Installation ablehnt,
        # wird die Anwendung gestartet und sofort das Einstellungsfenster angezeigt.
        app = temp_app
        app.show_settings_window()
        tk.Tk().withdraw()
        tk.mainloop()
