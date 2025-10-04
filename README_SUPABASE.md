# Companion Agent - Supabase Integration

This version of the Companion Agent uses Supabase as the backend database, providing a modern, API-based approach with built-in authentication, real-time features, and automatic API generation.

## 🚀 Quick Start

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Create Supabase Project
1. Go to [Supabase](https://supabase.com)
2. Create a new project
3. Get your project URL and anon key from Settings → API

### 3. Setup Database Tables
```bash
# Run setup script
python setup_supabase.py
```

### 4. Configure Environment Variables
Create a `.env` file with:
```env
# OpenAI Configuration
OPENAI_API_KEY=your_openai_api_key_here

# Supabase Configuration
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_ANON_KEY=your-anon-key-here
```

### 5. Run the Agent
```bash
python agent.py
```

## 📊 Database Schema

### Memory Table
```sql
CREATE TABLE memory (
    id BIGSERIAL PRIMARY KEY,
    category VARCHAR(50) NOT NULL,
    key VARCHAR(255) NOT NULL,
    value TEXT NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(category, key)
);
```

### Profiles Table
```sql
CREATE TABLE profiles (
    user_id VARCHAR(255) PRIMARY KEY,
    profile_text TEXT NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
```

## 🔄 Migration from PostgreSQL

If you have existing PostgreSQL data, use the migration script:

```bash
python migrate_to_supabase.py
```

This will migrate all data from PostgreSQL to Supabase.

## 🧪 Testing

Test the Supabase integration:

```bash
python test_supabase.py
```

## 🔧 Key Features of Supabase Integration

### 1. **Modern API-First Approach**
- Uses Supabase Python client for all database operations
- Automatic API generation and documentation
- Built-in authentication and authorization

### 2. **Advanced Querying**
Based on the [Supabase Python documentation](https://supabase.com/docs/reference/python/select), you can use:

```python
# Select specific columns
response = supabase.table('memory').select('category, key').execute()

# Filter data
response = supabase.table('memory').select('*').eq('category', 'FACT').execute()

# Count results
response = supabase.table('memory').select('*', count='exact').execute()

# Order results
response = supabase.table('memory').select('*').order('created_at', desc=True).execute()

# Limit results
response = supabase.table('memory').select('*').limit(10).execute()
```

### 3. **Real-time Features**
- Automatic real-time subscriptions
- Live data updates across clients
- WebSocket-based real-time communication

### 4. **Built-in Security**
- Row Level Security (RLS) support
- Automatic API key management
- Built-in authentication system

## 📈 Benefits of Supabase

- **API-First**: No need to write SQL queries manually
- **Real-time**: Built-in real-time subscriptions
- **Authentication**: Integrated auth system
- **Scalability**: Automatic scaling and performance optimization
- **Developer Experience**: Excellent tooling and documentation
- **Open Source**: Based on PostgreSQL with additional features

## 🛠️ Supabase-Specific Methods

The MemoryManager now includes Supabase-specific features:

```python
# Store data with upsert
memory_manager.store("FACT", "user_input", "Hello world")

# Retrieve with filtering
value = memory_manager.retrieve("FACT", "user_input")

# Get all data
all_data = memory_manager.retrieve_all()

# Delete data
memory_manager.forget("FACT", "user_input")
```

## 🔒 Security Features

### Row Level Security (RLS)
Enable RLS in Supabase for additional security:

```sql
-- Enable RLS
ALTER TABLE memory ENABLE ROW LEVEL SECURITY;
ALTER TABLE profiles ENABLE ROW LEVEL SECURITY;

-- Create policies (example)
CREATE POLICY "Users can view their own data" ON memory
    FOR SELECT USING (auth.uid()::text = user_id);
```

### API Key Management
- Use environment variables for sensitive data
- Rotate API keys regularly
- Use service role key only on server-side

## 📝 Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| `SUPABASE_URL` | Your Supabase project URL | Yes |
| `SUPABASE_ANON_KEY` | Your Supabase anon key | Yes |
| `OPENAI_API_KEY` | OpenAI API key | Yes |

## 🔧 Troubleshooting

### Connection Issues
- Verify SUPABASE_URL and SUPABASE_ANON_KEY are correct
- Check Supabase project status
- Ensure tables exist in Supabase dashboard

### Permission Issues
- Check RLS policies if enabled
- Verify API key permissions
- Check network access settings

### Migration Issues
- Ensure PostgreSQL connection is accessible
- Verify table schemas match
- Check data types compatibility

## 🚀 Advanced Features

### Real-time Subscriptions
```python
# Subscribe to memory changes
def handle_memory_changes(payload):
    print(f"Memory changed: {payload}")

supabase.table('memory').on('INSERT', handle_memory_changes).subscribe()
```

### Batch Operations
```python
# Batch insert
data = [{'category': 'FACT', 'key': f'item_{i}', 'value': f'value_{i}'} for i in range(10)]
supabase.table('memory').insert(data).execute()
```

### Advanced Filtering
```python
# Complex queries
response = supabase.table('memory').select('*').eq('category', 'FACT').gte('created_at', '2024-01-01').execute()
```

## 📚 Resources

- [Supabase Python Documentation](https://supabase.com/docs/reference/python/select)
- [Supabase Dashboard](https://supabase.com/dashboard)
- [Supabase Community](https://github.com/supabase/supabase)
