param(
  [Parameter(Mandatory = $true)][string]$Path
)

$file = (Resolve-Path $Path).Path
$bytes = [IO.File]::ReadAllBytes($file)
if ($bytes.Length -lt 4096) {
  Write-Error "file is too small to hold a UniXNU log header: $($bytes.Length) bytes"
  exit 1
}

$magic = [Text.Encoding]::ASCII.GetString($bytes, 0, 8)
if ($magic -ne 'UNIXNULG') {
  Write-Host "No UniXNU log header (magic: '$magic')." -ForegroundColor Yellow
  Write-Host "The EFI never reached the userdata window, or the window was overwritten."
  exit 2
}

$version    = [BitConverter]::ToUInt32($bytes, 8)
$headerSize = [BitConverter]::ToUInt32($bytes, 12)
$textCap    = [BitConverter]::ToUInt32($bytes, 16)
$textBytes  = [BitConverter]::ToUInt32($bytes, 20)
$sequence   = [BitConverter]::ToUInt32($bytes, 24)
$partBytes  = [BitConverter]::ToUInt64($bytes, 32)
$regOffset  = [BitConverter]::ToUInt64($bytes, 40)

Write-Host "UniXNU boot log" -ForegroundColor Green
Write-Host ("  version    {0}" -f $version)
Write-Host ("  header     {0} bytes" -f $headerSize)
Write-Host ("  text       {0} / {1} bytes" -f $textBytes, $textCap)
Write-Host ("  sequence   {0}" -f $sequence)
Write-Host ("  userdata   {0} bytes, window at 0x{1:X}" -f $partBytes, $regOffset)
Write-Host ""

if ($headerSize -ne 4096) {
  Write-Warning "unexpected header size; decoding anyway at offset 4096"
}

$start = 4096
$length = [Math]::Min([int]$textBytes, $bytes.Length - $start)
if ($length -le 0) {
  Write-Host "(empty log)" -ForegroundColor Yellow
  exit 0
}

$text = [Text.Encoding]::UTF8.GetString($bytes, $start, $length)
$out = [IO.Path]::ChangeExtension($file, '.txt')
[IO.File]::WriteAllText($out, $text, (New-Object Text.UTF8Encoding $false))
Write-Host "Saved $out" -ForegroundColor Green
Write-Host ""
Write-Output $text
