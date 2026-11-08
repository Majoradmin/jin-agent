"""In-app knowledge base: research findings, official routes, glossary, help.

All content is Roman Urdu. Technical terms stay in English on purpose.
This module deliberately contains NO instructions for bypassing account,
FRP, MDM, carrier or activation locks.
"""

BOUNDARY = {
    "title": "Sahulat & Safe Service Policy — hum kya madad karte hain",
    "policy_name": "Sahulat & Safe Service Policy",
    "canonical": (
        "Purana internal naam HARD POLICY tha. Sirf naam aur andaaz badla hai — "
        "qaida bilkul waisa ka waisa hai: koi bypass automation ya step-by-step "
        "tareeqa nahi, koi role-based chhoot nahi."
    ),
    "lead": (
        "Hum logon ki sahulat ke liye kaam karte hain: sahi firmware, saaf documentation "
        "aur jahan malik ki tasdeeq chahiye wahan seedha official raasta."
    ),
    "helps": [
        "Sahulat / Official Route view: customer request ki wajah + official link + agla jaez qadam.",
        "6 brand-wise official routes with required documents aur verified links.",
        "Proof-of-ownership checklist, customer consent form aur Roman Urdu / English service-request letter.",
        "Case / asset register — sarkari aur department devices ka local audit trail.",
    ],
    "does": [
        "Local firmware packages scan, parse aur validate karta hai (MTK scatter/preloader/DA, Qualcomm Firehose/rawprogram/patch/GPT).",
        "Missing images, storage mismatch (eMMC vs UFS), sector overlap, image-size-overshoot, duplicate partition aur corrupt/tiny loader pakarta hai.",
        "Har package ka local catalog, fingerprint, notes aur model card rakhta hai — sab kuch aap ke apne PC par.",
        "Real-time research agent: Google News, HN, GitHub releases aur 7 RSS feeds se live info la kar Roman Urdu mein khulasa deta hai, filters ke saath.",
        "Ownership / job register: IMEI, customer, proof-of-ownership aur official route ka record.",
    ],
    "does_not": [
        "Huawei ID, Google FRP, Samsung Account / KG, MDM, carrier lock ya iCloud Activation Lock bypass karne ka koi automation ya step-by-step tareeqa nahi deta.",
        "Kisi bhi partition (frp, persistent, modemst, nvram, devinfo, ...) ko erase/write karne wali script, rawprogram ya firehose command generate nahi karta.",
        "Server-side ownership record (Apple activation server, Google Device Protection, Knox Guard, Huawei cloud) ko badalne ka dawa nahi karta — ye technologically bhi mumkin nahi.",
        "Cracked tools, leaked loaders ya auth files provide nahi karta.",
    ],
    "why": "Account / activation locks anti-theft hain, sirf software bugs nahi. In ka faisla manufacturer ke server par hota hai. Is liye in ka 'pure local tool' banana na sirf ghair-qanooni ho sakta hai, balke aksar kaam bhi nahi karta — reset ya re-flash ke baad lock wapas aa jata hai. Isi liye main ne app ko uss hisse par nahi banaya jahan aap phans rahe hain (files), aur uss hisse par nahi jahan malik ki tasdeeq chahiye (accounts).",
}

