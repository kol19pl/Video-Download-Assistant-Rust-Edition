use actix_cors::Cors;
use actix_web::{web, App, HttpResponse, HttpServer, Responder};
use once_cell::sync::{Lazy, OnceCell};
use serde::{Deserialize, Serialize};
use std::env;
use std::fs;
use std::io::{BufRead, BufReader};
use std::path::{Path, PathBuf};
use std::process::{Command, Stdio};
use std::sync::atomic::{AtomicU64, AtomicUsize, Ordering};
use time::OffsetDateTime;
use tokio::sync::{mpsc, oneshot};
use std::sync::{Arc, Mutex};
use serde_json;
#[allow(unused_imports)]
use std::io::{self, Write};
#[cfg(target_family = "unix")]
use std::os::unix::fs::PermissionsExt;


static QUEUE_FILE: &str = "download_queue.json";

static YTDLP_STATUS: OnceCell<YtDlpStatus> = OnceCell::new();
static QUEUE_LEN: Lazy<AtomicUsize> = Lazy::new(|| AtomicUsize::new(0));

fn log_info(msg: &str) {
    let now = OffsetDateTime::now_local().unwrap_or_else(|_| OffsetDateTime::now_utc());
    eprintln!("{now} - INFO - {msg}");
}

fn log_error(msg: &str) {
    let now = OffsetDateTime::now_local().unwrap_or_else(|_| OffsetDateTime::now_utc());
    eprintln!("{now} - ERROR - {msg}");
}

#[derive(Serialize, Clone)]
struct StatusResponse {
    status: &'static str,
    version: &'static str,
    timestamp: f64,
    downloads_folder: String,
}

#[derive(Serialize, Clone)]
struct YtDlpStatus {
    installed: bool,
    #[serde(skip_serializing_if = "Option::is_none")]
    version: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    error: Option<String>,
    message: String,
}

#[derive(Deserialize, Clone)]
struct DownloadRequest {
    url: String,
    #[serde(default)]
    quality: Option<String>,
    #[serde(default)]
    format: Option<String>,
    #[serde(default)]
    subfolder: Option<String>,
    #[serde(default)]
    title: Option<String>,
    #[serde(default)]
    username: Option<String>,
    #[serde(default)]
    password: Option<String>,
}

#[derive(Serialize)]
struct DownloadResponse {
    success: bool,
    #[serde(skip_serializing_if = "Option::is_none")]
    message: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    error: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    output_path: Option<String>,
}

#[derive(Deserialize)]
struct VerifyPremiumRequest {
    username: Option<String>,
    password: Option<String>,
}

#[derive(Serialize)]
struct VerifyPremiumResponse {
    success: bool,
    #[serde(skip_serializing_if = "Option::is_none")]
    is_premium: Option<bool>,
    #[serde(skip_serializing_if = "Option::is_none")]
    message: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    error: Option<String>,
}

#[derive(Serialize, Deserialize, Clone)]
struct DownloadQueueItem {
    url: String,
    quality: String,
    format_selector: String,
    subfolder: String,
    title: Option<String>,
    username: Option<String>,
    password: Option<String>,
}



struct JobResult {
    success: bool,
    http_status: u16,
    message: Option<String>,
    error: Option<String>,
    output_path: Option<String>,
}

struct DownloadJob {
    id: u64,
    params: DownloadParams,
    resp_tx: oneshot::Sender<JobResult>,
}

#[derive(Clone)]
struct DownloadParams {
    url: String,
    quality: String,
    format_selector: String,
    output_path: PathBuf,
    custom_title: Option<String>,
    username: Option<String>,
    password: Option<String>,
}

static YTDLP_PATH: Lazy<String> = Lazy::new(|| {
    if cfg!(target_os = "linux") && !Command::new("yt-dlp").output().is_ok() {
        "./bin/yt-dlp".into()
    } else {
        "yt-dlp".into()
    }
});



