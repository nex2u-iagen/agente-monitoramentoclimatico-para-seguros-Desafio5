"""Tools de notificacao do SeguraMente.

Expoe ferramentas de envio de notificacoes (email real e simulacao) como tools LangGraph.
Tools sao funcoes puras — logging e feito pelo supervisor.
"""

from __future__ import annotations

import json
import os
import smtplib
import uuid
from dataclasses import asdict
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from langchain_core.tools import tool

from ..database import get_database
from ..models import SimulationRecord, utc_now_iso

SMTP_FROM_NAME = "SeguraMente Seguros"
UNSUBSCRIBE_EMAIL = "nao-responda@seguramenteseguros.com.br"
COMPANY_ADDRESS = "Av. Paulista, 1000 — 12o andar — Sao Paulo, SP — CEP 01310-100"


@tool
def simulate_notification(message_json: str) -> str:
    """Simula o envio de uma notificacao preventiva sem disparar mensagem real.

    Use esta tool para registrar uma simulacao de envio no banco de dados.
    Nenhum canal externo (email, SMS, push) e acionado.

    Args:
        message_json: JSON string com os dados da mensagem gerada.

    Returns:
        JSON string com o registro da simulacao.
    """
    msg_dict = json.loads(message_json)
    db = get_database()

    record = SimulationRecord(
        simulation_id=f"SIM-{uuid.uuid4().hex[:10].upper()}",
        profile_id=msg_dict.get("profile_id", ""),
        channel=msg_dict.get("channel", ""),
        recipient=msg_dict.get("recipient", ""),
        text=msg_dict.get("text", ""),
        status="SIMULADO — nenhuma comunicacao real foi disparada",
        created_at=utc_now_iso(),
    )
    db.save_simulation(record)
    return json.dumps(asdict(record), default=str)


@tool
def send_email_notification(message_json: str) -> str:
    """Envia uma notificacao preventiva por email de forma real.

    Requer configuracao das variaveis de ambiente SMTP:
    SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD, SMTP_FROM.

    Args:
        message_json: JSON string com os dados da mensagem gerada.

    Returns:
        JSON string com o resultado do envio.
    """
    msg_dict = json.loads(message_json)
    recipient = msg_dict.get("recipient", "")
    text = msg_dict.get("text", "")
    profile_id = msg_dict.get("profile_id", "")
    db = get_database()

    smtp_host = os.getenv("SMTP_HOST", "")
    smtp_port = int(os.getenv("SMTP_PORT", "587"))
    smtp_user = os.getenv("SMTP_USER", "")
    smtp_password = os.getenv("SMTP_PASSWORD", "")
    smtp_from = os.getenv("SMTP_FROM", smtp_user)

    if not all([smtp_host, smtp_user, smtp_password]):
        record = SimulationRecord(
            simulation_id=f"SIM-{uuid.uuid4().hex[:10].upper()}",
            profile_id=profile_id,
            channel="email",
            recipient=recipient,
            text=text,
            status="FALLBACK — SMTP nao configurado, simulacao como fallback",
            created_at=utc_now_iso(),
        )
        db.save_simulation(record)
        return json.dumps(asdict(record), default=str)

    subject = "[TESTE] SeguraMente — Alerta Preventivo Meteorologico"
    html_body = _build_html_email(text, subject, profile_id)

    msg = MIMEMultipart("alternative")
    msg["From"] = f"{SMTP_FROM_NAME} <{smtp_from}>"
    msg["To"] = recipient
    msg["Subject"] = subject
    msg["Reply-To"] = smtp_from
    msg["List-Unsubscribe"] = f"<mailto:{UNSUBSCRIBE_EMAIL}?subject=Descadastrar>"
    msg["List-Unsubscribe-Post"] = "List-Unsubscribe=One-Click"
    msg["Precedence"] = "bulk"
    msg["X-Mailer"] = "SeguraMente-Notification-System/1.0"
    msg["X-Auto-Response-Suppress"] = "All"

    msg.attach(MIMEText(text, "plain", "utf-8"))
    msg.attach(MIMEText(html_body, "html", "utf-8"))

    try:
        with smtplib.SMTP(smtp_host, smtp_port, timeout=30) as server:
            server.starttls()
            server.login(smtp_user, smtp_password)
            server.send_message(msg)
        status = "ENVIADO — email HTML entregue com sucesso"
    except smtplib.SMTPAuthenticationError:
        status = (
            "FALLBACK — SMTP autenticacao falhou (App Password necessaria no Gmail com 2FA). "
            "Simulacao como fallback."
        )
    except (smtplib.SMTPException, OSError) as exc:
        status = f"FALLBACK — SMTP falhou ({exc}). Simulacao como fallback."

    record = SimulationRecord(
        simulation_id=f"ENV-{uuid.uuid4().hex[:10].upper()}",
        profile_id=profile_id,
        channel="email",
        recipient=recipient,
        text=f"[{subject}] {text}",
        status=status,
        created_at=utc_now_iso(),
    )
    db.save_simulation(record)
    return json.dumps(asdict(record), default=str)


