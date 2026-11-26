#!/usr/bin/env python3
"""Revisa la casilla por IMAP (solo lectura) y avisa por Telegram de cada mail nuevo.
Solo lee remitente, asunto y hora. No marca nada como leído ni guarda mails.
Estado: state.json guarda únicamente el último número de mail ya avisado."""
import imaplib, json, os, ssl, sys, urllib.parse, urllib.request
from email import message_from_bytes
from email.header import decode_header, make_header
from email.utils import parseaddr, parsedate_to_datetime
from zoneinfo import ZoneInfo

TZ = ZoneInfo("America/Argentina/Buenos_Aires")
SERVIDOR, PUERTO = os.environ["MAIL_HOST"], int(os.environ.get("MAIL_PORT", "143"))
ESTADO = "state.json"
MAX_AVISOS = 15


def tls():
    c = ssl.create_default_context()
    c.set_ciphers("DEFAULT:AES256-GCM-SHA384:AES128-GCM-SHA256:@SECLEVEL=1")
    return c


def telegram(texto):
    url = f"https://api.telegram.org/bot{os.environ['TG_TOKEN']}/sendMessage"
    datos = urllib.parse.urlencode({"chat_id": os.environ["TG_CHAT"], "text": texto}).encode()
    urllib.request.urlopen(urllib.request.Request(url, datos), timeout=20).read()


def txt(v):
    try:
        return str(make_header(decode_header(v or ""))).replace("\n", " ").strip()
    except Exception:
        return (v or "").strip()


def resumen(raw):
    msg = message_from_bytes(raw)
    nombre, mail = parseaddr(txt(msg.get("From")))
    de = f"{nombre} <{mail}>" if nombre and mail else (nombre or mail or "(sin remitente)")
    asunto = txt(msg.get("Subject")) or "(sin asunto)"
    try:
        hora = parsedate_to_datetime(msg.get("Date")).astimezone(TZ).strftime("%H:%M del %d/%m")
    except Exception:
        hora = "hora desconocida"
    return de, asunto, hora


def leer_estado():
    try:
        return json.load(open(ESTADO))
    except Exception:
        return {}


def guardar(**cambios):
    est = leer_estado()
    est.update(cambios)
    json.dump(est, open(ESTADO, "w"))


def main():
    m = imaplib.IMAP4(SERVIDOR, PUERTO, timeout=40)
    m.starttls(tls())
    m.login(os.environ["MAIL_USER"], os.environ["MAIL_PASS"])
    m.select("INBOX", readonly=True)
    validez = m.response("UIDVALIDITY")[1][0].decode()
    uids = [int(x) for x in (m.uid("search", None, "ALL")[1][0] or b"").split()]
    est = leer_estado()
    ultimo = est.get("ultimo_uid")
    if ultimo is None or est.get("uidvalidity") != validez:
        guardar(ultimo_uid=max(uids, default=0), uidvalidity=validez)
        telegram("✅ Aviso de correo activado. Desde ahora te aviso de cada mail nuevo de la casilla.")
        m.logout(); return
    nuevos = [u for u in uids if u > ultimo]
    omitidos = nuevos[:-MAX_AVISOS] if len(nuevos) > MAX_AVISOS else []
    if omitidos:
        telegram(f"📧 Llegaron {len(nuevos)} mails nuevos juntos; te detallo los últimos {MAX_AVISOS}.")
    for u in nuevos:
        if u in omitidos:
            continue
        d = m.uid("fetch", str(u), "(BODY.PEEK[HEADER.FIELDS (FROM SUBJECT DATE)])")[1]
        raw = next((p[1] for p in d if isinstance(p, tuple)), b"")
        de, asunto, hora = resumen(raw)
        telegram(f"📧 {de}\n{asunto}\n🕐 {hora}")
        guardar(ultimo_uid=u, uidvalidity=validez)
    if omitidos:
        guardar(ultimo_uid=nuevos[-1], uidvalidity=validez)
    m.logout()


FALLAS_PARA_AVISAR = 3  # ~6 min seguidos fallando, para no avisar por un corte de un instante


def vigilar():
    """Corre main(); si falla varias veces seguidas avisa una vez, y avisa cuando se recupera."""
    fallas = leer_estado().get("fallas", 0)
    try:
        main()
    except Exception as e:
        fallas += 1
        guardar(fallas=fallas)
        if fallas == FALLAS_PARA_AVISAR:
            try:
                telegram("⚠️ El aviso de correo está fallando: no pude revisar la casilla.\n"
                         f"Error: {type(e).__name__}: {str(e)[:200]}\n"
                         "Mientras tanto no vas a recibir avisos. Te escribo cuando se arregle.")
            except Exception:
                pass
        raise
    if fallas:
        if fallas >= FALLAS_PARA_AVISAR:
            telegram("✅ El aviso de correo volvió a funcionar.")
        guardar(fallas=0)


if __name__ == "__main__":
    vigilar()
