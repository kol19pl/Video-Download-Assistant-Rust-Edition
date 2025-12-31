#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Video Download Assistant - GUI Server Launcher
Nowoczesne okno GUI w stylu cyberpunk z animacjami
"""

import sys
import os
import subprocess
import tkinter as tk
from tkinter import messagebox, filedialog
import threading
import datetime
import json
import time
import locale

# Ustaw kodowanie UTF-8
if sys.platform == 'win32':
    # Dla Windows ustaw UTF-8 w konsoli
    try:
        import ctypes
        kernel32 = ctypes.windll.kernel32
        kernel32.SetConsoleOutputCP(65001)
        kernel32.SetConsoleCP(65001)
    except:
        pass

# Ustaw locale na polskie jeśli dostępne
try:
    if sys.platform == 'win32':
        locale.setlocale(locale.LC_ALL, 'pl_PL.UTF-8')
    else:
        locale.setlocale(locale.LC_ALL, 'pl_PL.utf8')
except:
    try:
        locale.setlocale(locale.LC_ALL, '')
    except:
        pass

class FuturisticServerGUI:
    def __init__(self):
        self.server_process = None
        self.server_running = False
        self.manual_shutdown = False  # Flaga dla ręcznego zatrzymania
        self.log_history = []
        self.downloads_folder = os.path.join(os.path.expanduser("~"), "Downloads")
        self.downloads_count = 0
        self.start_time = None
        
        # Kolory cyberpunkowe
        self.colors = {
            'bg_dark': '#0a0e27',           # Ciemny granatowy tło
            'bg_panel': '#1a1f3a',          # Ciemniejszy panel
            'bg_lighter': '#2d3561',        # Jaśniejsze tło
            'primary': '#00ff9f',           # Neon zielony
            'secondary': '#00d4ff',         # Neon niebieski
            'accent': '#ff00ff',            # Neon różowy
            'warning': '#ffaa00',           # Pomarańczowy
            'error': '#ff0055',             # Neon czerwony
            'success': '#00ff00',           # Zielony
            'text': '#e0e0e0',              # Jasny tekst
            'text_dim': '#808080',          # Przyciemniony tekst
            'glow': '#00ffff'               # Cyan świecący
        }
        
        self.root = tk.Tk()
        self.root.title("Video Download Assistant - Server")
        self.root.geometry("1100x750")
        self.root.minsize(900, 600)
        self.root.configure(bg=self.colors['bg_dark'])
        self.root.resizable(True, True)
        
        self.load_settings()
        self.create_gui()
        self.check_requirements()
        self.animate_startup()
        
    def load_settings(self):
        """Wczytaj zapisane ustawienia"""
        settings_file = os.path.join(os.path.dirname(__file__), 'server_settings.json')
        if os.path.exists(settings_file):
            try:
                with open(settings_file, 'r', encoding='utf-8') as f:
                    settings = json.load(f)
                    self.downloads_folder = settings.get('downloads_folder', self.downloads_folder)
            except:
                pass
    
    def save_settings(self):
        """Zapisz ustawienia"""
        settings_file = os.path.join(os.path.dirname(__file__), 'server_settings.json')
        try:
            with open(settings_file, 'w', encoding='utf-8') as f:
                json.dump({'downloads_folder': self.downloads_folder}, f, indent=2)
        except:
            pass
    
    def create_gui(self):
        """Stwórz futurystyczny interfejs GUI"""
        
        # ============= NAGŁÓWEK =============
        header_frame = tk.Frame(self.root, bg=self.colors['bg_panel'], height=140)
        header_frame.pack(fill=tk.X, padx=0, pady=0)
        header_frame.pack_propagate(False)
        
        # ASCII Art Title - VDA SERVER
        title_label = tk.Label(
            header_frame,
            text="██╗   ██╗██████╗  █████╗     ███████╗███████╗██████╗ ██╗   ██╗███████╗██████╗\n"
                 "██║   ██║██╔══██╗██╔══██╗    ██╔════╝██╔════╝██╔══██╗██║   ██║██╔════╝██╔══██╗\n"
                 "██║   ██║██║  ██║███████║    ███████╗█████╗  ██████╔╝██║   ██║█████╗  ██████╔╝\n"
                 "╚██╗ ██╔╝██║  ██║██╔══██║    ╚════██║██╔══╝  ██╔══██╗╚██╗ ██╔╝██╔══╝  ██╔══██╗\n"
                 " ╚████╔╝ ██████╔╝██║  ██║    ███████║███████╗██║  ██║ ╚████╔╝ ███████╗██║  ██║\n"
                 "  ╚═══╝  ╚═════╝ ╚═╝  ╚═╝    ╚══════╝╚══════╝╚═╝  ╚═╝  ╚═══╝  ╚══════╝╚═╝  ╚═╝",
            font=('Consolas', 8, 'bold'),
            fg=self.colors['accent'],
            bg=self.colors['bg_panel'],
            justify=tk.LEFT
        )
        title_label.pack(pady=(10, 0), padx=10)
        
        # Subtitle
        subtitle_label = tk.Label(
            header_frame,
            text="LOCAL SERVER v2.0",
            font=('Consolas', 9, 'bold'),
            fg=self.colors['secondary'],
            bg=self.colors['bg_panel']
        )
        subtitle_label.pack(pady=(5, 5))
        
        # Linia oddzielająca z efektem świecenia
        separator1 = tk.Frame(self.root, bg=self.colors['primary'], height=2)
        separator1.pack(fill=tk.X)
        
        # ============= GŁÓWNY KONTENER =============
        main_container = tk.Frame(self.root, bg=self.colors['bg_dark'])
        main_container.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)
        
        # Lewy panel (70%) - Activity Log
        left_panel = tk.Frame(main_container, bg=self.colors['bg_dark'])
        left_panel.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 10))
        
        # Prawy panel (30%) - Status i kontrolki
        right_panel = tk.Frame(main_container, bg=self.colors['bg_dark'])
        right_panel.pack(side=tk.RIGHT, fill=tk.BOTH, padx=(10, 0))
        
        # ============= ACTIVITY LOG (LEWY PANEL) =============
        log_header = tk.Frame(left_panel, bg=self.colors['bg_panel'], height=50)
        log_header.pack(fill=tk.X)
        log_header.pack_propagate(False)
        
        log_title = tk.Label(
            log_header,
            text="📊 ACTIVITY LOG",
            font=('Segoe UI', 16, 'bold'),
            fg=self.colors['secondary'],
            bg=self.colors['bg_panel']
        )
        log_title.pack(side=tk.LEFT, padx=15, pady=10)
        
        self.log_count_label = tk.Label(
            log_header,
            text="(0)",
            font=('Segoe UI', 12, 'bold'),
            fg=self.colors['accent'],
            bg=self.colors['bg_panel']
        )
        self.log_count_label.pack(side=tk.LEFT, pady=10)
        
        # Przycisk eksportu logów
        export_btn = tk.Button(
            log_header,
            text="💾 Eksportuj",
            font=('Segoe UI', 9),
            fg=self.colors['text'],
            bg=self.colors['bg_lighter'],
            activebackground=self.colors['secondary'],
            activeforeground='white',
            relief=tk.FLAT,
            bd=0,
            padx=15,
            pady=5,
            cursor='hand2',
            command=self.export_logs
        )
        export_btn.pack(side=tk.RIGHT, padx=(0, 10), pady=10)
        
        # Przycisk czyszczenia logów
        clear_btn = tk.Button(
            log_header,
            text="🗑️ Wyczyść",
            font=('Segoe UI', 9),
            fg=self.colors['text'],
            bg=self.colors['bg_lighter'],
            activebackground=self.colors['warning'],
            activeforeground='white',
            relief=tk.FLAT,
            bd=0,
            padx=15,
            pady=5,
            cursor='hand2',
            command=self.clear_logs
        )
        clear_btn.pack(side=tk.RIGHT, padx=(0, 5), pady=10)
        
        # Text widget dla logów z scrollbarem
        log_container = tk.Frame(left_panel, bg=self.colors['bg_panel'])
        log_container.pack(fill=tk.BOTH, expand=True, pady=(2, 0))
        
        scrollbar = tk.Scrollbar(log_container, bg=self.colors['bg_lighter'])
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.log_text = tk.Text(
            log_container,
            wrap=tk.WORD,
            font=('Consolas', 10),
            bg=self.colors['bg_panel'],
            fg=self.colors['text'],
            insertbackground=self.colors['primary'],
            selectbackground=self.colors['bg_lighter'],
            selectforeground=self.colors['text'],
            relief=tk.FLAT,
            bd=0,
            padx=15,
            pady=10,
            yscrollcommand=scrollbar.set
        )
        self.log_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.config(command=self.log_text.yview)
        
        # Konfiguracja tagów kolorów dla logów
        self.log_text.tag_config('timestamp', foreground=self.colors['text_dim'])
        self.log_text.tag_config('success', foreground=self.colors['success'])
        self.log_text.tag_config('error', foreground=self.colors['error'])
        self.log_text.tag_config('warning', foreground=self.colors['warning'])
        self.log_text.tag_config('info', foreground=self.colors['secondary'])
        self.log_text.tag_config('download', foreground=self.colors['primary'])
        self.log_text.tag_config('accent', foreground=self.colors['accent'])
        
        # ============= STATUS PANEL (PRAWY GÓRNY) =============
        status_frame = tk.Frame(right_panel, bg=self.colors['bg_panel'], width=350)
        status_frame.pack(fill=tk.X, pady=(0, 15))
        status_frame.pack_propagate(False)
        
        status_header = tk.Label(
            status_frame,
            text="⚡ SYSTEM STATUS",
            font=('Segoe UI', 14, 'bold'),
            fg=self.colors['accent'],
            bg=self.colors['bg_panel']
        )
        status_header.pack(pady=(15, 10))
        
        # Status indicator z animacją
        status_container = tk.Frame(status_frame, bg=self.colors['bg_panel'])
        status_container.pack(pady=10)
        
        self.status_indicator = tk.Label(
            status_container,
            text="●",
            font=('Arial', 40),
            fg=self.colors['error'],
            bg=self.colors['bg_panel']
        )
        self.status_indicator.pack(side=tk.LEFT, padx=10)
        
        self.status_text = tk.Label(
            status_container,
            text="OFFLINE",
            font=('Segoe UI', 18, 'bold'),
            fg=self.colors['error'],
            bg=self.colors['bg_panel']
        )
        self.status_text.pack(side=tk.LEFT)
        
        # Separator
        tk.Frame(status_frame, bg=self.colors['primary'], height=1).pack(fill=tk.X, padx=20, pady=10)
        
        # Statystyki
        stats_frame = tk.Frame(status_frame, bg=self.colors['bg_panel'])
        stats_frame.pack(fill=tk.X, padx=20, pady=10)
        
        self.create_stat_row(stats_frame, "PORT:", "8080", 0)
        self.uptime_value = self.create_stat_row(stats_frame, "UPTIME:", "00:00:00", 1)
        self.downloads_value = self.create_stat_row(stats_frame, "POBRANE:", "0", 2)
        
        # Folder pobierania
        folder_label = tk.Label(
            status_frame,
            text="FOLDER:",
            font=('Segoe UI', 10, 'bold'),
            fg=self.colors['secondary'],
            bg=self.colors['bg_panel']
        )
        folder_label.pack(anchor=tk.W, padx=20, pady=(10, 5))
        
        self.folder_display = tk.Label(
            status_frame,
            text=self.downloads_folder,
            font=('Segoe UI', 8),
            fg=self.colors['text_dim'],
            bg=self.colors['bg_panel'],
            wraplength=300,
            justify=tk.LEFT
        )
        self.folder_display.pack(anchor=tk.W, padx=20, pady=(0, 15))
        
        # ============= KONTROLKI (PRAWY DOLNY) =============
        controls_frame = tk.Frame(right_panel, bg=self.colors['bg_panel'])
        controls_frame.pack(fill=tk.BOTH, expand=True)
        
        controls_header = tk.Label(
            controls_frame,
            text="⌨️ KONSOLA",
            font=('Segoe UI', 14, 'bold'),
            fg=self.colors['primary'],
            bg=self.colors['bg_panel']
        )
        controls_header.pack(pady=(15, 20))
        
        # Duży przycisk Start/Stop
        self.main_button = tk.Button(
            controls_frame,
            text="🚀 URUCHOM SERWER",
            font=('Segoe UI', 14, 'bold'),
            fg='white',
            bg=self.colors['success'],
            activebackground=self.colors['primary'],
            activeforeground='white',
            relief=tk.FLAT,
            bd=0,
            padx=20,
            pady=15,
            cursor='hand2',
            command=self.toggle_server
        )
        self.main_button.pack(pady=10, padx=20, fill=tk.X)
        
        # Dodatkowe przyciski
        folder_btn = self.create_control_button(
            controls_frame,
            "📁 Otwórz folder",
            self.colors['secondary'],
            self.open_downloads_folder
        )
        folder_btn.pack(pady=5, padx=20, fill=tk.X)
        
        change_folder_btn = self.create_control_button(
            controls_frame,
            "📂 Zmień folder",
            self.colors['bg_lighter'],
            self.change_downloads_folder
        )
        change_folder_btn.pack(pady=5, padx=20, fill=tk.X)
        
        # Linia oddzielająca dolna
        separator2 = tk.Frame(self.root, bg=self.colors['primary'], height=2)
        separator2.pack(fill=tk.X, side=tk.BOTTOM)
        
    def create_stat_row(self, parent, label_text, value_text, row):
        """Utwórz wiersz statystyki"""
        row_frame = tk.Frame(parent, bg=self.colors['bg_panel'])
        row_frame.pack(fill=tk.X, pady=5)
        
        label = tk.Label(
            row_frame,
            text=label_text,
            font=('Segoe UI', 10, 'bold'),
            fg=self.colors['secondary'],
            bg=self.colors['bg_panel'],
            width=10,
            anchor=tk.W
        )
        label.pack(side=tk.LEFT)
        
        value = tk.Label(
            row_frame,
            text=value_text,
            font=('Segoe UI', 10),
            fg=self.colors['text'],
            bg=self.colors['bg_panel'],
            anchor=tk.W
        )
        value.pack(side=tk.LEFT)
        
        return value
    
    def create_control_button(self, parent, text, color, command):
        """Utwórz przycisk kontrolny"""
        btn = tk.Button(
            parent,
            text=text,
            font=('Segoe UI', 10),
            fg=self.colors['text'],
            bg=color,
            activebackground=self.colors['primary'],
            activeforeground='white',
            relief=tk.FLAT,
            bd=0,
            padx=15,
            pady=10,
            cursor='hand2',
            command=command
        )
        return btn
    
    def animate_startup(self):
        """Animacja startowa"""
        self.log_activity("═" * 60, 'accent')
        self.log_activity("    VIDEO DOWNLOAD ASSISTANT v2.0", 'accent')
        self.log_activity("═" * 60, 'accent')
        self.log_activity("")
        
    def check_requirements(self):
        """Sprawdź wymagania systemowe"""
        self.log_activity("🔍 Sprawdzanie zależności...", 'info')
        
        # Python
        python_version = sys.version.split()[0]
        self.log_activity(f"✅ Python {python_version}", 'success')
        
        # server.py
        if os.path.exists('server.py'):
            self.log_activity("✅ server.py znaleziony", 'success')
        else:
            self.log_activity("❌ server.py NIE znaleziony!", 'error')
        
        # yt-dlp
        try:
            result = subprocess.run(['yt-dlp', '--version'], 
                                  capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                version = result.stdout.strip()
                self.log_activity(f"✅ yt-dlp v{version}", 'success')
            else:
                self.log_activity("⚠️ yt-dlp nie działa poprawnie", 'warning')
        except:
            self.log_activity("⚠️ yt-dlp nie znaleziony", 'warning')
        
        # FFmpeg
        try:
            result = subprocess.run(['ffmpeg', '-version'], 
                                  capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                self.log_activity("✅ FFmpeg zainstalowany", 'success')
            else:
                self.log_activity("⚠️ FFmpeg nie działa poprawnie", 'warning')
        except:
            self.log_activity("⚠️ FFmpeg nie znaleziony", 'warning')
        
        self.log_activity("")
        self.log_activity("💡 Gotowy do uruchomienia serwera!", 'info')
        self.log_activity("")
    
    def log_activity(self, message, tag='info'):
        """Dodaj wpis do logu z kolorowaniem"""
        timestamp = datetime.datetime.now().strftime("%H:%M:%S")
        
        self.log_history.append({
            'time': timestamp,
            'message': message,
            'tag': tag
        })
        
        # Aktualizuj licznik
        self.log_count_label.config(text=f"({len(self.log_history)})")
        
        # Dodaj do text widget
        self.log_text.insert(tk.END, f"[{timestamp}] ", 'timestamp')
        self.log_text.insert(tk.END, f"{message}\n", tag)
        self.log_text.see(tk.END)
        
        # Parsuj dla statystyk
        if "✅ Pobieranie zakończone" in message or "Download completed" in message:
            self.downloads_count += 1
            self.downloads_value.config(text=str(self.downloads_count))
    
    def clear_logs(self):
        """Wyczyść logi"""
        self.log_text.delete(1.0, tk.END)
        self.log_history.clear()
        self.log_count_label.config(text="(0)")
        self.log_activity("✅ Pomyślnie wyczyszczono aktywność", 'success')
    
    def export_logs(self):
        """Eksportuj logi do pliku"""
        if not self.log_history:
            messagebox.showinfo(
                "Brak logów",
                "Nie ma żadnych logów do wyeksportowania."
            )
            return
        
        # Otwórz okno dialogowe do wyboru lokalizacji
        from tkinter import filedialog
        
        # Domyślna nazwa pliku z datą i czasem
        default_name = f"VDA_logs_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        
        filepath = filedialog.asksaveasfilename(
            title="Zapisz logi jako",
            defaultextension=".txt",
            initialfile=default_name,
            filetypes=[
                ("Pliki tekstowe", "*.txt"),
                ("Wszystkie pliki", "*.*")
            ]
        )
        
        if not filepath:  # Użytkownik anulował
            return
        
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                # Nagłówek
                f.write("=" * 80 + "\n")
                f.write("VIDEO DOWNLOAD ASSISTANT - ACTIVITY LOG\n")
                f.write(f"Eksport: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write(f"Liczba wpisów: {len(self.log_history)}\n")
                f.write("=" * 80 + "\n\n")
                
                # Wszystkie logi
                for log_entry in self.log_history:
                    f.write(f"[{log_entry['time']}] {log_entry['message']}\n")
                
                # Stopka
                f.write("\n" + "=" * 80 + "\n")
                f.write("Koniec logu\n")
                f.write("=" * 80 + "\n")
            
            self.log_activity(f"💾 Logi wyeksportowane: {os.path.basename(filepath)}", 'success')
            messagebox.showinfo(
                "Sukces",
                f"Logi zostały pomyślnie wyeksportowane do:\n{filepath}"
            )
        except Exception as e:
            self.log_activity(f"❌ Błąd eksportu logów: {str(e)}", 'error')
            messagebox.showerror(
                "Błąd",
                f"Nie udało się wyeksportować logów:\n{str(e)}"
            )
    
    def toggle_server(self):
        """Przełącz stan serwera"""
        if self.server_running:
            self.stop_server()
        else:
            self.start_server()
    
    def start_server(self):
        """Uruchom serwer"""
        if self.server_running:
            return
        
        self.log_activity("═" * 60, 'accent')
        self.log_activity("🚀 URUCHAMIANIE SERWERA...", 'info')
        self.log_activity("═" * 60, 'accent')
        
        # Ustaw zmienną środowiskową
        os.environ['VDA_DOWNLOADS_FOLDER'] = self.downloads_folder
        
        try:
            self.server_process = subprocess.Popen(
                [sys.executable, 'server.py'],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding='utf-8',
                errors='replace',
                bufsize=1,
                universal_newlines=True,
                cwd=os.path.dirname(os.path.abspath(__file__)) or '.'
            )
            
            self.server_running = True
            self.start_time = datetime.datetime.now()
            
            # Aktualizuj UI
            self.status_indicator.config(fg=self.colors['success'])
            self.status_text.config(text="ONLINE", fg=self.colors['success'])
            self.main_button.config(
                text="⏹️ ZATRZYMAJ SERWER",
                bg=self.colors['error']
            )
            
            self.log_activity("✅ Serwer uruchomiony na http://localhost:8080", 'success')
            self.log_activity("🔗 Rozszerzenie może się teraz połączyć", 'info')
            self.log_activity(f"📁 Folder pobierania: {self.downloads_folder}", 'info')
            self.log_activity("")
            
            # Uruchom wątki
            threading.Thread(target=self.read_server_output, daemon=True).start()
            threading.Thread(target=self.update_uptime, daemon=True).start()
            threading.Thread(target=self.animate_status, daemon=True).start()
            
        except Exception as e:
            self.log_activity(f"❌ Błąd uruchamiania: {str(e)}", 'error')
            self.server_running = False
    
    def stop_server(self):
        """Zatrzymaj serwer"""
        if not self.server_running:
            return
        
        self.manual_shutdown = True  # Oznacz że to ręczne zatrzymanie
        
        try:
            if self.server_process:
                self.log_activity("═" * 60, 'accent')
                self.log_activity("🛑 Zatrzymywanie serwera...", 'warning')
                self.server_process.terminate()
                try:
                    self.server_process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    self.server_process.kill()
                    self.server_process.wait()
        except Exception as e:
            self.log_activity(f"❌ Błąd zatrzymywania: {str(e)}", 'error')
        
        self.server_running = False
        self.server_process = None
        self.start_time = None
        
        # Aktualizuj UI
        self.status_indicator.config(fg=self.colors['error'])
        self.status_text.config(text="OFFLINE", fg=self.colors['error'])
        self.main_button.config(
            text="🚀 URUCHOM SERWER",
            bg=self.colors['success']
        )
        self.uptime_value.config(text="00:00:00")
        
        self.log_activity("🔴 Serwer zatrzymany", 'error')
        self.log_activity("═" * 60, 'accent')
        self.log_activity("")
        
        self.manual_shutdown = False  # Reset flagi
    
    def read_server_output(self):
        """Czytaj output z serwera"""
        def read_stderr():
            try:
                for line in iter(self.server_process.stderr.readline, ''):
                    if line:
                        clean_line = line.strip()
                        
                        if clean_line and ' - INFO - ' in clean_line:
                            message = clean_line.split(' - INFO - ')[-1]
                            
                            if '127.0.0.1' in message and 'HTTP' in message:
                                continue
                            
                            # Określ tag na podstawie treści
                            if 'yt-dlp:' in message:
                                ytdlp_msg = message.replace('yt-dlp: ', '')
                                if '[download]' in ytdlp_msg:
                                    if 'Destination:' in ytdlp_msg:
                                        filename = os.path.basename(ytdlp_msg.split('Destination: ')[-1])
                                        self.root.after(0, self.log_activity, f"📄 {filename}", 'download')
                                    elif '%' in ytdlp_msg and 'ETA' in ytdlp_msg:
                                        self.root.after(0, self.log_activity, f"⏳ {ytdlp_msg}", 'download')
                                    elif '100%' in ytdlp_msg:
                                        self.root.after(0, self.log_activity, f"✅ {ytdlp_msg}", 'success')
                                elif '[Merger]' in ytdlp_msg:
                                    self.root.after(0, self.log_activity, f"🔄 {ytdlp_msg}", 'accent')
                            elif 'Download completed' in message:
                                self.root.after(0, self.log_activity, "✅ Pobieranie zakończone pomyślnie!", 'success')
                            elif 'New download' in message:
                                self.root.after(0, self.log_activity, f"📥 {message}", 'info')
                            elif 'ERROR' in message:
                                self.root.after(0, self.log_activity, f"❌ {message}", 'error')
                            else:
                                self.root.after(0, self.log_activity, f"ℹ️ {message}", 'info')
                        
                        if self.server_process.poll() is not None:
                            break
            except Exception as e:
                error_msg = str(e)
                try:
                    error_msg = error_msg.encode('utf-8', errors='ignore').decode('utf-8')
                except:
                    pass
                self.root.after(0, self.log_activity, f"❌ Błąd czytania: {error_msg}", 'error')
        
        threading.Thread(target=read_stderr, daemon=True).start()
        
        self.server_process.wait()
        
        if self.server_running:
            return_code = self.server_process.returncode
            # Tylko pokaż błąd jeśli to nie było ręczne zatrzymanie
            if return_code != 0 and not self.manual_shutdown:
                self.root.after(0, self.log_activity, f"💥 Serwer zakończył z błędem: {return_code}", 'error')
            
            self.root.after(0, self.stop_server)
    
    def update_uptime(self):
        """Aktualizuj czas działania"""
        while True:
            if self.server_running and self.start_time:
                elapsed = datetime.datetime.now() - self.start_time
                hours, remainder = divmod(int(elapsed.total_seconds()), 3600)
                minutes, seconds = divmod(remainder, 60)
                uptime = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
                self.root.after(0, self.uptime_value.config, {'text': uptime})
            time.sleep(1)
    
    def animate_status(self):
        """Animuj status indicator (pulsowanie)"""
        colors = [self.colors['success'], self.colors['primary'], self.colors['glow']]
        index = 0
        while True:
            if self.server_running:
                self.root.after(0, self.status_indicator.config, {'fg': colors[index % len(colors)]})
                index += 1
            time.sleep(0.5)
    
    def open_downloads_folder(self):
        """Otwórz folder pobierania"""
        import platform
        try:
            if platform.system() == "Windows":
                os.startfile(self.downloads_folder)
            elif platform.system() == "Darwin":
                subprocess.Popen(["open", self.downloads_folder])
            else:
                subprocess.Popen(["xdg-open", self.downloads_folder])
            self.log_activity(f"📁 Otwarto folder: {self.downloads_folder}", 'info')
        except Exception as e:
            self.log_activity(f"❌ Nie można otworzyć folderu: {str(e)}", 'error')
    
    def change_downloads_folder(self):
        """Zmień folder pobierania"""
        new_folder = filedialog.askdirectory(
            title="Wybierz folder pobierania",
            initialdir=self.downloads_folder
        )
        
        if new_folder:
            self.downloads_folder = new_folder
            self.folder_display.config(text=new_folder)
            self.save_settings()
            self.log_activity(f"📂 Zmieniono folder na: {new_folder}", 'success')
            
            if self.server_running:
                self.log_activity("⚠️ Zrestartuj serwer aby zmiany zostały zastosowane", 'warning')
    
    def on_closing(self):
        """Obsługa zamknięcia okna"""
        if self.server_running:
            if messagebox.askokcancel("Wyjście", "Serwer jest uruchomiony. Zatrzymać serwer i wyjść?"):
                self.stop_server()
                self.root.destroy()
        else:
            self.root.destroy()
    
    def run(self):
        """Uruchom aplikację"""
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        self.root.mainloop()


def main():
    """Główny punkt wejścia"""
    if not os.path.exists('server.py'):
        messagebox.showerror(
            "Błąd",
            "server.py nie znaleziony!\n\nUpewnij się, że oba pliki są w tym samym folderze."
        )
        sys.exit(1)
    
    app = FuturisticServerGUI()
    app.run()


if __name__ == '__main__':
    main()