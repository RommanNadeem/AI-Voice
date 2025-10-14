# How to Add a New Memory Category

## 🎯 Quick Answer

To add a new memory category (e.g., `EMOTION`), update **3 locations**:

---

## 📍 **Step 1: Update System Instructions** (agent.py)

### Location: Line ~297

**Find this:**
```python
- **Categories:** `FACT, PREFERENCE, INTEREST, GOAL, RELATIONSHIP, EXPERIENCE, PLAN, OPINION, STATE`
```

**Change to:**
```python
- **Categories:** `FACT, PREFERENCE, INTEREST, GOAL, RELATIONSHIP, EXPERIENCE, PLAN, OPINION, STATE, EMOTION`
```

---

## 📍 **Step 2: Update Tool Docstring** (agent.py)

### Location: Line ~562

**Find this:**
```python
category: Memory category - must be one of: FACT, GOAL, INTEREST, EXPERIENCE, 
          PREFERENCE, PLAN, RELATIONSHIP, OPINION
```

**Change to:**
```python
category: Memory category - must be one of: FACT, GOAL, INTEREST, EXPERIENCE, 
          PREFERENCE, PLAN, RELATIONSHIP, OPINION, STATE, EMOTION
```

---

## 📍 **Step 3: Update Context Loading** (agent.py)

### Location: Line ~1730

**Find this:**
```python
categories = ['FACT', 'PREFERENCE', 'GOAL', 'INTEREST', 'RELATIONSHIP', 'PLAN']
```

**Change to:**
```python
categories = ['FACT', 'PREFERENCE', 'GOAL', 'INTEREST', 'RELATIONSHIP', 'PLAN', 'EMOTION']
```

**Note**: This determines which categories are loaded into initial context. Don't add too many!

---

## 📍 **Step 4: Add Examples** (agent.py)

### Location: Line ~301-309

**Add example usage:**
```python
User: "آج میں بہت خوش ہوں"
→ storeInMemory("EMOTION", "current_mood", "خوش (happy)")
```

---

## 🎯 **Complete Example: Adding "EMOTION" Category**

### 1. System Instructions (line 297):
```python
- **Categories:** `FACT, PREFERENCE, INTEREST, GOAL, RELATIONSHIP, EXPERIENCE, PLAN, OPINION, STATE, EMOTION`
```

### 2. Tool Docstring (line 562):
```python
category: Memory category - must be one of: FACT, GOAL, INTEREST, EXPERIENCE, 
          PREFERENCE, PLAN, RELATIONSHIP, OPINION, STATE, EMOTION
```

### 3. Context Loading (line 1730):
```python
categories = ['FACT', 'PREFERENCE', 'GOAL', 'INTEREST', 'RELATIONSHIP', 'PLAN', 'EMOTION']
```

### 4. Add Examples (after line 309):
```python
User: "آج میں بہت خوش ہوں"
→ storeInMemory("EMOTION", "current_mood", "خوش (happy)")

User: "میں پریشان ہوں"
→ storeInMemory("EMOTION", "current_feeling", "پریشان (worried)")
```

---

## 📋 **Current Categories Explained**

| Category | Purpose | Examples |
|----------|---------|----------|
| `FACT` | Basic factual info | Name, age, location, job |
| `PREFERENCE` | Likes/dislikes | Favorite food, color, hobby |
| `INTEREST` | Activities they enjoy | Sports, reading, music |
| `GOAL` | Aspirations | Career goals, life plans |
| `RELATIONSHIP` | People in their life | Family, friends, colleagues |
| `EXPERIENCE` | Past events | Trips, achievements, stories |
| `PLAN` | Future plans | Upcoming events, intentions |
| `OPINION` | Views on topics | Beliefs, perspectives |
| `STATE` | Current status | Mood, health, situation |

---

## 💡 **Tips for New Categories**

### **Good Categories to Add**:
- `EMOTION` - Current emotional state
- `SKILL` - Abilities and talents
- `CHALLENGE` - Current struggles
- `ACHIEVEMENT` - Accomplishments
- `HABIT` - Regular behaviors
- `DREAM` - Aspirations and wishes

### **What Makes a Good Category**:
✅ **Distinct purpose** - Not overlapping with existing categories  
✅ **Frequently used** - Will be stored often  
✅ **Valuable context** - Helps understand user better  
✅ **Clear boundaries** - Easy to know when to use  

### **What to Avoid**:
❌ **Too similar to existing** - e.g., `LIKE` when you have `PREFERENCE`  
❌ **Too specific** - e.g., `FAVORITE_COLOR` (use PREFERENCE instead)  
❌ **Rarely used** - Won't add value  
❌ **Too broad** - e.g., `EVERYTHING` (not actionable)  

---

## ⚠️ **Important Notes**

### **Database Schema**:
The `memory` table schema is:
```sql
CREATE TABLE memory (
    id SERIAL PRIMARY KEY,
    user_id UUID REFERENCES profiles(user_id),
    category TEXT NOT NULL,
    key TEXT NOT NULL,
    value TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(user_id, category, key)
);
```

**No category validation in database** - you can add any category without schema changes! ✅

### **Context Budget**:
Don't load too many categories in Step 3! Current limit:
- 6 categories × 5 memories each = 30 memories max in context
- Adding more increases token usage
- Be selective about which categories to load at startup

---

## 🚀 **Quick Add Example**

Want to add `EMOTION` category? Here's the complete patch:

```python
# 1. agent.py line 297
- **Categories:** `FACT, PREFERENCE, INTEREST, GOAL, RELATIONSHIP, EXPERIENCE, PLAN, OPINION, STATE, EMOTION`

# 2. agent.py line 562
category: Memory category - must be one of: FACT, GOAL, INTEREST, EXPERIENCE, 
          PREFERENCE, PLAN, RELATIONSHIP, OPINION, STATE, EMOTION

# 3. agent.py line 1730 (optional - only if you want it in initial context)
categories = ['FACT', 'PREFERENCE', 'GOAL', 'INTEREST', 'RELATIONSHIP', 'PLAN', 'EMOTION']

# 4. agent.py after line 309 - Add examples
User: "میں بہت خوش ہوں"
→ storeInMemory("EMOTION", "current_mood", "خوش (happy)")
```

---

## ✅ **That's It!**

**No database changes needed** - just update the 3-4 locations in `agent.py`.

The new category will:
- ✅ Be available to `storeInMemory()` tool
- ✅ Work with `retrieveFromMemory()` tool
- ✅ Work with `searchMemories()` tool
- ✅ Be stored in database
- ✅ Be loaded in context (if added to categories list)

Want me to add a specific category for you? Let me know which one! 🎯

