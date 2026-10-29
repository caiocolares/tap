from dataclasses import replace
from unittest.mock import MagicMock

import pytest

import mail
from settings import load_settings


@pytest.mark.parametrize("security", ["starttls", "ssl", "none"])
def test_smtp_uses_configured_transport_timeout_and_auth(monkeypatch, security, tmp_path):
    settings = replace(
        load_settings(),
        smtp_host="smtp.example.com",
        smtp_user="smtp-test",
        smtp_password="test-only",
        smtp_security=security,
        smtp_timeout_seconds=7,
    )
    connection = MagicMock()
    smtp = connection.return_value.__enter__.return_value
    monkeypatch.setattr(mail.smtplib, "SMTP", connection)
    monkeypatch.setattr(mail.smtplib, "SMTP_SSL", connection)
    output = tmp_path / "result.json"
    output.write_text('[{"text":"olá"}]', encoding="utf-8")
    mail.send_transcription_email("alice@example.com", output, message_id="<job@tap.local>", settings=settings)
    assert connection.call_args.kwargs["timeout"] == 7
    assert smtp.starttls.called == (security == "starttls")
    smtp.login.assert_called_once_with("smtp-test", "test-only")
    message = smtp.send_message.call_args.args[0]
    assert message["Message-ID"] == "<job@tap.local>"
    attachment = list(message.iter_attachments())[0]
    assert attachment.get_content_type() == "application/json"
    assert "olá" in attachment.get_payload(decode=True).decode()


def test_missing_smtp_never_logs_auth_token(capsys, caplog):
    settings = replace(load_settings(), smtp_host=None)
    token = "test-only-token-must-not-be-logged"
    with pytest.raises(RuntimeError, match="SMTP_HOST"):
        mail.send_auth_code_email("alice@example.com", token, settings=settings)
    captured = capsys.readouterr()
    assert token not in captured.out + captured.err + caplog.text
