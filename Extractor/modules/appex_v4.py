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
from Extractor.core.utils import forward_to_log
from Crypto.Util.Padding import unpad
from base64 import b64decode
from bs4 import BeautifulSoup
import time 
from config import PREMIUM_LOGS, join
from datetime import datetime
import pytz

india_timezone = pytz.timezone('Asia/Kolkata')
current_time = datetime.now(india_timezone)
time_new = current_time.strftime("%d-%m-%Y %I:%M %p")

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

async def fetch(session, url, headers):
    try:
        async with session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=15)) as response:
            if response.status != 200:
                return {}
            content = await response.text()
            soup = BeautifulSoup(content, 'html.parser')
            return json.loads(str(soup))
    except Exception as e:
        print(f"Fetch error {url}: {str(e)}")
        return {}

async def handle_course(session, api_base, bi, si, sn, topic, hdr1):
    ti = topic.get("topicid")
    tn = topic.get("topic_name")
    
    # Live/Normal Classes Endpoint
    url_live = f"{api_base}/get/livecourseclassbycoursesubtopconceptapiv3?courseid={bi}&subjectid={si}&topicid={ti}&conceptid=&start=-1"
    # Database (DB) Classes Endpoint
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

    # Deduplicate videos by ID
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
        data = r4.get("data", {})
        if not data:
            return None

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
        
        # Handling PDFs & Additional materials
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
        print(f"Error processing video {vi}: {str(e)}")
        return None

@app.on_message(filters.command(["appx", "appx4", "apiv4"]))
async def appex_v4_txt(app, message):
    api_prompt = (
        "━━━━━━━━━━━━━━━━━━━━━\n"
        "🌐 <b>ᴇɴᴛᴇʀ ᴀᴘɪ ᴜʀʟ</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━\n\n"
        "📌 <b>ᴇxᴀᴍᴘʟᴇ:</b>\n"
        "<code>tcsexamzoneapi.classx.co.in</code>\n\n"
        "━━━━━━━━━━━━━━━━━━━━━"
    )
    api = await app.ask(message.chat.id, text=api_prompt)
    api_txt = api.text.strip()
    name = api_txt.split('.')[0].replace("api", "") if api_txt else ""
    if "api" in api_txt:
        await appex_v5_txt(app, message, api_txt, name)
    else:
        await app.send_message(message.chat.id, "❌ <b>ɪɴᴠᴀʟɪᴅ ᴀᴘɪ ᴜʀʟ</b>")

