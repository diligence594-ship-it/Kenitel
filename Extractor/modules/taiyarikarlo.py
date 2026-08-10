import re
import requests
import urllib.parse
from Extractor import app

async def taiyari_karlo(app, message):
    input1 = await app.ask(message.chat.id, text="Send **ID & Password** in this manner, otherwise, the bot will not respond.\n\nSend like this: **ID*Password**")
    raw_text = input1.text
    ph, pas = raw_text.split("*")
    await input1.delete(True)
    
    headers = {
        "Api-Version": "10",
        "User-Agent": "Mobile-Android",
        "x-access-env": "pro"
    }
    
    url = f"https://api.classplusapp.com/v2/users/login/details?orgCode=taiyari&mobile={ph}"
    r1 = requests.get(url, headers=headers).json()
    if r1.get("status") != "success":
        await message.reply_text("Login Failed! Check credentials.")
        return
        
    await message.reply_text(f"**Login System is Classplus** - Use normal classplus button with org code **taiyari**")
