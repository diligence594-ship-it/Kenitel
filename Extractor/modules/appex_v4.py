import requests
import json
import cloudscraper
from pyrogram import filters
from Extractor import app
import os
import asyncio
import aiohttp
import base64
from Crypto.Cipher import AES
from Crypto.Util.Padding import unpad
from base64 import b64decode
from bs4 import BeautifulSoup
import time 
from config import CHANNEL_ID

log_channel = CHANNEL_ID
log_channel2 = CHANNEL_ID

SEMAPHORE = asyncio.Semaphore(5)
DEFAULT_USER_ID = "4300255"

def decrypt_appx(encrypted_text):
    if not encrypted_text:
        return ""
    try:
        clean_enc = str(encrypted_text).split("*")[0].split(":")[0]
        encrypted_bytes = b64decode(clean_enc)
        key = '638udh3829162018'.encode('utf-8')
        iv = 'fedcba9876543210'.encode('utf-8')
        
        cipher = AES.new(key, AES.MODE_CBC, iv)
        plaintext = unpad(cipher.decrypt(encrypted_bytes), AES.block_size)
        return plaintext.decode('utf-8').strip()
    except Exception:
        return str(encrypted_text)

def decode_base64(encoded_str):
    try:
        decoded_bytes = base64.b64decode(encoded_str)
        return decoded_bytes.decode('utf-8')
    except Exception:
        return ""

def extract_userid_from_token(token):
    try:
        payload_str = token.split('.')[1]
        payload_bytes = base64.b64decode(payload_str + '==')
        payload = json.loads(payload_bytes)
        return str(payload.get("id") or payload.get("userid") or payload.get("user_id") or DEFAULT_USER_ID)
    except Exception:
        return DEFAULT_USER_ID

def get_headers(token, user_id):
    return {
        "Client-Service": "Appx",
        "Auth-Key": "appxapi",
        "Authorization": token,
        "User-ID": str(user_id),
        "User-Agent": "okhttp/4.9.1",
        "source": "website"
    }

async def fetch(session, url, headers):
    async with SEMAPHORE:
        for attempt in range(3):
            try:
                async with session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=15)) as response:
                    if response.status == 429:
                        await asyncio.sleep(2)
                        continue
                    if response.status != 200:
                        return {}
                    content = await response.text()
                    try:
                        return json.loads(content)
                    except Exception:
                        soup = BeautifulSoup(content, 'html.parser')
                        return json.loads(str(soup))
            except Exception as e:
                print(f"Fetch error {url}: {str(e)}")
                await asyncio.sleep(1)
        return {}

async def handle_course(session, api_base, bi, si, sn, topic, hdr1):
    ti = topic.get("id") or topic.get("topicid") or topic.get("topic_id")
    tn = topic.get("name") or topic.get("topic_name") or "Topic"
    
    url_live = f"{api_base}/get/livecourseclassbycoursesubtopconceptapiv3?courseid={bi}&subjectid={si}&topicid={ti}&conceptid=&start=-1"
    url_db = f"{api_base}/get/dbcourseclassbycoursesubtopconceptapiv3?courseid={bi}&subjectid={si}&topicid={ti}&conceptid=&start=-1"
    
    r3_live, r3_db = await asyncio.gather(
        fetch(session, url_live, hdr1),
        fetch(session, url_db, hdr1),
        return_exceptions=True
    )
    
    video_data = []
    if isinstance(r3_live, dict) and r3_live.get("data"):
        video_data.extend(r3_live.get("data", []))
    if isinstance(r3_db, dict) and r3_db.get("data"):
        video_data.extend(r3_db.get("data", []))

    seen_ids = set()
    unique_videos = []
    for v in video_data:
        v_id = v.get("id") or v.get("video_id")
        if v_id and v_id not in seen_ids:
            seen_ids.add(v_id)
            unique_videos.append(v)

    tasks = [process_video(session, api_base, bi, si, sn, ti, tn, video, hdr1) for video in unique_videos]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    clean_results = []
    for lines in results:
        if isinstance(lines, list) and lines:
            clean_results.extend(lines)
    return clean_results

