import os
import smtplib
from email.message import EmailMessage
from pathlib import Path

SMTP_HOST = os.environ.get("SMTP_HOST")
SMTP_PORT = int(os.environ.get("SMTP_PORT", 587))
SMTP_USER = os.environ.get("SMTP_USER")
SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD")
SMTP_FROM = os.environ.get("SMTP_FROM", "nao-responda@exemplo.com")

def send_transcription_email(to_email: str, file_path: Path):
    if not SMTP_HOST:
        print(f"[mail] SMTP_HOST não configurado. Simulação de envio para: {to_email}")
        return

    msg = EmailMessage()
    msg['Subject'] = 'Sua transcrição de áudio está pronta!'
    msg['From'] = SMTP_FROM
    msg['To'] = to_email
    
    msg.set_content(
        "Olá!\n\n"
        "Sua transcrição foi processada com sucesso. O arquivo solicitado encontra-se em anexo.\n\n"
        "Atenciosamente,\n"
        "Equipe Audio-to-Text"
    )
    
    # Define o subtipo baseado na extensão (.txt ou .json)
    extension = file_path.suffix.lower()
    subtype = "json" if extension == ".json" else "plain"
    
    with open(file_path, 'rb') as f:
        file_data = f.read()
        
    msg.add_attachment(
        file_data, 
        maintype='text', 
        subtype=subtype, 
        filename=file_path.name
    )

    try:
        # Tenta conectar e enviar usando STARTTLS
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            if SMTP_PORT == 587:
                server.starttls()
                
            if SMTP_USER and SMTP_PASSWORD:
                server.login(SMTP_USER, SMTP_PASSWORD)
                
            server.send_message(msg)
            print(f"[mail] E-mail enviado com sucesso para {to_email}")
    except Exception as e:
        print(f"[mail] Falha ao enviar e-mail para {to_email}: {e}")
        raise

def send_auth_code_email(to_email: str, token: str):
    if not SMTP_HOST:
        print(f"[mail] SMTP_HOST não configurado. Simulação de envio para: {to_email}. Token: {token}")
        return

    msg = EmailMessage()
    msg['Subject'] = 'Seu código de acesso para a API de Transcrição'
    msg['From'] = SMTP_FROM
    msg['To'] = to_email
    
    msg.set_content(
        "Olá!\n\n"
        "Você solicitou acesso à API de transcrição (Text & Audio Parser).\n\n"
        "Seu token de acesso é válido por 24 horas:\n"
        f"{token}\n\n"
        "Para utilizá-lo, passe o token no cabeçalho Authorization das suas requisições HTTP:\n"
        "Authorization: Bearer SEU_TOKEN_AQUI\n\n"
        "A requisição enviará automaticamente a transcrição finalizada para este e-mail.\n\n"
        "Atenciosamente,\n"
        "Equipe Audio-to-Text"
    )

    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            if SMTP_PORT == 587:
                server.starttls()
            if SMTP_USER and SMTP_PASSWORD:
                server.login(SMTP_USER, SMTP_PASSWORD)
            server.send_message(msg)
            print(f"[mail] E-mail de autorização enviado para {to_email}")
    except Exception as e:
        print(f"[mail] Falha ao enviar e-mail de autorização para {to_email}: {e}")
        raise
