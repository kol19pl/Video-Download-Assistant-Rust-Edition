#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Video Download Assistant Local Server
Obsługuje komunikację między rozszerzeniem przeglądarki a yt-dlp
versja koncepcji kolejki by kol19pl
"""

import json
import os
import subprocess
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from socketserver import ThreadingMixIn
from urllib.parse import urlparse
import shutil
import logging
import queue
import io

# Ustaw kodowanie UTF-8 dla Windows
if sys.platform == 'win32':
    try:
        import ctypes
        kernel32 = ctypes.windll.kernel32
        kernel32.SetConsoleOutputCP(65001)
        kernel32.SetConsoleCP(65001)
    except:
        pass

# Ustaw stderr na UTF-8
if sys.stderr.encoding != 'utf-8':
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')
if sys.stdout.encoding != 'utf-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

YTDLP_STATUS = None

# Globalna kolejka pobierania
DOWNLOAD_QUEUE = queue.Queue()
JOB_COUNTER = 0
JOB_COUNTER_LOCK = threading.Lock()
DOWNLOAD_WORKER_STARTED = False

# Konfiguracja logowania z UTF-8
logging.basicConfig(
    level=logging.INFO, 
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stderr)
    ]
)
logger = logging.getLogger(__name__)

# Globalna kolejka do komunikacji z GUI
gui_queue = None

def mask_password(password):
    """Zamień hasło na gwiazdki dla bezpieczeństwa w logach"""
    if password and len(password) > 0:
        return "****"
    return ""

def check_ytdlp_once():
    """Sprawdź yt-dlp raz przy starcie"""
    global YTDLP_STATUS
    try:
        result = subprocess.run(['yt-dlp', '--version'], 
                              capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            YTDLP_STATUS = {
                'installed': True,
                'version': result.stdout.strip(),
                'message': f'yt-dlp wersja {result.stdout.strip()} jest zainstalowany'
            }
        else:
            YTDLP_STATUS = {
                'installed': False,
                'error': 'command_failed',
                'message': 'yt-dlp nie działa poprawnie'
            }
    except:
        YTDLP_STATUS = {
            'installed': False,
            'error': 'not_found',
            'message': 'yt-dlp nie jest zainstalowany'
        }

def set_gui_queue(q):
    """Ustaw kolejkę GUI do komunikacji"""
    global gui_queue
    gui_queue = q

def send_to_gui(message):
    """Wyślij wiadomość do GUI jeśli dostępne"""
    global gui_queue
    if gui_queue:
        try:
            gui_queue.put(message)
        except:
            pass


def _download_worker_loop():
    """Wątek obsługujący kolejkę pobierania.

    Każde zadanie w kolejce wywołuje metodę _download_video danego handlera.
    Dzięki temu pobrania są wykonywane jedno po drugim, ale serwer HTTP
    pozostaje responsywny (każde żądanie HTTP działa w osobnym wątku).
    """
    global DOWNLOAD_QUEUE

    while True:
        task = DOWNLOAD_QUEUE.get()
        handler = task.get('handler')
        args = task.get('args', ())
        event = task.get('event')
        job_id = task.get('job_id')

        try:
            if job_id is not None:
                send_to_gui(f"🚀 Start pobierania #{job_id}")
                logger.info(f"Start pobierania #{job_id}")
            if handler is not None:
                # _download_video wysyła odpowiedź HTTP do klienta
                handler._download_video(*args)
        except Exception as e:
            error_msg = f"❌ Błąd wątku pobierania #{job_id}: {str(e)}"
            logger.error(error_msg)
            send_to_gui(error_msg)
        finally:
            if event is not None:
                event.set()
            DOWNLOAD_QUEUE.task_done()


def start_download_worker():
    """Uruchom wątek obsługujący globalną kolejkę pobierania (tylko raz)."""
    global DOWNLOAD_WORKER_STARTED
    if DOWNLOAD_WORKER_STARTED:
        return

    DOWNLOAD_WORKER_STARTED = True
    worker = threading.Thread(target=_download_worker_loop, daemon=True)
    worker.start()
    logger.info("Uruchomiono wątek kolejki pobierania")


class VideoDownloadHandler(BaseHTTPRequestHandler):
    def _set_cors_headers(self):
        """Ustaw nagłówki CORS aby umożliwić komunikację z rozszerzeniem"""
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')

    def _send_json_response(self, data, status_code=200):
        """Wyślij odpowiedź JSON z odpowiednimi nagłówkami"""
        self.send_response(status_code)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self._set_cors_headers()
        self.end_headers()
        
        response = json.dumps(data, ensure_ascii=False, indent=2)
        self.wfile.write(response.encode('utf-8'))

    def do_OPTIONS(self):
        """Obsługa żądań preflight"""
        self.send_response(200)
        self._set_cors_headers()
        self.end_headers()

    def do_GET(self):
        """Obsługa żądań GET"""
        parsed_path = urlparse(self.path)
        path = parsed_path.path
        
        if path == '/_status':
            self._handle_status()
        elif path == '/check-ytdlp':
            self._handle_check_ytdlp()
        else:
            self._send_json_response({'error': 'Nie znaleziono'}, 404)

    def do_POST(self):
        """Obsługa żądań POST"""
        parsed_path = urlparse(self.path)
        path = parsed_path.path
        
        if path == '/download':
            self._handle_download()
        elif path == '/verify-premium':
            self._handle_verify_premium()
        else:
            self._send_json_response({'error': 'Nie znaleziono'}, 404)

    def _handle_status(self):
        """Sprawdź czy serwer działa"""
        downloads_folder = os.environ.get('VDA_DOWNLOADS_FOLDER', os.path.join(os.path.expanduser("~"), "Downloads"))
        self._send_json_response({
            '_status': 'running',
            'version': '1.0.0',
            'timestamp': time.time(),
            'downloads_folder': downloads_folder
        })

    def _handle_check_ytdlp(self):
        """Zwróć cached _status yt-dlp"""
        try:
            global YTDLP_STATUS
            if YTDLP_STATUS is None:
                check_ytdlp_once()
            self._send_json_response(YTDLP_STATUS)
        except (ConnectionAbortedError, BrokenPipeError, ConnectionResetError):
            # Klient przerwał połączenie - to normalne, ignoruj
            logger.debug("Klient przerwał połączenie podczas sprawdzania yt-dlp")
        except Exception as e:
            logger.error(f'Błąd sprawdzania yt-dlp: {str(e)}')
            
    def _clean_filename(self, filename):
        """Oczyść nazwę pliku dla bezpiecznego użycia w systemie plików"""
        import re
        
        # Zamień niedozwolone znaki
        filename = re.sub(r'[<>:"/\|?*]', '_', filename)
        
        # Usuń wielokrotne spacje i podkreślniki
        filename = re.sub(r'[s_]+', '_', filename)
        
        # Usuń znaki z początku i końca
        filename = filename.strip('_. ')
        
        # Ogranicz długość
        if len(filename) > 100:
            filename = filename[:100]
        
        # Upewnij się, że nie jest pusty
        if not filename:
            filename = "Unknown_Video"
        
        return filename        

    def _handle_verify_premium(self):
        """Weryfikacja konta Premium CDA.pl"""
        try:
            content_length = int(self.headers.get('Content-Length', 0))
            if content_length == 0:
                self._send_json_response({'success': False, 'error': 'Nie podano danych'}, 400)
                return
            
            post_data = self.rfile.read(content_length)
            try:
                data = json.loads(post_data.decode('utf-8'))
            except json.JSONDecodeError:
                self._send_json_response({'success': False, 'error': 'Nieprawidłowe dane JSON'}, 400)
                return

            username = data.get('username')
            password = data.get('password')
            
            if not username or not password:
                self._send_json_response({'success': False, 'error': 'Brak danych logowania'}, 400)
                return
            
            masked_password = mask_password(password)
            send_to_gui(f"🔐 Weryfikacja konta Premium dla: {username}")
            logger.info(f"🔐 Weryfikacja konta Premium - użytkownik: {username} (hasło: {masked_password})")
            
            # Test logowania przez yt-dlp
            cmd = [
                'yt-dlp',
                '--username', username,
                '--password', password,
                '--dump-json',
                '--playlist-items', '0',
                '--no-download',
                'https://www.cda.pl'
            ]
            
            try:
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=30
                )
                
                if result.returncode == 0:
                    success_msg = "✅ Dane logowania są poprawne"
                    logger.info(success_msg)
                    send_to_gui(success_msg)
                    send_to_gui("⚠️ Uwaga: Status Premium zostanie sprawdzony podczas próby pobrania filmu Premium")
                    self._send_json_response({
                        'success': True,
                        'is_premium': None,  # Nieznane - wymaga testu na filmie Premium
                        'message': 'Dane logowania poprawne (_status Premium nieznany)'
                    })
                else:
                    error_msg = f"❌ Nieprawidłowe dane logowania"
                    logger.error(error_msg)
                    send_to_gui(error_msg)
                    self._send_json_response({
                        'success': False,
                        'error': 'Nieprawidłowe dane logowania'
                    })
                    
            except subprocess.TimeoutExpired:
                error_msg = "⏱️ Przekroczono czas oczekiwania weryfikacji"
                logger.error(error_msg)
                send_to_gui(error_msg)
                self._send_json_response({
                    'success': False,
                    'error': 'Przekroczono czas oczekiwania'
                })
                
        except Exception as e:
            error_msg = f"❌ Błąd weryfikacji Premium: {str(e)}"
            logger.error(error_msg)
            send_to_gui(error_msg)
            self._send_json_response({
                'success': False,
                'error': str(e)
            }, 500)

    def _handle_download(self):
        """Obsługa żądania pobierania wideo"""
        try:
            content_length = int(self.headers.get('Content-Length', 0))
            if content_length == 0:
                self._send_json_response({'success': False, 'error': 'Nie podano danych'}, 400)
                return
            
            post_data = self.rfile.read(content_length)
            try:
                data = json.loads(post_data.decode('utf-8'))
            except json.JSONDecodeError:
                self._send_json_response({'success': False, 'error': 'Nieprawidłowe dane JSON'}, 400)
                return

            if 'url' not in data:
                self._send_json_response({'success': False, 'error': 'URL jest wymagany'}, 400)
                return

            url = data['url']
            quality = data.get('quality', 'best')
            format_selector = data.get('format', 'mp4')
            
            # Loguj otrzymane parametry
            logger.info(f"📥 Otrzymano żądanie pobierania:")
            logger.info(f"   URL: {url}")
            logger.info(f"   Jakość: {quality}")
            logger.info(f"   Format: {format_selector}")
            send_to_gui(f"📥 Format: {format_selector}, Jakość: {quality}")
            
            # Pobierz dane Premium jeśli dostępne
            username = data.get('username')
            password = data.get('password')
            has_premium = bool(username and password)
            
            if has_premium:
                masked_password = mask_password(password)
                send_to_gui(f"👑 Pobieranie z kontem Premium użytkownika: {username}")
                logger.info(f"👑 Pobieranie Premium dla użytkownika: {username} (hasło: {masked_password})")
            
            # NOWA LOGIKA: Pobierz główny folder z GUI
            base_folder = os.environ.get('VDA_DOWNLOADS_FOLDER')
            if not base_folder:
                base_folder = os.path.join(os.path.expanduser("~"), "Downloads")
            
            # Pobierz subfolder z rozszerzenia (jeśli podany)
            subfolder = data.get('subfolder', '')
            
            # ZŁÓŻ pełną ścieżkę: bazowy_folder/subfolder
            if subfolder:
                output_path = os.path.join(base_folder, subfolder)
                send_to_gui(f"📂 Używam podfolderu: {output_path}")
                logger.info(f"Używam podfolderu: {output_path}")
            else:
                output_path = base_folder
            
            send_to_gui(f"📁 Folder docelowy: {output_path}")
            logger.info(f"Folder docelowy: {output_path}")
            
            # Pobierz własny tytuł jeśli jest dostępny
            custom_title = data.get('title')
            
            # Dodaj zadanie do globalnej kolejki pobierania
            global DOWNLOAD_QUEUE, JOB_COUNTER, JOB_COUNTER_LOCK

            with JOB_COUNTER_LOCK:
                JOB_COUNTER += 1
                job_id = JOB_COUNTER

            done_event = threading.Event()
            task = {
                'handler': self,
                'args': (url, quality, format_selector, output_path, custom_title, username, password),
                'event': done_event,
                'job_id': job_id,
            }

            try:
                DOWNLOAD_QUEUE.put(task)
                queue_position = DOWNLOAD_QUEUE.qsize()
                send_to_gui(f"📥 Dodano pobieranie #{job_id} do kolejki (pozycja: {queue_position})")
                logger.info(f"Dodano pobieranie #{job_id} do kolejki (pozycja: {queue_position})")
            except Exception as e:
                error_msg = f"❌ Nie udało się dodać zadania do kolejki: {str(e)}"
                logger.error(error_msg)
                send_to_gui(error_msg)
                self._send_json_response({
                    'success': False,
                    'error': 'Nie udało się dodać zadania do kolejki'
                }, 500)
                return

            # Czekaj, aż zadanie zostanie obsłużone przez wątek kolejki, który
            # wywoła _download_video i wyśle odpowiedź HTTP do klienta.
            done_event.wait()
                    
        except Exception as e:
            error_msg = f"❌ Błąd podczas pobierania wideo: {str(e)}"
            logger.error(error_msg)
            send_to_gui(error_msg)
            self._send_json_response({
                'success': False,
                'error': str(e)
            }, 500)

    def _download_video(self, url, quality, format_selector, output_path, custom_title=None, username=None, password=None):
        """Pobierz wideo używając yt-dlp"""
        try:
            # Określ czy mamy dane Premium
            has_premium = bool(username and password)
            
            # POPRAWKA: Używaj bezpośrednio przekazanego output_path
            os.makedirs(output_path, exist_ok=True)
            logger.info(f"Używam folderu pobierania: {output_path}")
            send_to_gui(f"📁 Używam folderu pobierania: {output_path}")
            
            # Określ czy potrzebna będzie konwersja po pobraniu
            needs_conversion = False
            target_format = format_selector
            downloaded_file = None
            
            cmd = ['yt-dlp']
            
            # ZAWSZE pobieraj pełny plik wideo jako MP4
            # Konwersja do MP3 będzie wykonana PÓŹNIEJ przez ffmpeg
            if quality == 'best':
                cmd.extend(['-f', 'bestvideo+bestaudio/best'])
            elif quality == 'worst':
                cmd.extend(['-f', 'worstvideo+bestaudio/worst'])
            elif quality == 'bestaudio':
                # Nawet dla bestaudio pobierz normalny plik
                cmd.extend(['-f', 'bestvideo+bestaudio/best'])
            elif quality == 'best[height<=720]':
                cmd.extend(['-f', 'bestvideo[height<=720]+bestaudio/best[height<=720]'])
            elif quality == 'best[height<=480]':
                cmd.extend(['-f', 'bestvideo[height<=480]+bestaudio/best[height<=480]'])
            else:
                cmd.extend(['-f', quality])
            
            # Zawsze pobieraj jako mp4 najpierw
            cmd.extend(['--merge-output-format', 'mp4'])
            
            # Jeśli użytkownik chce inny format niż mp4, będziemy konwertować później
            if format_selector in ['mkv', 'webm', 'mp3']:
                needs_conversion = True
                if format_selector == 'mp3':
                    send_to_gui(f"🔄 Po pobraniu zostanie wykonana konwersja do MP3 (audio)")
                else:
                    send_to_gui(f"🔄 Po pobraniu zostanie wykonana konwersja do {format_selector.upper()}")
            
            # ========== KRYTYCZNE DLA DASH - WYMUSZENIE ŁĄCZENIA ==========
            cmd.extend([
                '--no-part',
                '--remux-video', 'mp4',
                '--no-keep-fragments',
                '--fixup', 'detect_or_warn',
                '--postprocessor-args', 'ffmpeg:-movflags +faststart',
                '--concurrent-fragments', '10',
                '--retries', '10',
                '--fragment-retries', '10'
            ])
            # ===============================================================
            
            cmd.extend([
                '--no-playlist',
                '--no-write-info-json',
                '--no-write-thumbnail',
                '--no-write-description',
                '--no-write-annotations',
                '--no-write-auto-sub',
                '--no-write-sub',
                '--no-embed-thumbnail',
                '--add-metadata',
                '--no-warnings'
            ])

            # Użyj własnego tytułu jeśli jest dostępny
            if custom_title:
                # Oczyść tytuł dla nazwy pliku
                clean_title = self._clean_filename(custom_title)
                output_template = os.path.join(output_path, f'{clean_title}.%(ext)s')
                send_to_gui(f"📋 Używam własnego tytułu: {clean_title}")
            else:
                # Użyj domyślnego szablonu yt-dlp
                output_template = os.path.join(output_path, '%(title)s.%(ext)s')
            
            cmd.extend(['-o', output_template])
            
            if has_premium:
                cmd.extend(['--username', username])
                cmd.extend(['--password', password])
                send_to_gui("👑 Używam konta Premium do pobierania")
            
            cmd.append(url)

            send_to_gui(f"🚀 Rozpoczynam pobieranie...")
            logger.info(f"🚀 Rozpoczynam pobieranie z URL: {url}")

            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                universal_newlines=True
            )

            # Parsuj wyjście yt-dlp i wyślij do GUI
            for line in process.stdout:
                line = line.strip()
                if line:
                    logger.info(f"yt-dlp: {line}")
                    
                    # Parsuj informacje o postępie
                    if '[download]' in line:
                        if 'Destination:' in line:
                            filename = line.split('Destination: ')[-1]
                            downloaded_file = filename
                            logger.info(f"📌 Zapisano nazwę pliku: {downloaded_file}")
                            send_to_gui(f"📄 Plik: {os.path.basename(filename)}")
                        elif '%' in line and 'ETA' in line:
                            # Wyodrębnij procent postępu
                            parts = line.split()
                            for part in parts:
                                if '%' in part:
                                    send_to_gui(f"⏳ Postęp: {part}")
                                    break
                        elif 'has already been downloaded' in line:
                            send_to_gui("ℹ️ Plik już istnieje - pomijam")
                        else:
                            send_to_gui(f"📥 {line}")
                    elif '[Merger]' in line and 'Merging formats into' in line:
                        # Wyciągnij nazwę pliku po merge
                        if '"' in line:
                            parts = line.split('"')
                            if len(parts) >= 2:
                                downloaded_file = parts[1]
                                logger.info(f"📌 Zaktualizowano nazwę pliku po merge: {downloaded_file}")
                        send_to_gui(f"🔄 Łączę: {line}")
                    elif '[ExtractAudio]' in line:
                        send_to_gui(f"🎵 Konwertuję audio: {line}")
                    elif 'ERROR' in line.upper():
                        send_to_gui(f"❌ Błąd: {line}")
                    else:
                        # Inne wyjście yt-dlp
                        if line and not line.startswith('['):
                            send_to_gui(f"ℹ️ {line}")

            return_code = process.wait()

            if return_code == 0:
                success_msg = f"✅ Pobieranie zakończone pomyślnie!"
                logger.info(success_msg)
                send_to_gui(success_msg)
                
                # Loguj stan konwersji
                logger.info(f"🔍 Sprawdzanie możliwości konwersji - format docelowy: {target_format}")
                logger.info(f"📁 Pobrany plik (z yt-dlp): {downloaded_file}")
                
                # Jeśli potrzebna konwersja, użyj pobranego pliku
                actual_downloaded_file = None
                if needs_conversion:
                    try:
                        # Użyj downloaded_file który został ustawiony przez yt-dlp
                        if downloaded_file and os.path.exists(downloaded_file):
                            actual_downloaded_file = downloaded_file
                            logger.info(f"✅ Używam pliku z yt-dlp: {actual_downloaded_file}")
                            send_to_gui(f"✅ Znaleziono plik: {os.path.basename(actual_downloaded_file)}")
                        else:
                            # Fallback: szukaj najnowszego pliku .mp4
                            search_ext = '.mp4'
                            send_to_gui(f"🔍 Wyszukiwanie pobranego pliku MP4 do konwersji...")
                            
                            # Lista wszystkich plików z odpowiednim rozszerzeniem
                            files = [f for f in os.listdir(output_path) if f.endswith(search_ext)]
                            
                            if files:
                                # Sortuj po czasie utworzenia (najnowszy pierwszy)
                                files_with_time = [(f, os.path.getctime(os.path.join(output_path, f))) for f in files]
                                files_with_time.sort(key=lambda x: x[1], reverse=True)
                                
                                # Weź najnowszy plik
                                newest_file = files_with_time[0][0]
                                actual_downloaded_file = os.path.join(output_path, newest_file)
                                logger.info(f"Znaleziono plik do konwersji: {actual_downloaded_file}")
                                
                                if os.path.exists(actual_downloaded_file):
                                    send_to_gui(f"✅ Znaleziono plik: {os.path.basename(actual_downloaded_file)}")
                                else:
                                    logger.warning(f"Błąd: plik nie istnieje: {actual_downloaded_file}")
                                    actual_downloaded_file = None
                            else:
                                logger.warning(f"Nie znaleziono plików {search_ext} w {output_path}")
                                send_to_gui(f"⚠️ Nie znaleziono pliku MP4 do konwersji")
                    except Exception as e:
                        logger.error(f"Błąd podczas wyszukiwania pliku: {str(e)}")
                        send_to_gui(f"⚠️ Błąd wyszukiwania pliku: {str(e)}")
                
                # Jeśli potrzebna konwersja formatu
                if needs_conversion and actual_downloaded_file and os.path.exists(actual_downloaded_file):
                    try:
                        send_to_gui(f"🔄 Rozpoczynam konwersję do {target_format.upper()}...")
                        logger.info(f"Rozpoczynam konwersję {actual_downloaded_file} do {target_format}")
                        
                        # Sprawdź czy ffmpeg jest dostępny
                        if not shutil.which('ffmpeg'):
                            send_to_gui("⚠️ FFmpeg nie jest dostępny - pomijam konwersję")
                            logger.warning("FFmpeg nie znaleziony - pomijam konwersję")
                        else:
                            # Przygotuj nazwę pliku wyjściowego
                            base_name = os.path.splitext(actual_downloaded_file)[0]
                            output_file = f"{base_name}.{target_format}"
                            
                            # Komenda ffmpeg do konwersji
                            if target_format == 'mp3':
                                # Konwersja do MP3 - wyciągnij audio
                                ffmpeg_cmd = [
                                    'ffmpeg',
                                    '-i', actual_downloaded_file,
                                    '-vn',  # Bez video
                                    '-acodec', 'libmp3lame',  # Kodek MP3
                                    '-q:a', '2',  # Jakość audio (0-9, gdzie 0 to najlepsza)
                                    '-y',  # Nadpisz jeśli istnieje
                                    output_file
                                ]
                            else:
                                # Konwersja formatu kontenera (mkv, webm)
                                ffmpeg_cmd = [
                                    'ffmpeg',
                                    '-i', actual_downloaded_file,
                                    '-c', 'copy',  # Kopiuj strumienie bez rekodowania
                                    '-movflags', '+faststart',
                                    '-y',  # Nadpisz jeśli istnieje
                                    output_file
                                ]
                            
                            logger.info(f"Wykonuję: {' '.join(ffmpeg_cmd)}")
                            
                            # Uruchom konwersję
                            ffmpeg_process = subprocess.Popen(
                                ffmpeg_cmd,
                                stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE,
                                text=True
                            )
                            
                            _, ffmpeg_stderr = ffmpeg_process.communicate()
                            
                            if ffmpeg_process.returncode == 0:
                                send_to_gui(f"✅ Konwersja zakończona pomyślnie!")
                                logger.info(f"Konwersja zakończona: {output_file}")
                                
                                # Usuń oryginalny plik mp4
                                try:
                                    os.remove(actual_downloaded_file)
                                    send_to_gui(f"🗑️ Usunięto oryginalny plik MP4")
                                    logger.info(f"Usunięto oryginalny plik: {actual_downloaded_file}")
                                except Exception as e:
                                    logger.warning(f"Nie udało się usunąć oryginalnego pliku: {e}")
                                
                                send_to_gui(f"📁 Zapisano jako: {os.path.basename(output_file)}")
                            else:
                                send_to_gui(f"⚠️ Konwersja nie powiodła się")
                                logger.error(f"Błąd konwersji ffmpeg: {ffmpeg_stderr}")
                                send_to_gui(f"ℹ️ Plik pozostał w formacie MP4")
                    except Exception as e:
                        logger.error(f"Błąd podczas konwersji: {str(e)}")
                        send_to_gui(f"⚠️ Błąd konwersji: {str(e)}")
                        send_to_gui(f"ℹ️ Plik pozostał w formacie MP4")
                else:
                    # Loguj dlaczego konwersja nie została wykonana
                    if not needs_conversion:
                        logger.info("Konwersja nie jest potrzebna - plik już w wybranym formacie")
                    elif not actual_downloaded_file:
                        logger.warning("Nie znaleziono pobranego pliku - pomijam konwersję")
                        send_to_gui("⚠️ Nie można wykonać konwersji - nie znaleziono pliku")
                    elif not os.path.exists(actual_downloaded_file):
                        logger.warning(f"Plik nie istnieje: {actual_downloaded_file}")
                        send_to_gui(f"⚠️ Błąd konwersji - plik nie istnieje")
                
                send_to_gui(f"📁 Zapisano do: {output_path}")
                
                # Zwróć sukces do rozszerzenia
                self._send_json_response({
                    'success': True,
                    'message': 'Pobieranie zakończone pomyślnie',
                    'output_path': output_path
                })
            else:
                error_msg = f"❌ Pobieranie nie powiodło się z kodem {return_code}"
                logger.error(error_msg)
                send_to_gui(error_msg)
                
                # Sprawdź czy błąd dotyczy Premium
                # (yt-dlp nie zawsze zwraca czytelny komunikat, więc to może nie zadziałać idealnie)
                self._send_json_response({
                    'success': False,
                    'error': f'Pobieranie nie powiodło się (kod: {return_code})',
                    'requiresPremium': False  # Możesz dodać logikę wykrywania z stderr
                })

        except Exception as e:
            error_msg = f"❌ Błąd podczas pobierania wideo: {str(e)}"
            logger.error(error_msg)
            send_to_gui(error_msg)
            self._send_json_response({
                'success': False,
                'error': str(e)
            }, 500)

    def log_message(self, format, *args):
        """Nadpisz aby używać naszego loggera"""
        logger.info(f"{self.address_string()} - {format % args}")


class ThreadingHTTPServer(ThreadingMixIn, HTTPServer):
    """HTTPServer, który obsługuje każde żądanie w osobnym wątku."""
    daemon_threads = True


class VideoDownloadServer:
    def __init__(self, port=8080):
        self.port = port
        self.server = None

    def start(self):
        """Uruchom serwer HTTP"""
        try:
            downloads_folder = os.environ.get('VDA_DOWNLOADS_FOLDER', os.path.join(os.path.expanduser("~"), "Downloads"))
            
            # Użyj serwera wielowątkowego, aby każde żądanie było obsługiwane
            # w osobnym wątku i nie blokowało innych żądań HTTP.
            self.server = ThreadingHTTPServer(('localhost', self.port), VideoDownloadHandler)
            logger.info(f"Video Download Assistant Server uruchamia się na http://localhost:{self.port}")
            send_to_gui(f"🚀 Serwer uruchomiony na http://localhost:{self.port}")
            send_to_gui("🔗 Rozszerzenie może teraz połączyć się z serwerem")
            send_to_gui(f"📁 Folder pobierania: {downloads_folder}")
            
            self._check_ytdlp_installation()
            
            # Sprawdź yt-dlp raz przy starcie
            check_ytdlp_once()

            # Uruchom wątek obsługujący kolejkę pobierania
            start_download_worker()
            
            self.server.serve_forever()
            
        except KeyboardInterrupt:
            logger.info("Serwer zatrzymany przez użytkownika")
            send_to_gui("🛑 Serwer zatrzymany przez użytkownika")
            self.stop()
        except OSError as e:
            if e.errno == 98 or "Address already in use" in str(e):
                error_msg = f"❌ Port {self.port} jest już używany. Proszę wybrać inny port."
                logger.error(error_msg)
                send_to_gui(error_msg)
            else:
                error_msg = f"❌ Nie udało się uruchomić serwera: {str(e)}"
                logger.error(error_msg)
                send_to_gui(error_msg)
        except Exception as e:
            error_msg = f"❌ Nieoczekiwany błąd: {str(e)}"
            logger.error(error_msg)
            send_to_gui(error_msg)

    def stop(self):
        """Zatrzymaj serwer HTTP"""
        if self.server:
            logger.info("Zamykam serwer...")
            send_to_gui("🛑 Zamykam serwer...")
            self.server.shutdown()
            self.server.server_close()

    def _check_ytdlp_installation(self):
        """Sprawdź instalację yt-dlp przy uruchomieniu"""
        if shutil.which('yt-dlp'):
            try:
                result = subprocess.run(['yt-dlp', '--version'], capture_output=True, text=True, timeout=5)
                if result.returncode == 0:
                    version = result.stdout.strip()
                    success_msg = f"✅ yt-dlp jest zainstalowany: wersja {version}"
                    logger.info(success_msg)
                    send_to_gui(success_msg)
                else:
                    warning_msg = "⚠️ yt-dlp jest zainstalowany ale nie działa poprawnie"
                    logger.warning(warning_msg)
                    send_to_gui(warning_msg)
            except Exception as e:
                error_msg = f"⚠️ Błąd sprawdzania wersji yt-dlp: {str(e)}"
                logger.warning(error_msg)
                send_to_gui(error_msg)
        else:
            warning_msg = "⚠️ yt-dlp nie jest zainstalowany lub nie znajduje się w PATH"
            logger.warning(warning_msg)
            send_to_gui(warning_msg)
            send_to_gui("💡 Proszę zainstalować yt-dlp używając: pip install yt-dlp")


def main():
    """Główny punkt wejścia"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Video Download Assistant Local Server')
    parser.add_argument('--port', type=int, default=8080, 
                        help='Port do uruchomienia serwera (domyślnie: 8080)')
    parser.add_argument('--verbose', '-v', action='store_true',
                        help='Włącz szczegółowe logowanie')
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    if not (1 <= args.port <= 65535):
        logger.error("Port musi być między 1 a 65535")
        sys.exit(1)
    
    server = VideoDownloadServer(port=args.port)
    
    try:
        server.start()
    except KeyboardInterrupt:
        logger.info("Serwer zatrzymany przez użytkownika")
    except Exception as e:
        logger.error(f"Nie udało się uruchomić serwera: {str(e)}")
        sys.exit(1)


if __name__ == '__main__':
    main()