OFFICIAL_ROUTES = [
    {
        "issue": "Huawei ID / device activation screen (EMUI 16, HarmonyOS)",
        "steps": [
            "Pehle Huawei ID password recover karain: consumer.huawei.com > Support > HUAWEI ID.",
            "Agar device 'Activate device' screen par hai to Huawei Support ka official 'activation device page' guide dekhein.",
            "Doosre haath ka phone hai to asli malik se Huawei ID aur password, ya usay 'Find My Phone' se device remove karne ko kahein.",
            "In sab mein na-kamyabi par purchase proof (invoice, box, IMEI) le kar Huawei Authorized Service Center jayein.",
        ],
        "links": [
            ("Huawei ID support (global)", "https://consumer.huawei.com/en/support/mobile-services/huawei-id/"),
            ("Huawei Support home", "https://consumer.huawei.com/en/support/"),
            ("Huawei activation-device guide (CN)", "https://consumer.huawei.com/cn/support/content/zh-cn00448755.html"),
        ],
        "note": "EMUI 16 (July 2026, Android 16 base) overseas models par hai; China models HarmonyOS par hain. Dono ka account system cloud-based hai — local flash se Huawei ID nahi hatta.",
    },
    {
        "issue": "Google FRP (Android Device Protection)",
        "steps": [
            "Asli Google account aur password se sign in karain. Password abhi badla hai to Google 24 ghante baad retry ka mashwara deta hai.",
            "Account recovery: accounts.google.com/signin/recovery.",
            "Second-hand device: pichhle malik se contact karain ke wo apna account device se remove karein.",
            "Purchase proof ke saath authorized service center.",
        ],
        "links": [
            ("Google Account Recovery", "https://accounts.google.com/signin/recovery"),
            ("Android FRP help", "https://support.google.com/android/answer/9450130"),
        ],
        "note": "FRP, screen lock, MDM, carrier lock aur bootloader lock char alag cheezein hain — aik hatana doosre ko nahi hatata.",
    },
    {
        "issue": "iPhone / iPad Activation Lock",
        "steps": [
            "Apple Account aur password, ya device passcode darj karain.",
            "Pichhla malik iCloud.com > Find Devices se device apne account se remove karein.",
            "Corporate / school device: IT admin se MDM release karwayein.",
            "Purchase proof ke saath Apple Support se Activation Lock removal request.",
        ],
        "links": [
            ("Apple Activation Lock support", "https://al-support.apple.com/"),
            ("Apple: Activation Lock", "https://support.apple.com/en-us/108794"),
        ],
        "note": "Carrier policy aur Activation Lock Apple ke activation server par rehte hain. Is liye official unlock factory reset ke baad bhi qaim rehta hai; koi local Windows tool is database ko edit nahi kar sakta.",
    },
    {
        "issue": "Samsung Account / Knox Guard / MDM",
        "steps": [
            "Samsung Account recovery.",
            "Knox Guard (finance / rental / insurance lock): registering party ko console se unlock karna hota hai.",
            "MDM / Knox Mobile Enrollment: managing organization se de-registration.",
            "Galat IMEI registration: invoice ke saath Samsung support ko IMEI de-registration request.",
        ],
        "links": [
            ("Samsung Support", "https://www.samsung.com/support/"),
        ],
        "note": "Knox 0x1 (bootloader unlock se eFuse trip) physically irreversible hai; koi software isay wapas nahi la sakta.",
    },
    {
        "issue": "Carrier / SIM network lock",
        "steps": [
            "Operator se unlock eligibility check karain (account paid, contract complete, device blacklist mein nahi).",
            "Operator approval ke baad Apple / manufacturer server record update hota hai.",
        ],
        "links": [
            ("GSMA IMEI blacklist info", "https://www.gsma.com/"),
        ],
        "note": "Blacklisted / stolen IMEI ko 'clean' karwana alag aur aksar ghair-qanooni kaam hai — is app mein is ki koi support nahi.",
    },
]

TOOL_ARCH = [
    {
        "h": "1. Paid tools asal mein 'service' hain, software nahi",
        "b": "Chimera Tool aur UnlockTool ka model hai: Windows client + cloud authorization + subscription/credits. Chimera 2011 se chal raha hai (Basic $99.9 / Professional $149.9 / Premium $189.9 saalana, device-connection quotas ke saath) aur munafi' asal mein per-operation credits se aata hai (10 credits = $1; maslan kai FRP / network jobs 90–153 credits). UnlockTool 2017–18 mein Vietnam se aaya, pure time-based subscription ($20/3 mah, $30/6 mah, $50/12 mah) bina per-job charges ke. Dono ~42–44 updates saalana dete hain. Is liye in ka 'moat' code nahi balkay loader/exploit intelligence, model coverage matrix aur community test-point database hai.",
    },
    {
        "h": "2. Technical stack brand se nahi, 'entry mode' se banta hai",
        "b": "Samsung Download/Odin (BL/AP/CP/CSC, binary revision downgrade mana), Samsung Exynos EUB, Qualcomm EDL 9008 (Sahara protocol → Firehose programmer upload → rawprogram/patch XML → storage read/write), MediaTek BROM/Preloader (scatter + Download Agent + auth/SLA/DAA), aur ADB/MTP/Factory mode. Har naya security level (MTK 2025/2026 DA auth, Snapdragon no-auth changes, Samsung BIT) purane loader ko be-asar kar deta hai — isi liye subscription 'update speed' bechta hai.",
    },
    {
        "h": "3. Sabse bari structural hadd",
        "b": "Ye tools device ki LOCAL state (partitions, flags, firmware) badal sakte hain. Lekin ownership SERVER par rehti hai: Apple activation server, Google Device Protection, Knox Guard/MDM IMEI registry, Huawei cloud account. Tool is server ko chhoo nahi sakta. Isi liye 2026 mein kai 'bypass' temporary hote hain, re-lock ho jate hain, aur 2026-04 wale Knox Mobile Enrollment drift jaise cases mein sirf invoice + IMEI de-registration hi kaam karta hai. Industry ka trend clear hai: firmware repair aur hardware-level kaam ki value rehti hai, 'ownership bypass' ki jagah tang hoti ja rahi hai.",
    },
    {
        "h": "4. Qanooni pehlu (khud ko bachane ke liye zaroori)",
        "b": "US mein 2014 Unlocking Consumer Choice Act ne apne phone ka carrier unlock jaez kiya, magar DMCA §1201(a)(2) 'evasion tool bechne' ko alag se target karta hai. China / Pakistan / Gulf including markets mein bhi IMEI tampering, blacklist cleanup aur bina malik ki device par FRP ka kaam sabse zyada risk wala hai. AmalI nateeja: har job par IMEI + customer ID + purchase proof ka register rakhein (MobileLab ka Job Register isi liye hai), aur firmware repair / system restore ko apna primary business rakhein.",
    },
    {
        "h": "5. To aap ko paid tool ki jagah kya chahiye?",
        "b": "Aap ka asli rukavat 'account bypass' nahi balkay sahi firmware package banana hai: scatter ka har referenced image maujood ho, preloader chipset se match kare, DA/auth version sahi ho, Qualcomm Firehose ka eMMC/UFS type theek ho, rawprogram XML ki har image exist kare, sector size aik ho, LUN coverage poora ho, koi range overlap na ho. Ye sab 100% local, 100% legal aur 100% aap ke PC par ho sakta hai — MobileLab yahi karta hai. Baqi jahan server-side ownership aati hai, wahan official route hi aik maqbool aur durable raasta hai.",
    },
]

