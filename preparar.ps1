$ErrorActionPreference = 'Stop'
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
$baseDir = $PSScriptRoot
$runtimeDir = Join-Path $baseDir 'runtime'
$pythonExe = Join-Path $runtimeDir 'python.exe'
try {
    New-Item -ItemType Directory -Force -Path $runtimeDir | Out-Null
    if (-not (Test-Path $pythonExe)) {
        Write-Host 'Baixando Python portatil 3.11.9 (64 bits) de python.org...'
        $archive = Join-Path $runtimeDir 'python.zip'
        Invoke-WebRequest -UseBasicParsing -Uri 'https://www.python.org/ftp/python/3.11.9/python-3.11.9-embed-amd64.zip' -OutFile $archive
        Expand-Archive -LiteralPath $archive -DestinationPath $runtimeDir -Force
        Remove-Item -LiteralPath $archive
    }
    @('python311.zip', '.', '..', 'Lib\site-packages', 'import site') | Set-Content -Encoding ASCII -Path (Join-Path $runtimeDir 'python311._pth')
    if (-not (Test-Path (Join-Path $runtimeDir 'Lib\site-packages\pip\__init__.py'))) {
        Write-Host 'Preparando dependencias locais...'
        $bootstrap = Join-Path $runtimeDir 'get-pip.py'
        Invoke-WebRequest -UseBasicParsing -Uri 'https://bootstrap.pypa.io/get-pip.py' -OutFile $bootstrap
        & $pythonExe $bootstrap --no-warn-script-location
        if ($LASTEXITCODE -ne 0) { throw 'Falha ao preparar pip.' }
        Remove-Item -LiteralPath $bootstrap
    }
    Write-Host 'Instalando transcricao local e FFmpeg. Primeiro uso requer internet.'
    & $pythonExe -m pip install --disable-pip-version-check --no-warn-script-location -r (Join-Path $baseDir 'requirements.txt')
    if ($LASTEXITCODE -ne 0) { throw 'Falha ao instalar dependencias.' }
    & $pythonExe -c "import imageio_ffmpeg; import faster_whisper; import webview; print('Ferramentas prontas.')"
    if ($LASTEXITCODE -ne 0) { throw 'Uma dependencia nao carregou. Confira as mensagens acima.' }
    Set-Content -Encoding ASCII -Path (Join-Path $runtimeDir 'pronto-v07.txt') -Value 'MontaVideo 0.7'
    Write-Host 'Pronto. Tudo fica nesta pasta; nenhum Python global foi instalado.'
} catch {
    Write-Host ('ERRO: ' + $_.Exception.Message) -ForegroundColor Red
    exit 1
}
