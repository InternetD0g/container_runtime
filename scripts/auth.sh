#!/bin/bash
TOKEN_FILE="$HOME/.tokens.json"
KC_URL="http://192.168.56.10:8080/realms/containerd-auth/protocol/openid-connect/token"
CLIENT_ID="containerd-gateway"
CLIENT_SECRET="MyNewGatewaySecret2026"

get_exp() {
    /usr/bin/python3 -c "
import base64, json, sys
token = sys.argv[1]
try:
    payload = token.split('.')[1]
    padding = 4 - len(payload) % 4
    if padding != 4: payload += '=' * padding
    print(json.loads(base64.urlsafe_b64decode(payload))['exp'])
except: print(0)
" "$1" 2>/dev/null
}

if [ -f "$TOKEN_FILE" ]; then
    ACCESS=$(/usr/bin/python3 -c "import json; print(json.load(open('$TOKEN_FILE')).get('access_token',''))" 2>/dev/null)
    REFRESH=$(/usr/bin/python3 -c "import json; print(json.load(open('$TOKEN_FILE')).get('refresh_token',''))" 2>/dev/null)
    EXP=$(get_exp "$ACCESS")
    NOW=$(/bin/date +%s)

    if [ "$EXP" -gt 0 ] && [ "$((EXP - 60))" -gt "$NOW" ]; then
        echo "$ACCESS"
        exit 0
    fi

    if [ -n "$REFRESH" ] && [ "$REFRESH" != "null" ]; then
        RES=$(/usr/bin/curl -s -X POST "$KC_URL" \
            -d "grant_type=refresh_token&client_id=$CLIENT_ID&client_secret=$CLIENT_SECRET&refresh_token=$REFRESH")
        if echo "$RES" | /usr/bin/grep -q '"access_token"'; then
            echo "$RES" > "$TOKEN_FILE"
            /usr/bin/python3 -c "import json; print(json.load(open('$TOKEN_FILE'))['access_token'])"
            exit 0
        fi
    fi
fi

echo "AUTH_REQUIRED"
exit 1

