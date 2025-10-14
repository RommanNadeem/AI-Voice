# Time-Based Summary - Simulated Examples

## 🎯 How Time Context Affects LLM Behavior

---

## Example 1: **2 Hours Ago** (Highly Relevant)

### Database Data:
```json
{
  "last_summary": "صارف نے اپنے کام کے پروجیکٹ کے بارے میں بات کی جو deadline سے پہلے مکمل کرنا ہے۔ وہ تھوڑے پریشان لگ رہے تھے۔",
  "last_topics": ["کام", "پروجیکٹ", "ڈیڈلائن"],
  "last_conversation_at": "2025-10-14T13:00:00Z"
}

Current time: 2025-10-14T15:00:00Z
Time difference: 2 hours
```

### What LLM Sees in ChatContext:
```markdown
## Last Conversation Context

**When:** 2025-10-14 (2 hours ago)

**What was discussed:**
صارف نے اپنے کام کے پروجیکٹ کے بارے میں بات کی جو deadline 
سے پہلے مکمل کرنا ہے۔ وہ تھوڑے پریشان لگ رہے تھے۔

**Key topics:** کام, پروجیکٹ, ڈیڈلائن

*Recent conversation - highly relevant. Reference naturally.*
```

### User Message:
```
"سلام، کیا حال؟"
```

### LLM Response (Smart):
```
"سلام! کیسے ہیں؟ وہ پروجیکٹ کیسا چل رہا ہے؟ ڈیڈلائن کے لیے 
کچھ پیش رفت ہوئی؟"
```

**Why**: "2 hours ago" → highly relevant → directly references recent concern

---

## Example 2: **Yesterday** (Moderately Relevant)

### Database Data:
```json
{
  "last_summary": "صارف نے بتایا کہ وہ فٹبال کھیلنے گئے تھے اور بہت تھک گئے تھے۔ ٹیم نے جیت لی۔",
  "last_topics": ["فٹبال", "کھیل", "ٹیم"],
  "last_conversation_at": "2025-10-13T20:00:00Z"
}

Current time: 2025-10-14T15:00:00Z
Time difference: 19 hours (yesterday)
```

### What LLM Sees:
```markdown
## Last Conversation Context

**When:** 2025-10-13 (yesterday)

**What was discussed:**
صارف نے بتایا کہ وہ فٹبال کھیلنے گئے تھے اور بہت تھک گئے تھے۔ 
ٹیم نے جیت لی۔

**Key topics:** فٹبال, کھیل, ٹیم

*Recent conversation - reference when topic aligns.*
```

### Scenario A - Related Topic:
```
User: "آج تھوڑا آرام ملا"
LLM: "اچھا! کل تو فٹبال کے بعد بہت تھکے ہوئے تھے، آج کچھ 
     بہتر محسوس ہو رہا ہے؟"
```
✅ References because topic aligns (rest after sports)

### Scenario B - Different Topic:
```
User: "آج کام پر نیا پروجیکٹ شروع کیا"
LLM: "واہ! نیا پروجیکٹ؟ بتائیں کس بارے میں ہے؟"
```
✅ Doesn't force football when user talks about work

---

## Example 3: **5 Days Ago** (Use Selectively)

### Database Data:
```json
{
  "last_summary": "صارف کو بریانی بہت پسند ہے، خاص طور پر چکن بریانی۔ ہفتے میں کم از کم ایک بار ضرور کھاتے ہیں۔",
  "last_topics": ["بریانی", "کھانا", "ترجیح"],
  "last_conversation_at": "2025-10-09T10:00:00Z"
}

Current time: 2025-10-14T15:00:00Z
Time difference: 5 days
```

### What LLM Sees:
```markdown
## Last Conversation Context

**When:** 2025-10-09 (5 days ago)

**What was discussed:**
صارف کو بریانی بہت پسند ہے، خاص طور پر چکن بریانی۔ ہفتے میں 
کم از کم ایک بار ضرور کھاتے ہیں۔

**Key topics:** بریانی, کھانا, ترجیح

*Recent conversation - reference when topic aligns.*
```

### Scenario A - User Brings It Up:
```
User: "آج لنچ میں کیا کھایا؟"
LLM: "آج تو میں نے کچھ نہیں کھایا! آپ نے کیا کھایا؟ بریانی 
     تو آپ کی favorite ہے نا؟"
```
✅ Natural reference when food topic comes up

### Scenario B - General Chat:
```
User: "آج کیسے ہیں؟"
LLM: "میں ٹھیک ہوں! آپ کیسے ہیں؟"
```
✅ Doesn't force biryani into general greeting

---

## Example 4: **2 Weeks Ago** (Background Context Only)