fn downloads_folder() -> String {
    if let Ok(v) = env::var("VDA_DOWNLOADS_FOLDER") {
        if !v.is_empty() {
            return v;
        }
    }
    if let Some(home) = dirs::home_dir() {
        return home.join("Downloads").to_string_lossy().to_string();
    }
    "Downloads".to_string()
}

fn current_unix_time_f64() -> f64 {
    use std::time::{SystemTime, UNIX_EPOCH};
    let now = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .unwrap_or_default();
    now.as_secs() as f64 + f64::from(now.subsec_nanos()) / 1_000_000_000.0
}

fn check_ytdlp_once() -> &'static YtDlpStatus {
    YTDLP_STATUS.get_or_init(|| {
        log_info("Sprawdzam yt-dlp...");
        match Command::new("yt-dlp")
            .arg("--version")
            .stdout(Stdio::piped())
            .stderr(Stdio::null())
            .output()
        {
            Ok(out) if out.status.success() => {
                let ver = String::from_utf8_lossy(&out.stdout).trim().to_string();
                log_info(&format!("✅ yt-dlp jest zainstalowany: wersja {ver}"));
                YtDlpStatus {
                    installed: true,
                    version: Some(ver.clone()),
                    error: None,
                    message: format!("yt-dlp wersja {ver} jest zainstalowany"),
                }
            }
            Ok(_) => {
                log_error("⚠️ yt-dlp jest zainstalowany ale nie działa poprawnie");
                YtDlpStatus {
                    installed: false,
                    version: None,
                    error: Some("command_failed".into()),
                    message: "yt-dlp nie działa poprawnie".into(),
                }
            }
            Err(_) => {
                log_error("⚠️ yt-dlp nie jest zainstalowany");
                YtDlpStatus {
                    installed: false,
                    version: None,
                    error: Some("not_found".into()),
                    message: "yt-dlp nie jest zainstalowany".into(),
                }
            }
        }
    })
}

fn clean_filename(title: &str) -> String {
    let mut s: String = title
        .chars()
        .map(|c| match c {
            '<' | '>' | ':' | '"' | '/' | '\\' | '|' | '?' | '*' => '_',
            _ => c,
        })
        .collect();

    if s.len() > 100 {
        s.truncate(100);
    }
    s = s.trim_matches(&['_', ' ', '.'][..]).to_string();
    if s.is_empty() {
        "Unknown_Video".into()
    } else {
        s
    }
}

fn ffmpeg_available() -> bool {
    Command::new("ffmpeg")
        .arg("-version")
        .stdout(Stdio::null())
        .stderr(Stdio::null())
        .status()
        .is_ok()
}

struct AppState {
    job_sender: mpsc::Sender<DownloadJob>,
    job_counter: AtomicU64,
    queue: Mutex<Vec<DownloadQueueItem>>,
}

async fn status_handler() -> impl Responder {
    let folder = downloads_folder();
    let resp = StatusResponse {
        status: "running",
        version: "1.0.0",
        timestamp: current_unix_time_f64(),
        downloads_folder: folder,
    };
    HttpResponse::Ok().json(resp)
}

async fn check_ytdlp_handler() -> impl Responder {
    let st = check_ytdlp_once().clone();
    HttpResponse::Ok().json(st)
}

