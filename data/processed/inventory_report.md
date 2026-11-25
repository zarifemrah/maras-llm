# Kahramanmaraş Ağzı — Phase 1 Corpus Inventory Report

## 1. Collection Summary
- **Academic PDFs downloaded:** 11 / 15 discovered via OpenAlex (`657` total pages extracted)
- **Unique Lexicon Entries (`lexicon.jsonl`):** **2102**
- **Authentic Dialect Texts & Examples (`dialect_texts.jsonl`):** **3434**
- **TDK `sozluk.gov.tr` status:** `derleme.php` timed out and `/derleme` now serves an SPA frontend; GitHub open dumps had no Derleme Sözlüğü export.
- **DergiPark note:** `/tr/search` presented an `Arama Doğrulama` verification page so search scraping was skipped; open-access articles were discovered via OpenAlex API and downloaded directly.
- **Skipped PDFs during lexicon parsing:** `10_asyatik-turkiye-de-yasam...` (1875 travelogue, non-dialect) and `13_mine-kilic...` (book review with broken custom font encoding). Phonetic-grammar papers (`01_`, `02_`, `05_`) are retained in `data/raw/dergipark/texts/` as grammar references.

## 2. Breakdown by Source & Region
### Lexicon Entries by Primary Source
- `dergipark:telli-aslan-2023-2`: 446
- `emu:kaya-2017-afsin`: 440
- `web:marasavucumda`: 383
- `dergipark:telli-aslan-2023-1`: 273
- `web:ansiklopedi46-merkez`: 230
- `dergipark:turkoglu-2024-eski-turkce`: 196
- `dergipark:kirik-2025-turkoglu`: 127
- `web:ansiklopedi46`: 5
- `web:marasmanset`: 1
- `web:tr.wiktionary`: 1

### Lexicon Entries by Region
- `general`: 1305
- `afsin`: 440
- `merkez`: 230
- `turkoglu`: 127

### Dialect Texts by Source
- `emu:kaya-2017-afsin`: 3156
- `dergipark:kirik-2025`: 209
- `dergipark:gultekin-2005`: 27
- `web:ansiklopedi46-kilic-2008`: 21
- `web:marasavucumda`: 19
- `web:ansiklopedi46`: 2

### Dialect Texts by Region
- `afsin`: 3156
- `turkoglu`: 209
- `merkez`: 36
- `general`: 33

## 3. Sample Lexicon Entries (20)
- **Adı batasıca** (`general`, *web:marasavucumda*): Eti haram olan domuza, adını anmayı da haram sayanlar tarafından layık görülen isim. Hınzır.
- **Ağnanmak** (`general`, *web:marasavucumda*): Belenmek. Bulanmak. -Gene toprağa ağnanıp mı geldin evladım. Ne bu halin?
- **Akaba** (`general`, *web:marasavucumda*): Eğimli arazi, yüzey, yer. Yörep .
- **Appeş** (`general`, *web:marasavucumda*): 1. İri gulle . Löklökü . 2. Kafası büyükçe olan. Zıttı nucük . ( İğde / Elbistan )
- **avın** (`general`, *dergipark:telli-aslan-2023-1*): Hayvanların çiftleşme yeri
- **aynalı yular** (`general`, *dergipark:telli-aslan-2023-1*): Sadece kervanın başından giden ata takılan ve üzerinde aynanın olduğu deriden yapılan yuların adıdır
- **bağdadi** (`general`, *dergipark:telli-aslan-2023-1*): Bağdat’tan geldiği düşünülen ve Avrupa’da en fazla beslenen kuş türü
- **balek** (`general`, *dergipark:telli-aslan-2023-1*): Yazları büyükbaş hayvanları ısırarak kaçmasına neden olan sinek, büvelek
- **alengirli** (`turkoglu`, *dergipark:kirik-2025-turkoglu*): Ayrıntılı. (krş. DS-TTAS-, 2025)
- **açışmak** (`turkoglu`, *dergipark:kirik-2025-turkoglu*): (krş. DS I, s. 53) acışmak (I) 2. f. Ölenin ardından aşırı üzülmek; çok acı duymak."
- **gartaşık** (`turkoglu`, *dergipark:kirik-2025-turkoglu*): Taze olmayan sebze, kart.
- **gabiş** (`turkoglu`, *dergipark:kirik-2025-turkoglu*): Kel, saçı olmayan.
- **acıklanmak** (`general`, *dergipark:turkoglu-2024-eski-turkce*): üzülmek, acımak, müteessir olmak
- **ağal** (`general`, *dergipark:turkoglu-2024-eski-turkce*): gece, kırda yatırılan koyun sürüsünü korumak için yapılan çitle çevrili yer, açık ağıl
- **ağrıklanmak** (`general`, *dergipark:turkoglu-2024-eski-turkce*): Sözcük, Eski Türkçede "ağrımak, hasta olmak" , Kahramanmaraş ağzında ise "hastalanmak" anlamındadır.
- **ağrıklı** (`general`, *dergipark:turkoglu-2024-eski-turkce*): maraz, hastalıklı
- **aciş-** (`afsin`, *emu:kaya-2017-afsin*): Üzülmek, acımak
- **aciycak** (`afsin`, *emu:kaya-2017-afsin*): Azıcık
- **açık ekmek** (`afsin`, *emu:kaya-2017-afsin*): Yufka ekmeği
- **adeleş-** (`afsin`, *emu:kaya-2017-afsin*): İnatlaşmak

