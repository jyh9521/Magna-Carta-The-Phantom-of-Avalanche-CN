function Convert-CompatibilityProfile {
    [CmdletBinding()]
    param([Parameter(Mandatory)][byte[]]$Settings)
    if ($Settings.Length -ne 52 -or $Settings[1] -gt 1) {
        throw 'Unsupported settings layout or renderer.'
    }
    [byte[]]$result = $Settings.Clone()
    # The source-verified renderer field: Direct3D=0, OpenGL=1.
    # DDrawCompat borderless mode does not cover the OpenGL path.
    $result[1] = 0
    return ,$result
}

function Get-CompatibilityHash {
    param([Parameter(Mandatory)][string]$Path)
    $stream = [IO.File]::OpenRead($Path)
    $algorithm = [Security.Cryptography.SHA256]::Create()
    try {
        return [BitConverter]::ToString($algorithm.ComputeHash($stream)).Replace('-', '').ToLowerInvariant()
    } finally {
        $algorithm.Dispose()
        $stream.Dispose()
    }
}
