"""
Rica Pro — 20hr WhatsApp Scheduler
Runs every hour via GitHub Actions.
Reads contacts_state.json, finds contacts due for a message,
sends via WhatsApp Cloud API, updates state file.
"""

import json
import os
import time
import requests
from datetime import datetime, timezone

# ── CONFIG ────────────────────────────────────────────────
TOKEN          = os.environ.get('WA_TOKEN', '')
PHONE_NUM_ID   = os.environ.get('WA_PHONE_NUMBER_ID', '119440352708700')
API_URL        = f'https://graph.facebook.com/v19.0/{PHONE_NUM_ID}/messages'
STATE_FILE     = 'contacts_state.json'
INTERVAL_HRS   = 20          # send every 20 hours
MAX_ATTEMPTS   = 3           # stop after 3 no-replies
BATCH_LIMIT    = 500         # max messages per run (rate limit safety)
COST_PER_MSG   = 0.0125      # USD per message in Colombia

# ── MESSAGE ROTATION ──────────────────────────────────────
FREE_MESSAGES = [
    "¡Hola {nombre}! 🌟 Oferta flash de hoy: Colágeno Marino 500g por solo $58.000 COP con envío GRATIS. Solo 15 unidades disponibles. ¿Te apartamos una? Responde QUIERO",
    "Buenos días {nombre} ☀️ Esta semana tenemos Creatina Pura 100g al 2x1 por $65.000. Envío gratis a toda Colombia. ¿Te interesa? https://ricapro.us",
    "¡{nombre}! Nueva llegada 🆕 Proteína de Suero 1kg solo $89.000 con envío gratis. Contraentrega disponible en toda Colombia. ¿Pedimos el tuyo?",
    "{nombre}, tienes un descuento de clienta frecuente: *15% OFF* en tu próximo pedido 🎁 Código: RICA15. Válido solo hoy. ¿Lo usamos?",
    "¡Hola {nombre}! 💪 María de Medellín bajó 4kg en 6 semanas con Rica Pro + caminar 30 min al día. ¿Quieres su rutina gratis? Responde RUTINA",
    "{nombre} ⏰ ÚLTIMA HORA: Colágeno + Vitamina C por $65.000 (precio normal $120.000). Solo hoy hasta las 8pm. ¿Lo aprovechamos?",
]

# ── LOAD / SAVE STATE ─────────────────────────────────────
def load_state():
    if not os.path.exists(STATE_FILE):
        print(f"[INFO] No state file found. Starting fresh.")
        return {"contacts": [], "run_log": []}
    with open(STATE_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)

def save_state(state):
    with open(STATE_FILE, 'w', encoding='utf-8') as f:
        json.dump(state, f, ensure_ascii=False, indent=2)

# ── SEND MESSAGE ──────────────────────────────────────────
def send_text_message(phone, text):
    """Send a free-form text message (only works within 24hr window)."""
    clean_phone = phone.replace(' ', '').replace('-', '').replace('+', '')
    if not clean_phone.startswith('57'):
        clean_phone = '57' + clean_phone.lstrip('0')
    
    payload = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": clean_phone,
        "type": "text",
        "text": {"preview_url": True, "body": text}
    }
    headers = {
        "Authorization": f"Bearer {TOKEN}",
        "Content-Type": "application/json"
    }
    try:
        r = requests.post(API_URL, json=payload, headers=headers, timeout=15)
        data = r.json()
        if 'messages' in data and data['messages']:
            return True, data['messages'][0]['id']
        else:
            err = data.get('error', {}).get('message', 'Unknown error')
            return False, err
    except Exception as e:
        return False, str(e)

def send_template_message(phone, template_name, lang_code='es'):
    """Send a paid template message (works outside 24hr window)."""
    clean_phone = phone.replace(' ', '').replace('-', '').replace('+', '')
    if not clean_phone.startswith('57'):
        clean_phone = '57' + clean_phone.lstrip('0')
    
    payload = {
        "messaging_product": "whatsapp",
        "to": clean_phone,
        "type": "template",
        "template": {
            "name": template_name,
            "language": {"code": lang_code}
        }
    }
    headers = {
        "Authorization": f"Bearer {TOKEN}",
        "Content-Type": "application/json"
    }
    try:
        r = requests.post(API_URL, json=payload, headers=headers, timeout=15)
        data = r.json()
        if 'messages' in data and data['messages']:
            return True, data['messages'][0]['id']
        else:
            err = data.get('error', {}).get('message', 'Unknown error')
            return False, err
    except Exception as e:
        return False, str(e)

