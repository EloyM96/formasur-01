"""Notification adapters that communicate with external providers."""

from .cli import CLIAdapter
from .email_smtp import EmailSMTPAdapter
from .whatsapp_cli import WhatsAppCLIAdapter

__all__ = ["CLIAdapter", "EmailSMTPAdapter", "WhatsAppCLIAdapter"]
