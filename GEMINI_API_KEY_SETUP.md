# How to Get a Google Gemini API Key

## Step 1: Go to Google AI Studio

Visit [Google AI Studio](https://aistudio.google.com/app/apikey)

## Step 2: Sign In

- Sign in with your Google account
- If you don't have a Google account, create one at [accounts.google.com](https://accounts.google.com)

## Step 3: Create API Key

1. Click **"Get API Key"** or **"Create API Key"** button
2. You may be asked to create a new Google Cloud project (or select an existing one)
3. The API key will be generated and displayed

## Step 4: Copy Your API Key

- Copy the API key immediately (it starts with something like `AIza...`)
- ⚠️ **Important**: You won't be able to see the full key again after closing the dialog
- Store it securely

## Step 5: Set Environment Variable

### For Local Development:

```bash
export GOOGLE_API_KEY="your_api_key_here"
```

Or create a `.env` file:
```
GOOGLE_API_KEY=your_api_key_here
```

### For Render Deployment:

1. Go to your Render dashboard
2. Select your service
3. Go to **Environment** tab
4. Add environment variable:
   - **Key**: `GOOGLE_API_KEY`
   - **Value**: Your API key (paste it here)
5. Save changes (service will redeploy automatically)

## Step 6: Verify

Test that your API key works:

```bash
python -c "import google.generativeai as genai; genai.configure(api_key='YOUR_KEY'); print('✅ API Key is valid!')"
```

## Free Tier Limits

Google Gemini API has a generous free tier:
- **gemini-1.5-flash**: 15 requests per minute (RPM), 1 million tokens per day
- **gemini-1.5-pro**: 2 requests per minute (RPM), 50,000 tokens per day

For this quiz solver, `gemini-1.5-flash` is recommended as it's faster and has higher rate limits.

## Troubleshooting

### Error: "API key not valid"
- Make sure you copied the entire key
- Check for extra spaces or newlines
- Regenerate the key if needed

### Error: "Quota exceeded"
- You've hit the free tier limits
- Wait a bit and try again, or upgrade to a paid plan

### Error: "Model not found"
- Make sure you're using a valid model name:
  - ✅ `gemini-1.5-flash` (recommended)
  - ✅ `gemini-1.5-pro`
  - ❌ `gemini-pro` (deprecated)

## Security Notes

⚠️ **Never commit your API key to Git!**

- Always use environment variables
- Add `.env` to `.gitignore`
- Use Render's environment variables for production