async fn download_handler(
    body: web::Json<DownloadRequest>,
    app_state: web::Data<AppState>,
) -> impl Responder {
    let data = body.into_inner();

    if data.url.trim().is_empty() {
        return HttpResponse::BadRequest().json(DownloadResponse {
            success: false,
            message: None,
            error: Some("URL jest wymagany".into()),
            output_path: None,
        });
    }

    let url = data.url;
    let quality = data.quality.unwrap_or_else(|| "best".into());
    let format_selector = data.format.unwrap_or_else(|| "mp4".into());
    let subfolder = data.subfolder.unwrap_or_default();
    let custom_title = data.title;
    let username = data.username;
    let password = data.password;
    let has_premium = username.is_some() && password.is_some();

    log_info("📥 Otrzymano żądanie pobierania:");
    log_info(&format!("   URL: {url}"));
    log_info(&format!("   Jakość: {quality}"));
    log_info(&format!("   Format: {format_selector}"));

    if has_premium {
        if let Some(u) = &username {
            log_info(&format!("👑 Pobieranie Premium dla użytkownika: {u} (hasło: ****)"));
        }
    }

    let mut base_path = PathBuf::from(downloads_folder());
    if !subfolder.is_empty() {
        base_path.push(&subfolder);
        log_info(&format!("📂 Używam podfolderu: {}", base_path.to_string_lossy()));
    }
    log_info(&format!(
        "📁 Folder docelowy: {}",
        base_path.to_string_lossy()
    ));

    if let Err(e) = fs::create_dir_all(&base_path) {
        let msg = format!("Nie udało się utworzyć folderu: {e}");
        log_error(&msg);
        return HttpResponse::InternalServerError().json(DownloadResponse {
            success: false,
            message: None,
            error: Some(msg),
            output_path: None,
        });
    }

    let params = DownloadParams {
        url: url.clone(),
        quality: quality.clone(),
        format_selector: format_selector.clone(),
        output_path: base_path.clone(),
        custom_title: custom_title.clone(),
        username: username.clone(),
        password: password.clone(),
    };

    let queue_item = DownloadQueueItem {
        url,
        quality,
        format_selector,
        subfolder,
        title: custom_title,
        username,
        password,
    };


    {
        let mut queue = app_state.queue.lock().unwrap();
        queue.push(queue_item);
        save_queue_to_file(&queue);
    }

    let job_id = app_state
        .job_counter
        .fetch_add(1, Ordering::SeqCst)
        .wrapping_add(1);

    let (resp_tx, resp_rx) = oneshot::channel::<JobResult>();

    let job = DownloadJob {
        id: job_id,
        params,
        resp_tx,
    };

    if let Err(e) = app_state.job_sender.send(job).await {
        let msg = format!("Nie udało się dodać zadania do kolejki: {e}");
        log_error(&msg);
        return HttpResponse::InternalServerError().json(DownloadResponse {
            success: false,
            message: None,
            error: Some("Nie udało się dodać zadania do kolejki".into()),
            output_path: None,
        });
    }

    let queue_pos = QUEUE_LEN.fetch_add(1, Ordering::SeqCst) + 1;
    log_info(&format!(
        "📥 Dodano pobieranie #{job_id} do kolejki (pozycja: {queue_pos})"
    ));

    match resp_rx.await {
        Ok(res) => {
            QUEUE_LEN.fetch_sub(1, Ordering::SeqCst);
            if res.success {
                HttpResponse::Ok().json(DownloadResponse {
                    success: true,
                    message: res.message,
                    error: None,
                    output_path: res.output_path,
                })
            } else {
                let status = res.http_status;
                HttpResponse::build(actix_web::http::StatusCode::from_u16(status).unwrap_or(actix_web::http::StatusCode::INTERNAL_SERVER_ERROR))
                    .json(DownloadResponse {
                        success: false,
                        message: res.message,
                        error: res.error,
                        output_path: res.output_path,
                    })
            }
        }
        Err(_) => {
            QUEUE_LEN.fetch_sub(1, Ordering::SeqCst);
            let msg = "Błąd kolejki pobierania (kanał przerwany)".to_string();
            log_error(&msg);
            HttpResponse::InternalServerError().json(DownloadResponse {
                success: false,
                message: None,
                error: Some(msg),
                output_path: None,
            })
        }
    }
}

