# Firebase Firestore Database Schema

## Collections Structure

### 1. `users` Collection
Document ID: User UUID (from LiveKit identity)

```json
{
  "id": "4e3efa3d-d8fe-431e-a78f-4efffb0cf43a",
  "email": "user@example.com",
  "is_first_login": true,
  "created_at": "2025-01-05T10:00:00Z",
  "updated_at": "2025-01-05T10:00:00Z"
}
```

### 2. `user_profiles` Collection
Document ID: User UUID

```json
{
  "user_id": "4e3efa3d-d8fe-431e-a78f-4efffb0cf43a",
  "profile_text": "User profile summary...",
  "updated_at": "2025-01-05T10:00:00Z"
}
```

### 3. `memories` Collection
Document ID: `{user_id}_{key}` (e.g., "4e3efa3d-d8fe-431e-a78f-4efffb0cf43a_user_input_1703123456789")

```json
{
  "user_id": "4e3efa3d-d8fe-431e-a78f-4efffb0cf43a",
  "category": "FACT",
  "key": "user_input_1703123456789",
  "value": "User's input text...",
  "created_at": "2025-01-05T10:00:00Z",
  "updated_at": "2025-01-05T10:00:00Z"
}
```

### 4. `onboarding_details` Collection
Document ID: User UUID

```json
{
  "user_id": "4e3efa3d-d8fe-431e-a78f-4efffb0cf43a",
  "full_name": "John Doe",
  "occupation": "Software Engineer",
  "interests": ["AI", "Technology", "Music"],
  "created_at": "2025-01-05T10:00:00Z"
}
```

## Security Rules

### Firestore Security Rules
```javascript
rules_version = '2';
service cloud.firestore {
  match /databases/{database}/documents {
    // Users can only access their own data
    match /users/{userId} {
      allow read, write: if request.auth != null && request.auth.uid == userId;
    }
    
    match /user_profiles/{userId} {
      allow read, write: if request.auth != null && request.auth.uid == userId;
    }
    
    match /memories/{memoryId} {
      allow read, write: if request.auth != null && 
        resource.data.user_id == request.auth.uid;
    }
    
    match /onboarding_details/{userId} {
      allow read, write: if request.auth != null && request.auth.uid == userId;
    }
  }
}
```

## Migration Steps

1. **Create Firebase Project**
   - Go to Firebase Console
   - Create new project
   - Enable Firestore Database
   - Enable Authentication

2. **Set up Service Account**
   - Go to Project Settings > Service Accounts
   - Generate new private key
   - Download JSON file
   - Extract values for environment variables

3. **Configure Security Rules**
   - Go to Firestore > Rules
   - Replace default rules with the rules above

4. **Update Environment Variables**
   - Copy firebase.env.example to .env
   - Fill in your Firebase project details

5. **Test Migration**
   - Run: `python agent_firebase.py`
   - Test memory saving functionality
   - Verify data appears in Firestore console
