$mac = "BC-FC-E7-09-86-80"
$macBytes = ($mac -split "[:-]") | ForEach-Object { [byte]("0x$_") }
$packet = (,0xFF * 6) + ($macBytes * 16)

$udp = New-Object System.Net.Sockets.UdpClient
$udp.Connect("192.168.100.255",9)
$udp.Send($packet, $packet.Length)
$udp.Close()

Write-Host "WoL packet sent successfully to $mac"