async fn verify_premium_handler(body: web::Json<VerifyPremiumRequest>) -> impl Responder {
    let username = match &body.username {
        Some(u) if !u.is_empty() => u.clone(),
        _ => {
            return HttpResponse::BadRequest().json(VerifyPremiumResponse {
                success: false,
                is_premium: None,
                message: None,
                error: Some("Brak danych logowania".into()),
            })
        }
    };

    let password = match &body.password {
        Some(p) if !p.is_empty() => p.clone(),
        _ => {
            return HttpResponse::BadRequest().json(VerifyPremiumResponse {
                success: false,
                is_premium: None,
                message: None,
                error: Some("Brak danych logowania".into()),
            })
        }
    };

    log_info(&format!("🔐 Weryfikacja konta Premium dla: {username}"));

    let args = [
        "--username",
        &username,
        "--password",
        &password,
        "--dump-json",
        "--playlist-items",
        "0",
        "--no-download",
        "https://www.cda.pl",
    ];

    let output = Command::new("yt-dlp")
        .args(&args)
        .stdout(Stdio::null())
        .stderr(Stdio::piped())
        .output();

    match output {
        Ok(out) if out.status.success() => {
            log_info("✅ Dane logowania są poprawne");
            HttpResponse::Ok().json(VerifyPremiumResponse {
                success: true,
                is_premium: None,
                message: Some("Dane logowania poprawne (status Premium nieznany)".into()),
                error: None,
            })
        }
        Ok(out) => {
            let err = String::from_utf8_lossy(&out.stderr).to_string();
            log_error(&format!("❌ Nieprawidłowe dane logowania: {err}"));
            HttpResponse::Ok().json(VerifyPremiumResponse {
                success: false,
                is_premium: None,
                message: None,
                error: Some("Nieprawidłowe dane logowania".into()),
            })
        }
        Err(e) => {
            let msg = format!("Błąd uruchomienia yt-dlp: {e}");
            log_error(&msg);
            HttpResponse::InternalServerError().json(VerifyPremiumResponse {
                success: false,
                is_premium: None,
                message: None,
                error: Some(msg),
            })
        }
    }
}

fn parse_ytdlp_output_line(line: &str, downloaded_file: &mut Option<PathBuf>) {
    use std::ffi::OsStr;

    let trimmed = line.trim();
    if trimmed.is_empty() {
        return;
    }

    // Główne logowanie postępu
    if trimmed.contains("[download]") {
        if let Some(idx) = trimmed.find("Destination:") {
            // Znaleziono nazwę pliku
            let fname = trimmed[idx + "Destination:".len()..].trim();
            *downloaded_file = Some(PathBuf::from(fname));
            let basename = Path::new(fname)
                .file_name()
                .unwrap_or_else(|| OsStr::new(fname))
                .to_string_lossy()
                .to_string();
            log_info(&format!("📄 Plik: {basename}"));
        } else if trimmed.contains('%') && trimmed.contains("ETA") {
            // Klasyczny progress
            let part = trimmed
                .split_whitespace()
                .find(|p| p.contains('%'))
                .unwrap_or(trimmed);
            log_info(&format!("⏳ Postęp: {part}"));
        } else {
            // Inne komunikaty download
            log_info(&format!("⏳ Pobieranie: {trimmed}"));
        }
    } else if trimmed.contains("[Merger]") && trimmed.contains("Merging formats into") {
        if let Some(start) = trimmed.find('"') {
            if let Some(end_rel) = trimmed[start + 1..].find('"') {
                let end = start + 1 + end_rel;
                let fname = &trimmed[start + 1..end];
                *downloaded_file = Some(PathBuf::from(fname));
            }
        }
        log_info(&format!("🔄 Łączenie formatów: {trimmed}"));
    } else if trimmed.contains("[ExtractAudio]") {
        log_info(&format!("🎵 Konwersja audio: {trimmed}"));
    } else if trimmed.to_uppercase().contains("ERROR") {
        log_error(&format!("❌ Błąd: {trimmed}"));
    } else {
        // Wszystkie pozostałe linie wypisujemy, żeby nic się nie zgubiło
        log_info(&format!("ℹ️ {trimmed}"));
    }
}


