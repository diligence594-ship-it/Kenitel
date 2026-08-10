from pyrogram import filters



from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery



from Extractor import app



import re



import requests



import json



import asyncio







VC_APPS = {



    "mittal_cc": "Mittal CC",



    "ramani_inst": "Ramani Institute",



    "garhwal_sir": "Garhwal Sir English",



    "next_toppers": "Next toppers",



    "mission_jeet": "Mission Jeet",



    "abhinay_maths": "Abhinay Maths",



    "my_patashala": "My Patashala",



    "gca_gurujrat": "GCA Gurujrat",



    "tricks_wale": "Tricks Wale",



    "eduteria": "Eduteria",



    "exam_fodu": "Exam Fodu",



    "exampur": "Exampur",



    "awadh_ojha": "Awadh Ojha",



    "lab": "LAB",



    "kanet_guidance": "Kanet Guidance",



    "gammat_satheesh": "Gammat Satheesh Gyan",



    "patel_tutorials": "Patel Tutorials",



    "nimbus_defence": "Nimbus Defence",



    "reso_digital": "Reso Digital",



    "mother_education": "Mother Education-Hub",



    "warriors_academy": "Warriors Academy",



    "chandra_academy": "Chandra Academy",



    "ojas_study": "Ojas Study",



    "patel_sir": "Patel Sir classes",



    "rajput_tutorials": "Rajput Tutorials",



    "physics_sir_jee": "Physics Sir JEE",



    "param_sir": "Param Sir Classes",



    "abhayam_live": "Abhayam Live",



    "kota_mentors": "Kota Mentors",



    "target_on": "Target On",



    "physics_linx": "Physics Linx",



    "e_career_point": "E-Career-Point",



    "sarathi_plus": "Sarathi Plus",



    "straight_academy": "Straight Academy",



    "adarsh_institute": "Adarsh Institute",



    "sahitya_classes": "Sahitya Classes",



    "vimal_sir": "Vimal Sir classes",



    "kautilya_gs": "Kautilya Gs",



    "chronicle_ias": "Chronicle IAS",



    "artham_fine": "Artham Fine",



    "early_bird_ias": "Early Bird IAS",



    "champion_pub": "Champion Publication",



    "mission_selection": "Mission Selection",



    "study_norms": "Study Norms",



    "mentors_36": "Mentors 36",



    "vivek_sir": "Classes By Vivek Sir",



    "gs_sushant_sir": "Gs By Sushant Sir",



    "edu_iq_test": "Edu Iq Test",



    "geography_jaglan": "Geography By Jaglan Sir",



    "tlc_education": "TLC Education",



    "ensure_ias": "Ensure IAS",



    "exam_prep": "Exam Prep",



    "stable_class": "Stable Class",



    "ima_jodhpur": "IMA Jodhpur",



    "nursing_officer": "Nursing Officer",



    "upsc_toppers": "UpSc Toppers Hub",



    "progression_academy": "Progression Academy",



    "selection_path": "Selection Path",



    "aanand_defence": "Aanand Defence",



    "bazzar_gyan": "Bazzar Gyan",



    "trishul_defence": "Trishul Defence Academy",



    "vinish_chaudhary": "Vinish Chaudhary",



    "vidya_edutech": "Vidya Edutech",



    "medha_academy": "Medha Academy",



    "sunny_reasoning": "Sunny Reasoning",



    "maurya_guru": "Maurya Guru",



    "world_education": "World Education",



    "aim_learning": "Aim the Learning",



    "latara_educare": "Latara Educare",



    "go_ahead": "Go Ahead Academy",



    "law_legends": "Law Legends",



    "aw_class": "AW class Chaumahla",



    "mission_pathashala": "Mission Pathashala",



    "a_kumar_physics": "A Kumar Physics",



    "shri_ram_academy": "Shri Ram Academy",



    "punjabi_taleem": "Punjabi Taleem",



    "c4_chemestry": "C4 Chemestry",



    "edu_culture": "Edu Culture",



    "sri_ram_ias": "Sri Ram Ias",



    "vsi_jaipur": "VSI Jaipur",



    "q_sarthi_kota": "Q Sarthi Kota",



    "race_ias": "Race IAS",



    "unique_ias": "The Unique IAS",



    "class_pedia": "Class Pedia",



    "feel_free": "Feel Free To Learn",



    "kautilya_vision": "Kautilya Vision Classes",



    "mandarin_academy": "Mandarin Academy",



    "mulyankan_academy": "Mulyankan Academy",



    "parivartan_abhijit": "Parivartan By Abhijit Rathod",



    "sarvodaya_career": "Sarvodaya Career Institute",



    "vikalp_classes": "Vikalp Classes",



    "om_digital": "Om Digital Study",



    "mission_is_selection": "Mission is Selection",



    "iqra_ias": "Iqra IAS",



    "toppers_code": "Toppers Code"



}







@app.on_message(filters.command("videocrypt_apps"))



async def show_videocrypt_apps(client, message: Message):



    text = "**Available VideoCrypt Apps:**\n\n"



    keyboard = []



    keys = list(VC_APPS.keys())



    for i in range(0, len(keys), 2):



        row = []



        if i < len(keys):



            row.append(InlineKeyboardButton(VC_APPS[keys[i]][:15], callback_data=f"vc_{keys[i]}"))



        if i+1 < len(keys):



            row.append(InlineKeyboardButton(VC_APPS[keys[i+1]][:15], callback_data=f"vc_{keys[i+1]}"))



        keyboard.append(row)



    await message.reply_text(



        "**VideoCrypt Extractor Hub**\nSelect an App from the list below to begin:\n*(Note: Extraction modules for these will be added soon)*",



        reply_markup=InlineKeyboardMarkup(keyboard[:50])



    )







@app.on_callback_query(filters.regex(r"^vc_(.*)"))
async def vc_app_selected(client, callback_query: CallbackQuery):
    app_key = callback_query.data.split("_", 1)[1]
    app_name = VC_APPS.get(app_key, "Unknown App")
    
    msg = await callback_query.message.edit_text(
        f"**{app_name} Selected**\n\n"
        f"Please reply to this message with the course URL or ID you want to extract.\n"
        f"Send /cancel to abort."
    )
    
    input_msg = await app.listen(callback_query.message.chat.id, timeout=120)
    if input_msg.text == '/cancel':
        await msg.edit_text('Extraction Cancelled')
        return
        
    await msg.edit_text(f"Attempting to extract from {app_name}... this may take a moment.")
