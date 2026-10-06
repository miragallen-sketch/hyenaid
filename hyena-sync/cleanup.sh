#!/bin/bash
# Remove photos on the sync server that no hyena points at any more.
#
#   ./cleanup.sh
#
# Run this AFTER every device has synced. The server only knows about
# record changes it has received, so a photo an RA still uses but has
# not yet pushed would look unused and be deleted.

SERVER="https://hyena-sync.marahyenaproject.workers.dev"

read -rsp "Camp password: " KEY
echo

echo
echo "Before:"
curl -s -H "Authorization: Bearer $KEY" "$SERVER/api/stat" \
  | python3 -m json.tool 2>/dev/null || { echo "Could not reach the server, or the password is wrong."; exit 1; }

echo
read -rp "Delete every photo no hyena points at? (y/N) " YN
[[ "$YN" == "y" || "$YN" == "Y" ]] || { echo "Nothing done."; exit 0; }

echo
echo "Cleaning..."
curl -s -X POST -H "Authorization: Bearer $KEY" "$SERVER/api/gc" | python3 -m json.tool

echo
echo "After:"
curl -s -H "Authorization: Bearer $KEY" "$SERVER/api/stat" | python3 -m json.tool
