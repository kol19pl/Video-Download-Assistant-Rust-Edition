mod models;
mod setup;
mod pobieracz;
mod dodatkowe_funkcje;
mod api_handler;

use actix_cors::Cors;
use actix_web::{web, App, HttpResponse, HttpServer, Responder};
use once_cell::sync::{Lazy, OnceCell};
use serde::{Deserialize, Serialize};
use std::env;
use std::fs;
use std::io::{empty, BufRead, BufReader};
use std::path::{Path, PathBuf};
use std::process::{Command, Stdio};
use std::sync::atomic::{AtomicU64, AtomicUsize, Ordering};
use time::OffsetDateTime;
use tokio::sync::{mpsc, oneshot};
use std::sync::{Arc, Mutex};
use serde_json;
#[allow(unused_imports)]
use std::io::{self, Write};
use std::net::{IpAddr, Ipv4Addr};
#[cfg(target_family = "unix")]
use std::os::unix::fs::PermissionsExt;
use dirs::download_dir;
use crate::api_handler::{check_ytdlp_handler, download_handler, download_handlerv2, queue_handler, status_handler, verify_premium_handler};
use crate::dodatkowe_funkcje::{downloads_folder, load_queue_from_file, log_info, log_error, save_queue_to_file, set_global_download_dir};
use crate::models::{DownloadParams, DownloadQueueItem, DownloadRequest, DownloadResponse, JobResult, StatusResponse, YtDlpStatus};
use crate::pobieracz::download_worker_loop;
use crate::setup::{is_synology, port_is_available};





static YTDLP_STATUS: OnceCell<YtDlpStatus> = OnceCell::new();
static QUEUE_LEN: Lazy<AtomicUsize> = Lazy::new(|| AtomicUsize::new(0));
static GLOBAL_DOWNLOAD_DIR: Lazy<Mutex<Option<String>>> = Lazy::new(|| Mutex::new(None));





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


struct DownloadJob {
    id: u64,
    params: DownloadParams,
    resp_tx: oneshot::Sender<JobResult>,
}





struct AppState {
    job_sender: mpsc::Sender<DownloadJob>,
    job_counter: AtomicU64,
    queue: Mutex<Vec<DownloadQueueItem>>,
}






#[actix_web::main]
async fn main() -> std::io::Result<()> {
    //fix synology
    //#[cfg(target_os = "linux")]{
    //if(is_synology()){ register_urandom();}
    println!("Random number: {}", rand::random::<u32>());




    let mut port: u16 = 8080;
    let server_ip: IpAddr = IpAddr::V4(Ipv4Addr::new(0, 0, 0, 0));
    let mut verbose = false;
    let mut download_dir = String::new();


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
            "--download-dir" => {
                if i + 1 < args.len() {
                    download_dir = args[i + 1].clone();
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

    setup::check_dependencies();

    if !download_dir.is_empty(){
        // ustawiamy globalny folder
        set_global_download_dir(download_dir);
    }

    let downloads = downloads_folder();


    let version = option_env!("VDA_VERSION").unwrap_or(env!("CARGO_PKG_VERSION"));
    log_info(&format!(
        "🚀 Video Download Assistant Server {} uruchamia się na https://{server_ip}:{port}",
        version
    ));
    log_info(&format!("📁 Folder pobierania: {downloads}"));

    let _ = setup::check_ytdlp_once();

    let (tx, rx) = mpsc::channel::<DownloadJob>(100);



    let initial_queue = load_queue_from_file();
    log_info(&format!("📂 Wczytano {} zadań z poprzedniej sesji", initial_queue.len()));

    let app_state = web::Data::new(AppState {
        job_sender: tx,
        job_counter: AtomicU64::new(0),
        queue: Mutex::new(initial_queue),
    });

    tokio::spawn(download_worker_loop(rx, app_state.clone()));


    let max_prub = 10;
    let port_start= port;
    let mut port_end = port;

    for _ in 0..max_prub {
        if port_is_available(server_ip, port) {
            break; // port wolny
        } else {
            eprintln!("Port {}:{} jest zajęty, próbuję kolejny...", server_ip, port);
            port += 1; // idziemy do następnego
            port_end = port;
        }
    }

    if !port_is_available(server_ip, port) {
        eprintln!("❌ Żaden z portów od {} do {} nie jest dostępny", port_start, port_end);
        std::process::exit(1);
    }

    println!("✅ Wybrany port: {}", port);


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
            //api handler
            .route("/status", web::get().to(status_handler))
            .route("/check-ytdlp", web::get().to(check_ytdlp_handler))
            .route("/queue", web::get().to(queue_handler))
            .route("/download", web::post().to(download_handler))
            .route("/downloadV2", web::post().to(download_handlerv2))
            .route("/verify-premium", web::post().to(verify_premium_handler))
    })
    //.bind(("127.0.0.1", port))?

        .bind((server_ip, port))?
    .run()
    .await
}
