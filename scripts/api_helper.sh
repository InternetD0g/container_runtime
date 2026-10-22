api() {
    local METHOD="${1:-GET}"
    local ENDPOINT="${2:-/}"
    local DATA="${3:-}"
    local TOKEN=""

    if [ "$ENDPOINT" != "/login" ]; then
        TOKEN=$(~/auth.sh)
        if [ "$TOKEN" = "AUTH_REQUIRED" ]; then
            echo "Authorisation required."
            echo "Use: api POST /login '{\"username\":\"...\",\"password\":\"...\"}'"
            return 1
        fi
        if [[ ! "$TOKEN" == eyJ* ]]; then
            echo "Invalid token."
            return 1
        fi
    fi

    local CMD="/usr/bin/curl -s -X $METHOD -H 'Content-Type: application/json'"
    if [ -n "$TOKEN" ]; then
        CMD="$CMD -H 'Authorization: Bearer $TOKEN'"
    fi
    [ -n "$DATA" ] && CMD="$CMD -d '$DATA'"

    local RESPONSE
    RESPONSE=$(eval "$CMD http://127.0.0.1:8080$ENDPOINT")

    if [ "$ENDPOINT" = "/login" ] && echo "$RESPONSE" | /usr/bin/grep -q '"access_token"'; then
        echo "$RESPONSE" > "$HOME/.tokens.json"
    fi

    echo "$RESPONSE" | /usr/bin/python3 -m json.tool
}