## 4. Sample Authentic Dialect Sentences & Excerpts
- **[general]** Bıldır, Binboğa 'ya tırmanmıştık. *(raw: `Bıldır, Binboğa ‘ya tırmanmıştık.`)*
- **[general]** Ceyhan'ın şehri tam ortadan ikiye böldüğü Elbistan'da çocuklar çimmeyi bisiklet sürmekten önce öğrenirdi. *(raw: `Ceyhan’ın şehri tam ortadan ikiye böldüğü Elbistan’da çocuklar çimmeyi bisiklet sürmekten `)*
- **[general]** Gonur gonur gezme evladım . *(raw: `Gonur gonur gezme evladım .`)*
- **[general]** Kış güneşi yüzünü göstermeye başladı. Göğüne göğüne ısınırız artık. *(raw: `Kış güneşi yüzünü göstermeye başladı. Göğüne göğüne ısınırız artık.`)*
- **[general]** bi gısraķ var kin *(raw: `bi ġısraķ var kin`)*
- **[general]** gülmeyem deyim *(raw: `gülmeyem dėyim`)*
- **[general]** bugüne kadar' *(raw: `bugüne kadar’`)*
- **[general]** varana kadar' *(raw: `varana 
kadar’`)*
- **[turkoglu]** Apdal düğünde dembildeni çaldı, zurnacı zurnasını çaldı; şenlikli oldu. *(raw: `Apdal düğünde dembildēni çaldı, zurnacı zurnasını çaldı; şenlikli oldu.`)*
- **[turkoglu]** herifim bir iş yaparğan her şini düşünür; alengirli bağar hey yerine. *(raw: `herĭfim bir iş yapar─an her ş┬ni düşünür; alengirli ba─ar hey yėrine.`)*
- **[turkoglu]** bahciğe incir dikdigidi; cisi abbas inciri çıkdı şukur; par eder çok. *(raw: `bahci╒e incir diKdigidi; cisi abbas inciri çı╧dı şú╧úr; parΩeder ço╧.`)*
- **[turkoglu]** bekmez gatar yerik, gatıg olur. *(raw: `bekmez ġatar yėrik, ġatıġΩoļur.`)*
- **[afsin]** Benim annadığıma göre bak bu Çuvaloğlu, Abdırahmanoğlu, Mesecioğlu üçüncü hani, dördüncü haniye de Bayzit dedem gelmiş, dördüncü haniye. *(raw: `Benim annadığıma göre baḳ bu Çuvaloğlu, Abdırahmanoğlu, Mesecioğlu üçüncü hāni, dördüncü h`)*
- **[afsin]** Ondan sona Bayzit dedem annesiynen barabar geliyo burıya. Mesela o zaman kön danasını sıırını güderimiş, olum gel Bayazıt gel yemek yiyek diyene ikinciye yemea üçüncüye varmazımış utandindan. *(raw: `Ondan sōna Bayzit dedem annesiynen barabar geliyo burıya. Meselā o zaman ḵȫŋ danasını síír`)*
- **[afsin]** Böle böle çuğalmış, o da ev bark seabi oldukdan sona bir anesi getmiş banı yolmuş, banı yoluşun haydın demiş şiye gedek, o zaman Avşun'un adı Efsus'udu orıya gedek, müfdüye sorak. *(raw: `Bȫle bȫle çuğalmıĢ, o da ev barḳ seabi olduḳdan sōna bir ánesi getmiĢ bānı yolmuĢ, bānı yo`)*
- **[afsin]** Ney dic z, köye çıkmışlar, neydici orda, yemin, ne yapacaksiz, yemin ederik, temam olum yemin etdi, geri de öle gelirmiş öle. *(raw: `Nėy dic z, köye çıḳmıĢlar, nėydici orda, yemin, ne yapacaḳsīz, yemin ederik, temam ōlum ye`)*

## 5. Recommended Phase 2 Options
1. **Build the Chat Dataset (`data/chat/{train,valid,test}.jsonl`):** Convert the authentic texts + lexicon into ~800–1,500 natural Kahramanmaraş Merkez multi-turn chat dialogues grounded strictly in `lexicon.jsonl` and `grammar_notes.md`, with a sample for your native speaker spot-check.
2. **Optional Extra Authentic Text:** If you download YÖK Tez PDFs manually (e.g., Esra Kırık's *Kahramanmaraş Merkez İlçe Ağzı*) into `data/raw/yok_tez/`, we can parse their *Metinler* section directly into `dialect_texts.jsonl` before generating Phase 2 chat pairs.
3. **Prototype MLX QLoRA:** Run `configs/lora_qwen35_9b.yaml` first for fast iteration, then train the final adapter with `configs/lora_gemma3_12b.yaml`.
