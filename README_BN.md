# TEAM HACKER BD AI SIGNAL — Full Telegram Bot

## কী কী কাজ করে
- `/start` → Channel verification → Contact Admin ও Live Signal buttons
- Admin panel শুধু নির্ধারিত Admin ID-দের দেখায়
- মূল Admin IDs: `8717265614`, `8350956429`
- Admin panel থেকে Signal/Result template, brand emoji/text, WIN/LOSS/Jackpot/Next image বদলানো
- Botcast: Admin-এর পাঠানো text/photo/video/document সব নিবন্ধিত user-কে পাঠায়
- User Ban/Unban, নতুন Admin যোগ, channel ID/link পরিবর্তন
- Wingo 1M API থেকে সর্বশেষ ৫০টি record নিয়ে একটি স্পষ্ট baseline heuristic-এ Big/Small ও দুইটি number নির্বাচন
- Result API-তে target period দেখা দিলে WIN/LOSS/Number Jackpot নির্ধারণ
- WIN বা Number Jackpot হলে Entry Level 1; LOSS হলে পরের level
- ৬টি consecutive loss-level পার হলে সেশন ১ ঘণ্টা cooldown-এ যায়
- প্রতি ৫টি WIN/JACKPOT-এ report; report-এ total এবং শেষ ৪টি period
- সেশনে ২০টি WIN/JACKPOT হলে Live Signal বন্ধ করে ১ ঘণ্টা cooldown
- SQLite persistent database; Firebase বাধ্যতামূলক নয়

## Prediction সম্পর্কে গুরুত্বপূর্ণ সতর্কতা
এই project-এর default strategy হলো গত ৫০টি ফলাফলের Big/Small frequency এবং ওই side-এর সবচেয়ে বেশি আসা দুইটি number বেছে নেওয়া। এটি একটি স্বচ্ছ baseline heuristic; lottery/বেটিং ফলাফল random হতে পারে, তাই এটি নির্ভরযোগ্য ভবিষ্যদ্বাণী বা নিশ্চিত জয়ের পদ্ধতি নয়। কোনো win-rate বা profit guarantee নেই। বাস্তব API result দিয়েই outcome যাচাই হয়।

## Setup
1. Python 3.10+ ইনস্টল করুন।
2. ZIP extract করুন।
3. project folder-এ:
   `pip install -r requirements.txt`
4. `.env.example` ফাইলটি `.env` নামে copy করুন।
5. `.env`-এ BotFather token বসান। Channel bot-কে admin/member-check করার অনুমতি দিন; private channel হলে CHANNEL_ID হিসেবে numeric ID দিন।
6. চালান:
   `python bot.py`

## Admin ব্যবহার
- দুইটি মূল Admin ID কোডে `.env` থেকে আসে।
- `/start` → Admin Panel
- Signal Format / Result Format: template text পাঠান। Supported placeholders:
  - Signal: `{brand}`, `{market}`, `{period}`, `{entry}`, `{level}`, `{registration_link}`
  - Result: `{brand}`, `{market}`, `{period}`, `{entry}`, `{result}`, `{status}`, `{level}`
- Emoji/Text Style: brand text পাঠান।
- Images: photo পাঠিয়ে caption-এ `next`, `win`, `loss`, বা `jackpot` লিখুন।
- Botcast: যেকোনো message পাঠান; bot সেটি registered users-দের copy করবে।
- Ban/Unban: `123456789 ban` অথবা `123456789 unban`
- Add Admin: numeric Telegram User ID
- Channel Settings: `@channelusername | https://t.me/channelusername`

সব template/image/settings SQLite-এ সেভ হয় এবং পরবর্তী Signal/Result পাঠানোর সময় নতুন setting পড়া হয়—বট restart লাগবে না।

## Hosting / Database
Firebase বা external database server দরকার নেই। SQLite file `data/bot.sqlite3`-এ settings, users, admins, signal history থাকে। কিন্তু bot-কে ২৪/৭ চালু রাখতে Python-supporting VPS/hosting দরকার। Hosting-এর disk persistent হতে হবে; ephemeral hosting-এ redeploy/restart হলে data হারাতে পারে। নিয়মিত `data/bot.sqlite3` backup নিন। ZIP শুধু Telegram-এ upload করলে bot চালু হবে না; server-এ extract করে `python bot.py` চালাতে হবে।

## Notes
- একই user-এর একাধিক Live Signal worker যেন না চলে—bot একবারে এক session শুরু করে।
- Admin-এর নতুন settings database থেকে runtime-এ পড়া হয়।
- Telegram bot কোনো user-কে নিজে থেকে DM করতে পারে না যতক্ষণ না user bot-এ `/start` করেছে।
- API-তে 403/timeout হলে bot log-এ error দেখাবে; API access availability external service-এর ওপর নির্ভরশীল।