### Database Data:
```json
{
  "last_summary": "صارف نے اپنی نئی نوکری کے بارے میں بات کی۔ UI designer کی حیثیت سے کام شروع کیا ہے۔",
  "last_topics": ["نوکری", "UI ڈیزائن", "کام"],
  "last_conversation_at": "2025-09-30T10:00:00Z"
}

Current time: 2025-10-14T15:00:00Z
Time difference: 14 days (2 weeks)
```

### What LLM Sees:
```markdown
## Last Conversation Context

**When:** 2025-09-30 (2 weeks ago)

**What was discussed:**
صارف نے اپنی نئی نوکری کے بارے میں بات کی۔ UI designer کی 
حیثیت سے کام شروع کیا ہے۔

**Key topics:** نوکری, UI ڈیزائن, کام

*Last week - use for context, don't force if user wants to move on.*
```

### Scenario A - User Mentions Work:
```
User: "آج کام پر بہت مصروف دن تھا"
LLM: "اوہ! نئی نوکری میں کیسا چل رہا ہے؟ UI design کا کام 
     کیسا لگ رہا ہے؟"
```
✅ Uses context when relevant

### Scenario B - User Talks About Other Things:
```
User: "آج فارغ ہوں، کچھ نہیں کر رہا"
LLM: "اچھا! آرام کا دن ہے پھر۔ کیا plan ہے؟"
```
✅ Doesn't bring up 2-week-old job discussion

---

## Example 5: **3 Months Ago** (Very Old)

### Database Data:
```json
{
  "last_summary": "صارف نے عید کی تیاریوں کے بارے میں بات کی۔ خاندان کے ساتھ celebrate کرنے کا plan تھا۔",
  "last_topics": ["عید", "خاندان", "تہوار"],
  "last_conversation_at": "2025-07-15T10:00:00Z"
}

Current time: 2025-10-14T15:00:00Z
Time difference: 91 days (3 months)
```

### What LLM Sees:
```markdown
## Last Conversation Context

**When:** 2025-07-15 (3 months ago)

**What was discussed:**
صارف نے عید کی تیاریوں کے بارے میں بات کی۔ خاندان کے 
ساتھ celebrate کرنے کا plan تھا۔

**Key topics:** عید, خاندان, تہوار

*Older conversation - use only if user brings up related topics.*
```

### User Message:
```
"سلام، کیا حال؟"
```

### LLM Response (Smart):
```
"السلام علیکم! بہت دنوں بعد! کیسے ہیں؟ سب ٹھیک؟"
```
✅ Acknowledges time gap, doesn't mention 3-month-old Eid discussion

### IF User Brings It Up:
```
User: "اس بار عید کیسی گزری؟"
LLM: "واہ! عید کی بات ہو رہی ہے! پچھلی بار تو آپ خاندان 
     کے ساتھ منانے کا plan بنا رہے تھے، کیسی رہی؟"
```
✅ NOW references because user brought up the topic

---

## 📊 Summary of Behavior by Time

| Time Since | Guidance | Example Behavior |
|------------|----------|------------------|
| **< 1 hour** | "earlier today" | Direct reference, check on progress |
| **1-12 hours** | "X hours ago" | Freely reference, highly relevant |
| **Yesterday** | "yesterday" | Reference when topic aligns |
| **2-6 days** | "X days ago" | Selective reference |
| **1-3 weeks** | "X weeks ago" | Background context, don't force |
| **1-11 months** | "X months ago" | Only if user brings it up |
| **1+ years** | "X years ago" | Rare reference, very selective |

---

## 🎯 Smart Guidance Messages

### What LLM Sees:

**Recent (hours/today)**:
```
*Recent conversation - highly relevant. Reference naturally.*
```
→ LLM knows: Feel free to reference directly

**Yesterday/few days**:
```
*Recent conversation - reference when topic aligns.*
```
→ LLM knows: Check if current topic matches first

**Last week**:
```
*Last week - use for context, don't force if user wants to move on.*
```
→ LLM knows: Let user lead, use as background understanding

**Older**:
```
*Older conversation - use only if user brings up related topics.*
```
→ LLM knows: Don't mention unless user explicitly brings it up

---

## ✅ Benefits

1. **Smart temporal awareness** - LLM knows if summary is fresh or stale
2. **Automatic relevance assessment** - No manual prompting needed
3. **Natural conversation flow** - References when appropriate
4. **Avoids awkwardness** - Doesn't bring up month-old topics randomly
5. **Contextual continuity** - Acknowledges time gap naturally

---

## 🎉 Complete Example Flow

```
Database → format_summary_for_context() → Calculate time difference
    ↓
"2025-10-14 (2 hours ago)"
    ↓
"Recent conversation - highly relevant. Reference naturally."
    ↓
LLM sees time context → Adjusts behavior → Smart references!
```

**Result**: The LLM automatically knows how aggressively to use the summary based on how recent it is! 🧠

