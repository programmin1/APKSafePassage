# APKSafePassage
Simple APK backup/restore. Have you ever installed an update on your Android and then, something broke with compatibility? You find you don't like the redesign? 
APKSafePassage is a way to keep the backup APKs on your computer for starting over on old version if necessary.

#Usage
Install "adb" command if you hadn't already. On Linux:

"sudo apt install adb"

Run this program:

"python3 ./APKSafePassage.py"

Select and download backup of apps. Select "restore" and choose the file to install directly to device.

If you run in to issues you may have to uninstall app (which would remove data). Always back up data before running an install again.

#Code
Code should run on any Python3 with TKinter. Built for Hacktoberfest '26 using Gemma4, Codex assistants.
