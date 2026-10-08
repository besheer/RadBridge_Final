param([Parameter(Mandatory=$true)][string]$ServerUrl, [Parameter(Mandatory=$true)][string]$RadiAntPath)
$ErrorActionPreference = 'Stop'
$uri = [Uri]$ServerUrl
if ($uri.Scheme -ne 'https' -or -not $uri.Host -or $uri.UserInfo -or $uri.Query -or $uri.Fragment -or $uri.AbsolutePath -ne '/') { throw 'Specify the HTTPS RadBridge origin only.' }
$exe = [IO.Path]::GetFullPath($RadiAntPath)
if ($exe.StartsWith('\\') -or [IO.Path]::GetFileName($exe) -ne 'RadiAntViewer.exe' -or -not (Test-Path -LiteralPath $exe -PathType Leaf)) { throw 'Specify the installed RadiAntViewer.exe.' }
$folder = Join-Path $env:LOCALAPPDATA 'RadBridge\RadiAntBridge'
New-Item -ItemType Directory -Path $folder -Force | Out-Null
Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'Open-RadiAnt.ps1') -Destination $folder -Force
@{ServerOrigin=$uri.GetLeftPart([UriPartial]::Authority); RadiAntPath=$exe} | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $folder 'config.json') -Encoding UTF8
$registry = 'HKCU:\Software\Classes\radbridge-radiant'
New-Item -Path ($registry + '\shell\open\command') -Force | Out-Null
Set-Item -LiteralPath $registry -Value 'URL:RadBridge RadiAnt'
New-ItemProperty -LiteralPath $registry -Name 'URL Protocol' -Value '' -PropertyType String -Force | Out-Null
$shell = Join-Path $env:SystemRoot 'System32\WindowsPowerShell\v1.0\powershell.exe'
$command = '"' + $shell + '" -NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File "' + (Join-Path $folder 'Open-RadiAnt.ps1') + '" -LaunchUri "%1"'
Set-Item -LiteralPath ($registry + '\shell\open\command') -Value $command
Write-Output 'RadBridge RadiAnt launcher installed for this Windows user.'