fn find_latest_mp4_in_dir(dir: &Path) -> Option<PathBuf> {
    let mut candidates: Vec<(PathBuf, std::time::SystemTime)> = Vec::new();
    if let Ok(entries) = fs::read_dir(dir) {
        for e in entries.flatten() {
            let path = e.path();
            if path
                .extension()
                .map(|ext| ext.eq_ignore_ascii_case("mp4"))
                .unwrap_or(false)
            {
                if let Ok(meta) = e.metadata() {
                    if let Ok(mtime) = meta.modified() {
                        candidates.push((path, mtime));
                    }
                }
            }
        }
    }
    candidates.sort_by_key(|(_, t)| *t);
    candidates.pop().map(|(p, _)| p)
}

fn run_download_and_convert(params: &DownloadParams, job_id: u64) -> JobResult {
    let has_premium = params.username.is_some() && params.password.is_some();
    let output_path = params.output_path.clone();

    let mut cmd: Vec<String> = vec![YTDLP_PATH.clone()];

    // dodajemy --newline, żeby postęp był wypisywany od razu
    cmd.push("--newline".into());

    let quality_arg = match params.quality.as_str() {
        "best" => "bestvideo+bestaudio/best",
        "worst" => "worstvideo+bestaudio/worst",
        "bestaudio" => "bestvideo+bestaudio/best",
        "best[height<=720]" => "bestvideo[height<=720]+bestaudio/best[height<=720]",
        "best[height<=480]" => "bestvideo[height<=480]+bestaudio/best[height<=480]",
        other => other,
    }
    .to_string();
    cmd.push("-f".into());
    cmd.push(quality_arg);

    cmd.push("--merge-output-format".into());
    cmd.push("mp4".into());

    let mut needs_conversion = false;
    let target_format = params.format_selector.to_lowercase();
    if matches!(target_format.as_str(), "mkv" | "webm" | "mp3") {
        needs_conversion = true;
        if target_format == "mp3" {
            log_info("🔄 Po pobraniu zostanie wykonana konwersja do MP3 (audio)");
        } else {
            log_info(&format!(
                "🔄 Po pobraniu zostanie wykonana konwersja do {}",
                target_format.to_uppercase()
            ));
        }
    }

    cmd.extend([
        "--no-part".into(),
        "--remux-video".into(),
        "mp4".into(),
        "--no-keep-fragments".into(),
        "--fixup".into(),
        "detect_or_warn".into(),
        "--postprocessor-args".into(),
        "ffmpeg:-movflags +faststart".into(),
        "--concurrent-fragments".into(),
        "10".into(),
        "--retries".into(),
        "10".into(),
        "--fragment-retries".into(),
        "10".into(),
    ]);

    cmd.extend([
        "--no-playlist".into(),
        "--no-write-info-json".into(),
        "--no-write-thumbnail".into(),
        "--no-write-description".into(),
        "--no-write-auto-sub".into(),
        "--no-write-sub".into(),
        "--no-embed-thumbnail".into(),
        "--add-metadata".into(),
        "--no-warnings".into(),
    ]);

    let output_template = if let Some(title) = &params.custom_title {
        let clean = clean_filename(title);
        log_info(&format!("📋 Używam własnego tytułu: {clean}"));
        output_path.join(format!("{clean}.%(ext)s"))
    } else {
        output_path.join("%(title)s.%(ext)s")
    };
    let output_template_str = output_template.to_string_lossy().to_string();
    cmd.push("-o".into());
    cmd.push(output_template_str);

    if has_premium {
        if let (Some(u), Some(p)) = (&params.username, &params.password) {
            cmd.push("--username".into());
            cmd.push(u.clone());
            cmd.push("--password".into());
            cmd.push(p.clone());
            log_info("👑 Używam konta Premium do pobierania");
        }
    }

    cmd.push(params.url.clone());

    log_info(&format!("🚀 Start pobierania #{job_id}"));
    log_info(&format!("🚀 Rozpoczynam pobieranie z URL: {}", params.url));

    let mut child = match Command::new(&cmd[0])
        .args(&cmd[1..])
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
        .spawn()
    {
        Ok(c) => c,
        Err(e) => {
            let msg = format!("Nie udało się uruchomić yt-dlp: {e}");
            log_error(&msg);
            return JobResult {
                success: false,
                http_status: 500,
                message: None,
                error: Some(msg),
                output_path: None,
            };
        }
    };

    let stdout = child.stdout.take().unwrap();
    let stderr = child.stderr.take().unwrap();

    let downloaded_file = Arc::new(Mutex::new(None));
    let df_clone1 = downloaded_file.clone();
    let df_clone2 = downloaded_file.clone();


    /////duplikacja to nie błąd!!!!!!
    let stdout_thread = std::thread::spawn(move || {
        let reader = BufReader::new(stdout);
        for line in reader.lines().flatten() {
            let mut df = df_clone1.lock().unwrap();
            parse_ytdlp_output_line(&line, &mut df);
        }
    });

    let stderr_thread = std::thread::spawn(move || {
        let reader = BufReader::new(stderr);
        for line in reader.lines().flatten() {
            let mut df = df_clone2.lock().unwrap();
            parse_ytdlp_output_line(&line, &mut df);
        }
    });

    // Czekamy na zakończenie yt-dlp
    let _status = child.wait().expect("Błąd oczekiwania na yt-dlp");

    // Czekamy na wątki stdout/stderr
    let _ = stdout_thread.join();
    let _ = stderr_thread.join();

    // Pobranie finalnej wartości pobranego pliku
    let downloaded_file = downloaded_file.lock().unwrap().clone();


    ////
    let mut actual_downloaded_file: Option<PathBuf> = None;

    if needs_conversion {
        if let Some(mut p) = downloaded_file.clone() {
            if !p.is_absolute() {
                p = output_path.join(p);
            }
            if p.exists() {
                actual_downloaded_file = Some(p.clone());
                log_info(&format!(
                    "✅ Używam pliku z yt-dlp: {}",
                    p.to_string_lossy()
                ));
            }
        }

        if actual_downloaded_file.is_none() {
            log_info("🔍 Wyszukiwanie pobranego pliku MP4 do konwersji...");
            if let Some(p) = find_latest_mp4_in_dir(&output_path) {
                log_info(&format!(
                    "Znaleziono plik do konwersji: {}",
                    p.to_string_lossy()
                ));
                actual_downloaded_file = Some(p);
            } else {
                log_error("⚠️ Nie znaleziono pliku MP4 do konwersji");
            }
        }

        if let Some(src) = &actual_downloaded_file {
            if !src.exists() {
                log_error(&format!("⚠️ Błąd konwersji - plik nie istnieje"));
            } else if !ffmpeg_available() {
                log_error("⚠️ FFmpeg nie jest dostępny - pomijam konwersję");
            } else {
                let base = src.with_extension("");
                let output_file = base.with_extension(&target_format);

                log_info(&format!(
                    "🔄 Rozpoczynam konwersję {} do {}",
                    src.to_string_lossy(),
                    target_format
                ));

                let ffmpeg_cmd: Vec<String> = if target_format == "mp3" {
                    vec![
                        "ffmpeg".into(),
                        "-i".into(),
                        src.to_string_lossy().into(),
                        "-vn".into(),
                        "-acodec".into(),
                        "libmp3lame".into(),
                        "-q:a".into(),
                        "2".into(),
                        "-y".into(),
                        output_file.to_string_lossy().into(),
                    ]
                } else {
                    vec![
                        "ffmpeg".into(),
                        "-i".into(),
                        src.to_string_lossy().into(),
                        "-c".into(),
                        "copy".into(),
                        "-movflags".into(),
                        "+faststart".into(),
                        "-y".into(),
                        output_file.to_string_lossy().into(),
                    ]
                };

                log_info(&format!("ffmpeg cmd: {:?}", ffmpeg_cmd));

                let status = Command::new(&ffmpeg_cmd[0])
                    .args(&ffmpeg_cmd[1..])
                    .stdout(Stdio::null())
                    .stderr(Stdio::piped())
                    .status();

                match status {
                    Ok(s) if s.success() => {
                        log_info("✅ Konwersja zakończona pomyślnie!");
                        if let Err(e) = fs::remove_file(src) {
                            log_error(&format!(
                                "Nie udało się usunąć oryginalnego pliku: {e}"
                            ));
                        } else {
                            log_info("🗑️ Usunięto oryginalny plik MP4");
                        }
                        if let Some(name) = output_file.file_name() {
                            log_info(&format!(
                                "📁 Zapisano jako: {}",
                                name.to_string_lossy()
                            ));
                        }
                    }
                    Ok(_) => {
                        log_error("⚠️ Konwersja nie powiodła się");
                        log_info("ℹ️ Plik pozostał w formacie MP4");
                    }
                    Err(e) => {
                        log_error(&format!("Błąd konwersji ffmpeg: {e}"));
                        log_info("ℹ️ Plik pozostał w formacie MP4");
                    }
                }
            }
        } else {
            log_error("⚠️ Nie można wykonać konwersji - nie znaleziono pliku");
        }
    }

    log_info(&format!(
        "📁 Zapisano do: {}",
        output_path.to_string_lossy()
    ));

    JobResult {
        success: true,
        http_status: 200,
        message: Some("Pobieranie zakończone pomyślnie".into()),
        error: None,
        output_path: Some(output_path.to_string_lossy().to_string()),
    }
}