# ── MAIN SCHEDULER ────────────────────────────────────────
def run_scheduler():
    now_ts = time.time()
    now_str = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')
    print(f"\n{'='*50}")
    print(f"Rica Pro Scheduler — {now_str}")
    print(f"{'='*50}")

    if not TOKEN:
        print("[ERROR] WA_TOKEN secret not set in GitHub repository secrets!")
        return

    state = load_state()
    contacts = state.get('contacts', [])
    
    sent_count    = 0
    skipped_cold  = 0
    skipped_window = 0
    errors        = 0
    total_cost    = 0.0

    for contact in contacts:
        if sent_count >= BATCH_LIMIT:
            print(f"[INFO] Batch limit {BATCH_LIMIT} reached. Remaining contacts deferred.")
            break

        status = contact.get('status', 'active')

        # Skip cold and converted contacts
        if status in ('cold', 'converted'):
            skipped_cold += 1
            continue

        phone        = contact.get('phone', '')
        name         = contact.get('name', 'amiga')
        first_name   = name.split()[0] if name else 'amiga'
        last_msg_ts  = contact.get('last_msg_sent_ts', 0)
        last_reply_ts = contact.get('last_reply_ts', 0)
        hours_since_msg = (now_ts - last_msg_ts) / 3600 if last_msg_ts else 999
        hours_since_reply = (now_ts - last_reply_ts) / 3600 if last_reply_ts else 999
        window_open  = hours_since_reply < 24
        attempts     = contact.get('no_reply_attempts', 0)
        msg_index    = contact.get('msg_rotation_index', 0)

        # Check if 20 hours have passed since last message
        if hours_since_msg < INTERVAL_HRS:
            skipped_window += 1
            continue

        # Too many no-replies → move to cold
        if attempts >= MAX_ATTEMPTS and not window_open:
            contact['status'] = 'cold'
            print(f"[COLD] {name} ({phone}) — {attempts} no-replies. Moved to cold list.")
            skipped_cold += 1
            continue

        # Choose message type
        if window_open:
            # Free message — within 24hr window
            msg_text = FREE_MESSAGES[msg_index % len(FREE_MESSAGES)]
            msg_text = msg_text.replace('{nombre}', first_name)
            success, result = send_text_message(phone, msg_text)
            msg_type = 'free'
        else:
            # Window expired — send paid template to reopen
            success, result = send_template_message(phone, 'bog', 'es')
            msg_type = 'template (paid)'
            total_cost += COST_PER_MSG

        # Update contact state
        if success:
            contact['last_msg_sent_ts'] = now_ts
            contact['msg_rotation_index'] = (msg_index + 1) % len(FREE_MESSAGES)
            contact['last_msg_id'] = result
            if not window_open:
                contact['no_reply_attempts'] = attempts + 1
            sent_count += 1
            print(f"[OK]  {name} ({phone}) — {msg_type} — ID: {result[:20]}...")
        else:
            errors += 1
            print(f"[ERR] {name} ({phone}) — {result}")

        # Small delay to respect API rate limits
        time.sleep(0.1)

    # Log this run
    run_entry = {
        "timestamp": now_str,
        "sent": sent_count,
        "errors": errors,
        "skipped_cold": skipped_cold,
        "skipped_window": skipped_window,
        "cost_usd": round(total_cost, 4),
        "total_contacts": len(contacts)
    }
    state.setdefault('run_log', []).append(run_entry)
    # Keep only last 100 log entries
    state['run_log'] = state['run_log'][-100:]

    save_state(state)

    print(f"\n── Summary ──────────────────────────────")
    print(f"  Sent:           {sent_count}")
    print(f"  Errors:         {errors}")
    print(f"  Skipped (cold): {skipped_cold}")
    print(f"  Skipped (wait): {skipped_window}")
    print(f"  Cost this run:  ${total_cost:.4f} USD")
    print(f"  State saved to: {STATE_FILE}")
    print(f"{'='*50}\n")

if __name__ == '__main__':
    run_scheduler()
