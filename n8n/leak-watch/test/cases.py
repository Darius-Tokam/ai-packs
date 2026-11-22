"""Données fictives, sans clé réelle. Usage : python cases.py boucle|propre|deux."""
import json
import sys
case = sys.argv[1] if len(sys.argv) > 1 else 'boucle'
if case == 'boucle':
    payload = {'scope': 'essai-leak-boucle', 'source': 'boucle fictive',
               'lines': ['HTTP 429 GET /v1?api_key=' + 'FAKE_' + 'Repetition23456789AbCdEf'] * 150}
elif case == 'propre':
    payload = {'scope': 'essai-leak-propre', 'source': 'journal sans fuite', 'lines': [
        'sort_key=created_at', 'token_count=1532 max_tokens=2048', 'GET /items?page=2&per_page=50',
        'key=[REDACTED]', 'Authorization: Bearer YOUR_TOKEN', 'api_key=****a1b2',
        'INFO password reset email sent', 'no-reply@example.com', 'client@example.org',
        'GET /promotion?code=WELCOME10', 'sha256=0123456789abcdef0123456789abcdef',
        'request_id=123e4567-e89b-12d3-a456-426614174000']}
elif case == 'deux':
    payload = {'scope': 'essai-leak-01', 'source': 'journal fictif', 'lines': [
        'INFO service prêt', 'GET /v1?api_key=' + 'FAKE_' + 'Ab12Cd34Ef56Gh78Ij90Kl12',
        'Authorization: Bearer ' + 'FAKE_' + 'TestOnly987654321abcdefgh']}
else:
    raise SystemExit('Cas inconnu : boucle, propre ou deux.')
print(json.dumps(payload, ensure_ascii=True))