async fn download_worker_loop(
    mut rx: mpsc::Receiver<DownloadJob>,
    app_state: web::Data<AppState>,
) {
    while let Some(job) = rx.recv().await {
        let id = job.id;
        let params = job.params.clone();
        let res = run_download_and_convert(&params, id);

        if job.resp_tx.send(res).is_err() {
            log_error(&format!(
                "❌ Błąd wątku pobierania #{id}: nie udało się odesłać wyniku"
            ));
        }

        // Usuwanie z kolejki po zakończeniu
        let mut queue = app_state.queue.lock().unwrap();
        queue.retain(|item| item.url != job.params.url);
        save_queue_to_file(&queue);
    }
}








#[actix_web::main]
async fn main() -> std::io::Result<()> {
    let mut port: u16 = 8080;
    let mut verbose = false;

    let args: Vec<String> = env::args().collect();
    let mut i = 1;
    while i < args.len() {
        match args[i].as_str() {
            "--port" => {
                if i + 1 < args.len() {
                    if let Ok(p) = args[i + 1].parse::<u16>() {
                        port = p;
                    }
                    i += 1;
                }
            }
            "--verbose" | "-v" => {
                verbose = true;
            }
            _ => {}
        }
        i += 1;
    }

    if verbose {
        log_info("Włączono tryb verbose");
    }

    check_dependencies();

    let downloads = downloads_folder();
    log_info(&format!(
        "Video Download Assistant Server uruchamia się na http://localhost:{port}"
    ));
    log_info(&format!("📁 Folder pobierania: {downloads}"));

    let _ = check_ytdlp_once();

    let (tx, rx) = mpsc::channel::<DownloadJob>(100);



    let initial_queue = load_queue_from_file();
    log_info(&format!("📂 Wczytano {} zadań z poprzedniej sesji", initial_queue.len()));

    let app_state = web::Data::new(AppState {
        job_sender: tx,
        job_counter: AtomicU64::new(0),
        queue: Mutex::new(initial_queue),
    });

    tokio::spawn(download_worker_loop(rx, app_state.clone()));



    HttpServer::new(move || {
        App::new()
            .app_data(app_state.clone())
            .wrap(
                Cors::default()
                    .allow_any_origin()
                    .allowed_methods(vec!["GET", "POST", "OPTIONS"])
                    .allow_any_header()
                    .max_age(3600),
            )
            .route("/status", web::get().to(status_handler))
            .route("/check-ytdlp", web::get().to(check_ytdlp_handler))
            .route("/download", web::post().to(download_handler))
            .route("/verify-premium", web::post().to(verify_premium_handler))
    })
    .bind(("127.0.0.1", port))?
    .run()
    .await
}



