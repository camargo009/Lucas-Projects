param([switch]$SemTunel)
Set-Location $PSScriptRoot
python -m pip install -q -r requirements.txt

if (-not $SemTunel) {
  if (-not (Test-Path .\cloudflared.exe)) {
    Write-Host "Baixando cloudflared..."
    Invoke-WebRequest "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-windows-amd64.exe" -OutFile .\cloudflared.exe
  }
  Remove-Item .\tunel.log -ErrorAction SilentlyContinue
  Start-Process .\cloudflared.exe -ArgumentList "tunnel --url http://localhost:8080" -RedirectStandardError .\tunel.log -WindowStyle Hidden
  $url = $null
  for ($i = 0; $i -lt 30 -and -not $url; $i++) {
    Start-Sleep 1
    if (Test-Path .\tunel.log) {
      $m = Select-String -Path .\tunel.log -Pattern "https://[a-z0-9-]+\.trycloudflare\.com" | Select-Object -First 1
      if ($m) { $url = $m.Matches[0].Value }
    }
  }
  if ($url) {
    Write-Host ""
    Write-Host "URL PUBLICA (envie ao dev remoto): $url" -ForegroundColor Green
    Write-Host "No caso, use 'Definir URL publica' e cole esse endereco para o QR/link."
  } else { Write-Host "Tunel nao iniciou; use localhost." -ForegroundColor Yellow }
}
Write-Host "Local: http://localhost:8080  |  senha das contas demo: telessaude"
python server.py