def _build_html_email(plain_text: str, subject: str, recipient_name: str) -> str:
    """Constroi email HTML profissional com anti-spam e assinatura."""
    safe_text = (
        plain_text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace("\n", "<br>")
    )
    return f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <meta http-equiv="X-UA-Compatible" content="IE=edge">
  <title>{subject}</title>
</head>
<body style="margin:0;padding:0;background-color:#f4f4f4;font-family:Arial,Helvetica,sans-serif;">
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background-color:#f4f4f4;">
    <tr>
      <td align="center" style="padding:20px 0;">
        <table role="presentation" width="600" cellpadding="0" cellspacing="0" style="background-color:#ffffff;border-radius:8px;overflow:hidden;max-width:600px;">
          <tr>
            <td style="background-color:#1a5276;padding:24px 30px;text-align:center;">
              <h1 style="margin:0;color:#ffffff;font-size:22px;font-weight:700;letter-spacing:0.5px;">SEGURAMENTE SEGUROS</h1>
              <p style="margin:6px 0 0;color:#aed6f1;font-size:13px;">Comunicacao Preventiva</p>
            </td>
          </tr>
          <tr>
            <td style="background-color:#f39c12;padding:12px 30px;text-align:center;">
              <p style="margin:0;color:#ffffff;font-size:14px;font-weight:700;letter-spacing:1px;">
                &#9888; AVISO DE TESTE — Esta mensagem e uma simulacao do sistema
              </p>
            </td>
          </tr>
          <tr>
            <td style="padding:30px;">
              <p style="margin:0 0 16px;color:#333333;font-size:15px;line-height:1.6;">
                Prezado(a) <strong>{recipient_name}</strong>,
              </p>
              <p style="margin:0 0 20px;color:#333333;font-size:15px;line-height:1.6;">
                {safe_text}
              </p>
              <hr style="border:none;border-top:1px solid #eeeeee;margin:24px 0;">
              <p style="margin:0 0 8px;color:#666666;font-size:13px;font-style:italic;">
                Esta mensagem foi gerada automaticamente pelo sistema SeguraMente como parte de testes de integracao.
                Nenhuma acao e necessaria.
              </p>
            </td>
          </tr>
          <tr>
            <td style="background-color:#eaf2f8;padding:24px 30px;">
              <table role="presentation" width="100%" cellpadding="0" cellspacing="0">
                <tr>
                  <td style="color:#555555;font-size:12px;line-height:1.6;">
                    <strong style="color:#1a5276;">SeguraMente Seguros S.A.</strong><br>
                    {COMPANY_ADDRESS}<br>
                    CNPJ: 00.000.000/0001-00<br>
                    Telefone: (11) 3000-0000 | www.seguramenteseguros.com.br
                  </td>
                </tr>
              </table>
            </td>
          </tr>
          <tr>
            <td style="background-color:#d5e8f0;padding:12px 30px;text-align:center;">
              <p style="margin:0;color:#7f8c8d;font-size:11px;line-height:1.5;">
                Voce recebeu este email porque esta cadastrado nos sistemas da SeguraMente Seguros.<br>
                Para nao receber mais comunicacoes,
                <a href="mailto:{UNSUBSCRIBE_EMAIL}?subject=Descadastrar" style="color:#1a5276;text-decoration:underline;">clique aqui</a>.
              </p>
            </td>
          </tr>
        </table>
      </td>
    </tr>
  </table>
</body>
</html>"""