GLOSSARY = [
    ("Preloader", "MTK ka pehla boot stage. DRAM init aur BROM→DA handoff karta hai. Galat model ka preloader = port aa kar chala jata hai."),
    ("BROM", "MediaTek Boot ROM — chip ke andar ka read-only code, USB download mode ka entry point."),
    ("DA (Download Agent)", "MTK par flash operations chalane wala agent. Naye security levels par signed DA + auth/SLA/DAA chahiye."),
    ("Scatter file", "MTK partition layout text file: partition_name, file_name, linear_start_addr, partition_size, region, storage."),
    ("Sahara", "Qualcomm EDL (9008) ka pehla protocol — host se programmer image chip par bhejta hai."),
    ("Firehose", "Sahara ke baad chip par chalne wala programmer (prog_emmc_firehose_*.mbn / prog_ufs_firehose_*.elf). eMMC vs UFS wala loader alag hota hai."),
    ("rawprogram XML", "QFIL / fh_loader ka partition write map: label, filename, start_sector, num_partition_sectors, SECTOR_SIZE_IN_BYTES, LUN."),
    ("patch XML", "rawprogram ke baad GPT / boot header mein byte-level patch lagane wali file."),
    ("LUN", "UFS ka logical unit number. UFS firmware aksar LUN 0..5 ke liye alag alag rawprogram XML rakhta hai."),
    ("FRP", "Factory Reset Protection (Android 5.1 se). Ye fault nahi, Google account ke zariye ownership check hai."),
    ("Activation Lock", "Apple ka server-side anti-theft. Device par nahi, Apple activation database par rehta hai."),
    ("eFuse / Knox 0x1", "Samsung bootloader unlock par physical fuse trip — irreversible, sirf motherboard replacement."),
    ("EMUI 16", "Huawei ka 2026 wala global ROM (July 2026 launch, Android 16 AOSP base). China models HarmonyOS par hain; GMS officially nahi."),
]

HELP = [
    ("Chalana", "MobileLab folder mein run.bat par double-click karain. Browser khud http://127.0.0.1:8765 par khul jayega. Koi pip install, koi API key, koi account nahi — sirf Python 3.10+ chahiye."),
    ("Pehla scan", "Firmware Packages tab mein apna firmware folder ka full path likhein (maslan C:\\Firmware\\Pura90_EMUI16), phir 'Scan + Validate' dabayein. Test ke liye samples folder ka path de sakte hain."),
    ("Research Agent", "Koi topic likhein ya preset chunein, sources aur category filter lagayein, 'Live fetch' dabayein. 'Sirf zaroori' toggle kam score wali khabarein chhupa deta hai. Har card ka Roman Urdu khulasa + asal English headline + link milta hai."),
    ("Filters", "Include query, exclude words, days (freshness), min score, category, source. Bookmark ki hui khabarein 'Saved' mein rehti hain."),
    ("Model Brief", "Model number likhein → local model card + usi model par live news. Apna khud ka model card add/edit kar sakte hain (chipset, storage, official link, notes)."),
    ("Job Register", "Har device ka IMEI, customer, purchase proof aur official route note karain. Ye aap ka legal audit trail hai."),
    ("Sahulat / Official Route", "Customer ki request likh kar check karain → wajah + official link + agla jaez qadam. Brand-wise documents, checklist, consent, Roman Urdu / English letter aur case register aik hi view mein. Bypass wali line barqarar hai."),
    ("Optional LLM", "Settings mein koi OpenAI-compatible endpoint + key + model bhar dein to top 12 khabaroon ka khulasa model se natural Roman Urdu mein likha jayega. Warna built-in offline rule-based khulasa chalta hai."),
    ("Privacy", "SQLite DB data/mobilelab.db mein hai. Scan aur catalog bilkul offline. Research tab hi internet use karta hai aur woh bhi sirf public RSS/JSON feeds se."),
    ("Band karne ke liye", "run.bat wali black window band kar dein ya Ctrl+C dabayein."),
]

SECURITY_NOTE = "Hassas partitions (frp, persistent, config, devinfo, modemst1/2, nvram, nvdata, seccfg, proinfo, ...) sirf FLAG kiye jate hain taake aap galti se identity / calibration data na mitayein. App in par koi write/erase operation nahi banata."
