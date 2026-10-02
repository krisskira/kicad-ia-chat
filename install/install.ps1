# Instala KiCad IA en Documentos\KiCad\<versión>\plugins\kicad-ia
[CmdletBinding()]
param(
    [string]$Version = "",
    [string]$KicadVersion = "",
    [switch]$Uninstall,
    [switch]$Help
)

$ErrorActionPreference = "Stop"
$Repo = if ($env:KICAD_IA_REPO) { $env:KICAD_IA_REPO } else { "krisskira/kicad-ia-chat" }
$Api = "https://api.github.com/repos/$Repo"

function Show-Usage {
    @"
Uso: install.ps1 [-Version X.Y.Z] [-KicadVersion V] [-Uninstall] [-Help]

  -Version X.Y.Z       Versión del plugin (por defecto: último release)
  -KicadVersion V      Carpeta de KiCad (por ejemplo 10.0). Por defecto: la más nueva
  -Uninstall           Quita plugins\kicad-ia
  -Help                Esta ayuda

Ejemplos:
  irm https://raw.githubusercontent.com/krisskira/kicad-ia-chat/main/install/install.ps1 | iex
  .\install.ps1 -Version 0.1.0 -KicadVersion 10.0
"@
}

if ($Help) {
    Show-Usage
    return
}

function Get-DocumentsDir {
    [Environment]::GetFolderPath("MyDocuments")
}

function Get-KicadRoot {
    Join-Path (Get-DocumentsDir) "KiCad"
}

function Get-KicadVersions {
    $root = Get-KicadRoot
    if (-not (Test-Path -LiteralPath $root)) {
        return @()
    }
    Get-ChildItem -LiteralPath $root -Directory |
        Sort-Object { [version]($_.Name -replace '[^\d.].*$', '') } -ErrorAction SilentlyContinue |
        ForEach-Object { $_.Name }
}

function Resolve-KicadVersion {
    if ($KicadVersion) {
        return $KicadVersion
    }
    $versions = @(Get-KicadVersions)
    if ($versions.Count -eq 0) {
        throw "No hay $(Get-KicadRoot)\<versión>. Abre KiCad una vez y vuelve a ejecutar."
    }
    return $versions[-1]
}

function Get-PluginsDir([string]$Kver) {
    Join-Path (Join-Path (Get-KicadRoot) $Kver) "plugins"
}

function Uninstall-Plugin {
    $kver = Resolve-KicadVersion
    $plugins = Get-PluginsDir $kver
    $target = Join-Path $plugins "kicad-ia"
    $bak = Join-Path $plugins "kicad-ia.bak"
    if (Test-Path -LiteralPath $target) {
        Remove-Item -LiteralPath $target -Recurse -Force
        Write-Host "Eliminado $target"
    } else {
        Write-Host "No está instalado en $target"
    }
    if (Test-Path -LiteralPath $bak) {
        Remove-Item -LiteralPath $bak -Recurse -Force
        Write-Host "Eliminado $bak"
    }
}

function Get-LatestTag {
    $release = Invoke-RestMethod -Uri "$Api/releases/latest" -Headers @{ "User-Agent" = "kicad-ia-install" }
    return [string]$release.tag_name
}

function Resolve-Tag {
    if ($Version) {
        if ($Version.StartsWith("v")) { return $Version }
        return "v$Version"
    }
    $tag = Get-LatestTag
    if (-not $tag) {
        throw "No hay releases en $Repo"
    }
    return $tag
}

function Get-FileSha256([string]$Path) {
    (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToLowerInvariant()
}

function Assert-Checksum([string]$FilePath, [string]$SumsPath) {
    $name = Split-Path -Leaf $FilePath
    $expected = $null
    foreach ($line in Get-Content -LiteralPath $SumsPath) {
        $parts = $line.Trim() -split '\s+', 2
        if ($parts.Count -eq 2 -and $parts[1] -eq $name) {
            $expected = $parts[0].ToLowerInvariant()
            break
        }
    }
    if (-not $expected) {
        throw "SHA256SUMS no incluye $name"
    }
    $actual = Get-FileSha256 $FilePath
    if ($actual -ne $expected) {
        throw "Checksum incorrecto para $name`n  esperado: $expected`n  obtenido: $actual"
    }
    Write-Host "Checksum OK ($name)"
}

function Install-Plugin {
    $tag = Resolve-Tag
    $ver = $tag.TrimStart("v")
    $kver = Resolve-KicadVersion
    $plugins = Get-PluginsDir $kver
    $zipName = "kicad-ia-$ver.zip"
    $assetBase = "https://github.com/$Repo/releases/download/$tag"

    Write-Host "Release: $tag"
    Write-Host "KiCad:   $kver -> $plugins"

    New-Item -ItemType Directory -Force -Path $plugins | Out-Null
    $tmp = Join-Path ([System.IO.Path]::GetTempPath()) ("kicad-ia-install-" + [guid]::NewGuid().ToString("n"))
    New-Item -ItemType Directory -Force -Path $tmp | Out-Null
    try {
        $zipPath = Join-Path $tmp $zipName
        $sumsPath = Join-Path $tmp "SHA256SUMS"
        Write-Host "Descargando $zipName…"
        Invoke-WebRequest -Uri "$assetBase/$zipName" -OutFile $zipPath -UseBasicParsing
        Invoke-WebRequest -Uri "$assetBase/SHA256SUMS" -OutFile $sumsPath -UseBasicParsing
        Assert-Checksum -FilePath $zipPath -SumsPath $sumsPath

        $extract = Join-Path $tmp "extract"
        Expand-Archive -LiteralPath $zipPath -DestinationPath $extract -Force
        if (-not (Test-Path -LiteralPath (Join-Path $extract "plugin.json"))) {
            throw "El ZIP no tiene plugin.json en la raíz"
        }

        $target = Join-Path $plugins "kicad-ia"
        $bak = Join-Path $plugins "kicad-ia.bak"
        if (Test-Path -LiteralPath $target) {
            if (Test-Path -LiteralPath $bak) {
                Remove-Item -LiteralPath $bak -Recurse -Force
            }
            Move-Item -LiteralPath $target -Destination $bak
            Write-Host "Copia anterior en $bak"
        }
        New-Item -ItemType Directory -Force -Path $target | Out-Null
        Copy-Item -Path (Join-Path $extract "*") -Destination $target -Recurse -Force

        Write-Host "Instalado en $target"
        Write-Host "Reinicia KiCad, abre el editor de PCB y pulsa KiCad IA."
        Write-Host "La primera vez hace falta red: KiCad instala requirements.txt."
    }
    finally {
        Remove-Item -LiteralPath $tmp -Recurse -Force -ErrorAction SilentlyContinue
    }
}

if ($Uninstall) {
    Uninstall-Plugin
} else {
    Install-Plugin
}