async def process_video(session, api_base, bi, si, sn, ti, tn, video, hdr1):
    vi = video.get("id") or video.get("video_id")
    lines = []
    
    try:
        r4 = await fetch(session, f"{api_base}/get/fetchVideoDetailsById?course_id={bi}&video_id={vi}&ytflag=0&folder_wise_course=0", hdr1)
        
        if not r4 or not r4.get("data"):
            return None

        data = r4.get("data", {})
        vt = (data.get("Title") or video.get("title") or video.get("name") or "Lecture").strip()
        vl = data.get("download_link", "")
        fl = data.get("video_id", "")
        
        if fl:
            dfl = decrypt_appx(fl)
            if dfl and not dfl.startswith("http") and len(dfl) < 25:
                lines.append(f"{vt}:https://youtu.be/{dfl}\n")

        if vl:
            dvl = decrypt_appx(vl)
            if dvl and ".pdf" not in dvl: 
                lines.append(f"{vt}:{dvl}\n")
        else:
            encrypted_links = data.get("encrypted_links", [])
            if encrypted_links:
                first_link = encrypted_links[0]
                a = first_link.get("path")
                k = first_link.get("key")
                if a and k:
                    da = decrypt_appx(a)
                    k1 = decrypt_appx(k)
                    k2 = decode_base64(k1)
                    lines.append(f"{vt}:{da}*{k2}\n")
                elif a:
                    da = decrypt_appx(a)
                    lines.append(f"{vt}:{da}\n")
        
        p1 = data.get("pdf_link", "")
        pk1 = data.get("pdf_encryption_key", "")
        p2 = data.get("pdf_link2", "")
        pk2 = data.get("pdf2_encryption_key", "")
        
        if p1:
            dp1 = decrypt_appx(p1)
            depk1 = decrypt_appx(pk1) if pk1 else ""
            if depk1 and depk1 != "abcdefg":
                lines.append(f"{vt}:{dp1}*{depk1}\n")
            else:
                lines.append(f"{vt}:{dp1}\n")

        if p2:
            dp2 = decrypt_appx(p2)
            depk2 = decrypt_appx(pk2) if pk2 else ""
            if depk2 and depk2 != "abcdefg":
                lines.append(f"{vt}:{dp2}*{depk2}\n")
            else:
                lines.append(f"{vt}:{dp2}\n")
                        
        return lines
    except Exception as e:
        print(f"Error processing video ID {vi}: {str(e)}")
        return None

@app.on_message(filters.command(["appx"]))
async def appex_v4_txt(app, message):
    api = await app.ask(message.chat.id, text="**SEND APPX API Without https://\n\n✅ Example:\ntcsexamzoneapi.classx.co.in or rozgarapinew.teachx.in**")
    api_txt = api.text.strip()
    name = api_txt.split('.')[0].replace("api", "") if api_txt else api_txt.split('.')[0]
    if "." in api_txt:
        await appex_v5_txt(app, message, api_txt, name)
    else:
        await app.send_message(message.chat.id, "❌ **INVALID API INPUT.**")

