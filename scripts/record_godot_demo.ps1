param(
  [string]$Output = "artifacts/promo/fba_bench_demo.mp4",
  [string]$WindowTitle = "FBA-Bench-Enterprise-GUI",

  [string]$Host = "127.0.0.1",
  [int]$Port = 8000,
  [switch]$NoBackend,
  [switch]$Reload,
  [int]$WaitForWindowSeconds = 3,

  [string]$Scenario = "",
  [string]$Agent = "",
  [int]$Seed = 42,
  [int]$MaxTicks = 365,
  [double]$Speed = 1.0,

  [double]$StartDelaySeconds = 3.0,
  [double]$EndHoldSeconds = 4.0,

  [int]$Fps = 60,
  [string]$GodotExe = ""
)

$ErrorActionPreference = "Stop"

if (-not (Get-Command ffmpeg -ErrorAction SilentlyContinue)) {
  throw "ffmpeg not found in PATH."
}

$outPath = Resolve-Path -LiteralPath (Split-Path -Parent $Output) -ErrorAction SilentlyContinue
if (-not $outPath) {
  New-Item -ItemType Directory -Force -Path (Split-Path -Parent $Output) | Out-Null
}

$doneFile = Join-Path (Split-Path -Parent $Output) "demo_done.txt"
if (Test-Path -LiteralPath $doneFile) { Remove-Item -LiteralPath $doneFile -Force }

# Demo automation env consumed by Godot GUI (SimulationViewer.gd)
$env:FBA_BENCH_DEMO_AUTOSTART = "1"
$env:FBA_BENCH_DEMO_AUTOQUIT = "1"
$env:FBA_BENCH_DEMO_CINEMATIC = "1"
$env:FBA_BENCH_DEMO_DONE_FILE = $doneFile
$env:FBA_BENCH_DEMO_SEED = "$Seed"
$env:FBA_BENCH_DEMO_MAX_TICKS = "$MaxTicks"
$env:FBA_BENCH_DEMO_SPEED = "$Speed"
$env:FBA_BENCH_DEMO_START_DELAY_SECONDS = "$StartDelaySeconds"
$env:FBA_BENCH_DEMO_ENDCARD_HOLD_SECONDS = "$EndHoldSeconds"
if ($Scenario -ne "") { $env:FBA_BENCH_DEMO_SCENARIO = $Scenario }
if ($Agent -ne "") { $env:FBA_BENCH_DEMO_AGENT = $Agent }

if ($GodotExe -ne "") {
  $env:GODOT_EXE = $GodotExe
}

# Compute an expected duration (seconds) so ffmpeg can exit cleanly without being killed.
# The backend default tick_interval is 0.1s and the API scales it by 1/speed when "speed" is provided.
$baseTickInterval = 0.1
$effectiveSpeed = [math]::Max([double]$Speed, 0.1)
$tickInterval = $baseTickInterval / $effectiveSpeed
$duration = [math]::Ceiling(($StartDelaySeconds + ($MaxTicks * $tickInterval) + $EndHoldSeconds + 8.0))

Write-Host "Recording demo video..."
Write-Host "  Output: $Output"
Write-Host "  Duration (s): $duration"
Write-Host "  Window title: $WindowTitle"

$launcherArgs = @("--host", $Host, "--port", "$Port")
if ($NoBackend) { $launcherArgs += "--no-backend" }
if ($Reload) { $launcherArgs += "--reload" }
if ($GodotExe -ne "") { $launcherArgs += @("--godot", $GodotExe) }

# Start the GUI (and backend if needed) in the background.
$launchProc = Start-Process -FilePath "poetry" -ArgumentList (@("run", "python", "launch_godot_gui.py") + $launcherArgs) -PassThru

Start-Sleep -Seconds $WaitForWindowSeconds

# Capture just the Godot window by title. If this fails on your machine, try:
# - recording "desktop" and cropping
# - setting -WindowTitle to the actual runtime title
$ffmpegArgs = @(
  "-y",
  "-f", "gdigrab",
  "-framerate", "$Fps",
  "-i", "title=$WindowTitle",
  "-t", "$duration",
  "-c:v", "libx264",
  "-preset", "veryfast",
  "-pix_fmt", "yuv420p",
  "-movflags", "+faststart",
  $Output
)

& ffmpeg @ffmpegArgs | Out-Host

Wait-Process -Id $launchProc.Id -ErrorAction SilentlyContinue

if (Test-Path -LiteralPath $doneFile) {
  Write-Host "Demo completed (done file present): $doneFile"
} else {
  Write-Host "Demo finished (done file not found): $doneFile"
}

Write-Host "Wrote: $Output"
