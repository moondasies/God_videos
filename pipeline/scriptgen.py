"""Topic -> original episode script (YAML) + screenplay.

Two engines:
* ``templates`` (default, offline, free): a hand-written library of ORIGINAL bilingual story
  beats per content pillar (Roman Hinglish captions + Devanagari TTS text + English subtitle).
  The topic is matched to a pillar; outfit / location / tone can be overridden. Output follows
  the series structure: hook -> conflict -> Mahadev's guidance -> pushback -> analogy ->
  realisation -> takeaway. It is deliberately simple; edit the YAML before rendering.
* ``claude`` (optional, PAID): drafts fresh dialogue with the Anthropic API. Refuses to run
  without --allow-paid and ANTHROPIC_API_KEY. Output is validated and must still be reviewed.

All generated dialogue is labelled `original_fiction`; nothing is presented as a quotation
from Shiva or scripture.
"""
from __future__ import annotations

import csv
import json
import os
import random
import re
from pathlib import Path

import yaml

from .episode import ROOT

HELPLINE = ("If these feelings are heavy or constant, please talk to someone you trust or a mental-health "
            "professional (India: Tele-MANAS 14416).")

# Each beat: (roman, devanagari, english). Lines are short so a reel lands in 30-40 s.
TEMPLATES = {
    "overthinking": dict(
        keywords=["overthink", "future", "anxiety", "anxious", "worry", "chinta", "fear", "dar", "uncertain", "what if"],
        location="bedroom_night", outfit="home_tshirt", mood="night_reflective", helpline=True,
        title=("Dimaag chup kyun nahi hota?", "Why won't my mind go quiet?"),
        hook=("Raat ke do baj gaye... aur dimaag band hi nahi ho raha.", "रात के दो बज गए... और दिमाग़ बंद ही नहीं हो रहा।", "It's 2 AM... and my mind won't switch off."),
        problem=("Mahadev, agar sab galat ho gaya toh?", "महादेव, अगर सब ग़लत हो गया तो?", "Mahadev, what if everything goes wrong?"),
        reframe=("Aur agar sab theek ho gaya toh?", "और अगर सब ठीक हो गया तो?", "And what if everything goes right?"),
        pushback=("Aap mazaak kar rahe ho... main sach mein pareshaan hoon.", "आप मज़ाक कर रहे हो... मैं सच में परेशान हूँ।", "You're joking... I'm genuinely worried."),
        analogy=("Nadi har mod ki chinta nahi karti... bas behti hai.", "नदी हर मोड़ की चिंता नहीं करती... बस बहती है।", "A river doesn't worry about every bend... it just flows."),
        question=("Toh main bas agla ek kadam dekhun?", "तो मैं बस अगला एक क़दम देखूँ?", "So I just look at the next one step?"),
        confirm=("Haan. Kal ki chinta aaj ki neend na chheene.", "हाँ। कल की चिंता आज की नींद न छीने।", "Yes. Don't let tomorrow's worry steal tonight's sleep."),
        realise=("Ek kadam... ek saans. Itna kaafi hai.", "एक क़दम... एक साँस। इतना काफ़ी है।", "One step... one breath. That's enough."),
        moral=("Kal ki chinta aaj ka sukoon na chheene.", "Don't let tomorrow's worry steal today's peace."),
    ),
    "career_failure": dict(
        keywords=["career", "job", "rejection", "interview", "fail", "exam", "result", "office", "boss", "work"],
        location="corporate_office", outfit="blazer_plaid", mood="hopeful",
        title=("Kya main kisi kaam ki nahi?", "Am I not good enough?"),
        hook=("Phir se rejection mail...", "फिर से रिजेक्शन मेल...", "Another rejection email..."),
        problem=("Mahadev, main kisi kaam ki nahi hoon kya?", "महादेव, मैं किसी काम की नहीं हूँ क्या?", "Mahadev, am I just not good enough?"),
        reframe=("Ek darwaza band hua hai. Tum nahi.", "एक दरवाज़ा बंद हुआ है। तुम नहीं।", "A door has closed. Not you."),
        pushback=("Par kitni baar girungi main?", "पर कितनी बार गिरूँगी मैं?", "But how many times will I fall?"),
        analogy=("Jitni baar uthogi... utni mazboot banogi.", "जितनी बार उठोगी... उतनी मज़बूत बनोगी।", "Every time you rise, you rise stronger."),
        question=("Toh har rejection se kuch seekhun?", "तो हर रिजेक्शन से कुछ सीखूँ?", "So I learn something from each rejection?"),
        confirm=("Haan. Mehnat tumhari hai... nateeja waqt ka.", "हाँ। मेहनत तुम्हारी है... नतीजा वक़्त का।", "Yes. The effort is yours... the result belongs to time."),
        realise=("Kal phir apply karungi. Behtar taiyaari ke saath.", "कल फिर अप्लाई करूँगी। बेहतर तैयारी के साथ।", "I'll apply again tomorrow, better prepared."),
        moral=("Ek rejection tumhari kahani ka ant nahi hai.", "One rejection is not the end of your story."),
    ),
    "family_expectations": dict(
        keywords=["family", "parents", "mummy", "papa", "maa", "expectation", "marriage", "shaadi", "ghar"],
        location="quiet_garden", outfit="kurta", mood="hopeful",
        title=("Unke sapne ya mere?", "Their dreams or mine?"),
        hook=("Mummy-Papa ko lagta hai main galat raasta chun rahi hoon.", "मम्मी-पापा को लगता है मैं ग़लत रास्ता चुन रही हूँ।", "Mom and Dad think I'm choosing the wrong path."),
        problem=("Mahadev, unhe khush karun ya apne sapne chunu?", "महादेव, उन्हें ख़ुश करूँ या अपने सपने चुनूँ?", "Mahadev, do I make them happy or choose my dreams?"),
        reframe=("Kya dono mein se ek hi chunna zaroori hai?", "क्या दोनों में से एक ही चुनना ज़रूरी है?", "Must you choose only one?"),
        pushback=("Woh sunte hi nahi hain!", "वो सुनते ही नहीं हैं!", "They just don't listen!"),
        analogy=("Unka darr bhi pyaar hai... bas alag bhasha mein.", "उनका डर भी प्यार है... बस अलग भाषा में।", "Their fear is love too... just in a different language."),
        question=("Toh pehle unka darr samjhun?", "तो पहले उनका डर समझूँ?", "So first I understand their fear?"),
        confirm=("Haan. Phir apna sach pyaar se kaho.", "हाँ। फिर अपना सच प्यार से कहो।", "Yes. Then tell your truth with love."),
        realise=("Aaj raat unse aaram se baat karungi.", "आज रात उनसे आराम से बात करूँगी।", "I'll talk to them calmly tonight."),
        moral=("Samjho bhi, samjhao bhi — rishte aise hi bante hain.", "Understand, and help them understand — that's how bonds grow."),
    ),
    "heartbreak": dict(
        keywords=["heartbreak", "breakup", "break up", "ex", "love", "pyaar", "dil", "cheated", "relationship"],
        location="rainy_window", outfit="hoodie", mood="night_reflective", helpline=True,
        title=("Ye dard kab jaayega?", "When will this pain go away?"),
        hook=("Usne kaha tha hamesha saath rahega...", "उसने कहा था हमेशा साथ रहेगा...", "He said he'd always be there..."),
        problem=("Mahadev, ye dard kab jaayega?", "महादेव, ये दर्द कब जाएगा?", "Mahadev, when will this pain go away?"),
        reframe=("Dard ko jaldi bhagao mat. Use mehsoos karo.", "दर्द को जल्दी भगाओ मत। उसे महसूस करो।", "Don't rush the pain away. Feel it."),
        pushback=("Par main roz usi ke baare mein sochti hoon.", "पर मैं रोज़ उसी के बारे में सोचती हूँ।", "But I think about him every day."),
        analogy=("Baarish ke baad mitti sabse zyada mehakti hai.", "बारिश के बाद मिट्टी सबसे ज़्यादा महकती है।", "The earth smells sweetest after rain."),
        question=("Matlab is dard ke baad bhi main khil sakti hoon?", "मतलब इस दर्द के बाद भी मैं खिल सकती हूँ?", "So I can still bloom after this?"),
        confirm=("Bilkul. Tum toot nahi rahi... badal rahi ho.", "बिल्कुल। तुम टूट नहीं रही... बदल रही हो।", "Of course. You're not breaking... you're changing."),
        realise=("Thoda waqt doongi... khud ko.", "थोड़ा वक़्त दूँगी... ख़ुद को।", "I'll give myself some time."),
        moral=("Har dard ek din seekh ban jaata hai.", "Every pain becomes a lesson one day."),
    ),
    "letting_go": dict(
        keywords=["let go", "letting go", "attachment", "past", "memories", "yaad", "move on", "chhod"],
        location="rooftop_sunset", outfit="casual_denim", mood="sunset_tender",
        title=("Jo chala gaya, use chhodun kaise?", "How do I let go?"),
        hook=("Purani photos dekh kar sab yaad aa gaya...", "पुरानी फ़ोटोज़ देखकर सब याद आ गया...", "Old photos brought it all back..."),
        problem=("Mahadev, jo chala gaya use chhodun kaise?", "महादेव, जो चला गया उसे छोड़ूँ कैसे?", "Mahadev, how do I let go of what's gone?"),
        reframe=("Mutthi mein ret pakdogi, toh kitni bachegi?", "मुट्ठी में रेत पकड़ोगी, तो कितनी बचेगी?", "Clutch sand in a fist — how much stays?"),
        pushback=("Par chhodna matlab bhool jaana toh nahi?", "पर छोड़ना मतलब भूल जाना तो नहीं?", "But letting go isn't forgetting, right?"),
        analogy=("Nahi. Yaadein rakho... bas bojh utaar do.", "नहीं। यादें रखो... बस बोझ उतार दो।", "No. Keep the memories... just set down the weight."),
        question=("Toh khuli hatheli se pakdun?", "तो खुली हथेली से पकड़ूँ?", "So I hold it with an open palm?"),
        confirm=("Haan. Jo tumhara hai, woh khuli hatheli mein bhi rahega.", "हाँ। जो तुम्हारा है, वो खुली हथेली में भी रहेगा।", "Yes. What's yours stays even in an open palm."),
        realise=("Shukriya, purane din. Ab aage chalti hoon.", "शुक्रिया, पुराने दिन। अब आगे चलती हूँ।", "Thank you, old days. Now I move on."),
        moral=("Pakad dheeli karo — jo tumhara hai, woh rahega.", "Loosen your grip — what's truly yours will stay."),
    ),
    "loneliness": dict(
        keywords=["lonely", "loneliness", "alone", "akeli", "akela", "friends", "nobody"],
        location="coffee_shop", outfit="casual_denim", mood="hopeful", helpline=True,
        title=("Itni akeli kyun hoon?", "Why do I feel so alone?"),
        hook=("Phone mein sau contacts... par baat karne ko koi nahi.", "फ़ोन में सौ कॉन्टैक्ट्स... पर बात करने को कोई नहीं।", "A hundred contacts... and no one to talk to."),
        problem=("Mahadev, main itni akeli kyun hoon?", "महादेव, मैं इतनी अकेली क्यों हूँ?", "Mahadev, why am I so lonely?"),
        reframe=("Kabhi kabhi akelapan khud se milne ka bulawa hota hai.", "कभी कभी अकेलापन ख़ुद से मिलने का बुलावा होता है।", "Sometimes loneliness invites you to meet yourself."),
        pushback=("Par mujhe log chahiye, Mahadev.", "पर मुझे लोग चाहिए, महादेव।", "But I need people, Mahadev."),
        analogy=("Haan. Aur unhe bhi tum. Pehla kadam tum utha sakti ho.", "हाँ। और उन्हें भी तुम। पहला क़दम तुम उठा सकती हो।", "Yes. And they need you. You can take the first step."),
        question=("Toh aaj kisi purane dost ko message karun?", "तो आज किसी पुराने दोस्त को मैसेज करूँ?", "So I message an old friend today?"),
        confirm=("Haan. Aur thoda waqt khud ke saath bhi.", "हाँ। और थोड़ा वक़्त ख़ुद के साथ भी।", "Yes. And spend a little time with yourself too."),
        realise=("Akeli hoon... par khaali nahi.", "अकेली हूँ... पर ख़ाली नहीं।", "I'm alone... but not empty."),
        moral=("Khud se dosti karo — duniya bhi apni lagegi.", "Befriend yourself — the world will feel like home."),
    ),
    "self_love": dict(
        keywords=["self love", "self-love", "mirror", "ugly", "body", "confidence", "self worth", "insecure", "flaw"],
        location="bedroom_night", outfit="home_kurti", mood="night_reflective",
        title=("Main khud ko pasand kyun nahi karti?", "Why can't I like myself?"),
        hook=("Aaine mein bas kamiyan dikhti hain.", "आईने में बस कमियाँ दिखती हैं।", "In the mirror, I only see flaws."),
        problem=("Mahadev, main khud ko pasand kyun nahi kar paati?", "महादेव, मैं ख़ुद को पसंद क्यों नहीं कर पाती?", "Mahadev, why can't I like myself?"),
        reframe=("Jis nazar se doston ko dekhti ho, kabhi khud ko dekha?", "जिस नज़र से दोस्तों को देखती हो, कभी ख़ुद को देखा?", "Ever looked at yourself the way you see your friends?"),
        pushback=("Woh alag hai... unme kamiyan nahi hain.", "वो अलग है... उनमें कमियाँ नहीं हैं।", "That's different... they don't have flaws."),
        analogy=("Chaand mein bhi daag hain. Phir bhi woh roshni deta hai.", "चाँद में भी दाग़ हैं। फिर भी वो रोशनी देता है।", "Even the moon has marks. Still, it gives light."),
        question=("Toh main bhi apni kamiyon ke saath chamak sakti hoon?", "तो मैं भी अपनी कमियों के साथ चमक सकती हूँ?", "So I can shine too, flaws and all?"),
        confirm=("Haan. Khud se pyaar hi sudhaar ka pehla kadam hai.", "हाँ। ख़ुद से प्यार ही सुधार का पहला क़दम है।", "Yes. Self-love is the first step of growth."),
        realise=("Aaj khud se thoda pyaar se baat karungi.", "आज ख़ुद से थोड़ा प्यार से बात करूँगी।", "Today I'll speak to myself more kindly."),
        moral=("Chaand ki tarah — daag ke saath bhi roshan raho.", "Like the moon — shine, marks and all."),
    ),
    "karma_purpose": dict(
        keywords=["karma", "dharma", "purpose", "hard work", "mehnat", "effort", "unnoticed", "result", "patience"],
        location="corporate_office", outfit="blazer_plaid", mood="hopeful",
        title=("Mehnat ka phal kab milega?", "When will my effort pay off?"),
        hook=("Itni mehnat... aur koi notice hi nahi karta.", "इतनी मेहनत... और कोई नोटिस ही नहीं करता।", "So much work... and nobody notices."),
        problem=("Mahadev, mehnat ka phal kab milega?", "महादेव, मेहनत का फल कब मिलेगा?", "Mahadev, when will my hard work pay off?"),
        reframe=("Beej bote hi ped nahi ugta.", "बीज बोते ही पेड़ नहीं उगता।", "A tree doesn't grow the moment you plant a seed."),
        pushback=("Par intezaar bahut lamba lag raha hai.", "पर इंतज़ार बहुत लंबा लग रहा है।", "But the wait feels so long."),
        analogy=("Zameen ke neeche jadein ban rahi hain... dikhti nahi, par hain.", "ज़मीन के नीचे जड़ें बन रही हैं... दिखती नहीं, पर हैं।", "Roots are forming underground... unseen, but there."),
        question=("Toh bas imaandaari se kaam karti rahun?", "तो बस ईमानदारी से काम करती रहूँ?", "So I just keep working honestly?"),
        confirm=("Haan. Achha karm kabhi bekaar nahi jaata.", "हाँ। अच्छा कर्म कभी बेकार नहीं जाता।", "Yes. Good action is never wasted."),
        realise=("Jadein bana rahi hoon... ped bhi aayega.", "जड़ें बना रही हूँ... पेड़ भी आएगा।", "I'm growing roots... the tree will come."),
        moral=("Jo dikhta nahi, woh bhi badh raha hai.", "What you can't see is growing too."),
    ),
    "comparison": dict(
        keywords=["compar", "jealous", "behind", "instagram", "social media", "others", "peeche", "never enough"],
        location="bedroom_night", outfit="home_tshirt", mood="night_reflective",
        title=("Sab mujhse aage kyun?", "Why is everyone ahead of me?"),
        hook=("Sabki life kitni perfect lagti hai...", "सबकी लाइफ़ कितनी परफ़ेक्ट लगती है...", "Everyone's life looks so perfect..."),
        problem=("Mahadev, main hi peeche kyun hoon?", "महादेव, मैं ही पीछे क्यों हूँ?", "Mahadev, why am I the one left behind?"),
        reframe=("Tum unki highlight reel dekh rahi ho... apni poori film se.", "तुम उनकी हाइलाइट रील देख रही हो... अपनी पूरी फ़िल्म से।", "You're comparing their highlight reel with your whole film."),
        pushback=("Par unki reel bhi toh sach hai na?", "पर उनकी रील भी तो सच है ना?", "But their reel is real too, right?"),
        analogy=("Sach hai... par adhoora. Har pedh ka mausam alag hota hai.", "सच है... पर अधूरा। हर पेड़ का मौसम अलग होता है।", "Real... but incomplete. Every tree has its own season."),
        question=("Toh apni race khud se lagaun?", "तो अपनी रेस ख़ुद से लगाऊँ?", "So my only race is with myself?"),
        confirm=("Haan. Kal se behtar — bas itna kaafi hai.", "हाँ। कल से बेहतर — बस इतना काफ़ी है।", "Yes. Better than yesterday — that's enough."),
        realise=("Apni film ki hero main khud hoon.", "अपनी फ़िल्म की हीरो मैं ख़ुद हूँ।", "I'm the hero of my own film."),
        moral=("Doosron ki highlight reel se apni zindagi mat naapo.", "Don't measure your life against someone's highlight reel."),
    ),
    "boundaries": dict(
        keywords=["boundar", "betray", "trust", "hurt", "toxic", "forgive", "maaf", "friend", "dhokha", "respect"],
        location="rooftop_sunset", outfit="blazer_plaid", mood="sunset_tender", helpline=True,
        title=("Har baar 'haan' kyun kehti hoon?", "Why do I always say yes?"),
        hook=("Phir se sabka kaam... aur mera kuch nahi.", "फिर से सबका काम... और मेरा कुछ नहीं।", "Everyone's work again... and nothing for me."),
        problem=("Mahadev, 'na' kehna itna mushkil kyun hai?", "महादेव, 'ना' कहना इतना मुश्किल क्यों है?", "Mahadev, why is saying 'no' so hard?"),
        reframe=("Kyunki tumhe lagta hai pyaar sirf 'haan' se milta hai.", "क्योंकि तुम्हें लगता है प्यार सिर्फ़ 'हाँ' से मिलता है।", "Because you think love only comes from 'yes'."),
        pushback=("Par 'na' bolungi toh log naraz ho jaayenge.", "पर 'ना' बोलूँगी तो लोग नाराज़ हो जाएँगे।", "But if I say no, people will be upset."),
        analogy=("Jo sirf tumhari 'haan' se jude hain... woh tumse nahi jude.", "जो सिर्फ़ तुम्हारी 'हाँ' से जुड़े हैं... वो तुमसे नहीं जुड़े।", "Those tied only to your 'yes' aren't tied to you."),
        question=("Toh pyaar se 'na' bhi keh sakti hoon?", "तो प्यार से 'ना' भी कह सकती हूँ?", "So I can say 'no' kindly too?"),
        confirm=("Bilkul. Apni seema bhi seva hai — khud ki.", "बिल्कुल। अपनी सीमा भी सेवा है — ख़ुद की।", "Of course. A boundary is care — for yourself."),
        realise=("Aaj se meri 'haan' ki bhi keemat hogi.", "आज से मेरी 'हाँ' की भी क़ीमत होगी।", "From today, my 'yes' will mean something."),
        moral=("Pyaar se 'na' kehna bhi khud se pyaar hai.", "Saying 'no' kindly is also self-love."),
    ),
}


