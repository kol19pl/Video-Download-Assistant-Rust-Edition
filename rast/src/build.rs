use std::env;
use std::path::Path;
use std::fs;
#[cfg(target_os = "windows")]
use winres;

#[allow(dead_code)]
fn main() {
    let manifest_dir = std::env::var("CARGO_MANIFEST_DIR").unwrap();


    #[cfg(target_os = "windows")]
    {
        // Windows: wbudowujemy ikonę .ico w exe
        let icon_path = Path::new(&manifest_dir).join("src").join("icon.ico");
        let mut res = winres::WindowsResource::new();
        res.set_icon(icon_path.to_str().unwrap());
        res.compile().expect("Nie udało się ustawić ikony dla Windows");
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