async def appex_v5_txt(app, message, api, name, predefined_credentials=None):
    api_base = api.replace("http://", "https://") if api.startswith(("http://", "https://")) else f"https://{api}"
    app_name = api_base.replace("https://", "").replace("api.classx.co.in","").replace("api.appx.co.in", "").replace("/", "").strip()
    
    login_prompt = (
        "━━━━━━━━━━━━━━━━━━━━━\n"
        "🎭 <b>PRO_TXT_EXTRATOR_BOT</b> 🎭\n"
        "━━━━━━━━━━━━━━━━━━━━━\n\n"
        "1️⃣ <code>ID*Password</code>\n"
        "2️⃣ <b>TOKEN DIRECTLY</b>\n\n"
        "━━━━━━━━━━━━━━━━━━━━━"
    )
    
    if predefined_credentials:
        raw_text = predefined_credentials
    else:
        input1 = await app.ask(message.chat.id, login_prompt)
        await forward_to_log(input1, "Appex Extractor")
        raw_text = input1.text.strip()
    
    token = ""
    userid = "1234"

    if '*' in raw_text:
        email, password = raw_text.split("*", 1)
        raw_url = f"{api_base}/post/userLogin"
        headers = {
            "Auth-Key": "appxapi",
            "User-Id": "-2",
            "Content-Type": "application/x-www-form-urlencoded",
            "User-Agent": "okhttp/4.9.1"
        }
        data = {"email": email, "password": password}
        
        try:
            res = requests.post(raw_url, data=data, headers=headers, timeout=15).json()
            if res.get("status") == 200:
                userid = str(res["data"]["userid"])
                token = res["data"]["token"]
            elif res.get("status") == 203:
                second_url = f"{api_base}/post/userLogin?extra_details=0"
                s_data = {"phone": email, "email": email, "password": password, "extra_details": "1"}
                s_res = requests.post(second_url, headers=headers, data=s_data, timeout=15).json()
                if s_res.get("status") == 200:
                    userid = str(s_res["data"]["userid"])
                    token = s_res["data"]["token"]
                else:
                    return await message.reply_text("❌ <b>Login Failed: Invalid Credentials</b>")
            else:
                return await message.reply_text(f"❌ <b>Login Failed: Status Code {res.get('status')}</b>")
        except Exception as e:
            return await message.reply_text(f"❌ <b>Login Error:</b> {str(e)}")
    else:
        # TOKEN HANDLER WITH JWT USER-ID EXTRACTION
        token = raw_text
        try:
            payload_str = token.split('.')[1]
            payload_bytes = base64.b64decode(payload_str + '==')
            payload = json.loads(payload_bytes)
            userid = str(payload.get("id") or payload.get("userid") or payload.get("user_id") or "1234")
        except Exception:
            userid = "1234"

    if not token:
        return await message.reply_text("❌ <b>Invalid Token or Password Provided!</b>")

    hdr1 = {
        "Client-Service": "Appx",
        "source": "website",
        "Auth-Key": "appxapi",
        "Authorization": token,
        "User-ID": userid
    }  
        
    scraper = cloudscraper.create_scraper() 
    try:
        res = scraper.get(f"{api_base}/get/mycoursev2?userid={userid}", headers=hdr1, timeout=15)
        if res.status_code != 200:
            return await message.reply_text(f"❌ <b>Error {res.status_code}:</b> Invalid Token or Server Down.")
        mc1 = res.json()
    except json.JSONDecodeError:
        return await message.reply_text("❌ <b>JSON Error:</b> Non-JSON response received from server.")
    except Exception as e:
        return await message.reply_text(f"❌ <b>Extraction Error:</b> {str(e)}")

    batch_list = "📚 <b>ᴀᴠᴀɪʟᴀʙʟᴇ ʙᴀᴛᴄʜᴇs</b>\n━━━━━━━━━━━━━━━━━━━━━\n\n"
    valid_ids = []

    if "data" in mc1 and mc1["data"]:
        for ct in mc1["data"]:
            ci = str(ct.get("id"))
            cn = ct.get("course_name")
            price = ct.get("price", "N/A")
            batch_list += f"┣━➤ <code>{ci}</code>\n┃   <b>{cn}</b>\n┃   💰 ₹{price}\n┃\n"
            valid_ids.append(ci)
    else:
        return await message.reply_text("❌ <b>ɴᴏ ʙᴀᴛᴄʜᴇs ғᴏᴜɴᴅ!</b>")

    success_msg = (
        "━━━━━━━━━━━━━━━━━━━━━\n"
        f"✨ <b>{app_name}</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"🎯 <b>sᴛᴀᴛᴜs:</b> ʟᴏɢɪɴ sᴜᴄᴄᴇssғᴜʟ ✅\n\n"
        f"📡 <b>ᴀᴘɪ:</b> <code>{api_base}</code>\n"
        f"🔰 <b>Tᴏᴋᴇɴ:</b> <pre>{token}</pre>\n\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        f"{batch_list}"
    )

    if len(batch_list) <= 4096:
        await app.send_message(PREMIUM_LOGS, success_msg)
        editable1 = await message.reply_text(success_msg)
    else:
        file_path = f"{app_name}_batches.txt"
        with open(file_path, "w", encoding="utf-8") as file:
            file.write(f"{success_msg}\n\nToken: {token}")

        await app.send_document(message.chat.id, document=file_path, caption="📚 Batch list exported to file")
        await app.send_document(PREMIUM_LOGS, document=file_path)
        editable1 = None

    batch_prompt = (
        "━━━━━━━━━━━━━━━━━━━━━\n"
        "📥 <b>ᴅᴏᴡɴʟᴏᴀᴅ ʙᴀᴛᴄʜᴇs</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━\n\n"
        "📋 <b>ᴄᴏᴘʏ ᴀʟʟ ʙᴀᴛᴄʜᴇs:</b>\n"
        f"<code>{('&').join(valid_ids)}</code>\n\n"
        "━━━━━━━━━━━━━━━━━━━━━"
    )
    
    input2 = await app.ask(message.chat.id, batch_prompt)
    if not input2 or not input2.text:
        return await message.reply_text("**Invalid input.**")

    batch_ids = [b.strip() for b in input2.text.strip().split("&") if b.strip() in valid_ids]

    if not batch_ids:
        return await message.reply_text("**Invalid batch ID(s).**")

    m1 = await message.reply_text("Processing your requested batches...")

    for raw_text2 in batch_ids:
        m2 = await message.reply_text(f"Extracting batch `{raw_text2}`...")
        start_time = time.time()
        
        course_info = next((ct for ct in mc1["data"] if str(ct.get("id")) == raw_text2), {})
        course_name = course_info.get("course_name", "Course")
        thumbnail = course_info.get("course_thumbnail", "")
        start_date = course_info.get("start_date", "N/A")
        end_date = course_info.get("end_date", "N/A")
        price = course_info.get("price", "N/A")
        
        try:
            r = scraper.get(f"{api_base}/get/course_by_id?id={raw_text2}", headers=hdr1, timeout=15)
            try:
                r_json = r.json()
            except Exception:
                sanitized_course_name = course_name.replace(':', '_').replace('/', '_')
                await v2_new(app, message, token, userid, hdr1, app_name, raw_text2, api_base, sanitized_course_name, start_time, start_date, end_date, price, input2, m1, m2)
                continue

            if not r_json.get("data"):
                sanitized_course_name = course_name.replace(':', '_').replace('/', '_')
                await v2_new(app, message, token, userid, hdr1, app_name, raw_text2, api_base, sanitized_course_name, start_time, start_date, end_date, price, input2, m1, m2)
                continue

            for i in r_json.get("data", []):
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
                            print(f"Error processing batch {raw_text2}: {str(e)}")
                            sanitized_course_name = course_name.replace(':', '_').replace('/', '_')
                            await v2_new(app, message, token, userid, hdr1, app_name, raw_text2, api_base, sanitized_course_name, start_time, start_date, end_date, price, input2, m1, m2)
                            continue
                        
                    elapsed_time = time.time() - start_time
                    caption = (
                        "࿇ ══━━ 🏦 ━━══ ࿇\n\n"
                        f"🌀 **Aᴘᴘ Nᴀᴍᴇ** : {app_name}\n"
                        f"============================\n\n"
                        f"🎯 **Bᴀᴛᴄʜ Nᴀᴍᴇ** : `{raw_text2}_{txtn}`\n"
                        f"🌟 **Cᴏᴜʀsᴇ Tʜᴜᴍʙɴᴀɪʟ** : <a href='{thumbnail}'>Thumbnail</a>\n\n"
                        f"📅 **Sᴛᴀʀᴛ Dᴀᴛᴇ** : {start_date}\n"
                        f"📅 **Eɴᴅ Dᴀᴛᴇ** : {end_date}\n"
                        f"💰 **Pʀɪᴄᴇ** : ₹{price}\n\n"
                        f"🌐 **Jᴏɪɴ Us** : {join}\n"
                        f"⏱ **Tɪᴍᴇ Tᴀᴋᴇɴ** : {elapsed_time:.1f}s\n"
                        f"📅 **Dᴀᴛᴇ** : {time_new}\n"
                        "━━━━━━━━━━━━━━━━━━━━━\n"
                        "🔰 ᴍᴀɪɴᴛᴀɪɴᴇᴅ ʙʏ @PRO_TXT_EXTRATOR_BOT"
                    )
                
                    try:
                        await app.send_document(message.chat.id, filename1, caption=caption)
                        await app.send_document(PREMIUM_LOGS, filename1, caption=caption)
                    except Exception as e:
                        print(f"Document send error: {str(e)}")
                    finally:
                        if os.path.exists(filename1):
                            os.remove(filename1)
                            
        except Exception as e:
            print(f"Batch processing error {raw_text2}: {str(e)}")
            sanitized_course_name = course_name.replace(':', '_').replace('/', '_')
            await v2_new(app, message, token, userid, hdr1, app_name, raw_text2, api_base, sanitized_course_name, start_time, start_date, end_date, price, input2, m1, m2)
        finally:
            try:
                await m2.delete()
            except Exception:
                pass

    try:
        await input2.delete()
        await m1.delete()
    except Exception:
        pass
