param([Parameter(Mandatory=$true)][string]$LaunchUri, [switch]$ValidateOnly)
$ErrorActionPreference = 'Stop'
$partial = $null
try {
    $config = Get-Content -LiteralPath (Join-Path $PSScriptRoot 'config.json') -Raw | ConvertFrom-Json
    $origin = [Uri]$config.ServerOrigin
    $uri = [Uri]$LaunchUri
    if ($LaunchUri.Length -gt 16384 -or $uri.Scheme -ne 'radbridge-radiant' -or $uri.Host -ne 'open' -or $uri.UserInfo -or $uri.Fragment -or $uri.AbsolutePath -notin @('', '/')) { throw 'Invalid launch' }
    if ($uri.Query -notmatch '^\?url=([^&]+)$') { throw 'Invalid query' }
    $target = [Uri][Uri]::UnescapeDataString($Matches[1])
    if ($origin.Scheme -ne 'https' -or $target.Scheme -ne 'https' -or $target.UserInfo -or $target.Fragment -or $target.Query -or $target.GetLeftPart([UriPartial]::Authority) -ne $origin.GetLeftPart([UriPartial]::Authority)) { throw 'Invalid origin' }
    if ($target.AbsolutePath -notmatch '^/radiant-images/[1-9][0-9]{0,11}/[A-Za-z0-9_.-]{20,2048}/study\.zip$') { throw 'Invalid path' }
    if ($ValidateOnly) { Write-Output 'VALID'; exit 0 }
    $exe = [IO.Path]::GetFullPath([string]$config.RadiAntPath)
    if ($exe.StartsWith('\\') -or [IO.Path]::GetFileName($exe) -ne 'RadiAntViewer.exe' -or -not (Test-Path -LiteralPath $exe -PathType Leaf)) { throw 'RadiAnt unavailable' }
    Add-Type -AssemblyName System.Net.Http
    [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
    $handler = New-Object Net.Http.HttpClientHandler
    $handler.AllowAutoRedirect = $false
    $client = New-Object Net.Http.HttpClient($handler)
    $client.Timeout = [TimeSpan]::FromMinutes(10)
    try {
        $response = $client.GetAsync($target, [Net.Http.HttpCompletionOption]::ResponseHeadersRead).GetAwaiter().GetResult()
        try {
            if ([int]$response.StatusCode -ne 200 -or $response.Content.Headers.ContentType.MediaType -ne 'application/zip' -or $response.Content.Headers.ContentLength -gt 1GB) { throw 'Download refused' }
            $expected = ($response.Headers.GetValues('X-RadBridge-SHA256') | Select-Object -First 1)
            if ($expected -notmatch '^[a-f0-9]{64}$') { throw 'Missing checksum' }
            $cache = Join-Path $PSScriptRoot 'Cache'
            New-Item -ItemType Directory -Path $cache -Force | Out-Null
            $destination = Join-Path $cache (([Guid]::NewGuid().ToString('N')) + '.zip')
            $partial = $destination + '.partial'
            $inputStream = $response.Content.ReadAsStreamAsync().GetAwaiter().GetResult()
            $outputStream = [IO.File]::Open($partial, [IO.FileMode]::CreateNew, [IO.FileAccess]::Write, [IO.FileShare]::None)
            $sha = [Security.Cryptography.SHA256]::Create()
            try {
                $buffer = New-Object byte[] 1048576
                $size = [long]0
                while (($count = $inputStream.Read($buffer,0,$buffer.Length)) -gt 0) {
                    $size += $count
                    if ($size -gt 1GB) { throw 'Archive too large' }
                    $outputStream.Write($buffer,0,$count)
                    [void]$sha.TransformBlock($buffer,0,$count,$buffer,0)
                }
                [void]$sha.TransformFinalBlock((New-Object byte[] 0),0,0)
                $actual = [BitConverter]::ToString($sha.Hash).Replace('-','').ToLowerInvariant()
                if ($size -eq 0 -or $actual -ne $expected) { throw 'Checksum mismatch' }
            } finally { $outputStream.Dispose(); $inputStream.Dispose(); $sha.Dispose() }
            Move-Item -LiteralPath $partial -Destination $destination
            $partial = $null
            Start-Process -FilePath $exe -ArgumentList ('"' + $destination + '"') -WindowStyle Normal | Out-Null
        } finally { if ($response) { $response.Dispose() } }
    } finally { $client.Dispose(); $handler.Dispose() }
} catch {
    if ($partial -and (Test-Path -LiteralPath $partial)) { Remove-Item -LiteralPath $partial -Force }
    if (-not $ValidateOnly) {
        Add-Type -AssemblyName System.Windows.Forms
        [void][Windows.Forms.MessageBox]::Show('Unable to open images. Return to RadBridge to renew access; check RadiAnt installation and your connection.', 'RadBridge RadiAnt')
    }
    Write-Error 'RadBridge RadiAnt launch rejected.'
    exit 1
}