def match_pillar(topic, pillar=None):
    if pillar:
        if pillar not in TEMPLATES:
            raise ValueError(f"unknown pillar {pillar}; choose from {sorted(TEMPLATES)}")
        return pillar
    t = topic.lower()
    best, score = "overthinking", 0
    for name, tp in TEMPLATES.items():
        s = sum(1 for k in tp["keywords"] if k in t)
        if s > score:
            best, score = name, s
    return best


def _line(spk, beat, emotion, **extra):
    r, d, e = beat
    ln = dict(speaker=spk, emotion=emotion, roman=r, tts=d, en=e, attribution="original_fiction")
    ln.update(extra)
    return ln


def build_episode_dict(topic, tp, ep_id, number, outfit=None, location=None, tone="gentle", subtitles="hinglish",
                       girl_voice=None, mahadev_voice=None):
    loc = location or tp["location"]
    m_expr = {"gentle": "compassionate", "playful": "playful", "deep": "calm"}[tone]
    shots = [
        dict(id="s01", type="dialogue", background=loc, framing="closeup_girl", min_duration=3.0,
             camera={"from": {"zoom": 1.0}, "to": {"zoom": 1.06}}, sfx=[{"type": "sigh", "at": 0.1}],
             scene=f"Hook: {topic}", actors={"girl": {"expr": "disappointed", "pitch": 0.25, "look": [0.0, 0.4]}},
             lines=[_line("girl", tp["hook"], "disappointed", vo=True, delay=0.3)]),
        dict(id="s02", type="dialogue", background=loc, framing="closeup_girl",
             camera={"from": {"zoom": 1.0}, "to": {"zoom": 1.05}},
             actors={"girl": {"expr": "sad", "pitch_keys": [[0.0, 0.3], [0.6, 0.0]], "look_keys": [[0.0, [0, 0.5]], [0.6, [0.1, -0.3]]]}},
             lines=[_line("girl", tp["problem"], "sad", delay=0.3)]),
        dict(id="s03", type="dialogue", background=loc, framing="two_shot", transition_in="glow", transition_dur=0.5,
             sfx=[{"type": "divine_shimmer", "at": 0.0}], camera={"from": {"zoom": 1.08, "x": 600}, "to": {"zoom": 1.0, "x": 540}},
             actors={"mahadev": {"appear": {"at": 0.1, "dur": 1.2}, "expr": m_expr, "gesture": "lap"},
                     "girl": {"expr": "surprised", "expr_keys": [[1.5, "curious"]], "gesture": "lap"}},
             lines=[_line("mahadev", tp["reframe"], m_expr, delay=0.9, gesture="explain", listener_emotion="thoughtful")]),
        dict(id="s04", type="dialogue", background=loc, framing="closeup_girl",
             actors={"girl": {"yaw": 0.38, "expr": "frustrated", "gesture": "lap", "look": [0.35, 0.0]}},
             camera={"from": {"zoom": 1.0}, "to": {"zoom": 1.05}},
             lines=[_line("girl", tp["pushback"], "frustrated", emotion_end="worried")]),
        dict(id="s05", type="dialogue", background=loc, framing="closeup_mahadev",
             actors={"mahadev": {"yaw": -0.3, "expr": "calm", "gesture": "lap", "look": [-0.3, 0.0]}},
             camera={"from": {"zoom": 1.0}, "to": {"zoom": 1.05, "y": 930}},
             lines=[_line("mahadev", tp["analogy"], "calm", gesture="explain")]),
        dict(id="s06", type="dialogue", background=loc, framing="two_shot", music_swell=True,
             camera={"from": {"zoom": 1.0}, "to": {"zoom": 1.05, "y": 930}},
             actors={"girl": {"expr": "thoughtful", "gesture": "lap"}, "mahadev": {"expr": "smile", "gesture": "lap"}},
             lines=[_line("girl", tp["question"], "curious", listener_emotion="smile"),
                    _line("mahadev", tp["confirm"], "smile", gesture="abhaya", gesture_hold=True, listener_emotion="hopeful")]),
        dict(id="s07", type="dialogue", background=loc, framing="closeup_girl",
             camera={"from": {"zoom": 1.0}, "to": {"zoom": 1.08, "y": 930}},
             actors={"girl": {"yaw": 0.25, "expr": "hopeful", "gesture": "lap", "look": [0.2, -0.1]}},
             lines=[_line("girl", tp["realise"], "hopeful", emotion_end="peaceful")]),
        dict(id="s08", type="moral", background="moral_card", framing="empty", transition_in="dissolve",
             min_duration=3.6, fade_out=0.7, sfx=[{"type": "soft_whoosh", "at": 0.0}], lines=[]),
    ]
    note = "Original fiction generated from the Mahadev & Me template library; not a scriptural teaching."
    if tp.get("helpline"):
        note += " " + HELPLINE
    return dict(
        id=ep_id, number=number, title_roman=tp["title"][0], title_en=tp["title"][1],
        pillar=[k for k, v in TEMPLATES.items() if v is tp][0], topic=topic,
        target_audience="18-30, young Indians navigating modern-life pressure",
        core_problem=topic, moral=dict(roman=tp["moral"][0], english=tp["moral"][1]),
        attribution_note=note, subtitles=subtitles,
        voices=dict(girl=girl_voice or "girl_preview", mahadev=mahadev_voice or "mahadev_preview"),
        music=dict(mood=tp["mood"]),
        characters=dict(girl=dict(outfit=outfit or tp["outfit"]), mahadev={}),
        shots=shots,
        social=dict(caption=f"{tp['title'][0]} 🔱\n{tp['moral'][0]}\n(Original fictional story – Mahadev & Me)"
                            + ("\n" + HELPLINE if tp.get("helpline") else ""),
                    hashtags=["#MahadevAndMe", "#Mahadev", "#HarHarMahadev", "#HindiReels", "#Hinglish",
                              "#SpiritualReels", "#AnimatedStory", "#" + re.sub(r"\W", "", tp["title"][1].title())]),
    )


