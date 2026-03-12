from Crypto.Cipher import AES
from Crypto.Util.Padding import pad
import binascii
import requests
from flask import Flask, jsonify, request
from GetWishListItems_pb2 import CSGetWishListItemsRes
import uid_generator_pb2
import threading
from datetime import datetime

app = Flask(__name__)
jwt_tokens = {}  # region -> token
jwt_lock = threading.Lock()

# AES key & IV
KEY = "Yg&tc%DEuh6%Zc^8"
IV = "6oyZDr22E3ychjM%"

# Timestamp convert
def convert_timestamp(release_time):
    return datetime.utcfromtimestamp(release_time).strftime('%Y-%m-%d %H:%M:%S')

# Supported regions (for auto detection)
SUPPORTED_REGIONS = ["ME","IND","ID","VN","TH","BD","PK","TW","EU","RU","NA","SAC","BR"]

# Regions where JWT token is required
JWT_REGIONS = ["IND", "BR", "US", "SAC", "NA"]

# Region endpoints (host included)
REGION_API_ENDPOINTS = {
    "IND": "https://client.ind.freefiremobile.com/GetWishListItems",
    "BR": "https://client.us.freefiremobile.com/GetWishListItems",
    "US": "https://client.us.freefiremobile.com/GetWishListItems",
    "SAC": "https://client.us.freefiremobile.com/GetWishListItems",
    "NA": "https://client.us.freefiremobile.com/GetWishListItems",
    "default": "https://clientbp.ggpolarbear.com/GetWishListItems"
}

# JWT API URLs (old regions)
REGION_JWT_API = {
    "IND": "https://jwt-convert.vercel.app/jwt?uid=4631484275&password=CZY-GFKNEZR1O-NEXU",
    "BR": "https://jwt-convert.vercel.app/jwt?uid=4631485903&password=CZY-XAN4FYHWY-NEXU",
    "US": "https://jwt-convert.vercel.app/jwt?uid=4631485903&password=CZY-XAN4FYHWY-NEXU",
    "SAC": "https://jwt-convert.vercel.app/jwt?uid=4631487930&password=CZY-MVWLNJGCY-NEXU",
    "NA": "https://jwt-convert.vercel.app/jwt?uid=4631489462&password=CZY-DLX0SNVML-NEXU"
}

# Get JWT token
def get_jwt_token(region, uid):
    if region not in JWT_REGIONS:
        return None
    url_template = REGION_JWT_API.get(region)
    try:
        res = requests.get(url_template, timeout=10)
        if res.status_code == 200:
            token = res.json().get("token")
            if token:
                jwt_tokens[region] = token
                return token
    except:
        return None
    return None

def ensure_jwt_token(region, uid):
    token = jwt_tokens.get(region)
    if not token:
        return get_jwt_token(region, uid)
    return token

# AES encrypt
def encrypt_aes(hex_data, key, iv):
    key = key.encode()[:16]
    iv = iv.encode()[:16]
    cipher = AES.new(key, AES.MODE_CBC, iv)
    padded_data = pad(bytes.fromhex(hex_data), AES.block_size)
    encrypted_data = cipher.encrypt(padded_data)
    return binascii.hexlify(encrypted_data).decode()

# API call
def apis(encrypted_hex, region, token):
    endpoint = REGION_API_ENDPOINTS.get(region, REGION_API_ENDPOINTS["default"])
    headers = {
        'User-Agent': 'Dalvik/2.1.0 (Linux; U; Android 9)',
        'Connection': 'Keep-Alive',
        'Expect': '100-continue',
        'Authorization': f'Bearer {token}' if token else "",
        'X-Unity-Version': '2018.4.11f1',
        'X-GA': 'v1 1',
        'ReleaseVersion': 'OB52',
        'Content-Type': 'application/x-www-form-urlencoded',
    }
    try:
        data = bytes.fromhex(encrypted_hex)
        response = requests.post(endpoint, headers=headers, data=data, timeout=10)
        response.raise_for_status()
        return response.content.hex()
    except:
        return None

# Flask route
@app.route('/wishinfo', methods=['GET'])
def wish_info():
    uid = request.args.get('uid')
    if not uid:
        return jsonify({"error": "UID required"}), 400

    for region in SUPPORTED_REGIONS:
        try:
            token = ensure_jwt_token(region, uid) if region in JWT_REGIONS else None

            # Protobuf
            message = uid_generator_pb2.uid_generator()
            message.saturn_ = int(uid)
            message.garena = 1
            protobuf_data = message.SerializeToString()
            hex_data = binascii.hexlify(protobuf_data).decode()
            encrypted_hex = encrypt_aes(hex_data, KEY, IV)

            api_response_hex = apis(encrypted_hex, region, token)
            if api_response_hex:
                api_response_bytes = bytes.fromhex(api_response_hex)
                decoded_response = CSGetWishListItemsRes()
                decoded_response.ParseFromString(api_response_bytes)
                wishlist = [
                    {"item_id": item.item_id, "release_time": convert_timestamp(item.release_time)}
                    for item in decoded_response.items
                ]
                return jsonify({"uid": uid, "region": region, "wishlist": wishlist})
        except:
            continue

    return jsonify({"error": "UID not found in any region."}), 404

if __name__ == "__main__":
    # Proper host and port
    app.run(host="0.0.0.0", port=5552)