fn check_dependencies() {
    #[cfg(target_os = "linux")]
    {
        log_info("🔍 Sprawdzam dostępność yt-dlp i ffmpeg na Linuxie...");

        // Sprawdzenie yt-dlp
        let yt_installed = Command::new("yt-dlp").arg("--version").output().is_ok();
        if !yt_installed {
            log_error("❌ yt-dlp nie jest zainstalowany lub nie jest w PATH");

            print!("Chcesz pobrać yt-dlp automatycznie? (y/n): ");
            io::stdout().flush().unwrap();

            let mut input = String::new();
            io::stdin().read_line(&mut input).unwrap();

            if input.trim().eq_ignore_ascii_case("y") {
                log_info("📥 Pobieram yt-dlp...");
                let url = "https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp";
                let out_path = "./bin/yt-dlp";
                std::fs::create_dir_all("./bin").unwrap();

                let resp = reqwest::blocking::get(url).expect("Nie udało się pobrać yt-dlp");
                let bytes = resp.bytes().expect("Błąd odczytu pobranego pliku");
                std::fs::write(out_path, &bytes).expect("Nie udało się zapisać yt-dlp");
                std::fs::set_permissions(out_path, std::fs::Permissions::from_mode(0o755))
                    .expect("Nie udało się nadać uprawnień wykonywalnych");

                log_info("✅ yt-dlp został pobrany i zapisany w ./bin/yt-dlp");
            } else {
                log_error("❌ yt-dlp nie został zainstalowany. Pobieranie nie będzie działać.");
            }
        } else {
            log_info("✅ yt-dlp jest dostępny");
        }

        // Sprawdzenie ffmpeg
        if Command::new("ffmpeg").arg("-version").output().is_err() {
            log_error("❌ ffmpeg nie jest zainstalowany lub nie jest w PATH");
        } else {
            log_info("✅ ffmpeg jest dostępny");
        }
    }
}