# ------------------------------------------------------------------ optional Claude drafting
def claude_beats(topic, tp, allow_paid=False):
    """Ask Claude for fresh beats in the same schema. PAID – needs explicit --allow-paid."""
    if not allow_paid:
        raise SystemExit("--llm claude uses the paid Anthropic API. Re-run with --allow-paid after approving the cost.")
    import anthropic
    beat = {"type": "object", "additionalProperties": False, "required": ["roman", "devanagari", "english"],
            "properties": {"roman": {"type": "string"}, "devanagari": {"type": "string"}, "english": {"type": "string"}}}
    keys = ["hook", "problem", "reframe", "pushback", "analogy", "question", "confirm", "realise"]
    schema = {"type": "object", "additionalProperties": False, "required": keys + ["title", "moral"],
              "properties": {**{k: beat for k in keys}, "title": beat, "moral": beat}}
    system = ("You write ORIGINAL short Hinglish dialogue for 'Mahadev & Me', an animated series where a modern young "
              "Indian woman talks with a compassionate, gently playful Mahadev. Rules: each line under 60 characters; "
              "conversation, not sermon; the girl may push back; never present a line as a quote from Shiva or any "
              "scripture; never dismiss trauma or mental-health needs; 'devanagari' is the same line in Devanagari "
              "for Hindi TTS (transliterate English loan-words); 'english' is a subtitle.")
    client = anthropic.Anthropic()
    resp = client.messages.create(
        model="claude-opus-5-5", max_tokens=4000, system=system,
        output_config={"effort": "medium", "format": {"type": "json_schema", "schema": schema}},
        messages=[{"role": "user", "content": f"Topic: {topic}\nReturn the 8 story beats plus a title and a one-line moral."}],
    )
    if resp.stop_reason == "refusal":
        raise SystemExit("Claude declined this topic; use the template engine or rephrase.")
    data = json.loads(next(b.text for b in resp.content if b.type == "text"))
    out = dict(tp)
    for k in keys:
        out[k] = (data[k]["roman"], data[k]["devanagari"], data[k]["english"])
    out["title"] = (data["title"]["roman"], data["title"]["english"])
    out["moral"] = (data["moral"]["roman"], data["moral"]["english"])
    return out


