import os
import re
import json
import logging
import asyncio
import aiohttp
from pyrogram import Client, filters
from Extractor import app
from config import BOT_TEXT

def sanitize_filename(name):
    name = re.sub(r'[<>:"/\\|?*]', '_', str(name))
    name = re.sub(r'\s+', '_', name)
    name = re.sub(r'_+', '_', name)
    name = name.strip('_. ')
    return name if name else "Unknown_Course"

async def jchemistry(app: Client, m, user_id=None):
    if user_id is None:
        user_id = getattr(m.from_user, 'id', m.chat.id)
    loop = asyncio.get_event_loop()
    CONNECTOR = aiohttp.TCPConnector(limit=100, loop=loop)

    async with aiohttp.ClientSession(connector=CONNECTOR, loop=loop) as session:
        editable = await m.reply_text("Fetching J Chemistry courses... Please wait.")
        
        try:
            # Step 1: Fetch public frontend
            async with session.get("https://jchemistry.edmingle.com/courses", timeout=15) as resp:
                html = await resp.text()
            
            # Extract setUserDepts
            json_str = None
            m_search = re.search(r'setUserDepts\(\[(.*?)\]\);', html, re.DOTALL)
            if m_search:
                json_str = '[' + m_search.group(1) + ']'
            else:
                await editable.edit("Could not find course data on J Chemistry website.")
                return

            data = json.loads(json_str)
            if not data:
                await editable.edit("No data found.")
                return
                
            bundles = data[0].get('course_bundles', [])
            if not bundles:
                await editable.edit("No active courses found on J Chemistry.")
                return
                
            text = ''
            for cnt, batch in enumerate(bundles):
                name = batch.get("bundle_name", "Unknown")
                price = batch.get("cost", "Free")
                text += f"{cnt + 1}. {name} - Rs.{price}\n"
                
            course_details_file = f"{user_id}_jchemistry_courses.txt"
            with open(course_details_file, 'w', encoding='utf-8') as f:
                f.write(text)
                
            caption = (
                f"🎓 <b>J CHEMISTRY COURSES</b> 🎓\n\n"
                f"📚 <b>TOTAL COURSES:</b> {len(bundles)}\n\n"
                f"<code>╾───• @PRO_TXT_EXTRATOR_BOT •───╼</code>\n\n"
                "Send the index number to download course"
            )
            
            await editable.delete()
            msg = await m.reply_document(
                document=course_details_file,
                caption=caption,
                file_name="jchemistry_courses.txt"
            )
            
            try:
                os.remove(course_details_file)
            except:
                pass
                
            # Listen for index
            try:
                input_msg = await app.listen(chat_id=m.chat.id, filters=filters.user(user_id), timeout=120)
                user_choice = input_msg.text.strip()
                await input_msg.delete(True)
            except:
                await msg.edit("❌ <b>Timeout!</b>\n\nYou took too long to respond.")
                return
                
            if not user_choice.isdigit() or not (1 <= int(user_choice) <= len(bundles)):
                await msg.edit("❌ <b>Invalid Input!</b>\n\nPlease send a valid index number.")
                return
                
            selected_idx = int(user_choice) - 1
            selected_bundle = bundles[selected_idx]
            
            bundle_name = selected_bundle.get("bundle_name", "Unknown Batch")
            inst_bundle_id = selected_bundle.get("institution_bundle_id")
            course_ids = selected_bundle.get("course_ids", [])
            
            clean_batch_name = sanitize_filename(bundle_name)
            
            status_msg = await m.reply_text(
                "🔄 <b>Processing Course</b>\n"
                f"└─ Current: <code>{bundle_name}</code>\n"
                f"Extracting content without login..."
            )
            
            all_outputs = []
            
            api_base = "https://jchemistry-api.edmingle.com/nuSource/api/v1"
            headers = {
                "User-Agent": "Mozilla/5.0",
                "ORGID": "267" # J Chemistry Org ID
            }
            
            for course_id in course_ids:
                url = f"{api_base}/public/tutor/class/curriculum/{course_id}?institution_bundle_id={inst_bundle_id}"
                async with session.get(url, headers=headers) as r_api:
                    if r_api.status == 200:
                        curriculum_data = await r_api.json()
                        course_curr = curriculum_data.get('course_curriculum', {})
                        sections = course_curr.get('resources', [])
                        
                        for sec in sections:
                            sec_name = sec.get('section_name', 'Unknown Section')
                            items = sec.get('resources', [])
                            if items:
                                all_outputs.append(f"\n{sec_name}\n\n")
                                for item in items:
                                    mat_name = item.get('material_name', 'Untitled')
                                    mat_type = item.get('type')
                                    
                                    if mat_type in [7, 'video', 'video/mp4', 'video/vimeo']:
                                        # It's a video
                                        v_url = ""
                                        if item.get('drm_url'):
                                            drm = item.get('drm_url')
                                            if not drm.startswith('http'):
                                                v_id = drm.replace('-', '')
                                                v_url = f"https://player.vdocipher.com/v2/?otp=dummy&playbackInfo=dummy&videoId={v_id}"
                                            else:
                                                v_url = drm
                                        elif item.get('vdocipher_video_id'):
                                            v_url = f"https://player.vdocipher.com/v2/?otp=dummy&playbackInfo=dummy&videoId={item.get('vdocipher_video_id')}"
                                        elif item.get('gumlet_asset_id'):
                                            v_url = f"https://video.gumlet.io/{item.get('gumlet_asset_id')}/main.m3u8"
                                        elif item.get('vimeo_url'):
                                            v_url = f"https://vimeo.com/{item.get('vimeo_url')}"
                                        elif item.get('videocrypt_video_id'):
                                            v_url = f"videocrypt://{item.get('videocrypt_video_id')}"
                                            
                                        if v_url:
                                            all_outputs.append(f"{mat_name}:{v_url}\n")
                                        else:
                                            all_outputs.append(f"{mat_name}:[Video ID Missing]\n")
                                            
                                    elif mat_type in [2, 'application/pdf', 'document']:
                                        # It's a PDF
                                        f_name = item.get('file_name', 'document.pdf')
                                        if f_name and f_name.endswith('.pdf'):
                                            f_name = f"https://dragoapi.vercel.app/pdf/{f_name}"
                                        all_outputs.append(f"{mat_name}:{f_name}\n")
                                        
            if len(all_outputs) == 0:
                await status_msg.edit("❌ No content found for this course.")
                return
                
            clean_file_name = f"{user_id}_{clean_batch_name}"
            content = ''.join(all_outputs)
            
            with open(f"{clean_file_name}.txt", 'w', encoding='utf-8') as f:
                f.write(content)
                
            video_count = sum(1 for line in all_outputs if ":" in line and ".pdf" not in line.lower())
            pdf_count = sum(1 for line in all_outputs if ":" in line and ".pdf" in line.lower())
            total_links = video_count + pdf_count
            
            caption = (
                f"🎓 <b>J CHEMISTRY EXTRACTED</b> 🎓\n\n"
                f"📚 <b>BATCH:</b> {bundle_name}\n\n"
                f"📊 <b>CONTENT STATS</b>\n"
                f"├─ 📁 Total Items: {total_links}\n"
                f"├─ 🎬 Videos: {video_count}\n"
                f"└─ 📄 PDFs: {pdf_count}\n\n"
                f"🚀 <b>Extracted by</b>: @{(await app.get_me()).username}\n\n"
                f"<code>╾───• {BOT_TEXT} •───╼</code>"
            )
            
            with open(f"{clean_file_name}.txt", 'rb') as f:
                await msg.delete()
                await status_msg.delete()
                await m.reply_document(
                    document=f,
                    caption=caption,
                    file_name=f"{clean_batch_name}.txt"
                )
                
            try:
                os.remove(f"{clean_file_name}.txt")
            except:
                pass
                
        except Exception as e:
            await editable.edit(f"Error: {str(e)}")
            
        finally:
            await session.close()
            await CONNECTOR.close()

@app.on_callback_query(filters.regex("^jchemistry_$"))
async def jchemistry_callback(client, callback_query):
    try:
        
        await callback_query.answer()
        await jchemistry(client, callback_query.message, callback_query.from_user.id)
    except Exception as e:
        try:
            await callback_query.message.reply_text(f"Error: {str(e)}")
        except:
            pass
