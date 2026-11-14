$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$python = Join-Path $projectRoot '.venv/Scripts/python.exe'
$icon = Join-Path $projectRoot 'src/left_right_music_visualizer/assets/icon.ico'
if (-not (Test-Path $python)) {
    throw 'Create the .venv and install the build extra before running this script.'
}
Push-Location $projectRoot
try {
    & $python -m PyInstaller --onefile --noconsole `
        --name left-right-music-visualizer `
        --specpath build `
        --paths src `
        --icon $icon `
        --add-data "$icon;left_right_music_visualizer/assets" `
        scripts/pyinstaller_entry.py
    if ($LASTEXITCODE -ne 0) {
        throw "PyInstaller failed with exit code $LASTEXITCODE."
    }
}
finally {
    Pop-Location
}

