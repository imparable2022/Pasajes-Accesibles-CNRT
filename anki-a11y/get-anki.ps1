param([string]$Tag = '26.09.4')
$ErrorActionPreference = 'Stop'
$release = Invoke-RestMethod -Uri "https://api.github.com/repos/ankitects/anki/releases/tags/$Tag" -Headers @{'User-Agent'='anki-a11y-ci'}
$assets = @($release.assets | Where-Object { $_.name -match 'win-x64\.msi$' })
if ($assets.Count -ne 1) {
  $release.assets | ForEach-Object { Write-Host $_.name }
  throw "Expected one official win-x64 MSI, found $($assets.Count)"
}
$asset = $assets[0]
if ($asset.digest -notmatch '^sha256:([0-9a-fA-F]{64})$') {
  throw 'Official GitHub release does not provide a verifiable SHA256 digest'
}
$expected = $Matches[1]
New-Item -ItemType Directory -Force out/a11y/download | Out-Null
$file = Join-Path (Resolve-Path out/a11y/download).Path $asset.name
Invoke-WebRequest -Uri $asset.browser_download_url -OutFile $file
$actual = (Get-FileHash $file -Algorithm SHA256).Hash
if ($actual -ine $expected) { throw "Anki installer digest mismatch: $actual" }
Write-Host "Verified official Anki MSI SHA256 $actual"
$p = Start-Process msiexec.exe -ArgumentList @('/i',"`"$file`"","/qn","/norestart") -Wait -PassThru
if ($p.ExitCode -ne 0) { throw "MSI installer failed: $($p.ExitCode)" }
$candidates = @(
  "$env:LOCALAPPDATA\Programs\Anki\anki.exe",
  "$env:ProgramFiles\Anki\anki.exe",
  "${env:ProgramFiles(x86)}\Anki\anki.exe"
)
$exe = $candidates | Where-Object { $_ -and (Test-Path $_) } | Select-Object -First 1
if (-not $exe) { throw 'Anki MSI ran but anki.exe could not be located' }
"ANKI_EXE=$exe" | Out-File -FilePath $env:GITHUB_ENV -Append -Encoding utf8
Write-Host "Anki exe found: $exe"
