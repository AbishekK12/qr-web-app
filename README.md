QR Web App



A simple Flask app that generates QR codes, saves images, and records metadata to MySQL.



Features

\- Generate QR from text or URL

\- Set box size and border

\- Choose foreground and background color

\- Optional logo overlay

\- Stores metadata in MySQL

\- View and download generated QR images

\- Download count tracking



Quick start

1\. Create virtual env

&nbsp;  python -m venv venv

&nbsp;  venv\\Scripts\\activate



2\. Install deps

&nbsp;  pip install -r requirements.txt



3\. Create MySQL DB and user

&nbsp;  CREATE DATABASE qrapp;

&nbsp;  CREATE USER 'qruser'@'localhost' IDENTIFIED BY 'StrongPass123';

&nbsp;  GRANT ALL PRIVILEGES ON qrapp.\* TO 'qruser'@'localhost';

&nbsp;  FLUSH PRIVILEGES;



&nbsp;  If needed:

&nbsp;  ALTER USER 'qruser'@'localhost' IDENTIFIED WITH mysql\_native\_password BY 'StrongPass123';

&nbsp;  FLUSH PRIVILEGES;



4\. Set DB URL and run

&nbsp;  PowerShell:

&nbsp;    $env:DATABASE\_URL = "mysql+pymysql://qruser:StrongPass123@localhost/qrapp"

&nbsp;    python qr\_web.py



&nbsp;  CMD:

&nbsp;    set DATABASE\_URL=mysql+pymysql://qruser:StrongPass123@localhost/qrapp

&nbsp;    python qr\_web.py



5\. Open browser

&nbsp;  http://127.0.0.1:5000



Project layout

\- qr\_web.py

\- generated/   (images, ignored)

\- uploads/     (logos, ignored)

\- venv/        (ignored)

\- requirements.txt

\- README.md

\- .gitignore



Notes

\- generated and uploads folders are not pushed to GitHub.

\- Do not commit secrets. Use env var for DATABASE\_URL in production.



