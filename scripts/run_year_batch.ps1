# Year-like Tier 0/1 batch runner for FBA-Bench
$ErrorActionPreference = 'Continue'

# Models to run
$models = @(
  'x-ai/grok-4-fast:free',
  'deepseek/deepseek-chat-v3.1:free',
  'deepseek/deepseek-r1-0528:free',
  'qwen/qwen3-coder:free',
  'google/gemini-2.0-flash-exp:free',
  'meta-llama/llama-3.3-70b-instruct:free',
  'cognitivecomputations/dolphin-mistral-24b-venice-edition:free',
  'openai/gpt-oss-20b:free',
  'moonshotai/kimi-k2:free',
  'cognitivecomputations/dolphin3.0-mistral-24b:free',
  'openai/gpt-oss-120b:free'
)

$timestamp = Get-Date -Format 'yyyyMMdd_HHmmss'
$dir = Join-Path 'artifacts\year_runs' $timestamp
New-Item -ItemType Directory -Force -Path $dir | Out-Null

$summary = Join-Path $dir 'summary.md'
"# Year-Like Runs Summary" | Out-File -FilePath $summary -Encoding utf8
("Timestamp: " + $timestamp) | Out-File -FilePath $summary -Append -Encoding utf8
"" | Out-File -FilePath $summary -Append -Encoding utf8

foreach ($tier in @('T0','T1')) {
  Add-Content -Path $summary -Value ("## " + $tier + " Results")
  foreach ($m in $models) {
    $safe = ($m -replace '[/:]','_')
    $log = Join-Path $dir ($tier + '_' + $safe + '.log')
    Write-Host ("Running " + $tier + " for " + $m + " ...")

    # Year-like pacing
    $env:SIM_MAX_TICKS = '365'
    $env:SIM_TICK_INTERVAL_SECONDS = '0.01'
    $env:SIM_TIME_ACCELERATION = '200'
    $env:MODEL_SLUG = $m

    if (-not $env:OPENROUTER_API_KEY) {
      Write-Error "OPENROUTER_API_KEY is missing in environment."
      Add-Content -Path $summary -Value ("- " + $m + ": FAIL (missing OPENROUTER_API_KEY)")
      continue
    }

    $psi = New-Object System.Diagnostics.ProcessStartInfo
    $psi.FileName = 'python'
    $psi.ArgumentList.Add('integration_tests/run_integration_tests.py')
    $psi.ArgumentList.Add('--tier'); $psi.ArgumentList.Add($tier)
    $psi.ArgumentList.Add('--model'); $psi.ArgumentList.Add($m)
    $psi.ArgumentList.Add('--max-ticks'); $psi.ArgumentList.Add('365')
    $psi.ArgumentList.Add('--tick-interval-seconds'); $psi.ArgumentList.Add('0.01')
    $psi.ArgumentList.Add('--time-acceleration'); $psi.ArgumentList.Add('200')
    $psi.ArgumentList.Add('--verbose')
    $psi.RedirectStandardOutput = $true
    $psi.RedirectStandardError = $true
    $psi.UseShellExecute = $false
    $psi.CreateNoWindow = $true

    # Propagate env crucial for OpenRouter and pacing
    $psi.Environment['OPENROUTER_API_KEY'] = $env:OPENROUTER_API_KEY
    if ($env:OPENROUTER_REFERER) { $psi.Environment['OPENROUTER_REFERER'] = $env:OPENROUTER_REFERER }
    if ($env:OPENROUTER_TITLE) { $psi.Environment['OPENROUTER_TITLE'] = $env:OPENROUTER_TITLE }
    $psi.Environment['SIM_MAX_TICKS'] = '365'
    $psi.Environment['SIM_TICK_INTERVAL_SECONDS'] = '0.01'
    $psi.Environment['SIM_TIME_ACCELERATION'] = '200'
    $psi.Environment['MODEL_SLUG'] = $m

    $proc = New-Object System.Diagnostics.Process
    $proc.StartInfo = $psi
    $null = $proc.Start()
    $stdOut = $proc.StandardOutput.ReadToEnd()
    $stdErr = $proc.StandardError.ReadToEnd()
    $proc.WaitForExit()
    $code = $proc.ExitCode

    ($stdOut + "`n" + $stdErr) | Out-File -FilePath $log -Encoding utf8

    $status = if ($code -eq 0) { 'PASS' } else { 'FAIL' }
    Add-Content -Path $summary -Value ("- " + $m + ": " + $status + " (log: " + [IO.Path]::GetFileName($log) + ")")
  }
  Add-Content -Path $summary -Value ""
}

Write-Host ("All runs complete. Summary at " + $summary)