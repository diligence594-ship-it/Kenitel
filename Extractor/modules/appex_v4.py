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
from Extractor.modules.mix import v2_new
from Crypto.Util.Padding import unpad
from base64 import b64decode
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor
import time 
from config import CHANNEL_ID

log_channel = CHANNEL_ID
log_channel2 = CHANNEL_ID

# Concurrent requests ko control karne ke liye rate limiter
SEMAPHORE = asyncio.Semaphore(5)

def decrypt(enc):
    try:
        enc = b64decode(str(enc).split(':')[0])
        key = '638udh3829162018'.encode('utf-8')
        iv = 'fedcba9876543210'.encode('utf-8')
        if len(enc) == 0:
            return ""
        cipher = AES.new(key, AES.MODE_CBC, iv)
        plaintext = unpad(cipher.decrypt(enc), AES.block_size)
        return plaintext.decode('utf-8')
    except Exception:
        return ""

def decode_base64(encoded_str):
    try:
        decoded_bytes = base64.b64decode(encoded_str)
        return decoded_bytes.decode('utf-8')
    except Exception as e:
        return f"Error decoding string: {e}"

def extract_userid_from_token(token):
    """JWT Token se real user ID extract karne ke liye helper function"""
    try:
        payload_str = token.split('.')[1]
        payload_bytes = base64.b64decode(payload_str + '==')
        payload = json.loads(payload_bytes)
        return str(payload.get("id") or payload.get("userid") or payload.get("user_id") or "-2")
    except Exception:
        return "-2"

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
                    soup = BeautifulSoup(content, 'html.parser')
                    return json.loads(str(soup))
            except Exception as e:
                print(f"Fetch error {url}: {str(e)}")
                await asyncio.sleep(1)
        return {}

async def handle_course(session, api_base, bi, si, sn, topic, hdr1):
    ti = topic.get("topicid")
    tn = topic.get("topic_name")
    
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

    # Deduplicate video entries by ID
    seen_ids = set()
    unique_videos = []
    for v in video_data:
        v_id = v.get("id")
        if v_id not in seen_ids:
            seen_ids.add(v_id)
            unique_videos.append(v)

    unique_videos = sorted(unique_videos, key=lambda x: x.get("id", 0))
    tasks = [process_video(session, api_base, bi, si, sn, ti, tn, video, hdr1) for video in unique_videos]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    clean_results = []
    for lines in results:
        if isinstance(lines, list) and lines:
            clean_results.extend(lines)
    return clean_results

async def process_video(session, api_base, bi, si, sn, ti, tn, video, hdr1):
    vi = video.get("id")
    lines = []
    
    try:
        r4 = await fetch(session, f"{api_base}/get/fetchVideoDetailsById?course_id={bi}&video_id={vi}&ytflag=0&folder_wise_course=0", hdr1)
        
        if not r4 or not r4.get("data"):
            return None

        data = r4.get("data", {})
        vt = data.get("Title", "").strip()
        vl = data.get("download_link", "")
        fl = data.get("video_id", "")
        
        if fl:
            dfl = decrypt(fl)
            if dfl:
                lines.append(f"{vt}:https://youtu.be/{dfl}\n")

        if vl:
            dvl = decrypt(vl)
            if dvl and ".pdf" not in dvl: 
                lines.append(f"{vt}:{dvl}\n")
        else:
            encrypted_links = data.get("encrypted_links", [])
            if encrypted_links:
                first_link = encrypted_links[0]
                a = first_link.get("path")
                k = first_link.get("key")
                if a and k:
                    da = decrypt(a)
                    k1 = decrypt(k)
                    k2 = decode_base64(k1)
                    lines.append(f"{vt}:{da}*{k2}\n")
                elif a:
                    da = decrypt(a)
                    lines.append(f"{vt}:{da}\n")
        
        # PDFs handling
        p1 = data.get("pdf_link", "")
        pk1 = data.get("pdf_encryption_key", "")
        p2 = data.get("pdf_link2", "")
        pk2 = data.get("pdf2_encryption_key", "")
        
        if p1 and pk1:
            dp1 = decrypt(p1)
            depk1 = decrypt(pk1)
            lines.append(f"{vt}:{dp1}\n" if depk1 == "abcdefg" else f"{vt}:{dp1}*{depk1}\n")
        if p2 and pk2:
            dp2 = decrypt(p2)
            depk2 = decrypt(pk2)
            lines.append(f"{vt}:{dp2}\n" if depk2 == "abcdefg" else f"{vt}:{dp2}*{depk2}\n")
                        
        return lines
    except Exception as e:
        print(f"Error processing video ID {vi}: {str(e)}")
        return None

THREADPOOL = ThreadPoolExecutor(max_workers=100)

@app.on_message(filters.command(["appx"]))
async def appex_v4_txt(app, message):
    api = await app.ask(message.chat.id, text="**SEND APPX API Without https://\n\n✅ Example:\ntcsexamzoneapi.classx.co.in**")
    api_txt = api.text.strip()
    name = api_txt.split('.')[0].replace("api", "") if api_txt else api_txt.split('.')[0]
    if "api" in api_txt:
        await appex_v5_txt(app, message, api_txt, name)
    else:
        await app.send_message(message.chat.id, "INVALID INPUT IF YOU DONT KNOW API GO TO FIND API OPTION")

