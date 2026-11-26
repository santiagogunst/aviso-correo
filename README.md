# Aviso de correo por Telegram

Revisa una casilla IMAP cada pocos minutos (GitHub Actions) y manda por Telegram
remitente, asunto y hora de cada mail nuevo. Solo lee encabezados, en modo lectura:
no marca mails como leídos ni guarda su contenido.

Configuración (Settings → Secrets → Actions): `MAIL_HOST`, `MAIL_USER`, `MAIL_PASS`,
`TG_TOKEN`, `TG_CHAT`.

`state.json` guarda solo el número interno del último mail avisado.
