# Healthcare Analytics Dashboard

## Build a standalone Windows app

On a Windows computer with Python 3 installed, run:

```powershell
.\build_windows.ps1
```

The script creates an isolated build environment, installs the dependencies
from `requirements.txt`, and creates `dist\HealthcareAnalytics.exe`. Share that
executable with clients; they do not need Python, pip, or the application's
Python modules installed.

The app stores its database and default CSV under
`%LOCALAPPDATA%\HealthcareAnalyticsDashboard`, so it can write data without
requiring write access to the executable's folder. Clients can import their CSV
dataset using the app; imports are split into database files of up to 500
records each. Use the database selector to browse a shard or all records, search
across the imported databases, and choose from ten visualization types.