#[cfg(target_family = "unix")]

fn set_executable(path: &str) {
    #[cfg(target_family = "unix")]
    {
        let mut perms = std::fs::metadata(path).unwrap().permissions();
        perms.set_mode(0o755); // chmod +x
        std::fs::set_permissions(path, perms).unwrap();
    }
    #[cfg(not(target_family = "unix"))]
    {
        // Windows: nie trzeba nic robić, albo użyć atrybutów Windows jeśli konieczne
    }
}


///funkcje zapisu json
fn save_queue_to_file(queue: &[DownloadQueueItem]) {
    if let Ok(json) = serde_json::to_string_pretty(queue) {
        if let Err(e) = std::fs::write(QUEUE_FILE, json) {
            log_error(&format!("Nie udało się zapisać kolejki: {e}"));
        }
    } else {
        log_error("Błąd serializacji kolejki do JSON");
    }
}

fn load_queue_from_file() -> Vec<DownloadQueueItem> {
    if let Ok(data) = std::fs::read_to_string(QUEUE_FILE) {
        serde_json::from_str::<Vec<DownloadQueueItem>>(&data).unwrap_or_else(|e| {
            log_error(&format!("Nie udało się odczytać kolejki JSON: {e}"));
            vec![]
        })
    } else {
        vec![]
    }
}