def next_episode_id():
    nums = [int(m.group(1)) for p in (ROOT / "episodes").glob("episode_*") if (m := re.match(r"episode_(\d+)", p.name))]
    n = max(nums, default=0) + 1
    return f"episode_{n:03d}", n


def generate_episode(topic, outfit=None, location=None, tone="gentle", pillar=None, ep_id=None, subtitles="hinglish",
                     girl_voice=None, mahadev_voice=None, llm="none", allow_paid=False, seed=None):
    key = match_pillar(topic, pillar)
    tp = TEMPLATES[key]
    if llm == "claude":
        tp = claude_beats(topic, tp, allow_paid)
        TEMPLATES["_claude"] = tp
    eid, num = (ep_id, int(re.sub(r"\D", "", ep_id) or 0)) if ep_id else next_episode_id()
    ep = build_episode_dict(topic, tp, eid, num, outfit, location, tone, subtitles, girl_voice, mahadev_voice)
    if llm == "claude":
        ep["pillar"] = key
        TEMPLATES.pop("_claude", None)
    d = ROOT / "episodes" / eid
    d.mkdir(parents=True, exist_ok=True)
    (d / "episode.yaml").write_text("# Generated by `python -m pipeline new` – review & edit before publishing.\n"
                                    + yaml.safe_dump(ep, allow_unicode=True, sort_keys=False, width=120), encoding="utf-8")
    from .episode import load_episode
    from .storyboard import script_markdown
    (d / "script.md").write_text(script_markdown(load_episode(eid)), encoding="utf-8")
    return d


def list_ideas(pillar=None, n=10):
    f = ROOT / "research" / "50_original_reel_ideas.csv"
    rows = list(csv.DictReader(f.open(encoding="utf-8")))
    if pillar:
        rows = [r for r in rows if pillar.lower() in r["pillar"].lower()]
    return rows[:n]
