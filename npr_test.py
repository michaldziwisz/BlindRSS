
import re
import json

html = """
<div class="audio-module-controls-wrap" data-audio='{"uid":"nx-s1-5665796:nx-s1-9596781","available":true,"duration":217,"title":"Trump to meet with House Republicans to discuss Venezuela, other topics","audioUrl":"https:\/\/ondemand.npr.org\/anon.npr-mp3\/npr\/me\/2026\/01\/20260106_me_trump_to_meet_with_house_republicans_to_discuss_venezuela_other_topics.mp3?t=progseg&e=nx-s1-5652511&p=3&seg=1&d=217&size=3477465&sc=siteplayer","storyUrl":"https:\/\/www.npr.org\/2026\/01\/06\/nx-s1-5665796\/trump-to-meet-with-house-republicans-to-discuss-venezuela-other-topics","slug":"Politics","program":"Morning Edition","affiliation":"","song":"","artist":"","album":"","track":0,"type":"segment","subtype":"other","skipSponsorship":false,"hasAdsWizz":false,"isStreamAudioType":false,"podcastEpisodeRawType":"","podcastEpisodeDerivedPlusType":""}' data-audio-metrics='[]'>
"

match = re.search(r'data-audio=\'({.*?})\'', html)
if match:
    print("Match found!")
    try:
        data = json.loads(match.group(1))
        audio_url = data.get('audioUrl')
        print(f"Audio URL: {audio_url}")
    except Exception as e:
        print(f"JSON error: {e}")
else:
    print("No match found.")

# Try regex 2 from npr.py
# match = re.search(r'href="(https://ondemand.npr.org/anon.npr-mp3/.*?\.mp3.*?)"', html)
# This won't work on the snippet above because I didn't include the 'a' tag. 
# But let's check the logic.
