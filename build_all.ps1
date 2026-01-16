# Lista targetów
$targetsWindows = @(
    "x86_64-pc-windows-msvc",
    "x86_64-pc-windows-gnu",
    "i686-pc-windows-msvc",
    "aarch64-pc-windows-msvc"
)

#rustup target list
$targetsLinux = @(
    "x86_64-unknown-linux-musl",
    "x86_64-unknown-linux-gnu",
    "x86_64-apple-darwin"
    #"aarch64-unknown-linux-musl"
    #"i686-unknown-linux-gnu",
    #"aarch64-unknown-linux-gnu",
    #"arm-unknown-linux-gnueabi",
    #"powerpc64-unknown-linux-gnu",
    #"armv7-linux-androideabi",
    #"aarch64-linux-android",
    #"riscv64gc-unknown-linux-gnu"
)

$outDir = "release_builds"

# Tworzymy folder wynikowy
if (-Not (Test-Path $outDir)) {
    New-Item -ItemType Directory -Path $outDir | Out-Null
}

$projectName = Split-Path -Leaf (Get-Location)

# -----------------------------
# Build Windows targetów lokalnie
# -----------------------------
# MinGW 64-bit i 32-bit
$mingw64 = "C:\msys64\mingw64\bin"
$mingw32 = "C:\msys64\mingw32\bin"
$msvc = "C:\Program Files\Microsoft Visual Studio\18\Community\VC\Tools\MSVC\14.50.35717\bin\Hostx64\x64"
$msvcarm ="C:\Program Files\Microsoft Visual Studio\18\Community\VC\Tools\MSVC\14.50.35717\bin\Hostx64\arm64"
$msvc86 = "C:\Program Files\Microsoft Visual Studio\18\Community\VC\Tools\MSVC\14.50.35717\bin\Hostx64\x86"
$env:PATH = "$mingw64;$mingw32;$msvc;$msvcarm;$msvc86" + $env:PATH

cargo clean



foreach ($target in $targetsLinux) {

    # Convert Windows path to WSL path format
    $linuxPath = $scriptDir -replace '\\', '/' -replace '^([A-Za-z]):', '/mnt/$1' -replace ' ', '\\ '

    Write-Host "Buduję Linux target: $target"
    #wsl -l -v
    #bash -c rustc --version
    #wsl rustc --version
    #wsl cargo --version
    #wsl cargo build --release --target $target
    wsl bash -lc "cd '$linuxPath' && cargo build --release --target $target"


    # Nazwa binarki Linux (bez .exe)
    $exeName = $projectName
    $src = "target\$target\release\$exeName"
    $dst = "$outDir\$projectName-$target"

    if (Test-Path $src) {
        Copy-Item $src $dst -Force
        Write-Host "Skopiowano: $dst"
    } else {
        Write-Host "Nie znaleziono pliku: $src"
    }
}




foreach ($target in $targetsWindows) {
    Write-Host "Buduję Windows target: $target"

    # Dla targetów MSVC ustawienie dodatkowe
    if ($target -like "*msvc") {
        # Uruchom w x64 Native Tools PowerShell jeśli trzeba
        Write-Host "Używam MSVC toolchain dla $target"
    }

    cargo build --release --target $target

    # Kopiowanie pliku do release_builds
    $exeName = "$projectName.exe"
    $src = "target\$target\release\$exeName"
    $dst = "$outDir\$projectName-$target.exe"

    if (Test-Path $src) {
        Copy-Item $src $dst -Force
        Write-Host "Skopiowano: $dst"
    } else {
        Write-Host "Nie znaleziono pliku: $src"
    }
}


cargo clean


Write-Host "Build zakonczony. Wszystkie pliki w folderze: $outDir"
