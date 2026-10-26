# Stand-in for Microsoft's ArtifactSigning module (dry run only): takes the same
# parameters the template passes and signs with the runner's throwaway certificate.
function Invoke-ArtifactSigning {
    [CmdletBinding()]
    param(
        [string]$Endpoint, [string]$CodeSigningAccountName, [string]$CertificateProfileName,
        [Parameter(Mandatory)][string]$Files, [string]$FileDigest, [string]$TimestampRfc3161,
        [string]$TimestampDigest, [bool]$ExcludeEnvironmentCredential,
        [bool]$ExcludeWorkloadIdentityCredential, [bool]$ExcludeManagedIdentityCredential,
        [bool]$ExcludeSharedTokenCacheCredential, [bool]$ExcludeVisualStudioCredential,
        [bool]$ExcludeVisualStudioCodeCredential, [bool]$ExcludeAzurePowerShellCredential,
        [bool]$ExcludeAzureDeveloperCliCredential, [bool]$ExcludeInteractiveBrowserCredential
    )
    $cert = Get-ChildItem Cert:\CurrentUser\My -CodeSigningCert | Select-Object -First 1
    foreach ($file in $Files -split ',') {
        Write-Host "signing $file"
        $result = Set-AuthenticodeSignature -FilePath $file -Certificate $cert -HashAlgorithm SHA256
        if ($result.Status -ne 'Valid') { throw "could not sign ${file}: $($result.StatusMessage)" }
    }
}
Export-ModuleMember -Function Invoke-ArtifactSigning
