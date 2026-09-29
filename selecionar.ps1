param([ValidateSet('folder','audio','srt','media')][string]$Kind='folder')
$ErrorActionPreference='Stop'
[Console]::OutputEncoding = New-Object System.Text.UTF8Encoding($false)
Add-Type -AssemblyName System.Windows.Forms
# An explicit owner prevents the dialog from remaining behind the browser.
$owner=New-Object System.Windows.Forms.Form
$owner.Text='MontaVideo - Selecionar'
$owner.TopMost=$true
$owner.ShowInTaskbar=$false
$owner.StartPosition='CenterScreen'
$owner.Size=New-Object System.Drawing.Size(1,1)
$owner.Opacity=0
$owner.Show()
$owner.Activate()
try {
if ($Kind -eq 'folder') {
    $d=New-Object System.Windows.Forms.FolderBrowserDialog
    $d.Description='Selecione a pasta para o MontaVideo'
    if ($d.ShowDialog($owner) -eq [System.Windows.Forms.DialogResult]::OK) { @{path=$d.SelectedPath} | ConvertTo-Json -Compress } else { '{"path":""}' }
} else {
    $d=New-Object System.Windows.Forms.OpenFileDialog
    $d.Title='Selecione o arquivo'
    if ($Kind -eq 'audio') { $d.Filter='Audio|*.mp3;*.wav;*.m4a;*.aac;*.flac;*.ogg;*.opus|Todos|*.*' }
    elseif ($Kind -eq 'srt') { $d.Filter='Legenda SRT|*.srt' }
    else { $d.Filter='Midia|*.mp4;*.mov;*.mkv;*.webm;*.jpg;*.jpeg;*.png;*.webp|Todos|*.*' }
    if ($d.ShowDialog($owner) -eq [System.Windows.Forms.DialogResult]::OK) { @{path=$d.FileName} | ConvertTo-Json -Compress } else { '{"path":""}' }
}

} finally {
    if ($d) { $d.Dispose() }
    $owner.Close()
    $owner.Dispose()
}
