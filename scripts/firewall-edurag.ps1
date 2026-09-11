# Re-apply EduRAG LAN inbound rule. Run elevated.
$ErrorActionPreference = "Stop"
netsh advfirewall firewall delete rule name="EduRAG" | Out-Null
netsh advfirewall firewall add rule name="EduRAG" dir=in action=allow protocol=TCP localport=4747 profile=private | Out-Null
Write-Host "Inbound TCP 4747 allowed on Private profile only."
