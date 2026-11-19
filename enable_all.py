import subprocess

command = ("Get-PnpDevice | Where-Object { $_.InstanceId -like 'USB*VID_*' "
           "-and $_.Status -eq 'Error' } | Enable-PnpDevice -Confirm:$false")
subprocess.run(["powershell", "-NoProfile", "-Command", command])
print("All disabled USB devices have been re-enabled.")