async def appex_v5_txt(app, message, api, name):
    api_base = api.replace("http://", "https://") if api.startswith(("http://", "https://")) else f"https://{api}"
    app_name = api_base.replace("https://", "").replace("http://", "").split('.')[0].capitalize()
    
    input1 = await app.ask(message.chat.id, f"SEND MOBILE NUMBER AND PASSWORD IN THIS FORMAT\n\n`MOBILE*PASSWORD`\n\nᴄᴏᴀᴄʜɪɴɢ ɴᴀᴍᴇ:- **{app_name}**\n\nOR DIRECTLY SEND YOUR **TOKEN**")
    raw_text = input1.text.strip()
    
    userid = DEFAULT_USER_ID
    token = ""
    
    if '*' in raw_text:
        email, password = raw_text.split("*", 1)
        raw_url = f"{api_base}/post/userLogin"
        headers = get_headers("", "-2")
        headers["Content-Type"] = "application/x-www-form-urlencoded"
        data = {"email": email, "password": password}
        
        try:
            response = requests.post(raw_url, data=data, headers=headers, timeout=15).json()
            status = response.get("status")

            if status == 200:
                userid = str(response["data"]["userid"])
                token = response["data"]["token"]
            elif status == 203:
                second_api_url = f"{api_base}/post/userLogin?extra_details=0"
                second_data = {
                    "source": "website",
                    "phone": email,
                    "email": email,
                    "password": password,
                    "extra_details": "1"
                }
                second_response = requests.post(second_api_url, headers=headers, data=second_data, timeout=15).json()
                if second_response.get("status") == 200:
                    userid = str(second_response["data"]["userid"])
                    token = second_response["data"]["token"]
        except Exception as e:
            print(f"Login error: {str(e)}")
            return await message.reply_text("❌ Login failed. Incorrect Credentials.")
    else:
        token = raw_text
        userid = extract_userid_from_token(token)

    if not token:
        return await message.reply_text("❌ Invalid Token provided.")

    hdr1 = get_headers(token, userid)
    scraper = cloudscraper.create_scraper() 
    mc1 = {}
    try:
        res = scraper.get(f"{api_base}/get/mycoursev2?userid={userid}", headers=hdr1, timeout=15)
        if res.status_code != 200:
            return await message.reply_text(f"❌ **Server Error ({res.status_code}):** Token is invalid or expired.")
        mc1 = res.json()
    except Exception as e:
        return await message.reply_text(f"❌ **Connection Error:** `{str(e)}`")
    
    FFF = "𝗕𝗔𝗧𝗖𝗛 𝗜𝗗 ➤ 𝗕𝗔𝗧𝗖𝗛 𝗡𝗔𝗠𝗘\n\n"
    valid_ids = []

    raw_courses = mc1.get("data", [])
    if isinstance(raw_courses, list) and len(raw_courses) > 0:
        for ct in raw_courses:
            ci = str(ct.get("id") or ct.get("course_id") or ct.get("courseid"))
            cn = ct.get("course_name") or ct.get("title") or ct.get("name") or "Untitled Batch"
            FFF += f"**`{ci}`   -   `{cn}`**\n\n"
            valid_ids.append(ci)
    else:
        return await message.reply_text("❌ **NO BATCH PURCHASED OR EXPIRED TOKEN.**")

    if len(FFF) <= 4096:
        editable1 = await message.reply_text(f"𝗔𝗽𝗽𝘅 𝗟𝗼𝗴𝗶𝗻 𝗦𝘂𝗰𝗲𝘀𝘀✅\n\n{FFF}")      
    else:
        plain_FFF = FFF.replace("**", "").replace("`", "")
        file_path = f"{app_name}.txt"
        with open(file_path, "w", encoding="utf-8") as file:
            file.write(f"𝗔𝗽𝗽𝘅 𝗟𝗼𝗴𝗶𝗻 𝗦𝘂𝗰𝗲𝘀𝘀✅ for {app_name}\n\nToken: {token}\n\n{plain_FFF}")
        await app.send_document(message.chat.id, document=file_path, caption="Select batch IDs from the file.")

    input2 = await app.ask(
        message.chat.id, 
        "**Send Batch ID(s) separated by '&' to download:**\n\n`" + "&".join(valid_ids) + "`"
    )

    batch_ids = [batch.strip() for batch in input2.text.strip().split("&") if batch.strip() in valid_ids]

    if not batch_ids:
        await message.reply_text("❌ **Invalid Batch ID(s).**")
        return

    m1 = await message.reply_text("⏳ **Processing requested batch(es)...**")

    for raw_text2 in batch_ids:
        m2 = await message.reply_text(f"🔄 **Extracting batch `{raw_text2}`...**")
        start_time = time.time()
        
        course_info = next((ct for ct in raw_courses if str(ct.get("id") or ct.get("course_id") or ct.get("courseid")) == raw_text2), {})
        course_name = course_info.get("course_name") or course_info.get("title") or "Course"
        start = course_info.get("start_date", "N/A")
        end = course_info.get("end_date", "N/A")
        pricing = course_info.get("price", "N/A")

        filename1 = f"{raw_text2}_{course_name.replace(':', '_').replace('/', '_')}.txt".replace(" ", "_")

        async with aiohttp.ClientSession() as session:
            extracted_lines = []
            
            try:
                # Primary Subject Endpoint
                r1 = await fetch(session, f"{api_base}/get/allsubjectfrmlivecourseclass?courseid={raw_text2}&start=-1", hdr1)
                subjects = r1.get("data", [])
                
                # Fallback Subject Endpoint if empty
                if not subjects:
                    r1_alt = await fetch(session, f"{api_base}/get/subjectbycourseid?course_id={raw_text2}", hdr1)
                    subjects = r1_alt.get("data", [])

                for subject in subjects:
                    si = subject.get("subjectid") or subject.get("id") or subject.get("subject_id")
                    sn = subject.get("subject_name") or subject.get("name") or "Subject"

                    r2 = await fetch(session, f"{api_base}/get/alltopicfrmlivecourseclass?courseid={raw_text2}&subjectid={si}&start=-1", hdr1)
                    topics = r2.get("data", [])
                    
                    if not topics:
                        r2_alt = await fetch(session, f"{api_base}/get/topicbysubjectid?subject_id={si}", hdr1)
                        topics = r2_alt.get("data", [])

                    tasks = [handle_course(session, api_base, raw_text2, si, sn, t, hdr1) for t in topics]
                    all_data = await asyncio.gather(*tasks, return_exceptions=True)
        
                    for data in all_data:
                        if isinstance(data, list) and data:
                            extracted_lines.extend(data)

            except Exception as e:
                print(f"Extraction error for batch {raw_text2}: {str(e)}")

            # File Write and Send Logic
            if extracted_lines:
                with open(filename1, 'w', encoding='utf-8') as f:
                    f.writelines(extracted_lines)
                    
                end_time = time.time()
                elapsed_time = end_time - start_time
                c_text = (
                    f"**APP NAME: {app_name}**\n"
                    f"**Batch Name:** {raw_text2}_{course_name}\n"
                    f"**Total Links:** {len(extracted_lines)}\n"
                    f"**Time Taken:** {elapsed_time:.1f}s"
                )
                
                try:
                    await app.send_document(message.chat.id, filename1, caption=c_text)
                except Exception as e:
                    print(f"Send document error: {str(e)}")
                finally:
                    if os.path.exists(filename1):
                        os.remove(filename1)
            else:
                await message.reply_text(f"⚠️ **Batch `{raw_text2}` is empty or has encrypted video layout not supported by standard APIs.**")

    try:
        await m1.delete(True)
        await m2.delete(True)
    except Exception:
        pass
