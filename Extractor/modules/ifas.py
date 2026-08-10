import re
import requests
import urllib.parse
from Extractor import app

async def ifas(app, message):
    await message.reply_text("Currently IFAS requires an org code.\nPlease use the **🎯 CʟᴀssPʟᴜs 🎯** button if you have it!")
