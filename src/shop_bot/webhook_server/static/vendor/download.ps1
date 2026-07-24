$ProgressPreference = 'SilentlyContinue'
$base = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $base

$files = @{
 "tabler/css/tabler.min.css" = "https://cdn.jsdelivr.net/npm/@tabler/core@1.0.0-beta20/dist/css/tabler.min.css"
 "tabler/css/tabler-flags.min.css" = "https://cdn.jsdelivr.net/npm/@tabler/core@1.0.0-beta20/dist/css/tabler-flags.min.css"
 "tabler/css/tabler-payments.min.css" = "https://cdn.jsdelivr.net/npm/@tabler/core@1.0.0-beta20/dist/css/tabler-payments.min.css"
 "tabler/css/tabler-vendors.min.css" = "https://cdn.jsdelivr.net/npm/@tabler/core@1.0.0-beta20/dist/css/tabler-vendors.min.css"
 "tabler/css/tabler-icons.min.css" = "https://cdn.jsdelivr.net/npm/@tabler/icons-webfont@latest/tabler-icons.min.css"
 "tabler/js/tabler.min.js" = "https://cdn.jsdelivr.net/npm/@tabler/core@1.0.0-beta20/dist/js/tabler.min.js"
 "chartjs/chart.min.js" = "https://cdn.jsdelivr.net/npm/chart.js"
 "chartjs/chartjs-adapter-date-fns.bundle.min.js" = "https://cdn.jsdelivr.net/npm/chartjs-adapter-date-fns/dist/chartjs-adapter-date-fns.bundle.min.js"
 "flatpickr/flatpickr.min.css" = "https://cdn.jsdelivr.net/npm/flatpickr/dist/flatpickr.min.css"
 "flatpickr/dark.css" = "https://cdn.jsdelivr.net/npm/flatpickr/dist/themes/dark.css"
 "flatpickr/flatpickr.min.js" = "https://cdn.jsdelivr.net/npm/flatpickr"
 "flatpickr/ru.js" = "https://cdn.jsdelivr.net/npm/flatpickr/dist/l10n/ru.js"
 "sortablejs/Sortable.min.js" = "https://cdn.jsdelivr.net/npm/sortablejs@1.15.0/Sortable.min.js"
}

foreach ($k in $files.Keys) {
  $dir = Split-Path $k
  if ($dir -and !(Test-Path $dir)) { New-Item -ItemType Directory -Path $dir -Force | Out-Null }
  try {
    Invoke-WebRequest -Uri $files[$k] -OutFile $k -UseBasicParsing
    Write-Output "OK: $k"
  } catch {
    Write-Output "FAIL: $k -> $($_.Exception.Message)"
  }
}

# Fonts referenced by tabler-icons.min.css (relative ../fonts/tabler-icons.*)
if (!(Test-Path "tabler/fonts")) { New-Item -ItemType Directory -Path "tabler/fonts" -Force | Out-Null }
$fontFiles = @("tabler-icons.eot","tabler-icons.woff2","tabler-icons.woff","tabler-icons.ttf","tabler-icons.svg")
foreach ($f in $fontFiles) {
  $url = "https://cdn.jsdelivr.net/npm/@tabler/icons-webfont@latest/fonts/$f"
  try {
    Invoke-WebRequest -Uri $url -OutFile "tabler/fonts/$f" -UseBasicParsing
    Write-Output "OK: tabler/fonts/$f"
  } catch {
    Write-Output "FAIL: tabler/fonts/$f -> $($_.Exception.Message)"
  }
}

Write-Output "ALL DONE"
