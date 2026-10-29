"""SMTP com timeout e TLS explícitos; credenciais e tokens nunca são registrados."""

import smtplib
import ssl
from email.message import EmailMessage
from pathlib import Path

from settings import Settings, load_settings


def _send(message: EmailMessage, settings: Settings) -> None:
    if not settings.smtp_host:
        raise RuntimeError("SMTP_HOST não configurado")
    if settings.smtp_security == "ssl":
        connection = smtplib.SMTP_SSL(
            settings.smtp_host,
            settings.smtp_port,
            timeout=settings.smtp_timeout_seconds,
            context=ssl.create_default_context(),
        )
    else:
        connection = smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=settings.smtp_timeout_seconds)
    with connection as smtp:
        if settings.smtp_security == "starttls":
            smtp.starttls(context=ssl.create_default_context())
        if settings.smtp_user:
            smtp.login(settings.smtp_user, settings.smtp_password)
        smtp.send_message(message)


def send_transcription_email(
    to_email: str, file_path: Path, *, message_id: str | None = None, settings: Settings | None = None
) -> None:
    settings = settings or load_settings()
    message = EmailMessage()
    message["Subject"] = "Sua transcrição de áudio está pronta!"
    message["From"] = settings.smtp_from
    message["To"] = to_email
    if message_id:
        message["Message-ID"] = message_id
    message.set_content("Sua transcrição foi concluída. O arquivo solicitado encontra-se em anexo.")
    is_json = file_path.suffix.lower() == ".json"
    message.add_attachment(
        file_path.read_bytes(),
        maintype="application" if is_json else "text",
        subtype="json" if is_json else "plain",
        filename=file_path.name,
    )
    _send(message, settings)


def send_auth_code_email(to_email: str, token: str, *, settings: Settings | None = None) -> None:
    settings = settings or load_settings()
    message = EmailMessage()
    message["Subject"] = "Seu código de acesso para a API de Transcrição"
    message["From"] = settings.smtp_from
    message["To"] = to_email
    message.set_content(
        "Seu token de acesso para a API de transcrição:\n\n"
        f"{token}\n\n"
        f"Validade: {settings.jwt_ttl_seconds} segundos.\n"
        "Utilize o cabeçalho Authorization: Bearer SEU_TOKEN_AQUI.\n"
        "Se você não solicitou acesso, ignore esta mensagem."
    )
    _send(message, settings)