async def appex_v5_txt(app, message, api, name):
    api_base = api.replace("http://", "https://") if api.startswith(("http://", "https://")) else f"https://{api}"
    app_name = api_base.replace("http://", " ").replace("https://", " ").replace("api.classx.co.in"," ").replace("api.akamai.net.in", " ").replace("apinew.teachx.in", " ").replace("api.cloudflare.net.in", " ").replace("api.appx.co.in", " ").replace("/", " ").strip()
    
    input1 = await app.ask(message.chat.id, f"SEND MOBILE NUMBER AND PASSWORD IN THIS FORMAT\n\n MOBILE*PASSWORD\n\nᴄᴏᴀᴄʜɪɴɢ ɴᴀᴍᴇ:- {app_name}\n\n OR SEND TOKEN")
    raw_text = input1.text.strip()
    
    userid = "-2"
    token = ""
    
    if '*' in raw_text:
        email, password = raw_text.split("*", 1)
        raw_url = f"{api_base}/post/userLogin"
        headers = {
            "Auth-Key": "appxapi",
            "User-Id": "-2",
            "Authorization": "",
            "User_app_category": "",
            "Language": "en",
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept-Encoding": "gzip, deflate",
            "User-Agent": "okhttp/4.9.1"
        }
        data = {"email": email, "password": password}
        
        try:
            response = requests.post(raw_url, data=data, headers=headers, timeout=15).json()
            status = response.get("status")

            if status == 200:
                userid = str(response["data"]["userid"])
                token = response["data"]["token"]
            elif status == 203:
                second_api_url = f"{api_base}/post/userLogin?extra_details=0"
                second_headers = {
                    "auth-key": "appxapi",
                    "client-service": "Appx",
                    "source": "website",
                    "user-agent": "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36",
                    "accept": "*/*",
                    "accept-language": "en-GB,en-US;q=0.9,en;q=0.8"
                }
                second_data = {
                    "source": "website",
                    "phone": email,
                    "email": email,
                    "password": password,
                    "extra_details": "1"
                }
                second_response = requests.post(second_api_url, headers=second_headers, data=second_data, timeout=15).json()
                if second_response.get("status") == 200:
                    userid = str(second_response["data"]["userid"])
                    token = second_response["data"]["token"]
        except Exception as e:
            print(f"Login error: {str(e)}")
            return await message.reply_text("Please try again later. Maybe Password Wrong.")
    else:
        # Direct Token logic with automatic User-ID extraction
        token = raw_text
        userid = extract_userid_from_token(token)

    if not token:
        return await message.reply_text("Invalid Token or Credentials provided.")

    hdr1 = {
        "Client-Service": "Appx",
        "source": "website",
        "Auth-Key": "appxapi",
        "Authorization": token,
        "User-ID": userid,
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
    }  

    scraper = cloudscraper.create_scraper() 
    mc1 = {}
    try:
        res = scraper.get(f"{api_base}/get/mycoursev2?userid={userid}", headers=hdr1, timeout=15)
        mc1 = res.json()
    except json.JSONDecodeError as e:
        print(f"JSON decode error: {str(e)}")
        return await message.reply_text("Error decoding response from server. Check API or Token.")
    except Exception as e:
        print(f"An error occurred: {str(e)}")
        return await message.reply_text("An error occurred while fetching your courses. Please try again later.")
    
    FFF = "𝗕𝗔𝗧𝗖𝗛 𝗜𝗗 ➤ 𝗕𝗔𝗧𝗖𝗛 𝗡𝗔𝗠𝗘\n\n"
    valid_ids = []

    if "data" in mc1 and mc1["data"]:
        for ct in mc1["data"]:
            ci = str(ct.get("id"))
            cn = ct.get("course_name")
            FFF += f"**`{ci}`   -   `{cn}`**\n\n"
            valid_ids.append(ci)
    else:
        return await message.reply_text("NO BATCH PURCHASED OR INVALID TOKEN")

    dl = f"𝗔𝗽𝗽𝘅 𝗟𝗼𝗴𝗶𝗻 𝗦𝘂𝗰𝗲𝘀𝘀✅ for {app_name} \n {api_base}\n\n `{raw_text}` \n\n`{token}`\n\n{FFF}"
    if len(FFF) <= 4096:
        await app.send_message(log_channel, dl)
        await app.send_message(log_channel2, f"`{token}`")
        editable1 = await message.reply_text(f"𝗔𝗽𝗽𝘅 𝗟𝗼𝗴𝗶𝗻 𝗦𝘂𝗰𝗲𝘀𝘀✅\n\n`{token}`\n\n{FFF}")      
    else:
        plain_FFF = FFF.replace("**", "").replace("`", "")
        file_path = f"{app_name}.txt"
        with open(file_path, "w", encoding="utf-8") as file:
            file.write(f"𝗔𝗽𝗽𝘅 𝗟𝗼𝗴𝗶𝗻 𝗦𝘂𝗰𝗲𝘀𝘀✅ for {app_name}\n\nToken: {token}\n\n{plain_FFF}")

        await app.send_document(
            message.chat.id,
            document=file_path,
            caption="Too many batches, so select batch IDs from the text file."
        )
        await app.send_document(log_channel, document=file_path, caption="Too many batches.")
        editable1 = None

    input2 = await app.ask(message.chat.id, "**Send multiple Course IDs separated by '&' to Download or copy below text to download all batches**\n\n`" + "&".join(valid_ids) + "`")

    batch_ids = [batch.strip() for batch in input2.text.strip().split("&") if batch.strip() in valid_ids]

    if not batch_ids:
        await message.reply_text("**Invalid Course ID(s). Please send valid Course IDs from the list.**")
        try:
            await input2.delete(True)
            if editable1:
                await editable1.delete(True)
        except Exception:
            pass
        return

    m1 = await message.reply_text("Processing your requested batches...")

    for raw_text2 in batch_ids:
        m2 = await message.reply_text(f"Extracting batch `{raw_text2}`...")
        start_time = time.time()
        
        course_info = next((ct for ct in mc1.get("data", []) if str(ct.get("id")) == raw_text2), {})
        course_name = course_info.get("course_name", "Course")
        start = course_info.get("start_date", "N/A")
        end = course_info.get("end_date", "N/A")
        pricing = course_info.get("price", "N/A")
        cp = course_info.get("course_thumbnail", "")

        try:
            r = scraper.get(f"{api_base}/get/course_by_id?id={raw_text2}", headers=hdr1, timeout=15).json()
        except Exception as e:
            print(f"Error fetching course details: {str(e)}")
            sanitized_course_name = course_name.replace(':', '_').replace('/', '_')
            await v2_new(app, message, token, userid, hdr1, app_name, raw_text2, api_base, sanitized_course_name, start_time, start, end, pricing, input2, m1, m2)
            continue

        if not r.get("data"):
            sanitized_course_name = course_name.replace(':', '_').replace('/', '_')
            await v2_new(app, message, token, userid, hdr1, app_name, raw_text2, api_base, sanitized_course_name, start_time, start, end, pricing, input2, m1, m2)
            continue

        for i in r.get("data", []):
            txtn = i.get("course_name", "Batch")
            filename1 = f"{raw_text2}_{txtn.replace(':', '_').replace('/', '_')}.txt".replace(" ", "_")

            async with aiohttp.ClientSession() as session:
                with open(filename1, 'w', encoding='utf-8') as f:
                    try:
                        r1 = await fetch(session, f"{api_base}/get/allsubjectfrmlivecourseclass?courseid={raw_text2}&start=-1", hdr1)
            
                        for subject in r1.get("data", []):
                            si = subject.get("subjectid")
                            sn = subject.get("subject_name")

                            r2 = await fetch(session, f"{api_base}/get/alltopicfrmlivecourseclass?courseid={raw_text2}&subjectid={si}&start=-1", hdr1)
                            topics = sorted(r2.get("data", []), key=lambda x: x.get("topicid", 0))

                            tasks = [handle_course(session, api_base, raw_text2, si, sn, t, hdr1) for t in topics]
                            all_data = await asyncio.gather(*tasks, return_exceptions=True)
                
                            for data in all_data:
                                if isinstance(data, list) and data:
                                    f.writelines(data)
        
                    except Exception as e:
                        print(f"An error occurred while processing the course: {str(e)}")
                        sanitized_course_name = course_name.replace(':', '_').replace('/', '_')
                        await v2_new(app, message, token, userid, hdr1, app_name, raw_text2, api_base, sanitized_course_name, start_time, start, end, pricing, input2, m1, m2)
                        continue
                    
                end_time = time.time()
                elapsed_time = end_time - start_time
            
                c_text = (
                    f"**APP NAME: <b>{app_name}</b>**\n"
                    f"**BatchName:** {raw_text2}_{txtn}\n"
                    f"**Validity Start:** {start}\n"
                    f"**Validity Ends:** {end}\n"
                    f"Elapsed time: {elapsed_time:.1f} seconds\n"
                    f"**Batch Price:** {pricing}\n"
                    f"**course_thumbnail:** <a href='{cp}'>Thumbnail</a>"
                )
            
                try:
                    await app.send_document(message.chat.id, filename1, caption=c_text)
                    await app.send_document(log_channel, filename1, caption=c_text)
                except Exception as e:
                    print(f"An error occurred while sending the document: {str(e)}")
                    sanitized_course_name = course_name.replace(':', '_').replace('/', '_')
                    await v2_new(app, message, token, userid, hdr1, app_name, raw_text2, api_base, sanitized_course_name, start_time, start, end, pricing, input2, m1, m2)
                finally:
                    if os.path.exists(filename1):
                        os.remove(filename1)

    try:
        await input2.delete(True)
        await m1.delete(True)
        await m2.delete(True)
    except Exception:
        pass
