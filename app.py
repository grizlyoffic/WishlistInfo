from Crypto.Cipher import AES
from Crypto.Util.Padding import pad
import binascii
import requests
from flask import Flask, jsonify, request
from GetWishListItems_pb2 import CSGetWishListItemsRes
import uid_generator_pb2
from datetime import datetime
import threading

app = Flask(__name__)
jwt_tokens = {}
jwt_lock = threading.Lock()

KEY = "Yg&tc%DEuh6%Zc^8"
IV = "6oyZDr22E3ychjM%"

# Regions that require JWT token (old script)
JWT_REGIONS = ["IND","BR","US","SAC","NA"]

# JWT API URLs per region (old)
REGION_JWT_API = {
    "IND": "https://jwt-convert.vercel.app/jwt?uid=4631484275&password=CZY-GFKNEZR1O-NEXU",
    "BR": "https://jwt-convert.vercel.app/jwt?uid=4631485903&password=CZY-XAN4FYHWY-NEXU",
    "US": "https://jwt-convert.vercel.app/jwt?uid=4631485903&password=CZY-XAN4FYHWY-NEXU",
    "SAC": "https://jwt-convert.vercel.app/jwt?uid=4631487930&password=CZY-MVWLNJGCY-NEXU",
    "NA": "https://jwt-convert.vercel.app/jwt?uid=4631489462&password=CZY-DLX0SNVML-NEXU",
    "default": "https://jwt-convert.vercel.app/jwt?uid=4631482509&password=CZY-4TNNHJIYS-NEXU"
}

# Region API endpoints
REGION_API_ENDPOINTS = {
    "IND": "https://client.ind.freefiremobile.com/GetWishListItems",
    "BR": "https://client.us.freefiremobile.com/GetWishListItems",
    "US": "https://client.us.freefiremobile.com/GetWishListItems",
    "SAC": "https://client.us.freefiremobile.com/GetWishListItems",
    "NA": "https://client.us.freefiremobile.com/GetWishListItems",
    "default": "https://clientbp.ggpolarbear.com/GetWishListItems"
}

def convert_timestamp(ts):
    return datetime.utcfromtimestamp(ts).strftime("%Y-%m-%d %H:%M:%S")

# Get JWT token from URL
def get_jwt(region):
    if region not in JWT_REGIONS:
        return None
    url = REGION_JWT_API.get(region, REGION_JWT_API["default"])
    try:
        res = requests.get(url, timeout=10)
        if res.status_code == 200:
            token = res.json().get("token")
            if token:
                jwt_tokens[region] = token
                return token
    except:
        return None
    return None

def ensure_jwt(region):
    token = jwt_tokens.get(region)
    if not token:
        return get_jwt(region)
    return token

def encrypt_aes(hexdata,key,iv):
    cipher = AES.new(key.encode()[:16],AES.MODE_CBC,iv.encode()[:16])
    padded = pad(bytes.fromhex(hexdata),AES.block_size)
    return binascii.hexlify(cipher.encrypt(padded)).decode()

def call_api(encrypted_hex,region,token):
    endpoint = REGION_API_ENDPOINTS.get(region,REGION_API_ENDPOINTS["default"])
    headers = {
        "User-Agent":"Dalvik/2.1.0 (Linux; U; Android 9)",
        "Authorization": f"Bearer {token}" if token else "",
        "X-Unity-Version":"2018.4.11f1",
        "ReleaseVersion":"OB52",
        "Content-Type":"application/x-www-form-urlencoded"
    }
    try:
        resp = requests.post(endpoint,data=bytes.fromhex(encrypted_hex),headers=headers,timeout=10)
        return resp.content.hex()
    except:
        return None

@app.route("/wishinfo")
def wish_info():
    uid = request.args.get("uid")
    if not uid:
        return jsonify({"error":"UID required"}),400

    # Try all JWT regions first
    for region in JWT_REGIONS:
        try:
            token = ensure_jwt(region)
            msg = uid_generator_pb2.uid_generator()
            msg.saturn_ = int(uid)
            msg.garena = 1
            hexdata = binascii.hexlify(msg.SerializeToString()).decode()
            encrypted = encrypt_aes(hexdata,KEY,IV)
            resp_hex = call_api(encrypted,region,token)
            if resp_hex:
                resp_bytes = bytes.fromhex(resp_hex)
                decoded = CSGetWishListItemsRes()
                decoded.ParseFromString(resp_bytes)
                wishlist = [{"item_id":i.item_id,"release_time":convert_timestamp(i.release_time)} for i in decoded.items]
                return jsonify({"uid":uid,"region":region,"wishlist":wishlist})
        except:
            continue

    # Fallback to default endpoint
    try:
        region = "default"
        msg = uid_generator_pb2.uid_generator()
        msg.saturn_ = int(uid)
        msg.garena = 1
        hexdata = binascii.hexlify(msg.SerializeToString()).decode()
        encrypted = encrypt_aes(hexdata,KEY,IV)
        resp_hex = call_api(encrypted,region,None)
        if resp_hex:
            resp_bytes = bytes.fromhex(resp_hex)
            decoded = CSGetWishListItemsRes()
            decoded.ParseFromString(resp_bytes)
            wishlist = [{"item_id":i.item_id,"release_time":convert_timestamp(i.release_time)} for i in decoded.items]
            return jsonify({"uid":uid,"region":region,"wishlist":wishlist})
    except:
        pass

    return jsonify({"error":"UID not found in any region."}),404
