use std::env;
use std::path::Path;
use std::fs;
use std::process::Command;
#[cfg(target_os = "windows")]
use winres;

fn set_dynamic_version() {
    // Używamy daty w formacie YYYY-MM-DD
    use std::time::{SystemTime, UNIX_EPOCH};
    let now = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .unwrap()
        .as_secs();
    let days_since_epoch = now / 86400;
    let year = 1970 + (days_since_epoch / 365);
    let day_of_year = days_since_epoch % 365;
    let month = (day_of_year * 12 / 365) + 1;
    let day = (day_of_year * 31 / 365) + 1;
    let version = format!("v{:04}-{:02}-{:02}", year, month, day);

    println!("cargo:rustc-env=VDA_VERSION={}", version);
}

fn main() {
    println!("cargo:warning=Build script started!");
    // Ustawiamy dynamiczną wersję na podstawie daty lub git
    set_dynamic_version();

    let manifest_dir = std::env::var("CARGO_MANIFEST_DIR").unwrap();


    #[cfg(target_os = "windows")]
    {
        // Windows: wbudowujemy ikonę .ico w exe
        let ico_path = Path::new(&manifest_dir).join("src").join("icon.ico");
        let png_path = Path::new(&manifest_dir).join("src").join("icon.png");

        // Jeśli nie ma icon.ico, spróbuj skonwertować icon.png
        if !ico_path.exists() && png_path.exists() {
            println!("cargo:warning=Konwertowanie icon.png na icon.ico...");

            // Spróbuj użyć ImageMagick (magick convert)
            let convert_result = Command::new("magick")
                .args(&["convert", png_path.to_str().unwrap(),
                       "-background", "transparent",
                       "-define", "icon:auto-resize=16,24,32,48,64,128",
                       ico_path.to_str().unwrap()])
                .output();

            match convert_result {
                Ok(output) if output.status.success() => {
                    println!("cargo:warning=Pomyślnie skonwertowano icon.png na icon.ico");
                }
                _ => {
                    // Alternatywnie spróbuj użyć ffmpeg
                    println!("cargo:warning=Magick nie znaleziony, próba użycia ffmpeg...");
                    let ffmpeg_result = Command::new("ffmpeg")
                        .args(&["-i", png_path.to_str().unwrap(),
                               "-vf", "scale=256:256",
                               ico_path.to_str().unwrap()])
                        .output();

                    match ffmpeg_result {
                        Ok(output) if output.status.success() => {
                            println!("cargo:warning=Pomyślnie skonwertowano icon.png na icon.ico używając ffmpeg");
                        }
                        _ => {
                            println!("cargo:warning=Nie udało się skonwertować icon.png na icon.ico");
                        }
                    }
                }
            }
        }

        if ico_path.exists() {
            println!("cargo:warning=Ustawianie ikony Windows: {:?}", ico_path);
            let mut res = winres::WindowsResource::new();
            match res.set_icon(ico_path.to_str().unwrap()).compile() {
                Ok(_) => println!("cargo:warning=Ikona Windows została pomyślnie ustawiona"),
                Err(e) => println!("cargo:warning=Błąd kompilacji ikony Windows: {}", e),
            }
        } else {
            println!("cargo:warning=Plik ikony nie istnieje: {:?}", ico_path);
        }
    }

    #[cfg(target_os = "linux")]
    {
        // Linux: kopiujemy icon.png do ~/.local/share/icons i tworzymy .desktop
        let icon_src = Path::new(&manifest_dir).join("src").join("icon.png");
        let icon_dest = dirs::home_dir()
            .unwrap()
            .join(".local/share/icons/myapp.png");
        fs::create_dir_all(icon_dest.parent().unwrap()).unwrap();
        fs::copy(icon_src, &icon_dest).expect("Nie udało się skopiować ikony na Linux");

        // Tworzymy plik .desktop
        let desktop_file = dirs::home_dir()
            .unwrap()
            .join(".local/share/applications/myapp.desktop");
        let exec_path = env::current_exe().unwrap();

        let desktop_content = format!(
            "[Desktop Entry]
Name=vda_server
Exec={}
Icon={}
Terminal=false
Type=Application
Categories=Utility;",
            exec_path.display(),
            icon_dest.display()
        );

        fs::write(desktop_file, desktop_content).expect("Nie udało się utworzyć pliku .desktop");
    }

    #[cfg(target_os = "macos")]
    {
        // macOS: kopiujemy icon.icns do folderu Resources
        let icon_src = Path::new(&manifest_dir).join("src").join("icon.icns");
        let out_dir = env::var("OUT_DIR").unwrap();
        let icon_dest = Path::new(&out_dir).join("icon.icns");
        fs::copy(icon_src, icon_dest).expect("Nie udało się skopiować ikony na macOS");
        // Później trzeba ręcznie wskazać w Info.plist CFBundleIconFile = icon.icns
    }
}
