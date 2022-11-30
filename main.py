from base64 import b64decode
import json
import re
import requests
from Cryptodome.Cipher import AES
from Cryptodome.Protocol.KDF import PBKDF2
from Cryptodome.Hash import SHA256
import ffmpeg
import os
from tqdm import tqdm

# ID = "i3zqz9fhf69f"
ID = input("ENTER VIDEO ID:\n")

def write_to_file(string, file):
    with open(file, "w", encoding="utf-8") as file:
        file.write(str(string))

def decrypt_m3u8(msgn, cipher): 
    b64decoded = b64decode(cipher).decode()
    segments = b64decoded.split("-")
    secret = bytes(f'{msgn}{segments[0]}', encoding="utf-8")
    segments = segments[1:]
    segments = [bytes.fromhex(x) for x in segments]
    key = PBKDF2(secret, segments[0], 32, 1000, hmac_hash_module=SHA256)
    cipher = AES.new(key, AES.MODE_GCM, segments[1])
    res = cipher.decrypt(segments[2]).decode('utf-8', 'replace')
    return res


session = requests.Session()
session.headers = {
    "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9",
    "accept-encoding": "gzip, deflate, br",
    "accept-language": "en-US,en;q=0.9,fa;q=0.8,id;q=0.7,ps;q=0.6",
    "cache-control": "max-age=0",
    "cookie": "_ga=GA1.2.555325770.1667012237; _gid=GA1.2.969743052.1667193488",
    "referer": f"https://stream.biomaze.ir/{ID}/iframe",
    "sec-ch-ua": '"Chromium";v="106", "Google Chrome";v="106", "Not;A=Brand";v="99"',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"Windows"',
    "sec-fetch-dest": "document",
    "sec-fetch-mode": "navigate",
    "sec-fetch-site": "none",
    "sec-fetch-user": "?1",
    "upgrade-insecure-requests": '1',
    "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/106.0.0.0 Safari/537.36",
}

regex = re.compile(r"\|" + ID + r"\|(.*?)\|")

# GET IFRAME
res = session.get(f"https://stream.biomaze.ir/{ID}/iframe")
if res.status_code == 200:
    print("[INFO] SUCCESSFUL LOAD ON IFRAME")
else: 
    raise Exception("UNABLE TO FETCH IFRAME")

# GET EMBED
res = session.get(f"https://stream.biomaze.ir/{ID}/embed")
if res.status_code == 200:
    print("[INFO] SUCCESSFUL LOAD ON EMBED FILE")
else: 
    raise Exception("UNABLE TO FETCH EMBED FILE")
write_to_file(res.text, "embed.js")

# DECRYPT EMBED
quoteds = regex.findall(res.text)
encrypted_data = quoteds[0]
data_json = json.loads(b64decode(encrypted_data).decode("utf-8"))
write_to_file(json.dumps(data_json, indent=2), "index.json")

magic_id = quoteds[-1]
write_to_file(magic_id, "magic_id.txt")

# GET M3U8
res = session.get(f"https://stream.biomaze.ir/{data_json['playlist']}.m3u8")
cipher = res.text
if res.status_code == 200:
    print("[INFO] SUCCESSFUL LOAD ON PLAYLIST M3U8")
else: 
    raise Exception("UNABLE TO FETCH PLAYLIST M3U8")
write_to_file(cipher, "first_.txt")
m3u8 = decrypt_m3u8(data_json["msgn"], cipher)
write_to_file(m3u8, "first_decoded.txt")
play_lists = m3u8.split("#EXT-X-STREAM-INF:")[1:]

# CHOOSE VIDEO QUALITY
print("CHOOSE VIDEO QUALITY :")

for i, v in enumerate(play_lists):
    v = v[:v.index("m3u8") + 4]
    part = v.split("\n")
    play_lists[i] = part[1]
    print(f'{i} = {part[0].split("=")[-1]}')

index = input()

# GET RELEVANT PLAYLIST PARTS
res = session.get(play_lists[int(index)])
if res.status_code == 200:
    print("[INFO] SUCCESSFUL LOAD ON STREAM M3U8")
else: 
    raise Exception("UNABLE TO FETCH STREAM M3U8")
write_to_file(cipher, "second_.txt")
m3u8 = decrypt_m3u8(data_json["msgn"], res.text)
write_to_file(m3u8, "second_decoded.txt")

m3u8_data = m3u8.split("\n")

# GET DECRYPTION DATA
VIDEO_DECRYPTION_KEY = None
VIDEO_DECRYPTION_IV = None

BUFFER = 0
CIPHER = None

PARTS = []

for i, v in enumerate(m3u8_data):
    if "#EXT-X-KEY:" in v:
        v = v.split(",")
        for i in v:
            i = i.split("=")            
            if i[0] == "URI":
                uri = i[1][1:-1]
                print(f"KEY URI = {uri}")
                res = session.get(uri)
                VIDEO_DECRYPTION_KEY = res.content
                print(f"KEY = {VIDEO_DECRYPTION_KEY}")
            elif i[0] == "IV":
                iv = bytes.fromhex(i[1][2:])
                VIDEO_DECRYPTION_IV = iv 
                print(f"IV = {iv}")
        CIPHER = AES.new(VIDEO_DECRYPTION_KEY, AES.MODE_CBC, VIDEO_DECRYPTION_IV)
    elif "#EXTINF:" in v:
        link = m3u8_data[i+1]
        PARTS.append(link)


# START DOWNLOAD
Progress = tqdm(desc="Download", total=len(PARTS), unit="Part")

with open("vid", "wb") as file:
    for link in PARTS:
        res = session.get(link)
        data = res.content
        BUFFER += len(data)
        decrypted = CIPHER.decrypt(data)
        file.write(decrypted)
        Progress.update(1)

Progress.close()


# CONVERT VIDEO STREAM TO MP4 VIA FFMPEG
print(f"\nTOTAL SIZE [{BUFFER // 1048576}] MBs")
stream = ffmpeg.input("vid")
stream = ffmpeg.output(stream, "Video.mp4")
try:
    os.remove("Video.mp4")
except FileNotFoundError:
    pass
ffmpeg.run(stream)
os.remove("vid")
os.remove("embed.js")
os.remove("first_.txt")
os.remove("first_decoded.txt")
os.remove("index.json")
os.remove("magic_id.txt")
os.remove("second_.txt")
os.remove("second_decoded.txt")
