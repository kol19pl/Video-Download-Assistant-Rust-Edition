use std::fs;
use std::path::{Component, Path, PathBuf};
use std::process::{Command, Stdio};
use std::sync::atomic::Ordering;
use actix_web::{web, HttpResponse, Responder};
use serde::Serialize;
use tokio::sync::oneshot;
use crate::{dodatkowe_funkcje, log_error, log_info, setup, AppState, DownloadJob, VerifyPremiumRequest, VerifyPremiumResponse, QUEUE_LEN};
use crate::dodatkowe_funkcje::{downloads_folder, save_queue_to_file};
use crate::models::{DownloadParams, DownloadQueueItem, DownloadRequest, DownloadResponse, JobResult, StatusResponse};

// Progress response structure
#[derive(Serialize)]
struct ProgressResponse {
    progress: u8,
    file_name: String,
    status: String,
}

pub(crate) async fn status_handler() -> impl Responder {
    let folder = downloads_folder();
    let version = option_env!("VDA_VERSION").unwrap_or(env!("CARGO_PKG_VERSION"));
    let resp = StatusResponse {
        status: "running",
        version,
        timestamp: dodatkowe_funkcje::current_unix_time_f64(),
        downloads_folder: folder,
    };
    HttpResponse::Ok().json(resp)
}

pub(crate) async fn check_ytdlp_handler() -> impl Responder {
    let st = setup::check_ytdlp_once().clone();
    HttpResponse::Ok().json(st)
}




pub(crate) async fn queue_handler(app_state: web::Data<AppState>) -> impl Responder {
    let queue = app_state.queue.lock().unwrap();
    HttpResponse::Ok().json(&*queue)
}

pub(crate) async fn verify_premium_handler(body: web::Json<VerifyPremiumRequest>) -> impl Responder {
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


pub(crate) async fn download_handler(
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
            id: None,
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
            id: None,
        });
    }

    let job_id = app_state
        .job_counter
        .fetch_add(1, Ordering::SeqCst)
        .wrapping_add(1);

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
        id: job_id,
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
            id: None,
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
                    id: Some(job_id),
                })
            } else {
                let status = res.http_status;
                HttpResponse::build(actix_web::http::StatusCode::from_u16(status).unwrap_or(actix_web::http::StatusCode::INTERNAL_SERVER_ERROR))
                    .json(DownloadResponse {
                        success: false,
                        message: res.message,
                        error: res.error,
                        output_path: res.output_path,
                        id: None,
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
                id: None,
            })
        }
    }
}



pub(crate) async fn download_handlerv2(
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
            id: None,
        });
    }

    let url = data.url;
    let quality = data.quality.unwrap_or_else(|| "best".into());
    let format_selector = data.format.unwrap_or_else(|| "mp4".into());
    let subfolder = data.subfolder.unwrap_or_default();
    let custom_title = data.title;
    let username = data.username;
    let password = data.password;

    let mut base_path = PathBuf::from(downloads_folder());
    if !subfolder.is_empty() {
        let sub = Path::new(&subfolder);

        if sub.is_absolute()
            || sub.components().any(|c| matches!(c, Component::ParentDir))
        {
            let msg = "Nieprawidłowa nazwa podfolderu".to_string();
            return HttpResponse::BadRequest().json(DownloadResponse {
                success: false,
                message: None,
                error: Some(msg),
                output_path: None,
                id: None,
            });
        }

        base_path.push(sub);
    }

    if let Err(e) = fs::create_dir_all(&base_path) {

        let msg = format!("Nie udało się utworzyć folderu::{e:} /// {:?}", base_path);
        log_error(&format!("📂 Nie udało się utworzyć folderu:: {:?}", base_path));
        return HttpResponse::InternalServerError().json(DownloadResponse {
            success: false,
            message: None,
            error: Some(msg),
            output_path: None,
            id: None,
        });

    }

    log_info(&format!("📂 Folder gotowy: {:?}", base_path));

    let job_id = app_state
        .job_counter
        .fetch_add(1, Ordering::SeqCst)
        .wrapping_add(1);

    let params = DownloadParams {
        url: url.clone(),
        quality: quality.clone(),
        format_selector: format_selector.clone(),
        output_path: base_path.clone(),
        custom_title: custom_title.clone(),
        username: username.clone(),
        password: password.clone(),
    };

    let title = custom_title.clone().unwrap_or_else(|| "Unknown Title".into());

    let queue_item = DownloadQueueItem {
        id: job_id,                   // unikalne ID zadania
        url: url.clone(),             // adres URL wideo
        quality: quality.clone(),     // wybrana jakość
        format_selector: format_selector.clone(), // format wideo
        subfolder: subfolder.clone(), // ewentualny podfolder w folderze pobierania
        title: Some(title),           // tytuł wideo w polu `title`
        username: username.clone(),   // opcjonalne dane premium
        password: password.clone(),   // opcjonalne dane premium
    };


    {
        let mut queue = app_state.queue.lock().unwrap();
        queue.push(queue_item);
        dodatkowe_funkcje::save_queue_to_file(&queue);
    }

    let (resp_tx, _resp_rx) = oneshot::channel::<JobResult>();

    let job = DownloadJob {
        id: job_id,
        params,
        resp_tx,
    };

    // Dodajemy zadanie do kolejki w tle
    if let Err(e) = app_state.job_sender.send(job).await {
        let msg = format!("Nie udało się dodać zadania do kolejki: {e}");
        return HttpResponse::InternalServerError().json(DownloadResponse {
            success: false,
            message: None,
            error: Some("Nie udało się dodać zadania do kolejki".into()),
            output_path: None,
            id: None,
        });
    }

    // Od razu zwracamy odpowiedź do frontendu, że zadanie dodano
    HttpResponse::Ok().json(DownloadResponse {
        success: true,
        message: Some("Dodano do kolejki".into()),
        error: None,
        output_path: None,
        id: Some(job_id),
    })
}

pub(crate) async fn progress_handler() -> impl Responder {
    // For now, return a mock progress response
    // In a real implementation, this would check the actual download progress
    // from the download worker or queue system
    let progress_response = ProgressResponse {
        progress: 0,
        file_name: String::from("No active download"),
        status: String::from("idle"),
    };

    HttpResponse::Ok().json(progress_response)
}
