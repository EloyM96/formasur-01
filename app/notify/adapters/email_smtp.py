"""SMTP adapter that renders Jinja2 templates before sending emails."""
from __future__ import annotations

from dataclasses import dataclass, field
from email.message import EmailMessage
from pathlib import Path
from typing import Any, Callable, Mapping

import smtplib

try:  # pragma: no cover - prefer real Jinja2 when available
    from jinja2 import Environment, FileSystemLoader, TemplateNotFound, select_autoescape
except ModuleNotFoundError:  # pragma: no cover - fallback for lightweight test environments
    class TemplateNotFound(FileNotFoundError):
        """Fallback error matching the Jinja2 API."""

    class FileSystemLoader:  # type: ignore[override]
        def __init__(self, searchpath: Path | str | list[Path | str]):
            if isinstance(searchpath, (list, tuple)):
                self.searchpath = [Path(path) for path in searchpath]
            else:
                self.searchpath = [Path(searchpath)]

        def get_source(self, _environment, template: str):
            for base in self.searchpath:
                candidate = base / template
                if candidate.exists():
                    return candidate.read_text(encoding="utf-8"), str(candidate), lambda: True
            raise TemplateNotFound(template)

    class _FallbackTemplate:
        def __init__(self, source: str) -> None:
            self._source = source

        def render(self, context: Mapping[str, Any]) -> str:
            return _render_inline(self._source, context)

    class Environment:  # type: ignore[override]
        def __init__(self, loader: FileSystemLoader, **_kwargs) -> None:
            self.loader = loader

        def get_template(self, name: str) -> _FallbackTemplate:
            source, _, _ = self.loader.get_source(self, name)
            return _FallbackTemplate(source)

        def from_string(self, source: str) -> _FallbackTemplate:
            return _FallbackTemplate(source)

    def select_autoescape(_names):  # type: ignore[override]
        return False

DEFAULT_TEMPLATES_DIR = Path(__file__).resolve().parents[1] / "templates" / "email"


@dataclass(slots=True)
class EmailSMTPAdapter:
    """Render email templates and deliver them through an SMTP server."""

    host: str
    port: int
    username: str | None = None
    password: str | None = None
    from_email: str | None = None
    use_tls: bool = True
    templates_dir: Path = DEFAULT_TEMPLATES_DIR
    smtp_factory: Callable[[str, int], smtplib.SMTP] = smtplib.SMTP
    _env: Any = field(init=False, repr=False)

    def __post_init__(self) -> None:
        self._env = Environment(
            loader=FileSystemLoader(self.templates_dir),
            autoescape=select_autoescape(["html", "xml"]),
            trim_blocks=True,
            lstrip_blocks=True,
        )

    def send(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        action: dict[str, Any] = dict(payload.get("action") or {})
        context = payload.get("context") or {}
        playbook = payload.get("playbook")

        template_name = action.get("template")
        if not template_name:
            msg = "La acción de email necesita la clave 'template'"
            raise ValueError(msg)
        recipient = action.get("to")
        if not recipient:
            msg = "La acción de email necesita la clave 'to' con el destinatario"
            raise ValueError(msg)

        render_context = {
            "action": action,
            "context": context,
            "playbook": playbook,
            **context,
        }

        subject_template = action.get("subject") or "Notificación desde {{ playbook or 'PRL Notifier' }}"
        subject = self._env.from_string(subject_template).render(render_context).strip()
        text_template = self._env.get_template(f"{template_name}.txt")
        text_body = text_template.render(render_context)

        html_body = None
        try:
            html_template = self._env.get_template(f"{template_name}.html")
        except TemplateNotFound:
            html_body = None
        else:
            html_body = html_template.render(render_context)

        message = EmailMessage()
        message["To"] = str(recipient)
        message["From"] = action.get("from") or self.from_email or (self.username or "")
        message["Subject"] = subject

        if html_body:
            message.set_content(text_body or "")
            message.add_alternative(html_body, subtype="html")
        else:
            message.set_content(text_body or "")

        with self.smtp_factory(self.host, self.port) as client:
            if self.use_tls:
                client.starttls()
            if self.username:
                client.login(self.username, self.password or "")
            client.send_message(message)

        return {
            "status": "sent",
            "subject": subject,
            "to": message["To"],
            "template": template_name,
        }


_SAFE_GLOBALS = {"__builtins__": {}}


class _DotDict(dict):
    def __getattr__(self, item: str) -> Any:  # pragma: no cover - simple helper
        try:
            value = self[item]
        except KeyError as exc:
            raise AttributeError(item) from exc
        return _convert_value(value)


def _convert_value(value: Any) -> Any:
    if isinstance(value, dict):
        return _DotDict({key: _convert_value(val) for key, val in value.items()})
    if isinstance(value, list):
        return [_convert_value(item) for item in value]
    return value


def _render_inline(template: str, context: Mapping[str, Any]) -> str:
    locals_env = {key: _convert_value(val) for key, val in context.items()}
    result = template
    start = result.find("{{")
    while start != -1:
        end = result.find("}}", start)
        if end == -1:
            break
        expression = result[start + 2 : end].strip()
        try:
            value = eval(expression, _SAFE_GLOBALS, locals_env)
        except Exception:  # pragma: no cover - defensive
            value = ""
        replacement = "" if value is None else str(value)
        result = result[:start] + replacement + result[end + 2 :]
        start = result.find("{{", start + len(replacement))
    return result


__all__ = ["EmailSMTPAdapter"]
